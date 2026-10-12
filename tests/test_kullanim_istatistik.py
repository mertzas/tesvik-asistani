"""/api/analytics/usage: işlem sayısı ve depolama gerçek veriden (2026-10-13; önceden ikisi sabit 0 dönüyordu)."""
import uuid
from datetime import datetime, timedelta, timezone

from app.models import BasvuruTakibi, Query, Tesvik


def _hesap(client):
    r = client.post("/api/auth/signup", json={"email": f"k{uuid.uuid4().hex[:8]}@example.com", "password": "Parola123",
                                              "full_name": "A", "company_name": "B"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return h, uuid.UUID(client.get("/api/organizations/me", headers=h).json()["id"])


def test_islem_ve_depolama_gercek_veriden(client, db_session):
    h, org = _hesap(client)
    bos = client.get("/api/analytics/usage", headers=h).json()["usage_stats"]
    assert bos["queries_this_month"] == 0 and bos["api_calls_this_month"] == 0

    simdi = datetime.now(timezone.utc)
    db_session.add(Tesvik(id=501, kurum="KOSGEB", baslik="P", ozet="o", detay="d", aktif_mi=True))
    db_session.add_all([
        Query(org_id=org, question="KOSGEB desteği", results=[{"id": 1, "baslik": "x" * 2000}], created_at=simdi),
        Query(org_id=org, question="eski soru", results=[], created_at=simdi - timedelta(days=45)),
        BasvuruTakibi(org_id=org, tesvik_id=501, isaretli=["b:1"], taslak="T" * 3000,
                      taslak_tarihi=(simdi - timedelta(days=2)).replace(tzinfo=None)),
    ])
    db_session.commit()

    s = client.get("/api/analytics/usage", headers=h).json()["usage_stats"]
    assert s["queries_this_month"] == 1, "son 30 gün; 45 günlük soru sayılmaz"
    assert s["api_calls_this_month"] == 2, "1 soru + 1 taslak"
    assert s["storage_used_mb"] > bos["storage_used_mb"] and s["storage_used_mb"] > 0.004
