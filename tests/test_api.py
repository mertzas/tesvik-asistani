import pytest
from fastapi import status


def test_get_current_organization(client, test_user_token):
    """Test getting current organization"""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    response = client.get("/api/organizations/me", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "id" in data
    assert "plan" in data
    assert data["plan"] == "free"


def test_get_org_without_auth(client):
    """Test getting org without authentication"""
    response = client.get("/api/organizations/me")
    # FastAPI'nin HTTPBearer'i (auto_error=True) header hic yoksa 401
    # "Not authenticated" doner - 403 sadece gecersiz/eksik yetki
    # durumlari icin degil, bu kutuphanenin guncel standart davranisi.
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_ask_question_success(client, test_user_token):
    """Test asking a question"""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    payload = {"question": "KOSGEB destekleri"}

    response = client.post("/api/sor", json=payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "query_id" in data
    assert "results" in data
    assert data["question"] == "KOSGEB destekleri"


def test_ask_empty_question(client, test_user_token):
    """Test asking empty question"""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    payload = {"question": ""}

    response = client.post("/api/sor", json=payload, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_query_history(client, test_user_token):
    """Test getting query history"""
    headers = {"Authorization": f"Bearer {test_user_token}"}

    # Ask a question first
    payload = {"question": "Test question"}
    client.post("/api/sor", json=payload, headers=headers)

    # Get history
    response = client.get("/api/queries/history", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 1
    assert data[0]["question"] == "Test question"


def test_analytics_usage(client, test_user_token):
    """Test getting usage analytics"""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    response = client.get("/api/analytics/usage", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "usage_stats" in data
    assert "queries_this_month" in data["usage_stats"]
    assert data["usage_stats"]["queries_limit"] == 5  # Free plan


def test_rate_limiting_free_plan(client, test_user_token):
    """Test rate limiting for free plan"""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    payload = {"question": "Test"}

    # Ask 5 questions (free limit)
    for i in range(5):
        response = client.post("/api/sor", json=payload, headers=headers)
        assert response.status_code == status.HTTP_200_OK

    # 6th question should be rejected
    response = client.post("/api/sor", json=payload, headers=headers)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_legacy_sor_endpoint(client):
    """Test legacy /sor endpoint (without auth)"""
    payload = {"question": "KOSGEB"}
    response = client.post("/sor", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert "cevap" in response.json()


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ok"
