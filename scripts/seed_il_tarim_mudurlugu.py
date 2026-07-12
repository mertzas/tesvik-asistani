"""
81 il icin Tarim ve Orman Il Mudurlugu iletisim rehberini doldurur.

IKI FARKLI GUVEN SEVIYESI (bkz. app/models.py IlTarimMudurlugu docstring):
  - DOGRULANMIS_ILLER: WebFetch ile /Iletisim sayfasi gercekten acilip
    telefon+adres teyit edildi (13 il, buyuk tarim ekonomileri).
  - Geri kalan 68 il: sadece plaka kodu + il adi (TC'nin standart, kamuya
    acik plaka listesi - ayrica dogrulama gerektirmez) + PATTERN'e gore
    uretilmis kaynak_url. Telefon/adres BILEREK NULL - o ilin sayfasi
    henuz tek tek acilip okunmadi.

Calistirma: python scripts/seed_il_tarim_mudurlugu.py
Idempotent: mevcut il satirlarini gunceller.
"""
from datetime import date

from app.models import SessionLocal, IlTarimMudurlugu, init_db

DOGRULAMA_TARIHI = date(2026, 7, 12)


def _slug(il_adi: str) -> str:
    """Turkce il adini tarimorman.gov.tr alt-alan-adi desenine cevirir.
    Not: bu deseni izlemeyen istisnai iller olabilir - sadece
    DOGRULANMIS_ILLER listesindekiler icin bu URL'in dogrulugu kesindir."""
    d = {
        "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ç": "c", "Ç": "c",
        "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o",
    }
    s = "".join(d.get(ch, ch) for ch in il_adi)
    return s.lower().replace(" ", "")


# (plaka_kodu, il_adi) - TC'nin standart 81 il plaka kodu listesi.
ILLER = [
    (1, "Adana"), (2, "Adıyaman"), (3, "Afyonkarahisar"), (4, "Ağrı"), (5, "Amasya"),
    (6, "Ankara"), (7, "Antalya"), (8, "Artvin"), (9, "Aydın"), (10, "Balıkesir"),
    (11, "Bilecik"), (12, "Bingöl"), (13, "Bitlis"), (14, "Bolu"), (15, "Burdur"),
    (16, "Bursa"), (17, "Çanakkale"), (18, "Çankırı"), (19, "Çorum"), (20, "Denizli"),
    (21, "Diyarbakır"), (22, "Edirne"), (23, "Elazığ"), (24, "Erzincan"), (25, "Erzurum"),
    (26, "Eskişehir"), (27, "Gaziantep"), (28, "Giresun"), (29, "Gümüşhane"), (30, "Hakkari"),
    (31, "Hatay"), (32, "Isparta"), (33, "Mersin"), (34, "İstanbul"), (35, "İzmir"),
    (36, "Kars"), (37, "Kastamonu"), (38, "Kayseri"), (39, "Kırklareli"), (40, "Kırşehir"),
    (41, "Kocaeli"), (42, "Konya"), (43, "Kütahya"), (44, "Malatya"), (45, "Manisa"),
    (46, "Kahramanmaraş"), (47, "Mardin"), (48, "Muğla"), (49, "Muş"), (50, "Nevşehir"),
    (51, "Niğde"), (52, "Ordu"), (53, "Rize"), (54, "Sakarya"), (55, "Samsun"),
    (56, "Siirt"), (57, "Sinop"), (58, "Sivas"), (59, "Tekirdağ"), (60, "Tokat"),
    (61, "Trabzon"), (62, "Tunceli"), (63, "Şanlıurfa"), (64, "Uşak"), (65, "Van"),
    (66, "Yozgat"), (67, "Zonguldak"), (68, "Aksaray"), (69, "Bayburt"), (70, "Karaman"),
    (71, "Kırıkkale"), (72, "Batman"), (73, "Şırnak"), (74, "Bartın"), (75, "Ardahan"),
    (76, "Iğdır"), (77, "Yalova"), (78, "Karabük"), (79, "Kilis"), (80, "Osmaniye"),
    (81, "Düzce"),
]

