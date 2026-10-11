"""Tur 25 — KGF kefalet ürünlerinde sektör/ölçek kısıtı (2026-10-11).

Uygunluk ölçümü (docs/olcum/2026-10-09-uygunluk, --profil-alanlari) ilk 10 öneride şu yanlışları gösterdi:
  * 149 Refinansman Kefalet Programı e-ticaretçiye, otele, lokantaya öneriliyordu; KGF ürün sayfası "imalat
    sektöründe faaliyet gösteren KOBİ'lerin mevcut kredilerinin refinansman yöntemi ile ..." diyor.
  * 168 Ziraat Bankası Yeşil İhracat Kredisi 400 çalışanlı büyük işletmeye öneriliyordu; sayfa "net ihracatçı
    KOBİ'lerin faaliyetlerinin desteklenmesi amaçlanmaktadır" diyor.
Alıntılar canlı sayfada (tur21 önbelleği) aranır; bulunamazsa değişiklik yapılmaz. 162 (E-İhracat genel kaydı) bilerek
dokunulmadı: Genelge şahısların bazı kalemlerden (el işi ürünlerin listelenmesi) yararlanabildiğini söylüyor.

    python scripts/fix_veri_2026_10_11_kgf_olcek_tur25.py             (dry-run)
    python scripts/fix_veri_2026_10_11_kgf_olcek_tur25.py --uygula
    python scripts/fix_veri_2026_10_11_kgf_olcek_tur25.py --self-test
"""
import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur25 2026-10-11"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur25.db.bak"
# tesvik_id -> (kriter güncellemesi, canlı sayfadaki alıntı)
DEGISIKLIK = {
    149: ({"sektorler": ["imalat"], "max_olcek": "orta"},
          "imalat sektöründe faaliyet gösteren kobi'lerin mevcut kredilerinin refinansman yöntemi ile"),
    168: ({"max_olcek": "orta"}, "net ihracatçı* kobi'lerin faaliyetlerinin desteklenmesi amaçlanmaktadır"),
}


def _tur21():
    spec = importlib.util.spec_from_file_location("tur21", KOK / "scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def uygula(db, dry_run: bool = True, getir=None) -> int:
    from app.models import Tesvik
    t21 = _tur21()
    getir = getir or t21.metin_al
    n = 0
    for tid, (kriter, alinti) in DEGISIKLIK.items():
        t = db.get(Tesvik, tid)
        if t is None:
            raise SystemExit(f"[{tid}] kayıt yok; durduruldu")
        mevcut = dict(t.uygunluk_kriterleri or {})
        degisen = {a: (mevcut.get(a), d) for a, d in kriter.items() if mevcut.get(a) != d}
        if not degisen:
            continue
        metin, hata = getir(t.kaynak_url)
        if hata or t21.norm(alinti) not in t21.norm(metin):
            print(f"[{tid}] alıntı canlı sayfada bulunamadı ({hata or 'metinde yok'}); atlandı")
            continue
        print(f"[{tid}] {t.baslik[:55]}: {degisen}")
        if not dry_run:
            t.uygunluk_kriterleri = {**mevcut, **kriter}
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: sektör/ölçek kısıtı KGF ürün sayfasından (\"{alinti}\")")
        n += 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} değişiklik")
    return n


def _self_test() -> int:
    from app.matching import uygunluk_engeli
    from app.match_adapter import company_from_profile, program_from_tesvik
    from app.match_scoring import hard_filter
    from app.models import FinancialProfile, Tesvik
    t21 = _tur21()

    def elenir(tid, profil):
        t = Tesvik(id=tid, kurum="KGF", baslik="x", ozet="o", detay="d", aktif_mi=True, kaynak_url="u",
                   uygunluk_kriterleri={"sektorler": ["genel"], **DEGISIKLIK[tid][0]})
        sebep = hard_filter(company_from_profile(profil), program_from_tesvik(t))
        return bool(sebep[0] if isinstance(sebep, tuple) else sebep) or uygunluk_engeli(t, profil) is not None

    buyuk = FinancialProfile(sektor="imalat", calisan_sayisi=400, yillik_ciro=2e9, nace_kodu="29.10")
    kucuk = FinancialProfile(sektor="imalat", calisan_sayisi=20, yillik_ciro=50e6, nace_kodu="25.62")
    k = [("normalize alıntı arama", t21.norm("İmalat  sektöründe") in t21.norm("x imalat sektöründe y")),
         ("her değişikliğin alıntısı var", all(v[1] for v in DEGISIKLIK.values())),
         ("168: büyük işletme elenir", elenir(168, buyuk)),
         ("168: küçük işletme kalır", not elenir(168, kucuk))]
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
