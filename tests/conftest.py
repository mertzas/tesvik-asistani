import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base, get_db

# Gercek in-memory SQLite (StaticPool ile tum baglantilar ayni DB'yi
# paylasir, aksi halde her yeni baglanti bombos bir DB gorur). Onceki
# surum "sqlite:///./test.db" (KALICI DOSYA) kullaniyordu - yorumda
# "in-memory" yazsa da degildi, ve tablolar SADECE MODUL YUKLENIRKEN BIR
# KEZ olusturuluyordu. Bu iki test calistirmasi arasinda VE ayni
# calistirma icindeki farkli testler arasinda veri sizmasina yol acti
# (orn. test_signup_success, onceki bir test calistirmasindan kalan
# "test@example.com" kaydiyla carpisip yanlislikla 400 donuyordu).
SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch):
    """Her testten once temiz bir sema olustur, testten sonra sil - testler
    arasi veri sizmasini (orn. ayni email'in iki farkli testte carpismasi)
    engeller.

    app/rag.py `SessionLocal`'i adiyla ice aktarip kendi oturumunu aciyor; get_db
    override'i onu kapsamiyor. Yerelde ./tesvik.db var oldugu icin fark edilmiyordu,
    CI'da (bos ci.db) /api/sor "no such table" ile 500 veriyordu (run 37624057827).
    Testler artik yalnizca bellek-ici DB'ye bagli."""
    Base.metadata.create_all(bind=engine)
    import app.ikas_panel
    import app.rag
    monkeypatch.setattr(app.rag, "SessionLocal", TestingSessionLocal)
    # İKAS arka plan senkronu (BackgroundTasks) kendi oturumunu açar; o da bellek-içi DB'ye bağlansın.
    monkeypatch.setattr(app.ikas_panel, "oturum_ac", TestingSessionLocal)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _hiz_sayaci_sifirla():
    """Süreç içi hız sınırı sayaçları (login/signup IP başına 10/dk) testler arasında birikmesin:
    tüm testler aynı 'testclient' IP'sinden gelir."""
    from app.rate_limit import sayac
    sayac.temizle()
    yield
    sayac.temizle()


@pytest.fixture(autouse=True)
def _gercek_smtp_yok():
    """Testler GERÇEK posta sunucusuna asla bağlanmaz (.env'de SMTP_* dolu olsa bile).

    2026-10-08: .env'e SMTP bilgileri girilince test_smtp_yoksa_istek_yine_de_basarili gerçek EmailService ile
    canlı SMTP bağlantısı denemeye başladı. Ayrı bir MonkeyPatch bağlamı kullanılır: testlerin kendi
    `monkeypatch.undo()` çağrısı bu korumayı geri alamaz. smtplib yine de çağrılırsa test teardown'da düşer
    (EmailService istisnaları yuttuğu için yalnızca kayıt tutmak yetmezdi)."""
    import smtplib
    from app.models import settings
    denemeler = []

    def _yasak(*a, **k):
        denemeler.append(a)
        raise ConnectionRefusedError("testlerde gerçek SMTP bağlantısı yasak")

    with pytest.MonkeyPatch.context() as mp:
        for ad in ("SMTP_SERVER", "SMTP_USER", "SMTP_PASSWORD"):
            mp.setattr(settings, ad, "")
            mp.delenv(ad, raising=False)
        mp.setattr(smtplib, "SMTP", _yasak)
        mp.setattr(smtplib, "SMTP_SSL", _yasak)
        yield
    assert not denemeler, f"test gerçek SMTP bağlantısı denedi: {denemeler}"


@pytest.fixture
def test_org_data():
    return {
        "email": "test@example.com",
        "password": "securepass123",
        "full_name": "Test User",
        "company_name": "Test Corp"
    }


@pytest.fixture
def test_user_token(client, test_org_data):
    """Create test user and return auth token"""
    response = client.post("/api/auth/signup", json=test_org_data)
    return response.json()["access_token"]


@pytest.fixture
def db_session():
    """Butce/eslesme testleri icin dogrudan DB oturumu (HTTP katmani olmadan
    saf hesap mantigini test etmek icin)."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _claude_cagirma(monkeypatch, request):
    """Testler GERÇEK Claude API'sine gitmesin.

    SORUN: tests/test_api.py `/api/sor` uç noktasını 8+ kez çağırıyor ve her
    çağrı canlı Anthropic API'sine gidiyordu. Sonuçları (ölçüm 2026-09-28):

      - her çağrı ~25 saniye; suit dakikalar yerine saatler sürüyordu,
      - her test koşusu kullanıcının API kotasından PARA harcıyordu,
      - testler ağ erişimine ve dış servisin o anki durumuna bağlıydı,
      - yanıt metni her seferinde farklı olduğu için deterministik değildi.

    Bu fixture `app.main.answer`'ı sabit bir metinle değiştiriyor. Uç
    noktanın kendi mantığı (yetki, kota, sorgu kaydı, hata yolları) tam
    olarak sınanmaya devam ediyor; yalnızca LLM çağrısı taklit ediliyor.

    Claude katmanının kendisi tests/test_rag.py içinde, yine ağ erişimi
    olmadan, kendi monkeypatch'leriyle test ediliyor.

    Gerçek API'ye çıkması gereken bir test olursa `@pytest.mark.canli_llm`
    ile işaretlenebilir; bu fixture onu atlar.
    """
    if request.node.get_closest_marker("canli_llm"):
        return

    def _sahte_cevap(soru, profil=None, llm_kullan=True, **_kw):
        # Imza app.rag.answer ile AYNI kalmali; aksi halde uc nokta
        # TypeError alip 500 doner ve testler gercek hatayi degil imza
        # uyusmazligini bildirir (bu bir kez oldu: llm_kullan parametresi
        # eklendiginde 4 test 500 ile dustu).
        return (f"[test] '{soru[:40]}' sorusu için örnek yanıt "
                f"(llm_kullan={llm_kullan}). "
                "Bu metin testte üretildi, Claude API çağrılmadı.")

    # app/main.py `from app.rag import answer` ile içe aktardığı için
    # yamanacak hedef app.main.answer'dır, app.rag.answer değil.
    def _sahte_akis(soru, profil=None, llm_kullan=True, **_kw):
        # app.rag.answer_akis ile AYNI olay sırası: ("kayitlar", [...]) sonra ("parca", str)...
        yield "kayitlar", []
        yield "parca", _sahte_cevap(soru, profil, llm_kullan)

    import app.main
    monkeypatch.setattr(app.main, "answer", _sahte_cevap)
    monkeypatch.setattr(app.main, "answer_akis", _sahte_akis)
