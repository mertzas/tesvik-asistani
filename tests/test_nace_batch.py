"""Yasal metin temizliği, kalıcı YATAY kararı, log özeti/kapı ve logdan oynatma."""
import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app import nace_extraction as ne
from app.models import Tesvik, TesvikNace

KOK = Path(__file__).resolve().parent.parent


def run(coro):
    return asyncio.run(coro)


class SahteIstemci:
    def __init__(self, *cevaplar):
        self.cevaplar = list(cevaplar)
        self.cagrilar = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        self.cagrilar.append(kw)
        blok = SimpleNamespace(type="tool_use", name=ne.TOOL_ADI, input=self.cevaplar.pop(0))
        return SimpleNamespace(content=[blok])


def _cevap(tur, kodlar=(), haric=(), guven=0.95):
    return {"analiz_notu": "g", "kapsam_turu": tur, "kapsam_guven": guven,
            "yararlanici_tipi": "BELIRSIZ", "hedef_nace_kodlari": list(kodlar),
            "haric_tutulan_nace_kodlari": list(haric)}


def _kod(prefix, dayanak, guven=0.95):
    return {"nace_prefix": prefix, "guven_skoru": guven, "dayanak_metin": dayanak}


@pytest.fixture
def betik():
    sys.path.insert(0, str(KOK))
    return importlib.import_module("scripts.backfill_nace_llm")


@pytest.fixture
def ozet():
    sys.path.insert(0, str(KOK))
    return importlib.import_module("scripts.nace_log_ozet")


def _program(db, baslik, url, ozet_metni="Açıklama metni yeterince uzun bir cümledir."):
    t = Tesvik(kurum="X", baslik=baslik, ozet=ozet_metni, detay="d", kaynak_url=url,
               uygunluk_kriterleri={"sektorler": ["genel"]})
    db.add(t)
    db.commit()
    return t


# ------------------------------------------- 1) yasal metin / footer temizliği
FOOTER = ("Kişisel Verilerin Korunması\nAydınlatma Metinleri >\n"
          "Çalışan Adayları İçin Kişisel Verilerin İşlenmesine İlişkin Aydınlatma Metni\n"
          "Ziyaretçiler Ve Kapalı Devre Kamera Sistemi (Cctv) Kullanımı İçin Kişisel Verilerin "
          "İşlenmesine İlişkin Aydınlatma Metni\nKişisel Verileri Saklama ve İmha Politikası\n"
          "Bilgi Toplumu Hizmetleri\nKGF Bilgi Güvenliği Politikası\nÇerez Politikası\n"
          "Gizlilik Bildirimi\nKVKK Aydınlatma Metni\nSite Haritası\nKullanım Koşulları")
NACE_LISTESI = ("Desteklenen faaliyetler\n28 Makine ve ekipman imalatı\n27 Elektrikli teçhizat imalatı\n"
                "27.32 Diğer elektronik ve elektrik telleri ve kabloları\n21 Temel eczacılık ürünleri\n"
                "29 Motorlu kara taşıtı imalatı\n20 Kimyasalların imalatı")


def test_yasal_footer_temizlenir_nace_listesi_korunur():
    metin = NACE_LISTESI + "\n" + FOOTER
    t = ne.clean_grant_text(metin)
    assert t == NACE_LISTESI, t
    for kod in ["28 Makine", "27.32", "21 Temel", "29 Motorlu", "20 Kimyasalların"]:
        assert kod in t


def test_footer_icindeki_kisa_nace_satiri_korunur():
    """Footer'a bitişik bile olsa NACE içeren satır silinmez."""
    t = ne.clean_grant_text("Aydınlatma Metni 10.71\nKVKK Aydınlatma Metni")
    assert t == "Aydınlatma Metni 10.71"


def test_sart_cumlesi_icinde_kvkk_gecmesi_silinmez():
    cumle = "Başvuru sahibi, KVKK kapsamında hazırlanan aydınlatma metnini onaylamalıdır."
    assert ne.clean_grant_text(cumle) == cumle
    uzun = "Başvuru formundaki kişisel verilerin korunması yükümlülüğü yararlanıcıya aittir ve aksi halde destek iptal edilir"
    assert ne.clean_grant_text(uzun) == uzun, "uzun satır (>18 kelime) yasal başlık sayılmaz"


