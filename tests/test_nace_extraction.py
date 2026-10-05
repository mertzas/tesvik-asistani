"""app/nace_extraction.py ve scripts/backfill_nace_llm.py testleri.

LLM çağrısı sahte istemciyle taklit edilir (ağ yok). Test edilen şey modelin
zekâsı değil, ÇIKTI GÜVENLİK AĞLARIDIR: model ne dönerse dönsün yanlış sektör
kilidi veritabanına yazılmamalı.
"""
import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import nace_extraction as ne
from app.models import Tesvik, TesvikNace
from app.nace_extraction import (
    ExtractionError,
    KapsamTuru,
    NaceKapsami,
    SYSTEM_PROMPT,
    extract_nace_scope,
    kaynak_metni,
    satirlari_uret,
)

KOK = Path(__file__).resolve().parent.parent


def run(coro):
    return asyncio.run(coro)


class SahteIstemci:
    """messages.create çağrılarını kaydeder; sırayla hazır tool_use cevapları döner."""

    def __init__(self, *cevaplar, hata=None):
        self.cevaplar = list(cevaplar)
        self.cagrilar = []
        self.hata = hata
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        self.cagrilar.append(kw)
        if self.hata and "temperature" in kw:
            raise self.hata
        ham = self.cevaplar.pop(0)
        blok = SimpleNamespace(type="tool_use", name=ne.TOOL_ADI, input=ham)
        return SimpleNamespace(content=[blok])


def _kod(prefix, dayanak, guven=0.95):
    return {"nace_prefix": prefix, "guven_skoru": guven, "dayanak_metin": dayanak}


def _cevap(tur, kodlar=(), haric=(), tip="BELIRSIZ", not_="gerekçe", guven=0.95):
    return {"analiz_notu": not_, "kapsam_turu": tur, "kapsam_guven": guven, "yararlanici_tipi": tip,
            "hedef_nace_kodlari": list(kodlar), "haric_tutulan_nace_kodlari": list(haric)}


YATAY_METIN = {"id": 1, "baslik": "KOBİ Destek Paketi",
               "aciklama": "İmalat, turizm, bilişim dahil tüm sektörlerdeki KOBİ'ler başvurabilir."}
CAY_URETICI = {"id": 2, "baslik": "Çay Alımı Destek Primi",
               "aciklama": "Prim, yaş çay üreticilerine (müstahsil) yaş çay teslimi karşılığında ödenir."}
CAY_FABRIKA = {"id": 3, "baslik": "Çay İşleme Tesisi Modernizasyonu",
               "aciklama": "Hibe, çay işleme tesislerinin makine yenilemesi için verilir."}


# ------------------------------------------------- kritik: yanlış kilit koruması
def test_tum_sektorler_ifadesi_yatay_ve_satirsiz():
    istemci = SahteIstemci(_cevap("YATAY", tip="BELIRSIZ"))
    sonuc = run(extract_nace_scope(YATAY_METIN, client=istemci))
    assert sonuc.kapsam_turu is KapsamTuru.YATAY and sonuc.rows == []


def test_model_yataya_kod_eklerse_temizlenir():
    """Model "imalat dahil" ifadesinden C'yi çıkarıp YATAY ile birlikte dönerse
    kilit yazılmamalı."""
    istemci = SahteIstemci(_cevap("YATAY", [_kod("C", "İmalat, turizm, bilişim dahil")]))
    sonuc = run(extract_nace_scope(YATAY_METIN, client=istemci))
    assert sonuc.rows == [] and sonuc.kapsam.hedef_nace_kodlari == []


def test_kaynakta_olmayan_dayanak_reddedilir():
    """Güvenlik ağı dayanağın VARLIĞINI doğrular, anlamını değil (anlam prompt'ta).
    Kaynakta olmayan alıntı kesin reddedilir."""
    istemci = SahteIstemci(_cevap("SEKTOR_KISITLI", [_kod("C", "yalnızca imalat firmaları")]))
    sonuc = run(extract_nace_scope(YATAY_METIN, client=istemci))
    assert sonuc.rows == []
    assert sonuc.kapsam_turu is KapsamTuru.BELIRSIZ
    assert any("kaynakta bulunamadı" in s for _, s in sonuc.reddedilenler)


