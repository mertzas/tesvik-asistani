"""Dayanak denetimi: dış dil modelinin yanıtındaki somut bilgiler bağlamda geçiyor mu (2026-10-11).

Sistem promptunun "UYDURMA YASAK" kuralını modele bırakmak yetmez; yanıt kullanıcıya gitmeden önce kodla denetlenir.
Denetlenenler: URL, TL tutarı, yüzde oranı, tarih, telefon numarası. Her biri bağlamda (ya da kullanıcının sorusunda)
geçmelidir. Hesaplamaya izin verilen tek biçim "kullanıcının verdiği tutar × bağlamdaki oran" ve "kalan gün"
(bağlamdaki tarih − BUGÜN) sayısıdır. Denetimden geçemeyen yanıt atılır; çağıran yerel danışmana düşer.

    python -m app.dayanak --self-test
"""
from __future__ import annotations

import re
import sys
from datetime import date

AYLAR = {"ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5, "haziran": 6,
         "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11, "kasim": 11,
         "aralık": 12, "aralik": 12}
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"'\])|`’]+", re.IGNORECASE)
_EPOSTA = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TARIH_NOKTA = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b")
_TARIH_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_TARIH_AY = re.compile(r"\b(\d{1,2})\s+(" + "|".join(AYLAR) + r")(?:\s+(\d{4}))?\b", re.IGNORECASE)
_TARIH_GUN_AY = re.compile(r"(?<![\d.,])(\d{1,2})\.(\d{1,2})(?![\d.,])")
# Binlik ayırıcı yalnız nokta: "Md. 15 100.000 TL" 15.100.000 okunmasın (Opus incelemesi 2026-10-11).
_SAYI = r"(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
_CARPAN = r"(?:\s*(milyar|milyon|bin))?"
_PARA = r"(?:TL|₺|TRY|Türk\s+lirası|lira|EUR|Avro|Euro|€|USD|(?:ABD\s+)?dolar(?:ının|ını|ına|ı|a|dan)?|\$)"
_TL = re.compile(rf"(?:[₺€$]\s*({_SAYI}){_CARPAN})|(?:({_SAYI}){_CARPAN}\s*(?:'?(?:l[ıi]k|l[uü]k))?\s*{_PARA}"
                 rf"(?![a-zçğıöşü]))", re.IGNORECASE)
