"""
Serbest metin aramada ("Arama" kutusu, /api/sor) kullanicinin yazdigi bir
urun/faaliyet adinin (orn. "cilek", "sut") hangi sektore ait oldugunu
belirlemek icin kullanilan anahtar kelime -> sektor eslemesi.

Neden gerekli: tesvikler tablosundaki 210 kayit genelde program adlarindan
olusuyor ("Hayvancilik Destekleri" gibi) ve neredeyse hicbiri belirli bir
urun adini (orn. "cilek") metninde gecirmiyor. Kullanici duz "cilek" yazip
arattiginda literal substring arama (Tesvik.detay ILIKE %cilek%) 0 sonuc
donuyordu - oysa kullanici gercekte "ben cilek yetistiriyorum, bana uygun
tarim destekleri hangileri" diye sormak istiyor. Bu modul, boyle bir
urun adi tanindiginda aramayi ilgili sektore ("tarim") genisletebilmek
icin kullanilir (bkz. app/main.py sor()).
"""

# sektor -> bu sektore ait yaygin urun/faaliyet anahtar kelimeleri
SEKTOR_URUN_ANAHTAR_KELIMELERI: dict[str, list[str]] = {
    "tarim": [
        # meyve
        "çilek", "cilek", "elma", "üzüm", "uzum", "zeytin", "fındık", "findik",
        "incir", "kiraz", "vişne", "visne", "portakal", "mandalina", "limon",
        "muz", "kayısı", "kayisi", "şeftali", "seftali", "erik", "armut",
        "nar", "kavun", "karpuz",
        # sebze
        "domates", "biber", "patlıcan", "patlican", "salatalık", "salatalik",
        "patates", "soğan", "sogan", "sarımsak", "sarimsak", "havuç", "havuc",
        "lahana", "ıspanak", "ispanak", "marul",
        # tahil / endustriyel bitkiler
        "buğday", "bugday", "arpa", "mısır", "misir", "çavdar", "cavdar",
        "yulaf", "pirinç", "pirinc", "çeltik", "celtik", "nohut", "mercimek",
        "fasulye", "pamuk", "ayçiçeği", "aycicegi", "şeker pancarı",
        "seker pancari", "tütün", "tutun", "çay", "cay", "fındık", "susam",
        # hayvancılık
        "hayvancılık", "hayvancilik", "süt", "sut", "sığır", "sigir",
        "koyun", "keçi", "keci", "tavuk", "kanatlı", "kanatli", "arıcılık",
        "aricilik", "bal", "balıkçılık", "balikcilik", "su ürünleri",
        "su urunleri",
        # genel tarim terimleri
        "sera", "seracılık", "seracilik", "fide", "fidan", "gübre", "gubre",
        "traktör", "traktor", "tarla", "bahçe", "bahce", "bağcılık",
        "bagcilik", "organik tarım", "organik tarim", "çiftçi", "ciftci",
        "çiftlik", "ciftlik",
    ],
}


def anahtar_kelimeden_sektor_bul(metin: str) -> str | None:
    """Verilen serbest metinde (arama sorgusu) taninan bir urun/faaliyet
    anahtar kelimesi geçiyorsa ilgili sektor etiketini dondurur, yoksa None."""
    metin_l = metin.lower()
    for sektor, kelimeler in SEKTOR_URUN_ANAHTAR_KELIMELERI.items():
        if any(kelime in metin_l for kelime in kelimeler):
            return sektor
    return None