def test_dusuk_guven_reddedilir():
    istemci = SahteIstemci(_cevap("SEKTOR_KISITLI",
                                  [_kod("01.27", "yaş çay üreticilerine", guven=0.6)]))
    sonuc = run(extract_nace_scope(CAY_URETICI, client=istemci))
    assert sonuc.rows == [] and sonuc.kapsam_turu is KapsamTuru.BELIRSIZ


def test_sektor_kisitli_ama_kodsuz_belirsize_duser():
    k = NaceKapsami(analiz_notu="x", kapsam_turu="SEKTOR_KISITLI", kapsam_guven=0.9, yararlanici_tipi="URETICI")
    assert k.kapsam_turu is KapsamTuru.BELIRSIZ


# ----------------------------------------------- tedarik zinciri / yararlanıcı
def test_cay_alimi_ureticiye_giderse_tarim():
    istemci = SahteIstemci(_cevap("SEKTOR_KISITLI",
                                  [_kod("01.27", "yaş çay üreticilerine (müstahsil)")], tip="URETICI"))
    sonuc = run(extract_nace_scope(CAY_URETICI, client=istemci))
    assert [r["nace_prefix"] for r in sonuc.rows] == ["01.27"]
    assert sonuc.kapsam.yararlanici_tipi.value == "URETICI"


def test_cay_isleme_tesisi_imalata_baglanir():
    istemci = SahteIstemci(_cevap("SEKTOR_KISITLI",
                                  [_kod("10.83", "çay işleme tesislerinin makine yenilemesi")],
                                  tip="ISLEYICI_TESIS"))
    sonuc = run(extract_nace_scope(CAY_FABRIKA, client=istemci))
    assert sonuc.rows == [{"tesvik_id": 3, "nace_prefix": "10.83", "kaynak": "llm_extraction",
                           "haric_mi": False}]


def test_yatay_programda_hariclar_haric_mi_satiri_olur():
    metin = dict(YATAY_METIN, aciklama="Tüm sektörlerdeki KOBİ'ler başvurabilir; finans kuruluşları hariçtir.")
    istemci = SahteIstemci(_cevap("YATAY", haric=[_kod("L", "finans kuruluşları hariçtir")]))
    sonuc = run(extract_nace_scope(metin, client=istemci))
    assert sonuc.rows == [{"tesvik_id": 1, "nace_prefix": "L", "kaynak": "llm_extraction", "haric_mi": True}]
    assert not sonuc.manuel_inceleme_gerekli


def test_dislama_kaniti_yetersizse_sessizce_atlanmaz_incelemeye_isaretlenir():
    """Kanıtsız dışlama yazılmaz AMA sessiz de kalmaz: aksi hâlde hariç kolun
    işletmesine tam uyum skoru verilirdi."""
    istemci = SahteIstemci(_cevap("YATAY", haric=[_kod("L", "bankalar kapsam dışıdır")]))  # metinde yok
    sonuc = run(extract_nace_scope(YATAY_METIN, client=istemci))
    assert sonuc.rows == [] and sonuc.manuel_inceleme_gerekli
    assert "L" in sonuc.inceleme_nedenleri[0]


IMALAT_HARIC = {"id": 4, "baslik": "Sanayi Yatırım Desteği",
                "aciklama": "Destek imalat sanayiine yöneliktir, ancak tütün ürünleri (12) ve silah-mühimmat "
                            "(25.4) imalatı kapsam dışıdır."}


def test_imalat_ve_alt_kol_dislamasi_birlikte_uretilir():
    istemci = SahteIstemci(_cevap("SEKTOR_KISITLI",
        [_kod("C", "Destek imalat sanayiine yöneliktir")],
        haric=[_kod("12", "tütün ürünleri (12)"), _kod("25.4", "silah-mühimmat (25.4) imalatı kapsam dışıdır")]))
    sonuc = run(extract_nace_scope(IMALAT_HARIC, client=istemci))
    assert [(r["nace_prefix"], r["haric_mi"]) for r in sonuc.rows] == [
        ("C", False), ("12", True), ("25.4", True)]


