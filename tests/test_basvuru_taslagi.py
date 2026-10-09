"""Başvuru ön taslağı (app/basvuru_taslagi.py + POST /api/basvuru-listesi/{id}/taslak), 2026-10-08.
Gerçek Claude çağrısı YOK: _claude_istek her testte yamalanır."""
import subprocess
import sys
from pathlib import Path

import pytest

from app import basvuru_taslagi
from app.models import BasvuruTakibi, FinancialProfile, Organization, PlanType, Tesvik, User, settings

KOK = Path(__file__).resolve().parent.parent
CAGRILAR = []


@pytest.fixture(autouse=True)
def sahte_claude(monkeypatch):
    CAGRILAR.clear()
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-anahtari")

    def _sahte(sistem, kullanici):
        CAGRILAR.append((sistem, kullanici))
        return ("## 1. İşletme tanıtımı\nMetin [DOLDURUN: kuruluş yılı]\n## 2. Projenin amacı ve gerekçesi\nx",
                {"giris": 1200, "cikis": 400, "durma": "end_turn"})
    monkeypatch.setattr(basvuru_taslagi, "_claude_istek", _sahte)


@pytest.fixture
def hazir(client, db_session):
    """PRO plan, rızalı, profilli kullanıcı + belge listeli teşvik. (başlık, kurum) döner."""
    db_session.add(Tesvik(id=9, kurum="KOSGEB", baslik="Küresel Rekabetçilik", ozet="o", detay="d", aktif_mi=True,
                          kaynak_url="https://t/9", uygunluk_kriterleri={"sektorler": ["genel"]},
                          basvuru_sartlari=["KOBİ olmak"], gerekli_belgeler=["Proje Başvuru Formu"],
                          basvuru_yeri="KBS"))
    db_session.commit()
    r = client.post("/api/auth/signup", json={"email": "a@example.com", "password": "Parola123", "full_name": "A",
                                              "company_name": "B", "ai_yurtdisi_riza": True})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    org = db_session.query(Organization).join(User, User.org_id == Organization.id).filter(
        User.email == "a@example.com").one()
    org.plan = PlanType.PRO
    db_session.add(FinancialProfile(org_id=org.id, sektor="imalat", bolge="Bursa", calisan_sayisi=18,
                                    yillik_ciro=32e6, nace_kodu="25.62"))
    db_session.commit()
    return h, org


def _olustur(client, h):
    return client.post("/api/basvuru-listesi/9/taslak?yontem=yapay_zeka", headers=h)


def test_taslak_uretilir_saklanir_ve_belgeler_listeden_gelir(client, db_session, hazir):
    h, _ = hazir
    r = _olustur(client, h)
    assert r.status_code == 200, r.text
    taslak = r.json()["taslak"]
    assert taslak.startswith("> **Ön taslak — resmi başvuru formu değildir.**")
    assert "## 6. Hazırlanacak belgeler ve şartlar" in taslak and "- [ ] Proje Başvuru Formu" in taslak
    assert r.json()["taslak_tarihi"] and r.json()["takipte"] is True
    # profil ve program bilgisi istemde; boş profil alanı yok
    _, kullanici = CAGRILAR[0]
    assert "Küresel Rekabetçilik" in kullanici and "sektör: imalat" in kullanici and "TRL" not in kullanici
    # GET'te geri gelir (tekrar ücret ödenmez)
    assert client.get("/api/basvuru-listesi/9", headers=h).json()["taslak"] == taslak
    assert db_session.query(BasvuruTakibi).one().taslak_model == settings.CLAUDE_MODEL[:60]


def test_free_plan_rizasiz_ve_profilsiz_cagri_yapilmaz(client, db_session, hazir):
    h, org = hazir
    org.plan = PlanType.FREE
    db_session.commit()
    assert _olustur(client, h).status_code == 403
    org.plan = PlanType.PRO
    org.ai_yurtdisi_riza = False
    db_session.commit()
    r = _olustur(client, h)
    assert r.status_code == 403 and "rıza" in r.json()["detail"]
    org.ai_yurtdisi_riza = True
    db_session.query(FinancialProfile).delete()
    db_session.commit()
    assert _olustur(client, h).status_code == 404
    assert CAGRILAR == [], "koşullar sağlanmadan ücretli çağrı yapılmamalı"


