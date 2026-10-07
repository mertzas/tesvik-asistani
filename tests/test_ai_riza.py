"""Yapay zekâ için yurt dışına aktarım açık rızası testleri.

/api/sor çağrısında işletme profili ve sorunun metni Anthropic'e (ABD)
gönderiliyor; bu KVKK açısından yurt dışına aktarımdır ve açık rıza
gerektirir. Testler rızanın gerçekten bağlayıcı olduğunu — rıza yokken
hiçbir dış çağrı yapılmadığını — sabitliyor.
"""
import uuid

import pytest

import app.main as anamodul
from app.models import Organization


def _hesap_ac(client, riza=None):
    govde = {
        "email": f"riza{uuid.uuid4().hex[:8]}@example.com",
        "password": "GucluSifre123",
        "full_name": "Test Kullanici",
        "company_name": "Test Ltd",
    }
    if riza is not None:
        govde["ai_yurtdisi_riza"] = riza
    r = client.post("/api/auth/signup", json=govde)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def cagri_kaydi(monkeypatch):
    """answer() çağrılarını kaydeder; gerçek LLM'e çıkmaz."""
    kayitlar = []

    def _sahte(soru, profil=None, llm_kullan=True, **_kw):
        kayitlar.append({"profil": profil, "llm_kullan": llm_kullan})
        return "[test] yanıt"

    monkeypatch.setattr(anamodul, "answer", _sahte)
    return kayitlar


def test_varsayilan_riza_yok(client, db_session):
    """Rıza varsayılan olarak KAPALI olmalı. Açık gelirse kullanıcı hiç
    onay vermeden verisi yurt dışına gider."""
    _hesap_ac(client)
    org = db_session.query(Organization).order_by(
        Organization.created_at.desc()).first()
    assert org.ai_yurtdisi_riza is False
    assert org.ai_riza_tarihi is None


def test_riza_yokken_llm_cagrilmaz(client, cagri_kaydi):
    """En kritik davranış: rıza yoksa dış çağrı HİÇ yapılmamalı.

    Sorunun metni de kişisel veridir; profili göndermemek yetmez, çağrının
    kendisi yapılmamalıdır.
    """
    h = _hesap_ac(client)
    r = client.post("/api/sor", json={"question": "KOSGEB desteği"}, headers=h)
    assert r.status_code == 200
    assert cagri_kaydi[-1]["llm_kullan"] is False
    assert cagri_kaydi[-1]["profil"] is None


def test_riza_yokken_kullaniciya_aciklanir(client, cagri_kaydi):
    """Kullanıcı neden AI yanıtı almadığını ve nasıl açacağını görmeli;
    sessizce düşük kaliteli yanıt vermek şeffaf değil."""
    h = _hesap_ac(client)
    r = client.post("/api/sor", json={"question": "destek"}, headers=h)
    mesaj = r.json().get("message") or ""
    assert "açık rıza" in mesaj
    assert "/api/organizations/ai-riza" in mesaj
    assert "/kvkk" in mesaj


def test_kayitta_riza_verilebilir(client, db_session):
    _hesap_ac(client, riza=True)
    org = db_session.query(Organization).order_by(
        Organization.created_at.desc()).first()
    assert org.ai_yurtdisi_riza is True
    assert org.ai_riza_tarihi is not None


def test_riza_verilince_llm_cagrilir(client, cagri_kaydi):
    h = _hesap_ac(client)
    client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is True


def test_riza_geri_alinabilir(client, cagri_kaydi):
    """KVKK açık rızası her zaman GERİ ALINABİLİR olmalıdır."""
    h = _hesap_ac(client, riza=True)
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is True

    r = client.post("/api/organizations/ai-riza", json={"riza": False},
                    headers=h)
    assert r.status_code == 200
    assert r.json()["ai_yurtdisi_riza"] is False
    assert r.json()["tarih"] is None

    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False, "rıza geri alındı ama çağrı sürüyor"


def test_riza_ucu_kimlik_dogrulamasi_ister(client):
    r = client.post("/api/organizations/ai-riza", json={"riza": True})
    assert r.status_code in (401, 403)


def test_riza_yanitinda_aydinlatma_metni_gosterilir(client):
    h = _hesap_ac(client)
    r = client.post("/api/organizations/ai-riza", json={"riza": True},
                    headers=h)
    assert r.json()["aydinlatma_metni"] == "/kvkk"


def test_rizali_profil_nace_ve_kobi_olcegini_tasir_ozellikleri_tasimaz(client, cagri_kaydi):
    """Danışman ölçek/NACE ile eleme yapabilsin; hedef kitle özellikleri
    (kadın/genç girişimci) KVKK metninde belirtildiği gibi aktarılmasın."""
    h = _hesap_ac(client, riza=True)
    r = client.put("/api/profil", headers=h, json={
        "sektor": "imalat", "bolge": "Konya", "calisan_sayisi": 30, "yillik_ciro": 80_000_000,
        "nace_kodu": "C.10.71", "ozellikler": ["kadin_girisimci"]})
    assert r.status_code == 200, r.text
    client.post("/api/sor", json={"question": "Makine yatırımı için destek"}, headers=h)
    profil = cagri_kaydi[-1]["profil"]
    assert profil["NACE kodu"] == "10.71"
    assert profil["KOBİ ölçeği"].startswith("küçük işletme") and "7 Ağustos 2025" in profil["KOBİ ölçeği"]
    assert profil["yatırım teşvik bölgesi (9903 sayılı Karar EK-2)"].endswith("bölge")
    assert not any("kadin" in str(v) or "özellik" in k for k, v in profil.items())