def test_hedefin_altinda_olmayan_dislama_reddedilir_ve_incelemeye_duser():
    istemci = SahteIstemci(_cevap("SEKTOR_KISITLI",
        [_kod("10", "Destek imalat sanayiine yöneliktir")],
        haric=[_kod("12", "tütün ürünleri (12)")]))   # 12, "10"un altında değil
    sonuc = run(extract_nace_scope(IMALAT_HARIC, client=istemci))
    assert [r["nace_prefix"] for r in sonuc.rows] == ["10"]
    assert any("anlamsız dışlama" in sebep for _, sebep in sonuc.reddedilenler)
    assert sonuc.manuel_inceleme_gerekli


def test_ayni_kod_hem_hedef_hem_haric_celiskidir():
    istemci = SahteIstemci(_cevap("SEKTOR_KISITLI",
        [_kod("C", "Destek imalat sanayiine yöneliktir")],
        haric=[_kod("C", "imalat sanayiine yöneliktir")]))
    sonuc = run(extract_nace_scope(IMALAT_HARIC, client=istemci))
    assert [r["nace_prefix"] for r in sonuc.rows] == ["C"] and sonuc.manuel_inceleme_gerekli


# ------------------------------------------------------------- kod doğrulayıcı
@pytest.mark.parametrize("kod,beklenen", [
    ("C", "C"), ("C.10", "10"), ("10.71", "10.71"), ("1071", "10.71"), ("K.62", "62"),
])
def test_kod_normalizasyonu(kod, beklenen):
    assert ne.NaceKodu(nace_prefix=kod, guven_skoru=0.9, dayanak_metin="x").nace_prefix == beklenen


@pytest.mark.parametrize("kod", ["A.10", "J.62", "10.71.01", "ZZ", "", "99.99.99"])
def test_gecersiz_kod_reddedilir(kod):
    """Harf-bölüm uyuşmazlığı (A.10), Rev.2 harfi (J.62 -> Rev.2.1'de K) ve
    4 haneden uzun kodlar şemadan geçemez."""
    with pytest.raises(ValueError):
        ne.NaceKodu(nace_prefix=kod, guven_skoru=0.9, dayanak_metin="x")


def test_gecersiz_cikti_icin_modele_duzeltme_firsati_verilir():
    kotu = _cevap("SEKTOR_KISITLI", [_kod("A.10", "yaş çay üreticilerine")])
    iyi = _cevap("SEKTOR_KISITLI", [_kod("01.27", "yaş çay üreticilerine")])
    istemci = SahteIstemci(kotu, iyi)
    sonuc = run(extract_nace_scope(CAY_URETICI, client=istemci))
    assert len(istemci.cagrilar) == 2
    assert "doğrulamasından geçmedi" in istemci.cagrilar[1]["messages"][-1]["content"]
    assert [r["nace_prefix"] for r in sonuc.rows] == ["01.27"]


def test_iki_kez_gecersizse_belirsiz_ve_hata_doner_kilit_yok():
    kotu = _cevap("SEKTOR_KISITLI", [_kod("A.10", "yaş çay üreticilerine")])
    sonuc = run(extract_nace_scope(CAY_URETICI, client=SahteIstemci(kotu, kotu)))
    assert sonuc.rows == [] and sonuc.hata and sonuc.kapsam_turu is KapsamTuru.BELIRSIZ


# ----------------------------------------------------------- çağrı sözleşmesi
def test_temperature_sifir_ve_arac_zorunlu(monkeypatch):
    monkeypatch.setattr(ne, "_TEMPERATURE_REDDEDEN_MODELLER", set())
    istemci = SahteIstemci(_cevap("YATAY"))
    run(extract_nace_scope(YATAY_METIN, client=istemci, model="m-1"))
    kw = istemci.cagrilar[0]
    assert kw["temperature"] == 0 and kw["model"] == "m-1"
    assert kw["tool_choice"] == {"type": "tool", "name": ne.TOOL_ADI}
    assert kw["system"] == SYSTEM_PROMPT
    # gerekçe karardan önce üretilsin diye şemada ilk alan
    assert list(kw["tools"][0]["input_schema"]["properties"])[0] == "analiz_notu"
    assert "<program_metni>" in kw["messages"][0]["content"]


