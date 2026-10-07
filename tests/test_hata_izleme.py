"""Yaşam döngüsü (on_event yerine lifespan) ve isteğe bağlı Sentry hata izleme (2026-10-08). Ağ yok: sahte taşıyıcı."""
import pytest
import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

import app.main as m
from app import hata_izleme


def test_lifespan_acilis_ve_kapanisi_cagirir(monkeypatch):
    sira = []
    monkeypatch.setattr(m, "on_startup", lambda: sira.append("acilis"))
    monkeypatch.setattr(m, "on_shutdown", lambda: sira.append("kapanis"))
    with TestClient(m.app) as c:
        assert c.get("/health").status_code in (200, 503)
        assert sira == ["acilis"]
    assert sira == ["acilis", "kapanis"]
    assert not m.app.router.on_startup and not m.app.router.on_shutdown, "on_event kalmamalı"


def test_dsn_yoksa_kapali():
    assert hata_izleme.kur("") is False and hata_izleme.kur(None) is False


class _Yakala(Transport):
    def __init__(self):
        super().__init__()
        self.olaylar = []

    def capture_envelope(self, zarf):
        olay = zarf.get_event()
        if olay:
            self.olaylar.append(olay)


@pytest.fixture
def sentry_sahte():
    tasiyici = _Yakala()
    assert hata_izleme.kur("https://anahtar@o0.ingest.de.sentry.io/1", "test", transport=tasiyici)
    yield tasiyici
    sentry_sdk.get_client().close()
    sentry_sdk.init(dsn=None)
    hata_izleme._ETKIN = False


def test_beklenmeyen_hata_kimlikle_bildirilir_kisisel_veri_gitmez(sentry_sahte):
    # Gizli değerler çalışma anında üretilir: kaynak satırı (Sentry'nin kod bağlamı) onları içermesin, test yalnızca
    # VERİ sızıntısını (yerel değişken, istek gövdesi/başlığı/sorgu dizesi) ölçsün.
    parola, belirtec, eposta = "Gizli" + "Parola9", "gizli-" + "belirtec", "kisi" + "@example.com"

    async def patla(request: m.Request):
        govde = await request.json()  # yerel değişkende parola var: gönderilmemeli
        raise RuntimeError(f"izleme denemesi ({len(govde)})")

    m.app.add_api_route("/_test_izleme", patla, methods=["POST"])
    try:
        r = TestClient(m.app, raise_server_exceptions=False).post(
            f"/_test_izleme?eposta={eposta}", json={"password": parola},
            headers={"Authorization": f"Bearer {belirtec}"})
        assert r.status_code == 500
        kimlik = r.json()["hata_kimligi"]
        sentry_sdk.flush()
        assert len(sentry_sahte.olaylar) == 1, "tek olay (logging entegrasyonu çift göndermemeli)"
        olay = sentry_sahte.olaylar[0]
        assert olay["tags"]["hata_kimligi"] == kimlik
        assert olay["exception"]["values"][-1]["value"] == "izleme denemesi (1)"
        metin = str(olay)
        for gizli in (parola, belirtec, eposta):
            assert gizli not in metin, gizli
        cerceveler = olay["exception"]["values"][-1]["stacktrace"]["frames"]
        assert all(not c.get("vars") for c in cerceveler), "yerel değişkenler gönderilmemeli"
    finally:
        m.app.router.routes[:] = [rt for rt in m.app.router.routes if getattr(rt, "path", "") != "/_test_izleme"]


def test_temizle_istek_alanlarini_siler():
    olay = {"request": {"data": {"password": "x"}, "cookies": {"a": "b"}, "query_string": "t=abc",
                        "headers": {"Authorization": "Bearer x", "User-Agent": "ua"}}}
    temiz = hata_izleme._temizle(olay)["request"]
    assert "data" not in temiz and "cookies" not in temiz and temiz["query_string"] == "[silindi]"
    assert temiz["headers"] == {"Authorization": "[silindi]", "User-Agent": "ua"}
