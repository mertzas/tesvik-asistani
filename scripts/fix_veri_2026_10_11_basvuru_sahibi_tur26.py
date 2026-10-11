"""Tur 26 — başvuru sahibi türü ve kontrol listesindeki geliştirici notu (2026-10-11).

Bağımsız uzman değerlendirmesi (docs/olcum/2026-10-11-yerel-danisman/degerlendirme_E.json, senaryo 27-28):
  * 199 Ankara Sosyal Girişimcilik Ekosistemi programı A.Ş.'ye "uygun" gösteriliyordu; kaydın doğrulanmış şart
    maddesi (resmî sayfa alıntısı "Uygun Başvuru Sahipleri Kooperatifler İktisadi İşletmesi Olan Dernek ve Vakıflar
    Sosyal İşletmeler") şirketleri saymıyor. Profil türlerinden yalnız kooperatif açık: sirket_turleri = ["kooperatif"].
    (221 bilerek dokunulmadı: oda kayıtlı tarımsal üretim yapan işletmeler de başvurabiliyor.)
  * 192-196 (5986 e-ihracat kalemleri) kontrol listesindeki "Türk ürünü" şartının sonunda bir geliştirici notu
    kullanıcıya gösteriliyordu ("..., Genelge'den teyit edildikten sonra eklenmeli"). Not, kullanıcıya dönük
    "ayrıntıyı Genelge'den teyit edin" ifadesiyle değişir; madde ve alıntısı aynı kalır.
Şirket türü kısıtı yalnız kaydın tur21'de canlı sayfayla doğrulanmış (dogrulandi=True) maddesinin alıntısına dayanır.

    python scripts/fix_veri_2026_10_11_basvuru_sahibi_tur26.py             (dry-run)
    python scripts/fix_veri_2026_10_11_basvuru_sahibi_tur26.py --uygula
    python scripts/fix_veri_2026_10_11_basvuru_sahibi_tur26.py --self-test
"""
import argparse
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur26 2026-10-11"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur26.db.bak"
SIRKET_TURU = {199: (["kooperatif"], "Uygun Başvuru Sahipleri Kooperatifler İktisadi İşletmesi Olan Dernek ve Vakıflar "
                                     "Sosyal İşletmeler")}
ESKI_NOT = "(KTÜN, üretim yeri ve tescilli marka bilgisi şartı ayrı madde olarak, Genelge'den teyit edildikten sonra eklenmeli)"
YENI_NOT = "(ürün belgesi, üretim yeri ve marka ayrıntılarını E-İhracat Genelgesi'nden teyit edin)"
DUZELTILEN = {192, 193, 194, 195, 196}


def duzelt(metin: str) -> str:
    return metin.replace(ESKI_NOT, YENI_NOT)


def uygula(db, dry_run: bool = True) -> int:
    from app.models import Tesvik
    n = 0
    for tid, (turler, alinti) in SIRKET_TURU.items():
        t = db.get(Tesvik, tid)
        if t is None:
            raise SystemExit(f"[{tid}] kayıt yok; durduruldu")
        k = dict(t.uygunluk_kriterleri or {})
        if k.get("sirket_turleri") == turler:
            continue
        dayanak = [x for x in (t.kontrol_listesi or []) if x.get("dogrulandi") and x.get("alinti") == alinti]
        if not dayanak:
            print(f"[{tid}] doğrulanmış alıntılı madde bulunamadı; atlandı")
            continue
        print(f"[{tid}] {t.baslik[:60]}: sirket_turleri {k.get('sirket_turleri')} → {turler}")
        if not dry_run:
            t.uygunluk_kriterleri = {**k, "sirket_turleri": turler}
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: başvuru sahibi türü doğrulanmış şart maddesinden (\"{alinti}\")")
        n += 1
    for tid in sorted(DUZELTILEN):
        t = db.get(Tesvik, tid)
        if t is None:
            continue
        liste = [({**x, "metin": duzelt(x["metin"])} if ESKI_NOT in x.get("metin", "") else x)
                 for x in (t.kontrol_listesi or [])]
        sartlar = [duzelt(x) for x in (t.basvuru_sartlari or [])]
        if liste == (t.kontrol_listesi or []) and sartlar == (t.basvuru_sartlari or []):
            continue
        print(f"[{tid}] {t.baslik[:60]}: geliştirici notu kullanıcıya dönük ifadeyle değişir")
        if not dry_run:
            t.kontrol_listesi, t.basvuru_sartlari = liste, sartlar
        n += 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} değişiklik")
    return n


def _self_test() -> int:
    from app.matching import uygunluk_engeli
    from app.models import FinancialProfile, Tesvik
    t = Tesvik(id=199, kurum="Ankara Kalkınma Ajansı", baslik="Sosyal Girişimcilik", ozet="o", detay="d", aktif_mi=True,
               kaynak_url="u", uygunluk_kriterleri={"sektorler": ["genel"], "sirket_turleri": SIRKET_TURU[199][0]})
    k = [("A.Ş. elenir", uygunluk_engeli(t, FinancialProfile(sektor="imalat", sirket_turu="anonim")) is not None),
         ("kooperatif kalır", uygunluk_engeli(t, FinancialProfile(sektor="tarim", sirket_turu="kooperatif")) is None),
         ("not düzeltmesi", duzelt(f"Türk ürünü olmalı {ESKI_NOT}") == f"Türk ürünü olmalı {YENI_NOT}"),
         ("notsuz metin değişmez", duzelt("Türk ürünü olmalı") == "Türk ürünü olmalı"),
         ("yeni ifade geliştirici notu değil", "eklenmeli" not in YENI_NOT and "teyit edildikten sonra" not in YENI_NOT)]
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
