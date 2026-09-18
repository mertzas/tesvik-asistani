"""
Hiz siniri testleri.

Uretimde SADECE /api/sor'da aylik kota kontrolu vardi; /api/eslesme,
/api/butce-onerisi, /api/eticaret/destek-hesapla ve /api/ikas/* endpoint'
lerinin hicbirinde kisa pencereli koruma YOKTU - bunlar her cagrida tum
tesvik tablosunu tarayan ya da dis API'ye giden pahali islemler.
"""
import pytest

from app.rate_limit import sayac


@pytest.fixture(autouse=True)
def _sayaci_sifirla():
    sayac.temizle()
    yield
    sayac.temizle()


def _pro_yap(db):
    """Eslesme/butce endpoint'leri PRO plan ister; test kullanicisini yukselt."""
    from app.models import User, Organization, PlanType
    u = db.query(User).filter(User.email == "test@example.com").first()
    org = db.query(Organization).filter(Organization.id == u.org_id).first()
    org.plan = PlanType.PRO
    db.commit()


def test_pencere_icinde_limit_asilinca_429(client, test_user_token, db_session):
    _pro_yap(db_session)

    H = {"Authorization": f"Bearer {test_user_token}"}
    kodlar = [client.get("/api/eslesme", headers=H).status_code for _ in range(25)]

    assert 429 in kodlar, "limit asildiginda 429 donmeli"
    # 429'dan onceki istekler 429 olmamali (limit 20)
    assert kodlar[0] != 429


def test_429_yaniti_retry_after_basligi_tasir(client, test_user_token, db_session):
    _pro_yap(db_session)

    H = {"Authorization": f"Bearer {test_user_token}"}
    son = None
    for _ in range(25):
        r = client.get("/api/eslesme", headers=H)
        if r.status_code == 429:
            son = r
            break
    assert son is not None
    assert "retry-after" in {k.lower() for k in son.headers}


def test_sayac_penceresi_anahtar_bazinda_ayrik():
    """Farkli anahtarlar birbirinin limitini tuketmemeli."""
    for _ in range(3):
        assert sayac.izin_ver("org:A", 3, 60)[0] is True
    assert sayac.izin_ver("org:A", 3, 60)[0] is False   # A doldu
    assert sayac.izin_ver("org:B", 3, 60)[0] is True    # B etkilenmedi


def test_pencere_dolunca_bekleme_suresi_bildirilir():
    sayac.izin_ver("org:C", 1, 60)
    izin, bekle = sayac.izin_ver("org:C", 1, 60)
    assert izin is False
    assert 1 <= bekle <= 61
