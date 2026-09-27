#!/usr/bin/env python3
"""
Teşvik kayıtlarının kaynak linklerinin çalışıp çalışmadığını denetler.

NEDEN
-----
Kaynak linki, kullanıcının bilgiyi teyit edebildiği tek yer. AI danışman da
"kurumun resmî sayfasından teyit edin" derken bu linki veriyor. Link ölüyse
kullanıcı hiçbir şeyi doğrulayamaz ve uygulamaya güveni kırılır.

Ölçüm (2026-09-27): aktiflik doğrulaması sırasında 5 KGF kaydının linkinin
302 ile /index.php?option=com_content&view=article&id=1 adresine gittiği ve
oradan döngüye girdiği görüldü - KGF o sayfaları kaldırmış. Bu kayıtların
linkleri kullanıcıya kırık bir sayfa gösteriyor.

Bu script durumu ölçer ve --uygula ile ölü linkleri durum_notu'na yazar;
böylece AI danışman kullanıcıyı çalışmayan bir adrese yönlendirdiğini
söyleyebilir. Link SİLİNMEZ - hangi adresin bozulduğunu bilmek değerli.

Kullanım:
    python -m scripts.check_kaynak_linkleri                 # rapor
    python -m scripts.check_kaynak_linkleri --kurum KGF
    python -m scripts.check_kaynak_linkleri --uygula
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from urllib.parse import urlparse

_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from app.logging_setup import kur as gunluklemeyi_kur  # noqa: E402
from app.models import SessionLocal, Tesvik  # noqa: E402

logger = logging.getLogger("link_kontrol")

BEKLEME_SN = 1.0
ZAMAN_ASIMI = 20
BASLIK = {"User-Agent": "Mozilla/5.0 (tesvik-asistani link denetleyici)"}
OLU_NOT_ONEKI = "⚠️ KAYNAK LİNKİ ÇALIŞMIYOR"


@dataclass
class LinkDurumu:
    baslik: str
    kurum: str
    url: str
    durum: str        # "saglam" | "olu" | "yonlendirildi" | "hata"
    ayrinti: str


def _oturum() -> requests.Session:
    o = requests.Session()
    o.headers.update(BASLIK)
    return o


def _ayni_sayfa(a: str, b: str) -> bool:
    """Iki adres, yalnizca kanonik farklarla ayni sayfayi mi gosteriyor?

    Kanonik kabul edilenler: sema (http/https), basindaki "www.", sondaki
    egik cizgi ve buyuk-kucuk harfli alan adi. YOL farkli ise ayni sayfa
    DEGILDIR - kurum icerigi tasimis olabilir.
    """
    def parcala(u: str):
        p = urlparse(u)
        alan = p.netloc.lower()
        if alan.startswith("www."):
            alan = alan[4:]
        yol = p.path.rstrip("/") or "/"
        return alan, yol, p.query
    return parcala(a) == parcala(b)


def _kontrol(oturum: requests.Session, url: str) -> tuple[str, str]:
    """(durum, ayrinti) doner."""
    try:
        # Once yonlendirmeyi TAKIP ETMEDEN bak: dongu tespiti icin.
        r = oturum.get(url, timeout=ZAMAN_ASIMI, allow_redirects=False)
        if r.is_redirect or r.is_permanent_redirect:
            hedef = r.headers.get("Location", "")
            try:
                r2 = oturum.get(url, timeout=ZAMAN_ASIMI, allow_redirects=True)
            except requests.TooManyRedirects:
                return ("olu", f"HTTP {r.status_code} -> {hedef} (yönlendirme döngüsü)")
            if r2.status_code >= 400:
                return ("olu", f"HTTP {r.status_code} -> {hedef} -> {r2.status_code}")
            # Kanonik yonlendirmeler (www ekleme/cikarma, sondaki egik cizgi,
            # http->https) ZARARSIZ; bunlari "guncellenmeli" diye bildirmek
            # raporu kullanissiz kiliyordu. Olcum (2026-09-27): 67 "yonlendirme"
            # uyarisinin TAMAMI www.tubitak.gov.tr -> tubitak.gov.tr idi, yani
            # tek bir gercek sorun yoktu. Yalnizca YOL degistiyse bildiriyoruz.
            if _ayni_sayfa(url, r2.url):
                return ("saglam", f"HTTP {r.status_code} (kanonik yönlendirme)")
            return ("yonlendirildi", f"HTTP {r.status_code} -> {r2.url}")
        if r.status_code >= 400:
            return ("olu", f"HTTP {r.status_code}")
        return ("saglam", f"HTTP {r.status_code}")
    except requests.TooManyRedirects:
        return ("olu", "yönlendirme döngüsü (30+ adım)")
    except Exception as e:
        return ("hata", f"{type(e).__name__}: {e}"[:110])


def calistir(kurum: str | None, uygula: bool, limit: int | None) -> int:
    gunluklemeyi_kur("INFO")
    db = SessionLocal()
    try:
        q = db.query(Tesvik)
        if kurum:
            q = q.filter(Tesvik.kurum == kurum)
        kayitlar = q.all()
        urlsiz = [t for t in kayitlar if not (t.kaynak_url or "").startswith("http")]
        kayitlar = [t for t in kayitlar if (t.kaynak_url or "").startswith("http")]
        if limit:
            kayitlar = kayitlar[:limit]

        print(f"{len(kayitlar)} link kontrol edilecek "
              f"({len(urlsiz)} kayitta kaynak linki YOK)")
        if urlsiz:
            print("\nKAYNAK LINKI OLMAYAN KAYITLAR:")
            for t in urlsiz:
                print(f"  {(t.kurum or '')[:16]:17} {(t.baslik or '')[:54]}")

        oturum = _oturum()
        simdi = datetime.now(timezone.utc)
        sonuclar: list[LinkDurumu] = []
        for i, t in enumerate(kayitlar, 1):
            durum, ayrinti = _kontrol(oturum, t.kaynak_url)
            sonuclar.append(LinkDurumu(t.baslik or "", t.kurum or "",
                                       t.kaynak_url, durum, ayrinti))
            if durum != "saglam":
                print(f"[{i}/{len(kayitlar)}] {durum.upper():14} "
                      f"{(t.baslik or '')[:44]:46} {ayrinti[:52]}")
            if uygula and durum == "olu":
                mevcut = (t.durum_notu or "").strip()
                not_ = (f"{OLU_NOT_ONEKI} ({ayrinti}, kontrol: "
                        f"{simdi.date().isoformat()}). Bilgiyi kurumun kendi "
                        "sitesinden arayarak teyit edin.")
                if OLU_NOT_ONEKI not in mevcut:
                    t.durum_notu = (not_ + " " + mevcut).strip()
                    t.guncelleme_tarihi = simdi
            time.sleep(BEKLEME_SN)

        if uygula:
            db.commit()

        ozet = Counter(s.durum for s in sonuclar)
        print("\n" + "=" * 62)
        print("OZET:", dict(ozet))
        olu = [s for s in sonuclar if s.durum == "olu"]
        if olu:
            print(f"\nOLU LINKLER ({len(olu)}):")
            for s in olu:
                print(f"  {s.kurum[:14]:15} {s.baslik[:44]:46} {s.ayrinti[:46]}")
        yon = [s for s in sonuclar if s.durum == "yonlendirildi"]
        if yon:
            print(f"\nYONLENDIRILEN LINKLER ({len(yon)}) - adres guncellenmeli:")
            for s in yon[:15]:
                print(f"  {s.baslik[:44]:46} {s.ayrinti[:60]}")
        print(f"\n{'YAZILDI' if uygula else 'RAPOR (yazilmadi)'}: "
              f"{len(olu)} olu link isaretlen{'di' if uygula else 'ecek'}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Kaynak linki denetleyici.")
    a.add_argument("--kurum")
    a.add_argument("--limit", type=int)
    a.add_argument("--uygula", action="store_true")
    args = a.parse_args()
    sys.exit(calistir(args.kurum, args.uygula, args.limit))
