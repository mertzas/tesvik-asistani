"""Tur 34 — araştırılmış ama eklenmemiş programlar ve persona testinin ortaya çıkardığı boşluklar (2026-10-12).

10962 sayılı Kararın kalan maddeleri, Türk Eximbank'ın uluslararası kaynaklı kredileri, tarım (fındık, TARSİM,
sübvansiyonlu tarımsal kredi, iyi tarım, sertifikalı fide), esnaf kredisi ve vergi istisnaları.
Kayıtlar: docs/olcum/2026-10-12-tur34/kayit/<slug>.json (şema: docs/olcum/2026-10-10-tur21/YENI_KAYIT_SEMASI.md).
Doğrulama ve ekleme tur32'nin aynısıdır; resmî alan adı listesi bu kurumların kendi alan adlarıyla genişler.

    python scripts/fix_veri_2026_10_12_tur34.py --metin URL      (kaynağı indirir; doğrulayıcının gördüğü metnin yolu)
    python scripts/fix_veri_2026_10_12_tur34.py --dogrula-tek SLUG (tek kaydı doğrular; dogrulama.json'a yazmaz)
    python scripts/fix_veri_2026_10_12_tur34.py --dogrula        (hepsini doğrular, dogrulama.json; DB'ye dokunmaz)
    python scripts/fix_veri_2026_10_12_tur34.py                  (dry-run)
    python scripts/fix_veri_2026_10_12_tur34.py --uygula         (önce yedek; tekrar çalıştırılırsa aynı kurum+başlık atlanır)
    python scripts/fix_veri_2026_10_12_tur34.py --self-test
"""
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("tur32", KOK / "scripts/fix_veri_2026_10_11_kapsam_tur32.py")
tur32 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tur32)
tur21 = tur32.tur21

tur21.DIZIN = KOK / "docs/olcum/2026-10-12-tur34"
tur21.ONBELLEK = tur21.DIZIN / "kaynak"
tur21.YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur34.db.bak"
tur21.BUGUN = date(2026, 10, 12)
tur21.NOT = "Tur34 2026-10-12"
# Kurumların kendi alan adları: Gelir İdaresi, mevzuat, TARSİM, TMO, kamu bankaları, Tarım Kredi, TÜBİTAK.
EK_RESMI = (r"gib\.gov\.tr|mevzuat\.gov\.tr|tarsim\.gov\.tr|tmo\.gov\.tr|ziraatbank\.com\.tr|halkbank\.com\.tr|"
            r"tarimkredi\.org\.tr|tubitak\.gov\.tr|hmb\.gov\.tr|ebelge\.gib\.gov\.tr")
tur21.RESMI = re.compile(tur21.RESMI.pattern.replace(r"(^|\.)(", rf"(^|\.)({EK_RESMI}|", 1))


def _metin(url: str) -> int:
    if not tur21.resmi_mi(url):
        print(f"resmî alan adı değil: {url}")
        return 1
    metin, hata = tur21.metin_al(url)
    if hata:
        print(f"indirilemedi: {hata}")
        return 1
    import hashlib
    yol = tur21.ONBELLEK / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".txt")
    print(f"{yol}  ({len(metin)} karakter)")
    return 0


def _dogrula_tek(slug: str) -> int:
    yol = tur21.DIZIN / "kayit" / f"{slug}.json"
    r = tur21.dogrula_kayit(json.loads(yol.read_text(encoding="utf-8")))
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["kabul"] else 1


def _self_test() -> int:
    k = [("tur21 doğrulama kuralları", tur21._self_test() == 0),
         ("tur32 resmî alan adları devralındı", tur21.resmi_mi("https://ticaret.gov.tr/x")
          and tur21.resmi_mi("https://www.eximbank.gov.tr/x")),
         ("yeni resmî alan adları", all(tur21.resmi_mi(u) for u in (
             "https://www.gib.gov.tr/x", "https://www.mevzuat.gov.tr/x", "https://www.tarsim.gov.tr/x",
             "https://www.tmo.gov.tr/x", "https://www.ziraatbank.com.tr/x", "https://www.halkbank.com.tr/x",
             "https://www.tarimkredi.org.tr/x", "https://tubitak.gov.tr/x"))),
         ("taklit alan adları reddedilir", not any(tur21.resmi_mi(u) for u in (
             "https://gib.gov.tr.evil.com/x", "https://halkbank-kredi.com/x", "https://www.tarsimm.gov.tr/x"))),
         ("kurum+başlık tekrar ölçütü", tur21.URL_TEKILLIGI is False),
         ("tur34 klasörü, yedek ve not", tur21.DIZIN.name == "2026-10-12-tur34" and tur21.YEDEK.name.endswith("tur34.db.bak")
          and tur21.NOT.startswith("Tur34"))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    for akim in (sys.stdout, sys.stderr):
        akim.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if "--metin" in sys.argv:
        sys.exit(_metin(sys.argv[sys.argv.index("--metin") + 1]))
    if "--dogrula-tek" in sys.argv:
        sys.exit(_dogrula_tek(sys.argv[sys.argv.index("--dogrula-tek") + 1]))
    tur21.main()
