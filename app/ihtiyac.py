"""Sorudaki ihtiyaç/harcama türü ve programların bu türlere uygunluğu (saf fonksiyonlar).

Arama (app/rag.retrieve) yalnızca kelime eşleşmesine dayandığında "makine alacağım"
sorusu 9903 yatırım teşviklerini hiç getirmiyor, "makine" kelimesi geçen tarım
makineleştirme programını getiriyordu (ölçüm 2026-10-07). Bu modül soruyu ihtiyaç
türlerine, programları da aynı türlere çevirir; arama ikisini eşleştirir.

Program sınıflandırması yalnızca yapılandırılmış alanlara ve başlığa dayanır
(kurum, kategori, sektör etiketi, tutar niteliği, TÜBİTAK kaynak URL bölümü);
açıklama metni kullanılmaz çünkü KGF/TÜBİTAK sayfalarında menü gürültüsü var.
"""
from __future__ import annotations

import re
from typing import Any

from app.urun_sektor_anahtarlari import kucult

_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")   # şapkalı harfler de ("yapay zekâ", "kâr")


def _katla(metin: str | None) -> str:
    return kucult(metin or "").translate(_ASCII)


# ihtiyaç -> soruda arandığı kalıplar (aksansız küçük harf metin üzerinde)
SORU_KALIPLARI: dict[str, re.Pattern] = {
    # Makine/teçhizat adları da yatırımdır: "5 eksenli CNC tezgahı almak istiyoruz ... krediler" sorusu
    # yalnızca "finansman" sayılıp aramada 8 KGF kredisi getiriyor, 9903 ve Kapasite Geliştirme
    # gelmiyordu (tarayıcı denemesi 2026-10-07).
    "yatirim": re.compile(
        r"\b(makine\w*|makina\w*|ekipman\w*|techizat\w*|teçhizat\w*|uretim hatt?\w*|hatt?i\b|"
        r"tesis\w*|fabrika\w*|yatirim\w*|kapasite\w*|modernizasyon\w*|bina\w*|insaat\w*|"
        r"tezgah\w*|cnc\b|robot\w*|kalip\w*|kalib\w*|pres\b|presi\b|kompresor\w*|jenerator\w*|"
        r"ges\b|gunes enerji\w*|santral\w*|soguk hava\w*|forklift\w*|firin\w*|kavurma\w*|simulator\w*|"
        r"egitim arac\w*|tasit\w*|ekipman\w*)"),
    # Traktör/mibzer gibi tarım makineleri BİLEREK yok: çiftçi sorusu tarım alt kategorisi
    # (makineleştirme) üzerinden ele alınır; "yatırım" sayılınca 9903 programları KKYP/TSS'yi
    # geri itiyordu (G_persona_esles.py, 2026-10-07).
    "arge": re.compile(
        r"\b(ar-?ge|urun gelistir\w*|gelistirme\w*|prototip\w*|inovasyon\w*|yenilik\w*|"
        r"tasarim\w*|patent\w*|teknoloji gelistir\w*)"),
    "ihracat": re.compile(r"\b(ihracat\w*|ihrac\w*|fuar\w*|yurt ?disi\w*|e-ihracat\w*|dis pazar\w*|amazon\w*|"
                          r"etsy\w*|ebay\w*|walmart\w*|pazar ?yer\w*|almanya\w*|avrupa\w*|abd\b|amerika\w*|"
                          r"korfez\w*|ingiltere\w*)"),
    # "3 kişi daha işe alacağım" hiçbir ihtiyaca sınıflanmıyordu (2026-10-07).
    "istihdam": re.compile(r"\b(istihdam\w*|personel\w*|eleman\w*|isci\w*|ise alim\w*|ise al\w*|"
                           r"calisan alim\w*|calisan al\w*|kisi daha al\w*|sgk\b|iskur\w*|sgk tesvik\w*|prim destek\w*|"
                           r"prim tesvik\w*|sigorta prim\w*|isveren prim\w*|usta ogretici\w*)"),
    "dijital": re.compile(
        r"\b(dijital\w*|erp\b|yazilim\w*|otomasyon\w*|yapay zeka\w*|amazon\w*|etsy\w*|pazar ?yer\w*|"
        # "e-ticaret şirketimiz" işletmeyi anlatır; ihtiyaç ancak altyapı/site kurma ise dijitaldir.
        r"e-?ticaret (?:altyap|sitesi kur|sitesi ac|sistem)\w*)"),
    "finansman": re.compile(r"\b(kredi\w*|kefalet\w*|finansman\w*|faiz\w*|isletme sermaye\w*|nakit\w*)"),
    "girisim": re.compile(
        r"\b(girisim\w*|startup|start-up|bigg|1512|1812|sirket kurmad\w*|sirket kurar\w*|sirketles\w*|"
        r"prototip\w*|tohum\w*|kulucka\w*|teknogirisim\w*|is kurma\w*)"),
    # Persona denemesi 2026-10-12: "dolu ve don riskine karşı sigorta" sorusu SGK prim teşviklerini, "kargo
    # masrafı" sorusu fuar desteklerini, "Instagram reklam giderleri" sorusu kredi kalabalığını getiriyordu.
    # SGK/işveren primi "istihdam"dır; burada yalnız ürün/alacak/mesleki sigorta.
    "sigorta": re.compile(r"\b(sigorta\w*|tarsim\w*|dolu\w*|don\b|dondan|afet\w*|alacak sigorta\w*)"),
    "tanitim": re.compile(r"\b(reklam\w*|tanitim\w*|pazarlama\w*|instagram\w*|google ads|sosyal medya\w*|"
                          r"marka(?!\w* tescil)\w*)"),
    # Marka/patent tescili ayrı bir gider kalemidir (reklam değil).
    "tescil": re.compile(r"\b(tescil\w*|patent\w*|faydali model\w*)"),
    "lojistik": re.compile(r"\b(kargo\w*|lojistik\w*|depo\b|depo[a-z]+|fulfillment|siparis karsila\w*|"
                           r"gonderi\w*|nakliye\w*|navlun\w*)"),
    # Çiftçinin dekar başı doğrudan ödemesi (temel destek, alan bazlı gelir desteği, eski mazot/gübre).
    # "bahçe/tarla" araziyi anlatır ("bahçeyi yenilemek" bir yatırım sorusudur); ödeme ihtiyacı sayılmaz.
    "tarim_odeme": re.compile(r"\b(dekar\w*|donum\w*|alan bazli\w*|gelir destek\w*|temel destek\w*|mazot\w*|"
                              r"gubre\w*)"),
}
# "SGK teşviki", "işveren primi", "sigorta primi" istihdam sorusudur; sigorta ihtiyacı sayılmaz.
_SGK_SIGORTA = re.compile(r"\bsgk\b|isveren|sigorta prim\w*|prim (?:tesvik|destek|indirim)\w*|sigortali\w*|"
                          r"sosyal sigorta\w*|issizlik sigorta\w*")