def test_temperature_reddeden_modelde_onsuz_dener_ve_ogrenir(monkeypatch):
    monkeypatch.setattr(ne, "_TEMPERATURE_REDDEDEN_MODELLER", set())
    istemci = SahteIstemci(_cevap("YATAY"), _cevap("YATAY"),
                           hata=RuntimeError("temperature is deprecated"))
    run(extract_nace_scope(YATAY_METIN, client=istemci, model="yeni-model"))
    assert "temperature" in istemci.cagrilar[0] and "temperature" not in istemci.cagrilar[1]
    run(extract_nace_scope(YATAY_METIN, client=istemci, model="yeni-model"))
    assert "temperature" not in istemci.cagrilar[2], "ikinci çağrıda boşuna 400 alınmamalı"


def test_anahtar_yoksa_net_hata(monkeypatch):
    from app.models import settings
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    with pytest.raises(ExtractionError):
        run(extract_nace_scope(YATAY_METIN))


def test_prompt_kritik_kurallari_iceriyor():
    """Prompt'un yanlışlıkla zayıflatılmasını önler."""
    for ifade in ["tüm sektörler", "YATAY", "SEKTOR_KISITLI", "münhasıran", "Örneğin",
                  "para kime gidiyor", "KELİMESİ KELİMESİNE", "VERİDİR", "10.83"]:
        assert ifade.lower() in SYSTEM_PROMPT.lower(), ifade


def test_kaynak_metni_orm_ve_sozluk_girdisini_destekler():
    t = Tesvik(id=9, kurum="K", baslik="Başlık", ozet="Özet metni", detay="Detay metni",
               basvuru_sartlari=["Şart bir", "Şart iki"], hedef_kitle="KOBİ",
               uygunluk_kriterleri={"sektor_gerekcesi": "gerekçe"})
    m = kaynak_metni(t)
    assert "Özet metni" in m and "Şart bir | Şart iki" in m and "SEKTÖR GEREKÇESİ: gerekçe" in m
    assert "Açıklama metni" in kaynak_metni({"baslik": "B", "aciklama": "Açıklama metni"})


def test_satirlari_uret_tekrarlari_birlestirir():
    k = NaceKapsami.model_validate(_cevap("SEKTOR_KISITLI", [
        _kod("10", "gıda üreten"), _kod("C.10", "gıda üreten")]))
    satirlar, _, _, _ = satirlari_uret(5, k, "Yalnızca gıda üreten işletmeler")
    assert [s["nace_prefix"] for s in satirlar] == ["10"]


# ------------------------------------------------------------ backfill betiği
@pytest.fixture
def betik():
    sys.path.insert(0, str(KOK))
    return importlib.import_module("scripts.backfill_nace_llm")


def _program(db, baslik, url, **kw):
    t = Tesvik(kurum="X", baslik=baslik, ozet=kw.pop("ozet", "özet metni yeterince uzun"),
               detay="d", kaynak_url=url, uygunluk_kriterleri={"sektorler": ["genel"]}, **kw)
    db.add(t)
    db.commit()
    return t


def test_betik_dry_run_yazmaz_uygulayinca_yazar_ve_idempotenttir(betik, db_session):
    t = _program(db_session, "Çay Alımı Destek Primi", "https://t/c",
                 ozet="Prim, yaş çay üreticilerine (müstahsil) ödenir.")
    cevap = _cevap("SEKTOR_KISITLI", [_kod("01.27", "yaş çay üreticilerine (müstahsil)")], tip="URETICI")

    kuru = run(betik.calistir(db_session, dry_run=True, client=SahteIstemci(cevap)))
    assert kuru["kisitli"] == 1 and db_session.query(TesvikNace).count() == 0

    gercek = run(betik.calistir(db_session, client=SahteIstemci(cevap)))
    assert gercek["yazilan_satir"] == 1 and db_session.query(TesvikNace).count() == 1

    ikinci = run(betik.calistir(db_session, client=SahteIstemci()))   # çağrı yapılmamalı
    assert ikinci["atlanan"] == 1 and ikinci["islenen"] == 0
    assert db_session.query(TesvikNace).count() == 1


