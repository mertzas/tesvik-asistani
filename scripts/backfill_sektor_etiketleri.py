"""
"genel" etiketli kayitlarin gercek sektorlerle etiketlenmesi.

SORUN: 174 kaydin 92'si SADECE "genel" etiketi tasiyordu. app/matching.py
skorlamasinda "genel" etiketi 0.2 puan verir, dogrudan sektor eslesmesi
ise 0.6 - yani bu 92 kayit her profile ayni duz skorla geliyordu ve
"sektorune ozel eslestirme" iddiasi buyuk olcude islemiyordu.

YONTEM - kanit temelli, muhafazakar:
  - Sadece kaydin KENDI basligi/ozeti/detayi sektoru acikca isaret
    ediyorsa etiketlendi. Tahmin yapilmadi.
  - Detay alani bos ya da sadece menu metni olan kayitlar (bircok KOSGEB
    ve bazi KGF kayitlarinda scraping eksik kalmis) DOKUNULMADAN "genel"
    birakildi - icerigi bilinmeyen bir kaydi etiketlemek uydurma olur.
  - ["tarim"] gibi TEK etiket = program gercekten o sektore ozel; diger
    sektorlerdeki kullanici bu kaydi hic gormez.
  - ["tarim", "genel"] gibi CIFT etiket = agirlikli olarak o sektor ama
    digerlerine de acik; ilgili sektor 0.6, digerleri 0.2 alir.

YANLIS POZITIFTEN KACINILAN ORNEK: "TURWIB PROGRAMI DESTEK PAKETI"
basligindan sektorel sanilabilir, ama detayi okununca EBRD kaynakli
"kadin yonetici bulunan isletmelere" yonelik oldugu goruldu - bu bir
sektor degil isletme ozelligi, o yuzden "genel" birakildi.

Calistirma: python scripts/backfill_sektor_etiketleri.py
Idempotent.
"""
from app.models import SessionLocal, Tesvik

# id -> (sektorler, gerekce)
ETIKETLER = {
    # --- TARIM ---
    94:  (["tarim"], "Baslik ve dogrulanmis icerik: 'tarim, ormancilik veya balikcilik sektorunde faaliyet gosteren' isletmeler"),
    109: (["tarim"], "Baslik: 'TARIMSAL URETIME ENERJI FINANSMAN' - dogrudan tarimsal uretim"),
    98:  (["tarim"], "Baslik: 'CAY ALIMI' - tarimsal urun alimi"),
    84:  (["tarim", "genel"], "Soguk hava unitesi/frigorifik arac - agirlikli olarak gida-tarim soguk zinciri, ancak diger sektorlere de acik"),

    # --- IHRACAT ---
    92:  (["ihracat"], "Baslik: 'IHRACAT DESTEK PAKETI'"),
    159: (["ihracat"], "Baslik: 'Ihracat Destek Paketi'"),
    100: (["ihracat"], "Baslik: 'YESIL IHRACAT KREDISI (GREENDEKS)'"),
    120: (["ihracat"], "Baslik: 'Doviz Kazandirici Faaliyetleri' - ihracat/doviz geliri odakli"),
    111: (["ihracat"], "Eximbank (Turkiye Ihracat Kredi Bankasi) stok finansmani"),
    128: (["ihracat"], "Eximbank (Turkiye Ihracat Kredi Bankasi) kredisi"),

    # --- IMALAT ---
    134: (["imalat"], "Baslik: 'IMALATA DAYALI ITHAL IKAMESI'"),
    158: (["imalat"], "Baslik: 'Imalat Sanayii Destek Paketi'"),
    133: (["imalat"], "Savunma sanayii tedarikci programi - imalat tedarik zinciri"),
    101: (["imalat", "genel"], "Yesil donusum/enerji verimliligi - agirlikli olarak sanayi tesisleri, ancak diger sektorlere de acik"),

    # --- AR-GE / TEKNOLOJI ---
    102: (["arge", "genel"], "Teknoloji destek paketi - teknoloji yatirimi agirlikli"),
    103: (["arge"], "Teknoloji Gelistirme Bolgeleri (teknopark) kredisi - sadece TGB firmalari"),
    152: (["arge"], "TUBITAK transfer odemeleri - TUBITAK projesi yuruten firmalar"),
    4:   (["arge"], "KOSGEB Teknoloji Merkezi (TEKMER) destek programi"),
    2:   (["arge", "genel"], "Yapay Zeka Kredi Programi - teknoloji odakli ama genis kullanim"),

    # --- HIZMET ---
    83:  (["hizmet"], "Baslik: 'TURIZM DESTEK PAKETI'"),
    88:  (["hizmet"], "Baslik: 'EGITIM DESTEK PAKETI' - egitim kurumlari"),
    89:  (["hizmet"], "Halkbank Mesleki Egitim Kredisi - egitim kurumlari"),
    93:  (["hizmet"], "Vakifbank Hukuk Burosu Destek Paketi - hukuk burolari"),
    85:  (["hizmet"], "Basin Ilan Kurumu Destek Programi - basin/medya kuruluslari"),
    130: (["hizmet"], "Dogrulanmis icerik: 4708 sayili Yapi Denetimi Kanunu kapsaminda yapi denetim kuruluslari"),
}


def main():
    db = SessionLocal()
    try:
        degisen = 0
        for tid, (sektorler, gerekce) in ETIKETLER.items():
            t = db.query(Tesvik).filter(Tesvik.id == tid).first()
            if t is None:
                print(f"  UYARI: id={tid} bulunamadi, atlandi")
                continue
            kriterler = dict(t.uygunluk_kriterleri or {})
            eski = kriterler.get("sektorler", [])
            kriterler["sektorler"] = sektorler
            kriterler["sektor_gerekcesi"] = gerekce
            t.uygunluk_kriterleri = kriterler
            degisen += 1
            print(f"  [{tid}] {t.baslik[:44]:44} {eski} -> {sektorler}")
        db.commit()
        print(f"\n{degisen} kayit etiketlendi.")

        kalan = [t for t in db.query(Tesvik).all()
                 if [s.lower() for s in (t.uygunluk_kriterleri or {}).get("sektorler", [])] == ["genel"]]
        print(f"Hala sadece 'genel' olan: {len(kalan)} "
              f"(icerigi bilinmeyen/gercekten sektor bagimsiz kayitlar - bilerek dokunulmadi)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