_SORU_TUTAR = re.compile(rf"({_SAYI}){_CARPAN}(?:'?\s*(?:l[ıi]k|l[uü]k))?", re.IGNORECASE)
_YUZDE = re.compile(rf"(?:%\s*({_SAYI}))|(?:({_SAYI})\s*%)|(?:yüzde\s+({_SAYI}))", re.IGNORECASE)
_BIRLER = {"bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9}
_ONLAR = {"on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50, "altmış": 60, "yetmiş": 70, "seksen": 80,
          "doksan": 90, "yüz": 100}
_YUZDE_YAZI = re.compile(r"yüzde\s+(" + "|".join(_ONLAR) + r")(?:\s+(" + "|".join(_BIRLER) + r"))?|yüzde\s+("
                         + "|".join(_BIRLER) + r")\b", re.IGNORECASE)
_TELEFON = re.compile(r"(?<![\d.])(?:\+90\s*)?0?\s*\(?(?:[2-5]\d{2}|850)\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?![\d.])"
                      r"|(?<![\d.])444[\s-]?\d[\s-]?\d{3}(?![\d.])")
_KALAN_GUN = re.compile(r"\b(\d{1,4})\s+gün\b", re.IGNORECASE)
CARPANLAR = {"bin": 1e3, "milyon": 1e6, "milyar": 1e9}


def _deger(sayi: str, carpan: str | None = None) -> float | None:
    s = sayi.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", s):
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"\d+\.\d{3}", s):  # 1.000 = bin (Türkçe binlik ayırıcı)
        s = s.replace(".", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return v * CARPANLAR.get((carpan or "").lower(), 1)


def tl_tutarlari(metin: str) -> set[float]:
    """Para tutarları (TL, lira, Avro/EUR, USD/dolar; çarpanıyla). Para birimi ayrımı yapılmaz: değer bağlamda
    herhangi bir para tutarı olarak geçmelidir."""
    sonuc = set()
    for m in _TL.finditer(metin or ""):
        sayi, carpan = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        v = _deger(sayi, carpan)
        if v is not None:
            sonuc.add(round(v, 2))
    return sonuc


def yuzdeler(metin: str) -> set[float]:
    sonuc = set()
    for m in _YUZDE.finditer(metin or ""):
        v = _deger(next(g for g in m.groups() if g))
        if v is not None:
            sonuc.add(round(v, 4))
    for on, bir, tek in _YUZDE_YAZI.findall(metin or ""):
        sonuc.add(float(_ONLAR.get(on.lower(), 0) + _BIRLER.get((bir or tek).lower(), 0)))
    return sonuc


def tarihler(metin: str, varsayilan_yil: int | None = None) -> set[date]:
    """Tarihler. Yılsız "30 Kasım" varsayılan yıl verilirse o yılla okunur, verilmezse 1900 yılıyla (gün-ay
    karşılaştırması için)."""
    sonuc = set()
    for g, a, y in _TARIH_NOKTA.findall(metin or ""):
        try:
            sonuc.add(date(int(y), int(a), int(g)))
        except ValueError:
            pass
    for y, a, g in _TARIH_ISO.findall(metin or ""):
        try:
            sonuc.add(date(int(y), int(a), int(g)))
        except ValueError:
            pass
    for g, ay, y in _TARIH_AY.findall(metin or ""):
        try:
            sonuc.add(date(int(y) if y else (varsayilan_yil or 1900), AYLAR[ay.lower()], int(g)))
        except (ValueError, KeyError):
            pass
    return sonuc


_CARPIM = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*TL/(\w+)\s*[×x]\s*"
                     r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*\w*\s*=\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*TL")
_YUZDE_CARPIM = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*TL(?:\s+\w+)?\s*[×x]\s*%\s*(\d+(?:,\d+)?)"
                           r"\s*=\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*TL")
_BIRIM_FIYAT = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*TL/(\w+)")
# Açık toplama: "4.954,50 TL + 1.234,00 TL = 6.188,50 TL" (her terim ayrıca doğrulanmış olmalı).
_TL_SAYI = r"\d{1,3}(?:\.\d{3})*(?:,\d+)?"
_TOPLAM = re.compile(rf"(?<![\d.,])((?:{_TL_SAYI}\s*TL\s*\+\s*)+{_TL_SAYI}\s*TL)\s*=\s*({_TL_SAYI})\s*TL")


def _gun_ay(tarihler_: set[date]) -> set[tuple[int, int]]:
    return {(t.day, t.month) for t in tarihler_}


def _url_norm(u: str) -> str:
    u = re.split(r"[`’]", u)[0]
    return re.sub(r"^https?://", "", u.rstrip(".,;:!?*_").rstrip("/").lower())


def _rakamlar(s: str) -> str:
    return re.sub(r"\D", "", s)


