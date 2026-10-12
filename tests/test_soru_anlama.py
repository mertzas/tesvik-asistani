"""Soru anlama katmanı (Groq) testleri, 2026-10-12.

Varsayılan kapalı; sunucuda SORU_ANLAMA=groq + GROQ_API_KEY ve kuruluşun açık rızası gerekir. Groq'a yalnız maskeli
soru gider (ad, rakam, e-posta yok; profil yok); etiketler kelime kalıplarına eklenir, karar ve yanıt yerel danışmanda
kalır; Groq hata verirse yanıt yine üretilir. Ağ çağrısı yok: groq_cagir sahtelenir.
"""
import json
import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from app import rag, soru_anlama
from app.models import Organization, Tesvik


@pytest.fixture(autouse=True)
def _temiz(monkeypatch):
    for ad in ("SORU_ANLAMA", "GROQ_API_KEY", "SORU_ANLAMA_MODEL", "LLM_SAGLAYICI"):
        monkeypatch.delenv(ad, raising=False)
    soru_anlama._ONBELLEK.clear()
    soru_anlama._DEVRE.update(hata=0, acilis=0.0)


@pytest.fixture
def groq(monkeypatch):
    """Yapılandırılmış sunucu; Groq çağrıları kaydedilir, yanıt `groq.yanit`."""
    monkeypatch.setenv("SORU_ANLAMA", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-anahtar")

    class Kayit:
        yanit = '{"niyet": [], "ihtiyac": ["istihdam"]}'
        hata: Exception | None = None
        mesajlar: list = []

    kayit = Kayit()
    kayit.mesajlar = []

    def _sahte(mesajlar, api_key, model, **_kw):
        kayit.mesajlar.append(mesajlar)
        if kayit.hata:
            raise kayit.hata
        return kayit.yanit, 500, 30

    monkeypatch.setattr(soru_anlama, "groq_cagir", _sahte)
    return kayit


def _hesap_ac(client, ad="Zeynep Arıkan", firma="Arıkan Örgü Ltd"):
    r = client.post("/api/auth/signup", json={"email": f"sa{uuid.uuid4().hex[:8]}@example.com",
                                              "password": "GucluSifre123", "full_name": ad, "company_name": firma})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _org(db_session):
    return db_session.query(Organization).order_by(Organization.created_at.desc()).first()


# ------------------------------------------------------------------ rıza
def test_varsayilan_kapali_ve_yapilandirilmamissa_acilamaz(client, db_session):
    h = _hesap_ac(client)
    j = client.get("/api/yapay-zeka", headers=h).json()["soru_anlama"]
    assert j["etkin"] is False and j["riza"] is False and j["ulke"] == "ABD"
    r = client.post("/api/organizations/soru-anlama", json={"riza": True}, headers=h)
    assert r.status_code == 409
    assert _org(db_session).ai_yurtdisi_riza is False
    assert client.post("/api/organizations/soru-anlama", json={"riza": False}, headers=h).status_code == 200


def test_ac_kapat_ve_ozel_sunucu_tercihi_rizayi_silmez(client, db_session, groq):
    h = _hesap_ac(client)
    r = client.post("/api/organizations/soru-anlama", json={"riza": True}, headers=h)
    assert r.status_code == 200 and r.json()["riza"] is True and "Groq" in r.json()["mesaj"]
    org = _org(db_session)
    db_session.refresh(org)
    assert org.ai_yurtdisi_riza is True and org.ai_riza_tarihi >= soru_anlama.RIZA_BASLANGICI
    # Kendi sunucumuzdaki model tercihi (ayrı anahtar) soru anlama rızasını temizlememeli.
    assert client.post("/api/organizations/ai-riza", json={"riza": False}, headers=h).status_code == 200
    db_session.refresh(org)
    assert org.ai_yurtdisi_riza is True
    assert client.get("/api/yapay-zeka", headers=h).json()["soru_anlama"]["riza"] is True
    assert client.post("/api/organizations/soru-anlama", json={"riza": False}, headers=h).status_code == 200
    db_session.refresh(org)
    assert org.ai_yurtdisi_riza is False and org.ai_riza_tarihi is None


def test_eski_tarihli_yurtdisi_rizasi_gecersiz(client, db_session, groq):
    """Gemini döneminden kalan ai_yurtdisi_riza=True kayıtları soru anlamayı açmaz ve temizlenir."""
    from datetime import datetime
    h = _hesap_ac(client)
    org = _org(db_session)
    org.ai_yurtdisi_riza, org.ai_riza_tarihi = True, datetime(2026, 9, 30)
    db_session.commit()
    client.post("/api/sor", json={"question": "3 kişi daha alacağız destek var mı"}, headers=h)
    assert groq.mesajlar == []
    client.post("/api/organizations/ai-riza", json={"riza": False}, headers=h)
    db_session.refresh(org)
    assert org.ai_yurtdisi_riza is False


# ------------------------------------------------------------------ giden veri
def test_rizasiz_groqa_hicbir_sey_gitmez(client, groq):
    h = _hesap_ac(client)
    assert client.post("/api/sor", json={"question": "Ekip büyütmek istiyoruz"}, headers=h).status_code == 200
    assert client.post("/api/sor/akis", json={"question": "Ekip büyütmek istiyoruz"}, headers=h).status_code == 200
    assert groq.mesajlar == []


def test_groqa_yalniz_maskeli_soru_gider(client, groq):
    h = _hesap_ac(client)
    client.put("/api/profil", json={"sektor": "imalat", "bolge": "Konya", "calisan_sayisi": 12,
                                    "yillik_ciro": 7_500_000}, headers=h)
    client.post("/api/organizations/soru-anlama", json={"riza": True}, headers=h)
    soru = "Ben Zeynep Arıkan, Arıkan Örgü olarak 3 kişi daha alacağız; zeynep@arikan.com.tr 0532 111 22 33"
    r = client.post("/api/sor", json={"question": soru}, headers=h)
    assert r.status_code == 200
    assert len(groq.mesajlar) == 1
    giden = json.dumps(groq.mesajlar[0], ensure_ascii=False)
    for gizli in ("Zeynep", "Arıkan", "arikan", "@", "0532", "3 kişi", "7500000", "7.500.000", "Konya", "imalat"):
        assert gizli not in giden, gizli
    assert [m["role"] for m in groq.mesajlar[0]] == ["system", "user"]
    assert "N kişi daha alacağız" in groq.mesajlar[0][1]["content"]


def test_groq_hatasinda_yanit_yine_uretilir(client, groq):
    groq.hata = RuntimeError("Groq HTTP 503")
    h = _hesap_ac(client)
    client.post("/api/organizations/soru-anlama", json={"riza": True}, headers=h)
    r = client.post("/api/sor", json={"question": "Ekip büyütmek istiyoruz"}, headers=h)
    assert r.status_code == 200 and r.json()["message"]
    assert len(groq.mesajlar) == 1


# ------------------------------------------------------------------ yanıt hattı
@pytest.fixture
def veri(db_session, monkeypatch):
    monkeypatch.setattr(rag, "SessionLocal", sessionmaker(bind=db_session.get_bind()))
    db_session.add(Tesvik(id=71, kurum="SGK / İŞKUR", baslik="İlave İstihdam Teşviki", ozet="İşverene prim desteği",
                          detay="d", aktif_mi=True, kaynak_url="https://www.sgk.gov.tr/ilave",
                          tesvil_tutari="Asgari ücret tutarında prim desteği", uygunluk_kriterleri={"sektorler": ["genel"]}))
    db_session.add(Tesvik(id=72, kurum="KOSGEB", baslik="Ekip Ruhu Eğitim Programı", ozet="Ekip büyütmek isteyenlere eğitim",
                          detay="d", aktif_mi=True, kaynak_url="https://www.kosgeb.gov.tr/ekip",
                          tesvil_tutari="50.000 TL", uygunluk_kriterleri={"sektorler": ["genel"]}))
    db_session.commit()


SORU = "Ekip büyütmek istiyoruz, ne yapabiliriz?"


def _etiket(ihtiyac=("istihdam",), gonderildi=True):
    return soru_anlama.Etiketler(soru_anlama._anahtar(SORU), frozenset(), tuple(ihtiyac), "m", gonderildi)


def test_etiket_kayit_havuzuna_ihtiyac_programini_katar(veri):
    olmadan = [t.id for t in rag.answer_akis(SORU, None, llm_kullan=False).__next__()[1]]
    ile = [t.id for t in rag.answer_akis(SORU, None, llm_kullan=False, soru_etiketleri=_etiket()).__next__()[1]]
    assert 71 not in olmadan, "kalıplar 'ekip büyütmek'i istihdam saymıyor (Groq'un kattığı fark)"
    assert 71 in ile


def test_yontem_notu_gonderimi_soyler(veri):
    metin = "".join(v for t, v in rag.answer_akis(SORU, None, llm_kullan=False, soru_etiketleri=_etiket())
                    if t == "parca")
    assert soru_anlama.YONTEM_NOTU in metin
    yerel = rag.answer(SORU, None, llm_kullan=False)
    assert soru_anlama.YONTEM_NOTU not in yerel and "sunucumuzdan çıkmadı" in yerel
    onbellek = rag.answer(SORU, None, llm_kullan=False, soru_etiketleri=_etiket(gonderildi=False))
    assert "sunucumuzdan çıkmadı" in onbellek


def test_adiyla_anilan_program_ya_da_kurum_groqa_gitmez(client, groq, veri):
    """Ad eşleştirmesi yanıtı kurar; Groq etiketi aramayı kaydırıyordu (ölçüm 2026-10-12: IPARD sorusu 1507'ye döndü)."""
    h = _hesap_ac(client)
    client.post("/api/organizations/soru-anlama", json={"riza": True}, headers=h)
    for soru in ("Ekip Ruhu Eğitim Programı nedir?", "KOSGEB'den bizim için ne var?"):
        assert client.post("/api/sor", json={"question": soru}, headers=h).status_code == 200
    assert groq.mesajlar == []
    assert client.post("/api/sor", json={"question": SORU}, headers=h).status_code == 200
    assert len(groq.mesajlar) == 1, "adsız soru gönderilir"


def test_baglam_istekten_sizmaz(veri):
    list(rag.answer_akis(SORU, None, llm_kullan=False, soru_etiketleri=_etiket()))
    assert soru_anlama.etkin_etiket() is None
    from app.ihtiyac import soru_ihtiyaclari
    assert "istihdam" not in soru_ihtiyaclari(SORU)
