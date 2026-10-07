"""Hata yanıtları JSON olmalı (2026-10-08). Denetim 2 / Aşama D: kilitli SQLite'ta okuma/yazma düz metin
"Internal Server Error" dönüyordu."""
import logging
import sqlite3
import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as m
from app.models import Base, get_db


def test_kilitli_veritabani_json_503_ve_retry_after(tmp_path):
    yol = tmp_path / "kilitli.db"
    eng = create_engine(f"sqlite:///{yol}", connect_args={"timeout": 0.3})
    Base.metadata.create_all(bind=eng)
    Oturum = sessionmaker(bind=eng)

    def kilitli_db():
        db = Oturum()
        try:
            yield db
        finally:
            db.close()

    kilit = sqlite3.connect(yol, timeout=0, isolation_level=None)
    kilit.execute("BEGIN EXCLUSIVE")
    onceki = m.app.dependency_overrides.get(get_db)
    m.app.dependency_overrides[get_db] = kilitli_db
    try:
        t0 = time.time()
        r = TestClient(m.app).get("/api/veri-durumu")
        assert r.status_code == 503 and r.headers["content-type"].startswith("application/json")
        assert r.json() == m.DB_MESGUL_YANITI and r.headers["retry-after"] == "5"
        assert time.time() - t0 < 5
    finally:
        m.app.dependency_overrides[get_db] = onceki
        kilit.execute("ROLLBACK")
        kilit.close()
        eng.dispose()


def test_beklenmeyen_hata_json_500_ve_gunlukte_ayni_kimlik(caplog):
    def patla():
        raise RuntimeError("deneme hatasi")

    m.app.add_api_route("/_test_beklenmeyen_hata", patla)
    try:
        with caplog.at_level(logging.ERROR, logger="app.main"):
            r = TestClient(m.app, raise_server_exceptions=False).get("/_test_beklenmeyen_hata")
        assert r.status_code == 500 and r.headers["content-type"].startswith("application/json")
        kimlik = r.json()["hata_kimligi"]
        assert len(kimlik) == 12 and kimlik in r.json()["detail"]
        kayit = [k for k in caplog.records if kimlik in k.getMessage()]
        assert kayit and kayit[0].exc_info and "deneme hatasi" in str(kayit[0].exc_info[1])
        assert "deneme hatasi" not in r.text, "iç hata ayrıntısı kullanıcıya sızmamalı"
    finally:
        m.app.router.routes[:] = [rt for rt in m.app.router.routes
                                  if getattr(rt, "path", "") != "/_test_beklenmeyen_hata"]


def test_kilit_disi_veritabani_hatasi_json_500(caplog):
    from sqlalchemy.exc import OperationalError

    def patla():
        raise OperationalError("SELECT 1", {}, Exception("no such table: yok"))

    m.app.add_api_route("/_test_db_hatasi", patla)
    try:
        r = TestClient(m.app, raise_server_exceptions=False).get("/_test_db_hatasi")
        assert r.status_code == 500 and r.json()["detail"] == "Veritabanı hatası oluştu."
        assert "no such table" not in r.text
    finally:
        m.app.router.routes[:] = [rt for rt in m.app.router.routes if getattr(rt, "path", "") != "/_test_db_hatasi"]