def test_betik_elle_girilene_dokunmaz_ve_geri_alir(betik, db_session):
    t1 = _program(db_session, "Elle Program", "https://t/e")
    db_session.add(TesvikNace(tesvik_id=t1.id, nace_prefix="C", kaynak="elle"))
    t2 = _program(db_session, "Çay Alımı Destek Primi", "https://t/c2",
                  ozet="Prim, yaş çay üreticilerine (müstahsil) ödenir.")
    db_session.commit()
    cevap = _cevap("SEKTOR_KISITLI", [_kod("01.27", "yaş çay üreticilerine (müstahsil)")])

    run(betik.calistir(db_session, client=SahteIstemci(cevap)))
    kaynaklar = {(r.tesvik_id, r.nace_prefix): r.kaynak for r in db_session.query(TesvikNace)}
    assert kaynaklar == {(t1.id, "C"): "elle", (t2.id, "01.27"): "llm_extraction"}

    run(betik.calistir(db_session, geri_al=True))
    assert {(r.tesvik_id, r.nace_prefix) for r in db_session.query(TesvikNace)} == {(t1.id, "C")}


def test_betik_yatay_kilidi_ezer_ve_cakismayi_loglar(betik, db_session, tmp_path):
    t = _program(db_session, "İmalat Sanayii Destek Paketi", "https://t/i",
                 ozet="İmalat, turizm, bilişim dahil tüm sektörler başvurabilir.")
    db_session.add(TesvikNace(tesvik_id=t.id, nace_prefix="C", kaynak="otomatik:imalat_baslik:imalat"))
    db_session.commit()
    log = tmp_path / "log.jsonl"

    s1 = run(betik.calistir(db_session, client=SahteIstemci(_cevap("YATAY")), log_yolu=log))
    assert s1["cakisma"] == 1 and s1["ezilen_otomatik"] == 1
    assert db_session.query(TesvikNace).count() == 0
    kayit = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert kayit["cakisma"]["tur"] == "yatay_kilidi_kaldirildi" and kayit["cakisma"]["aksiyon"] == "ezildi"


def test_betik_dusuk_guvenli_yatay_otomatik_kilidi_ezmez(betik, db_session):
    t = _program(db_session, "İmalat Sanayii Destek Paketi", "https://t/i2")
    db_session.add(TesvikNace(tesvik_id=t.id, nace_prefix="C", kaynak="otomatik:imalat_baslik:imalat"))
    db_session.commit()
    run(betik.calistir(db_session, client=SahteIstemci(_cevap("YATAY", guven=0.4))))
    assert db_session.query(TesvikNace).count() == 1


def test_betik_belirsizde_otomatik_kilit_korunur_ve_loglanir(betik, db_session, tmp_path):
    t = _program(db_session, "İmalat Sanayii Destek Paketi", "https://t/i3")
    db_session.add(TesvikNace(tesvik_id=t.id, nace_prefix="C", kaynak="otomatik:imalat_baslik:imalat"))
    db_session.commit()
    log = tmp_path / "l.jsonl"
    run(betik.calistir(db_session, client=SahteIstemci(_cevap("BELIRSIZ", guven=0.3)), log_yolu=log))
    assert db_session.query(TesvikNace).count() == 1
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["cakisma"]["tur"] == "korundu_belirsiz"


def test_betik_kapsam_daralmasi_kaba_kilidi_ince_kodla_degistirir(betik, db_session, tmp_path):
    """Çay Alımı: başlık-regex'i kaba kilit bastı, LLM metinden 10.83'ü güvenle buldu."""
    t = _program(db_session, "ÇAY ALIMI DESTEK PAKETİ", "https://t/c3",
                 ozet="Müstahsilden yaş çay satın alan işletmelere destek verilir.")
    db_session.add(TesvikNace(tesvik_id=t.id, nace_prefix="C", kaynak="otomatik:imalat_baslik:x"))
    db_session.commit()
    log = tmp_path / "c.jsonl"
    cevap = _cevap("SEKTOR_KISITLI", [_kod("10.83", "yaş çay satın alan işletmelere")], tip="ISLEYICI_TESIS")
    run(betik.calistir(db_session, client=SahteIstemci(cevap), log_yolu=log))
    satirlar = {(r.nace_prefix, r.kaynak) for r in db_session.query(TesvikNace)}
    assert satirlar == {("10.83", "llm_extraction")}, "kaba otomatik kilit silinmeli"
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["cakisma"]["tur"] == "kapsam_daralmasi"


