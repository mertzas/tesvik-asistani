"""Denetim 2 / Aşama G (Tur 5) — KOSGEB Dijital Dönüşüm ve Küresel Rekabetçilik kapsamı (+ bağlı KGF paketleri),
Kapasite Geliştirme alt ölçek sınırı.

Kaynaklar (2026-10-07 Chrome ile salt okunur okundu):
  - 3   KOBİ Dijital Dönüşüm: https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9144/kobi-dijital-donusum-destek-programi
        "NACE koduna göre C-İmalat sektöründe faaliyet gösteriyor olması ... İşletme sınıfının küçük veya orta büyüklükte olması"
  - 125 KGF 2024 Dijital Dönüşüm Destek Paketi: kayıt metni "küçük ve orta ölçekli, imalatçı KOBİ'ler yararlanabilecektir"
  - 9   Küresel Rekabetçilik: https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9206/kuresel-rekabetcilik-destek-programi
        NACE sınırı YOK; şart: hızlı büyüyen + (orta-)yüksek teknoloji + 3 yıl ihracat artışı | hızlı büyüyen + 3 yıl ihracat
        ve Ar-Ge harcaması artışı | yüksek teknoloji orta ölçekli öncelikli ürün | Turcorn 100. Bu yüzden NACE değil
        ihtiyaç etiketi (ihracat, arge) verilir: program yalnızca ihracat/Ar-Ge hedefli profillere gelir.
  - 107 KGF Küresel Rekabetçilik paketi: kayıt metni "... kredi faiz desteği almaya hak kazanan KOBİ'ler" -> en çok orta ölçek
  - 8, 81 Kapasite Geliştirme: kayıt 8 metni "İşletme sınıfının küçük veya orta büyüklükte olması" -> mikro kapalı

Tarayıcı denemesi 2026-10-07: 3 çalışanlı şahıs buğday çiftçisine Dijital Dönüşüm ve Küresel Rekabetçilik öneriliyordu.
Idempotent: durum_notu'nda "Denetim2-T5" varsa kayıt atlanır.

    python scripts/fix_veri_2026_10_07_denetim2_tur5.py --dry-run   (varsayılan)
    python scripts/fix_veri_2026_10_07_denetim2_tur5.py --uygula
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, TesvikNace  # noqa: E402

NOT = "Denetim2-T5 2026-10-07"
DD_URL = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9144/kobi-dijital-donusum-destek-programi"
KR_URL = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9206/kuresel-rekabetcilik-destek-programi"
KAP_URL = "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/9200/kapasite-gelistirme-destek-programi"

# id -> (açıklama, kriter güncellemesi, eklenecek NACE, kaynak)
KAYITLAR = {
    3: ("NACE C, küçük/orta ölçek", {"sektorler": ["imalat"], "min_olcek": "kucuk", "max_olcek": "orta"}, ["C"], DD_URL),
    125: ("NACE C, küçük/orta ölçek (bağlı KGF paketi)", {"sektorler": ["imalat"], "min_olcek": "kucuk", "max_olcek": "orta"},
          ["C"], DD_URL),
    9: ("NACE sınırı yok; ihracat/Ar-Ge şartlı (ihtiyaç etiketi)", {"sektorler": ["ihracat", "arge"]}, [], KR_URL),
    107: ("ihracat/Ar-Ge şartlı, KOBİ (bağlı KGF paketi)", {"sektorler": ["ihracat", "arge"], "max_olcek": "orta"}, [], KR_URL),
    8: ("küçük/orta ölçek (mikro kapalı)", {"min_olcek": "kucuk", "max_olcek": "orta"}, [], KAP_URL),
    81: ("küçük/orta ölçek (bağlı KGF paketi)", {"min_olcek": "kucuk", "max_olcek": "orta"}, [], KAP_URL),
}


def uygula(db, dry_run: bool) -> int:
    n = 0
    for tid, (aciklama, guncelleme, nace, kaynak) in KAYITLAR.items():
        t = db.get(Tesvik, tid)
        if t is None:
            print(f"!! {tid} yok")
            continue
        if t.durum_notu and NOT in t.durum_notu:
            print(f"[{tid}] zaten işlenmiş, atlandı")
            continue
        kriter = dict(t.uygunluk_kriterleri or {})
        mevcut_nace = sorted(x.nace_prefix for x in t.nace_kayitlari if not x.haric_mi)
        print(f"[{tid}] {t.baslik[:60]}  — {aciklama}")
        for alan, deger in guncelleme.items():
            if kriter.get(alan) != deger:
                print(f"    {alan}: {kriter.get(alan)} -> {deger}")
        eklenecek = [p for p in nace if p not in mevcut_nace]
        if eklenecek:
            print(f"    NACE kapsamı: {mevcut_nace or '(yok)'} -> {sorted(set(mevcut_nace) | set(eklenecek))}")
        if not dry_run:
            kriter.update(guncelleme)
            t.uygunluk_kriterleri = kriter
            for p in eklenecek:
                db.add(TesvikNace(tesvik_id=t.id, nace_prefix=p, kaynak="elle:denetim2-t5"))
            if eklenecek:
                t.nace_kapsam_turu = "SEKTOR_KISITLI"
                t.nace_kapsam_guven = 1.0
                t.nace_kapsam_kaynak = "elle"
                t.nace_kapsam_tarihi = datetime.now(timezone.utc).replace(tzinfo=None)
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + f"{NOT}: {aciklama} (kaynak {kaynak})"
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
