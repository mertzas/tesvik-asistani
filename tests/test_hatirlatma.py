"""Çağrı son tarihi hatırlatması (app/hatirlatma.py, 2026-10-13): gerçek veritabanıyla."""
import uuid
from datetime import date, datetime, timedelta

from app import hatirlatma
from app.models import BasvuruTakibi, Organization, Tesvik, TesvikCagrisi, User

BUGUN = date(2026, 10, 13)


def test_yalniz_dogrulanmis_adrese_ve_esik_gununde(db_session):
    org = Organization(id=uuid.uuid4(), name="O", email="o@example.com")
    db_session.add(org)
    db_session.flush()
    db_session.add_all([
        User(email="dogru@example.com", full_name="D", org_id=org.id, is_active=True,
             email_dogrulama_zamani=datetime(2026, 10, 1)),
        User(email="dogrulanmamis@example.com", full_name="N", org_id=org.id, is_active=True),
        User(email="pasif@example.com", full_name="P", org_id=org.id, is_active=False,
             email_dogrulama_zamani=datetime(2026, 10, 1)),
        Tesvik(id=601, kurum="TUBITAK", baslik="1501 Sanayi Ar-Ge", ozet="o", detay="d", aktif_mi=True),
        Tesvik(id=602, kurum="Ajans", baslik="Ajans Mali Destek", ozet="o", detay="d", aktif_mi=True),
    ])
    db_session.flush()
    db_session.add_all([
        TesvikCagrisi(tesvik_id=601, ad="2026-2", acilis=date(2026, 9, 1), kapanis=BUGUN + timedelta(days=13),
                      on_kayit_son=BUGUN + timedelta(days=3), kaynak_url="https://tubitak.gov.tr/c",
                      dogrulama_tarihi=date(2026, 10, 8)),
        TesvikCagrisi(tesvik_id=602, ad="2026", acilis=date(2026, 9, 1), kapanis=BUGUN + timedelta(days=5),
                      kaynak_url="https://ajans.gov.tr/c", dogrulama_tarihi=date(2026, 10, 8)),
        BasvuruTakibi(org_id=org.id, tesvik_id=601, isaretli=[]),
        BasvuruTakibi(org_id=org.id, tesvik_id=602, isaretli=[]),
    ])
    db_session.commit()

    h = hatirlatma.hatirlatmalar(db_session, BUGUN)
    assert list(h) == ["dogru@example.com"], "doğrulanmamış ve pasif kullanıcıya gitmez"
    assert [(k["tesvik_id"], k["kalan_gun"]) for k in h["dogru@example.com"]["kalemler"]] == [(601, 3)], \
        "ön kayıt son gününe 3 gün (eşik); 5 gün eşik değil"
    giden = []
    ozet = hatirlatma.gonder(db_session, BUGUN, lambda *a: giden.append(a) or True)
    assert ozet == "1 hatırlatma gönderildi, 0 gönderilemedi" and giden[0][0] == "dogru@example.com"
    assert hatirlatma.hatirlatmalar(db_session, BUGUN + timedelta(days=1)) == {}, "eşik dışı gün"
