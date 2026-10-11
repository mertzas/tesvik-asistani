"""Tur 24 — Organik Tarım Destekleri (kayıt 77): doğrulanamayan "Tebliğ 2024/39" atıfları (2026-10-11).

Kaydın şart/belge alanları ve onlardan kurulan kontrol listesi maddeleri "Tebliğ 2024/39 m.7/3-a" gibi atıflar
taşıyordu. Bu numarayla bir tebliğ bulunamadı: 2024 üretim yılının bitkisel üretim destekleri tebliği
Tebliğ No 2024/31'dir (RG 26.09.2024, sayı 32674; organik tarım desteği Madde 6) ve 2026 üretim yılı için geçerli
uygulama tebliği teyit edilmedi. Madde içerikleri (ÇKS/OTBİS kaydı, hasat, ürün sertifikası) 2024/31 m.6 ve
8859 sayılı Karar m.2/(7)-c ile tutarlı; yalnız atıf yanlış. Atıf "2026 uygulama tebliğinden teyit edin" ile
değiştirilir; maddeler doğrulanmamış (dogrulandi=False) kalır. tur23'ün 8859 alıntılı şartına dokunulmaz.
Kanıt: docs/olcum/2026-10-11-tur24/teblig_2024_31.txt.

    python scripts/fix_veri_2026_10_11_organik_atif_tur24.py             (dry-run)
    python scripts/fix_veri_2026_10_11_organik_atif_tur24.py --uygula
    python scripts/fix_veri_2026_10_11_organik_atif_tur24.py --self-test
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TESVIK_ID = 77
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur24.db.bak"
KANIT = KOK / "docs/olcum/2026-10-11-tur24/teblig_2024_31.txt"
NOT = ("Tur24 2026-10-11: 'Tebliğ 2024/39' atıfları doğrulanamadı (2024 üretim yılı tebliği 2024/31, RG 26.09.2024; "
       "2026 uygulama tebliği teyit edilmedi); atıflar 'uygulama tebliğinden teyit edin' olarak düzeltildi")
TEYIT = "2026 uygulama tebliğinden teyit edin"
# "(Tebliğ 2024/39 m.7/3-a)" ya da "(…; Tebliğ 2024/39 m.15/1)" → atıf kısmı değişir, parantez içi diğer bilgi kalır.
_ATIF = re.compile(r"(;\s*)?Tebliğ 2024/39 [^)]*")


def duzelt(metin: str) -> str:
    def _yerine(m):
        return (m.group(1) or "") + TEYIT
    return _ATIF.sub(_yerine, metin)


def uygula(db, dry_run: bool = True) -> int:
    from app.models import Tesvik
    t = db.get(Tesvik, TESVIK_ID)
    if t is None:
        raise SystemExit(f"[{TESVIK_ID}] kayıt yok; durduruldu")
    sartlar = [duzelt(x) for x in (t.basvuru_sartlari or [])]
    belgeler = [duzelt(x) for x in (t.gerekli_belgeler or [])]
    liste = [({**x, "metin": duzelt(x["metin"]), "dogrulandi": False} if "Tebliğ 2024/39" in (x.get("metin") or "")
              else x) for x in (t.kontrol_listesi or [])]
    degisen = (sartlar != (t.basvuru_sartlari or [])) + (belgeler != (t.gerekli_belgeler or [])) \
        + (liste != (t.kontrol_listesi or []))
    if not degisen:
        print("\nDRY-RUN: 0 değişiklik" if dry_run else "\nUYGULANDI: 0 değişiklik")
        return 0
    n = sum("Tebliğ 2024/39" in x for x in (t.basvuru_sartlari or []) + (t.gerekli_belgeler or [])) + \
        sum("Tebliğ 2024/39" in (x.get("metin") or "") for x in (t.kontrol_listesi or []))
    print(f"[{TESVIK_ID}] {t.baslik}: {n} atıf düzeltilecek")
    if not dry_run:
        t.basvuru_sartlari, t.gerekli_belgeler, t.kontrol_listesi = sartlar, belgeler, liste
        t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + NOT
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} atıf")
    return n


def _self_test() -> int:
    kanit = KANIT.read_text(encoding="utf-8") if KANIT.exists() else ""
    k = [("kanıt: tebliğ numarası 2024/31", "TEBLİĞ NO: 2024/31" in kanit),
         ("kanıt: organik tarım desteği m.6 ürün sertifikası", "Organik tarım desteği" in kanit
          and "ürettiği ürüne ürün sertifikası düzenlenmiş" in kanit),
         ("kanıtta 2024/39 yok", "2024/39" not in kanit),
         ("tek atıf", duzelt("Hasat (Tebliğ 2024/39 m.7/3-a-2)") == f"Hasat ({TEYIT})"),
         ("noktalı virgüllü atıf", duzelt("Dilekçe (il müdürlüğüne; Tebliğ 2024/39 m.15/1)")
          == f"Dilekçe (il müdürlüğüne; {TEYIT})"),
         ("atıfsız metin değişmez", duzelt("Ürün sertifikası (8859 sayılı Karar m.2/7-c)")
          == "Ürün sertifikası (8859 sayılı Karar m.2/7-c)")]
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
