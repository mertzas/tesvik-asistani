"""Tur 22 — 1512 BiGG'nin durumu ve şartsız kalan dört ajans kaydına başvuru şartları (2026-10-10).

1. 1512 (kayıt 174): TÜBİTAK 1612 sayfası (EN) "The Implementing Organizations that will carry out the Phase 1 activities
   during the 2026-2028 period within the framework of the 1812 Investment-Based Entrepreneurship Support Program (BiGG
   Investment) have been determined." diyor; 1512 program sayfası erişime kapalı; 1812-BİGG+2026-1 çağrısı 1512'yi yalnız
   önceki program olarak anıyor. -> 1512 pasif; yeni girişimci 1812 (kayıt 49) çağrılarına yönlendirilir.
   Kanıt: docs/olcum/2026-10-10-tur22/tubitak_1612_en.txt.
2. 201 (BAKKA Fizibilite), 231, 232, 235 (OKA teknik destekleri): tur21'de şart maddesi çıkarılamamıştı. Başvuru
   rehberlerinin "KİMLER BAŞVURABİLİR?" / ilan sayfasının "Uygun Başvuru Sahipleri" bölümünden alıntılı maddeler.
   Alıntılar tur21 önbelleğindeki resmî metinde aranır; bulunamayan madde eklenmez.

    python scripts/fix_veri_2026_10_10_bigg_sart_tur22.py             (dry-run)
    python scripts/fix_veri_2026_10_10_bigg_sart_tur22.py --uygula
    python scripts/fix_veri_2026_10_10_bigg_sart_tur22.py --self-test
"""
import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur22 2026-10-10"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur22.db.bak"
BIGG_NOTU = ("TÜBİTAK, BiGG 1. aşamasını 2026-2028 döneminde 1812 Yatırım Tabanlı Girişimcilik Destek Programı (BiGG Yatırım) "
             "çerçevesinde yürütüyor (1612 çağrı sayfası); 1512 program sayfası erişime kapalı. Yeni başvuru için 1812 "
             "çağrılarına bakın. Kanıt: docs/olcum/2026-10-10-tur22/tubitak_1612_en.txt")
OKA_REHBER = "https://oka.gov.tr/assets/upload/dosyalar/"
# tesvik_id -> [(tur, metin, alıntı, alıntının kaynak dosyası anahtarı: kaydın kontrol listesindeki URL'nin bu sonekle bitmesi)]
MADDELER = {
    201: [("sart", "Kamu kurumu, belediye, OSB, sanayi sitesi, TTO/TGB/serbest bölge yönetici şirketi, STK, birlik ya da "
                   "kooperatif olmak (özel şirketler bu programa başvuramaz)",
           "Sivil Toplum Kuruluşları, Birlikler ve Kooperatifler", "15169")],
    231: [("sart", "Kâr amacı güden gerçek ya da tüzel kişi (işletme), kooperatif, birlik, STK, yerel yönetim ya da kamu "
                   "kurumu olmak", "Kar amacı güden diğer gerçek veya tüzel kişiler", "tr83-26-td-tur_-basvuru-rehberi.pdf"),
          ("kural", "Her başvuru döneminde en fazla 2 proje sunulabilir; aynı dönemde yalnız 1 projeye destek verilir",
           "her başvuru döneminde en fazla 2 (iki) adet proje sunabilir", "tr83-26-td-tur_-basvuru-rehberi.pdf")],
    232: [("sart", "Kâr amacı güden gerçek ya da tüzel kişi (işletme), kooperatif, birlik, STK, OSB, sanayi sitesi ya da "
                   "kamu kurumu olmak", "Kâr amacı güden diğer gerçek ve tüzel kişiler", "tr83-26-td-id_-basvuru-rehberi.pdf"),
          ("sart", "Amasya, Çorum, Samsun ya da Tokat'ta kayıtlı olmak veya merkezi ya da yasal şubesi bu illerde bulunmak",
           "Ajansın faaliyet gösterdiği Düzey 2 bölgesinde (Amasya, Çorum, Samsun, Tokat) kayıtlı olması",
           "tr83-26-td-id_-basvuru-rehberi.pdf"),
          ("kural", "Her başvuru döneminde en fazla 2 proje sunulabilir; programda toplam en fazla 1 projeye destek verilir",
           "her başvuru döneminde en fazla 2 (iki) adet proje sunabilir", "tr83-26-td-id_-basvuru-rehberi.pdf")],
    235: [("sart", "Kâr amacı güden gerçek ya da tüzel kişi (işletme), kooperatif, birlik, STK, üniversite, OSB ya da kamu "
                   "kurumu olmak", "Kâr amacı güden diğer gerçek ve tüzel kişiler", "tr83-26-td-skg_-basvuru-rehberi_15012026.pdf"),
          ("kural", "Her başvuru döneminde en fazla 2 proje sunulabilir; yerel yönetimler dışındakiler yılda en fazla 1 "
                    "proje için destek alır", "her başvuru döneminde en fazla 2 (iki) adet proje sunabilir",
           "tr83-26-td-skg_-basvuru-rehberi_15012026.pdf")],
}