def test_gercek_kgf_kaydi_aydinlatma_sizintisi_kalmaz():
    """İmalat Sanayii paketinde ilk 5000 karakterde hâlâ aydınlatma satırı sızıyordu."""
    metin = ("İmalat Sanayii Destek Paketi\n" + FOOTER + "\nÜrün Açıklaması\nMakine imalatı, otomotiv tedarik sanayi "
             "sektörlerinde faaliyet gösteren KOBİ'lerin finansmana erişimi amaçlanmaktadır.")
    t = ne.clean_grant_text(metin, baslik="İmalat Sanayii Destek Paketi")
    assert "Aydınlatma" not in t and "Çerez" not in t and "Makine imalatı" in t


# --------------------------------------------- 2) YATAY kalıcılığı / maliyet
def test_yatay_karar_kalici_ikinci_kosuda_api_cagrilmaz(betik, db_session):
    t = _program(db_session, "KGF Genel Destek", "https://t/y")
    istemci = SahteIstemci(_cevap("YATAY"))
    s1 = run(betik.calistir(db_session, client=istemci))
    assert s1["yatay"] == 1 and len(istemci.cagrilar) == 1
    db_session.refresh(t)
    assert (t.nace_kapsam_turu, t.nace_kapsam_guven, t.nace_kapsam_kaynak) == ("YATAY", 0.95, "llm_extraction")
    assert t.nace_kapsam_tarihi is not None

    ikinci = SahteIstemci()          # çağrı yapılırsa pop() patlar
    s2 = run(betik.calistir(db_session, client=ikinci))
    assert s2["atlanan_yatay"] == 1 and s2["islenen"] == 0 and ikinci.cagrilar == []


def test_yeniden_bayragi_yatay_korumasini_asar(betik, db_session):
    _program(db_session, "KGF Genel Destek", "https://t/y2")
    run(betik.calistir(db_session, client=SahteIstemci(_cevap("YATAY"))))
    istemci = SahteIstemci(_cevap("YATAY"))
    s = run(betik.calistir(db_session, yeniden=True, client=istemci))
    assert s["islenen"] == 1 and len(istemci.cagrilar) == 1


def test_dusuk_guvenli_yatay_atlanmaz_tekrar_denenir(betik, db_session):
    _program(db_session, "Belirsiz Genel Destek", "https://t/y3")
    run(betik.calistir(db_session, client=SahteIstemci(_cevap("YATAY", guven=0.5))))
    istemci = SahteIstemci(_cevap("YATAY", guven=0.9))
    s = run(betik.calistir(db_session, client=istemci))
    assert s["islenen"] == 1 and s["atlanan_yatay"] == 0


def test_dry_run_kapsam_kararini_kalici_yazmaz(betik, db_session):
    t = _program(db_session, "KGF Genel Destek", "https://t/y4")
    run(betik.calistir(db_session, dry_run=True, client=SahteIstemci(_cevap("YATAY"))))
    db_session.refresh(t)
    assert t.nace_kapsam_turu is None


def test_geri_al_kalici_yatay_isaretini_da_sifirlar(betik, db_session):
    t = _program(db_session, "KGF Genel Destek", "https://t/y5")
    run(betik.calistir(db_session, client=SahteIstemci(_cevap("YATAY"))))
    run(betik.calistir(db_session, geri_al=True))
    db_session.refresh(t)
    assert t.nace_kapsam_turu is None
    istemci = SahteIstemci(_cevap("YATAY"))
    assert run(betik.calistir(db_session, client=istemci))["islenen"] == 1


def test_kapsam_karari_gocu_upgrade_downgrade(tmp_path, monkeypatch):
    from app import models
    db_yolu = tmp_path / "k.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")
    yeni = {"nace_kapsam_turu", "nace_kapsam_guven", "nace_kapsam_kaynak", "nace_kapsam_tarihi"}

    command.upgrade(cfg, "head")
    assert yeni <= {c["name"] for c in inspect(motor).get_columns("tesvikler")}
    command.downgrade(cfg, "d9e3f5a7b123")
    assert not (yeni & {c["name"] for c in inspect(motor).get_columns("tesvikler")})
    command.upgrade(cfg, "head")


