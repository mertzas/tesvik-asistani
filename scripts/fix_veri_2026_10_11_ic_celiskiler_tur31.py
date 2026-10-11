"""Tur 31 — kayıt içi çelişkiler: 163, 79, 142 (2026-10-11).

Bağımsız değerlendirme (degerlendirme4..8_B/E) aynı kaydın alanlarının birbirini yalanladığını buldu. Yeni bilgi
eklenmez; her düzeltme kaydın kendi kaynaklı alanına ya da önceki turun kanıtına dayanır:

  * 163 "Pazara Girişte Dijital Faaliyetlerin Desteklenmesi": Tur12 (2026-10-08) Bakanlık sayfasında dayanağın
    "MÜLGA" olduğunu gördü (2573 sayılı Karar 18.08.2022'de yürürlükten kalktı) ve kaydı pasifleştirdi; güncel
    karşılığını 5986 sayılı Karar m.8 ve m.4 olarak not etti. Tutar ve açıklama alanları ise Denetim2'nin eski
    "yürürlükte 5973" ifadesini taşıyordu; danışman "Son bilinen destek: 5973 sayılı Karar kapsamında" diyordu.
  * 79 "Sera/Örtüaltı Tarım Destekleri": Tur20 (2026-10-10) tutar ve hesaplama alanlarını 11781 sayılı CB Kararıyla
    (RG 08.09.2026; destek katsayı değeri 367,00 TL/da) güncelledi; açıklamada eski 310 / 527 TL/da kaldı.
  * 142 KGF "İSTİHDAM KORUMA DESTEK PROGRAMI": tutar alanı "Üst limit 45 Milyon TL" diyordu, KOSGEB programı (kayıt 7)
    ise "kredi üst limiti KOBİ 50 Milyon TL". Çelişki değil: kaydın kendi sayfa metni "Kefalet üst limiti … KOBİ 45
    Milyon TL 90%" (50 M TL kredinin %90'ı). Etiket "Kefalet üst limiti" olarak netleşir.

    python scripts/fix_veri_2026_10_11_ic_celiskiler_tur31.py             (dry-run)
    python scripts/fix_veri_2026_10_11_ic_celiskiler_tur31.py --uygula
    python scripts/fix_veri_2026_10_11_ic_celiskiler_tur31.py --self-test
"""
import argparse
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur31 2026-10-11"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur31.db.bak"

# kayıt → alan → (eski parça, yeni parça); eski parça alanda birebir aranır, yoksa (zaten düzeltilmiş) atlanır.
DUZELTMELER: dict[int, dict[str, list[tuple[str, str]]]] = {
    163: {
        "tesvil_tutari": [(
            "5973 sayılı İhracat Destekleri Hakkında Karar kapsamında; e-ticaret sitesi üyeliği oranı/limiti Bakanlık "
            "Genelgesi ve yıllık 'Destek Üst Limitleri' belgesinden teyit edilmeli (15.102 TL ifadesi 2022 yılına "
            "aitti)",
            "Program yürürlükte değil: dayanağı 2573 sayılı Karar 18.08.2022'de yürürlükten kalktı (mülga; Bakanlık "
            "sayfası). "
            "E-ticaret sitesi üyelik giderinin güncel karşılığı 5986 sayılı Karar m.8 (Çevrim İçi Mağaza ve Hedef Ülke "
            "E-Ticaret Paydaşı Hizmet Desteği); Bakanlık sayfasının andığı m.4 (Dijital Pazaryeri Tanıtım Desteği) "
            "reklam giderini destekler, üyelik giderini kapsamaz; 15.102 TL 2022 yılı değeridir"),
            # önceki uygulamanın metni → güncel metin
            ("Çevrim İçi Mağaza ve Hedef Ülke E-Ticaret Paydaşı Hizmet Desteği) ve m.4 (Dijital Pazaryeri Tanıtım "
             "Desteği); 15.102 TL",
             "Çevrim İçi Mağaza ve Hedef Ülke E-Ticaret Paydaşı Hizmet Desteği); Bakanlık sayfasının andığı m.4 "
             "(Dijital Pazaryeri Tanıtım Desteği) reklam giderini destekler, üyelik giderini kapsamaz; 15.102 TL"),
            # ilk uygulamadaki metin (2026-10-11, "mülga" ibaresi eksik) → güncel metin
            ("yürürlükten kalktı (Bakanlık sayfası). E-ticaret", "yürürlükten kalktı (mülga; Bakanlık sayfası). "
                                                                 "E-ticaret")],
        "tutari_hesaplama_formulu": [(
            "yıllık TL üst limiti için 5973 sayılı Karar Genelgesi / 'Destek Üst Limitleri' belgesine bakın (15.102 TL "
            "2022 yılı değeridir, güncel sayılmaz)",
            "program 18.08.2022'de sona erdi; güncel oran ve limitler için 5986 sayılı Karar m.8 ve m.4 kayıtlarına "
            "bakın (15.102 TL 2022 yılı değeridir, güncel sayılmaz)")],
        "detay": [(
            "(limit, 5973 sayılı Karar kapsamında Bakanlık Genelgesi ve yıllık 'Destek Üst Limitleri' belgesinde "
            "belirlenir; eski 15.102 TL rakamı 2022 yılına aittir, güncel kabul edilmemelidir)",
            "(dayanağı 2573 sayılı Karar 18.08.2022'de yürürlükten kalktı; güncel karşılığı 5986 sayılı Karar m.8 ve "
            "m.4; eski 15.102 TL rakamı 2022 yılına aittir)")],
    },
    79: {
        "detay": [(
            "2026 birim değerleri: temel destek 310 TL/da; örtüaltı iyi tarım bireysel sertifika katsayısı 1,7 = 527 "
            "TL/da (grup sertifikasında 0,85).",
            "2026 birim değerleri (11781 sayılı CB Kararı, RG 08.09.2026; destek katsayı değeri 367,00 TL/da): temel "
            "destek 367,00 TL/da; örtüaltı iyi tarım bireysel sertifika katsayısı 1,7 = 623,90 TL/da (grup "
            "sertifikasında 0,85 = 311,95 TL/da).")],
    },
    142: {
        "tesvil_tutari": [("Üst limit 45 Milyon TL; başvuru ücreti 10.000 TL",
                           "Kefalet üst limiti 45 Milyon TL (KOBİ, kefalet oranı %90); başvuru ücreti 10.000 TL")],
    },
}
# Değişiklikten önce kaydın kendi kaynaklı alanında bulunması gereken dayanak ifadeleri.
DAYANAK = {163: ("durum_notu", "güncel karşılığı 5986 m.8"), 79: ("tutari_hesaplama_formulu", "11781 sayılı CB Kararı"),
           142: ("detay", "45 Milyon TL")}


