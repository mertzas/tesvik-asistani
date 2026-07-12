"""
Profildeki serbest metin urun_turu alanini (orn. "domates", "elma") HKS
Ihracat Fiyat Bulteni'ndeki (bkz. app/scrapers/hal_ihracat_fiyat.py)
urun_adi ile eslestirip en guncel ihracat referans fiyatini dondurur.
"""
from sqlalchemy.orm import Session

from app.models import IhracatFiyati

# Turkce karakterleri sadelestirerek esnek eslesme yapmak icin.
_TR_CEVIRI = str.maketrans("çÇğĞıİöÖşŞüÜ", "cCgGiIoOsSuU")


def _sadelestir(metin: str) -> str:
    return metin.translate(_TR_CEVIRI).lower().strip()


def ihracat_fiyati_bul(db: Session, urun_turu: str | None) -> dict | None:
    urun_turu_l = _sadelestir(urun_turu or "")
    if not urun_turu_l:
        return None

    # Kelime siniri gozetmeyen ham "substring in substring" kontrolu yanlis
    # pozitif uretiyordu (orn. "hayvancilik" icinde "ayva" gectigi icin
    # "AYVA" urunuyle eslesiyordu). Bunun yerine urun_turu_l'yi kelimelere
    # bolup HKS urun adiyla TAM kelime eslesmesi ariyoruz.
    urun_turu_kelimeleri = set(urun_turu_l.split())

    son_tarih = db.query(IhracatFiyati.tarih).order_by(IhracatFiyati.tarih.desc()).first()
    if son_tarih is None:
        return None

    kayitlar = db.query(IhracatFiyati).filter(IhracatFiyati.tarih == son_tarih[0]).all()

    eslesenler = [
        k for k in kayitlar
        if _sadelestir(k.urun_adi) in urun_turu_kelimeleri
    ]
    if not eslesenler:
        return None

    return {
        "urun_adi": eslesenler[0].urun_adi.title(),
        "veri_tarihi": son_tarih[0].isoformat(),
        "kaynak": "T.C. Ticaret Bakanlığı Hal Kayıt Sistemi (HKS) İhracat Fiyat Bülteni",
        "kalemler": [
            {
                "urun_cinsi": k.urun_cinsi,
                "urun_turu": k.urun_turu,
                "fiyat_kg": k.fiyat_kg,
                "miktar_kg": k.miktar_kg,
            }
            for k in eslesenler
        ],
    }
