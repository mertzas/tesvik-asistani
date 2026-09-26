#!/usr/bin/env python3
"""
Tum veri kaynaklarini sirayla tazeler. Zamanlanmis gorev icin tek giris noktasi.

NEDEN BU DOSYA VAR
------------------
Veri tazeleme iki ayri yoldan yapiliyordu ve ikisi de eksikti:

1) app/scheduler.py (APScheduler) hal + TUIK dahil her seyi kapsiyor AMA
   yalnizca uvicorn AYAKTAYKEN tetikleniyor. Sunucu 7/24 acik olmadigi icin
   cron saati geldiginde uygulama kapaliysa is hic calismiyor.

2) run_scrapers.bat yalnizca app.scrapers.run_all'i (KOSGEB/TUBITAK/KGF/
   Hazine) cagiriyordu; TUIK makro gostergeleri ve hal fiyatlari HIC
   tazelenmiyordu. Ustelik .bat sabit bir yola cd yapiyordu; proje klasoru
   tasindiginda zamanlanmis gorev sessizce olmustu (olcum 2026-09-26:
   makro veri 77 gunluktu).

Bu script iki bosluğu da kapatir: sunucudan bagimsiz calisir, TUM kaynaklari
kapsar ve her kaynagin sonucunu tek tek raporlar.

KULLANIM
--------
    python -m scripts.tum_verileri_guncelle              # hepsi
    python -m scripts.tum_verileri_guncelle --sadece makro,hal
    python -m scripts.tum_verileri_guncelle --liste

CIKIS KODU: herhangi bir kaynak basarisiz olursa 1, hepsi basariliysa 0.
Zamanlanmis gorev basarisizligi bu sayede fark edebilir.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from typing import Callable

# Proje kokunu yola ekle - script dogrudan cift tiklanarak da calistirilabilir.
import os
_KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _KOK not in sys.path:
    sys.path.insert(0, _KOK)

from app.logging_setup import kur as gunluklemeyi_kur  # noqa: E402

logger = logging.getLogger("veri_guncelleme")


@dataclass(frozen=True)
class Is:
    anahtar: str
    baslik: str
    calistir: Callable[[], object]
    # Bu is basarisiz olursa digerleri yine denenir; kritik olan hicbiri yok.
    aciklama: str = ""


def _kosgeb() -> object:
    from app.scrapers import kosgeb
    return kosgeb.run()


def _tubitak() -> object:
    from app.scrapers import tubitak
    return tubitak.run()


def _kgf() -> object:
    from app.scrapers import kgf
    return kgf.run()


def _hazine() -> object:
    from app.scrapers import hazine_tesvik
    return hazine_tesvik.run()


def _tarim_bakanligi() -> object:
    from app.scrapers import tarim_bakanligi
    return tarim_bakanligi.run()


def _hal_urun() -> object:
    from app.scrapers import hal_urun_fiyat
    return hal_urun_fiyat.run()


def _hal_ihracat() -> object:
    from app.scrapers import hal_ihracat_fiyat
    return hal_ihracat_fiyat.run()


def _hal_cilek() -> object:
    from app.scrapers import hal_cilek_fiyat
    return hal_cilek_fiyat.run()


def _tuik_makro() -> object:
    from app.scrapers import tuik_macro
    return tuik_macro.run()


ISLER: tuple[Is, ...] = (
    # Makro en basta: butce hesaplarini besleyen en kritik kaynak ve en cok
    # bayatlayan kaynak o.
    Is("makro", "TUIK makro gostergeler + TCMB sektor bilancolari", _tuik_makro,
       "Butce onerisindeki TUFE projeksiyonu ve sektor kar oranlari."),
    Is("hal", "HKS hal urun fiyatlari", _hal_urun,
       "150+ urun gunluk toptan fiyati."),
    Is("hal_ihracat", "HKS ihracat referans fiyatlari", _hal_ihracat),
    Is("hal_cilek", "HKS cilek fiyatlari (cilek paneli)", _hal_cilek),
    Is("kosgeb", "KOSGEB destek programlari", _kosgeb),
    Is("tubitak", "TUBITAK destek programlari", _tubitak),
    Is("kgf", "KGF kefalet urunleri", _kgf),
    Is("hazine", "Hazine/Ticaret Bakanligi yatirim tesvikleri", _hazine),
    Is("tarim", "Tarim Bakanligi destekleri", _tarim_bakanligi),
)

_INDEKS = {i.anahtar: i for i in ISLER}


def calistir(secilenler: list[Is]) -> int:
    """Isleri sirayla calistirir. Donen deger: basarisiz is sayisi."""
    basarisiz: list[tuple[str, Exception]] = []
    basarili: list[tuple[str, object, float]] = []

    logger.info("%d veri kaynagi tazelenecek", len(secilenler))
    for i, is_ in enumerate(secilenler, 1):
        logger.info("[%d/%d] %s basliyor", i, len(secilenler), is_.baslik)
        basla = time.monotonic()
        try:
            sonuc = is_.calistir()
        except Exception as e:
            # Bir kaynagin cokmesi digerlerini engellememeli: kurum siteleri
            # sik sik yapi degistiriyor ve tek bir scraper yuzunden butun
            # tazeleme turunu kaybetmek en kotu sonuc olur.
            sure = time.monotonic() - basla
            logger.error("[%s] BASARISIZ (%.1fs): %s: %s",
                         is_.anahtar, sure, type(e).__name__, e, exc_info=True)
            basarisiz.append((is_.anahtar, e))
        else:
            sure = time.monotonic() - basla
            logger.info("[%s] tamam (%.1fs): %s", is_.anahtar, sure, sonuc)
            basarili.append((is_.anahtar, sonuc, sure))

    logger.info("=" * 60)
    logger.info("OZET: %d basarili, %d basarisiz", len(basarili), len(basarisiz))
    for anahtar, sonuc, sure in basarili:
        logger.info("  OK   %-14s %s (%.1fs)", anahtar, sonuc, sure)
    for anahtar, hata in basarisiz:
        logger.info("  HATA %-14s %s: %s", anahtar, type(hata).__name__, hata)

    _tazelik_ozeti()
    return len(basarisiz)


def _tazelik_ozeti() -> None:
    """Tazeleme sonrasi durumu yaz - is 'basarili' donse de veri gercekten
    guncellendi mi sorusunun cevabi bu. (Scraper 0 kayit ekleyip basariyla
    donebilir; o durumda kaynak hala bayat kalir.)"""
    try:
        from app.models import SessionLocal
        from app.veri_tazeligi import tazelik_raporu, genel_durum
        db = SessionLocal()
        try:
            rapor = tazelik_raporu(db)
            logger.info("-" * 60)
            logger.info("TAZELEME SONRASI VERI DURUMU: %s", genel_durum(rapor))
            for t in rapor:
                logger.info("  %-9s %-38s %s gun (n=%s)",
                            t.durum, t.baslik, t.yas_gun, t.kayit_sayisi)
        finally:
            db.close()
    except Exception as e:
        logger.warning("Tazelik ozeti alinamadi: %s: %s", type(e).__name__, e)


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(
        description="Tum veri kaynaklarini tazeler.")
    ayristirici.add_argument(
        "--sadece",
        help="Virgulle ayrilmis kaynak anahtarlari (bkz. --liste).")
    ayristirici.add_argument(
        "--liste", action="store_true", help="Kaynaklari listeler ve cikar.")
    ayristirici.add_argument(
        "--log-seviyesi", default="INFO", help="INFO (varsayilan) / DEBUG.")
    args = ayristirici.parse_args(argv)

    if args.liste:
        for i in ISLER:
            print(f"{i.anahtar:14} {i.baslik}")
            if i.aciklama:
                print(f"{'':14} {i.aciklama}")
        return 0

    gunluklemeyi_kur(args.log_seviyesi)

    if args.sadece:
        anahtarlar = [a.strip() for a in args.sadece.split(",") if a.strip()]
        bilinmeyen = [a for a in anahtarlar if a not in _INDEKS]
        if bilinmeyen:
            logger.error("Bilinmeyen kaynak(lar): %s. Gecerli: %s",
                         ", ".join(bilinmeyen), ", ".join(_INDEKS))
            return 2
        secilenler = [_INDEKS[a] for a in anahtarlar]
    else:
        secilenler = list(ISLER)

    return 1 if calistir(secilenler) else 0


if __name__ == "__main__":
    sys.exit(main())