def denetle(yanit: str, baglam: str, soru: str = "", bugun: date | None = None) -> list[str]:
    """Bağlamda (ya da soruda) dayanağı olmayan somut bilgilerin listesi; boş liste = denetimden geçti.

    Karşılaştırma değer düzeyindedir (aynı sayı bağlamda başka bir anlamda geçiyor diye kabul edilmez). Tek hesap
    istisnası: kullanıcının sorudaki tutarı × bağlamdaki oran ve bunun tamamlayanı (tutar − hesaplanan)."""
    kaynak = f"{baglam}\n{soru}"
    sorunlar: list[str] = []

    baglam_urlleri = {_url_norm(u) for u in _URL.findall(kaynak)}
    for u in _URL.findall(yanit or ""):
        n = _url_norm(u)
        if n and not any(b == n or n.startswith(b + "#") or b.startswith(n + "#") for b in baglam_urlleri):
            sorunlar.append(f"URL bağlamda yok: {u}")
    baglam_eposta = {e.lower() for e in _EPOSTA.findall(kaynak)}
    for e in _EPOSTA.findall(yanit or ""):
        if e.lower() not in baglam_eposta:
            sorunlar.append(f"e-posta bağlamda yok: {e}")

    baglam_tl = tl_tutarlari(kaynak)
    soru_tl = tl_tutarlari(soru) | {round(v, 2) for v in (_deger(m.group(1), m.group(2))
                                                          for m in _SORU_TUTAR.finditer(soru or "")) if v}
    oranlar = yuzdeler(kaynak)
    hesap = {round(t * o / 100, 2) for t in soru_tl for o in oranlar}
    hesaplanabilir = hesap | {round(t - h, 2) for t in soru_tl for h in hesap} | soru_tl
    birim_fiyatlar = {(_deger(m.group(1)), m.group(2).lower()) for m in _BIRIM_FIYAT.finditer(kaynak)}
    # Kuruş basamaklı sayı ("477,10") kaynakta birimsiz geçse de (tablo/formül) aynı değer tutar olarak kabul edilir;
    # tam sayılar kabul edilmez (yıl, madde no gibi sayılarla karışır).
    kurusl = {_deger(x) for x in re.findall(r"(?<![\d.,])\d{1,3}(?:\.\d{3})*,\d{2}(?![\d,])", kaynak)}
    kaynak_sayilari = {_deger(x) for x in re.findall(r"(?<![\d.,])\d{1,3}(?:\.\d{3})*(?:,\d+)?(?![\d,])|"
                                                      r"(?<![\d.,])\d+(?:\.\d+)?(?![\d.,])", kaynak)}
    kaynak_sayilari |= {float(x) for x in re.findall(r"(?<![\d.,])\d+\.\d+(?![\d.,])", kaynak)}
    tam_hesap = set()
    for m in _CARPIM.finditer(yanit or ""):
        birim, adet, sonuc = _deger(m.group(1)), _deger(m.group(3)), _deger(m.group(4))
        if ((birim, m.group(2).lower()) in birim_fiyatlar or birim in kurusl) and adet in kaynak_sayilari \
                and round(birim * adet, 2) == round(sonuc, 2):
            tam_hesap.add(round(sonuc, 2))
    for m in _YUZDE_CARPIM.finditer(yanit or ""):
        taban, oran, sonuc = _deger(m.group(1)), _deger(m.group(2)), _deger(m.group(3))
        if taban in baglam_tl and oran in oranlar and round(taban * oran / 100, 2) == round(sonuc, 2):
            tam_hesap.add(round(sonuc, 2))
    dogru = tam_hesap | kurusl | baglam_tl
    for m in _TOPLAM.finditer(yanit or ""):
        terimler = [_deger(x) for x in re.findall(_TL_SAYI, m.group(1))]
        if all(x in dogru for x in terimler) and round(sum(terimler), 2) == round(_deger(m.group(2)), 2):
            tam_hesap.add(round(_deger(m.group(2)), 2))
    for v in tl_tutarlari(yanit):
        if v in tam_hesap or v in kurusl or v in baglam_tl or any(abs(v - h) <= max(1.0, h * 0.005) for h in hesaplanabilir | baglam_tl):
            continue
        sorunlar.append(f"tutar bağlamda yok: {v:,.0f}")

    for v in yuzdeler(yanit) - oranlar:
        sorunlar.append(f"oran bağlamda yok: %{v:g}")

    yil = bugun.year if bugun else None
    baglam_tarih = tarihler(kaynak, yil)
    if bugun:
        baglam_tarih.add(bugun)
    gun_ay = _gun_ay(baglam_tarih)
    for t in tarihler(yanit, 1900) - baglam_tarih:
        if t.year == 1900 and (t.day, t.month) in gun_ay:
            continue
        sorunlar.append(f"tarih bağlamda yok: {t.isoformat() if t.year != 1900 else f'{t.day:02}.{t.month:02}'}")

    if bugun:
        gecerli_gun = {abs((t - bugun).days) for t in baglam_tarih}
        for g in _KALAN_GUN.findall(yanit or ""):
            gun = int(g)
            if gun not in gecerli_gun and str(gun) not in {_rakamlar(x) for x in re.findall(r"\d+\s+gün", kaynak)}:
                sorunlar.append(f"gün sayısı dayanaksız: {gun} gün")

    baglam_tel = {_rakamlar(x)[-10:] for x in _TELEFON.findall(kaynak)}
    for tel in _TELEFON.findall(yanit or ""):
        if _rakamlar(tel)[-10:] not in baglam_tel:
            sorunlar.append(f"telefon bağlamda yok: {tel.strip()}")
    return sorunlar