def test_betik_ayni_kod_ise_kaynak_yukseltilir_cift_satir_olmaz(betik, db_session):
    t = _program(db_session, "TURİZM DESTEK PAKETİ", "https://t/t",
                 ozet="Turizm sektöründe faaliyet gösteren işletmelere verilir.")
    db_session.add(TesvikNace(tesvik_id=t.id, nace_prefix="I", kaynak="otomatik:turizm_baslik:turizm"))
    db_session.commit()
    cevap = _cevap("SEKTOR_KISITLI", [_kod("I", "Turizm sektöründe faaliyet gösteren işletmelere")])
    run(betik.calistir(db_session, client=SahteIstemci(cevap)))
    assert [(r.nace_prefix, r.kaynak) for r in db_session.query(TesvikNace)] == [("I", "llm_extraction")]


def test_betik_supersede_yok_bayragi_sadece_raporlar(betik, db_session):
    t = _program(db_session, "İmalat Sanayii Destek Paketi", "https://t/i4")
    db_session.add(TesvikNace(tesvik_id=t.id, nace_prefix="C", kaynak="otomatik:imalat_baslik:imalat"))
    db_session.commit()
    s = run(betik.calistir(db_session, supersede=False, client=SahteIstemci(_cevap("YATAY"))))
    assert s["cakisma"] == 1 and db_session.query(TesvikNace).count() == 1


def test_betik_haric_satirini_yazar(betik, db_session):
    _program(db_session, "Sanayi Yatırım Desteği", "https://t/s",
             ozet="Destek imalat sanayiine yöneliktir, ancak tütün ürünleri (12) kapsam dışıdır.")
    cevap = _cevap("SEKTOR_KISITLI", [_kod("C", "Destek imalat sanayiine yöneliktir")],
                   haric=[_kod("12", "tütün ürünleri (12) kapsam dışıdır")])
    s = run(betik.calistir(db_session, client=SahteIstemci(cevap)))
    assert s["yazilan_satir"] == 1 and s["haric_satir"] == 1
    assert {(r.nace_prefix, r.haric_mi) for r in db_session.query(TesvikNace)} == {("C", False), ("12", True)}


@pytest.mark.parametrize("eski,yeni,yatay,beklenen", [
    (["C"], [], True, "yatay_kilidi_kaldirildi"),
    (["A"], ["10.83"], False, "sektor_degisimi"),
    (["C"], ["10.83"], False, "kapsam_daralmasi"),
    (["10.83"], ["C"], False, "kapsam_genislemesi"),
    (["C"], ["C"], False, "ayni_kod_kaynak_yukseltildi"),
    (["10", "55"], ["10.83", "62"], False, "karisik_degisim"),
])
def test_cakisma_siniflandirmasi(betik, eski, yeni, yatay, beklenen):
    assert betik.cakisma_turu(eski, yeni, yatay) == beklenen


# --------------------------------------------- kazıma gürültüsü temizleyici
MENU = "\n".join(["Bölgesel Odaklı Kobi Destek Paketi", "Döviz Kazandırıcı Faaliyetleri Destek Paketi",
                  "Girişimci Destek Paketi", "Kadın Girişimci Destek Paketi", "Teknoloji Destek Paketi",
                  "Dijital Dönüşüm Destek Paketi", "Eğitim Destek Paketi", "Kefalet Süreçleri",
                  "Vadeler ve Limitler", "Bilgi Merkezi"])
AGAC = "\n".join(["— Özkaynak Kefaletlerimiz", "—— Banka Kredileri >", "——— TOBB Nefes Kredisi 2026 Destek Programı"])
KGF_GURULTULU = (
    "İmalat Sanayii Destek Paketi\n" + MENU + "\nPlease select your page\nAnasayfa\nHakkımızda\n" + AGAC +
    "\n\n\n\nBuradasınız: Anasayfa / Ürünlerimiz / Hazine Destekli Kefaletler\n"
    "İmalat Sanayii Destek Paketi\nÜrün Açıklaması\n"
    "Makine imalatı, elektrik-elektronik sektörü, otomotiv tedarik sanayi, kimyasal madde imalatı "
    "sektörlerinde faaliyet gösteren tüm KOBİ ve KOBİ Dışı işletmelerin finansmana erişiminin "
    "kolaylaştırılması amaçlanmaktadır.\nKefalet İçin Kullanılan Kaynak\nHazine Fonu\n"
    "© 2026 KGF Tüm hakları saklıdır\nÇerez politikası")