# --------------------------------------- 3) log özeti, kapı ve logdan oynatma
def _log_kaydi(tid, tur="SEKTOR_KISITLI", guven=0.95, cakisma=None, inceleme=(), reddedilen=(),
               kodlar=(), haric=()):
    return {"tesvik_id": tid, "baslik": f"P{tid}",
            "kapsam": {"analiz_notu": "g", "kapsam_turu": tur, "kapsam_guven": guven,
                       "yararlanici_tipi": "URETICI",
                       "hedef_nace_kodlari": [_kod(k, "x") for k in kodlar],
                       "haric_tutulan_nace_kodlari": []},
            "reddedilen": [list(r) for r in reddedilen], "haric": list(haric),
            "manuel_inceleme_gerekli": bool(inceleme), "inceleme_nedenleri": list(inceleme),
            "cakisma": cakisma}


def _yaz(yol, kayitlar):
    yol.write_text("\n".join(json.dumps(k, ensure_ascii=False) for k in kayitlar) + "\n", encoding="utf-8")


def test_ozet_cakisma_frekans_tablosu_ve_dagilimlar(ozet, tmp_path):
    c = lambda tur, e, y: {"tur": tur, "eski": e, "yeni": y, "aksiyon": "ezildi"}
    yol = tmp_path / "l.jsonl"
    _yaz(yol, [
        _log_kaydi(1, cakisma=c("kapsam_daralmasi", ["C"], ["10.83"]), kodlar=["10.83"]),
        _log_kaydi(2, cakisma=c("kapsam_daralmasi", ["C"], ["28"]), kodlar=["28"]),
        _log_kaydi(3, "YATAY", cakisma=c("yatay_kilidi_kaldirildi", ["C"], [])),
        _log_kaydi(4, cakisma=c("sektor_degisimi", ["A"], ["10.83"]), kodlar=["10.83"]),
        _log_kaydi(5, "BELIRSIZ", 0.4, inceleme=["dışlama 12 yazılamadı"],
                   reddedilen=[("12", "hariç: dayanak metin kaynakta bulunamadı (uydurma olabilir)")]),
    ])
    o = ozet.ozetle(ozet.log_oku(yol))
    assert o["kayit_sayisi"] == 5
    assert o["cakisma_turu"] == {"kapsam_daralmasi": 2, "yatay_kilidi_kaldirildi": 1, "sektor_degisimi": 1}
    assert o["kapsam_turu"] == {"SEKTOR_KISITLI": 3, "YATAY": 1, "BELIRSIZ": 1}
    assert [r["tesvik_id"] for r in o["riskli_cakismalar"]] == [4]
    assert o["en_sik_hedef_kodlar"]["10.83"] == 2
    assert len(o["manuel_inceleme"]) == 1 and len(o["dusuk_guvenli"]) == 1
    assert "dayanak metin kaynakta bulunamadı" in list(o["reddedilen_sebepleri"])[0]
    metin = ozet.bicimle(o)
    assert "kapsam_daralmasi" in metin and "ELLE BAKILACAK" in metin and "[4] P4" in metin


def test_ozet_ayni_kaydin_son_satiri_gecerli(ozet, tmp_path):
    yol = tmp_path / "l.jsonl"
    _yaz(yol, [_log_kaydi(1, "BELIRSIZ", 0.3), _log_kaydi(1, "YATAY", 0.9)])
    assert ozet.ozetle(ozet.log_oku(yol))["kapsam_turu"] == {"YATAY": 1}


def test_kapi_temiz_logda_gecer_riskli_cakismada_kalir(ozet, tmp_path):
    temiz = tmp_path / "t.jsonl"
    _yaz(temiz, [_log_kaydi(i, kodlar=["10"]) for i in range(1, 6)])
    assert ozet.kapi_kontrol(ozet.ozetle(ozet.log_oku(temiz))) == []

    riskli = tmp_path / "r.jsonl"
    _yaz(riskli, [_log_kaydi(i, kodlar=["10"]) for i in range(1, 5)] +
         [_log_kaydi(9, cakisma={"tur": "sektor_degisimi", "eski": ["A"], "yeni": ["10"], "aksiyon": "ezildi"})])
    ihlal = ozet.kapi_kontrol(ozet.ozetle(ozet.log_oku(riskli)))
    assert len(ihlal) == 1 and "riskli çakışma" in ihlal[0]
    # eşik gevşetilirse geçer
    assert ozet.kapi_kontrol(ozet.ozetle(ozet.log_oku(riskli)), {"maks_riskli_cakisma": 1}) == []


