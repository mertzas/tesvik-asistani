"""KVKK m.11 silme hakkı: DELETE /api/organizations/me (parola teyidi + açık onay).
Denetim 2026-10-07: aydınlatma metni silmeyi vaat ediyordu, self-service yol yoktu."""
from app.models import FinancialProfile, Organization, Query, User

HESAP = {"email": "sil@example.com", "password": "GucluSifre123", "full_name": "S", "company_name": "S Ltd"}


def _hazirla(client):
    h = {"Authorization": f"Bearer {client.post('/api/auth/signup', json=HESAP).json()['access_token']}"}
    client.post("/api/organizations/upgrade", json={"plan": "pro"}, headers=h)  # varsa; başarısızlığı önemli değil
    client.post("/api/sor", json={"question": "KOSGEB desteği"}, headers=h)
    return h


def test_silme_parola_ve_onay_ister(client, db_session):
    h = _hazirla(client)
    assert client.request("DELETE", "/api/organizations/me", json={"password": "GucluSifre123", "onay": False},
                          headers=h).status_code == 400
    assert client.request("DELETE", "/api/organizations/me", json={"password": "Yanlis123", "onay": True},
                          headers=h).status_code == 401
    assert db_session.query(Organization).count() == 1


def test_silme_tum_org_verisini_kaldirir(client, db_session):
    h = _hazirla(client)
    org = db_session.query(Organization).first()
    db_session.add(FinancialProfile(org_id=org.id, sektor="imalat"))
    db_session.commit()
    assert db_session.query(Query).count() == 1

    r = client.request("DELETE", "/api/organizations/me", json={"password": "GucluSifre123", "onay": True}, headers=h)
    assert r.status_code == 200, r.text
    db_session.expire_all()
    for model in (Organization, User, Query, FinancialProfile):
        assert db_session.query(model).count() == 0, model.__name__
    # Eski token artık geçersiz, giriş yapılamaz
    assert client.get("/api/organizations/me", headers=h).status_code == 401
    assert client.post("/api/auth/login", json={"email": HESAP["email"], "password": HESAP["password"]}).status_code == 401


def test_silme_yetkisiz_401(client):
    assert client.request("DELETE", "/api/organizations/me", json={"password": "x", "onay": True}).status_code == 401