IHTIYAC_ADLARI: dict[str, str] = {
    "yatirim": "makine/tesis yatırımı", "arge": "Ar-Ge ve ürün geliştirme",
    "ihracat": "ihracat", "istihdam": "istihdam", "dijital": "dijital dönüşüm",
    "finansman": "kredi/finansman",
    "girisim": "girişim / şirketleşme öncesi ve erken aşama",
    "sigorta": "ürün/alacak sigortası", "tanitim": "reklam, tanıtım ve marka", "lojistik": "kargo, depo ve lojistik",
    "tarim_odeme": "dekar başı tarımsal destek ödemesi", "tescil": "marka/patent tescili",
}

_BASLIK = {
    # "yatırım" tek başına yetmez: "Yatırım Tabanlı Girişimcilik" (BiGG) ve "Girişim
    # Sermayesi" girişim/fon programlarıdır; "kapasite" tek başına 1601 gibi ekosistem
    # programlarını yatırım sayıyordu (ölçüm 2026-10-07). "hamle" de yok: TÜBİTAK 1511'in
    # adı "Teknoloji Odaklı Sanayi Hamlesi" ve 9903 kotasını dolduruyordu; 9903 programları
    # zaten kurum adından (Sanayi ve Teknoloji Bakanlığı) yatırım sayılır.
    "yatirim": re.compile(r"yatirim (?:tesvik|destek|kredi)|yatirim-(?:isletme|proje)|yatirimlar|"
                          r"makine|modernizasyon|imalat|kapasite gelistirme|turizm yatirim|turizmi tesvik kanunu"),
    "arge": re.compile(r"ar-?ge|inovasyon|tasarim|patent"),
    "ihracat": re.compile(r"ihracat|pazara giris|doviz kazandirici|e-ihracat|uluslararasi pazar"),
    "istihdam": re.compile(r"istihdam"),
    "dijital": re.compile(r"dijital|yapay zek|e-ticaret|e-ihracat|bilisim|yazilim"),
    "finansman": re.compile(r"kredi|kefalet|finansman"),
    # Girişimcinin KENDİSİNE verilen programlar. Ekosistem tarafı hariç: 1612 uygulayıcı
    # kuruluş çağrısı, 1514 girişim sermayesi fonları, 1601 kapasite artırma (ölçüm 2026-10-07:
    # şirketsiz girişim sorusunda BiGG hiç gelmiyor, model "kaydım yok" diyordu).
    "girisim": re.compile(r"bigg|girisimci destek|girisimcilik destek|girisimcilik egitim|genc girisimci|ilk adim|"
                          r"teknogirisim|tohum|"
                          r"kulucka"),
    "sigorta": re.compile(r"sigorta"),
    # Yalnız "marka" değil: "Şirket ve Marka Alım Desteği" bir satın alma desteğidir (persona denemesi 2026-10-12).
    "tanitim": re.compile(r"reklam|tanitim|pazarlama|markalasma|marka kredi|turquality"),
    "tescil": re.compile(r"tescil|patent"),
    "lojistik": re.compile(r"lojistik|siparis karsilama|fulfillment|birim kira|depo|dagitim ag"),
}
_GIRISIM_HARIC = re.compile(r"uygulayici kurulus|girisim sermayesi|kapasite artirilmasi")
# Tarım makineleştirme bir yatırım programıdır ama çiftçiye yöneliktir; sektör uyumu
# profil filtresinde ele alınır, burada yalnızca ihtiyaç türü belirlenir.