def _tur21():
    spec = importlib.util.spec_from_file_location("tur21", KOK / "scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def uygula(db, dry_run: bool = True, getir=None) -> int:
    from app.models import Tesvik
    t21 = _tur21()
    getir = getir or t21.metin_al
    n = 0
    t = db.get(Tesvik, 174)
    if t is not None and t.aktif_mi is not False:
        print(f"[174] {t.baslik[:50]}: aktif_mi {t.aktif_mi} → False")
        if not dry_run:
            t.aktif_mi = False
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + f"{NOT}: {BIGG_NOTU}"
        n += 1
    for tid, maddeler in MADDELER.items():
        t = db.get(Tesvik, tid)
        if t is None:
            raise SystemExit(f"[{tid}] kayıt yok; durduruldu")
        liste = list(t.kontrol_listesi or [])
        mevcut = {x["metin"] for x in liste}
        url_adaylari = {x.get("kaynak_url") for x in liste} | {t.kaynak_url}
        yeni = []
        for tur, metin, alinti, sonek in maddeler:
            if metin in mevcut:
                continue
            url = next((u for u in url_adaylari if u and u.endswith(sonek)), None)
            if url is None:
                print(f"[{tid}] kaynak adresi bulunamadı ({sonek}); madde atlandı")
                continue
            metin_k, hata = getir(url)
            if hata or t21.norm(alinti) not in t21.norm(metin_k):
                print(f"[{tid}] alıntı kaynakta yok; madde atlandı: {alinti[:50]}")
                continue
            yeni.append({"tur": tur, "metin": metin, "alinti": alinti, "kaynak_url": url, "kaynak_tarihi": "2026-10-10",
                         "dogrulandi": True})
        if not yeni:
            continue
        print(f"[{tid}] {t.baslik[:50]}: +{len(yeni)} madde ({', '.join(x['tur'] for x in yeni)})")
        if not dry_run:
            sartlar = [x for x in yeni if x["tur"] == "sart"]
            t.kontrol_listesi = sartlar + liste + [x for x in yeni if x["tur"] != "sart"]
            t.basvuru_sartlari = [*(t.basvuru_sartlari or []), *(x["metin"] for x in sartlar)]
            t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                f"{NOT}: başvuru sahibi şartları rehberin 'Kimler başvurabilir' bölümünden eklendi")
        n += 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} değişiklik")
    return n


def _self_test() -> int:
    t21 = _tur21()
    kanit = (KOK / "docs/olcum/2026-10-10-tur22/tubitak_1612_en.txt").read_text(encoding="utf-8")
    k = [("1612 kanıtı 1812 çerçevesini içerir", "within the framework of the 1812 Investment-Based Entrepreneurship" in kanit),
         ("her maddenin alıntısı ve kaynak soneki var", all(len(x) == 4 and x[2] and x[3] for v in MADDELER.values() for x in v)),
         ("türler geçerli", all(x[0] in ("sart", "kural") for v in MADDELER.values() for x in v)),
         ("BAKKA fizibilite özel şirketi dışlar", "özel şirketler bu programa başvuramaz" in MADDELER[201][0][1]),
         ("normalize alıntı arama", t21.norm("Kâr amacı  güden\ndiğer") in t21.norm("x Kâr amacı güden diğer y"))]
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
