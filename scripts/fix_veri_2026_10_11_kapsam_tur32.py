"""Tur 32 — kapsam ölçümünden çıkan eksik programlar (2026-10-11).

Kapsam matrisi (docs/olcum/2026-10-11-kapsam/KAPSAM.md) veritabanında kaydı olmayan 6 kalkınma ajansını, KOSGEB'in
eksik programlarını ve imalat/hizmet/tarım için ince kalan ihracat, turizm, tarım ve istihdam desteklerini gösterdi.
Araştırma ajanları kayıtları docs/olcum/2026-10-11-kapsam/kayit/<slug>.json olarak hazırladı (şema:
docs/olcum/2026-10-10-tur21/YENI_KAYIT_SEMASI.md). Doğrulama ve ekleme tur21 betiğinin aynısıdır
(scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py): her kaynak adresi indirilir, her alıntı metinde aranır,
tutardaki ve çağrı tarihlerindeki her sayı alıntıda geçmek zorundadır; geçmeyen kayıt REDDEDİLİR. Bu tur yalnız
klasörü, yedeği ve resmî alan adı listesini değiştirir (KOSGEB, Ticaret Bakanlığı, Eximbank, KGF, Kültür ve Turizm
Bakanlığı, İŞKUR, SGK eklendi).

    python scripts/fix_veri_2026_10_11_kapsam_tur32.py --dogrula   (indirir, doğrular, dogrulama.json; DB'ye dokunmaz)
    python scripts/fix_veri_2026_10_11_kapsam_tur32.py             (dry-run: kabul edilenleri gösterir)
    python scripts/fix_veri_2026_10_11_kapsam_tur32.py --uygula    (önce yedek; kabul edilenleri ekler; tekrar
                                                                     çalıştırılırsa aynı kaynak/başlık atlanır)
    python scripts/fix_veri_2026_10_11_kapsam_tur32.py --self-test
"""
import importlib.util
import re
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("tur21", KOK / "scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py")
tur21 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tur21)

tur21.DIZIN = KOK / "docs/olcum/2026-10-11-kapsam"
tur21.ONBELLEK = tur21.DIZIN / "kaynak"
tur21.YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur32.db.bak"
tur21.BUGUN = date(2026, 10, 11)
tur21.NOT = "Tur32 2026-10-11"
# SGK'nın teşvikler sayfası birden çok teşviki anlatır (4447 kayıtları da aynı adreste): tekrar ölçütü kurum + başlık.
tur21.URL_TEKILLIGI = False
tur21.RESMI = re.compile(
    r"(^|\.)(tkdk\.gov\.tr|resmigazete\.gov\.tr|sanayi\.gov\.tr|yatirimadestek\.gov\.tr|tarimorman\.gov\.tr|"
    r"kosgeb\.gov\.tr|ticaret\.gov\.tr|eximbank\.gov\.tr|kgf\.com\.tr|ktb\.gov\.tr|iskur\.gov\.tr|sgk\.gov\.tr|"
    rf"(?:{tur21.AJANSLAR})\.(?:gov|org)\.tr)$")


def _self_test() -> int:
    k = [("tur21 doğrulama kuralları", tur21._self_test() == 0),
         ("yeni resmî alan adları", all(tur21.resmi_mi(u) for u in (
             "https://www.kosgeb.gov.tr/site/tr/genel/destekdetay/1", "https://ticaret.gov.tr/destekler/x",
             "https://www.eximbank.gov.tr/tr/urunler/x", "https://www.ktb.gov.tr/x", "https://www.iskur.gov.tr/x",
             "https://www.sgk.gov.tr/x", "https://www.istka.org.tr/x", "https://www.izka.org.tr/x",
             "https://www.gmka.gov.tr/x"))),
         ("resmî olmayan reddedilir", not any(tur21.resmi_mi(u) for u in (
             "https://kosgebdestek.com/x", "https://www.kosgeb.gov.tr.evil.com/x", "https://ihracat-danismanlik.com/x"))),
         ("tur32 klasörü ve yedek", tur21.DIZIN.name == "2026-10-11-kapsam" and tur21.YEDEK.name.endswith("tur32.db.bak"))]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    tur21.main()
