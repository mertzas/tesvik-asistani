"""
Serbest metin aramada ("Arama" kutusu, /api/sor) kullanicinin yazdigi bir
urun/faaliyet adinin (orn. "cilek", "sut") hangi sektore ait oldugunu
belirlemek icin kullanilan anahtar kelime -> sektor eslemesi.

Neden gerekli: tesvikler tablosundaki kayitlar genelde program adlarindan
olusuyor ("Hayvancilik Destekleri" gibi) ve neredeyse hicbiri belirli bir
urun adini (orn. "cilek") metninde gecirmiyor. Kullanici duz "cilek" yazip
arattiginda literal substring arama (Tesvik.detay ILIKE %cilek%) 0 sonuc
donuyordu - oysa kullanici gercekte "ben cilek yetistiriyorum, bana uygun
tarim destekleri hangileri" diye sormak istiyor. Bu modul, boyle bir
urun adi tanindiginda aramayi ilgili sektore ("tarim") genisletebilmek
icin kullanilir (bkz. app/main.py sor()).
"""
import re

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
        # -lik/-lık ile biten kelimeler KOK halinde yazildi: Turkce'de son
        # sessiz yumusuyor (hayvanciliK -> hayvanciliGa), bu yuzden tam hali
        # yazmak cekimli kullanimlari kaciriyordu - "hayvanciliga basladim"
        # hicbir sektore eslesmiyordu (dogrulandi 2026-09-26). Kok hali her
        # iki bicimi de yakalar.
        "hayvancılı", "hayvancili", "süt", "sut", "sığır", "sigir",
        "koyun", "keçi", "keci", "tavuk", "kanatlı", "kanatli", "arıcılı",
        "aricili", "bal", "balıkçılı", "balikcili", "su ürünleri",
        "su urunleri",
        # genel tarim terimleri
        "sera", "seracılı", "seracili", "fide", "fidan", "gübre", "gubre",
        "traktör", "traktor", "tarla", "bahçe", "bahce", "bağcılı",
        "bagcili", "organik tarım", "organik tarim", "çiftçi", "ciftci",
        "çiftlik", "ciftlik",
    ],
}


# Turkce harfler dahil "kelime karakteri" kumesi. re.\w Unicode modunda
# Turkce harfleri zaten kapsiyor ama acik olmak icin tanimliyoruz.
_KELIME_KARAKTERI = re.compile(r"[^\W\d_]", re.UNICODE)

# Turkce unlu uyumu: bir kelimenin ekleri, kokun son unlusuyle ayni siradan
# (art/on) unlu tasir. Bu, kelime basindan eslesen kisa anahtarlarin yanlis
# pozitiflerini ayiklamaya yetiyor (bkz. anahtar_kelimeden_sektor_bul).
def kucult(metin: str) -> str:
    """Turkce'ye dogru kucuk harfe cevirir.

    Python'un str.lower()'i Turkce'de iki yerde yanlis sonuc verir:
      "İ".lower() -> "i̇"  (i + U+0307 BIRLESIK NOKTA, iki kod noktasi!)
      "I".lower() -> "i"   (Turkce'de "ı" olmasi gerekir)
    Birincisi somut bir hataya yol aciyordu: kullanici "ÇİLEK SERASI" diye
    buyuk harfle yazdiginda metin "çi̇lek serasi" oluyor ve "çilek" anahtari
    HIC eslesmiyordu - yani caps lock acik yazan kullanici hicbir sektor
    etiketi alamiyordu (dogrulandi 2026-09-26).
    """
    return metin.replace("İ", "i").replace("I", "ı").lower()


_ART_UNLULER = set("aıou")
_ON_UNLULER = set("eiöü")
_UNLULER = _ART_UNLULER | _ON_UNLULER


def _kelime_basinda_mi(metin: str, konum: int) -> bool:
    """konum, metinde bir kelimenin BASI mi?"""
    if konum == 0:
        return True
    return not _KELIME_KARAKTERI.match(metin[konum - 1])