def test_servis_yoksa_503_ve_hata_kaydi_bozmaz(client, db_session, hazir, monkeypatch):
    h, _ = hazir
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    assert _olustur(client, h).status_code == 503
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-anahtari")

    def _patla(sistem, kullanici):
        raise RuntimeError("kredi bitti")
    monkeypatch.setattr(basvuru_taslagi, "_claude_istek", _patla)
    r = _olustur(client, h)
    assert r.status_code == 503 and "kredi" not in r.json()["detail"], "iç hata ayrıntısı sızmamalı"
    assert db_session.query(BasvuruTakibi).count() == 0


def test_gunluk_sinir(client, hazir):
    h, _ = hazir
    for _ in range(5):
        assert _olustur(client, h).status_code == 200
    r = _olustur(client, h)
    assert r.status_code == 429 and len(CAGRILAR) == 5


def test_max_tokens_kesilmesi_bildirilir(client, hazir, monkeypatch):
    h, _ = hazir
    monkeypatch.setattr(basvuru_taslagi, "_claude_istek",
                        lambda s, k: ("## 1. İşletme tanıtımı\nyarım", {"durma": "max_tokens"}))
    assert "uzunluk sınırında kesildi" in _olustur(client, h).json()["taslak"]


def test_hesap_silmede_taslak_da_silinir(client, db_session, hazir):
    h, _ = hazir
    _olustur(client, h)
    r = client.request("DELETE", "/api/organizations/me", headers=h, json={"password": "Parola123", "onay": True})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.query(BasvuruTakibi).count() == 0


def test_goc_taslak_sutunlari(tmp_path, monkeypatch):
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
    sutunlar = {c["name"] for c in inspect(motor).get_columns("basvuru_takipleri")}
    assert {"taslak", "taslak_tarihi", "taslak_model"} <= sutunlar
    command.downgrade(cfg, "i6d8f0a2b678")
    assert "taslak" not in {c["name"] for c in inspect(motor).get_columns("basvuru_takipleri")}
    command.upgrade(cfg, "head")


def test_kvkk_metni_taslak_aktarimini_ve_saklamayi_soyler():
    html = (KOK / "app/static/kvkk.html").read_text(encoding="utf-8")
    assert "ön taslağı yazılması için de gönderilir" in html and "basvuru_takipleri.taslak" in html


