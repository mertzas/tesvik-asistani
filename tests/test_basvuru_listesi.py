"""Başvuru kontrol listesi (app/basvuru_listesi.py, 2026-10-08)."""
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.models import BasvuruTakibi, Tesvik

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture
def tesvik(db_session):
    t = Tesvik(id=9, kurum="KOSGEB", baslik="Küresel Rekabetçilik", ozet="o", detay="d", aktif_mi=True,
               kaynak_url="https://www.kosgeb.gov.tr/x", uygunluk_kriterleri={"sektorler": ["genel"]},
               basvuru_sartlari=["KOBİ olmak"], gerekli_belgeler=["Proje Başvuru Formu", "Taahhütname"],
               basvuru_yeri="KOSGEB KBS", basvuru_suresi="Dönemsel çağrı")
    db_session.add(t)
    db_session.commit()
    return t


def _h(client, email):
    r = client.post("/api/auth/signup", json={"email": email, "password": "Parola123", "full_name": "A",
                                              "company_name": "B"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_maddeler_kayit_alanlarindan_uretilir(client, tesvik):
    r = client.get("/api/basvuru-listesi/9", headers=_h(client, "a@example.com"))
    assert r.status_code == 200
    d = r.json()
    assert [(m["tur"], m["metin"]) for m in d["maddeler"]] == [
        ("sart", "KOBİ olmak"), ("belge", "Proje Başvuru Formu"), ("belge", "Taahhütname"),
        ("basvuru", "Başvuruyu yap: KOSGEB KBS — Dönemsel çağrı")]
    assert d["tamamlanan"] == 0 and d["toplam"] == 4 and d["takipte"] is False and d["uyari"] is None


def test_isaretleme_kaydedilir_ve_listede_gorunur(client, tesvik):
    h = _h(client, "a@example.com")
    anahtarlar = [m["anahtar"] for m in client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"]]
    r = client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": anahtarlar[:2]})
    assert r.status_code == 200 and r.json()["tamamlanan"] == 2 and r.json()["takipte"] is True
    assert [m["isaretli"] for m in client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"]] == \
        [True, True, False, False]
    liste = client.get("/api/basvuru-listesi", headers=h).json()["listeler"]
    assert liste == [{"tesvik_id": 9, "baslik": "Küresel Rekabetçilik", "kurum": "KOSGEB", "aktif_mi": True,
                      "tamamlanan": 2, "toplam": 4, "guncelleme": liste[0]["guncelleme"]}]
    # işaret kaldırma = tam listeyi yeniden gönderme
    assert client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": []}).json()["tamamlanan"] == 0


def test_bilinmeyen_madde_reddedilir(client, tesvik):
    r = client.put("/api/basvuru-listesi/9", headers=_h(client, "a@example.com"), json={"isaretli": ["b:uydurma0000"]})
    assert r.status_code == 400 and "yenileyip" in r.json()["detail"]


def test_kuruluslar_birbirinin_isaretini_gormez(client, tesvik):
    a, b = _h(client, "a@example.com"), _h(client, "b@example.com")
    ilk = client.get("/api/basvuru-listesi/9", headers=a).json()["maddeler"][0]["anahtar"]
    client.put("/api/basvuru-listesi/9", headers=a, json={"isaretli": [ilk]})
    assert client.get("/api/basvuru-listesi/9", headers=b).json()["tamamlanan"] == 0
    assert client.get("/api/basvuru-listesi", headers=b).json()["listeler"] == []


def test_kayit_metni_degisince_eski_isaret_duser(client, db_session, tesvik):
    h = _h(client, "a@example.com")
    anahtarlar = [m["anahtar"] for m in client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"]]
    client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": anahtarlar})
    t = db_session.get(Tesvik, 9)
    t.gerekli_belgeler = ["Proje Başvuru Formu (2026 sürümü)", "Taahhütname"]
    db_session.commit()
    d = client.get("/api/basvuru-listesi/9", headers=h).json()
    assert {m["metin"]: m["isaretli"] for m in d["maddeler"]}["Proje Başvuru Formu (2026 sürümü)"] is False
    assert d["tamamlanan"] == 3


def test_takibi_birak_ve_404_ve_yetki(client, tesvik):
    h = _h(client, "a@example.com")
    k = client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"][0]["anahtar"]
    client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": [k]})
    assert client.delete("/api/basvuru-listesi/9", headers=h).status_code == 200
    assert client.get("/api/basvuru-listesi", headers=h).json()["listeler"] == []
    assert client.get("/api/basvuru-listesi/12345", headers=h).status_code == 404
    assert client.get("/api/basvuru-listesi/9").status_code in (401, 403)


def test_bilgisi_olmayan_kayitta_uyari(client, db_session):
    db_session.add(Tesvik(id=3, kurum="X", baslik="Bos", ozet="o", detay="d", kaynak_url="https://t/3",
                          uygunluk_kriterleri={}))
    db_session.commit()
    d = client.get("/api/basvuru-listesi/3", headers=_h(client, "a@example.com")).json()
    assert d["maddeler"] == [] and "resmi sayfasından" in d["uyari"]


def test_hesap_silmede_listeler_silinir(client, db_session, tesvik):
    h = _h(client, "a@example.com")
    k = client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"][0]["anahtar"]
    client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": [k]})
    assert db_session.query(BasvuruTakibi).count() == 1
    r = client.request("DELETE", "/api/organizations/me", headers=h, json={"password": "Parola123", "onay": True})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.query(BasvuruTakibi).count() == 0


def test_goc_upgrade_downgrade(tmp_path, monkeypatch):
    from app import models
    db_yolu = tmp_path / "b.db"
    monkeypatch.setattr(models.settings, "DATABASE_URL", f"sqlite:///{db_yolu}")
    cfg = Config(str(KOK / "alembic.ini"))
    cfg.set_main_option("script_location", str(KOK / "migrations"))
    motor = create_engine(f"sqlite:///{db_yolu}")
    command.upgrade(cfg, "head")
    assert "basvuru_takipleri" in inspect(motor).get_table_names()
    command.downgrade(cfg, "h5c7e9f1a567")
    assert "basvuru_takipleri" not in inspect(motor).get_table_names()
    command.upgrade(cfg, "head")


def test_self_test_bayragi():
    r = subprocess.run([sys.executable, "-m", "app.basvuru_listesi", "--self-test"], cwd=KOK,
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "6/6 geçti" in r.stdout
