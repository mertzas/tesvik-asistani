"""Yapay zekâ için yurt dışına aktarım açık rızası testleri (2026-10-11 sağlayıcı katmanı).

Varsayılan sağlayıcı yerel danışmandır: hiçbir veri dışarı çıkmaz, rıza alınmaz. Yönetici yurt dışındaki bir servis
(Gemini) yapılandırırsa /api/sor sorunun metnini ve profili oraya gönderebilir; bu KVKK açısından yurt dışına
aktarımdır ve o sağlayıcıya verilmiş açık rıza gerektirir. Testler rızanın bağlayıcı ve sağlayıcıya özel olduğunu
— rıza yokken ya da başka bir sağlayıcıya verilmişken hiçbir dış çağrı yapılmadığını — sabitliyor.
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


@pytest.fixture
def gemini(monkeypatch):
    """Yurt dışındaki bir servis yapılandırılmış sunucu (ağ çağrısı yok; answer sahte)."""
    monkeypatch.setenv("LLM_SAGLAYICI", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "test-anahtar")


@pytest.fixture(autouse=True)
def _varsayilan_yerel(monkeypatch):
    monkeypatch.delenv("LLM_SAGLAYICI", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)


def _son_org(db_session):
    return db_session.query(Organization).order_by(Organization.created_at.desc()).first()


# ------------------------------------------------------------------ varsayılan: yerel danışman
def test_varsayilan_riza_yok(client, db_session):
    """Rıza varsayılan olarak KAPALI olmalı."""
    _hesap_ac(client)
    org = _son_org(db_session)
    assert org.ai_yurtdisi_riza is False and org.ai_riza_tarihi is None and org.ai_riza_saglayici is None


def test_yerelde_dis_cagri_ve_profil_aktarimi_yok(client, cagri_kaydi):
    h = _hesap_ac(client)
    r = client.post("/api/sor", json={"question": "KOSGEB desteği"}, headers=h)
    assert r.status_code == 200
    assert cagri_kaydi[-1]["llm_kullan"] is False and cagri_kaydi[-1]["profil"] is None
    assert "rıza" not in (r.json().get("message") or ""), "yerel danışmanda rıza notu gereksiz"


def test_yerelde_riza_alinmaz(client, db_session):
    h = _hesap_ac(client)
    r = client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    assert r.status_code == 409 and "yerel danışman" in r.json()["detail"]
    assert _son_org(db_session).ai_yurtdisi_riza is False


def test_yerelde_kayit_rizasi_saklanmaz(client, db_session):
    _hesap_ac(client, riza=True)
    assert _son_org(db_session).ai_yurtdisi_riza is False


def test_yapay_zeka_durumu_ucu(client):
    h = _hesap_ac(client)
    j = client.get("/api/yapay-zeka", headers=h).json()
    assert j["saglayici"] == "yerel" and j["yurtdisi"] is False and j["riza_gerekli"] is False
    assert j["dis_model_kullaniliyor"] is False


# ------------------------------------------------------------------ yurt dışı servis (Gemini)
def test_rizasiz_dis_cagri_yok_ve_aciklanir(client, cagri_kaydi, gemini):
    """Rıza yoksa dış çağrı HİÇ yapılmamalı; kullanıcı neden ve nasıl açacağını görmeli."""
    h = _hesap_ac(client)
    r = client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False and cagri_kaydi[-1]["profil"] is None
    mesaj = r.json().get("message") or ""
    assert "açık rıza" in mesaj and "Google Gemini" in mesaj and "ABD" in mesaj and "/kvkk" in mesaj


def test_kayitta_riza_saglayiciyla_saklanir(client, db_session, gemini):
    _hesap_ac(client, riza=True)
    org = _son_org(db_session)
    assert org.ai_yurtdisi_riza is True and org.ai_riza_tarihi is not None
    assert org.ai_riza_saglayici == "gemini:Google LLC:ABD:generativelanguage.googleapis.com"


def test_riza_verilince_dis_model_cagrilir(client, cagri_kaydi, gemini):
    h = _hesap_ac(client)
    r = client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    assert r.status_code == 200 and r.json()["saglayici"]["kurum"] == "Google LLC"
    assert r.json()["aydinlatma_metni"] == "/kvkk"
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is True


def test_riza_geri_alinabilir(client, cagri_kaydi, gemini):
    """KVKK açık rızası her zaman GERİ ALINABİLİR olmalıdır."""
    h = _hesap_ac(client, riza=True)
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is True
    r = client.post("/api/organizations/ai-riza", json={"riza": False}, headers=h)
    assert r.status_code == 200 and r.json()["ai_yurtdisi_riza"] is False and r.json()["tarih"] is None
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False, "rıza geri alındı ama çağrı sürüyor"


def test_baska_saglayiciya_verilmis_riza_gecersiz(client, db_session, cagri_kaydi, gemini):
    """Anthropic'e verilmiş (göçte işaretlenen) rıza Google'a aktarılmaz."""
    h = _hesap_ac(client)
    org = _son_org(db_session)
    org.ai_yurtdisi_riza, org.ai_riza_saglayici = True, "anthropic:Anthropic PBC"
    db_session.commit()
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False and cagri_kaydi[-1]["profil"] is None
    j = client.get("/api/yapay-zeka", headers=h).json()
    assert j["riza_gecerli"] is False and j["eski_riza_gecersiz"] is True


def test_yurt_ici_sunucuda_riza_gerekmez(client, cagri_kaydi, monkeypatch):
    monkeypatch.setenv("LLM_SAGLAYICI", "openai_uyumlu")
    monkeypatch.setenv("LLM_BASE_URL", "http://10.0.0.5:8000/v1")
    monkeypatch.setenv("LLM_MODEL", "yerel-model")
    monkeypatch.setenv("LLM_YURTDISI", "false")
    h = _hesap_ac(client)
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is True


def test_yurt_ici_sunucuda_vazgecilebilir(client, cagri_kaydi, monkeypatch):
    """Opus incelemesi 2026-10-11: yurt içi modda vazgeçen kuruluşa dış servis kullanılmaya devam ediyordu."""
    monkeypatch.setenv("LLM_SAGLAYICI", "openai_uyumlu")
    monkeypatch.setenv("LLM_BASE_URL", "http://10.0.0.5:8000/v1")
    monkeypatch.setenv("LLM_MODEL", "yerel-model")
    monkeypatch.setenv("LLM_YURTDISI", "false")
    h = _hesap_ac(client)
    r = client.post("/api/organizations/ai-riza", json={"riza": False}, headers=h)
    assert r.status_code == 200 and "Vazgeçtiniz" in r.json()["mesaj"]
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False
    client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is True


def test_riza_ucu_kimlik_dogrulamasi_ister(client):
    r = client.post("/api/organizations/ai-riza", json={"riza": True})
    assert r.status_code in (401, 403)


def test_rizali_profil_nace_ve_kobi_olcegini_tasir_ozellikleri_tasimaz(client, cagri_kaydi, gemini):
    """Danışman ölçek/NACE ile eleme yapabilsin; hedef kitle özellikleri (kadın/genç girişimci) KVKK metninde
    belirtildiği gibi aktarılmasın."""
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
