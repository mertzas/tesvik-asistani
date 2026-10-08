"""Tur 18 — 1501 (kayıt 34) tutar formülü çelişkisi ve eskimiş başvuru süresi (2026-10-08).

Bulgu (şablon taslağı gözden geçirilirken): tesvil_tutari "ilk 5 proje %75 (en fazla 20 M TL/proje)" derken
tutari_hesaplama_formulu "çağrı duyurusunda aksi belirtilmedikçe üst limit yok" diyordu. Program sayfası ve 2026-2
çağrı metni (8. madde): "Proje başına TÜBİTAK katkısı 20 milyon TL ile sınırlandırılmıştır". Tüm aktif kayıtlar aynı
türden çelişki için tarandı (formülde "limit yok" + tanımlı limit; tutar/formül yüzdeleri uyuşmazlığı): yalnız 34.
basvuru_suresi "genellikle Ocak-Şubat ve Temmuz-Ağustos" diyordu; güncel çağrı takvimiyle değiştirilir. Çağrı metnindeki
"kuruluş başına en fazla 2 proje önerisi" şartı eklenir. Eski metinler durum_notu'na yazılır.
Kanıt: docs/olcum/2026-10-08-tur18/kanit.json.

    python scripts/fix_veri_2026_10_08_1501_tur18.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_08_1501_tur18.py --uygula
    python scripts/fix_veri_2026_10_08_1501_tur18.py --self-test
"""
import argparse
import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from app.models import SessionLocal, Tesvik  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur18 2026-10-08"
KANIT = KOK / "docs/olcum/2026-10-08-tur18/kanit.json"
FORMUL = ("Destek = uygun proje giderleri × %75 (firmanın desteklenen ilk 5 projesi) ya da × %60 (6. ve sonraki "
          "projeler); proje başına TÜBİTAK katkısı en fazla 20 milyon TL. Desteklenen giderler: personel; seyahat; alet, "
          "teçhizat, yazılım ve yayın alımı; malzeme ve sarf; yurt içi/yurt dışı danışmanlık ve diğer hizmet alımı; Ar-Ge "
          "kurum ve kuruluşlarına yaptırılan Ar-Ge hizmeti.")
SURE = ("Çağrı esaslı. 2026 yılı 2. çağrı: açılış 20.07.2026; kuruluş bazlı ön kayıt son günü 22.10.2026 (23:59); "
        "kapanış 26.10.2026. Sonraki çağrılar TÜBİTAK duyurusuyla.")
SART = "Bu çağrı döneminde kuruluş başına en fazla 2 proje önerisi sunulabilir (2026-2 çağrı metni)"


def uygula(db, dry_run: bool = True) -> int:
    t = db.get(Tesvik, 34)
    if t is None or "1501" not in t.baslik:
        raise SystemExit("34 beklenen 1501 kaydı değil; durduruldu")
    if NOT in (t.durum_notu or ""):
        print("[34] zaten düzeltilmiş; atlandı")
        return 0
    print(f"[34] formül: '{(t.tutari_hesaplama_formulu or '')[:70]}…' → '{FORMUL[:70]}…'")
    print(f"[34] süre: '{t.basvuru_suresi}' → '{SURE[:70]}…'")
    print(f"[34] şart eklenir: {SART}")
    if not dry_run:
        eski_f, eski_s = t.tutari_hesaplama_formulu, t.basvuru_suresi
        t.tutari_hesaplama_formulu, t.basvuru_suresi = FORMUL, SURE
        t.basvuru_sartlari = [*(t.basvuru_sartlari or []), SART]
        t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
            f"{NOT}: formül tutarla çelişiyordu ('üst limit yok'), program sayfası ve 2026-2 çağrı metniyle düzeltildi; "
            f"eski formül: '{eski_f}'; eski süre: '{eski_s}'; kanıt docs/olcum/2026-10-08-tur18/kanit.json")
        db.commit()
    return 1


def _self_test() -> int:
    k_ = json.dumps(json.loads(KANIT.read_text(encoding="utf-8")), ensure_ascii=False)
    k = [
        ("20 milyon sınırı kanıtta ve formülde", "20 milyon TL ile sınırlandırılmıştır" in k_ and "en fazla 20 milyon" in FORMUL),
        ("formülde 'limit yok' yok", "limit yok" not in FORMUL),
        ("oranlar kanıtla aynı", "%75" in k_ and "%75" in FORMUL and "%60" in FORMUL),
        ("takvim kanıtla aynı", "20.07.2026" in k_ and "20.07.2026" in SURE and "22.10.2026" in SURE),
        ("2 proje şartı kanıtta", "en fazla 2 proje önerisi" in k_),
    ]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in k)
    print(f"\nself-test: {gecen}/{len(k)} geçti")
    return 0 if gecen == len(k) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(_self_test())
    db = SessionLocal()
    try:
        n = uygula(db, dry_run=not a.uygula)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} kayıt")
    finally:
        db.close()
