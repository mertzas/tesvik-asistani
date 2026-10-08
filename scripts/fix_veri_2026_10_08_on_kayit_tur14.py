"""Tur 14 — TÜBİTAK çağrılarında firmanın son günü: ön kayıt tarihi (tesvik_cagrilari.on_kayit_son, göç n1c3e5a7b234).

Ölçüm (docs/olcum/2026-10-08-persona/RAPOR.md): çip ve "sıradaki adım" çağrı kapanışını gösteriyordu; firmanın
son günü ise PRODİS ön kaydı. Tarihler çağrı satırının kaynak PDF'inden (6. Çağrı Takvimi) 2026-10-08'de okundu:
  1501 2026-2: "Kuruluş Başvurusu Son Tarihi 22.10.2026 (Saat 23.59)", kapanış 26.10.2026
  1507 2026-2: "Ön Kayıt Son Tarihi 09.11.2026 (Saat 23:59)", kapanış 11.11.2026
Bu tarihler tur10'da notlar alanına zaten yazılmıştı; bu tur onları yapılandırılmış alana taşır.

(B) 5986 m.8 ve m.5 kayıtlarına asgari önceki yıl ihracatı (uygunluk_kriterleri.min_onceki_yil_ihracat_usd):
  m.8 Çevrim İçi Mağaza: şirketlerde 1.000.000 USD üstü (Genelge m.18; kayıt şartlarında yazılı)
  m.5 E-İhracat Tanıtım: Perakende E-Ticaret Sitesi statüsü için 500.000 USD (Genelge m.7; diğer yol ETBİS ≥ 1 milyar
      TL, bu yüzden statü sahibi muaf: statu_ile_muaf). Eşleştirme bilinen ihracat bu değerin altındaysa programı eler.

Idempotent: on_kayit_son doluysa ve aynıysa atlanır; farklıysa durur (elle inceleme). Kriter aynıysa atlanır.

    python scripts/fix_veri_2026_10_08_on_kayit_tur14.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_08_on_kayit_tur14.py --uygula
    python scripts/fix_veri_2026_10_08_on_kayit_tur14.py --self-test
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik, TesvikCagrisi  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# (tesvik_id, çağrı adı) -> (ön kayıt son günü, kapanış — doğrulama için, kaynakta okunan ifade)
ON_KAYIT = {
    (34, "2026 yılı 2. çağrı"): (date(2026, 10, 22), date(2026, 10, 26), "Kuruluş Başvurusu Son Tarihi 22.10.2026"),
    (44, "2026 yılı 2. çağrı"): (date(2026, 11, 9), date(2026, 11, 11), "Ön Kayıt Son Tarihi 09.11.2026"),
}


KARAR_5986 = "https://ticaret.gov.tr/data/632b13e013b8767974670b91/E-ihracat%20Karar.pdf"
IHRACAT_KRITERI = {
    f"{KARAR_5986}#madde-8": {"min_onceki_yil_ihracat_usd": 1_000_000},
    f"{KARAR_5986}#madde-5": {"min_onceki_yil_ihracat_usd": 500_000, "statu_ile_muaf": True},
}


def uygula(db, dry_run: bool = True) -> tuple[int, int]:
    n, atlanan = _on_kayit(db, dry_run)
    for url, kriter in IHRACAT_KRITERI.items():
        t = db.query(Tesvik).filter(Tesvik.kaynak_url == url).first()
        if t is None:
            raise SystemExit(f"{url} kaydı yok: önce tur12 uygulanmalı")
        mevcut = dict(t.uygunluk_kriterleri or {})
        if all(mevcut.get(k) == v for k, v in kriter.items()):
            atlanan += 1
            continue
        print(f"[{t.id}] {t.baslik[:60]}: kriter {kriter}")
        if not dry_run:
            t.uygunluk_kriterleri = {**mevcut, **kriter}   # JSON sütunu: yeni nesne atanmalı
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"Tur14 2026-10-08: asgari önceki yıl ihracatı kriteri {kriter} (5986 Genelgesi; kayıt şartlarında yazılı)")
        n += 1
    if not dry_run:
        db.commit()
    return n, atlanan


def _on_kayit(db, dry_run: bool) -> tuple[int, int]:
    n = atlanan = 0
    for (tid, ad), (on_kayit, kapanis, ifade) in ON_KAYIT.items():
        c = db.query(TesvikCagrisi).filter(TesvikCagrisi.tesvik_id == tid, TesvikCagrisi.ad == ad).first()
        if c is None:
            raise SystemExit(f"[{tid}] '{ad}' çağrısı yok: önce tur10 uygulanmalı")
        if c.kapanis != kapanis:
            raise SystemExit(f"[{tid}] kapanış beklenenden farklı ({c.kapanis} != {kapanis}); durduruldu")
        if c.on_kayit_son == on_kayit:
            atlanan += 1
            continue
        if c.on_kayit_son is not None:
            raise SystemExit(f"[{tid}] on_kayit_son zaten farklı dolu ({c.on_kayit_son}); elle inceleyin")
        print(f"[{tid}] {ad}: ön kayıt son gün {on_kayit} (kapanış {kapanis}) — kaynak: '{ifade}' ({c.kaynak_url})")
        if not dry_run:
            c.on_kayit_son = on_kayit
        n += 1
    return n, atlanan  # commit, uygula() içinde iki bölüm birlikte


def _self_test() -> int:
    k = [
        ("iki çağrı", len(ON_KAYIT) == 2),
        ("ön kayıt kapanıştan önce", all(o < kp for o, kp, _ in ON_KAYIT.values())),
        ("kaynak ifadesindeki tarih alanla aynı", all(o.strftime("%d.%m.%Y") in ifade for o, _, ifade in ON_KAYIT.values())),
        ("ihracat eşikleri: m.8 1 M USD, m.5 500 bin USD ve statü muafiyeti",
         [v["min_onceki_yil_ihracat_usd"] for v in IHRACAT_KRITERI.values()] == [1_000_000, 500_000]
         and IHRACAT_KRITERI[f"{KARAR_5986}#madde-5"].get("statu_ile_muaf") is True),
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
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} kayıt güncellendi, {atlanan} atlandı")
    finally:
        db.close()
