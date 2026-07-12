"""
Profildeki serbest metin `bolge` alanini (il adi) Turkiye'nin 7 cografi
bolgesine (IBBS Duzey-1) esler ve o bolgenin one cikan tarimsal
uretim/uzmanlik alanlarina dair GENEL, resmi kaynaklara (TUIK/Tarim ve
Orman Bakanligi yayinlari) dayanan statik bir referans dondurur.

Bu modul canli/guncel sayisal veri CEKMEZ - TCMB/TUIK/HKS entegrasyonlarinin
aksine (bkz. budget.py, ihracat_fiyatlari.py, hal_fiyatlari.py) burada
"su an X TL" gibi degisken bir deger yok, "bu bolgede tarihsel olarak hangi
urunler one cikar" gibi nispeten sabit, yapisal bir bilgi var. Bu yuzden
TMO fiyatlari gibi (tmo_fiyatlar.py) curated/statik bir sozluk olarak
tutuluyor; canli bir haber/istatistik API'sine baglanip serbest metin
yorumlamak (a) deterministik/tekrarlanabilir olmaktan cikarir, (b) bu
projenin diger tum modulleriyle tutarsiz bir "LLM yorumu" katmani ekler.
Ileride TUIK'in bolgesel/il bazli yillik uretim istatistikleri (Bitkisel
Uretim, Hayvancilik Istatistikleri) indirilip buraya sayisal olarak
eklenebilir; simdilik nitel/yapisal bilgi veriyoruz.
"""

# Il adi (sadelestirilmis, kucuk harf) -> bolge anahtari.
IL_BOLGE_ESLEME: dict[str, str] = {
    # Marmara
    "istanbul": "marmara", "edirne": "marmara", "kirklareli": "marmara", "tekirdag": "marmara",
    "kocaeli": "marmara", "sakarya": "marmara", "yalova": "marmara", "bursa": "marmara",
    "balikesir": "marmara", "canakkale": "marmara", "bilecik": "marmara",
    # Ege
    "izmir": "ege", "aydin": "ege", "denizli": "ege", "mugla": "ege", "manisa": "ege",
    "usak": "ege", "afyonkarahisar": "ege", "kutahya": "ege",
    # Akdeniz
    "antalya": "akdeniz", "mersin": "akdeniz", "adana": "akdeniz", "hatay": "akdeniz",
    "kahramanmaras": "akdeniz", "osmaniye": "akdeniz", "burdur": "akdeniz", "isparta": "akdeniz",
    # Ic Anadolu
    "ankara": "ic_anadolu", "konya": "ic_anadolu", "kayseri": "ic_anadolu", "sivas": "ic_anadolu",
    "eskisehir": "ic_anadolu", "kirikkale": "ic_anadolu", "aksaray": "ic_anadolu",
    "karaman": "ic_anadolu", "kirsehir": "ic_anadolu", "nevsehir": "ic_anadolu", "nigde": "ic_anadolu",
    "yozgat": "ic_anadolu", "cankiri": "ic_anadolu",
    # Karadeniz
    "samsun": "karadeniz", "trabzon": "karadeniz", "rize": "karadeniz", "ordu": "karadeniz",
    "giresun": "karadeniz", "artvin": "karadeniz", "gumushane": "karadeniz", "bayburt": "karadeniz",
    "amasya": "karadeniz", "tokat": "karadeniz", "corum": "karadeniz", "zonguldak": "karadeniz",
    "bartin": "karadeniz", "karabuk": "karadeniz", "kastamonu": "karadeniz", "sinop": "karadeniz",
    "duzce": "karadeniz", "bolu": "karadeniz",
    # Dogu Anadolu
    "erzurum": "dogu_anadolu", "erzincan": "dogu_anadolu", "agri": "dogu_anadolu",
    "kars": "dogu_anadolu", "ardahan": "dogu_anadolu", "igdir": "dogu_anadolu",
    "van": "dogu_anadolu", "mus": "dogu_anadolu", "bitlis": "dogu_anadolu", "hakkari": "dogu_anadolu",
    "elazig": "dogu_anadolu", "tunceli": "dogu_anadolu", "malatya": "dogu_anadolu", "bingol": "dogu_anadolu",
    # Guneydogu Anadolu
    "gaziantep": "guneydogu_anadolu", "sanliurfa": "guneydogu_anadolu", "diyarbakir": "guneydogu_anadolu",
    "mardin": "guneydogu_anadolu", "batman": "guneydogu_anadolu", "siirt": "guneydogu_anadolu",
    "sirnak": "guneydogu_anadolu", "adiyaman": "guneydogu_anadolu", "kilis": "guneydogu_anadolu",
}

