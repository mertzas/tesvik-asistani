"""Sunucu tarafı girdi sınırları (2026-10-08). Önceden: 5.000 karakterlik parsel adı kabul ediliyordu, geçersiz
ortam tipi 500, 100.000 karakterlik parolayla giriş passlib PasswordSizeError ile 500 veriyordu."""
import pytest

from app.schemas_cilek import AD, ACIKLAMA


@pytest.fixture
def h(client, test_user_token):
    return {"Authorization": f"Bearer {test_user_token}"}


def _parsel(client, h, **alan):
    return client.post("/api/cilek/parseller", headers=h, json={"ad": "Sera 1", "ortam_tipi": "sera", **alan})


def test_parsel_adi_siniri(client, h):
    assert _parsel(client, h, ad="x" * AD).status_code == 200
    assert _parsel(client, h, ad="x" * (AD + 1)).status_code == 422
    assert _parsel(client, h, ad="").status_code == 422


def test_gecersiz_ortam_tipi_422_olur_500_degil(client, h):
    r = _parsel(client, h, ortam_tipi="uzay_istasyonu")
    assert r.status_code == 422
    assert _parsel(client, h, ortam_tipi="acik_tarla").status_code == 200


def test_cilek_metin_alanlari_sinirli(client, h):
    pid = _parsel(client, h).json()["id"]
    uzun = "x" * 5000
    istekler = [
        ("/api/cilek/hasat", {"parsel_id": pid, "tarih": "2026-10-01", "toplanan_kasa": 3, "isci_adi": uzun}),
        ("/api/cilek/gider", {"parsel_id": pid, "tarih": "2026-10-01", "kategori": "gubre", "tutar": 5,
                              "aciklama": "x" * (ACIKLAMA + 1)}),
        ("/api/cilek/ilaclama", {"parsel_id": pid, "ilac_adi": uzun, "uygulama_tarihi": "2026-10-01T08:00:00",
                                 "phi_gun": 3}),
        ("/api/cilek/soguk-zincir", {"depo_adi": uzun, "sicaklik": 1.0}),
        ("/api/cilek/sensor-okuma", {"parsel_id": pid, "sensor_tipi": "toprak_nemi", "deger": 50, "kaynak": uzun}),
        ("/api/cilek/pazar-fiyati", {"tarih": "2026-10-01", "kaynak": "hal", "kalite_sinifi": "ekstra",
                                     "fiyat_kg": 90, "bolge": uzun}),
    ]
    for yol, govde in istekler:
        assert client.post(yol, headers=h, json=govde).status_code == 422, yol


def test_cok_uzun_parola_giris_ve_silmede_422(client, h, test_org_data):
    uzun = "x" * 100_000
    assert client.post("/api/auth/login", json={"email": test_org_data["email"], "password": uzun}).status_code == 422
    r = client.request("DELETE", "/api/organizations/me", headers=h, json={"password": uzun, "onay": True})
    assert r.status_code == 422
    # normal giriş etkilenmedi
    assert client.post("/api/auth/login", json={"email": test_org_data["email"],
                                                "password": test_org_data["password"]}).status_code == 200
