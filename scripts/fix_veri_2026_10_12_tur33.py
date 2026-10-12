"""Tur 33 — tur32 araştırmasında hazır olup sınır yüzünden eklenmeyen programlar (2026-10-12).

Ticaret Bakanlığı 5973 ve 10962 sayılı Kararların kalan maddeleri, Türk Eximbank ürünleri ve SGK işveren teşvikleri.
Kayıtlar: docs/olcum/2026-10-12-tur33/kayit/<slug>.json (şema: docs/olcum/2026-10-10-tur21/YENI_KAYIT_SEMASI.md).
Doğrulama ve ekleme tur32'nin aynısıdır (tur21 hattı + tur32'nin resmî alan adları ve kurum+başlık tekrar ölçütü);
yalnız klasör, yedek ve not değişir.

    python scripts/fix_veri_2026_10_12_tur33.py --dogrula   (indirir, doğrular, dogrulama.json; DB'ye dokunmaz)
    python scripts/fix_veri_2026_10_12_tur33.py             (dry-run)
    python scripts/fix_veri_2026_10_12_tur33.py --uygula    (önce yedek; tekrar çalıştırılırsa aynı kurum+başlık atlanır)
    python scripts/fix_veri_2026_10_12_tur33.py --self-test
"""
import importlib.util
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("tur32", KOK / "scripts/fix_veri_2026_10_11_kapsam_tur32.py")
tur32 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tur32)
tur21 = tur32.tur21

tur21.DIZIN = KOK / "docs/olcum/2026-10-12-tur33"
tur21.ONBELLEK = tur21.DIZIN / "kaynak"
tur21.YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur33.db.bak"
tur21.BUGUN = date(2026, 10, 12)
tur21.NOT = "Tur33 2026-10-12"


def _self_test() -> int:
    k = [("tur21 doğrulama kuralları", tur21._self_test() == 0),
         ("tur32 resmî alan adları devralındı", tur21.resmi_mi("https://ticaret.gov.tr/x")
          and tur21.resmi_mi("https://www.eximbank.gov.tr/x") and not tur21.resmi_mi("https://ihracat.com.tr/x")),
         ("kurum+başlık tekrar ölçütü", tur21.URL_TEKILLIGI is False),
         ("tur33 klasörü, yedek ve not", tur21.DIZIN.name == "2026-10-12-tur33" and tur21.YEDEK.name.endswith("tur33.db.bak")
          and tur21.NOT.startswith("Tur33"))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    tur21.main()