def _kelime_sonu(metin: str, konum: int) -> int:
    """konum'dan baslayarak icinde bulundugumuz kelimenin bittigi indeks."""
    i = konum
    while i < len(metin) and _KELIME_KARAKTERI.match(metin[i]):
        i += 1
    return i


def _son_unlu(kelime: str) -> str | None:
    for ch in reversed(kelime):
        if ch in _UNLULER:
            return ch
    return None


def _ek_unlu_uyumlu_mu(anahtar: str, kalan: str) -> bool:
    """anahtar'dan sonra gelen `kalan` gecerli bir Turkce ek olabilir mi?

    Tam kanit degil, pratik bir suzgec: ekin ILK unlusu kokun son unlusuyle
    ayni siradan olmali.
        "bal"  + "a"   -> bala   (art + art)  : uyumlu, gecerli cekim
        "bal"  + "e"   -> bale   (art + on)   : UYUMSUZ, ek degil, farkli kelime
        "cilek"+ "ten" -> cilekten (on + on)  : uyumlu
    Kalan hic unlu icermiyorsa (ornegin "hayvancili" + "k") karar veremeyiz,
    kabul ediyoruz.
    """
    if not kalan:
        return True
    kalan_unlu = next((ch for ch in kalan if ch in _UNLULER), None)
    if kalan_unlu is None:
        return True
    kok_unlu = _son_unlu(anahtar)
    if kok_unlu is None:
        return True
    return (kok_unlu in _ART_UNLULER) == (kalan_unlu in _ART_UNLULER)


def anahtar_kelimeden_sektor_bul(metin: str) -> str | None:
    """Verilen serbest metinde (arama sorgusu) taninan bir urun/faaliyet
    anahtar kelimesi geçiyorsa ilgili sektor etiketini dondurur, yoksa None.

    Eslesme KELIME BASINDAN yapilir, kelimenin ortasindan degil. Duz
    substring aramasi su yanlis pozitifleri veriyordu (dogrulandi 2026-09-26):

        "global pazar"   -> tarim   ("bal", global'in icinde)
        "bale kursu"     -> tarim   ("bal")
        "mesut bir gun"  -> tarim   ("sut")

    Yani "global pazara acilmak istiyorum" yazan bir yazilimciya tarim
    tesvikleri gosteriliyordu.

    Kelime SONU serbest birakiliyor cunku Turkce eklemeli bir dil:
    "cilekten", "bugdayi", "hayvanciliga" gibi cekimli hallerin taninmasi
    gerekiyor. Ama serbest birakmak tek basina "bale kursu" -> tarim ("bal"
    kelime basinda) hatasini birakiyordu. Bu yuzden anahtar kelimeden sonra
    gelen kismin gecerli bir Turkce ek olup olmadigi UNLU UYUMU ile
    suzuluyor: "bal" art unlulu oldugu icin eki de art unlulu olmali
    ("bala", "balı", "baldan"); "bale"nin "e"si on unlu, dolayisiyla ek
    degil, farkli bir kelime.

    Kalan bilinen sinirlar (bilerek kabul edildi):
      - "Mısır" hem tahil hem ulke adi. "Mısır'a ihracat yapiyorum" tarim
        olarak etiketlenir; ayirt etmek baglam analizi gerektirir.
      - Unlu uyumu suzgeci tam bir morfoloji cozumleyici degil; kokun son
        unlusuyle uyumlu bir unluyle baslayan farkli bir kelime yine yanlis
        pozitif verebilir. Pratikte bu kalinti cok daha nadir.
    """
    metin_l = kucult(metin)
    for sektor, kelimeler in SEKTOR_URUN_ANAHTAR_KELIMELERI.items():
        for kelime in kelimeler:
            baslangic = metin_l.find(kelime)
            while baslangic != -1:
                if _kelime_basinda_mi(metin_l, baslangic):
                    bitis = baslangic + len(kelime)
                    kalan = metin_l[bitis:_kelime_sonu(metin_l, bitis)]
                    if _ek_unlu_uyumlu_mu(kelime, kalan):
                        return sektor
                baslangic = metin_l.find(kelime, baslangic + 1)
    return None


