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
def _fresh_db():
    """Her testten once temiz bir sema olustur, testten sonra sil - testler
    arasi veri sizmasini (orn. ayni email'in iki farkli testte carpismasi)
    engeller."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


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
