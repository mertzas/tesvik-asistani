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
        ("adim", "Başvuruyu yap: KOSGEB KBS — Dönemsel çağrı")]
    # ilerleme yalnız belge + adım; şartlar ayrı (Evet/Hayır/Emin değilim)
    assert d["tamamlanan"] == 0 and d["toplam"] == 3 and d["takipte"] is False and d["uyari"] is None
    assert d["uygunluk"] == {"toplam": 1, "evet": 0, "hayir": 0, "bilmiyorum": 0}
    assert d["taslak_kapsami"]["gerekli"] is True and "proje/iş planı" in d["taslak_kapsami"]["ne_icin"]


def test_isaretleme_kaydedilir_ve_listede_gorunur(client, tesvik):
    h = _h(client, "a@example.com")
    m = client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"]
    belgeler = [x["anahtar"] for x in m if x["tur"] == "belge"]
    r = client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": belgeler})
    assert r.status_code == 200 and r.json()["tamamlanan"] == 2 and r.json()["takipte"] is True
    assert [x["isaretli"] for x in client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"]] == \
        [False, True, True, False]
    liste = client.get("/api/basvuru-listesi", headers=h).json()["listeler"]
    assert liste == [{"tesvik_id": 9, "baslik": "Küresel Rekabetçilik", "kurum": "KOSGEB", "aktif_mi": True,
                      "tamamlanan": 2, "toplam": 3, "guncelleme": liste[0]["guncelleme"]}]
    # işaret kaldırma = tam listeyi yeniden gönderme
    assert client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": []}).json()["tamamlanan"] == 0


def test_bilinmeyen_madde_reddedilir(client, tesvik):
    r = client.put("/api/basvuru-listesi/9", headers=_h(client, "a@example.com"), json={"isaretli": ["b:uydurma0000"]})
    assert r.status_code == 400 and "yenileyip" in r.json()["detail"]


def test_kuruluslar_birbirinin_isaretini_gormez(client, tesvik):
    a, b = _h(client, "a@example.com"), _h(client, "b@example.com")
    ilk = client.get("/api/basvuru-listesi/9", headers=a).json()["maddeler"][1]["anahtar"]
    assert client.put("/api/basvuru-listesi/9", headers=a, json={"isaretli": [ilk]}).status_code == 200
    assert client.get("/api/basvuru-listesi/9", headers=b).json()["tamamlanan"] == 0
    assert client.get("/api/basvuru-listesi", headers=b).json()["listeler"] == []


def test_kayit_metni_degisince_eski_isaret_duser(client, db_session, tesvik):
    h = _h(client, "a@example.com")
    anahtarlar = [m["anahtar"] for m in client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"]
                  if m["tur"] in ("belge", "adim")]
    assert client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": anahtarlar}).status_code == 200
    t = db_session.get(Tesvik, 9)
    t.gerekli_belgeler = ["Proje Başvuru Formu (2026 sürümü)", "Taahhütname"]
    db_session.commit()
    d = client.get("/api/basvuru-listesi/9", headers=h).json()
    assert {m["metin"]: m["isaretli"] for m in d["maddeler"]}["Proje Başvuru Formu (2026 sürümü)"] is False
    assert d["tamamlanan"] == 2


def test_takibi_birak_ve_404_ve_yetki(client, tesvik):
    h = _h(client, "a@example.com")
    k = client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"][1]["anahtar"]
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
    client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": [], "uygunluk": {k: "evet"}})
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
    assert r.returncode == 0 and "9/9 geçti" in r.stdout


# ------------------------------------------------- denetlenmiş kontrol listesi (2026-10-10)
def test_sart_cevaplari_ayri_saklanir_kutularla_karismaz(client, tesvik):
    h = _h(client, "a@example.com")
    m = client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"]
    sart, belge = m[0]["anahtar"], m[1]["anahtar"]
    # şart onay kutusu değil: isaretli listesinde reddedilir
    assert client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": [sart]}).status_code == 400
    # belge şart cevabı alamaz
    assert client.put("/api/basvuru-listesi/9", headers=h, json={"uygunluk": {belge: "evet"}}).status_code == 400
    assert client.put("/api/basvuru-listesi/9", headers=h, json={"uygunluk": {sart: "belki"}}).status_code == 422
    d = client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": [belge], "uygunluk": {sart: "hayir"}}).json()
    assert d["maddeler"][0]["cevap"] == "hayir" and d["uygunluk"]["hayir"] == 1 and d["tamamlanan"] == 1
    # uygunluk verilmeyen kayıtta cevap korunur
    d = client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": []}).json()
    assert d["maddeler"][0]["cevap"] == "hayir" and d["tamamlanan"] == 0


def test_eski_sart_isareti_evet_sayilir(client, db_session, tesvik):
    h = _h(client, "a@example.com")
    sart = client.get("/api/basvuru-listesi/9", headers=h).json()["maddeler"][0]["anahtar"]
    client.put("/api/basvuru-listesi/9", headers=h, json={"isaretli": []})
    kayit = db_session.query(BasvuruTakibi).one()
    kayit.isaretli = [sart]  # eski sürümün kaydı
    db_session.commit()
    d = client.get("/api/basvuru-listesi/9", headers=h).json()
    assert d["maddeler"][0]["cevap"] == "evet" and d["tamamlanan"] == 0


def test_kontrol_listesi_alani_esas_alintiyla_doner(client, db_session, tesvik):
    t = db_session.get(Tesvik, 9)
    t.kontrol_listesi = [
        {"tur": "sart", "metin": "Küçük veya orta işletme olmak", "alinti": "küçük ve orta", "kaynak_url": "https://k",
         "kaynak_tarihi": "2026-10-09", "dogrulandi": True},
        {"tur": "belge", "metin": "Başvuru Kontrol Formu", "alinti": None, "kaynak_url": "https://k",
         "kaynak_tarihi": "2026-10-09", "dogrulandi": False},
        {"tur": "adim", "metin": "Başvuruyu yap: KOSGEB KBS", "alinti": "KBS", "kaynak_url": "https://k",
         "kaynak_tarihi": "2026-10-09", "dogrulandi": True},
        {"tur": "bilgi", "metin": "Destek oranı %60", "alinti": "%60", "kaynak_url": "https://k",
         "kaynak_tarihi": "2026-10-09", "dogrulandi": True}]
    t.basvuru_bicimi = "kefalet"
    db_session.commit()
    d = client.get("/api/basvuru-listesi/9", headers=_h(client, "a@example.com")).json()
    assert [(m["tur"], m["metin"]) for m in d["maddeler"]] == [
        ("sart", "Küçük veya orta işletme olmak"), ("belge", "Başvuru Kontrol Formu"),
        ("adim", "Başvuruyu yap: KOSGEB KBS"), ("bilgi", "Destek oranı %60")]
    assert d["maddeler"][0]["alinti"] == "küçük ve orta" and d["maddeler"][1]["dogrulandi"] is False
    assert d["toplam"] == 2  # bilgi işaretlenmez
    # eski alanlardaki "KOBİ olmak" artık gösterilmez; dönem adım metnine yapıştırılmaz
    assert all("KOBİ olmak" != m["metin"] and "Dönemsel" not in m["metin"] for m in d["maddeler"])
    k = d["taslak_kapsami"]
    assert k["gerekli"] is False and "kefalet" in k["aciklama"] and k["nereye"] == "KOSGEB KBS"
