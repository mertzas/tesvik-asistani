"""10 persona uçtan uca denemesinden çıkan düzeltmeler (docs/olcum/2026-10-08-persona/RAPOR.md), 2026-10-08."""
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.cagrilar import durum
from app.hazirlik import yol_haritasi
from app.matching import esles, uygunluk_engeli
from app.models import BasvuruTakibi, FinancialProfile, Organization, Tesvik, TesvikCagrisi

KOK = Path(__file__).resolve().parent.parent
BUGUN = date.today()
K5986 = "https://ticaret.gov.tr/data/632b13e013b8767974670b91/E-ihracat%20Karar.pdf"


def _t(**k):
    v = dict(kurum="KOSGEB", baslik="Program", ozet="o", detay="d", aktif_mi=True, kaynak_url="https://t/x",
             uygunluk_kriterleri={"sektorler": ["genel"]})
    v.update(k)
    if "kaynak_url" not in k and "id" in k:
        v["kaynak_url"] = f"https://t/{k['id']}"   # kaynak_url benzersiz
    return Tesvik(**v)


# ---------------------------------------------------------------- 1. firmanın son günü (ön kayıt)
def test_on_kayit_son_gunu_kalan_gunu_belirler():
    c = TesvikCagrisi(acilis=BUGUN - timedelta(days=60), kapanis=BUGUN + timedelta(days=18),
                      on_kayit_son=BUGUN + timedelta(days=14))
    assert durum(c)["durum"] == "acik" and durum(c)["kalan_gun"] == 14
    c.on_kayit_son = BUGUN - timedelta(days=1)
    assert durum(c)["durum"] == "on_kayit_kapandi" and durum(c)["kalan_gun"] == 18


def test_on_kayit_api_ve_ozet(client, test_user_token, db_session):
    db_session.add(_t(id=34, kurum="TUBITAK", baslik="1501 - Sanayi Ar-Ge", kaynak_url="https://t/34"))
    db_session.flush()
    db_session.add(TesvikCagrisi(tesvik_id=34, ad="2026/2", acilis=BUGUN - timedelta(days=80),
                                 kapanis=BUGUN + timedelta(days=18), on_kayit_son=BUGUN + timedelta(days=14),
                                 kaynak_url="https://tubitak.gov.tr/x.pdf", dogrulama_tarihi=BUGUN))
    db_session.commit()
    h = {"Authorization": f"Bearer {test_user_token}"}
    c = client.get("/api/basvuru-listesi/34", headers=h).json()["cagrilar"][0]
    assert c["on_kayit_son"] == (BUGUN + timedelta(days=14)).isoformat() and c["son_gun"] == c["on_kayit_son"]
    # Takipteki başvuru, eşleşme listesinde olmasa da "sıradaki adım"a girer.
    client.put("/api/profil", headers=h, json={"sektor": "imalat", "bolge": "Konya", "calisan_sayisi": 12,
                                               "yillik_ciro": 5e6, "hedefler": ["yatirim"], "sirket_turu": "limited"})
    org = db_session.query(Organization).first()
    db_session.add(BasvuruTakibi(org_id=org.id, tesvik_id=34, isaretli=[]))
    db_session.commit()
    o = client.get("/api/ozet", headers=h).json()
    assert o["sonraki_adim"].get("tesvik_id") == 34, o["sonraki_adim"] and "ön kayıt son gününe 14 gün" in o["sonraki_adim"]["metin"]
    assert o["yaklasan_son_basvurular"][0]["tesvik_id"] == 34


# ---------------------------------------------------------------- 3, 6, 8. eşleştirme engelleri
def test_kosgeb_buyuk_isletmeye_kapali_ama_buyuge_acik_program_istisna():
    buyuk = FinancialProfile(sektor="imalat", calisan_sayisi=320, yillik_ciro=2.5e9)
    assert "KOBİ" in uygunluk_engeli(_t(baslik="Küresel Rekabetçilik"), buyuk)
    acik = _t(baslik="İstihdamı Koruma", basvuru_sartlari=["KOBİ veya büyük işletme olması (ikisi de başvurabilir)"])
    assert uygunluk_engeli(acik, buyuk) is None
    assert uygunluk_engeli(_t(), FinancialProfile(sektor="imalat", calisan_sayisi=45, yillik_ciro=120e6)) is None


