"""Denetim 2 / Aşama G (Tur 4) — KOSGEB Kapasite Geliştirme ve İstihdamı Koruma kapsamı (kayıt 8, 81, 7, 142).

Kayıt 8 (KOSGEB Kapasite Geliştirme Destek Programı) ve 81 (KGF Kapasite Geliştirme Destek Paketi; KOSGEB'in
bu programına onaylı KOBİ'lere kefalet) "genel" sektörlü ve NACE kapsamsızdı. Sonuç (tarayıcı denemesi
2026-10-07): program Van'daki otele öneriliyor, metal işleme KOBİ'sinde sektör puanı alamayıp 8. sıraya
düşüyordu.

Kaynak: https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9200/kapasite-gelistirme-destek-programi
(Başvuru Şartları: "NACE koduna göre; C-İmalat, 61-Telekomünikasyon, 62-Bilgisayar programlama..., 63-Bilişim
altyapısı..., 72-Bilimsel araştırma ve geliştirme faaliyetleri sektörlerinde faaliyet gösteren işletme";
metin kayıt 8'in detay alanında da duruyor, Aşama A'da sayfa canlı teyit edildi).

Idempotent: durum_notu'nda "Denetim2-T4" varsa kayıt atlanır.

    python scripts/fix_veri_2026_10_07_denetim2_tur4.py --dry-run   (varsayılan)
    python scripts/fix_veri_2026_10_07_denetim2_tur4.py --uygula
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, TesvikNace  # noqa: E402

NOT = "Denetim2-T4 2026-10-07"
KAPASITE_URL = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9200/kapasite-gelistirme-destek-programi"
ISTIHDAM_URL = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9224/istihdami-koruma-destek-programi"
KGF_ISTIHDAM_URL = "https://www.kgf.com.tr/index.php/tr/urunlerimiz/kosgeb-destekli-kefaletler/istihdam-koruma-destek-programi"
# id -> (ad, NACE kapsamı, sektör etiketleri, kaynak)
KAYITLAR = {
    8: ("KOSGEB Kapasite Geliştirme Destek Programı", ["C", "61", "62", "63", "72"], ["imalat", "arge"], KAPASITE_URL),
    81: ("KGF Kapasite Geliştirme Destek Paketi", ["C", "61", "62", "63", "72"], ["imalat", "arge"], KAPASITE_URL),
    # "NACE kodu Kısım C – İmalat başlığı altında" (KOSGEB sayfası, 2026-10-07 Chrome ile okundu; KGF sayfası
    # "NACE Kodu; Kısım C – İmalat başlığı altında faaliyet gösteren KOBİ'ler"). Tarayıcı denemesinde çiftçiye çıkıyordu.
    7: ("KOSGEB İstihdamı Koruma Destek Programı", ["C"], ["imalat"], ISTIHDAM_URL),
    142: ("KGF İstihdam Koruma Destek Programı", ["C"], ["imalat"], KGF_ISTIHDAM_URL),
}


def uygula(db, dry_run: bool) -> int:
    n = 0
    for tid, (ad, NACE, SEKTORLER, KAYNAK_URL) in KAYITLAR.items():
        t = db.get(Tesvik, tid)
        if t is None:
            print(f"!! {tid} yok")
            continue
        if t.durum_notu and NOT in t.durum_notu:
            print(f"[{tid}] zaten işlenmiş, atlandı")
            continue
        kriter = dict(t.uygunluk_kriterleri or {})
        mevcut_nace = sorted(x.nace_prefix for x in t.nace_kayitlari if not x.haric_mi)
        print(f"[{tid}] {t.baslik[:60]}")
        print(f"    sektorler: {kriter.get('sektorler')} -> {SEKTORLER}")
        print(f"    NACE kapsamı: {mevcut_nace or '(yok)'} -> {NACE}")
        print(f"    nace_kapsam_turu: {t.nace_kapsam_turu} -> SEKTOR_KISITLI")
        if not dry_run:
            kriter["sektorler"] = SEKTORLER
            t.uygunluk_kriterleri = kriter
            for p in NACE:
                if p not in mevcut_nace:
                    db.add(TesvikNace(tesvik_id=t.id, nace_prefix=p, kaynak="elle:denetim2-t4"))
            t.nace_kapsam_turu = "SEKTOR_KISITLI"
            t.nace_kapsam_guven = 1.0
            t.nace_kapsam_kaynak = "elle"
            t.nace_kapsam_tarihi = datetime.now(timezone.utc).replace(tzinfo=None)
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: NACE kapsamı {', '.join(NACE)} ({ad}; kaynak {KAYNAK_URL})")
        n += 1
    if not dry_run:
        db.commit()
    return n


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
