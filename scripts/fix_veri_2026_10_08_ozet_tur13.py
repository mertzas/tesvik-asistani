"""Tur 13 — özeti yalnız kurum sitesi menü metni olan aktif kayıtlara resmi "amaç" metni (2026-10-08).

Ölçüm: aktif kayıtların 22'sinde özet tamamen menü/başlık listesiydi ("Girişimci Destek Programı Kapasite Geliştirme
Destek Programı Küresel ..."); eşleşme kartında kullanıcının ilk gördüğü metin buydu. Kaynak sayfalardaki "Programın
Amacı" / "Ürün Açıklaması" / TÜBİTAK "Genel Bilgi" bölümleri birebir çıkarıldı (docs/olcum/2026-10-08-ozet/ozet_cikar.py),
gözden geçirildi ve tur13_ozetler.json'a yazıldı. Metin değiştirilmez; yalnız sondaki başlık artığı ("Ürün Vadesi")
atıldı. KGF'nin 7 sayfasında içerik JavaScript ile yüklendiği için metin yok: o kayıtlara dokunulmaz (arayüz menü
metnini zaten göstermez, app/basvuru_taslagi.kart_ozeti).

Kural: yalnızca mevcut özeti _temiz_ozet ile boş çıkan (tamamen menü) kayıtlar güncellenir; önceki özet durum_notu'na
kısaltılmış olarak not edilmez (menü metnidir), yalnızca değişiklik kaydı düşülür. Idempotent: "Tur13" notu varsa atlanır.

    python scripts/fix_veri_2026_10_08_ozet_tur13.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_08_ozet_tur13.py --uygula
    python scripts/fix_veri_2026_10_08_ozet_tur13.py --self-test
"""
import argparse
import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from app.basvuru_taslagi import _temiz_ozet  # noqa: E402
from app.models import SessionLocal, Tesvik  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur13 2026-10-08"
VERI = KOK / "docs/olcum/2026-10-08-ozet/tur13_ozetler.json"


def ozetler() -> dict[int, dict]:
    return {int(k): v for k, v in json.loads(VERI.read_text(encoding="utf-8")).items()}


def uygula(db, dry_run: bool = True) -> tuple[int, int]:
    n = atlanan = 0
    for tid, v in ozetler().items():
        t = db.get(Tesvik, tid)
        if t is None:
            raise SystemExit(f"[{tid}] kayıt yok; durduruldu")
        if NOT in (t.durum_notu or "") or _temiz_ozet(t.ozet):
            atlanan += 1
            continue
        if t.kaynak_url != v["kaynak"]:
            raise SystemExit(f"[{tid}] kaynak adresi değişmiş ({t.kaynak_url} != {v['kaynak']}); durduruldu")
        print(f"[{tid}] {t.baslik[:55]}\n      → {v['ozet'][:150]}")
        if not dry_run:
            t.ozet = v["ozet"]
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: özet (site menü metniydi) kaynak sayfanın '{v['bolum']}' bölümüyle değiştirildi ({v['kaynak']})")
        n += 1
    if not dry_run:
        db.commit()
    return n, atlanan


def _self_test() -> int:
    o = ozetler()
    k = [
        ("15 kayıt", len(o) == 15),
        ("her metin cümle (menü değil)", all(_temiz_ozet(v["ozet"]) for v in o.values())),
        ("başlık artığı yok", not any(v["ozet"].endswith(("Ürün Vadesi", "Başvuru Şartları")) for v in o.values())),
        ("kaynaklar resmi alan adı", all(v["kaynak"].startswith(("https://www.kosgeb.gov.tr", "https://www.tubitak.gov.tr",
                                                                "https://tubitak.gov.tr", "https://www.kgf.com.tr",
                                                                "https://kgf.com.tr")) for v in o.values())),
        ("KGF JS sayfaları dahil değil", not set(o) & {93, 116, 125, 153, 154, 171, 173}),
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
        n, atlanan = uygula(db, dry_run=not a.uygula)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} özet güncellendi, {atlanan} atlandı")
    finally:
        db.close()
