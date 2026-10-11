"""Tur 28 — Halkbank Genç İşi Kredisi'nin sektör kısıtı (2026-10-11).

Kurucu yaşından "genç girişimci" etiketi türetilince (app/match_adapter.profil_etiketleri) kayıt 112 "HALKBANK GENÇ İŞİ
KREDİSİ PROJESİ" tarım profillerine de önerilmeye başladı (docs/olcum/2026-10-09-uygunluk/ozet_2026_10_11_tur27.md:
Afyon genç besici, 4. sıra, "faaliyet: İmalat veya bilişim/yazılım sektöründe faaliyet" şartına göre uygun değil).
Kaydın sektörü "genel" kalmıştı; oysa kontrol listesindeki doğrulanmış (dogrulandi=True) şart maddesinin resmî
alıntısı faaliyeti imalat ve bilişim/yazılım ile sınırlıyor. Sistemdeki karşılığı: "imalat" ve "arge" (bilişim/yazılım
profilleri "arge" sektörüyle ve NACE 62/63 ile eşleşir, bkz. app/matching._ARGE_NACE).

    python scripts/fix_veri_2026_10_11_genc_isi_sektor_tur28.py             (dry-run)
    python scripts/fix_veri_2026_10_11_genc_isi_sektor_tur28.py --uygula
    python scripts/fix_veri_2026_10_11_genc_isi_sektor_tur28.py --self-test
"""
import argparse
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur28 2026-10-11"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur28.db.bak"
KAYIT = 112
SEKTORLER = ["imalat", "arge"]
ALINTI = "İmalat ve bilişim/yazılım sektörlerinde faaliyet gösteren, yeni kurulmuş veya işini büyütmek isteyen girişimlere"


def yeni_kriterler(kriterler: dict, kontrol_listesi: list) -> dict | None:
    """Doğrulanmış alıntılı şart maddesi varsa ve sektör henüz kısıtlanmamışsa yeni kriterler; değilse None."""
    if (kriterler or {}).get("sektorler") == SEKTORLER:
        return None
    if not any(m.get("dogrulandi") and m.get("alinti") == ALINTI for m in kontrol_listesi or []):
        return None
    return {**(kriterler or {}), "sektorler": SEKTORLER}


def uygula(db, dry_run: bool = True) -> int:
    from app.models import Tesvik
    t = db.get(Tesvik, KAYIT)
    if t is None:
        raise SystemExit(f"[{KAYIT}] kayıt yok; durduruldu")
    yeni = yeni_kriterler(t.uygunluk_kriterleri, t.kontrol_listesi)
    n = 0
    if yeni is not None:
        print(f"[{KAYIT}] {t.baslik[:60]}: sektorler {(t.uygunluk_kriterleri or {}).get('sektorler')} → {SEKTORLER}")
        if not dry_run:
            t.uygunluk_kriterleri = yeni
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: sektör kısıtı doğrulanmış şart maddesinden (\"{ALINTI}\")")
        n = 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} değişiklik")
    return n


def _self_test() -> int:
    madde = [{"tur": "sart", "metin": "İmalat veya bilişim/yazılım sektöründe faaliyet göstermek", "alinti": ALINTI,
              "dogrulandi": True}]
    k = {"sektorler": ["genel"], "kurucu_yasi_max": 35}
    k_ = [("genel → imalat+arge", yeni_kriterler(k, madde) == {"sektorler": SEKTORLER, "kurucu_yasi_max": 35}),
          ("ikinci koşuda değişiklik yok", yeni_kriterler({"sektorler": SEKTORLER}, madde) is None),
          ("doğrulanmamış alıntıyla dokunulmaz",
           yeni_kriterler(k, [{**madde[0], "dogrulandi": None}]) is None),
          ("alıntısız kayda dokunulmaz", yeni_kriterler(k, []) is None)]
    for ad, ok in k_:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k_)
    print(f"\nself-test: {g}/{len(k_)} geçti")
    return 0 if g == len(k_) else 1


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
    db = SessionLocal()
    try:
        uygula(db, dry_run=not a.uygula)
    finally:
        db.close()


if __name__ == "__main__":
    main()
