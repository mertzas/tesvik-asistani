"""Denetim 2 / Aşama G (Tur 6) — YÖNDE (kayıt 5) eski şart cümlesi.

Kayıt 5'in detay metninde "NACE koduna göre C-İmalat sektöründe faaliyet gösteriyor olması, İşletme sınıfının
küçük veya orta büyüklükte olması" cümlesi duruyordu (önceki kazıma). KOSGEB'in canlı sayfası (2026-10-07, Chrome ile
salt okunur okundu) bu şartı ARTIK İÇERMİYOR; başvuru şartları yalnızca: TTK'da tanımlı gerçek veya tüzel kişi statüsü
ve KOSGEB Veri Tabanında kayıtlı, aktif, İşletme Beyanı güncel olmak. SSS: "Türk Ticaret Kanunu'na göre gerçek veya
tüzel kişi statüsündeki işletmeler yararlanabilir"; %100 geri ödemesiz, program üst limiti toplam 700.000 TL, 36 ay.

Bu yüzden kapsam DARALTILMAZ (genel kalır); yalnızca eski cümle metinden çıkarılır ki danışman "yalnızca imalat" demesin.
Kaynak: https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9165/yonde-yonderlik-ve-degerlendirme-destek-programi
Idempotent: durum_notu'nda "Denetim2-T6" varsa atlanır.

    python scripts/fix_veri_2026_10_07_denetim2_tur6.py --dry-run   (varsayılan)
    python scripts/fix_veri_2026_10_07_denetim2_tur6.py --uygula
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik  # noqa: E402

NOT = "Denetim2-T6 2026-10-07"
KAYNAK = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9165/yonde-yonderlik-ve-degerlendirme-destek-programi"
# Metinde maddeler satır sonuyla ayrılmış; boşluk/satır sonuna duyarsız eşleşir.
ESKI = re.compile(r"NACE koduna göre C-İmalat sektöründe faaliyet gösteriyor olması,\s*"
                  r"İşletme sınıfının küçük veya orta büyüklükte olması,\s*")
SURE = "Program süresi 36 ay"


def uygula(db, dry_run: bool) -> int:
    t = db.get(Tesvik, 5)
    if t is None:
        print("!! 5 yok")
        return 0
    if t.durum_notu and NOT in t.durum_notu:
        print("[5] zaten işlenmiş, atlandı")
        return 0
    adet = len(ESKI.findall(t.detay or ""))
    if adet == 0:
        raise SystemExit("HATA: eski şart cümlesi detayda bulunamadı")
    print(f"[5] {t.baslik}")
    print(f"    detay: eski şart cümlesi {adet} yerde çıkarılıyor ('NACE koduna göre C-İmalat ... küçük veya orta büyüklükte olması')")
    print(f"    destek_verilme_suresi: {t.destek_verilme_suresi!r} -> {SURE!r}")
    print("    uygunluk_kriterleri (değişmez):", t.uygunluk_kriterleri)
    if not dry_run:
        t.detay = ESKI.sub("", t.detay)
        t.destek_verilme_suresi = SURE
        t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
            f"{NOT}: canlı sayfada imalat/ölçek şartı yok (yalnızca TTK statüsü + KOSGEB kaydı); eski cümle çıkarıldı, "
            f"kapsam genel bırakıldı ({KAYNAK})")
        db.commit()
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    db = SessionLocal()
    try:
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {uygula(db, dry_run=not a.uygula)} kayıt")
    finally:
        db.close()
