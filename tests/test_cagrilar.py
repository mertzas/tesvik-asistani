"""Dönemsel başvuru çağrıları (app/cagrilar.py, tablo tesvik_cagrilari), 2026-10-08."""
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.models import Tesvik, TesvikCagrisi

KOK = Path(__file__).resolve().parent.parent
BUGUN = date.today()


def _gun(n):
    return BUGUN + timedelta(days=n)


@pytest.fixture
def kayitlar(db_session):
    db_session.add_all([
        Tesvik(id=1, kurum="KOSGEB", baslik="Küresel Rekabetçilik", ozet="o", detay="d", aktif_mi=True,
               kaynak_url="https://t/1", uygunluk_kriterleri={"sektorler": ["genel"]}, basvuru_yeri="KBS"),
        Tesvik(id=2, kurum="Kalkınma Ajansı", baslik="Mali Destek Programı", ozet="o", detay="d", aktif_mi=True,
               kaynak_url="https://t/2", uygunluk_kriterleri={"sektorler": ["genel"]}),
    ])
    db_session.flush()
    db_session.add_all([
        TesvikCagrisi(tesvik_id=1, ad="2026/1", acilis=_gun(-200), kapanis=_gun(-150), kaynak_url="https://k/1",
                      dogrulama_tarihi=BUGUN),
        TesvikCagrisi(tesvik_id=1, ad="2026/2", acilis=_gun(-5), kapanis=_gun(20), kaynak_url="https://k/2",
                      dogrulama_tarihi=BUGUN, notlar="Kapanış saati 23:59"),
        TesvikCagrisi(tesvik_id=2, ad="2026 MDP", acilis=_gun(30), kapanis=_gun(75), kaynak_url="https://k/3",
                      dogrulama_tarihi=BUGUN),
        TesvikCagrisi(tesvik_id=2, ad="2027 MDP", acilis=_gun(200), kapanis=_gun(260), kaynak_url="https://k/4",
                      dogrulama_tarihi=BUGUN),
    ])
    db_session.commit()


def test_yaklasan_cagrilar_pencere_ve_siralama(client, test_user_token, kayitlar):
    h = {"Authorization": f"Bearer {test_user_token}"}
    r = client.get("/api/cagrilar?gun=20", headers=h).json()["cagrilar"]  # +30. günde açılan dışarıda
    assert [(c["baslik"], c["ad"], c["durum"]) for c in r] == [("Küresel Rekabetçilik", "2026/2", "acik")]
    assert r[0]["kalan_gun"] == 20 and r[0]["notlar"] == "Kapanış saati 23:59"
    r = client.get("/api/cagrilar?gun=120", headers=h).json()["cagrilar"]
    assert [c["ad"] for c in r] == ["2026/2", "2026 MDP"] and r[1]["durum"] == "yaklasan" and r[1]["kalan_gun"] == 30


def test_sadece_eslesen_profilsiz_bos(client, test_user_token, kayitlar):
    h = {"Authorization": f"Bearer {test_user_token}"}
    assert client.get("/api/cagrilar?sadece_eslesen=true", headers=h).json()["cagrilar"] == []


def test_kimliksiz_erisim_yok(client, kayitlar):
    assert client.get("/api/cagrilar").status_code in (401, 403)


def test_kontrol_listesi_cagrilari_icerir(client, test_user_token, kayitlar):
    h = {"Authorization": f"Bearer {test_user_token}"}
    c = client.get("/api/basvuru-listesi/1", headers=h).json()["cagrilar"]
    assert [x["ad"] for x in c] == ["2026/2", "2026/1"] and c[1]["durum"] == "kapandi"
    assert client.get("/api/basvuru-listesi/2", headers=h).json()["cagrilar"][0]["durum"] == "yaklasan"


def test_program_silinince_cagrilari_silinir(db_session, kayitlar):
    db_session.delete(db_session.get(Tesvik, 2))
    db_session.commit()
    assert db_session.query(TesvikCagrisi).filter(TesvikCagrisi.tesvik_id == 2).count() == 0


def test_goc_cagri_tablosu(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    from app import models
    db_yolu = tmp_path / "t.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")
    command.upgrade(cfg, "head")
    sutunlar = {c["name"] for c in inspect(motor).get_columns("tesvik_cagrilari")}
    assert {"tesvik_id", "ad", "acilis", "kapanis", "kaynak_url", "dogrulama_tarihi", "notlar"} <= sutunlar
    command.downgrade(cfg, "k8f0b2c4d890")
    assert "tesvik_cagrilari" not in inspect(motor).get_table_names()
    command.upgrade(cfg, "head")


def test_self_test_bayragi():
    r = subprocess.run([sys.executable, "-m", "app.cagrilar", "--self-test"], cwd=KOK, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"self-test: (\d+)/(\d+) geçti", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= 6
