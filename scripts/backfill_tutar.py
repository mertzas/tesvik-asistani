"""
Mevcut tesvikler tablosundaki kayitlarin tesvil_tutari alanini doldurur.

Bu alan bos oldugu icin /api/eslesme endpoint'indeki "tahmini toplam destek"
hesabi hep 0 donuyordu. Buradaki tutarlar, ilgili kurumun program
turune gore GENEL BILGI DUZEYINDE curated bir tahmindir (resmi, satir
satir dogrulanmis kesin rakamlar degildir) - amac "0 TL" yerine kullaniciya
kaba bir buyukluk fikri vermek. Gercek başvuru asamasinda kurumun guncel
tebligine bakilmalidir; bu, matching.py ve dashboard'da da "tahmini" olarak
etiketleniyor.

Format: "₺<min> - ₺<max>" (matching._tutari_parse bu formati ayristirir).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, init_db

# kurum adindaki bozuk/duzgun Turkce karakter varyasyonlarina karsi
# esnek eslesme icin anahtar kelime bazli kontrol kullaniliyor.
KURUM_TUTAR_ARALIKLARI = [
    (["kgf"], "₺500.000 - ₺5.000.000", "kredi teminatı büyüklüğü"),
    (["tubitak", "tübİtak", "tübitak"], "₺50.000 - ₺2.000.000", None),
    (["kosgeb"], "₺50.000 - ₺500.000", None),
    (["ticaret bakan"], "₺100.000 - ₺1.000.000", None),
    (["İşkur", "iskur"], "₺50.000 - ₺300.000", None),
    (["hazine"], "₺500.000 - ₺10.000.000", "yatırım teşvik belgesi kapsamı"),
    (["tarım bakan", "tarim bakan"], "₺20.000 - ₺300.000", None),
    (["invest in turkey"], "₺1.000.000 - ₺10.000.000", None),
    (["çalışma bakan", "calisma bakan"], "₺50.000 - ₺200.000", None),
    (["enerji bakan"], "₺100.000 - ₺500.000", None),
    (["tkdk"], "₺100.000 - ₺500.000", None),
    (["kalkınma ajans", "kalkinma ajans"], "₺50.000 - ₺750.000", None),
    (["kültür bakan", "kultur bakan"], "₺20.000 - ₺150.000", None),
    (["spor bakan"], "₺20.000 - ₺150.000", None),
    (["çevre bakan", "cevre bakan"], "₺50.000 - ₺300.000", None),
]

# TUBITAK icindeki kucuk olcekli (etkinlik/bilim fuari/egitim) programlar
# genel Ar-Ge projelerinden cok daha kucuk tutarlidir; baslik/kod on ekine
# gore ozel olarak kucultuyoruz.
TUBITAK_KUCUK_PROGRAM_ANAHTARLARI = ["4006", "2224", "2237", "bilim fuar", "eğitim etkinlik"]

VARSAYILAN_TUTAR = "₺50.000 - ₺500.000"


def _kurum_tutar_araligi(kurum: str, baslik: str) -> str:
    kurum_l = (kurum or "").lower()
    baslik_l = (baslik or "").lower()

    for anahtarlar, tutar, _not in KURUM_TUTAR_ARALIKLARI:
        if any(a in kurum_l for a in anahtarlar):
            if "tubitak" in kurum_l or "tübİtak" in kurum_l or "tübitak" in kurum_l:
                if any(a in baslik_l for a in TUBITAK_KUCUK_PROGRAM_ANAHTARLARI):
                    return "₺10.000 - ₺50.000"
            return tutar

    return VARSAYILAN_TUTAR


def run():
    init_db()
    db = SessionLocal()
    guncellenen = 0
    try:
        for t in db.query(Tesvik).all():
            if t.tesvil_tutari and t.tesvil_tutari.strip():
                continue
            t.tesvil_tutari = _kurum_tutar_araligi(t.kurum, t.baslik)
            guncellenen += 1
        db.commit()
    finally:
        db.close()

    print(f"{guncellenen} kayit icin tesvil_tutari dolduruldu.")


if __name__ == "__main__":
    run()
