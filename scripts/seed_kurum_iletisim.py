"""
Kurum iletisim rehberini doldurur - her satir WebFetch ile resmi kurum
sayfasindan TEK TEK dogrulanmis, kaynak_url + dogrulama_tarihi ile
izlenebilir. Hicbir numara/adres uydurulmamistir (bkz. app/models.py
KurumIletisim docstring'i).

Calistirma: python scripts/seed_kurum_iletisim.py
Idempotent: zaten var olan kurum satirlarini gunceller, yeniden calistirmak
guvenlidir.
"""
from datetime import date

from app.models import SessionLocal, KurumIletisim, init_db

DOGRULAMA_TARIHI = date(2026, 7, 12)

KAYITLAR = [
    dict(
        kurum="KOSGEB",
        kurum_tam_ad="Küçük ve Orta Ölçekli İşletmeleri Geliştirme ve Destekleme İdaresi Başkanlığı",
        cagri_merkezi_no="444 1 567",
        genel_merkez_no="0 312 595 28 00",
        calisma_saatleri="Pazartesi-Cumartesi 08:30-17:30 (çağrı merkezi); Pazartesi-Cuma 08:30-17:30 (genel merkez)",
        adres="Hacı Bayram Mah. İstanbul Cad. No: 32 06050 Ulus / Altındağ / Ankara",
        web_sitesi="https://www.kosgeb.gov.tr",
        eposta="kosgeb.baskanlik@hs01.kep.tr",
        kaynak_url="https://www.kosgeb.gov.tr/site/tr/genel/iletisim",
        dogrulama_tarihi=DOGRULAMA_TARIHI,
    ),
    dict(
        kurum="TUBITAK",
        kurum_tam_ad="Türkiye Bilimsel ve Teknolojik Araştırma Kurumu",
        cagri_merkezi_no="444 66 90",
        genel_merkez_no="0 312 298 10 00",
        calisma_saatleri="Pazartesi-Cuma 08:30-17:30",
        adres="Remzi Oğuz Arık Mah. Tunus Cd. No:80 06540 Çankaya / Ankara",
        web_sitesi="https://www.tubitak.gov.tr",
        eposta=None,
        kaynak_url="https://tubitak.gov.tr/en/node/11658",
        dogrulama_tarihi=DOGRULAMA_TARIHI,
    ),
    dict(
        kurum="KGF",
        kurum_tam_ad="Kredi Garanti Fonu A.Ş.",
        cagri_merkezi_no="444 7 543",
        genel_merkez_no="0 312 204 00 00",
        calisma_saatleri=None,
        adres="Dumlupınar Bulv. No: 252 (Eskişehir Yolu 9. Km) TOBB İkiz Kuleleri C Blok Kat 5-6-7 06530 Çankaya / Ankara",
        web_sitesi="https://www.kgf.com.tr",
        eposta="info@kgf.com.tr",
        kaynak_url="https://www.kgf.com.tr/index.php/tr/bize-ulasin/kurumsal-iletisim",
        dogrulama_tarihi=DOGRULAMA_TARIHI,
    ),
    dict(
        kurum="Tarım Bakanlığı",
        kurum_tam_ad="Tarım ve Orman Bakanlığı - Tarım İletişim Merkezi",
        cagri_merkezi_no="180 (Alo 180)",
        genel_merkez_no=None,
        calisma_saatleri="7/24",
        adres="Üniversiteler Mah. Dumlupınar Bulvarı, No: 161, 06800, Çankaya / Ankara",
        web_sitesi="https://timer.tarimorman.gov.tr",
        eposta=None,
        kaynak_url="https://timer.tarimorman.gov.tr/Home/Hakkinda",
        dogrulama_tarihi=DOGRULAMA_TARIHI,
    ),
    dict(
        kurum="Ticaret Bakanlığı",
        kurum_tam_ad="T.C. Ticaret Bakanlığı",
        cagri_merkezi_no="444 8 482",
        genel_merkez_no="0 312 204 75 00",
        calisma_saatleri=None,
        adres="Söğütözü Mah. Nizami Gencevi Cad. No:63/1, 06530 Çankaya / Ankara",
        web_sitesi="https://ticaret.gov.tr",
        eposta=None,
        kaynak_url="https://ticaret.gov.tr/iletisim",
        dogrulama_tarihi=DOGRULAMA_TARIHI,
    ),
]


def main():
    init_db()
    db = SessionLocal()
    try:
        for kayit in KAYITLAR:
            mevcut = db.query(KurumIletisim).filter(KurumIletisim.kurum == kayit["kurum"]).first()
            if mevcut:
                for alan, deger in kayit.items():
                    setattr(mevcut, alan, deger)
                print(f"güncellendi: {kayit['kurum']}")
            else:
                db.add(KurumIletisim(**kayit))
                print(f"eklendi: {kayit['kurum']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