def duzelt(tid: int, alan: str, metin: str | None) -> str | None:
    for eski, yeni in DUZELTMELER.get(tid, {}).get(alan, []):
        if metin and eski in metin:
            metin = metin.replace(eski, yeni)
    return metin


def uygula(db, dry_run: bool = True) -> int:
    from app.models import Tesvik
    n = 0
    for tid, alanlar in DUZELTMELER.items():
        t = db.get(Tesvik, tid)
        if t is None:
            raise SystemExit(f"[{tid}] kayıt yok; durduruldu")
        alan_ad, ifade = DAYANAK[tid]
        if ifade not in (getattr(t, alan_ad) or ""):
            print(f"[{tid}] dayanak ifadesi '{ifade}' {alan_ad} alanında yok; atlandı")
            continue
        degisen = []
        for alan in alanlar:
            eski = getattr(t, alan)
            yeni = duzelt(tid, alan, eski)
            if yeni != eski:
                degisen.append(alan)
                print(f"[{tid}] {alan}: …{yeni[:110]}…")
                if not dry_run:
                    setattr(t, alan, yeni)
        if degisen:
            n += len(degisen)
            if not dry_run:
                t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                    f"{NOT}: kayıt içi çelişki giderildi ({', '.join(degisen)}; dayanak: {alan_ad})")
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} alan")
    return n


def _self_test() -> int:
    eski79 = "Temel destek. 2026 birim değerleri: temel destek 310 TL/da; örtüaltı iyi tarım bireysel sertifika " \
             "katsayısı 1,7 = 527 TL/da (grup sertifikasında 0,85). Sera kurulumu ayrı."
    k = [("79 eski değerler 367 / 623,90", "367,00 TL/da" in duzelt(79, "detay", eski79)
          and "310 TL" not in duzelt(79, "detay", eski79)),
         ("ikinci koşuda değişiklik yok", duzelt(79, "detay", duzelt(79, "detay", eski79))
          == duzelt(79, "detay", eski79)),
         ("163 5973 ifadesi kalkar", "5973" not in duzelt(163, "tesvil_tutari",
                                                           DUZELTMELER[163]["tesvil_tutari"][0][0])),
         ("142 kefalet etiketi", duzelt(142, "tesvil_tutari", "Üst limit 45 Milyon TL; başvuru ücreti 10.000 TL")
          .startswith("Kefalet üst limiti 45 Milyon TL")),
         ("tanımsız alan dokunulmaz", duzelt(142, "detay", "metin") == "metin"),
         ("None güvenli", duzelt(79, "detay", None) is None)]
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
    db = SessionLocal()
    try:
        uygula(db, dry_run=not a.uygula)
    finally:
        db.close()


if __name__ == "__main__":
    main()
