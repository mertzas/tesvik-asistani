"""İKAS webhook kimlik doğrulaması (Denetim 2 / Aşama E).

İKAS belgesi (ikas.dev, 2026-10-07) webhook imzası tanımlamıyor; bu yüzden doğrulama bizim tanımladığımız
adresteki mağazaya özgü HMAC belirtecine konur. Önceki hâlinde endpoint kimlik doğrulamasızdı:
herkes herhangi bir mağaza için senkronizasyon (dış API çağrısı + DB yazımı) tetikleyebiliyordu."""
import pytest

from app import ikas_panel
from app.ikas_integration import SiparisSonucu
from app.models import IkasBaglanti, Organization


@pytest.fixture
def magaza(db_session):
    org = Organization(name="Test", email="t@example.com")
    db_session.add(org)
    db_session.commit()
    db_session.add(IkasBaglanti(org_id=org.id, store_name="demomagaza", access_token="tok", baglanti_durumu="bagli"))
    db_session.commit()
    return "demomagaza"


def _sahte_senkron(monkeypatch, basarili=True):
    cagrilar = []

    def sahte(store, token, *a, **k):
        cagrilar.append(store)
        return SiparisSonucu(basarili=basarili, siparisler=[], hata=None if basarili else "ikas hatasi")

    monkeypatch.setattr(ikas_panel, "siparisleri_getir", sahte)
    monkeypatch.setattr(ikas_panel, "profili_ikas_verisiyle_guncelle", lambda *a, **k: None)
    return cagrilar


def test_belirtec_magazaya_ozgu_ve_kararli():
    a = ikas_panel.ikas_webhook_belirteci("magaza-a")
    assert a == ikas_panel.ikas_webhook_belirteci("magaza-a")
    assert a != ikas_panel.ikas_webhook_belirteci("magaza-b")
    assert len(a) >= 40 and "=" not in a


def test_dogru_belirtec_senkronu_tetikler(client, magaza, monkeypatch):
    cagrilar = _sahte_senkron(monkeypatch)
    r = client.post(f"/api/ikas/webhook/order-created/{ikas_panel.ikas_webhook_belirteci(magaza)}", json={"herhangi": "sema"})
    assert r.status_code == 200 and r.json()["status"] == "senkronize_edildi"
    assert cagrilar == [magaza]


def test_govdesiz_cagri_da_calisir(client, magaza, monkeypatch):
    """İKAS gövde şemasını belgelemiyor: belirteç mağazayı tek başına belirler."""
    _sahte_senkron(monkeypatch)
    r = client.post(f"/api/ikas/webhook/order-created/{ikas_panel.ikas_webhook_belirteci(magaza)}")
    assert r.status_code == 200


def test_yanlis_belirtec_401_ve_senkron_yok(client, magaza, monkeypatch):
    cagrilar = _sahte_senkron(monkeypatch)
    r = client.post("/api/ikas/webhook/order-created/yanlis-belirtec", json={"storeName": magaza})
    assert r.status_code == 401 and cagrilar == []


def test_belirtecsiz_eski_adres_artik_yok(client, magaza):
    r = client.post("/api/ikas/webhook/order-created", json={"storeName": magaza})
    assert r.status_code in (404, 405)


def test_bagli_olmayan_magazanin_belirteci_gecersiz(client, db_session, monkeypatch):
    org = Organization(name="T2", email="t2@example.com")
    db_session.add(org)
    db_session.commit()
    db_session.add(IkasBaglanti(org_id=org.id, store_name="beklemede", baglanti_durumu="beklemede"))
    db_session.commit()
    cagrilar = _sahte_senkron(monkeypatch)
    r = client.post(f"/api/ikas/webhook/order-created/{ikas_panel.ikas_webhook_belirteci('beklemede')}")
    assert r.status_code == 401 and cagrilar == []


def test_durum_baglanti_varsa_webhook_url_verir(client, db_session, test_org_data):
    client.post("/api/auth/signup", json=test_org_data)
    tok = client.post("/api/auth/login", json={"email": test_org_data["email"], "password": test_org_data["password"]}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert "webhook_url" not in client.get("/api/ikas/durum", headers=h).json()
    org = db_session.query(Organization).filter(Organization.email == test_org_data["email"]).one()
    db_session.add(IkasBaglanti(org_id=org.id, store_name="benimmagaza", access_token="t", baglanti_durumu="bagli"))
    db_session.commit()
    url = client.get("/api/ikas/durum", headers=h).json()["webhook_url"]
    assert url.endswith("/api/ikas/webhook/order-created/" + ikas_panel.ikas_webhook_belirteci("benimmagaza"))