# ---------------------------------------------------------------------------
# Urun adi -> tarim alt kategorisi
# ---------------------------------------------------------------------------
# NEDEN: profilde "Tarim Kategorisi" acilir listesi bos birakilabiliyor ama
# "Urun Turu" alani dolu olabiliyor ("bugday"). Esleştirme (app/matching.py)
# alt kategoriyi yalnizca "alt_kategori metni urun_turu icinde geciyor mu"
# diye kontrol ediyordu; "tahil_baklagil" ifadesi "bugday" icinde gecmedigi
# icin bu ipucu HIC calismiyordu. Olcum (2026-09-26): urun_turu="bugday"
# girmis bir ciftci icin kendisine tam uyan "Hububat ve Baklagil Uretim
# Destekleri" kaydi, hicbir ilgisi olmayan "Hayvancilik Destekleri" ile ayni
# skoru (0.45) aliyordu.
#
# Degerler, profil acilir listesindeki ve tesvik kayitlarindaki alt_kategori
# sozluguyle AYNI olmak zorunda: hayvancilik | sebze_meyve | tahil_baklagil |
# organik | sera | sulama | makinelestirme
URUN_TARIM_KATEGORISI: dict[str, str] = {
    # tahil / baklagil
    "buğday": "tahil_baklagil", "bugday": "tahil_baklagil",
    "arpa": "tahil_baklagil", "çavdar": "tahil_baklagil", "cavdar": "tahil_baklagil",
    "yulaf": "tahil_baklagil", "mısır": "tahil_baklagil", "misir": "tahil_baklagil",
    "çeltik": "tahil_baklagil", "celtik": "tahil_baklagil",
    "pirinç": "tahil_baklagil", "pirinc": "tahil_baklagil",
    "nohut": "tahil_baklagil", "mercimek": "tahil_baklagil",
    "fasulye": "tahil_baklagil", "bakla": "tahil_baklagil",
    # sebze / meyve
    "çilek": "sebze_meyve", "cilek": "sebze_meyve",
    "domates": "sebze_meyve", "biber": "sebze_meyve",
    "patlıcan": "sebze_meyve", "patlican": "sebze_meyve",
    "salatalık": "sebze_meyve", "salatalik": "sebze_meyve",
    "kabak": "sebze_meyve", "marul": "sebze_meyve",
    "ıspanak": "sebze_meyve", "ispanak": "sebze_meyve",
    "lahana": "sebze_meyve", "havuç": "sebze_meyve", "havuc": "sebze_meyve",
    "patates": "sebze_meyve", "soğan": "sebze_meyve", "sogan": "sebze_meyve",
    "sarımsak": "sebze_meyve", "sarimsak": "sebze_meyve",
    "elma": "sebze_meyve", "armut": "sebze_meyve", "üzüm": "sebze_meyve",
    "uzum": "sebze_meyve", "zeytin": "sebze_meyve", "kiraz": "sebze_meyve",
    "vişne": "sebze_meyve", "visne": "sebze_meyve", "şeftali": "sebze_meyve",
    "seftali": "sebze_meyve", "kayısı": "sebze_meyve", "kayisi": "sebze_meyve",
    "erik": "sebze_meyve", "incir": "sebze_meyve", "nar": "sebze_meyve",
    "muz": "sebze_meyve", "kavun": "sebze_meyve", "karpuz": "sebze_meyve",
    "portakal": "sebze_meyve", "mandalina": "sebze_meyve", "limon": "sebze_meyve",
    "fındık": "sebze_meyve", "findik": "sebze_meyve",
    "antep fıstığı": "sebze_meyve", "antep fistigi": "sebze_meyve",
    # hayvancilik
    "süt": "hayvancilik", "sut": "hayvancilik",
    "sığır": "hayvancilik", "sigir": "hayvancilik",
    "büyükbaş": "hayvancilik", "buyukbas": "hayvancilik",
    "küçükbaş": "hayvancilik", "kucukbas": "hayvancilik",
    "koyun": "hayvancilik", "keçi": "hayvancilik", "keci": "hayvancilik",
    "tavuk": "hayvancilik", "kanatlı": "hayvancilik", "kanatli": "hayvancilik",
    "yumurta": "hayvancilik", "besi": "hayvancilik", "besicilik": "hayvancilik",
    "arı": "hayvancilik", "ari": "hayvancilik", "bal": "hayvancilik",
    "arıcılı": "hayvancilik", "aricili": "hayvancilik",
}