# İşyeri yenileme/tadilat bir yatırımdır ("butik otelimizi yenilemek", persona denemesi 2026-10-12); belge, ruhsat
# ya da üyelik yenileme değildir. Bahçe/fidan yenileme tarım alt kategorisinde ele alınır (makine notu yukarıda).
_YENILEME = re.compile(r"\b(?:yenile(?:me|mek|yecek|yip|rek)\w*|tadilat\w*|renovasyon\w*|restorasyon\w*)")
_YENILEME_DISI = re.compile(r"belge|sertifika|ruhsat|lisans|sozlesme|uyelik|kayit|abonelik|bahce|tarla|fidan|agac|"
                            r"ocak|bag\b|kredi(?:mi|yi) yenile")


_FIRMA_ARGE = re.compile(
    r"ar-?ge projeleri|kobi ar-?ge|ar-?ge baslangic|oncelikli alanlar|universite-sanayi|"
    r"eureka|eurostars|sanayide yesil donusum")


def soru_ihtiyaclari(soru: str) -> list[str]:
    """Sorudaki ihtiyaç türleri, soruda geçiş sırasıyla."""
    metin = _katla(soru)
    bulunan: list[tuple[int, str]] = []
    for ad, kalip in SORU_KALIPLARI.items():
        m = kalip.search(metin)
        if m:
            bulunan.append((m.start(), ad))
    if "yatirim" not in {ad for _, ad in bulunan}:
        m = _YENILEME.search(metin)
        if m and not _YENILEME_DISI.search(metin):
            bulunan.append((m.start(), "yatirim"))
    ihtiyaclar = [ad for _, ad in sorted(bulunan)]
    if "sigorta" in ihtiyaclar and _SGK_SIGORTA.search(metin) and not re.search(r"tarsim|dolu|don\b|afet|alacak", metin):
        ihtiyaclar.remove("sigorta")
    # "dijital pazarlama/reklam" bir tanıtım ihtiyacıdır, dijital dönüşüm değildir.
    if "dijital" in ihtiyaclar and re.search(r"dijital (?:pazarlama|reklam|tanitim)", metin) and not re.search(
            r"dijitalles|dijital donusum|erp\b|yazilim|otomasyon|yapay zeka", metin):
        ihtiyaclar.remove("dijital")
        if "tanitim" not in ihtiyaclar:
            ihtiyaclar.append("tanitim")
    # "Markamızı yurt dışında tescil ettirmek": ihtiyaç tescildir; "marka" kelimesi tek başına tanıtım sayılmaz.
    if "tescil" in ihtiyaclar and "tanitim" in ihtiyaclar and not re.search(
            r"reklam|tanitim|pazarlama|instagram|google ads|sosyal medya", metin):
        ihtiyaclar.remove("tanitim")
    # "Depoya 3 kişi alacağız": depo işyeridir, ihtiyaç istihdamdır.
    if "istihdam" in ihtiyaclar and "lojistik" in ihtiyaclar and not re.search(
            r"kargo|lojistik|fulfillment|siparis karsila|nakliye|navlun|gonderi|depolama", metin):
        ihtiyaclar.remove("lojistik")
    # "dijital baskı makinesi" (matbaa) bir makine yatırımıdır, dijital dönüşüm değildir (persona denemesi 2026-10-12).
    if "dijital" in ihtiyaclar and re.search(r"dijital bask", metin) and not re.search(
            r"dijitalles|dijital donusum|erp\b|yazilim|e-ticaret|eticaret|otomasyon|yapay zeka", metin):
        ihtiyaclar.remove("dijital")
    return ihtiyaclar