def test_temizleyici_menu_cop_ve_footeri_atar_icerigi_korur():
    t = ne.clean_grant_text(KGF_GURULTULU, baslik="İmalat Sanayii Destek Paketi")
    assert "Makine imalatı" in t and "finansmana erişiminin" in t and "Hazine Fonu" in t
    for cop in ["Please select your page", "Özkaynak Kefaletlerimiz", "Kadın Girişimci Destek Paketi",
                "Tüm hakları saklıdır", "Çerez politikası", "Buradasınız"]:
        assert cop not in t, cop
    assert "\n\n\n" not in t and len(t) < len(KGF_GURULTULU) / 2


def test_temizleyici_basliksiz_de_menu_serisini_ve_agaci_siler():
    t = ne.clean_grant_text(MENU + "\n" + AGAC + "\nProgram yalnızca KOBİ'lere yöneliktir.")
    assert t == "Program yalnızca KOBİ'lere yöneliktir."


def test_temizleyici_sart_ve_nace_listesini_bozmaz():
    metin = ("Başvuru Şartları\nİşletmenin KOBİ olması\nYalnızca aşağıdaki sektörlerde faaliyet göstermesi\n"
             "Gıda Maddeleri İmalatı 10.71\nİçecek İmalatı 11.07\nTekstil Ürünleri İmalatı 13.10\n"
             "Giyim Eşyası İmalatı 14.13\nMobilya İmalatı 31.01\nKâğıt Ürünleri İmalatı 17.21\n"
             "Plastik Ürünler İmalatı 22.29\nMetal Eşya İmalatı 25.99\nNACE listesi EK-3'te yer alır.")
    assert ne.clean_grant_text(metin) == metin, "NACE kodlu satırlar menü sayılmamalı"


def test_temizleyici_bos_ve_none():
    assert ne.clean_grant_text(None) == "" and ne.clean_grant_text("  \n ") == ""


def test_imalat_sanayii_gurultulu_metin_modele_temiz_gider_ve_dayanak_dogrulanir():
    """GERÇEK OLAY: 12K karakterlik KGF menü dökümü yüzünden model BELIRSIZ dönmüştü.
    Temizlenmiş metinde asıl açıklama kalmalı ve şartlar kesilmemeli."""
    tesvik = {"id": 158, "baslik": "İmalat Sanayii Destek Paketi", "detay": KGF_GURULTULU,
              "basvuru_sartlari": ["Yatırım kredisi tutarı yatırım tutarının %70'ini aşamaz."]}
    gonderilen = ne.kaynak_metni(tesvik)
    assert "Özkaynak Kefaletlerimiz" not in gonderilen and "Makine imalatı" in gonderilen
    assert "BAŞVURU ŞARTLARI: Yatırım kredisi" in gonderilen

    cevap = _cevap("SEKTOR_KISITLI", [_kod("C", "faaliyet gösteren tüm KOBİ ve KOBİ Dışı işletmelerin")],
                   tip="ISLEYICI_TESIS")
    istemci = SahteIstemci(cevap)
    sonuc = run(extract_nace_scope(tesvik, client=istemci))
    assert [r["nace_prefix"] for r in sonuc.rows] == ["C"]
    assert "Özkaynak Kefaletlerimiz" not in istemci.cagrilar[0]["messages"][0]["content"]


def test_uzun_govde_sartlari_kesmez():
    uzun = "Program açıklaması cümlesi burada yer alır. " * 400
    m = ne.kaynak_metni({"baslik": "B", "aciklama": uzun, "basvuru_sartlari": ["ÖNEMLİ ŞART METNİ"]})
    assert "ÖNEMLİ ŞART METNİ" in m and len(m) <= ne.EN_COK_METIN_KARAKTER


def test_prompt_gurultu_ve_dislama_talimatlarini_iceriyor():
    for ifade in ["web kazıma kaynaklı gürültü", "arayüz metinlerini", "haric_tutulan_nace_kodlari",
                  "tütün", "25.4", "kapsam_guven", "yararlanıcı GRUBUNA"]:
        assert ifade in SYSTEM_PROMPT, ifade