@pytest.mark.parametrize("tur,kapali", [("sahis", False), (None, False), ("kooperatif", True), ("anonim", True),
                                        ("yok", True)])
def test_sahis_isletmeleri_urunu(tur, kapali):
    t = _t(kurum="KGF", baslik="HALK BANKASI ŞAHIS İŞLETMELERİ DESTEK KREDİSİ PROJESİ")
    assert (uygunluk_engeli(t, FinancialProfile(sektor="genel", calisan_sayisi=3, sirket_turu=tur)) is not None) == kapali


def test_9903_sirketsize_kapali():
    t = _t(kurum="Sanayi ve Teknoloji Bakanlığı", baslik="Hedef Yatırımlar (9903)")
    assert uygunluk_engeli(t, FinancialProfile(sektor="arge", sirket_turu="yok")) is not None
    assert uygunluk_engeli(t, FinancialProfile(sektor="imalat", sirket_turu="limited")) is None


@pytest.mark.parametrize("usd,statu,kapali", [(300_000, None, True), (600_000, None, False), (None, None, False),
                                              (300_000, True, False)])
def test_asgari_ihracat_kriteri(usd, statu, kapali):
    t = _t(kurum="Ticaret Bakanlığı", uygunluk_kriterleri={"sektorler": ["e-ticaret"],
                                                           "min_onceki_yil_ihracat_usd": 500_000, "statu_ile_muaf": True})
    p = FinancialProfile(sektor="e-ticaret", sirket_turu="limited",
                         hazirlik={"eihracat": {"onceki_yil_ihracat_usd": usd, "perakende_statusu": statu}})
    assert (uygunluk_engeli(t, p) is not None) == kapali


# ---------------------------------------------------------------- sıralama
@pytest.fixture
def siralama(db_session):
    db_session.add_all([
        _t(id=1, kurum="KGF", baslik="Genel Kefalet", uygunluk_kriterleri={"sektorler": ["genel"]}),
        _t(id=2, kurum="KGF", baslik="Kadın Girişimci Paketi",
           uygunluk_kriterleri={"sektorler": ["genel"], "exclusive_target_group": True,
                                "target_group_tags": ["kadin_girisimci"]}),
        _t(id=3, kurum="Sanayi ve Teknoloji Bakanlığı", baslik="Yerel Kalkınma Hamlesi (9903)",
           uygunluk_kriterleri={"sektorler": ["genel", "hizmet"]}),
        _t(id=4, kurum="Tarım Bakanlığı", baslik="Organik Tarım Destekleri",
           uygunluk_kriterleri={"sektorler": ["tarim"], "alt_kategori": "organik", "genislik": "genis"}),
        _t(id=5, kurum="Tarım Bakanlığı", baslik="Hububat", basvuru_sartlari=["ÇKS kaydı"],
           uygunluk_kriterleri={"sektorler": ["tarim"], "alt_kategori": "tahil_baklagil", "genislik": "dar"}),
    ])
    db_session.commit()


def test_hedef_kitle_etiketi_one_cikarir_yatirim_tesvigi_hedefsizde_geride(db_session, siralama):
    p = FinancialProfile(sektor="hizmet", calisan_sayisi=2, sirket_turu="sahis", hedefler=["istihdam"],
                         ozellikler=["kadin_girisimci"])
    s = {e.tesvik.id: e for e in esles(p, db_session)}
    assert s[2].skor > s[1].skor and any("hedef kitlenize" in g for g in s[2].gerekce)
    assert s[3].skor < s[2].skor and any("Yatırım teşviki" in x for x in s[3].eksik_kriterler)
    hedefsiz = {e.tesvik.id: e for e in esles(FinancialProfile(sektor="hizmet", calisan_sayisi=2), db_session)}
    assert not any("Yatırım teşviki" in x for x in hedefsiz[3].eksik_kriterler)  # yokluk ihlal değildir