# WebFetch ile TEK TEK dogrulanan iller (2026-07-12) - kaynak: <il-slug>.tarimorman.gov.tr/Iletisim
DOGRULANMIS_ILLER = {
    "İstanbul": dict(telefon="0 216 468 21 00", adres="Bağdat Caddesi No: 307-309 Erenköy-Kadıköy/İSTANBUL"),
    "Ankara": dict(telefon="0312 344 59 50", adres="Gayret Mahallesi Şehit Cem Ersever Cad. No: 14 Yenimahalle/ANKARA"),
    "İzmir": dict(telefon="0232 435 10 02", adres="Kazım Dirik Mahallesi Sanayi Caddesi No:34 35100 Bornova/İZMİR"),
    "Bursa": dict(telefon="0224 246 42 30", adres="Adalet Mahallesi 1.Hürriyet Caddesi Osmangazi/BURSA"),
    "Antalya": dict(telefon="0242 345 28 20", adres="Vatan Bulvarı, Sedir Mahallesi, Tarım Kampüsü, Muratpaşa/ANTALYA"),
    "Adana": dict(telefon="0322 344 17 17", adres="Köprülü Mahallesi Mithat Özsan Bulvarı No:4, 01230 Yüreğir/ADANA"),
    "Konya": dict(telefon="0332 322 34 60", adres="Konevi Mahallesi Larende Caddesi No:14 Meram/KONYA"),
    "Gaziantep": dict(telefon="0342 321 10 66", adres="Mücahitler Mahallesi Fevzi Çakmak Blv. No:102 Şehitkamil/GAZİANTEP"),
    "Şanlıurfa": dict(telefon="0414 313 27 11", adres="İmambakır Mahallesi 702. Sokak No: 6 Haliliye/ŞANLIURFA"),
    "Kayseri": dict(telefon="0352 338 21 44", adres="Sümer Yeni Mahalle 7. Cadde No:59, 38090 Kocasinan/KAYSERİ"),
    "Mersin": dict(telefon="0324 326 40 06", adres="Gazi Mah. 1303. Sokak No:13/A 33140 Yenişehir/MERSİN"),
    "Samsun": dict(telefon="0362 231 37 00", adres="Kılıçdede Mah. Abdülhakhamit Cad. No:5 55060 İlkadım/SAMSUN"),
    "Denizli": dict(telefon="0258 212 54 80", adres="İncilipınar Mah. İncilipınar Cad. No:2, 20150 Pamukkale/DENİZLİ"),
}


def main():
    init_db()
    db = SessionLocal()
    try:
        for il_kodu, il_adi in ILLER:
            slug = _slug(il_adi)
            kaynak_url = f"https://{slug}.tarimorman.gov.tr/Iletisim"
            dogrulanmis = DOGRULANMIS_ILLER.get(il_adi)

            mevcut = db.query(IlTarimMudurlugu).filter(IlTarimMudurlugu.il_kodu == il_kodu).first()
            veri = dict(
                il_adi=il_adi,
                telefon=dogrulanmis["telefon"] if dogrulanmis else None,
                adres=dogrulanmis["adres"] if dogrulanmis else None,
                eposta=f"{slug}@tarimorman.gov.tr" if dogrulanmis else None,
                kaynak_url=kaynak_url,
                url_dogrulandi=bool(dogrulanmis),
                dogrulama_tarihi=DOGRULAMA_TARIHI if dogrulanmis else None,
            )
            if mevcut:
                for alan, deger in veri.items():
                    setattr(mevcut, alan, deger)
            else:
                db.add(IlTarimMudurlugu(il_kodu=il_kodu, **veri))
        db.commit()
        toplam = db.query(IlTarimMudurlugu).count()
        dogrulanan = db.query(IlTarimMudurlugu).filter(IlTarimMudurlugu.url_dogrulandi == True).count()  # noqa: E712
        print(f"{toplam} il eklendi/güncellendi, {dogrulanan} tanesi telefon/adres ile doğrulanmış.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
