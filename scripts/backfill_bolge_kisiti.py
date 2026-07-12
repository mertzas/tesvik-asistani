"""
Bazi tesvikler (orn. 6 Subat depremleri destek paketleri) sadece belirli
illerde faaliyet gosteren/yatirim yapacak isletmeler icin gecerlidir.
Bunlar simdiye kadar "genel" (bolge bagimsiz) etiketlendigi icin,
eslestirme motoru bu programlari HER kullaniciya (yanlislikla) gosteriyordu.

Bu script, bilinen bolge-kisitli tesvikleri tespit edip
uygunluk_kriterleri alanina "bolge_kisitli" (il listesi) ekler; bkz.
app/matching.py'daki bolge kontrolu.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, init_db

# Baslikta gecen anahtar kelime -> bolge kisitli il listesi.
# Yeni bolgesel-kisitli tesvik eklenirse buraya eklenmelidir.
BOLGE_KISITLI_PROGRAMLAR = {
    "6 ŞUBAT DEPREMLERİ": [
        "kahramanmaraş", "gaziantep", "şanlıurfa", "diyarbakır", "adana",
        "adıyaman", "malatya", "osmaniye", "hatay", "elazığ", "kilis", "sivas",
    ],
    "İSTİHDAM TAAHHÜTLÜ KOBİ FİNANSMAN DESTEK PROGRAMI-II": [
        "adana", "adıyaman", "ankara", "batman", "bursa", "diyarbakır",
        "gaziantep", "hatay", "istanbul", "izmir", "kahramanmaraş", "kayseri",
        "kilis", "kocaeli", "konya", "malatya", "mardin", "mersin",
        "osmaniye", "şanlıurfa",
    ],
}


def run():
    init_db()
    db = SessionLocal()
    guncellenen = 0
    try:
        for t in db.query(Tesvik).all():
            baslik_upper = (t.baslik or "").upper()
            for anahtar, iller in BOLGE_KISITLI_PROGRAMLAR.items():
                if anahtar in baslik_upper:
                    kriterler = dict(t.uygunluk_kriterleri or {})
                    if kriterler.get("bolge_kisitli") != iller:
                        kriterler["bolge_kisitli"] = iller
                        t.uygunluk_kriterleri = kriterler
                        guncellenen += 1
                    break
        db.commit()
    finally:
        db.close()

    print(f"{guncellenen} kayida bolge_kisitli eklendi.")


if __name__ == "__main__":
    run()
