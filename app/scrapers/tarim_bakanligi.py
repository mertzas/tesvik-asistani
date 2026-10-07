"""
T.C. Tarım ve Orman Bakanlığı'nın resmi destek programları. Şu an statik veri
(curated list) olarak tutulup ve periyodik manuel güncellemeler yapılıyor.

Ileride Bakanlık tarafından yayınlanan veri API'sine (TDVP, eğer varsa) ya da
Resmî Gazete'de yayınlanan paket tutarlarına dayalı bir scraper eklenebilir.
Şimdilik, Bakanlık'ın https://www.tarim.gov.tr adresindeki halkla ilişkiler
yayınlarından ve KDVK kararlarından derlenmiş ana programa ve tutar referans
değerleri kullanıyoruz.
"""
from datetime import datetime
from app.models import SessionLocal, Tesvik, init_db


# Tarım Bakanlığı'nın başlıca destek programları (statik curated veri).
# Tutar/koşul referans değerleri, son güncelleme tarihi de dahil.
TARIM_BAKANLIGI_DESTEKLERI = [
    {
        "baslik": "Hayvancılık Destekleri",
        "ozet": "Büyükbaş, küçükbaş, tavuk, arıcılık vb. hayvancılık faaliyetlerine yönelik kamu desteği.",
        "detay": (
            "Tarım ve Orman Bakanlığı tarafından sağlanan hayvancılık destekleri, "
            "büyükbaş (sığır, manda), küçükbaş (koyun, keçi), kanatlı ve arıcılık "
            "alanında yatırım ve işletme desteğini içerir. Destekler, hayvan başına "
            "veya üretim miktarına dayalı olarak hesaplanır ve çiftçilerin verim artışı "
            "ile modern hayvancılık tekniklerine geçişini destekler."
        ),
        "kurum": "Tarım Bakanlığı",
        "hedef_kitle": "Hayvancılık işletmeleri, çiftçiler",
        "uygunluk_kriterleri": {
            "sektorler": ["tarim"],
            "alt_kategori": "hayvancilik",
            "genislik": "dar"
        },
        "tesvil_tutari": "Hayvancılık türüne ve ölçeğine göre değişken",
        "tutari_min": 50000,
        "tutari_max": 500000,
        "tutari_hesaplama_kriteri": "genel",
        "tutari_hesaplama_formulu": "İşletme başına ₺50K-500K ortalama (hayvan türü/ırkına göre değişir)",
        "basvuru_sartlari": [
            "Hayvancılık işletmesi sahibi olmalı",
            "Asgari 2 hayvan bulunmalı (irk ve tür bazında)",
            "Hayvan Sağlık Sertifikası gerekli",
            "İlk kuruluş 5 yıl içinde geçerli"
        ],
        "gerekli_belgeler": [
            "Hayvan Sağlık Sertifikası",
            "Üretim Belgesi (Tarım Bakanlığı)",
            "Arazi/İşletme Belgesi",
            "Yıllık Muhasebe Kaydı"
        ],
        "basvuru_yeri": "İL/İlçe Tarım ve Orman Müdürlüğü",
        "basvuru_suresi": "Dönemsel (1. ve 2. Dönem) — HAYGEM'in yıllık yayınladığı Çalışma Takvimi'ne göre değişir, kesin tarihler için resmi kaynağı kontrol edin",
        "destek_verilme_suresi": "60-90 gün",
        "baslama_tarihi": datetime(2024, 1, 1),
        "bitis_tarihi": None,
        "kaynak_url": "https://www.tarimorman.gov.tr/HAYGEM"
    },
    {
        "baslik": "Organik Tarım Destekleri",
        "ozet": "Organik tarım uygulamalarına geçiş ve organik tarım faaliyetlerine yönelik destek.",
        "detay": (
            "Tarım Bakanlığı tarafından sağlanan organik tarım destekleri, "
            "konvansiyonel tarımdan organik tarıma geçişte ilk 3 yıl boyunca ve "
            "organik tarım yapan işletmelerin devamı için sağlanan doğrudan desteklerdir. "
            "Destekler dekar başına ödenmek üzere, ürün türüne göre farklı tutarlarla verilir."
        ),
        "kurum": "Tarım Bakanlığı",
        "hedef_kitle": "Organik tarım yapan veya geçiş aşamasında olan çiftçiler",
        "uygunluk_kriterleri": {
            "sektorler": ["tarim"],
            "alt_kategori": "organik",
            "genislik": "genis"
        },
        # Tutar alanları BUGEM 2026 birim fiyat tablosundan (bkz. app/tarim_destek_2026.py KAYNAK_URL);
        # canlı DB ile aynı (Denetim 2 tur 7, 2026-10-08).
        "tesvil_tutari": (
            "Dekar başına 62–465 TL organik tarım desteği (2026; ürün grubu ve bireysel/grup sertifikaya göre, "
            "1. derece örgüt üyesine %25 ilave dâhil); temel destek ayrıca ödenir"
        ),
        "tutari_min": 62,
        "tutari_max": 465,
        "tutari_hesaplama_kriteri": "dekar",
        "tutari_hesaplama_formulu": (
            "Ürün grubuna ve sertifika türüne göre: 3. grup grup sertifikası 62.00 TL/dekar (en az), 1. grup "
            "bireysel sertifika 372.00 TL/dekar. 1. derece tarımsal amaçlı örgüt üyesi çiftçilere katsayının %25'i "
            "kadar ilave ödenir; üst sınır 465.00 TL/dekar bunu içerir. Temel destek buna ek olarak alınır."
        ),
        "basvuru_sartlari": [
            "Tarım yapan işletme",
            "Asgari 5 dekar arazi",
            "Organik Tarım Sertifikası (geçişte veya elde) gerekli",
            "Son 3 yıl kimyasal gübre/ilaç kullanılmamış olmalı"
        ],
        "gerekli_belgeler": [
            "Arazi Belgesi / Satın Alma Sözleşmesi",
            "Organik Sertifika veya Uygunluk Belgesi",
            "Üretim Planı",
            "Toprak Analiz Raporu"
        ],
        "basvuru_yeri": "İL/İlçe Tarım ve Orman Müdürlüğü",
        "basvuru_suresi": "Yıllık ilan edilir (kesin tarihler için BUGEM'in güncel duyurularını kontrol edin)",
        "destek_verilme_suresi": "90-120 gün",
        "baslama_tarihi": datetime(2024, 1, 1),
        "bitis_tarihi": None,
        "kaynak_url": "https://www.tarimorman.gov.tr/BUGEM#organik-tarim"
    },
    {
        "baslik": "Tarımsal Makineleştirme Destekleri",
        "ozet": "Tarım makineleri alımına yönelik finansman ve hibe destekleri.",
        "detay": (
            "Tarım ve Orman Bakanlığı tarafından sağlanan makineleştirme destekleri, "
            "çiftçilerin modern tarım makineleri (traktör, harvestor, sera teknolojileri vb.) "
            "satın almasında finansal destek sağlar. Destekler, hibe (doğrudan ödeme) veya "
            "kredi garantisi şeklinde uygulanmaktadır."
        ),
        "kurum": "Tarım Bakanlığı",
        "hedef_kitle": "Çiftçiler, tarım işletmeleri",
        "uygunluk_kriterleri": {
            "sektorler": ["tarim"],
            "alt_kategori": "makinelestirme",
            "genislik": "genis"
        },
        "tesvil_tutari": "Makine türüne göre ₺50.000 - ₺500.000",
        "tutari_min": 50000,
        "tutari_max": 500000,
        "tutari_hesaplama_kriteri": "genel",
        "tutari_hesaplama_formulu": "Makine türüne göre hibe yüzdesi %40-60 (alış fiyatının belirli bir yüzdesi)",
        "basvuru_sartlari": ["Çiftçi olmalı", "Yeşil Kartlı", "En az 5 yıl tarım yapan"],
        "gerekli_belgeler": ["Yeşil Kart", "Tarımsal Arazisi Belgesi", "Makine Teknik Şartnamesi"],
        "basvuru_yeri": "İL/İlçe Tarım ve Orman Müdürlüğü",
        "basvuru_suresi": "Yıllık ilan edilir (kesin tarihler için BUGEM'in güncel duyurularını kontrol edin)",
        "destek_verilme_suresi": "45-90 gün",
        "baslama_tarihi": datetime(2024, 1, 1),
        "bitis_tarihi": None,
        "kaynak_url": "https://www.tarimorman.gov.tr/BUGEM#makinelestirme"
    },
    {
        "baslik": "Sera/Örtüaltı Tarım Destekleri",
        "ozet": "Sera ve örtüaltı yapı kurulumuna yönelik yatırım destekleri.",
        "detay": (
            "Tarım Bakanlığı tarafından sera ve örtüaltı tarım yapılarının kurulumuna "
            "yönelik hibe ve kredi desteği sağlanmaktadır. Bahçıvanlık ürünleri "
            "(sebze, meyve, çiçek) üretim alanlarında verimlilik artışı amacıyla verilir."
        ),
        "kurum": "Tarım Bakanlığı",
        "hedef_kitle": "Çiftçiler, bahçıvanlık işletmeleri",
        "uygunluk_kriterleri": {
            "sektorler": ["tarim"],
            "alt_kategori": "sera",
            "genislik": "dar"
        },
        "tesvil_tutari": (
            "Dekar başına 310 TL temel destek; iyi tarım sertifikalı örtüaltı üretimde bireysel sertifikayla "
            "+527 TL (en çok 837 TL/da, 2026)"
        ),
        "tutari_min": 310,
        "tutari_max": 837,
        "tutari_hesaplama_kriteri": "dekar",
        "tutari_hesaplama_formulu": (
            "Temel destek 310.00 TL/dekar. İyi tarım uygulamaları sertifikası varsa örtüaltı üretim için bireysel "
            "sertifikada 527.00 TL/dekar ilave; üst sınır bu iki kalemin toplamı. Grup sertifikasında ilave yarıya iner."
        ),
        "basvuru_sartlari": ["Arazi sahibi ya da 20+ yıl kiralamış", "Sera alanı min. 500 m²", "Yeşil Kart"],
        "gerekli_belgeler": ["Arazi Belgesi / Kira Sözleşmesi", "Sera Teknik Projesi", "Yapı Ruhsatı"],
        "basvuru_yeri": "İL/İlçe Tarım ve Orman Müdürlüğü",
        "basvuru_suresi": "Yıllık ilan edilir (kesin tarihler için BUGEM'in güncel duyurularını kontrol edin)",
        "destek_verilme_suresi": "90-120 gün (inşaat sonrası)",
        "baslama_tarihi": datetime(2024, 1, 1),
        "bitis_tarihi": None,
        "kaynak_url": "https://www.tarimorman.gov.tr/BUGEM#sera"
    },
    {
        "baslik": "Sulama Yatırımı Destekleri",
        "ozet": "Tarımsal sulama altyapı yatırımlarına yönelik destek.",
        "detay": (
            "Tarım Bakanlığı tarafından kuyu açma, sulama tesisatı kurulumu, "
            "damla sulama sistemleri vb. sulama altyapı yatırımlarına hibe ve kredi "
            "desteği sağlanmaktadır."
        ),
        "kurum": "Tarım Bakanlığı",
        "hedef_kitle": "Tarım işletmeleri, çiftçi kooperatifleri",
        "uygunluk_kriterleri": {
            "sektorler": ["tarim"],
            "alt_kategori": "sulama",
            "genislik": "genis"
        },
        "tesvil_tutari": "Proje hacmine göre ₺100.000 - ₺1.000.000",
        "tutari_min": 100000,
        "tutari_max": 1000000,
        "tutari_hesaplama_kriteri": "genel",
        "tutari_hesaplama_formulu": "Proje bütçesinin %50-60'ı hibe olarak verilir (kredi garantisi de mümkün); tutar proje büyüklüğüne bağlıdır, yıllık cironuzla orantılı değildir",
        "basvuru_sartlari": ["Arazi sahibi", "En az 10 dekar arazi", "Su kaynağı bulunması"],
        "gerekli_belgeler": ["Arazi Belgesi", "Teknik Proje", "Su Mühendisinden Onay", "Çevre Etüdü"],
        "basvuru_yeri": "İL/İlçe Tarım ve Orman Müdürlüğü / TKDK",
        "basvuru_suresi": "Yıllık ilan edilir (kesin tarihler için TRGM'in güncel duyurularını kontrol edin)",
        "destek_verilme_suresi": "120-180 gün (projenin aşamasına göre)",
        "baslama_tarihi": datetime(2024, 1, 1),
        "bitis_tarihi": None,
        "kaynak_url": "https://www.tarimorman.gov.tr/TRGM#sulama-yatirimlari"
    },
    {
        "baslik": "Hububat ve Baklagil Üretim Destekleri (Mazot-Gübre)",
        "ozet": "Buğday, arpa, mercimek, nohut vb. hububat/baklagil üreticilerine dekar başına mazot ve gübre desteği.",
        "detay": (
            "Tarım ve Orman Bakanlığı her üretim sezonu için 'Bitkisel Üretim Destekleme Birim "
            "Fiyatları' kararnamesiyle hububat ve baklagil üreticilerine dekar başına mazot ve "
            "gübre masraflarını karşılamaya yönelik doğrudan destek öder. Tutarlar ürün grubuna "
            "göre yıllık kararname ile belirlenir."
        ),
        "kurum": "Tarım Bakanlığı",
        "hedef_kitle": "Hububat/baklagil üreten çiftçiler",
        "uygunluk_kriterleri": {
            "sektorler": ["tarim"],
            "alt_kategori": "tahil_baklagil",
            "genislik": "dar"
        },
        "tesvil_tutari": (
            "Dekar başına 620–806 TL (2026): temel destek + planlı üretim desteği, her biri ürün katsayısı × "
            "310 TL (mercimek/nohut 1,0; buğday/arpa/mısır 1,3); sertifikalı tohum ayrıca. 2026'da mazot ve "
            "gübre desteği 'temel destek' adıyla birleştirildi"
        ),
        "tutari_min": 620,
        "tutari_max": 806,
        "tutari_hesaplama_kriteri": "dekar",
        "tutari_hesaplama_formulu": (
            "Temel destek + planlı üretim desteği. Kategori katsayısı ürüne göre değişir: mercimek/nohut 1,0 "
            "(310.00 TL/da), buğday/arpa/mısır 1,3 (403.00 TL/da). İki kalem ayrı ayrı ödendiği için alt sınır "
            "620.00, üst sınır 806.00 TL/dekar. Sertifikalı tohum kullanılırsa ilave ödenir. Birim değer 310.00 "
            "TL/da (katsayı 1)."
        ),
        "basvuru_sartlari": [
            "Çiftçi Kayıt Sistemi (ÇKS)'ye kayıtlı olmak",
            "Arazi/parsel bilgilerinin ÇKS'de güncel olması",
            "İlgili üretim sezonunda ekim yapılmış olması"
        ],
        "gerekli_belgeler": ["ÇKS Kaydı", "Arazi/Parsel Belgesi", "Ekiliş Beyanı"],
        "basvuru_yeri": "İL/İlçe Tarım ve Orman Müdürlüğü (ÇKS başvurusu)",
        "basvuru_suresi": "Yıllık ilan edilir (ÇKS başvuru dönemi için BUGEM duyurularını takip edin)",
        "destek_verilme_suresi": "Üretim sezonu sonrası, bakanlık ödeme takvimine göre",
        "baslama_tarihi": datetime(2024, 1, 1),
        "bitis_tarihi": None,
        "kaynak_url": "https://www.tarimorman.gov.tr/BUGEM#hububat-baklagil"
    },
    {
        "baslik": "Meyve-Sebze Üretim Destekleri (Mazot-Gübre)",
        "ozet": "Sebze ve meyve üreticilerine dekar başına mazot ve gübre desteği.",
        "detay": (
            "Tarım ve Orman Bakanlığı her üretim sezonu için 'Bitkisel Üretim Destekleme Birim "
            "Fiyatları' kararnamesiyle sebze ve meyve üreticilerine dekar başına mazot ve gübre "
            "masraflarını karşılamaya yönelik doğrudan destek öder. Tutarlar ürün grubuna göre "
            "yıllık kararname ile belirlenir ve genelde hububata göre daha yüksektir (yoğun "
            "işçilik/girdi gerektiren ürünler)."
        ),
        "kurum": "Tarım Bakanlığı",
        "hedef_kitle": "Sebze/meyve üreten çiftçiler",
        "uygunluk_kriterleri": {
            "sektorler": ["tarim"],
            "alt_kategori": "sebze_meyve",
            "genislik": "dar"
        },
        "tesvil_tutari": (
            "Dekar başına 310 TL temel destek (2026, 1. kategori 'diğer ürünler'); fidan kullanım desteği "
            "ayrıca 620 TL/da (standart) veya 1.550 TL/da (sertifikalı). 2026'da mazot ve gübre desteği "
            "'temel destek' adıyla birleştirildi"
        ),
        "tutari_min": 310,
        "tutari_max": 310,
        "tutari_hesaplama_kriteri": "dekar",
        "tutari_hesaplama_formulu": (
            "Sebze ve meyve, tabloda 1. kategori \"Diğer ürünler\" kapsamında: temel destek 310.00 TL/dekar. "
            "Planlı üretim desteği kategorilerinde yer almadığı için o kalem eklenmez. Fidan kullanım desteği "
            "(standart 620,00 / sertifikalı 1.550,00 TL/da) ayrıca alınabilir."
        ),
        "basvuru_sartlari": [
            "Çiftçi Kayıt Sistemi (ÇKS)'ye kayıtlı olmak",
            "Arazi/parsel bilgilerinin ÇKS'de güncel olması",
            "İlgili üretim sezonunda dikim/ekim yapılmış olması"
        ],
        "gerekli_belgeler": ["ÇKS Kaydı", "Arazi/Parsel Belgesi", "Dikim/Ekiliş Beyanı"],
        "basvuru_yeri": "İL/İlçe Tarım ve Orman Müdürlüğü (ÇKS başvurusu)",
        "basvuru_suresi": "Yıllık ilan edilir (ÇKS başvuru dönemi için BUGEM duyurularını takip edin)",
        "destek_verilme_suresi": "Üretim sezonu sonrası, bakanlık ödeme takvimine göre",
        "baslama_tarihi": datetime(2024, 1, 1),
        "bitis_tarihi": None,
        "kaynak_url": "https://www.tarimorman.gov.tr/BUGEM#sebze-meyve"
    }
]