# "Belirtmek istemiyorum" secenegi. Gercek bir kategori DEGIL: hicbir tesvik
# kaydinda alt_kategori="genel" yok, dolayisiyla bunu gercek bir secim gibi
# islemek her kategorili kaydin skorunu dusuruyordu - yani kullanici "genel"
# secince BOS BIRAKMAKTAN DAHA KOTU sonuc aliyordu (olcum 2026-09-26:
# tum tarim destekleri 0.70/0.60'tan 0.45'e duşuyordu).
BELIRTILMEMIS_KATEGORILER = {"", "genel", "belirtmek istemiyorum"}


def urun_turunden_tarim_kategorisi(urun_turu: str | None) -> str | None:
    """Urun adindan tarim alt kategorisini cikarir ("bugday" -> tahil_baklagil)."""
    if not urun_turu:
        return None
    metin = kucult(urun_turu)
    # Once tam eslesme (cok kelimeli anahtarlar icin), sonra kelime basi.
    if metin.strip() in URUN_TARIM_KATEGORISI:
        return URUN_TARIM_KATEGORISI[metin.strip()]
    for urun, kategori in URUN_TARIM_KATEGORISI.items():
        baslangic = metin.find(urun)
        while baslangic != -1:
            if _kelime_basinda_mi(metin, baslangic):
                bitis = baslangic + len(urun)
                kalan = metin[bitis:_kelime_sonu(metin, bitis)]
                if _ek_unlu_uyumlu_mu(urun, kalan):
                    return kategori
            baslangic = metin.find(urun, baslangic + 1)
    return None


# Turkce yapim/cekim eklerinin yaygin olanlari, UZUNDAN KISAYA sirali
# (once en uzun ek denenir, yoksa "destekleri" -> "destekler" kalir).
# Tam bir morfoloji cozumleyici degil; amac ILIKE aramasinin ek yuzunden
# kaybettigi eslesmeleri geri kazanmak.
_EKLER = (
    "larından", "lerinden", "larına", "lerine", "larını", "lerini",
    "ların", "lerin", "ları", "leri", "lar", "ler",
    "sından", "sinden", "sında", "sinde", "sını", "sini", "sının", "sinin",
    "ndan", "nden", "tan", "ten", "dan", "den",
    "nın", "nin", "nun", "nün",
    "ası", "esi", "sı", "si", "su", "sü",
    "da", "de", "ta", "te", "ya", "ye",
    "ın", "in", "un", "ün",
    "ı", "i", "u", "ü", "a", "e",
)


def govde(terim: str) -> str:
    """Terimden bir Turkce eki soyup govdeyi dondurur, yoksa terimi.

    NEDEN: veritabani aramasi ILIKE '%terim%' ile yapiliyor ve Turkce
    eklemeli bir dil oldugu icin cekimli terim kayda eslesmiyordu.
    Somut ornek (dogrulandi 2026-09-26): "cilek serasi icin hibe var mi"
    sorgusunda terim "serasi" oluyor ve '%serasi%' ile "Sera/Ortualti Tarim
    Destekleri" kaydi HIC eslesmiyordu - yani tam isabet olan kayit
    bulunamiyordu.

    Govde en az 3 karakter kalacak sekilde soyuluyor; daha kisasi ("ser")
    alakasiz kayitlara eslesip gurultu uretirdi.
    """
    for ek in _EKLER:
        if terim.endswith(ek) and len(terim) - len(ek) >= 4:
            return terim[: -len(ek)]
    return terim
