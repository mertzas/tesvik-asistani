from app.models import FinancialProfile, IlTarimMudurlugu, Tesvik
from datetime import date


def _tesvik(db, **kw):
    t = Tesvik(kurum=kw.pop("kurum", "KOSGEB"), baslik="Test Destek", ozet="o", detay="d",
               kaynak_url="https://example.test/x" + str(kw.get("n", 1)), aktif_mi=kw.pop("aktif_mi", True), **{k: v for k, v in kw.items() if k != "n"})
    db.add(t); db.commit()
    return t


def test_yol_haritasi_sirali_ve_belgeli(client, test_user_token, db_session):
    t = _tesvik(db_session, basvuru_sartlari=["KOBİ olmalı"], gerekli_belgeler=["Vergi levhası"],
                basvuru_yeri="Online", basvuru_suresi="Sürekli", destek_verilme_suresi="2-3 ay")
    r = client.get(f"/api/tesvik/{t.id}/basvuru-yolu", headers={"Authorization": f"Bearer {test_user_token}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [a["no"] for a in d["adimlar"]] == list(range(1, len(d["adimlar"]) + 1))
    assert any("Vergi levhası" in a["liste"] for a in d["adimlar"])
    assert any("2-3 ay" in a["aciklama"] for a in d["adimlar"])
    assert d["uyarilar"]


def test_kapali_ve_teyitsiz_uyari(client, test_user_token, db_session):
    h = {"Authorization": f"Bearer {test_user_token}"}
    kapali = _tesvik(db_session, aktif_mi=False, n=2, durum_notu="2023'te kapandı")
    belirsiz = _tesvik(db_session, aktif_mi=None, n=3)
    a = client.get(f"/api/tesvik/{kapali.id}/basvuru-yolu", headers=h).json()["adimlar"][0]
    assert a["tur"] == "uyari" and "kapandı" in a["aciklama"]
    b = client.get(f"/api/tesvik/{belirsiz.id}/basvuru-yolu", headers=h).json()["adimlar"][0]
    assert b["tur"] == "uyari" and "teyit" in b["baslik"]


def test_tarim_il_muduru_iletisimi_dogrulanmis_ise(client, test_user_token, db_session):
    h = {"Authorization": f"Bearer {test_user_token}"}
    me = client.get("/api/organizations/me", headers=h).json()
    import uuid
    db_session.add(FinancialProfile(org_id=uuid.UUID(me["id"]), sektor="tarim", bolge="Konya", hedefler=[]))
    db_session.add(IlTarimMudurlugu(il_kodu=42, il_adi="Konya", telefon="0 332 000 00 00", adres="Adres",
                                    kaynak_url="https://example.test/konya", url_dogrulandi=True,
                                    dogrulama_tarihi=date(2026, 1, 1)))
    t = _tesvik(db_session, kurum="Tarım Bakanlığı", n=4)
    d = client.get(f"/api/tesvik/{t.id}/basvuru-yolu", headers=h).json()
    assert d["iletisim"]["telefon"] == "0 332 000 00 00"
    assert any("ÇKS" in a["baslik"] for a in d["adimlar"])


def test_olmayan_tesvik_404(client, test_user_token):
    r = client.get("/api/tesvik/99999/basvuru-yolu", headers={"Authorization": f"Bearer {test_user_token}"})
    assert r.status_code == 404
