"""
Kritik hata duzeltmesi: app/matching.py::esles() SADECE uygunluk_kriterleri
alaninda "sektorler" listesi olan kayitlari degerlendirir (bkz. matching.py
satir 98: "if not tesvik_sektorler: continue"). Bu oturumda eklenen 6 kayit
(2 Ticaret Bakanligi e-ihracat destegi + 4 Hazine/Ticaret Bakanligi yatirim
tesvik programi) bu alani HIC DOLDURMADAN eklenmisti - yani hicbir kullanici
profiline HICBIR ZAMAN eslesmiyorlardi. "Dogru tesvikleri bulmuyor" sikayeti
buydu.

Calistirma: python scripts/fix_uygunluk_kriterleri_eksik.py
"""
from app.models import SessionLocal, Tesvik

# baslik -> uygunluk_kriterleri
DUZELTMELER = {
    "E-İhracat Destekleri (5986 Sayılı Karar)": {
        "sektorler": ["e-ticaret", "ihracat"],
    },
    "Pazara Girişte Dijital Faaliyetlerin Desteklenmesi": {
        "sektorler": ["e-ticaret", "ihracat"],
    },
    # Yatirim Tesvik Sistemi programlari - sektor bagimsiz, yatirim
    # olcegine/bolgeye gore degisir; "genel" etiketi mevcut kalipla ayni
    # (bkz. KOSGEB Girisimci Destek Programi: {"sektorler": ["genel"]}).
    "Genel Teşvik Uygulamaları": {"sektorler": ["genel"]},
    "Bölgesel Teşvik Uygulamaları": {"sektorler": ["genel"]},
    "Büyük Ölçekli Yatırımların Teşviki": {"sektorler": ["genel"]},
    "Stratejik Yatırımların Teşviki": {"sektorler": ["genel"]},
}


def main():
    db = SessionLocal()
    try:
        for baslik, kriter in DUZELTMELER.items():
            t = db.query(Tesvik).filter(Tesvik.baslik == baslik).first()
            if t is None:
                print(f"UYARI: '{baslik}' bulunamadı, atlandı.")
                continue
            t.uygunluk_kriterleri = kriter
            print(f"düzeltildi: [{t.kurum}] {baslik} -> {kriter}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
