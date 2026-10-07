"""Aşama 1 veri bütünlüğü denetiminde (2026-10-07) ölçülen tutarsızlıkları düzeltir.

Bulgular (gerçek veritabanı, 184 kayıt):
  1. 8 kaydın uygunluk_kriterleri.sektorler alanı BOŞ (KGF 168-173, TÜBİTAK 175-176).
     matching.esles() ve rag._sektor_kayitlari() etiketi boş kaydı hiç görmez; bu
     programlar hiçbir profile eşleşmiyordu. Kurum kuralı (backfill_sektorler_genel_kurumlar
     ile aynı): KGF -> genel, TÜBİTAK -> arge+genel; 168 ihracat kredisi -> ihracat da.
  2. 44 (TÜBİTAK 1507) ve 163 (Pazara Girişte Dijital): tutar/oran var, tutar_niteligi yok;
     ikisi de geri ödemesiz (hibe) -> toplam tahmini desteğe doğru girsin.
  3. 183/184 (kapalı KOSGEB kayıtları): nitelik hibe ama tutar formülü yok; resmî sayfa
     tablosundaki limitler formül alanına yazılır (bilgi amaçlı, program kapalı).
  4. 164-167 (2012/3305 eski Hazine kayıtları, kapalı): kaynak_url boş; link denetimi ve
     danışman "Kaynak:" satırı için durum_notu'ndaki R.G. adresi + program parçası yazılır.
  5. Tarım Bakanlığı'nın BUGEM 2026 birim fiyat tablosuna dayanan 4 kaydı (dekar bazlı
     tutar backfill'i yapılmış olanlar) aktif_mi=None; tablo 2026 üretim yılı için resmî
     kaynaktan doğrulandığından aktif_mi=True + durum_notu.

  python scripts/fix_veri_butunlugu_2026_10.py --dry-run
  python scripts/fix_veri_butunlugu_2026_10.py            # idempotent
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, init_db  # noqa: E402
from app.tarim_destek_2026 import KAYNAK as BUGEM_KAYNAK, KAYNAK_URL as BUGEM_URL  # noqa: E402

DOGRULAMA = "2026-10-07"
_URL = re.compile(r"https?://\S+")


def _slug(baslik: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", baslik.lower().translate(str.maketrans("çğıöşü", "cgiosu"))).strip("-")


def _degis(t, alan, yeni, degisimler):
    eski = getattr(t, alan)
    if eski != yeni:
        degisimler.append((t.id, alan, eski if not isinstance(eski, str) else eski[:40], yeni if not isinstance(yeni, str) else yeni[:40]))
        setattr(t, alan, yeni)


def calistir(db, *, dry_run: bool = False) -> list[tuple]:
    degisimler: list[tuple] = []
    for t in db.query(Tesvik).order_by(Tesvik.id):
        k = dict(t.uygunluk_kriterleri or {})
        yeni_k = dict(k)

        # 1) sektorler boş
        if not k.get("sektorler"):
            if t.kurum == "KGF":
                yeni_k["sektorler"] = ["ihracat", "genel"] if "İHRACAT" in (t.baslik or "").upper() else ["genel"]
            elif t.kurum in ("TUBITAK", "TÜBİTAK"):
                yeni_k["sektorler"] = ["arge", "genel"]
            elif t.kurum == "KOSGEB":
                yeni_k["sektorler"] = ["genel"]
            if yeni_k.get("sektorler"):
                yeni_k["sektor_gerekcesi"] = f"Kurum kuralıyla etiketlendi (veri bütünlüğü düzeltmesi {DOGRULAMA})"

        # 2) tutar var, nitelik yok -> hibe (yalnızca formül/metin 'hibe' veya 'geri ödemesiz' diyorsa)
        if (t.tutari_max or t.tutari_hesaplama_formulu) and not k.get("tutar_niteligi"):
            formul = (t.tutari_hesaplama_formulu or "").lower()
            metin = f"{formul} {(t.detay or '').lower()}"
            # "hisse karşılığı yatırım" (BiGG 1512) hibe değildir; nitelik elle kararlaştırılmalı.
            if "hisse" not in formul and ("hibe" in metin or "geri ödemesiz" in metin or "%" in formul):
                yeni_k["tutar_niteligi"] = "hibe"

        if yeni_k != k:
            degisimler.append((t.id, "uygunluk_kriterleri", {x: k.get(x) for x in yeni_k if k.get(x) != yeni_k[x]},
                               {x: yeni_k[x] for x in yeni_k if k.get(x) != yeni_k[x]}))
            t.uygunluk_kriterleri = yeni_k

        # 3) kapalı KOSGEB kayıtları: formül
        if t.aktif_mi is False and t.kurum == "KOSGEB" and not t.tutari_hesaplama_formulu:
            if "Ar-Ge, Ür-Ge" in (t.baslik or ""):
                _degis(t, "tutari_hesaplama_formulu",
                       "Kapalı program. Resmî sayfa tablosu: makine-teçhizat/yazılım/hizmet geri ödemesiz 200.000 TL "
                       "(%75, yerli malı +%15) ve geri ödemeli 300.000 TL (%75); nitelikli personel 300.000 TL (%100); "
                       "sınai mülkiyet 100.000 TL (%75); test/analiz/belgelendirme 100.000 TL (%75)", degisimler)
            elif "KOBİGEL" in (t.baslik or ""):
                _degis(t, "tutari_hesaplama_formulu",
                       "Kapalı program. Resmî sayfa: proje başına azami 2.000.000 TL; personel dışı giderlerde en az "
                       "%60, makine/yazılım/hizmetin %70'i geri ödemeli, personel %100 geri ödemesiz", degisimler)

        # 4) kaynak_url boş (eski Hazine kayıtları)
        if not t.kaynak_url:
            m = _URL.search(t.durum_notu or "")
            if m:
                _degis(t, "kaynak_url", f"{m.group(0).rstrip('.,;)')}#{_slug(t.baslik or str(t.id))}", degisimler)

        # 5) BUGEM 2026 tablosuna dayanan tarım kayıtları
        if (t.kurum == "Tarım Bakanlığı" and t.aktif_mi is None and t.tutari_hesaplama_kriteri == "dekar"
                and t.tutari_max):
            _degis(t, "aktif_mi", True, degisimler)
            _degis(t, "durum_notu", f"DURUM: Doğrulanmış, güncel/aktif program. 2026 üretim yılı birim fiyatları "
                                    f"resmî tablodan doğrulandı ({BUGEM_KAYNAK}; {BUGEM_URL}); teyit {DOGRULAMA}.",
                   degisimler)
    if not dry_run:
        db.commit()
    else:
        db.rollback()
    return degisimler


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    init_db()
    db = SessionLocal()
    try:
        d = calistir(db, dry_run=a.dry_run)
    finally:
        db.close()
    for tid, alan, eski, yeni in d:
        print(f"[{tid}] {alan}: {eski!r} -> {yeni!r}")
    print(f"\n{'(DRY-RUN) ' if a.dry_run else ''}degisiklik={len(d)}")


if __name__ == "__main__":
    main()
