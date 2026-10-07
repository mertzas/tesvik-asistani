"""Mevcut 9903 program kayıtlarının basvuru_sartlari alanını program-özel şartlarla günceller.

İlk seed (scripts/mark_9903_yururlukten_kalkanlar.py) beş programın hepsine "EK-3 listesinde
yer alması" şartını yazmıştı; MADDE 5/1 bu şartı Kalkınma Hamlesi programları için aramaz.
Doğru şartlar seed betiğindeki PROGRAM_SARTLARI'ndan alınır (tek kaynak).

  python scripts/fix_9903_program_sartlari.py --dry-run
  python scripts/fix_9903_program_sartlari.py            # uygula (idempotent)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, init_db  # noqa: E402
from scripts.mark_9903_yururlukten_kalkanlar import YENI_PROGRAMLAR, program_sartlari  # noqa: E402


def calistir(db, *, dry_run: bool = False) -> dict:
    guncellenen, ayni, bulunamayan = [], 0, []
    for p in YENI_PROGRAMLAR:
        t = db.query(Tesvik).filter(Tesvik.baslik == p["baslik"]).first()
        if t is None:
            bulunamayan.append(p["baslik"])
            continue
        yeni = program_sartlari(p["parca"]) + p.get("ek_sartlar", [])
        if list(t.basvuru_sartlari or []) == yeni:
            ayni += 1
            continue
        guncellenen.append(p["baslik"])
        if not dry_run:
            t.basvuru_sartlari = yeni
    if not dry_run:
        db.commit()
    return {"guncellenen": guncellenen, "ayni": ayni, "bulunamayan": bulunamayan}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    init_db()
    db = SessionLocal()
    try:
        sonuc = calistir(db, dry_run=a.dry_run)
    finally:
        db.close()
    for b in sonuc["guncellenen"]:
        print(f"[{'güncellenecek' if a.dry_run else 'güncellendi'}] {b}")
    for b in sonuc["bulunamayan"]:
        print(f"[bulunamadı] {b}")
    print(f"\n{'(DRY-RUN) ' if a.dry_run else ''}güncellenen={len(sonuc['guncellenen'])} "
          f"zaten_dogru={sonuc['ayni']} bulunamayan={len(sonuc['bulunamayan'])}")


if __name__ == "__main__":
    main()
