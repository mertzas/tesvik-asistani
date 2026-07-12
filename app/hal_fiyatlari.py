"""
Profildeki serbest metin urun_turu alanini (orn. "muz") HKS Fiyat
Detaylari bultenindeki (bkz. app/scrapers/hal_urun_fiyat.py, HalFiyati
tablosu) urun_adi ile eslestirip en guncel hal fiyatini dondurur.

Cilek'e ozel _cilek_hal_fiyati_bul (bkz. app/budget.py) ayrı ve oncelikli
kalir - bu fonksiyon SADECE cilek disindaki hedef urunler (HEDEF_URUNLER,
su an MUZ) icindir.
"""
from sqlalchemy.orm import Session

from app.models import HalFiyati

_TR_CEVIRI = str.maketrans("çÇğĞıİöÖşŞüÜ", "cCgGiIoOsSuU")


def _sadelestir(metin: str) -> str:
    return metin.translate(_TR_CEVIRI).lower().strip()


def hal_fiyati_bul(db: Session, urun_turu: str | None) -> dict | None:
    urun_turu_l = _sadelestir(urun_turu or "")
    if not urun_turu_l:
        return None

    # Kelime siniri gozeterek eslesme (bkz. app/ihracat_fiyatlari.py'daki
    # ayni prensip - "hayvancilik" icinde "ayva" gecmesi gibi yanlis
    # pozitifleri onlemek icin).
    urun_turu_kelimeleri = set(urun_turu_l.split())

    son_tarih = db.query(HalFiyati.tarih).order_by(HalFiyati.tarih.desc()).first()
    if son_tarih is None:
        return None

    kayitlar = db.query(HalFiyati).filter(HalFiyati.tarih == son_tarih[0]).all()

    eslesenler = [k for k in kayitlar if _sadelestir(k.urun_adi) in urun_turu_kelimeleri]
    if not eslesenler:
        return None

    return {
        "kaynak_tipi": "hal_genel",
        "urun_adi": eslesenler[0].urun_adi.title(),
        "veri_tarihi": son_tarih[0].isoformat(),
        "kaynak": "T.C. Ticaret Bakanlığı Hal Kayıt Sistemi (HKS), günlük ulusal ortalama",
        "kalemler": [
            {
                "urun_cinsi": k.urun_cinsi,
                "urun_turu": k.urun_turu,
                "fiyat_kg": k.fiyat_kg,
                "miktar_kg": k.hacim_kg,
            }
            for k in eslesenler
        ],
    }
