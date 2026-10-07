"""FREE plan eşleşme önizlemesi (/api/eslesme) ve OrganizationResponse.ai_yurtdisi_riza.
Denetim 2026-10-07: FREE kullanıcı 403 alıyor, ürünün ana değerini görmeden yükseltme isteniyordu."""
import app.main as m
from app.models import Organization, PlanType, Tesvik

HESAP = {"email": "o@example.com", "password": "GucluSifre123", "full_name": "O", "company_name": "O Ltd"}


def _hazirla(client, db_session, adet=6):
    h = {"Authorization": f"Bearer {client.post('/api/auth/signup', json=HESAP).json()['access_token']}"}
    for i in range(adet):
        db_session.add(Tesvik(id=900 + i, kurum="KOSGEB", baslik=f"Genel Program {i}", ozet="o", detay="d",
                              aktif_mi=True, kaynak_url=f"https://t/{i}", uygunluk_kriterleri={"sektorler": ["genel"]}))
    db_session.commit()
    assert client.put("/api/profil", json={"sektor": "imalat", "calisan_sayisi": 10}, headers=h).status_code == 200
    return h


def test_free_plan_onizleme_ilk_3(client, db_session):
    h = _hazirla(client, db_session)
    r = client.get("/api/eslesme", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["onizleme"] is True and d["toplam_eslesme"] == 6 and len(d["eslesen_tesvikler"]) == m.ONIZLEME_ADEDI


def test_pro_plan_tam_liste(client, db_session):
    h = _hazirla(client, db_session)
    org = db_session.query(Organization).first()
    org.plan = PlanType.PRO
    db_session.commit()
    d = client.get("/api/eslesme", headers=h).json()
    assert d["onizleme"] is False and len(d["eslesen_tesvikler"]) == 6 == d["toplam_eslesme"]


def test_butce_onerisi_free_hala_pro_ister(client, db_session):
    h = _hazirla(client, db_session)
    assert client.get("/api/butce-onerisi", headers=h).status_code == 403


def test_organizations_me_riza_alanini_doner(client, db_session):
    h = _hazirla(client, db_session, adet=0)
    assert client.get("/api/organizations/me", headers=h).json()["ai_yurtdisi_riza"] is False
    client.post("/api/organizations/ai-riza", json={"riza": True}, headers=h)
    assert client.get("/api/organizations/me", headers=h).json()["ai_yurtdisi_riza"] is True