def run() -> int:
    """Tarım Bakanlığı destek programlarını veritabanına ekle/güncelle.
    Zaten varsa (başlık + kurum eşleşmesi) kip yapma."""
    init_db()
    db = SessionLocal()

    eklenen = 0
    for destek_data in TARIM_BAKANLIGI_DESTEKLERI:
        zaten_var = (
            db.query(Tesvik)
            .filter(
                Tesvik.baslik == destek_data["baslik"],
                Tesvik.kurum == destek_data["kurum"],
            )
            .first()
        )
        if zaten_var is not None:
            continue

        tesvik = Tesvik(
            kurum=destek_data["kurum"],
            baslik=destek_data["baslik"],
            ozet=destek_data["ozet"],
            detay=destek_data["detay"],
            hedef_kitle=destek_data.get("hedef_kitle"),
            kaynak_url=destek_data.get("kaynak_url"),
            kategori="tarim",
            baslama_tarihi=destek_data.get("baslama_tarihi"),
            bitis_tarihi=destek_data.get("bitis_tarihi"),
            tesvil_tutari=destek_data.get("tesvil_tutari"),
            uygunluk_kriterleri=destek_data.get("uygunluk_kriterleri", {}),
            tutari_min=destek_data.get("tutari_min"),
            tutari_max=destek_data.get("tutari_max"),
            tutari_hesaplama_kriteri=destek_data.get("tutari_hesaplama_kriteri"),
            tutari_hesaplama_formulu=destek_data.get("tutari_hesaplama_formulu"),
            basvuru_sartlari=destek_data.get("basvuru_sartlari"),
            gerekli_belgeler=destek_data.get("gerekli_belgeler"),
            basvuru_yeri=destek_data.get("basvuru_yeri"),
            basvuru_suresi=destek_data.get("basvuru_suresi"),
            destek_verilme_suresi=destek_data.get("destek_verilme_suresi"),
            guncelleme_tarihi=datetime.now(),
        )
        db.add(tesvik)
        eklenen += 1

    db.commit()
    db.close()
    print(f"Tarım Bakanlığı destekleri: {eklenen} yeni kayıt eklendi.")
    return eklenen


if __name__ == "__main__":
    run()
