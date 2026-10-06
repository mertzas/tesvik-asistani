"""Başlığında ölçek şartı AÇIKÇA geçen programlara `max_olcek` yazar.

  mikro -> "mikro işletmeler" | kucuk -> "küçük işletme" |
  orta  -> başlıkta "KOBİ" (ama "KOBİ dışı" geçmeyen): KOBİ vasfı şart

Yalnızca BAŞLIĞA bakılır; emin olunmayan programa (ör. "KOBİ ve KOBİ dışı" kabul
eden KGF paketleri, KOSGEB'in girişimci programları) dokunulmaz: yanlış bir ölçek
şartı hak eden işletmeden programı gizler. Eşikler app/kobi.py'dedir.

  python scripts/backfill_olcek_kriterleri.py --dry-run   # yalnızca göster
  python scripts/backfill_olcek_kriterleri.py             # uygula (idempotent)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, init_db  # noqa: E402
from app.urun_sektor_anahtarlari import kucult  # noqa: E402

_ASCII = str.maketrans("çğıöşü", "cgiosu")
_MIKRO = re.compile(r"\bmikro isletme")
_KUCUK = re.compile(r"\bkucuk isletme")
_KOBI = re.compile(r"\bkobi\b|\bkobi[''`]?(?:ler|nin|lerin)\b")
_KOBI_DISI = re.compile(r"kobi\s+disi")


def _katla(m: str) -> str:
    return kucult(m or "").translate(_ASCII)


def olcek_bul(baslik: str) -> tuple[str, str] | None:
    """(max_olcek, neden) ya da None. Saf fonksiyon."""
    b = _katla(baslik)
    if _MIKRO.search(b):
        return "mikro", "baslik:mikro isletme"
    if _KUCUK.search(b):
        return "kucuk", "baslik:kucuk isletme"
    if _KOBI.search(b) and not _KOBI_DISI.search(b):
        return "orta", "baslik:kobi"
    return None


def calistir(db, *, dry_run: bool = False) -> dict:
    degisen, zaten, satirlar = 0, 0, []
    for t in db.query(Tesvik).order_by(Tesvik.id):
        sonuc = olcek_bul(t.baslik)
        if sonuc is None:
            continue
        olcek, neden = sonuc
        kriter = dict(t.uygunluk_kriterleri or {})
        if kriter.get("max_olcek") == olcek:
            zaten += 1
            continue
        satirlar.append((t.id, t.baslik, olcek, neden))
        degisen += 1
        if not dry_run:
            kriter["max_olcek"] = olcek
            t.uygunluk_kriterleri = kriter
    if not dry_run:
        db.commit()
    return {"degisen": degisen, "zaten_var": zaten, "satirlar": satirlar}


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
    for tid, baslik, olcek, neden in sonuc["satirlar"]:
        print(f"[{tid}] {baslik} -> {olcek}  ({neden})")
    print(f"\n{'(DRY-RUN) ' if a.dry_run else ''}degisen={sonuc['degisen']} zaten_var={sonuc['zaten_var']}")


if __name__ == "__main__":
    main()