def _tubitak_bolumu(url: str | None) -> str | None:
    m = re.search(r"/destekler/([^/]+)/", url or "")
    return m.group(1) if m else None


def program_ihtiyaclari(t: Any) -> set[str]:
    """Bir teşvik kaydının hizmet ettiği ihtiyaç türleri."""
    k = getattr(t, "uygunluk_kriterleri", None) or {}
    sektorler = {s.lower() for s in k.get("sektorler", [])}
    baslik = _katla(getattr(t, "baslik", ""))
    kurum = getattr(t, "kurum", "") or ""
    kategori = _katla(getattr(t, "kategori", ""))
    nitelik = k.get("tutar_niteligi")
    sonuc: set[str] = set()

    for ad, kalip in _BASLIK.items():
        if kalip.search(baslik):
            sonuc.add(ad)
    if "girisim" in sonuc and _GIRISIM_HARIC.search(baslik):
        sonuc.discard("girisim")
    if "dijital" in sonuc and re.search(r"dijital (?:kefalet|kanal)", baslik):
        sonuc.discard("dijital")   # krediyi dijital kanaldan veren kefalet; dijital dönüşüm desteği değil
    if "istihdam" in sonuc and re.search(r"istihdami koruma|istihdam koruma|istihdam taahhutlu", baslik):
        # Zor dönemde istihdamı koruma ve istihdam taahhütlü KOBİ finansmanı kredi ürünleridir, işe alım teşviki değil.
        sonuc.discard("istihdam")
        sonuc.add("finansman")
    if "sigorta" in sonuc and (kurum == "SGK / İŞKUR" or re.search(
            r"sigortalari isveren|isveren hisse|sosyal sigorta|issizlik sigorta", baslik)):
        sonuc.discard("sigorta")   # SGK işveren primi teşvikleri istihdamdır (TARSİM "prim desteği" sigortadır)
    if "tanitim" in sonuc and re.search(r"marka ve kadin|markalasma program", baslik) is None and \
            re.search(r"tescil", baslik) and kurum == "TUBITAK":
        sonuc.discard("tanitim")   # patent/tescil Ar-Ge çağrıları
    if kurum == "SGK / İŞKUR":
        # "imalatta 5 puan" gibi başlık ifadeleri SGK teşvikini yatırım programı yapmaz.
        sonuc.discard("yatirim")
    if kurum == "SGK / İŞKUR" and "sigorta" not in sonuc and not re.search(r"is sagligi|isg\b", baslik):
        # SGK/İŞKUR teşvikleri işverene işe alım/istihdam teşvikidir ("Malullük, Yaşlılık ve Ölüm Sigortaları İşveren
        # Hissesinden Prim İndirimi" başlığında "istihdam" geçmez ama en geniş kapsamlı istihdam teşvikidir).
        sonuc.add("istihdam")
    if kurum == "KOSGEB" and re.search(r"yonde|yonderlik", baslik):
        # YÖNDE kapsamında dijital dönüşüm değerlendirme analizi ve yol haritası var (KOSGEB program sayfası).
        sonuc.add("dijital")
    if kurum == "Tarım Bakanlığı" and k.get("alt_kategori") != "makinelestirme" and re.search(
            r"temel destek|uretim destek|alan bazli|organik tarim destek|ortualti|iyi tarim|fidan|tohum", baslik):
        sonuc.add("tarim_odeme")
    if (kurum in ("Sanayi ve Teknoloji Bakanlığı", "Hazine/Ticaret Bakanligi") or "yatirim tesvik" in kategori) \
            and not re.search(r"teknoloji gelistirme bolgesi|ar-?ge|tasarim indirimi|stopaj|vergi istisna", baslik):
        sonuc.add("yatirim")
    if kurum == "Sanayi ve Teknoloji Bakanlığı" and re.search(r"teknoloji gelistirme bolgesi|ar-?ge|tasarim", baslik):
        # 4691 (Teknopark) ve 5746 (Ar-Ge/tasarım) vergi teşvikleri Ar-Ge faaliyetine bağlıdır, makine yatırımı değil
        # (hakem bulgusu 2026-10-12: Teknopark istisnası sürücü kursuna "makine/tesis yatırımı" diye sunuluyordu).
        sonuc.discard("yatirim")
        sonuc.add("arge")
    if "yatirim" in sonuc and re.search(r"teknik destek", baslik):
        sonuc.discard("yatirim")   # kalkınma ajansı teknik desteği eğitim/danışmanlıktır
    if "ihracat" in sektorler:
        sonuc.add("ihracat")
    if "e-ticaret" in sektorler:
        sonuc.add("dijital")
    if nitelik in ("kredi_kefalet", "faiz_destegi") or kurum == "KGF":
        sonuc.add("finansman")
    if kurum == "TUBITAK":
        # Akademik/etkinlik çağrıları ve sanayi bölümündeki ekosistem programları
        # (TTO, girişim sermayesi, BiGG, değerlendirici çağrısı) işletmenin kendi Ar-Ge
        # projesine destek değildir; yalnızca firma Ar-Ge projesi programları sayılır.
        if (_tubitak_bolumu(getattr(t, "kaynak_url", None)) == "sanayi"
                and _FIRMA_ARGE.search(baslik)):
            sonuc.add("arge")
        else:
            sonuc.discard("arge")
    elif "arge" in sektorler:
        sonuc.add("arge")
    return sonuc


