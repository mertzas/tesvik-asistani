"""Tur 23 — profil alanlarıyla denetlenebilen kişisel şartlar (2026-10-10).

Eşleştirme (app/matching._kisisel_engel) üç yapılandırılmış şartı okur; burada resmî metinden alıntıyla girilirler:
  * kurucu_yasi_max          — 122 Halkbank İlk Adım (29), 112 Halkbank Genç İşi (35); KGF ürün sayfaları
  * ortaklik_yasagi_sirketsiz — 49 TÜBİTAK 1812 BiGG Yatırım hızlandırma aşaması; TÜBİTAK program sayfası
  * gerekli_sertifika        — 77 Organik Tarım Destekleri; 8859 sayılı Karar m.2/(7)-c
Ayrıca 153 TURYIB (KGF) yalnız genç sahibi/yöneticisi olan işletmelere açık: zorunlu hedef kitle genc_girisimci.

Alıntılar canlı sayfada (tur21 önbelleği, docs/olcum/2026-10-10-tur21/kaynak) aranır. 8859 PDF'i taranmış görüntü olduğundan
metin katmanı yok; onun alıntısı sayfa görüntüsünden yapılan çevriyazıda ve PDF'in SHA-256 özetiyle doğrulanır
(docs/olcum/2026-10-10-tur23/). Bulunamayan alıntının şartı eklenmez. 138, 89, 169 kapsam dışı: 169 zaten
kadın/genç zorunlu hedef kitleli; 138 ve 89'un yaş şartı yalnız bileşen düzeyinde.

    python scripts/fix_veri_2026_10_10_profil_sart_tur23.py             (dry-run)
    python scripts/fix_veri_2026_10_10_profil_sart_tur23.py --uygula
    python scripts/fix_veri_2026_10_10_profil_sart_tur23.py --self-test
"""
import argparse
import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur23 2026-10-10"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur23.db.bak"
KANIT = KOK / "docs/olcum/2026-10-10-tur23"
RG_8859 = KOK / "docs/olcum/2026-10-10-tur20/rg_20240829_8859.pdf"
RG_8859_SHA256 = "89df0b6222edb4eddf3d5f588a4007061458adec8d518e3fbdb86b46ae5ba85f"
RG_8859_URL = "https://www.resmigazete.gov.tr/eskiler/2024/08/20240829-1.pdf"
CEVRIYAZI = KANIT / "rg_8859_m2_7_cevriyazi.txt"

# tesvik_id -> (uygunluk_kriterleri güncellemesi, kontrol listesine eklenecek şart metni, alıntı, kaynak: None = kayıt
# adresi, "8859" = çevriyazı)
SARTLAR = {
    122: ({"kurucu_yasi_max": 29},
          "İşletme sahibi ya da en az %50 hisseli ortağı kredi başvuru tarihinde en çok 29 yaşında olmalı",
          "Kredi başvuru tarihi itibarıyla, sahibi veya asgari %50 hisse sahibi ortağı azami 29 yaşında olan işletmeler",
          None),
    112: ({"kurucu_yasi_max": 35},
          "Kuruluşunun üzerinden 3 yıl geçmemiş ve en az %50 hissesi 35 yaşını aşmamış ortaklara ait işletme olmalı",
          "kuruluş tarihinden itibaren 3 yılını doldurmamış ve asgari %50 hissesi 35 yaşını aşmamış ortaklara ait "
          "işletmeler", None),
    49: ({"ortaklik_yasagi_sirketsiz": True},
         "Hızlandırma programına kabul tarihinde herhangi bir sermaye şirketinin ya da şahıs işletmesinin ortağı "
         "olmamak (borsadaki hisseler ve kitle fonlaması payları sayılmaz)",
         "hızlandırma programına kabul edildiği tarih itibarı ile sermaye şirketi veya gerçek kişi işletmesi herhangi "
         "bir işletmenin ortaklık yapısında yer alan kişiler başvuru yapamaz", None),
    77: ({"gerekli_sertifika": "organik_sertifika"},
         "Organik tarım faaliyeti yapılan ürüne yetkilendirilmiş kuruluşça \"ürün sertifikası\" düzenlenmiş olmalı "
         "ya da organik arıcılık yapılmalı (8859 sayılı Karar m.2/7-c)",
         "organik tarım faaliyeti yapan ve ürettiği ürüne \"ürün sertifikası\" düzenlenmiş olan çiftçiler ile organik "
         "arıcılık yapan yetiştiricilere", "8859"),
    153: ({"exclusive_target_group": True, "target_group_tags": ["genc_girisimci"]},
          "Sahibi ya da yöneticisi genç olan işletme olmalı (TURYIB programı)",
          "genç sahibi ve/veya yöneticisi bulunan işletmelere destek sağlanarak", None),
}


