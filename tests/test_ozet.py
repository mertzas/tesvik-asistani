"""Ana sayfa özeti (/api/ozet), il listesi (/api/iller) ve kart özeti temizliği (2026-10-08)."""
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.models import Tesvik, TesvikCagrisi

KOK = Path(__file__).resolve().parent.parent
BUGUN = date.today()
MENU = "Girişimci Destek Programı\nKapasite Geliştirme Destek Programı\nKüresel Rekabetçilik Destek Programı"


@pytest.fixture
def kayitlar(db_session):
    db_session.add_all([
        Tesvik(id=11, kurum="KOSGEB", baslik="İmalat Dönüşüm", aktif_mi=True, kaynak_url="https://t/11",
               ozet=MENU + "\nProgramın amacı imalat yapan işletmelerin verimliliğini artırmaktır.",
               detay="imalat", uygunluk_kriterleri={"sektorler": ["imalat"]}),
        Tesvik(id=12, kurum="KOSGEB", baslik="Yalnız Menü Özetli", aktif_mi=True, kaynak_url="https://t/12",
               ozet=MENU, detay="imalat", uygunluk_kriterleri={"sektorler": ["imalat"]}),
    ])
    db_session.flush()
    db_session.add(TesvikCagrisi(tesvik_id=11, ad="2026/2", acilis=BUGUN - timedelta(days=3),
                                 kapanis=BUGUN + timedelta(days=12), kaynak_url="https://k/11", dogrulama_tarihi=BUGUN))
    db_session.commit()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_iller_81_il_turkce_sirali(client):
    iller = client.get("/api/iller").json()["iller"]
    assert len(iller) == 81 and iller[0] == "Adana" and iller.index("Çanakkale") < iller.index("Denizli")


def test_ozet_profilsiz_ilk_adim_profil(client, test_user_token, kayitlar):
    o = client.get("/api/ozet", headers=_h(test_user_token)).json()
    assert o["profil"]["tamamlanma"] == 0 and o["eslesme_sayisi"] == 0
    assert o["sonraki_adim"]["eylem"] == "profil"


def test_ozet_eksik_profil_yakin_cagri(client, test_user_token, kayitlar):
    h = _h(test_user_token)
    assert client.put("/api/profil", headers=h, json={"sektor": "imalat", "bolge": "Konya", "calisan_sayisi": 12,
                                                       "yillik_ciro": 5e6, "hedefler": ["verimlilik"]}).status_code == 200
    o = client.get("/api/ozet", headers=h).json()
    assert [e["alan"] for e in o["profil"]["eksikler"]] == ["sirket_turu", "nace_kodu", "kurulus_tarihi"]
    assert o["profil"]["tamamlanma"] == 5 * 14
    assert o["sonraki_adim"]["eylem"] == "profil"  # temel alan eksikken önce o istenir
    assert o["eslesme_sayisi"] >= 1
    yakin = [c for c in o["yaklasan_son_basvurular"] if c["tesvik_id"] == 11]
    assert yakin and yakin[0]["kalan_gun"] == 12 and yakin[0]["durum"] == "acik"

    client.put("/api/profil", headers=h, json={"sektor": "imalat", "bolge": "Konya", "calisan_sayisi": 12,
                                               "yillik_ciro": 5e6, "hedefler": ["verimlilik"], "sirket_turu": "limited"})
    adim = client.get("/api/ozet", headers=h).json()["sonraki_adim"]
    assert adim["eylem"] == "liste" and adim["tesvik_id"] == 11 and "12 gün" in adim["metin"]


def test_ozet_kimliksiz_erisim_yok(client):
    assert client.get("/api/ozet").status_code in (401, 403)


def test_eslesme_karti_cagri_ve_temiz_ozet(client, test_user_token, kayitlar):
    h = _h(test_user_token)
    client.put("/api/profil", headers=h, json={"sektor": "imalat", "calisan_sayisi": 12})
    kartlar = {k["id"]: k for k in client.get("/api/eslesme", headers=h).json()["eslesen_tesvikler"]}
    assert kartlar[11]["ozet"] == "Programın amacı imalat yapan işletmelerin verimliliğini artırmaktır."
    assert kartlar[11]["cagri"]["ad"] == "2026/2" and kartlar[11]["cagri"]["durum"] == "acik"
    assert kartlar[12]["ozet"] == "" and kartlar[12]["cagri"] is None


@pytest.mark.parametrize("komut,asgari", [(["-m", "app.ozet"], 9), (["-m", "app.basvuru_taslagi"], 10),
                                          (["scripts/fix_veri_2026_10_08_ozet_tur13.py"], 5)])
def test_self_testler(komut, asgari):
    import re
    r = subprocess.run([sys.executable, *komut, "--self-test"], cwd=KOK, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= asgari, r.stdout + r.stderr
