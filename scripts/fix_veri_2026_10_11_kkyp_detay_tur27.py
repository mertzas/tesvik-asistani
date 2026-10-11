"""Tur 27 — Kırsal Kalkınma Yatırım Programı (kayıt 78) açıklamasındaki eski metin (2026-10-11).

Bağımsız uzman değerlendirmesi (docs/olcum/2026-10-11-yerel-danisman/degerlendirme4_A.json, senaryo 1): kayıt 78
2026-10-07'de KKYP olarak yeniden yazılmıştı (özet: "Bireysel traktör/makine alımı bu programda desteklenmez"), ama
`detay` alanında eski makineleştirme metni kalmıştı ("çiftçilerin modern tarım makineleri (traktör, harvestor ...)
satın almasında finansal destek sağlar"). İki alan birbirini yalanlıyordu; "traktör destekleniyor mu" sorusuna
danışman yanlış cümleyi alıntılayabilirdi. Yeni bilgi eklenmez: `detay`, kaydın kaynaklı özetiyle (Resmî Gazete
03.04.2026 KKYP Tebliği'ne dayanan yeniden yazım) aynı olur.

    python scripts/fix_veri_2026_10_11_kkyp_detay_tur27.py             (dry-run)
    python scripts/fix_veri_2026_10_11_kkyp_detay_tur27.py --uygula
    python scripts/fix_veri_2026_10_11_kkyp_detay_tur27.py --self-test
"""
import argparse
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur27 2026-10-11"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur27.db.bak"
KAYIT = 78
ESKI_BASI = "Tarım ve Orman Bakanlığı tarafından sağlanan makineleştirme destekleri"
OZET_SARTI = "Bireysel traktör/makine alımı bu programda desteklenmez."


def yeni_detay(ozet: str, detay: str) -> str | None:
    """Eski makineleştirme metni duruyorsa ve özet KKYP yeniden yazımıysa yeni detay; değilse None."""
    if not (detay or "").startswith(ESKI_BASI) or OZET_SARTI not in (ozet or ""):
        return None
    return ozet


def uygula(db, dry_run: bool = True) -> int:
    from app.models import Tesvik
    t = db.get(Tesvik, KAYIT)
    if t is None:
        raise SystemExit(f"[{KAYIT}] kayıt yok; durduruldu")
    yeni = yeni_detay(t.ozet, t.detay)
    n = 0
    if yeni is not None:
        print(f"[{KAYIT}] {t.baslik[:60]}: detay eski makineleştirme metni → kaynaklı KKYP özeti")
        if not dry_run:
            t.detay = yeni
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: detay alanındaki eski makineleştirme metni kaldırıldı (özetle çelişiyordu)")
        n = 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} değişiklik")
    return n


def _self_test() -> int:
    ozet = f"KKYP: işleme, paketleme yatırımlarına hibe. {OZET_SARTI}"
    eski = f"{ESKI_BASI}, çiftçilerin modern tarım makineleri (traktör) satın almasında finansal destek sağlar."
    k = [("eski metin özetle değişir", yeni_detay(ozet, eski) == ozet),
         ("ikinci koşuda değişiklik yok", yeni_detay(ozet, ozet) is None),
         ("özet KKYP değilse dokunulmaz", yeni_detay("makine desteği", eski) is None),
         ("başka detay dokunulmaz", yeni_detay(ozet, "Tebliğ ayrıntıları") is None)]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(_self_test())
    from app.models import SessionLocal, settings
    if a.uygula and not YEDEK.exists():
        shutil.copy2(Path(settings.DATABASE_URL.replace("sqlite:///", "")), YEDEK)
        print(f"yedek: {YEDEK}")
    uygula(SessionLocal(), dry_run=not a.uygula)


if __name__ == "__main__":
    main()
