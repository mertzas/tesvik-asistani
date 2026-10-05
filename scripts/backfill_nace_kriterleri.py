"""Teşvik kayıtlarını 3 ana dikeye (imalat, tarım, turizm) NACE önekiyle bağlar.

  İmalat  -> C   (bölüm 10-33)
  Tarım   -> A   (bölüm 01-03)
  Turizm  -> I   (bölüm 55-56)

Yalnızca program BAŞLIĞINDAKİ anahtar kelimelere bakılır (özet/açıklama
bilerek hariç: "imalat sanayi dahil tüm sektörler" gibi tesadüfi geçişler
yanlış kilitleme üretirdi). Eşleşmeyen kayıt "yatay" kalır: yanlış bir sektör
kilidi hak eden kullanıcıdan programı gizler, bu yüzden emin olunmayan
programa dokunulmaz.

Idempotent: mevcut (tesvik_id, nace_prefix) çifti tekrar eklenmez; elle
girilmiş kayıtlar silinmez/değiştirilmez. Otomatik eklenenler
kaynak="otomatik:..." ile işaretlidir; geri almak için --geri-al.

  python scripts/backfill_nace_kriterleri.py --dry-run   # yalnızca göster
  python scripts/backfill_nace_kriterleri.py             # uygula
  python scripts/backfill_nace_kriterleri.py --geri-al   # otomatik ekleneleri sil
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, TesvikNace, init_db  # noqa: E402
from app.urun_sektor_anahtarlari import kucult  # noqa: E402

KAYNAK_ONEKI = "otomatik:"

# (nace_prefix, kaynak etiketi, aksansız küçük harf başlıkta aranan regex)
DIKEYLER: list[tuple[str, str, re.Pattern]] = [
    ("C", "imalat_baslik",
     re.compile(r"\bimalat\w*")),
    ("A", "tarim_baslik",
     re.compile(r"\b(tarim\w*|hayvanc\w*|hububat|baklagil|meyve|sebze|sera|ortualti|sulama)\b")),
    ("I", "turizm_baslik",
     re.compile(r"\b(turizm\w*|otel\w*|konaklama)\b")),
]

_ASCII = str.maketrans("çğıöşü", "cgiosu")


def _katla(metin: str) -> str:
    return kucult(metin or "").translate(_ASCII)


def dikeyleri_bul(tesvik) -> list[tuple[str, str]]:
    """[(nace_prefix, neden)] - saf fonksiyon (testlenebilir)."""
    baslik = _katla(tesvik.baslik)
    bulunan: list[tuple[str, str]] = []
    for prefix, etiket, regex in DIKEYLER:
        m = regex.search(baslik)
        if m:
            bulunan.append((prefix, f"{etiket}:{m.group(0)}"))
    return bulunan


def calistir(db, *, dry_run: bool = False, geri_al: bool = False) -> dict:
    if geri_al:
        sorgu = db.query(TesvikNace).filter(TesvikNace.kaynak.like(f"{KAYNAK_ONEKI}%"))
        sayi = sorgu.count()
        if not dry_run:
            sorgu.delete(synchronize_session=False)
            db.commit()
        return {"silinen": sayi, "eklenen": 0, "zaten_var": 0, "satirlar": []}

    mevcut = {(r.tesvik_id, r.nace_prefix) for r in db.query(TesvikNace).all()}
    eklenen, zaten_var, satirlar = 0, 0, []
    for t in db.query(Tesvik).order_by(Tesvik.id):
        for prefix, neden in dikeyleri_bul(t):
            if (t.id, prefix) in mevcut:
                zaten_var += 1
                continue
            satirlar.append((t.id, t.baslik, prefix, neden))
            eklenen += 1
            if not dry_run:
                db.add(TesvikNace(tesvik_id=t.id, nace_prefix=prefix,
                                  kaynak=f"{KAYNAK_ONEKI}{neden}"))
                mevcut.add((t.id, prefix))
    if not dry_run:
        db.commit()
    return {"eklenen": eklenen, "zaten_var": zaten_var, "silinen": 0, "satirlar": satirlar}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="Veritabanına yazmadan göster")
    ap.add_argument("--geri-al", action="store_true", help="Otomatik eklenen bağları sil")
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        sonuc = calistir(db, dry_run=args.dry_run, geri_al=args.geri_al)
    finally:
        db.close()
    for tid, baslik, prefix, neden in sonuc["satirlar"]:
        print(f"[{tid}] {baslik} -> {prefix}  ({neden})")
    etiket = "(DRY-RUN) " if args.dry_run else ""
    print(f"\n{etiket}eklenen={sonuc['eklenen']} zaten_var={sonuc['zaten_var']} silinen={sonuc['silinen']}")


if __name__ == "__main__":
    main()
