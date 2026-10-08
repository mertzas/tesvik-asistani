"""init_db: Alembic'in yönettiği veritabanında create_all çalışmaz (2026-10-08).

Önceki hâli dev sunucusu açılışında yeni tabloları göçten önce oluşturuyordu (basvuru_takipleri, tesvik_cagrilari);
"alembic upgrade" sonra 'table already exists' ile düşüyor, elle `alembic stamp` gerekiyordu."""
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app import models

KOK = Path(__file__).resolve().parent.parent


def _cfg():
    from alembic.config import Config
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    return cfg


def test_bos_veritabaninda_tablolar_olusur(tmp_path):
    motor = create_engine(f"sqlite:///{tmp_path / 'bos.db'}")
    assert models.init_db(motor) == "olusturuldu"
    assert "tesvik_cagrilari" in inspect(motor).get_table_names()


def test_guncel_gocte_create_all_calismaz(tmp_path, monkeypatch):
    from alembic import command
    db = tmp_path / "goc.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db}")
    command.upgrade(_cfg(), "head")
    motor = create_engine(f"sqlite:///{db}")
    with motor.begin() as b:
        b.exec_driver_sql("DROP TABLE tesvik_cagrilari")
    assert models.init_db(motor) == "guncel"
    assert "tesvik_cagrilari" not in inspect(motor).get_table_names(), "create_all göçün yerine geçmemeli"


def test_geride_kalan_gocte_uyari_ve_tablo_acilmaz(tmp_path, monkeypatch):
    from alembic import command
    db = tmp_path / "eski.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db}")
    command.upgrade(_cfg(), "k8f0b2c4d890")
    # alembic env.py süreç içinde logging.config.fileConfig çağırıp logger'ları ve kök yakalayıcıyı söker (canlıda göç
    # ayrı süreçte çalışır); bu yüzden caplog yerine modül logger'ı yamanır.
    uyarilar = []
    monkeypatch.setattr(models._gunluk, "critical", lambda msg, *a: uyarilar.append(msg % a))
    motor = create_engine(f"sqlite:///{db}")
    assert models.init_db(motor) == "goc_gerekli"
    assert "tesvik_cagrilari" not in inspect(motor).get_table_names()
    assert len(uyarilar) == 1 and "alembic upgrade head" in uyarilar[0] and "k8f0b2c4d890" in uyarilar[0]
