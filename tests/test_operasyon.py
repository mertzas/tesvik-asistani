"""Aşama 6 operasyon: Redis hız sayacı (sahte istemci), zamanlayıcı kilidi, /health DB kontrolü."""
import pytest

from app import rate_limit, scheduler


class _SahtePipeline:
    def __init__(self, r):
        self.r, self.cmds = r, []

    def zremrangebyscore(self, k, lo, hi):
        self.cmds.append(("zrem", k, hi))

    def zcard(self, k):
        self.cmds.append(("zcard", k))

    def zrange(self, k, a, b, withscores=False):
        self.cmds.append(("zrange", k))

    def zadd(self, k, m):
        self.cmds.append(("zadd", k, m))

    def expire(self, k, s):
        self.cmds.append(("expire", k, s))

    def execute(self):
        out = []
        for c in self.cmds:
            k = c[1]
            z = self.r.veri.setdefault(k, {})
            if c[0] == "zrem":
                for uye in [u for u, s in z.items() if s <= c[2]]:
                    del z[uye]
                out.append(None)
            elif c[0] == "zcard":
                out.append(len(z))
            elif c[0] == "zrange":
                en = sorted(z.items(), key=lambda x: x[1])[:1]
                out.append([(u.encode(), s) for u, s in en])
            elif c[0] == "zadd":
                z.update(c[2]); out.append(1)
            elif c[0] == "expire":
                out.append(True)
        self.cmds = []
        return out


class _SahteRedis:
    def __init__(self):
        self.veri = {}

    def pipeline(self):
        return _SahtePipeline(self)

    def scan_iter(self, desen):
        return list(self.veri)

    def delete(self, k):
        self.veri.pop(k, None)


class _BozukRedis:
    def pipeline(self):
        raise ConnectionError("redis yok")


def test_redis_sayaci_kayan_pencere():
    s = rate_limit._RedisSayac(_SahteRedis())
    for _ in range(3):
        assert s.izin_ver("a", 3, 60) == (True, 0)
    izin, bekle = s.izin_ver("a", 3, 60)
    assert izin is False and 1 <= bekle <= 61
    assert s.izin_ver("b", 3, 60)[0] is True, "anahtarlar bağımsız"
    s.temizle()
    assert s.izin_ver("a", 3, 60)[0] is True


def test_redis_erisilemezse_acik_kalir():
    assert rate_limit._RedisSayac(_BozukRedis()).izin_ver("a", 1, 60) == (True, 0)


def test_redis_url_bossa_surec_ici(monkeypatch):
    monkeypatch.setattr(rate_limit.settings, "REDIS_URL", "")
    assert isinstance(rate_limit._sayac_kur(), rate_limit._Sayac)


def test_redis_url_bozuksa_surec_iciye_duser(monkeypatch):
    monkeypatch.setattr(rate_limit.settings, "REDIS_URL", "redis://127.0.0.1:1/0")
    assert isinstance(rate_limit._sayac_kur(), rate_limit._Sayac)


def test_scheduler_kilidi(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "_KILIT_DOSYASI", str(tmp_path / "k.lock"))
    monkeypatch.setattr(scheduler, "_kilit_tutucu", None)
    assert scheduler.scheduler_kilidi_al() is True
    try:
        import fcntl  # noqa: F401
    except ImportError:
        pytest.skip("Windows: dosya kilidi atlanır")
    # Aynı süreçte ikinci alma denemesi (ayrı tanıtıcı) başarısız olmalı
    monkeypatch.setattr(scheduler, "_kilit_tutucu", None)
    assert scheduler.scheduler_kilidi_al() is False


def test_health_db_ve_durum_alanlari(client):
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok" and d["hiz_siniri"] in ("redis", "surec_ici") and "zamanlayici" in d


def test_health_db_kopuksa_503(client, monkeypatch):
    import app.main as m
    from app.models import get_db

    class _Bozuk:
        def execute(self, *a, **k):
            raise RuntimeError("baglanti yok")

    def bozuk_db():
        yield _Bozuk()

    onceki = m.app.dependency_overrides[get_db]  # conftest'in bellek-içi DB override'ı
    m.app.dependency_overrides[get_db] = bozuk_db
    try:
        r = client.get("/health")
        assert r.status_code == 503 and r.json()["status"] == "db_erisilemiyor"
    finally:
        m.app.dependency_overrides[get_db] = onceki


def test_health_kilitli_sqlite_dosyasinda_hizli_503(tmp_path):
    """Dayanıklılık deneyi 2026-10-07: dosya kilitliyken /health 35 sn sonra 'ok' dönüyordu."""
    import sqlite3
    import time

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.main as m

    yol = tmp_path / "kilitli.db"
    c = sqlite3.connect(yol)
    c.execute("CREATE TABLE tesvikler (id INTEGER)")
    c.commit()
    c.close()
    kilit = sqlite3.connect(yol, timeout=0, isolation_level=None)
    kilit.execute("BEGIN EXCLUSIVE")
    try:
        eng = create_engine(f"sqlite:///{yol}", connect_args={"timeout": 0.3})
        db = sessionmaker(bind=eng)()
        t0 = time.time()
        r = m.health_check(db)
        assert r.status_code == 503 and time.time() - t0 < 3
        db.close()
    finally:
        kilit.execute("ROLLBACK")
        kilit.close()
