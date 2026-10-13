"""Profilde planlanan yatırım tutarı (2026-10-13): 9903 asgari sabit yatırım şartı profilden denetlenir."""
import uuid

from app import rag
from app.matching import esles
from app.models import FinancialProfile, Tesvik
from app.tesvik_9903_uygunluk import yatirim_tutari

HEDEF = "Hedef Yatırımlar Teşvik Sistemi (9903 sayılı Karar)"


def _profil(tutar):
    return FinancialProfile(org_id=uuid.uuid4(), sektor="hizmet", nace_kodu="55.10", sirket_turu="limited",
                            calisan_sayisi=14, yillik_ciro=30e6, bolge="Antalya", hedefler=["yatirim"],
                            planlanan_yatirim_tl=tutar)


def test_yatirim_tutari_onceligi():
    p = _profil(8e6)
    assert yatirim_tutari("yaklaşık 50 milyon TL'lik otel yatırımı", p) == (50e6, "sorudaki")
    assert yatirim_tutari("otel yatırımı için destek", p) == (8e6, "profilinizdeki planlanan")
    assert yatirim_tutari("otel yatırımı", _profil(None)) == (None, "")


def test_eslesme_asgari_altindaki_9903_programini_eler(db_session):
    db_session.add(Tesvik(id=880, kurum="Sanayi ve Teknoloji Bakanlığı", baslik=HEDEF, ozet="o", detay="d",
                          aktif_mi=True, uygunluk_kriterleri={"sektorler": ["genel", "hizmet"]}))
    db_session.commit()
    kucuk = [s.tesvik.id for s in esles(_profil(8e6), db_session, limit=50)]
    buyuk = [s.tesvik.id for s in esles(_profil(50e6), db_session, limit=50)]
    bos = [s.tesvik.id for s in esles(_profil(None), db_session, limit=50)]
    assert 880 not in kucuk, "8 milyon TL, bölgenin asgari sabit yatırımının altında (MADDE 5/2)"
    assert 880 in buyuk and 880 in bos, "yeterli tutar ya da boş alan eleme yapmaz"


def test_danisman_notu_profil_tutarini_soyler():
    t = Tesvik(id=880, kurum="Sanayi ve Teknoloji Bakanlığı", baslik=HEDEF, ozet="o", detay="d", aktif_mi=True,
               uygunluk_kriterleri={"sektorler": ["genel"]})
    notlar = rag.profil_9903_degerlendirmesi([t], _profil(8e6), "otel yatırımı için destek var mı")
    assert notlar[880].durum == "uygun_degil" and "profilinizdeki planlanan yatırım tutarı" in notlar[880].gerekce


def test_profil_ucu_alani_kaydeder(client):
    r = client.post("/api/auth/signup", json={"email": f"y{uuid.uuid4().hex[:8]}@example.com", "password": "Parola123",
                                              "full_name": "A", "company_name": "B"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    govde = {"sektor": "hizmet", "bolge": "Antalya", "calisan_sayisi": 14, "yillik_ciro": 30e6,
             "planlanan_yatirim_tl": 8_500_000}
    assert client.put("/api/profil", json=govde, headers=h).status_code == 200
    assert client.get("/api/profil", headers=h).json()["planlanan_yatirim_tl"] == 8_500_000
    assert client.put("/api/profil", json=govde | {"planlanan_yatirim_tl": -5}, headers=h).status_code == 422
