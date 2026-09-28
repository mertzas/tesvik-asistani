#!/usr/bin/env python3
"""
Teşvik kayıtlarının hâlâ başvuruya açık olup olmadığını kaynak sayfadan doğrular.

NEDEN
-----
Ölçüm (2026-09-27): 181 kaydın 111'inde aktif_mi=None, yani programın açık mı
kapalı mı olduğu hiç doğrulanmamış. Kapanmış bir programı başvurulabilir gibi
sunmak kullanıcıyı boşa evrak toplamaya gönderir. 111 sayfayı elle açmak
sürdürülebilir değil ve her ay tekrar gerekiyor; bu yüzden tekrarlanabilir bir
doğrulayıcı.

TASARIM: MUHAFAZAKÂR
--------------------
Düz anahtar kelime araması YANLIŞ POZİTİF üretiyor. Gerçek örnek (TÜBİTAK 4005
sayfası): "Açık ve kapalı uçlu deney" ifadesi "kapalı" kelimesiyle eşleşiyor ve
program yanlışlıkla kapanmış işaretlenebiliyordu. Bu yüzden:

  - Yalnızca CÜMLE DÜZEYİNDE, yüksek güvenli kalıplar kullanılır
    ("başvuruya kapatılmıştır" gibi), tek kelimeler değil.
  - Kalıp bulunamazsa karar VERİLMEZ; aktif_mi None kalır ve kayıt
    "kararsız" olarak raporlanır. Tahmin etmek, bilmemekten kötüdür.
  - Her karar için sayfadan alınan KANIT PARÇASI durum_notu'na yazılır;
    böylece bir insan kararı denetleyebilir.
  - Çelişki varsa (hem açık hem kapalı kalıbı) karar verilmez.

Kullanım:
    python -m scripts.verify_aktiflik --kurum KOSGEB          # rapor
    python -m scripts.verify_aktiflik --kurum TUBITAK --limit 20
    python -m scripts.verify_aktiflik --kurum KOSGEB --uygula
    python -m scripts.verify_aktiflik --tumu --uygula
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from app.logging_setup import kur as gunluklemeyi_kur  # noqa: E402
from app.models import SessionLocal, Tesvik  # noqa: E402

logger = logging.getLogger("aktiflik")

BEKLEME_SN = 1.5   # kurum sunucularini yormamak icin istekler arasi bekleme
ZAMAN_ASIMI = 25
BASLIK = {"User-Agent": "Mozilla/5.0 (tesvik-asistani aktiflik dogrulayici)"}

# KAPALI kaliplari - cumle duzeyinde, yuksek guven.
KAPALI_KALIPLARI = (
    r"başvuruya\s+kapat[ıi]lm[ıi]şt[ıi]r",
    r"başvuruya\s+kapal[ıi]d[ıi]r",
    r"çağr[ıi](?:s[ıi])?\s+kapa(?:nm[ıi]şt[ıi]r|t[ıi]lm[ıi]şt[ıi]r)",
    r"program(?:[ıi])?\s+kapat[ıi]lm[ıi]şt[ıi]r",
    r"programa\s+başvuru\s+al[ıi]nmamaktad[ıi]r",
    r"yürürlükten\s+kald[ıi]r[ıi]lm[ıi]şt[ıi]r",
    r"başvuru\s+al[ıi]mma?\s*durdurulmuştur",
    r"geçici\s+olarak\s+başvuruya\s+kapat[ıi]lm[ıi]şt[ıi]r",
)

# ACIK kaliplari
ACIK_KALIPLARI = (
    r"çağr[ıi](?:s[ıi])?\s+aç[ıi](?:ld[ıi]|lm[ıi]şt[ıi]r)",
    r"başvurular[ıi]?\s+başlad[ıi]",
    r"başvuruya\s+aç[ıi]lm[ıi]şt[ıi]r",
    r"başvurular\s+al[ıi]nmaktad[ıi]r",
    r"başvuru\s+dönemi\s+aç[ıi]k",
    # KOSGEB program sayfalarinda "Yürürlükte Olan Çağrılar" basligi ve
    # ardindan cagri adi geliyor. Basligin ARDINDAN icerik gelmesi sart:
    # yalnizca baslik varsa (bos bolum) program acik demek degil.
    # Baslikta icerik OLMASI sart: baslik + 80 karakter icinde bir cagri adi
    # ya da yil. Yalnizca baslik varsa (bos bolum) acik saymayiz.
    r"yürürlükte\s+olan\s+çağr[ıi]lar[\s\S]{1,80}?"
    r"(?:çağr[ıi]s[ıi]|\d{4}\s+y[ıi]l[ıi]|başvuru\s+dönemi)",
)

# "son basvuru tarihi 31.10.2026" gibi ifadeler - tarih GELECEKTEyse acik sayilir.
SON_BASVURU_TARIHI = re.compile(
    r"son\s+başvuru\s+tarihi[^0-9]{0,20}(\d{1,2})[./](\d{1,2})[./](\d{4})", re.I)
# "1 Eylul-31 Ekim 2026" gibi donem ifadeleri
AYLAR = {"ocak":1,"şubat":2,"mart":3,"nisan":4,"mayıs":5,"haziran":6,
         "temmuz":7,"ağustos":8,"eylül":9,"ekim":10,"kasım":11,"aralık":12}
DONEM_TARIHI = re.compile(
    r"başvuru\s+tarihleri[^0-9]{0,20}\d{1,2}\s+\w+\s*[-–]\s*(\d{1,2})\s+(\w+)\s+(\d{4})", re.I)

# Karar vermeye YETMEYEN ifadeler - o dönem bitmis olabilir ama program acik.
KARARSIZ_KALIPLARI = (
    r"başvuru\s+sonuçlar[ıi]\s+aç[ıi]kland[ıi]",
    r"değerlendirme\s+sürecí?\s+devam",
    # TUBITAK sayfalarinda sik gorulen "13. ÇAĞRISI SONUÇLANDI!" gibi
    # ifadeler o DONEMIN bittigini soyler, programin TAMAMEN kapandigini
    # degil - yeni bir cagri acilabilir. "Kapali" ile karistirilmamali.
    r"çağr[ıi]s[ıi]\s+sonuçland[ıi]",
)

# KGF urun sayfalarinda genellikle acik/kapali diyen bir cumle HIC gecmiyor
# (urun sayfasi sadece sart/oran anlatir). Ama "Hazine Destekli Kefaletler"
# kategorisindeki urunlerin BREADCRUMB'inda (sayfa basindaki "Buradasınız:
# Anasayfa / ... / X >" gezinme cubugu) kategori acikca yaziyor:
#   "Buradasınız: ... / Hazine Destekli Kefaletler / Aktif Destek Paketleri > / Ürün Adı"
#   "Buradasınız: ... / Hazine Destekli Kefaletler / Geçmiş Programlar > / Ürün Adı"
# Bu, sayfanin SOL MENUSUNDEN (tekrarlayan, sayfa icerigini de yutan)
# cok daha guvenilir bir sinyal: breadcrumb sayfada TEK YER geciyor ve
# dogrudan urunun kendisinden hemen once geliyor. Sol menu tabanli bir
# deneme (kelime kumesi ortusmesi) YANLIS SONUC uretmisti: menu footer'da
# tekrarlaniyor ve son tekrar sayfa icerigini de kendi icine aliyordu, bu
# yuzden o yontem terk edildi (bkz. git log). Breadcrumb bu sorunu tasimiyor.
# Yalnizca "Hazine Destekli Kefaletler" alt kategorisi bu ayrimi tasiyor;
# digerlerinde (KOSGEB Destekli Kefaletler, Ozkaynak Kefaletlerimiz vb.)
# eslesme bulunmaz ve kararsiz kalinir - bu dogru davranistir, tahmin
# ETMEK yerine.
KGF_BREADCRUMB_KATEGORI = re.compile(
    r"Buradasınız:.*?(Aktif Destek Paketleri|Geçmiş Programlar)\s*>\s*/",
    re.S)


@dataclass
class Sonuc:
    tesvik_id: object
    baslik: str
    kurum: str
    url: str | None
    karar: str            # "acik" | "kapali" | "kararsiz" | "hata"
    kanit: str = ""
    ayrinti: str = ""


# Bazi kurum sunuculari hizli ardisik isteklerde baglantiyi kesiyor. Olcum
# (2026-09-27): 111 kayitlik taramada 12 kayit alinamadi, cogu kgf.com.tr'den
# "Connection aborted / ConnectionResetError". Tekrar deneme + artan bekleme
# bunlarin cogunu kurtariyor.
YENIDEN_DENEME = 3
_OTURUM: requests.Session | None = None


def _oturum() -> requests.Session:
    """Tek Session: baglanti havuzu yeniden kullanilir, el sikisma maliyeti
    dusuyor ve sunucu daha az yukleniyor."""
    global _OTURUM
    if _OTURUM is None:
        _OTURUM = requests.Session()
        _OTURUM.headers.update(BASLIK)
    return _OTURUM


def _sayfa_metni(url: str) -> str:
    son_hata: Exception | None = None
    for deneme in range(1, YENIDEN_DENEME + 1):
        try:
            r = _oturum().get(url, timeout=ZAMAN_ASIMI, allow_redirects=True)
            r.raise_for_status()
            corba = BeautifulSoup(r.text, "html.parser")
            for etiket in corba(["script", "style", "noscript"]):
                etiket.decompose()
            return " ".join(corba.get_text(" ").split())
        except requests.TooManyRedirects:
            # Yonlendirme dongusu tekrar denemekle cozulmez.
            raise
        except Exception as e:
            son_hata = e
            if deneme < YENIDEN_DENEME:
                bekle = BEKLEME_SN * (2 ** deneme)
                logger.info("%s alinamadi (deneme %d/%d): %s - %.1fs sonra tekrar",
                            url, deneme, YENIDEN_DENEME, type(e).__name__, bekle)
                time.sleep(bekle)
    raise son_hata if son_hata else RuntimeError("bilinmeyen hata")


def _kanit(metin: str, m: re.Match, cevre: int = 90) -> str:
    a = max(0, m.start() - cevre)
    b = min(len(metin), m.end() + cevre)
    return "..." + metin[a:b].strip() + "..."


def _degerlendir(metin: str, bugun: date | None = None) -> tuple[str, str, str]:
    """(karar, kanit, ayrinti) doner. Karar vermek icin yeterli isaret yoksa
    'kararsiz' doner - tahmin ETMEZ."""
    bugun = bugun or date.today()

    kapali_bulgu = None
    for kalip in KAPALI_KALIPLARI:
        m = re.search(kalip, metin, re.I)
        if m:
            kapali_bulgu = (kalip, _kanit(metin, m))
            break

    acik_bulgu = None
    for kalip in ACIK_KALIPLARI:
        m = re.search(kalip, metin, re.I)
        if m:
            acik_bulgu = (kalip, _kanit(metin, m))
            break

    # Gelecek tarihli son basvuru / donem sonu -> acik sayilir
    tarih_bulgu = None
    for m in SON_BASVURU_TARIHI.finditer(metin):
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            continue
        if d >= bugun:
            tarih_bulgu = (f"son başvuru tarihi {d.isoformat()}", _kanit(metin, m))
            break
    if tarih_bulgu is None:
        for m in DONEM_TARIHI.finditer(metin):
            ay = AYLAR.get(m.group(2).lower())
            if not ay:
                continue
            try:
                d = date(int(m.group(3)), ay, int(m.group(1)))
            except ValueError:
                continue
            if d >= bugun:
                tarih_bulgu = (f"başvuru dönemi sonu {d.isoformat()}",
                               _kanit(metin, m))
                break

    # Celiski -> karar verme
    if kapali_bulgu and (acik_bulgu or tarih_bulgu):
        return ("kararsiz", kapali_bulgu[1],
                "Sayfada hem kapalı hem açık işareti var; elle kontrol gerekiyor. "
                f"kapalı kalıbı: {kapali_bulgu[0]}")

    if kapali_bulgu:
        return ("kapali", kapali_bulgu[1], f"kalıp: {kapali_bulgu[0]}")
    if tarih_bulgu:
        return ("acik", tarih_bulgu[1], tarih_bulgu[0])
    if acik_bulgu:
        return ("acik", acik_bulgu[1], f"kalıp: {acik_bulgu[0]}")

    for kalip in KARARSIZ_KALIPLARI:
        m = re.search(kalip, metin, re.I)
        if m:
            return ("kararsiz", _kanit(metin, m),
                    "Yalnızca sonuç/değerlendirme duyurusu var; programın açık "
                    "olup olmadığı anlaşılmıyor.")

    bc = KGF_BREADCRUMB_KATEGORI.search(metin)
    if bc:
        if bc.group(1) == "Geçmiş Programlar":
            return ("kapali", _kanit(metin, bc),
                    "KGF sayfa gezinme çubuğunda (breadcrumb) bu ürün "
                    "'Geçmiş Programlar' kategorisinde.")
        return ("acik", _kanit(metin, bc),
                "KGF sayfa gezinme çubuğunda (breadcrumb) bu ürün "
                "'Aktif Destek Paketleri' kategorisinde.")

    return ("kararsiz", "", "Sayfada aktiflik hakkında yüksek güvenli bir "
                            "ifade bulunamadı.")


def _not_yaz(t: Tesvik, s: Sonuc, simdi: datetime) -> None:
    tarih = simdi.date().isoformat()
    if s.karar == "kapali":
        onek = ("⚠️ ARTIK AKTİF DEĞİL. Kaynak sayfada başvuruya kapalı olduğu "
                "belirtiliyor.")
    else:
        onek = "DURUM: Doğrulanmış, güncel/aktif program."
    t.durum_notu = (
        f"{onek} Doğrulama: {tarih}, kaynak: {s.url}. "
        f"Dayanak ({s.ayrinti}): {s.kanit}"
    ).strip()


def calistir(kurum: str | None, tumu: bool, limit: int | None,
             uygula: bool, yeniden: bool) -> int:
    gunluklemeyi_kur("INFO")
    db = SessionLocal()
    try:
        q = db.query(Tesvik)
        if kurum:
            q = q.filter(Tesvik.kurum == kurum)
        if not yeniden:
            q = q.filter(Tesvik.aktif_mi.is_(None))
        kayitlar = [t for t in q.all() if (t.kaynak_url or "").startswith("http")]
        atlanan_urlsiz = (len(q.all()) - len(kayitlar))
        if limit:
            kayitlar = kayitlar[:limit]

        if not kayitlar:
            print("Dogrulanacak kayit yok.")
            return 0

        print(f"{len(kayitlar)} kayit kontrol edilecek "
              f"({atlanan_urlsiz} kayit kaynak_url'siz oldugu icin atlandi)")
        if not tumu and not kurum:
            print("UYARI: --kurum veya --tumu verilmedi, tum kayitlar taranacak.")

        simdi = datetime.now(timezone.utc)
        sonuclar: list[Sonuc] = []
        for i, t in enumerate(kayitlar, 1):
            print(f"[{i}/{len(kayitlar)}] {(t.baslik or '')[:56]}", flush=True)
            try:
                metin = _sayfa_metni(t.kaynak_url)
            except Exception as e:
                logger.warning("sayfa alinamadi (%s): %s: %s",
                               t.kaynak_url, type(e).__name__, e)
                sonuclar.append(Sonuc(t.id, t.baslik, t.kurum, t.kaynak_url,
                                      "hata", ayrinti=f"{type(e).__name__}: {e}"))
                time.sleep(BEKLEME_SN)
                continue

            karar, kanit, ayrinti = _degerlendir(metin)
            s = Sonuc(t.id, t.baslik, t.kurum, t.kaynak_url, karar, kanit, ayrinti)
            sonuclar.append(s)
            print(f"        -> {karar}  ({ayrinti[:70]})")

            if uygula and karar in ("acik", "kapali"):
                t.aktif_mi = (karar == "acik")
                _not_yaz(t, s, simdi)
                t.guncelleme_tarihi = simdi
            time.sleep(BEKLEME_SN)

        if uygula:
            db.commit()

        from collections import Counter
        ozet = Counter(s.karar for s in sonuclar)
        print("\n" + "=" * 62)
        print("OZET:", dict(ozet))
        print(f"{'YAZILDI' if uygula else 'RAPOR (yazilmadi)'}: "
              f"{ozet.get('acik',0)} acik, {ozet.get('kapali',0)} kapali "
              f"olarak isaretlen{'di' if uygula else 'ecek'}; "
              f"{ozet.get('kararsiz',0)} kararsiz, {ozet.get('hata',0)} hata.")

        if ozet.get("kararsiz"):
            print("\nKARARSIZ KALANLAR (elle kontrol gerekiyor):")
            for s in sonuclar:
                if s.karar == "kararsiz":
                    print(f"  {s.baslik[:52]:54} {s.ayrinti[:60]}")
        if ozet.get("hata"):
            print("\nSAYFASINA ULASILAMAYANLAR:")
            for s in sonuclar:
                if s.karar == "hata":
                    print(f"  {s.baslik[:52]:54} {s.ayrinti[:60]}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Tesvik aktiflik dogrulayici.")
    a.add_argument("--kurum", help="Yalnizca bu kurumun kayitlari (KOSGEB, TUBITAK, KGF...)")
    a.add_argument("--tumu", action="store_true", help="Tum kurumlar")
    a.add_argument("--limit", type=int, help="En fazla bu kadar kayit")
    a.add_argument("--yeniden", action="store_true",
                   help="Daha once dogrulanmis kayitlari da tekrar kontrol et")
    a.add_argument("--uygula", action="store_true", help="Sonuclari veritabanina yaz")
    args = a.parse_args()
    sys.exit(calistir(args.kurum, args.tumu, args.limit, args.uygula, args.yeniden))