def test_kapi_belirsiz_ve_inceleme_oranlarini_yakalar(ozet, tmp_path):
    yol = tmp_path / "b.jsonl"
    _yaz(yol, [_log_kaydi(i, "BELIRSIZ", 0.3, inceleme=["x"]) for i in range(1, 5)])
    ihlal = " ".join(ozet.kapi_kontrol(ozet.ozetle(ozet.log_oku(yol))))
    assert "manuel inceleme" in ihlal and "BELIRSIZ oranı" in ihlal and "düşük güvenli" in ihlal
    assert ozet.kapi_kontrol(ozet.ozetle([])) == ["log boş: doğrulanacak karar yok"]


def test_cli_kapi_cikis_kodu(ozet, tmp_path, capsys):
    yol = tmp_path / "c.jsonl"
    _yaz(yol, [_log_kaydi(1, cakisma={"tur": "karisik_degisim", "eski": ["10"], "yeni": ["55"],
                                      "aksiyon": "ezildi"}, kodlar=["55"])])
    assert ozet.main([str(yol)]) == 0
    assert ozet.main([str(yol), "--kapi"]) == 2
    assert "KAPI: GEÇMEDİ" in capsys.readouterr().out
    assert ozet.main([str(tmp_path / "yok.jsonl")]) == 1


def test_dry_run_logundan_api_cagirmadan_uygula(betik, db_session, tmp_path):
    """Maliyet: dry-run bir kez ödenir; gerçek yazma aynı kararları logdan alır."""
    metin = "Prim, yaş çay üreticilerine (müstahsil) ödenir."
    t = _program(db_session, "Çay Destek", "https://t/c", ozet_metni=metin)
    cevap = _cevap("SEKTOR_KISITLI", [_kod("01.27", "yaş çay üreticilerine (müstahsil)")])
    log = tmp_path / "nace.jsonl"

    istemci = SahteIstemci(cevap)
    run(betik.calistir(db_session, dry_run=True, client=istemci, log_yolu=log))
    kuru_log = log.with_suffix(".dry-run.jsonl")
    assert len(istemci.cagrilar) == 1 and kuru_log.exists()
    assert db_session.query(TesvikNace).count() == 0

    ikinci = SahteIstemci()                       # API çağrısı olursa patlar
    s = run(betik.calistir(db_session, client=ikinci, kararlar_logu=kuru_log))
    assert ikinci.cagrilar == [] and s["logdan_oynatilan"] == 1 and s["yazilan_satir"] == 1
    assert [(r.nace_prefix, r.kaynak) for r in db_session.query(TesvikNace)] == [("01.27", "llm_extraction")]
    db_session.refresh(t)
    assert t.nace_kapsam_turu == "SEKTOR_KISITLI"


def test_logdan_oynatma_guncel_metne_karsi_guvenlik_aglarini_yeniden_calistirir(betik, db_session, tmp_path):
    """Log sonrası metin değiştiyse (dayanak artık geçmiyorsa) satır yazılmamalı."""
    t = _program(db_session, "Çay Destek", "https://t/c2", ozet_metni="Prim yaş çay üreticilerine ödenir.")
    log = tmp_path / "k.jsonl"
    kapsam = _cevap("SEKTOR_KISITLI", [_kod("01.27", "yaş çay üreticilerine")])
    _yaz(log, [{"tesvik_id": t.id, "baslik": t.baslik, "kapsam": kapsam}])
    t.ozet = "Metin tamamen değişti ve artık farklı bir şeyden bahsediyor."
    db_session.commit()
    s = run(betik.calistir(db_session, client=SahteIstemci(), kararlar_logu=log))
    assert s["yazilan_satir"] == 0 and db_session.query(TesvikNace).count() == 0
