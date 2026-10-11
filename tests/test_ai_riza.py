"""Yapay zekâ veri güvenliği testleri (2026-10-11; üçüncü taraf servisler kaldırıldı).

Varsayılan sağlayıcı yerel danışmandır: dil modeli yok, hiçbir veri dışarı çıkmaz. Üçüncü taraf servisler (Gemini,
OpenAI uyumlu dış uç, Anthropic) yapılandırılsa bile reddedilir. Tek dil modeli seçeneği kendi sunucumuzdaki modeldir
(LLM_SAGLAYICI=ozel_sunucu) ve yalnız iç ağ adresine bağlanır; kuruluş bazında varsayılan kapalıdır, kullanıcı
açıkça açar ve kapatır; tercih sağlayıcıdan ve sunucu adresinden bağımsız saklanır.
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
def ozel_sunucu(monkeypatch):
    """Kendi sunucumuzdaki model yapılandırılmış sunucu (ağ çağrısı yok; answer sahte)."""
    monkeypatch.setenv("LLM_SAGLAYICI", "ozel_sunucu")
    monkeypatch.setenv("LLM_BASE_URL", "http://10.0.0.5:8000/v1")
    monkeypatch.setenv("LLM_MODEL", "yerel-model")


@pytest.fixture(autouse=True)
def _varsayilan_yerel(monkeypatch):
    for ad in ("LLM_SAGLAYICI", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(ad, raising=False)


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


# ------------------------------------------------------------------ üçüncü taraf servisler reddedilir
@pytest.mark.parametrize("ortam", [
    {"LLM_SAGLAYICI": "gemini", "LLM_API_KEY": "k"},
    {"LLM_SAGLAYICI": "openai_uyumlu", "LLM_BASE_URL": "https://api.openai.com/v1", "LLM_MODEL": "gpt", "LLM_API_KEY": "k"},
    {"LLM_SAGLAYICI": "anthropic", "LLM_API_KEY": "k"},
    {"LLM_SAGLAYICI": "ozel_sunucu", "LLM_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
     "LLM_MODEL": "gemini-2.5-flash"},
    {"LLM_SAGLAYICI": "ozel_sunucu", "LLM_BASE_URL": "http://8.8.8.8/v1", "LLM_MODEL": "m"},
])
def test_ucuncu_taraf_ya_da_dis_adres_yapilandirilsa_da_veri_cikmaz(client, cagri_kaydi, monkeypatch, ortam):
    for ad, deger in ortam.items():
        monkeypatch.setenv(ad, deger)
    h = _hesap_ac(client, riza=True)
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False and cagri_kaydi[-1]["profil"] is None
    j = client.get("/api/yapay-zeka", headers=h).json()
    assert j["etkin"] is False and j["dis_model_kullaniliyor"] is False and j["ucuncu_taraf"] is False
    assert client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h).status_code == 409


def test_eski_ucuncu_taraf_rizasi_temizlenir(client, db_session, cagri_kaydi):
    """Eski sürümden kalan Gemini/Anthropic rıza kaydı hiçbir şeyi açmaz; rıza ucu onu temizler."""
    h = _hesap_ac(client)
    org = _son_org(db_session)
    org.ai_yurtdisi_riza, org.ai_riza_saglayici = True, "gemini:Google LLC:ABD:generativelanguage.googleapis.com"
    db_session.commit()
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False and cagri_kaydi[-1]["profil"] is None
    r = client.post("/api/organizations/ai-riza", json={"riza": False}, headers=h)
    assert r.status_code == 200 and "hiçbir veri dışarı aktarılmaz" in r.json()["mesaj"]
    db_session.refresh(org)
    assert org.ai_yurtdisi_riza is False and org.ai_riza_saglayici is None


# ------------------------------------------------------------------ kendi sunucumuzdaki model
def test_ozel_sunucu_varsayilan_kapali_acinca_kullanilir(client, cagri_kaydi, ozel_sunucu):
    h = _hesap_ac(client)
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False and cagri_kaydi[-1]["profil"] is None
    j = client.get("/api/yapay-zeka", headers=h).json()
    assert j["saglayici"] == "ozel_sunucu" and j["riza_gerekli"] is False and j["yurtdisi"] is False
    assert j["ucuncu_taraf"] is False and j["ulke"] == "Türkiye" and j["varsayilan_kapali"] is True
    assert j["riza_gecerli"] is False
    r = client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    assert "üçüncü taraf bir yapay zekâ servisine gitmez" in r.json()["mesaj"] and r.json()["aydinlatma_metni"] == "/kvkk"
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is True


def test_ozel_sunucuda_kayit_rizasi_saklanmaz(client, db_session, ozel_sunucu):
    _hesap_ac(client, riza=True)
    org = _son_org(db_session)
    assert org.ai_yurtdisi_riza is False and org.ai_riza_saglayici is None


def test_ozel_sunucu_kapatilabilir(client, cagri_kaydi, ozel_sunucu):
    h = _hesap_ac(client)
    client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    r = client.post("/api/organizations/ai-riza", json={"riza": False}, headers=h)
    assert r.status_code == 200 and "Kapattınız" in r.json()["mesaj"]
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False


def test_kapatma_tercihi_model_kapatilip_acilinca_ve_adres_degisince_korunur(client, cagri_kaydi, monkeypatch,
                                                                             ozel_sunucu):
    """Opus güvenlik incelemesi 2026-10-11: model kapalıyken yapılan vazgeçme kaydı siliniyor, sunucu adresi
    değişince vazgeçme düşüyordu."""
    h = _hesap_ac(client)
    monkeypatch.setenv("LLM_SAGLAYICI", "yerel")                      # yönetici modeli geçici kapattı
    assert client.post("/api/organizations/ai-riza", json={"riza": False}, headers=h).status_code == 200
    monkeypatch.setenv("LLM_SAGLAYICI", "ozel_sunucu")                # geri açtı ve adresi değiştirdi
    monkeypatch.setenv("LLM_BASE_URL", "http://vllm:8000/v1")
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is False
    client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    monkeypatch.setenv("LLM_BASE_URL", "http://10.0.0.9:8000/v1")     # açık tercih de adres değişince korunur
    client.post("/api/sor", json={"question": "destek"}, headers=h)
    assert cagri_kaydi[-1]["llm_kullan"] is True


def test_riza_ucu_kimlik_dogrulamasi_ister(client):
    r = client.post("/api/organizations/ai-riza", json={"riza": True})
    assert r.status_code in (401, 403)


def test_modele_giden_profil_nace_ve_kobi_olcegini_tasir_ozellikleri_tasimaz(client, cagri_kaydi, ozel_sunucu):
    """Danışman ölçek/NACE ile eleme yapabilsin; hedef kitle özellikleri (kadın/genç girişimci) KVKK metninde
    belirtildiği gibi aktarılmasın."""
    h = _hesap_ac(client)
    client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
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
