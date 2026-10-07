"""DATABASE_URL calisma dizininden bagimsiz cozulur (2026-10-08).

Gecmis: uygulama ana dizinden baslatilinca 'sqlite:///./tesvik.db' o dizinde bos bir
veritabani olusturuyordu. Artik goreli sqlite yolu proje kokune gore cozulur.
"""
import os
import subprocess
import sys
from pathlib import Path

from app.models import PROJE_KOKU, sqlite_url_mutlak


def test_goreli_yol_proje_kokune_cozulur():
    u = sqlite_url_mutlak("sqlite:///./data/tesvikler.db")
    assert u == "sqlite:///" + (PROJE_KOKU / "data" / "tesvikler.db").as_posix()


def test_bellek_ici_ve_mutlak_yol_degismez():
    assert sqlite_url_mutlak("sqlite://") == "sqlite://"
    assert sqlite_url_mutlak("sqlite:///:memory:") == "sqlite:///:memory:"
    assert sqlite_url_mutlak("sqlite:////tmp/x.db") == "sqlite:////tmp/x.db"
    assert sqlite_url_mutlak("sqlite:///C:/veri/x.db") == "sqlite:///C:/veri/x.db"


def test_sqlite_disi_adres_degismez():
    pg = "postgresql://u:p@db:5432/tesvik_db"
    assert sqlite_url_mutlak(pg) == pg


def test_baska_dizinden_import_ayni_veritabanini_gosterir(tmp_path):
    """Calisma dizini baska bir klasorken de motor proje icindeki DB'yi gosterir ve
    o klasorde yeni dosya olusmaz."""
    kod = "import app.models as m; print(m.engine.url.database)"
    env = dict(os.environ, PYTHONPATH=str(PROJE_KOKU), PYTHONIOENCODING="utf-8")
    env.pop("DATABASE_URL", None)
    # stdin=DEVNULL: tam pakette onceki testler miras alinan standart tanitiyicilari bozabiliyor
    # (Windows: WinError 6), bu yuzden alt surece acik bir stdin verilir.
    r = subprocess.run([sys.executable, "-c", kod], cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-400:]
    gosterilen = Path(r.stdout.strip().splitlines()[-1]).resolve()
    assert gosterilen.parent == (PROJE_KOKU / "data").resolve(), gosterilen
    assert list(tmp_path.iterdir()) == [], "calisma dizininde istenmeyen dosya olustu"
