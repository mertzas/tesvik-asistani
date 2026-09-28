"""app/sifreleme.py testleri.

İKAS OAuth token'ları kullanıcının mağaza verisine erişim sağlar ve
veritabanında AÇIK METİN duruyordu (KVKK metni yazılırken tespit edildi,
2026-09-27). Bu testler şifrelemenin gerçekten diske uygulandığını ve
sürüm geçişinin mevcut bağlantıları koparmadığını sabitliyor.
"""
import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, IkasBaglanti, Organization
from app.sifreleme import ONEK, SifreliMetin, coz, onbellegi_temizle, sifrele


def test_sifrele_coz_yuvarlak_gider_gelir():
    acik = "ikas-erisim-anahtari-abc123"
    sifreli = sifrele(acik)
    assert sifreli != acik
    assert acik not in sifreli, "açık metin şifreli değerin içinde görünmemeli"
    assert coz(sifreli) == acik


def test_sifreli_deger_onek_tasir():
    """Ön ek olmadan bir değerin şifreli mi açık metin mi olduğu anlaşılamaz;
    sürüm geçişi (eski açık metin kayıtlar) bu ön eke dayanıyor."""
    assert sifrele("x").startswith(ONEK)


def test_ayni_deger_farkli_sifreli_metin_uretir():
    """Fernet rastgele IV kullanır; aynı token iki kez şifrelendiğinde aynı
    çıktı verirse saldırgan eşit değerleri eşleştirebilir."""
    a, b = sifrele("ayni-token"), sifrele("ayni-token")
    assert a != b
    assert coz(a) == coz(b) == "ayni-token"


def test_iki_kez_sifreleme_engellenir():
    """Zaten şifreli bir değeri tekrar şifrelemek, çözerken tek katman
    açıldığı için bozuk veri üretirdi."""
    bir = sifrele("token")
    assert sifrele(bir) == bir
    assert coz(bir) == "token"


def test_none_degeri_korunur():
    assert sifrele(None) is None
    assert coz(None) is None


def test_eski_sifresiz_deger_oldugu_gibi_doner():
    """SÜRÜM GEÇİŞİ: veritabanındaki eski kayıtlar şifresiz. Çözmeye
    çalışıp hata vermek mevcut İKAS bağlantılarını koparırdı."""
    assert coz("mock-access-token-eski") == "mock-access-token-eski"


def test_yanlis_anahtarla_cozulemez_ve_none_doner(monkeypatch):
    """Anahtar değişirse (ör. SECRET_KEY döndürüldü) değer uydurulmamalı;
    None dönmeli ki çağıran taraf bağlantının yenilenmesi gerektiğini
    anlasın."""
    sifreli = sifrele("gizli-token")

    monkeypatch.setenv("IKAS_TOKEN_KEY", "tamamen-baska-bir-anahtar")
    onbellegi_temizle()
    try:
        assert coz(sifreli) is None
    finally:
        monkeypatch.delenv("IKAS_TOKEN_KEY", raising=False)
        onbellegi_temizle()


# ------------------------------------------------------- sütun düzeyinde

@pytest.fixture
def gecici_db(tmp_path):
    yol = tmp_path / "sifre.db"
    motor = create_engine(f"sqlite:///{yol}",
                          connect_args={"check_same_thread": False})
    Base.metadata.create_all(motor)
    yield motor, str(yol)
    motor.dispose()


def test_diske_sifreli_yazilir_uygulamaya_duz_gelir(gecici_db):
    """Asıl güvence: ORM düz metin görür ama DİSKTE açık metin yoktur.

    Şifreleme çağrı yerlerinde değil sütun tipinde yapılıyor; böylece
    ileride eklenecek yeni bir çağrı yerinde unutulması mümkün değil.
    """
    motor, yol = gecici_db
    Oturum = sessionmaker(bind=motor)

    db = Oturum()
    org = Organization(name="Test", email="t@example.com")
    db.add(org)
    db.commit()
    db.add(IkasBaglanti(org_id=org.id, store_name="magaza",
                        access_token="GIZLI-ERISIM-999",
                        refresh_token="GIZLI-YENILEME-888"))
    db.commit()
    db.close()

    ham = sqlite3.connect(yol).execute(
        "select access_token, refresh_token from ikas_baglanti").fetchone()
    assert "GIZLI-ERISIM" not in ham[0], "açık metin diske yazılmış!"
    assert "GIZLI-YENILEME" not in ham[1], "açık metin diske yazılmış!"
    assert ham[0].startswith(ONEK)

    db2 = Oturum()
    kayit = db2.query(IkasBaglanti).first()
    assert kayit.access_token == "GIZLI-ERISIM-999"
    assert kayit.refresh_token == "GIZLI-YENILEME-888"
    db2.close()


def test_sutun_tipi_dogru_baglanmis():
    """Sütunlar düz String'e geri dönerse şifreleme sessizce kaybolur."""
    for alan in ("access_token", "refresh_token"):
        tip = IkasBaglanti.__table__.columns[alan].type
        assert isinstance(tip, SifreliMetin), f"{alan} artık şifrelenmiyor"


def test_sifresiz_kayit_okunabilir_kalir(gecici_db):
    """Sürüm geçişi: elle (şifresiz) yazılmış eski satır hâlâ okunabilmeli."""
    motor, yol = gecici_db
    Oturum = sessionmaker(bind=motor)
    db = Oturum()
    org = Organization(name="Test", email="t@example.com")
    db.add(org)
    db.commit()
    org_id = str(org.id)
    db.close()

    ham = sqlite3.connect(yol)
    ham.execute(
        "insert into ikas_baglanti (id, org_id, store_name, access_token) "
        "values (?, ?, ?, ?)",
        ("11111111-1111-1111-1111-111111111111", org_id, "eski",
         "eski-sifresiz-token"))
    ham.commit()

    db2 = Oturum()
    kayit = db2.query(IkasBaglanti).filter(
        IkasBaglanti.store_name == "eski").first()
    assert kayit.access_token == "eski-sifresiz-token"
    db2.close()