BOLGE_BILGI: dict[str, dict] = {
    "marmara": {
        "ad": "Marmara Bölgesi",
        "one_cikan_urunler": ["zeytin", "zeytinyağı", "üzüm", "şeftali", "ayçiçeği", "süt/besi hayvancılığı"],
        "tavsiye": (
            "Marmara, zeytin/zeytinyağı ve ayçiçeğinde Türkiye'nin önde gelen üretim bölgelerinden; "
            "sanayi/lojistiğe yakınlık nedeniyle katma değerli işleme (yağ, konserve) ve doğrudan "
            "ihracat kanalları burada daha avantajlı olabilir."
        ),
    },
    "ege": {
        "ad": "Ege Bölgesi",
        "one_cikan_urunler": ["zeytin", "zeytinyağı", "incir", "üzüm/kuru üzüm", "pamuk", "tütün"],
        "tavsiye": (
            "Ege; zeytinyağı, kuru incir ve kuru üzümde dünya çapında ihracat gücüne sahip bir bölge. "
            "İhracat odaklı üretim yapıyorsanız İZFAŞ/kooperatif kanallarını ve TSE/coğrafi işaret "
            "tescilli ürün avantajlarını değerlendirmenizi öneririz."
        ),
    },
    "akdeniz": {
        "ad": "Akdeniz Bölgesi",
        "one_cikan_urunler": ["turunçgil (narenciye)", "sera sebzeciliği (domates/biber/salatalık)", "muz", "pamuk"],
        "tavsiye": (
            "Akdeniz (özellikle Antalya-Mersin hattı), örtüaltı (sera) sebzecilikte ve turunçgilde "
            "Türkiye'nin en yoğun üretim alanı; erkenci hasat avantajıyla iç pazarda fiyat "
            "avantajı, ihracatta ise AB pazarına yakınlık öne çıkıyor."
        ),
    },
    "ic_anadolu": {
        "ad": "İç Anadolu Bölgesi",
        "one_cikan_urunler": ["buğday/arpa (hububat)", "şeker pancarı", "patates", "elma", "küçükbaş/büyükbaş hayvancılık"],
        "tavsiye": (
            "İç Anadolu, Türkiye'nin tahıl ambarı konumunda (buğday/arpa) ve şeker pancarı üretiminde "
            "başı çekiyor. Hububatta TMO taban fiyatı önemli bir referans; hayvancılıkta yem "
            "maliyetleri bölgedeki en büyük gider kalemi olma eğiliminde."
        ),
    },
    "karadeniz": {
        "ad": "Karadeniz Bölgesi",
        "one_cikan_urunler": ["fındık", "çay", "mısır", "kivi", "süt hayvancılığı"],
        "tavsiye": (
            "Karadeniz, fındıkta dünya üretiminin büyük bölümünü, çayda ise neredeyse tamamını "
            "karşılıyor (Rize/Trabzon-Giresun/Ordu hattı). Bu iki üründe TMO/ÇAYKUR gibi kurumların "
            "taban alım fiyatları önemli bir gelir güvencesi sağlar."
        ),
    },
    "dogu_anadolu": {
        "ad": "Doğu Anadolu Bölgesi",
        "one_cikan_urunler": ["büyükbaş hayvancılık (et/süt)", "arıcılık/bal", "şeker pancarı", "kayısı (Malatya)"],
        "tavsiye": (
            "Doğu Anadolu; geniş mera alanları nedeniyle büyükbaş hayvancılıkta (özellikle Erzurum-Kars "
            "hattında et/süt) ve arıcılıkta güçlü. Malatya kayısıda dünya lideri konumda. Hayvancılıkla "
            "uğraşıyorsanız Tarım Bakanlığı'nın hayvancılık destekleri bu bölgede özellikle önemli bir "
            "gelir kalemi olabilir."
        ),
    },
    "guneydogu_anadolu": {
        "ad": "Güneydoğu Anadolu Bölgesi",
        "one_cikan_urunler": ["pamuk", "buğday", "antep fıstığı", "üzüm", "kırmızı mercimek"],
        "tavsiye": (
            "GAP sulama yatırımları sayesinde Güneydoğu Anadolu, pamuk ve mercimekte önemli bir üretim "
            "merkezi; Antep fıstığında (Gaziantep-Şanlıurfa) ise Türkiye üretiminin büyük kısmı burada. "
            "Sulu tarıma geçişle verim artışı destekleri (TKDK/Tarım Bakanlığı sulama destekleri) "
            "özellikle bu bölgede değerlendirilmeye değer."
        ),
    },
}

KAYNAK_ACIKLAMASI = (
    "TÜİK ve T.C. Tarım ve Orman Bakanlığı'nın yayınladığı bölgesel tarımsal üretim istatistiklerine "
    "dayanan genel/yapısal bir bilgidir; güncel fiyat verisi değildir ve işletmenize özel bir garanti "
    "teşkil etmez."
)


def _sadelestir(metin: str) -> str:
    tr_ceviri = str.maketrans("çÇğĞıİöÖşŞüÜ", "cCgGiIoOsSuU")
    return metin.translate(tr_ceviri).lower().strip()


def bolge_anahtari_bul(il_adi: str | None) -> str | None:
    """Serbest metin il/bolge adini (orn. 'Antalya', 'Gaziantep ili') bilinen
    bolge anahtarlarindan birine (orn. 'akdeniz') esler. Eslesme yoksa None."""
    if not il_adi:
        return None
    metin = _sadelestir(il_adi)
    for il, bolge in IL_BOLGE_ESLEME.items():
        if il in metin:
            return bolge
    return None


def bolgesel_tavsiye_getir(il_adi: str | None) -> dict | None:
    """Profildeki bolge (il) alanina karsilik gelen bolgesel tarim tavsiyesini
    dondurur. Il taninmiyorsa (bos, yanlis yazim, yurt disi vb.) None doner -
    boylece cagiran kod sessizce atlayabilir."""
    bolge = bolge_anahtari_bul(il_adi)
    if bolge is None:
        return None

    bilgi = BOLGE_BILGI[bolge]
    return {
        "bolge_anahtari": bolge,
        "bolge_adi": bilgi["ad"],
        "one_cikan_urunler": bilgi["one_cikan_urunler"],
        "tavsiye": bilgi["tavsiye"],
        "kaynak": KAYNAK_ACIKLAMASI,
    }
