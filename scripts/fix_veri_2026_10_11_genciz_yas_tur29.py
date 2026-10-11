"""Tur 29 — Halk Bankası Gençiz Kredisi'nin yaş sınırı (2026-10-11).

Opus kod incelemesi (2026-10-11, ikinci tur): kayıt 138 "HALK BANKASI GENÇİZ KREDİSİ PROGRAMI DESTEK PAKETİ" genç
girişimci hedef kitleli ama yapılandırılmış yaş sınırı (kurucu_yasi_max) boştu; danışman genç tanımı için varsayılan 35'i
kullandığından 32 yaşındaki, profilinde "genç girişimci" kutusu işaretli kullanıcıya "engel yok" diyordu. Kaydın
kontrol listesindeki doğrulanmış (dogrulandi=True) şart maddesinin resmî alıntısı "Sahibi 30 yaş altı olan gerçek kişi
işletmeler": yaş sınırı 29 (30'dan küçük). Ziraat Kadın ve Genç (169) bilerek dokunulmadı: kadın girişimci için yaş
sınırı yok, kurucu_yasi_max 40 yaşındaki kadın girişimciyi yanlışlıkla elerdi.

    python scripts/fix_veri_2026_10_11_genciz_yas_tur29.py             (dry-run)
    python scripts/fix_veri_2026_10_11_genciz_yas_tur29.py --uygula
    python scripts/fix_veri_2026_10_11_genciz_yas_tur29.py --self-test
"""
import argparse
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur29 2026-10-11"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur29.db.bak"
KAYIT = 138
YAS_MAX = 29
ALINTI = "Sahibi 30 yaş altı olan gerçek kişi işletmeler,"


def yeni_kriterler(kriterler: dict, kontrol_listesi: list) -> dict | None:
    """Doğrulanmış alıntılı yaş maddesi varsa ve sınır henüz yazılmamışsa yeni kriterler; değilse None."""
    if (kriterler or {}).get("kurucu_yasi_max") == YAS_MAX:
        return None
    if not any(m.get("dogrulandi") and (m.get("alinti") or "").strip() == ALINTI.strip()
               for m in kontrol_listesi or []):
        return None
    return {**(kriterler or {}), "kurucu_yasi_max": YAS_MAX}


def uygula(db, dry_run: bool = True) -> int:
    from app.models import Tesvik
    t = db.get(Tesvik, KAYIT)
    if t is None:
        raise SystemExit(f"[{KAYIT}] kayıt yok; durduruldu")
    yeni = yeni_kriterler(t.uygunluk_kriterleri, t.kontrol_listesi)
    n = 0
    if yeni is not None:
        print(f"[{KAYIT}] {t.baslik[:60]}: kurucu_yasi_max {(t.uygunluk_kriterleri or {}).get('kurucu_yasi_max')} "
              f"→ {YAS_MAX}")
        if not dry_run:
            t.uygunluk_kriterleri = yeni
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: yaş sınırı doğrulanmış şart maddesinden (\"{ALINTI}\")")
        n = 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} değişiklik")
    return n


def _self_test() -> int:
    madde = [{"tur": "sart", "metin": "Gerçek kişi işletmede sahibi 30 yaşından küçük olmalı", "alinti": ALINTI,
              "dogrulandi": True}]
    k = {"sektorler": ["genel"], "target_group_tags": ["genc_girisimci"]}
    k_ = [("sınır yazılır", yeni_kriterler(k, madde) == {**k, "kurucu_yasi_max": 29}),
          ("ikinci koşuda değişiklik yok", yeni_kriterler({**k, "kurucu_yasi_max": 29}, madde) is None),
          ("doğrulanmamış alıntıyla dokunulmaz", yeni_kriterler(k, [{**madde[0], "dogrulandi": False}]) is None),
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
