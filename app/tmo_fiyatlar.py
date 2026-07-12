"""
TMO (Toprak Mahsulleri Ofisi) hububat alim/satis fiyatlari.

Hal Kayit Sistemi'nin (hal.gov.tr) aksine bu veri GUNLUK degil - TMO her
hasat sezonu icin bir kez resmi fiyat aciklar (genelde Haziran-Temmuz).
Bu yuzden canli scraping yerine, sezon aciklandiginda elle guncellenen
curated bir tablo kullaniliyor; hal.gov.tr'de denedigimiz otomatik
postback/scraping yaklasimi bot korumasi (WAF) tarafindan engellendigi
icin guvenilir bulunmadi (bkz. proje notlari).

Guncelleme: TMO her sezon fiyat acikladiginda bu tablo elle guncellenmelidir.
Kaynak: https://www.tmo.gov.tr, resmi basin aciklamalari.
"""

# urun_turu profil alaninda gecen anahtar kelime -> TMO fiyat bilgisi
TMO_URUN_FIYATLARI = {
    "bugday": {
        "anahtar_kelimeler": ["bugday", "buğday"],
        "urun_adi": "Buğday (ekmeklik/makarnalık)",
        "alim_fiyati_ton": 16500,
        "destekli_gelir_ton": 19514,
        "satis_fiyati_ton": 18500,
        "sezon": "2026",
        "kaynak": "TMO 2026 sezonu hububat alım fiyatları (resmi açıklama)",
    },
    "arpa": {
        "anahtar_kelimeler": ["arpa"],
        "urun_adi": "Arpa",
        "alim_fiyati_ton": 12750,
        "destekli_gelir_ton": 15764,
        "satis_fiyati_ton": 14000,
        "sezon": "2026",
        "kaynak": "TMO 2026 sezonu hububat alım fiyatları (resmi açıklama)",
    },
}


def urun_fiyati_bul(urun_turu: str | None) -> dict | None:
    """Profildeki serbest metin urun_turu alaninda TMO'nun fiyat acikladigi
    bir urun geciyorsa, o urune ait fiyat bilgisini dondurur."""
    if not urun_turu:
        return None

    urun_turu_l = urun_turu.strip().lower()
    for bilgi in TMO_URUN_FIYATLARI.values():
        if any(kelime in urun_turu_l for kelime in bilgi["anahtar_kelimeler"]):
            return bilgi

    return None