def test_self_test_bayragi():
    r = subprocess.run([sys.executable, "-m", "app.basvuru_taslagi", "--self-test"], cwd=KOK,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    import re
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= 8


# ---------------------------------------------------------------- yapay zekâsız şablon taslak (varsayılan, 2026-10-08)
def test_sablon_taslak_free_planda_rizasiz_ve_claude_cagirmadan(client, db_session, hazir):
    h, org = hazir
    org.plan, org.ai_yurtdisi_riza = PlanType.FREE, False
    db_session.commit()
    r = client.post("/api/basvuru-listesi/9/taslak", headers=h)          # yontem varsayılanı: sablon
    assert r.status_code == 200, r.text
    d = r.json()
    assert CAGRILAR == [], "şablon taslak Anthropic'e gitmemeli"
    # taslak neye hazırlandığını ilk satırda söyler (2026-10-10 kullanıcı geri bildirimi)
    assert d["taslak"].startswith("> **Ne için:** Küresel Rekabetçilik başvurusunda") and "**Nereye girilir:** KBS" in d["taslak"]
    assert "> **Ön taslak" in d["taslak"] and "yapay zekâ kullanılmadan" in d["taslak"]
    assert "Bursa" in d["taslak"] and "NACE 25.62" in d["taslak"] and "32.000.000 TL" in d["taslak"]
    assert "- [ ] Proje Başvuru Formu" in d["taslak"] and "Başvuru yeri: KBS" in d["taslak"]
    kayit = db_session.query(BasvuruTakibi).filter(BasvuruTakibi.tesvik_id == 9).one()
    from app.sablon_taslak import MODEL_ADI
    assert kayit.taslak_model == MODEL_ADI


def test_sablon_taslak_profilsiz_404_ve_yapay_zeka_kurallari_korunur(client, db_session, hazir):
    h, org = hazir
    db_session.query(FinancialProfile).delete()
    db_session.commit()
    assert client.post("/api/basvuru-listesi/9/taslak", headers=h).status_code == 404
    org.ai_yurtdisi_riza = False
    db_session.commit()
    assert client.post("/api/basvuru-listesi/9/taslak?yontem=yapay_zeka", headers=h).status_code == 403
    assert client.post("/api/basvuru-listesi/9/taslak?yontem=baska", headers=h).status_code == 422


@pytest.mark.parametrize("modul,en_az", [("app.sablon_taslak", 13), ("app.form_sablonlari", 5)])
def test_sablon_self_test(modul, en_az):
    import re
    r = subprocess.run([sys.executable, "-m", modul, "--self-test"], cwd=KOK, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= en_az, r.stdout


# ---------------------------------------------------------------- taslak sihirbazı (sablon-v2, 2026-10-08)
@pytest.fixture
def ar_ge(client, db_session, hazir):
    h, org = hazir
    db_session.add(Tesvik(id=34, kurum="TUBITAK", baslik="1501 - TÜBİTAK Sanayi Ar-Ge Projeleri Destekleme Programı",
                          ozet="o", detay="d", aktif_mi=True, kaynak_url="https://t/34",
                          tesvil_tutari="Hibe: ilk 5 proje %75 (en fazla 20 M TL/proje), 6. ve sonrası %60",
                          tutari_max=20_000_000,
                          tutari_hesaplama_formulu="Destek = giderler × %75 ya da × %60. Desteklenen giderler: personel; malzeme.",
                          basvuru_sartlari=["Sermaye şirketi olmak", "Proje başvurusundan önce tamamlanmış Ar-Ge faaliyetleri desteklenmez"],
                          gerekli_belgeler=["Proje öneri formu"], uygunluk_kriterleri={"sektorler": ["arge"]}))
    db_session.commit()
    return h


def test_sihirbaz_sorulari(client, ar_ge):
    s = client.get("/api/basvuru-listesi/34/taslak-sorulari", headers=ar_ge).json()
    assert s["turler"][0] == "arge" and s["oran_secenekleri"] == [75.0, 60.0] and s["ust_limit"] == 20_000_000
    assert s["gider_kalemleri"] == ["personel", "malzeme"] and s["cevaplar"] is None
    # 1501 resmi form şablonuna bağlı (app/form_sablonlari.py): sorular AGY100 A-E bölümleri
    assert [q["anahtar"] for q in s["gerekce"]][:4] == ["A3", "B1", "B2", "B3"]
    assert s["form"]["ad"].startswith("TÜBİTAK Proje Öneri") and "M011 Personel" in s["form"]["tablolar"][0]


def test_sihirbaz_cevaplari_taslaga_girer_saklanir_ve_yeniden_kullanilir(client, db_session, ar_ge):
    cev = {"proje_adi": "Yeni fermantasyon süreci", "gerekce": {"B2": "Raf ömrü 7 gün"},
           "faaliyetler": [{"ad": "Prototip", "baslangic": "2027-01", "bitis": "2027-06"}],
           "butce": [{"kalem": "personel", "tutar": 2_000_000}, {"kalem": "malzeme", "tutar": 500_000}],
           "destek_orani": 75}
    d = client.post("/api/basvuru-listesi/34/taslak", headers=ar_ge, json={"cevaplar": cev}).json()
    assert "Yeni fermantasyon süreci" in d["taslak"] and "| Prototip | Ocak 2027 | Haziran 2027 |" in d["taslak"]
    assert "**2.500.000 TL**" in d["taslak"] and "= **1.875.000 TL**" in d["taslak"]
    # Cevap resmi formun başlığı altında; cevapsız bölüm formun kendi açıklamasıyla işaretli kalır.
    assert "### B.2 Projenin Teknoloji Düzeyi\n\nRaf ömrü 7 gün" in d["taslak"]
    assert "### B.4 Projenin Yenilikçi Yönleri\n\n[DOLDURUN" in d["taslak"]
    assert "Formda ayrıca doldurulacak tablolar" in d["taslak"] and "M030 Dönemsel giderler" in d["taslak"]
    assert d["taslak_cevaplar"]["proje_adi"] == "Yeni fermantasyon süreci"
    # Cevapsız yeniden oluşturma kayıtlı cevapları kullanır; sorular ucu da döndürür.
    d2 = client.post("/api/basvuru-listesi/34/taslak", headers=ar_ge).json()
    assert "Yeni fermantasyon süreci" in d2["taslak"]
    assert client.get("/api/basvuru-listesi/34/taslak-sorulari", headers=ar_ge).json()["cevaplar"]["destek_orani"] == 75


def test_kosgeb_kapasite_gelistirme_resmi_form(client, db_session, hazir):
    h, _ = hazir
    db_session.add(Tesvik(id=8, kurum="KOSGEB", baslik="Kapasite Geliştirme Destek Programı", ozet="o", detay="d",
                          aktif_mi=True, kaynak_url="https://k/8", tesvil_tutari="%60 hibe", tutari_max=5_000_000,
                          uygunluk_kriterleri={"sektorler": ["imalat"]}))
    db_session.commit()
    s = client.get("/api/basvuru-listesi/8/taslak-sorulari", headers=h).json()
    assert [q["anahtar"] for q in s["gerekce"]] == [f"2.{i}" for i in range(11, 21)]
    assert s["form"]["kaynak"].startswith("https://webdosya.kosgeb.gov.tr/") and "2.9 Üretim-satış planı" in s["form"]["tablolar"]
    t = client.post("/api/basvuru-listesi/8/taslak", headers=h,
                    json={"cevaplar": {"gerekce": {"2.13": "Talep kapasiteyi aşıyor"}}}).json()["taslak"]
    assert "### 2.13 Projenin Amacı ve Gerekçesi\n\nTalep kapasiteyi aşıyor" in t
    assert "### 2.20 Sürdürülebilirlik" in t and "2.10 Yatırımın geri dönüş süresi" in t


def test_kural_isaretlenmez_ilerlemeye_sayilmaz(client, ar_ge):
    d = client.get("/api/basvuru-listesi/34", headers=ar_ge).json()
    kural = [m for m in d["maddeler"] if m["kural"]]
    assert [m["metin"] for m in kural] == ["Proje başvurusundan önce tamamlanmış Ar-Ge faaliyetleri desteklenmez"]
    assert d["toplam"] == sum(m["tur"] in ("belge", "adim") for m in d["maddeler"])
    taslak = client.post("/api/basvuru-listesi/34/taslak", headers=ar_ge).json()["taslak"]
    assert "- ⚠ Proje başvurusundan önce" in taslak and "- [ ] Proje başvurusundan önce" not in taslak
    # şartlar onay kutusu değil, cevap durumuyla
    assert "**Başvurabilir miyim? (şartlar)**" in taslak and "- Sermaye şirketi olmak — cevaplanmadı" in taslak


@pytest.mark.parametrize("hatali", [{"faaliyetler": [{"ad": "x", "baslangic": "2027-13"}]},
                                    {"butce": [{"kalem": "x", "tutar": -5}]}, {"destek_orani": 150},
                                    {"proje_adi": "x" * 201}])
def test_sihirbaz_gecersiz_girdi(client, ar_ge, hatali):
    assert client.post("/api/basvuru-listesi/34/taslak", headers=ar_ge, json={"cevaplar": hatali}).status_code == 422


def test_goc_taslak_cevaplar(tmp_path, monkeypatch):
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
    assert "taslak_cevaplar" in {c["name"] for c in inspect(motor).get_columns("basvuru_takipleri")}
    command.downgrade(cfg, "n1c3e5a7b234")
    assert "taslak_cevaplar" not in {c["name"] for c in inspect(motor).get_columns("basvuru_takipleri")}
    command.upgrade(cfg, "head")
