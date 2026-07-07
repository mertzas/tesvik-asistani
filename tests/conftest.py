import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models import Base, get_db

# Use in-memory SQLite for tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


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
