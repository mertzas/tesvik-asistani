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

_ASCII = str.maketrans("çğıöşü", "cgiosu")


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
        r"ges\b|gunes enerji\w*|santral\w*|soguk hava\w*|forklift\w*)"),
    # Traktör/mibzer gibi tarım makineleri BİLEREK yok: çiftçi sorusu tarım alt kategorisi
    # (makineleştirme) üzerinden ele alınır; "yatırım" sayılınca 9903 programları KKYP/TSS'yi
    # geri itiyordu (G_persona_esles.py, 2026-10-07).
    "arge": re.compile(
        r"\b(ar-?ge|urun gelistir\w*|gelistirme\w*|prototip\w*|inovasyon\w*|yenilik\w*|"
        r"tasarim\w*|patent\w*|teknoloji gelistir\w*)"),
    "ihracat": re.compile(r"\b(ihracat\w*|ihrac\w*|fuar\w*|yurt ?disi\w*|e-ihracat\w*|dis pazar\w*)"),
    # "3 kişi daha işe alacağım" hiçbir ihtiyaca sınıflanmıyordu (2026-10-07).
    "istihdam": re.compile(r"\b(istihdam\w*|personel\w*|eleman\w*|isci\w*|ise alim\w*|ise al\w*|"
                           r"calisan alim\w*|kisi daha al\w*|sgk tesvik\w*|prim destek\w*)"),
    "dijital": re.compile(
        r"\b(dijital\w*|erp\b|yazilim\w*|e-ticaret\w*|eticaret\w*|otomasyon\w*|yapay zeka\w*)"),
    "finansman": re.compile(r"\b(kredi\w*|kefalet\w*|finansman\w*|faiz\w*|isletme sermaye\w*|nakit\w*)"),
    "girisim": re.compile(
        r"\b(girisim\w*|startup|start-up|bigg|1512|1812|sirket kurmad\w*|sirketles\w*|prototip\w*|"
        r"tohum\w*|kulucka\w*|teknogirisim\w*|is kurma\w*)"),
}

IHTIYAC_ADLARI: dict[str, str] = {
    "yatirim": "makine/tesis yatırımı", "arge": "Ar-Ge ve ürün geliştirme",
    "ihracat": "ihracat", "istihdam": "istihdam", "dijital": "dijital dönüşüm",
    "finansman": "kredi/finansman",
    "girisim": "girişim / şirketleşme öncesi ve erken aşama",
}

_BASLIK = {
    # "yatırım" tek başına yetmez: "Yatırım Tabanlı Girişimcilik" (BiGG) ve "Girişim
    # Sermayesi" girişim/fon programlarıdır; "kapasite" tek başına 1601 gibi ekosistem
    # programlarını yatırım sayıyordu (ölçüm 2026-10-07). "hamle" de yok: TÜBİTAK 1511'in
    # adı "Teknoloji Odaklı Sanayi Hamlesi" ve 9903 kotasını dolduruyordu; 9903 programları
    # zaten kurum adından (Sanayi ve Teknoloji Bakanlığı) yatırım sayılır.
    "yatirim": re.compile(r"yatirim (?:tesvik|destek|kredi)|yatirim-(?:isletme|proje)|yatirimlar|"
                          r"makine|modernizasyon|imalat|kapasite gelistirme"),
    "arge": re.compile(r"ar-?ge|inovasyon|tasarim|patent"),
    "ihracat": re.compile(r"ihracat|pazara giris|doviz kazandirici|e-ihracat|uluslararasi pazar"),
    "istihdam": re.compile(r"istihdam"),
    "dijital": re.compile(r"dijital|yapay zek|e-ticaret|e-ihracat|bilisim|yazilim"),
    "finansman": re.compile(r"kredi|kefalet|finansman"),
    # Girişimcinin KENDİSİNE verilen programlar. Ekosistem tarafı hariç: 1612 uygulayıcı
    # kuruluş çağrısı, 1514 girişim sermayesi fonları, 1601 kapasite artırma (ölçüm 2026-10-07:
    # şirketsiz girişim sorusunda BiGG hiç gelmiyor, model "kaydım yok" diyordu).
    "girisim": re.compile(r"bigg|girisimci destek|girisimcilik destek|ilk adim|teknogirisim|tohum|kulucka"),
}
_GIRISIM_HARIC = re.compile(r"uygulayici kurulus|girisim sermayesi|kapasite artirilmasi")
# Tarım makineleştirme bir yatırım programıdır ama çiftçiye yöneliktir; sektör uyumu
# profil filtresinde ele alınır, burada yalnızca ihtiyaç türü belirlenir.


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
    return [ad for _, ad in sorted(bulunan)]


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
    if kurum in ("Sanayi ve Teknoloji Bakanlığı", "Hazine/Ticaret Bakanligi") or "yatirim tesvik" in kategori:
        sonuc.add("yatirim")
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