# TÜBİTAK "sanayi" bölümünde olup son kullanıcı İŞLETMEYE verilmeyen çağrılar (kaynak:
# programların kendi "Kimler Başvurabilir" tanımları, 2026-10-07):
#   1503 Proje Pazarları: etkinliği düzenleyen üniversite/TTO/oda vb.
#   1513 TTO Destekleme, 1613 TT Profesyoneli: teknoloji transfer ofisleri
#   1514 Tech-InvesTR: girişim sermayesi fonlarına yatırımcı TTO/TGB/araştırma altyapısı
#   1601: uygulayıcı kuruluşlar (sermaye şirketi/üniversite/oda), "bireysel girişimci başvuramaz"
#   1612: BiGG 1. aşama uygulayıcı kuruluş çağrısı
#   1701: Ar-Ge proje değerlendirme ve izleme çağrısı (hakem/izleyici)
TUBITAK_EKOSISTEM_KODLARI = ("1503", "1513", "1514", "1601", "1612", "1613", "1701")


def isletmeye_yonelik_mi(t: Any) -> bool:
    """Akademisyen/öğretmen/araştırmacıya yönelik çağrılar ve aracı/ekosistem kuruluş
    çağrıları işletme sorularında ve eşleşmede yer almamalı."""
    if (getattr(t, "kurum", "") or "") != "TUBITAK":
        return True
    if _tubitak_bolumu(getattr(t, "kaynak_url", None)) not in (None, "sanayi"):
        return False
    kod = re.match(r"\s*(\d{4})", getattr(t, "baslik", "") or "")
    return not (kod and kod.group(1) in TUBITAK_EKOSISTEM_KODLARI)