def _self_test() -> int:
    baglam = ("BUGÜN: 2026-10-11\n[KOSGEB] Girişimcilik Destek Programı\nKaynak: https://www.kosgeb.gov.tr/site/tr/genel/"
              "destekdetay/1231/girisimcilik\nTutar/oran: 375.000 TL geri ödemesiz, %60 destek; üst limit 1 milyon TL\n"
              "Çağrı: 2026/2. dönem, son gün 22.10.2026. Çağrı merkezi 444 1 567")
    bugun = date(2026, 10, 11)
    k = [("bağlamdaki bilgiler geçer", denetle(
             "KOSGEB 375.000 TL hibe verir, oran %60, üst limit 1.000.000 TL; son gün 22 Ekim 2026 (11 gün kaldı). "
             "Kaynak: https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/1231/girisimcilik", baglam, bugun=bugun) == []),
         ("uydurma tutar yakalanır", any("tutar" in s for s in denetle("500.000 TL hibe", baglam, bugun=bugun))),
         ("uydurma oran yakalanır", any("oran" in s for s in denetle("destek oranı %75", baglam, bugun=bugun))),
         ("uydurma URL yakalanır", any("URL" in s for s in denetle("bkz. https://ornek.com/x", baglam, bugun=bugun))),
         ("uydurma tarih yakalanır", any("tarih" in s for s in denetle("son gün 30.11.2026", baglam, bugun=bugun))),
         ("yanlış kalan gün yakalanır", any("gün" in s for s in denetle("15 gün kaldı", baglam, bugun=bugun))),
         ("soru tutarı × bağlam oranı geçer", denetle("1.000.000 TL yatırımın %60'ı 600.000 TL eder", baglam,
                                                     soru="1 milyon TL yatırım", bugun=bugun) == []),
         ("uydurma telefon yakalanır", any("telefon" in s for s in denetle("arayın: 0312 555 12 34", baglam,
                                                                          bugun=bugun))),
         ("açık çarpım geçer, yanlış çarpım yakalanır",
          denetle("954,20 TL/da × 180 da = 171.756,00 TL", "954,20 TL/da; arazi (dekar): 180", bugun=bugun) == []
          and any("tutar" in x for x in denetle("954,20 TL/da × 180 da = 181.756,00 TL",
                                                "954,20 TL/da; arazi (dekar): 180", bugun=bugun))),
         ("çarpımın N'si kaynakta yoksa geçmez (uydurma ölçekleme)",
          any("tutar" in x for x in denetle("954,20 TL/da × 5000 da = 4.771.000,00 TL", "954,20 TL/da; dekar: 180",
                                            bugun=bugun))
          and any("tutar" in x for x in denetle("375.000 TL/ortak × 4 ortak = 1.500.000 TL", baglam,
                                                bugun=bugun))),
         ("birimsiz kuruşlu kaynak değeri kabul, uydurma kuruşlu değer yakalanır",
          denetle("477,10 TL/da × 180 da = 85.878,00 TL", "1,3 → 477,10 + 477,10; dekar: 180", bugun=bugun) == []
          and any("tutar" in x for x in denetle("478,10 TL/da", "1,3 → 477,10 + 477,10", bugun=bugun))),
         ("açık yüzde çarpımı: doğrusu geçer, yanlışı yakalanır",
          denetle("3.500.000 TL bütçe × %75 = 2.625.000 TL", "bütçe en fazla 3.500.000 TL; %75 hibe", bugun=bugun) == []
          and any("tutar" in x for x in denetle("3.500.000 TL bütçe × %75 = 2.700.000 TL",
                                                "bütçe en fazla 3.500.000 TL; %75 hibe", bugun=bugun))),
         ("açık toplama: doğrusu geçer, yanlışı yakalanır",
          denetle("550,50 TL/da × 9 da = 4.954,50 TL; 205,52 TL/da × 9 da = 1.849,68 TL; toplam 4.954,50 TL + "
                  "1.849,68 TL = 6.804,18 TL", "550,50 TL/da; 205,52 TL/da; dekar: 9", bugun=bugun) == []
          and any("tutar" in x for x in denetle("4.954,50 TL + 1.849,68 TL = 7.000,00 TL",
                                                "550,50 TL/da; 205,52 TL/da; dekar: 9", bugun=bugun))),
         ("kesirli dekar çarpımı", denetle("954,20 TL/da × 180,5 da = 172.233,10 TL",
                                           "954,20 TL/da; dekar: 180.5", bugun=bugun) == []),
         ("'ABD doları' yazımı tutar sayılır", tl_tutarlari("1.000.000 ABD dolarının üzerinde") == {1000000.0}),
         ("Türkçe binlik ayrıştırma", _deger("1.234.567,5") == 1234567.5 and _deger("2,5", "milyon") == 2.5e6),
         ("program kodu tutara karışmaz", tl_tutarlari("1507 600.000 TL destek") == {600000.0}),
         ("yüzde rakamı bağlamda başka anlamda geçse de yakalanır", any("oran" in x for x in denetle(
             "destek oranı %22", baglam + " MADDE 22", bugun=bugun))),
         ("yazıyla yüzde yakalanır", any("oran" in x for x in denetle("yüzde elli hibe", baglam, bugun=bugun))),
         ("Avro tutarı yakalanır", any("tutar" in x for x in denetle("100.000 Avro destek", baglam, bugun=bugun))),
         ("lira tutarı yakalanır", any("tutar" in x for x in denetle("500 bin lira", baglam, bugun=bugun))),
         ("yılsız tarih yakalanır", any("tarih" in x for x in denetle("son gün 30 Kasım", baglam, bugun=bugun))
          and denetle("son gün 22 Ekim", baglam, bugun=bugun) == []),
         ("444 telefon yakalanır", any("telefon" in x for x in denetle("444 9 876", baglam, bugun=bugun))
          and denetle("444 1 567", baglam, bugun=bugun) == []),
         ("e-posta ve www yakalanır", len(denetle("destek@ornek.gov.tr ve www.hibe-portal.com", baglam,
                                                   bugun=bugun)) == 2),
         ("kesik URL kabul edilmez", any("URL" in x for x in denetle(
             "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/12", baglam, bugun=bugun))),
         ("2 milyonluk yatırımın %60'ı ve kalanı geçer", denetle(
             "2.000.000 TL yatırımın %60'ı 1.200.000 TL, kalan 800.000 TL özkaynak", baglam,
             soru="2 milyonluk yatırım", bugun=bugun) == []),
         ("madde numarası tutara karışmaz", denetle("Md. 15 375.000 TL", baglam, bugun=bugun) == []),
         ("tarih biçimleri", tarihler("22.10.2026 ve 2026-10-22 ve 22 Ekim 2026") == {date(2026, 10, 22)})]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(_self_test())
