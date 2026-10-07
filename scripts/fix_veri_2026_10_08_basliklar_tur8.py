"""Denetim 2 / Tur 8 — 160 ve 161 kayıtlarının başlık/özet/ayrıntı metni: "(Mazot-Gübre)" 2026'da geçersiz.

2026 Bitkisel Üretim Destekleme Birim Fiyatları'nda mazot ve gübre desteği "temel destek" adıyla tek kalemde birleşti
(app/tarim_destek_2026.py, KAYNAK_URL: BUGEM 2026 PDF; tutar alanları tur 7'de düzeltildi). Eski ayrıntı metni ayrıca
"meyve-sebze desteği genelde hububattan yüksektir" diyordu; 2026 tablosunda tersi: meyve-sebze 310 TL/da, hububat ve
baklagil 620–806 TL/da (temel + planlı üretim).

Kazıyıcı (app/scrapers/tarim_bakanligi.py) kaydı başlık + kurum ile tanır: tohum metinleri AYNI committe güncellenir,
yoksa bir sonraki kazıma eski başlıklı kaydı yeniden ekler. Kontrol: eski başlık birebir eşleşmezse kayıt atlanır.
Idempotent: durum_notu'nda "Denetim2-T8" varsa atlanır.

    python scripts/fix_veri_2026_10_08_basliklar_tur8.py --dry-run   (varsayılan)
    python scripts/fix_veri_2026_10_08_basliklar_tur8.py --uygula
    python scripts/fix_veri_2026_10_08_basliklar_tur8.py --self-test
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik  # noqa: E402
from app.scrapers.tarim_bakanligi import TARIM_BAKANLIGI_DESTEKLERI  # noqa: E402
from app.tarim_destek_2026 import KAYNAK_URL  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Denetim2-T8 2026-10-08"
ESKI = {160: "Hububat ve Baklagil Üretim Destekleri (Mazot-Gübre)",
        161: "Meyve-Sebze Üretim Destekleri (Mazot-Gübre)"}
# Yeni metinler kazıyıcı tohumundan okunur: veritabanı ile tohum tek kaynaktan eşitlenir.
YENI_BASLIK = {160: "Hububat ve Baklagil Üretim Destekleri (Temel Destek + Planlı Üretim)",
               161: "Meyve-Sebze Üretim Destekleri (Temel Destek)"}


def tohum(tid: int) -> dict:
    return next(d for d in TARIM_BAKANLIGI_DESTEKLERI if d["baslik"] == YENI_BASLIK[tid])


def uygula(db, dry_run: bool) -> tuple[int, int]:
    n = atlanan = 0
    for tid, eski in ESKI.items():
        t = db.get(Tesvik, tid)
        if t is None:
            print(f"!! {tid} yok")
            atlanan += 1
            continue
        if t.durum_notu and NOT in t.durum_notu:
            print(f"[{tid}] zaten işlenmiş, atlandı")
            continue
        if t.baslik != eski:
            print(f"!! [{tid}] başlık beklenenden farklı ({t.baslik!r}); atlandı")
            atlanan += 1
            continue
        yeni = tohum(tid)
        print(f"[{tid}] başlık: {t.baslik!r}\n      -> {yeni['baslik']!r}")
        print(f"      özet:   {t.ozet[:70]!r}...\n      -> {yeni['ozet'][:110]!r}...")
        print(f"      ayrıntı: {len(t.detay or '')} -> {len(yeni['detay'])} karakter")
        if not dry_run:
            t.baslik, t.ozet, t.detay = yeni["baslik"], yeni["ozet"], yeni["detay"]
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: 2026'da mazot+gübre 'temel destek' adıyla birleşti; başlık/özet/ayrıntı güncellendi "
                f"(kaynak {KAYNAK_URL})")
        n += 1
    if not dry_run:
        db.commit()
    return n, atlanan


def _self_test() -> int:
    kontroller = [
        ("tohumda iki yeni başlık var", all(any(d["baslik"] == b for d in TARIM_BAKANLIGI_DESTEKLERI)
                                            for b in YENI_BASLIK.values())),
        ("tohumda eski başlık kalmadı", not any(d["baslik"] in ESKI.values() for d in TARIM_BAKANLIGI_DESTEKLERI)),
        ("yeni metinlerde 'Mazot-Gübre' başlık kalıbı yok", all("Mazot-Gübre" not in tohum(i)["baslik"] for i in ESKI)),
        ("ayrıntı birleşmeyi açıklıyor", all("temel destek" in tohum(i)["detay"] for i in ESKI)),
        ("yanlış karşılaştırma ('hububata göre daha yüksek') kalmadı",
         "hububata göre daha yüksek" not in tohum(161)["detay"]),
    ]
    for ad, ok in kontroller:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in kontroller)
    print(f"\nself-test: {gecen}/{len(kontroller)} geçti")
    return 0 if gecen == len(kontroller) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(_self_test())
    db = SessionLocal()
    try:
        n, atlanan = uygula(db, dry_run=not a.uygula)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} kayıt, {atlanan} atlandı")
    finally:
        db.close()
