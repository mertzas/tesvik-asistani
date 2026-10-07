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
    "yatirim": re.compile(
        r"\b(makine\w*|makina\w*|ekipman\w*|techizat\w*|teçhizat\w*|uretim hatt?\w*|hatt?i\b|"
        r"tesis\w*|fabrika\w*|yatirim\w*|kapasite\w*|modernizasyon\w*|bina\w*|insaat\w*)"),
    "arge": re.compile(
        r"\b(ar-?ge|urun gelistir\w*|gelistirme\w*|prototip\w*|inovasyon\w*|yenilik\w*|"
        r"tasarim\w*|patent\w*|teknoloji gelistir\w*)"),
    "ihracat": re.compile(r"\b(ihracat\w*|ihrac\w*|fuar\w*|yurt ?disi\w*|e-ihracat\w*|dis pazar\w*)"),
    "istihdam": re.compile(r"\b(istihdam\w*|personel\w*|eleman\w*|isci\w*|ise alim\w*|calisan alim\w*)"),
    "dijital": re.compile(
        r"\b(dijital\w*|erp\b|yazilim\w*|e-ticaret\w*|eticaret\w*|otomasyon\w*|yapay zeka\w*)"),
    "finansman": re.compile(r"\b(kredi\w*|kefalet\w*|finansman\w*|faiz\w*|isletme sermaye\w*|nakit\w*)"),
}

IHTIYAC_ADLARI: dict[str, str] = {
    "yatirim": "makine/tesis yatırımı", "arge": "Ar-Ge ve ürün geliştirme",
    "ihracat": "ihracat", "istihdam": "istihdam", "dijital": "dijital dönüşüm",
    "finansman": "kredi/finansman",
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
    "dijital": re.compile(r"dijital|yapay zek|e-ticaret|e-ihracat"),
    "finansman": re.compile(r"kredi|kefalet|finansman"),
}
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


def isletmeye_yonelik_mi(t: Any) -> bool:
    """Akademisyen/öğretmen/araştırmacıya yönelik TÜBİTAK çağrıları işletme sorularında
    sonuç kotasını doldurmamalı."""
    if (getattr(t, "kurum", "") or "") != "TUBITAK":
        return True
    return _tubitak_bolumu(getattr(t, "kaynak_url", None)) in (None, "sanayi")