def _tur21():
    spec = importlib.util.spec_from_file_location("tur21", KOK / "scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cevriyazi_metni() -> tuple[str, str | None]:
    """8859 çevriyazısı; yerel PDF'in özeti çevriyazıdaki özetle ve sabitle eşleşmezse hata."""
    if not RG_8859.exists() or not CEVRIYAZI.exists():
        return "", "8859 PDF'i ya da çevriyazısı yok"
    ozet = hashlib.sha256(RG_8859.read_bytes()).hexdigest()
    metin = CEVRIYAZI.read_text(encoding="utf-8")
    if ozet != RG_8859_SHA256 or f"SHA256: {ozet}" not in metin:
        return "", f"8859 PDF özeti uyuşmuyor ({ozet[:12]})"
    return metin, None


def uygula(db, dry_run: bool = True, getir=None) -> int:
    from app.models import Tesvik
    t21 = _tur21()
    getir = getir or t21.metin_al
    n = 0
    for tid, (kriter, metin, alinti, kaynak) in SARTLAR.items():
        t = db.get(Tesvik, tid)
        if t is None:
            raise SystemExit(f"[{tid}] kayıt yok; durduruldu")
        mevcut_k = dict(t.uygunluk_kriterleri or {})
        liste = list(t.kontrol_listesi or [])
        k_degisir = any(mevcut_k.get(a) != d for a, d in kriter.items())
        madde = next((x for x in liste if x.get("metin") == metin), None)
        madde_var = madde is not None
        # "ekleyen" işareti tur19'un kontrol listesini yeniden kurarken bu maddeyi korumasını sağlar.
        if not k_degisir and madde_var and madde.get("ekleyen") == "tur23":
            continue
        url = RG_8859_URL if kaynak == "8859" else t.kaynak_url
        kaynak_metin, hata = cevriyazi_metni() if kaynak == "8859" else getir(t.kaynak_url)
        if hata or t21.norm(alinti) not in t21.norm(kaynak_metin):
            print(f"[{tid}] alıntı kaynakta bulunamadı ({hata or 'metinde yok'}); atlandı")
            continue
        degisen = {a: (mevcut_k.get(a), d) for a, d in kriter.items() if mevcut_k.get(a) != d}
        print(f"[{tid}] {t.baslik[:50]}: kriter {degisen or '-'}; madde {'işaretlenir' if madde_var else 'eklenir'}")
        if not dry_run:
            t.uygunluk_kriterleri = {**mevcut_k, **kriter}
            if madde_var:
                t.kontrol_listesi = [{**x, "ekleyen": "tur23"} if x is madde else x for x in liste]
            else:
                t.kontrol_listesi = [{"tur": "sart", "metin": metin, "alinti": alinti, "kaynak_url": url,
                                      "kaynak_tarihi": "2026-10-10", "dogrulandi": True, "ekleyen": "tur23"}, *liste]
                t.basvuru_sartlari = [*(t.basvuru_sartlari or []), metin]
            if k_degisir:
                t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + (
                    f"{NOT}: profil alanıyla denetlenen şart eklendi ({', '.join(kriter)})")
        n += 1
    if not dry_run:
        db.commit()
    print(f"\n{'UYGULANDI' if not dry_run else 'DRY-RUN'}: {n} değişiklik")
    return n


def _self_test() -> int:
    from app.match_adapter import OZELLIK_ETIKETLERI, SERTIFIKA_ETIKETLERI
    from app.matching import uygunluk_engeli
    from app.models import FinancialProfile, Tesvik
    t21 = _tur21()
    cevri, hata = cevriyazi_metni()

    def engel(tid, **profil):
        kriter = {"sektorler": ["genel", "tarim", "arge"], **SARTLAR[tid][0]}
        t = Tesvik(kurum="X", baslik="Program", ozet="o", detay="d", aktif_mi=True, kaynak_url="u",
                   uygunluk_kriterleri=kriter)
        return uygunluk_engeli(t, FinancialProfile(sektor="genel", **profil))

    k = [("8859 çevriyazısı PDF özetiyle eşleşir", hata is None),
         ("77 alıntısı çevriyazıda", t21.norm(SARTLAR[77][2]) in t21.norm(cevri)),
         ("her şartın metni ve alıntısı var", all(v[1] and v[2] for v in SARTLAR.values())),
         ("kriter anahtarları eşleştirmenin okuduklarıyla aynı",
          {a for v in SARTLAR.values() for a in v[0]} <= {"kurucu_yasi_max", "ortaklik_yasagi_sirketsiz",
                                                          "gerekli_sertifika", "exclusive_target_group",
                                                          "target_group_tags"}),
         ("sertifika ve hedef kitle değerleri tanımlı", SARTLAR[77][0]["gerekli_sertifika"] in SERTIFIKA_ETIKETLERI
          and set(SARTLAR[153][0]["target_group_tags"]) <= set(OZELLIK_ETIKETLERI)),
         ("122: 30 yaş elenir, 29 kalır", engel(122, kurucu_yasi=30) is not None and engel(122, kurucu_yasi=29) is None),
         ("49: şirketsiz + ortak elenir, bilinmeyen kalır",
          engel(49, sirket_turu="yok", baska_sirkette_ortak=True) is not None and engel(49, sirket_turu="yok") is None),
         ("77: 'hiçbiri' elenir, boş kalır", engel(77, sertifikalar=["hicbiri"]) is not None and engel(77) is None)]
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
