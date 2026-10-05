"""app/nace_extraction.py ve scripts/backfill_nace_llm.py testleri.

LLM çağrısı sahte istemciyle taklit edilir (ağ yok). Test edilen şey modelin
zekâsı değil, ÇIKTI GÜVENLİK AĞLARIDIR: model ne dönerse dönsün yanlış sektör
kilidi veritabanına yazılmamalı.
"""
import asyncio
import importlib
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


def _cevap(tur, kodlar=(), haric=(), tip="BELIRSIZ", not_="gerekçe"):
    return {"analiz_notu": not_, "kapsam_turu": tur, "yararlanici_tipi": tip,
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
    k = NaceKapsami(analiz_notu="x", kapsam_turu="SEKTOR_KISITLI", yararlanici_tipi="URETICI")
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
    assert sonuc.rows == [{"tesvik_id": 3, "nace_prefix": "10.83", "kaynak": "llm_extraction"}]


def test_haric_tutulanlar_raporlanir_ama_satir_olmaz():
    istemci = SahteIstemci(_cevap("YATAY", haric=[_kod("K", "finans kuruluşları hariç")]))
    sonuc = run(extract_nace_scope(YATAY_METIN, client=istemci))
    assert sonuc.rows == []
    assert [h.nace_prefix for h in sonuc.kapsam.haric_tutulan_nace_kodlari] == ["K"]


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
    satirlar, _, _ = satirlari_uret(5, k, "Yalnızca gıda üreten işletmeler")
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


def test_betik_yatay_cakismayi_raporlar_silme_bayragiyla_siler(betik, db_session):
    t = _program(db_session, "İmalat Sanayii Destek Paketi", "https://t/i",
                 ozet="İmalat, turizm, bilişim dahil tüm sektörler başvurabilir.")
    db_session.add(TesvikNace(tesvik_id=t.id, nace_prefix="C", kaynak="otomatik:imalat_baslik:imalat"))
    db_session.commit()

    s1 = run(betik.calistir(db_session, client=SahteIstemci(_cevap("YATAY"))))
    assert s1["cakisma"] == 1 and s1["silinen"] == 0
    assert db_session.query(TesvikNace).count() == 1, "varsayılanda otomatik satıra dokunulmaz"

    s2 = run(betik.calistir(db_session, client=SahteIstemci(_cevap("YATAY")),
                            otomatik_yatay_ise_sil=True))
    assert s2["silinen"] == 1 and db_session.query(TesvikNace).count() == 0
