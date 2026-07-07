import pytest
from fastapi import status


def test_signup_success(client, test_org_data):
    """Test user signup"""
    response = client.post("/api/auth/signup", json=test_org_data)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == test_org_data["email"]


def test_signup_duplicate_email(client, test_org_data):
    """Test signup with duplicate email"""
    client.post("/api/auth/signup", json=test_org_data)
    response = client.post("/api/auth/signup", json=test_org_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already" in response.json()["detail"].lower()


def test_signup_weak_password(client, test_org_data):
    """Test signup with weak password"""
    test_org_data["password"] = "weak"
    response = client.post("/api/auth/signup", json=test_org_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_login_success(client, test_org_data):
    """Test user login"""
    client.post("/api/auth/signup", json=test_org_data)

    login_data = {
        "email": test_org_data["email"],
        "password": test_org_data["password"]
    }
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()


def test_login_wrong_password(client, test_org_data):
    """Test login with wrong password"""
    client.post("/api/auth/signup", json=test_org_data)

    login_data = {
        "email": test_org_data["email"],
        "password": "wrongpassword"
    }
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_nonexistent_user(client):
    """Test login with nonexistent user"""
    login_data = {
        "email": "nonexistent@example.com",
        "password": "password123"
    }
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