def test_organik_beyansiz_geride_beyanli_degil(db_session, siralama):
    bugday = FinancialProfile(sektor="tarim", calisan_sayisi=2, tarim_kategori="tahil_baklagil", sirket_turu="sahis")
    organik = FinancialProfile(sektor="tarim", calisan_sayisi=2, tarim_kategori="organik", sirket_turu="sahis")
    b = {e.tesvik.id: e for e in esles(bugday, db_session)}
    o = {e.tesvik.id: e for e in esles(organik, db_session)}
    assert b[4].skor < o[4].skor and any("sertifikalı" in x for x in b[4].eksik_kriterler)
    assert b[5].skor > b[4].skor


def test_sifir_skorlu_kayit_listelenmez(db_session, siralama):
    assert all(e.skor > 0 for e in esles(FinancialProfile(sektor="arge", sirket_turu="yok"), db_session))


# ---------------------------------------------------------------- 5. hazırlık sıralaması
def test_ciftcide_cks_ilk_adim_ilgisiz_programla_sirket_adimi_yok(db_session, siralama):
    db_session.add(_t(id=6, kurum="TUBITAK", baslik="1501 Sanayi Ar-Ge",
                      uygunluk_kriterleri={"sektorler": ["arge", "genel"]}))
    db_session.commit()
    p = FinancialProfile(sektor="tarim", calisan_sayisi=2, tarim_kategori="tahil_baklagil", sirket_turu="sahis")
    adimlar = yol_haritasi(p, db_session)["adimlar"]
    assert adimlar[0]["kod"] == "cks" and "sirket" not in {a["kod"] for a in adimlar}


# ---------------------------------------------------------------- göç ve veri betiği
def test_goc_on_kayit_sutunu(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    from app import models
    db_yolu = tmp_path / "t.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")
    command.upgrade(cfg, "head")
    assert "on_kayit_son" in {c["name"] for c in inspect(motor).get_columns("tesvik_cagrilari")}
    command.downgrade(cfg, "m0b2d4f6a012")
    assert "on_kayit_son" not in {c["name"] for c in inspect(motor).get_columns("tesvik_cagrilari")}
    command.upgrade(cfg, "head")


def test_tur14_self_test():
    r = subprocess.run([sys.executable, "scripts/fix_veri_2026_10_08_on_kayit_tur14.py", "--self-test"], cwd=KOK,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= 4, r.stdout


# ---------------------------------------------------------------- ilgi cezaları (100 sentetik ajan, 2026-10-09)
@pytest.fixture
def ilgi(db_session):
    db_session.add_all([
        _t(id=2, kurum="KOSGEB", baslik="Yapay Zekâ Kredi Programı", uygunluk_kriterleri={"sektorler": ["arge", "genel"]}),
        _t(id=186, kurum="SGK / İŞKUR", baslik="İşsizlik Ödeneği Alanların İstihdamı", uygunluk_kriterleri={"sektorler": ["genel"]}),
        _t(id=5, kurum="KOSGEB", baslik="YÖNDE - Yönderlik ve Değerlendirme", uygunluk_kriterleri={"sektorler": ["genel"]}),
        _t(id=160, kurum="Tarım Bakanlığı", baslik="Hububat", uygunluk_kriterleri={"sektorler": ["tarim"],
                                                                                 "alt_kategori": "tahil_baklagil", "genislik": "dar"}),
    ])
    db_session.commit()


def test_ilgisiz_genel_programlar_ciftciye_gelmez(db_session, ilgi):
    p = FinancialProfile(sektor="tarim", calisan_sayisi=2, tarim_kategori="tahil_baklagil", sirket_turu="sahis",
                         hedefler=["makine"])
    ids = {e.tesvik.id for e in esles(p, db_session)}
    assert 160 in ids and not ({2, 186, 5} & ids)


def test_ilgi_sinyali_varsa_kalir(db_session, ilgi):
    yazilim = FinancialProfile(sektor="hizmet", nace_kodu="62.01", calisan_sayisi=10, sirket_turu="limited",
                               hedefler=["istihdam"])
    ids = {e.tesvik.id for e in esles(yazilim, db_session)}
    assert {2, 186} <= ids                          # Ar-Ge NACE'si ve istihdam hedefi var
    hedefsiz = FinancialProfile(sektor="hizmet", calisan_sayisi=10, sirket_turu="limited")
    assert 186 in {e.tesvik.id for e in esles(hedefsiz, db_session)}   # yokluk ihlal değildir
