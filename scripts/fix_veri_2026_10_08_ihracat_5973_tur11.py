"""Tur 11 — 5973 sayılı İhracat Destekleri Kararından e-ticaret/KOBİ ihracatçısına uyan 5 destek (yeni kayıt).

Ölçüm (2026-10-08): İKAS satıcısının hedef kitlesi e-ticaret/e-ihracat KOBİ'si; veritabanında Ticaret Bakanlığı'nın
yalnız 3 aktif kaydı vardı ve 5973 sayılı Kararın 25 destek maddesinin hiçbiri yoktu.

Kaynaklar (2026-10-08'de indirildi, metin PyMuPDF/pdfplumber ile çıkarıldı):
  - Karar metni (değişikliklerle güncel; RG 18.08.2022/31927, son değişiklik RG 07.03.2026/33189):
    https://ticaret.gov.tr/data/69afdacb269de120c032b73a/5973%20Say%C4%B1l%C4%B1%20Karar.pdf
  - 2026 üst limitleri (Karar m.30: her yıl (TÜFE+Yİ-ÜFE)/2 ile güncellenir), tablolar hücre hücre okundu:
    UR-GE ve Yeşil Dönüşüm (m.3, m.4, m.6) ve Markalaşma Dairesi (m.11, m.12) PDF'leri.
Seçilen maddeler: 3 (pazara giriş belgesi), 4 (yurt dışı marka tescili), 6 (yurt dışı pazar araştırması),
11 (yurt dışı birim kira: mağaza/depo/ofis), 12 (yurt dışı tanıtım ve pazarlama). Fuar desteği (m.7) ALINMADI:
2026 fuar limit tablosu sayfada bağlantı olarak yok, Karar'daki TL tutarları 2022 tabanı.

Kurallar
  - Yalnız Karar ve 2026 limit tablosunda yazanlar. Başvuru süresi ve belge listesi uygulama genelgesinde
    (Karar m.31); genelge okunamadığı için bu alanlar BOŞ bırakıldı (kontrol listesi "resmi sayfadan kontrol edin" der).
  - "Şirket" (Karar m.2/n): TTK md.124 şirketleri ile kooperatifler -> şahıs işletmesi ve şirketi olmayan
    kapsam dışı (uygunluk_kriterleri.sirket_turleri; eşleştirme bunu uygular).
  - kaynak_url benzersiz olmalı: Karar adresi + "#madde-N".
  - Idempotent: aynı kaynak_url varsa kayıt atlanır.

    python scripts/fix_veri_2026_10_08_ihracat_5973_tur11.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_08_ihracat_5973_tur11.py --uygula
    python scripts/fix_veri_2026_10_08_ihracat_5973_tur11.py --self-test
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

KARAR = "https://ticaret.gov.tr/data/69afdacb269de120c032b73a/5973%20Say%C4%B1l%C4%B1%20Karar.pdf"
LIMIT_URGE = ("https://ticaret.gov.tr/data/63c0063e13b8763b44f9df24/"
              "2026%20Destek%20%C3%9Cst%20Limitleri_Ur-GE%20ve%20Ye%C5%9Fil%20D%C3%B6n%C3%BC%C5%9F%C3%BCm%20Destekleri.pdf")
LIMIT_MARKA = "https://ticaret.gov.tr/data/63c0063e13b8763b44f9df24/Markala%C5%9Fma%20Dairesi%20-%202026%20Destek%20Limitleri.pdf"
NOT = "Tur11 2026-10-08"
SIRKET_SARTI = ("Şirket olmak: 6102 sayılı TTK md.124'teki şirketler (kollektif, komandit, anonim, limited) ya da "
                "ticari/sınai faaliyette bulunan kooperatif (Karar m.2); şahıs işletmesi kapsam dışı")
BASVURU_YERI = ("Ticaret Bakanlığı Destek Yönetim Sistemi (DYS) üzerinden; başvuru süresi, usulü ve istenen belgeler "
                "5973 sayılı Karar uygulama genelgesinde belirlenir (Karar m.31) — güncel genelgeyi kontrol edin")
ORTAK_KRITER = {"sektorler": ["ihracat", "e-ticaret"], "tutar_niteligi": "hibe",
                "sirket_turleri": ["limited", "anonim", "kooperatif"]}


def _tl(x: int) -> str:
    return f"{x:,}".replace(",", ".") + " TL"


# madde -> alanlar. tutari_max = 2026 üst limiti (ilgili birim: yıl / faaliyet / birim-yıl; formülde açık).
KAYITLAR = {
    3: dict(
        baslik="Pazara Giriş Belgesi Desteği (5973 sayılı Karar m.3)",
        ozet="İhraç pazarına girişte zorunlu ya da avantaj sağlayan belge, sertifika, test/analiz ile ruhsatlandırma ve "
             "kayıt giderlerinin %50'si desteklenir.",
        detay=("Şirketlerin pazara giriş belgeleri ile ruhsatlandırma ve kayıt işlemlerine ilişkin giderleri %50 oranında "
               "desteklenir (Karar m.3). Pazara giriş belgeleri: akredite kuruluşlardan alınan, bir ülke pazarına girişte "
               "zorunlu olan veya avantaj sağlayan kalite/çevre belgeleri ve sertifikaları; can ve mal güvenliğini gösteren "
               "işaretler; ihraç ürünlerine ilişkin laboratuvar analizleri ve test/analiz raporları (Karar m.2). "
               "2026 üst limiti: şirket başına yıllık 19.728.672 TL (Karar'daki 4.000.000 TL 2022 tabanıdır)."),
        hedef_kitle="Ürününü yurt dışında satmak için CE, kalite, çevre belgesi ya da test raporu alan ihracatçı şirketler",
        tesvil_tutari="%50; 2026 yıllık üst limit 19.728.672 TL (şirket başına)", tutari_max=19_728_672,
        formul="Uygun giderin %50'si, yıllık en çok 19.728.672 TL (2026)",
        sartlar=[SIRKET_SARTI,
                 "Gider, akredite kurum/kuruluştan alınan ve hedef ülke pazarına girişte zorunlu ya da avantaj sağlayan "
                 "belge, sertifika, test/analiz veya ruhsatlandırma/kayıt işlemine ilişkin olmalı"],
        sure="Yıllık (takvim yılı esaslı üst limit)", kaynak_limit=LIMIT_URGE),
    4: dict(
        baslik="Yurt Dışı Marka Tescil Desteği (5973 sayılı Karar m.4)",
        ozet="Türkiye'de tescilli markanın yurt dışında tescil ve korunma giderlerinin %50'si, en çok 4 yıl desteklenir.",
        detay=("Şirketlerin yurt içi marka tescil belgesine sahip oldukları markalarının yurt dışında tescili ve korunmasına "
               "ilişkin giderleri %50 oranında desteklenir; destekten en fazla 4 yıl yararlanılır (Karar m.4). "
               "2026 üst limiti: yıllık 3.698.274 TL (Karar'daki 750.000 TL 2022 tabanıdır)."),
        hedef_kitle="Kendi markasıyla yurt dışına satış yapan (ör. e-ihracat) ve markasını hedef ülkede koruma altına "
                    "almak isteyen şirketler",
        tesvil_tutari="%50; 2026 yıllık üst limit 3.698.274 TL; en fazla 4 yıl", tutari_max=3_698_274,
        formul="Yurt dışı tescil/koruma giderinin %50'si, yıllık en çok 3.698.274 TL (2026), en fazla 4 yıl",
        sartlar=[SIRKET_SARTI, "Markanın Türkiye'de tescil belgesi bulunmalı (yurt içi marka tescil belgesi)",
                 "Destekten en fazla 4 yıl yararlanılabilir"],
        sure="En fazla 4 yıl", kaynak_limit=LIMIT_URGE),
    6: dict(
        baslik="Yurt Dışı Pazar Araştırması Desteği (5973 sayılı Karar m.6)",
        ozet="Yurt dışı pazar araştırması gezilerinin ulaşım ve konaklama giderlerinin %50'si desteklenir; yılda en çok "
             "5, toplamda en çok 20 faaliyet.",
        detay=("Şirketlerin yurt dışı pazar araştırması faaliyetine ilişkin ulaşım ve konaklama giderleri %50 oranında "
               "desteklenir; bir takvim yılında en çok 5, toplamda en çok 20 faaliyet (Karar m.6). 2026 üst limitleri: "
               "faaliyet başına toplam ulaşım ve konaklama 490.559 TL, kişi başı günlük konaklama 12.264 TL "
               "(Karar'daki 100.000 TL 2022 tabanıdır)."),
        hedef_kitle="Yeni bir ülkede satış kanalı, distribütör ya da pazaryeri araştıran ihracatçı şirketler",
        tesvil_tutari="%50; 2026'da faaliyet başına 490.559 TL, günlük konaklama kişi başı 12.264 TL; yılda en çok 5 "
                      "faaliyet", tutari_max=490_559,
        formul="Ulaşım+konaklama giderinin %50'si, faaliyet başına en çok 490.559 TL (2026); yılda 5, toplam 20 faaliyet",
        sartlar=[SIRKET_SARTI, "Bir takvim yılında en çok 5, toplamda en çok 20 pazar araştırması faaliyeti desteklenir",
                 "Desteklenen giderler: pazar araştırmasına ilişkin ulaşım ve konaklama"],
        sure="Faaliyet bazlı (yılda en çok 5, toplam 20)", kaynak_limit=LIMIT_URGE),
    11: dict(
        baslik="Yurt Dışı Birim Kira Desteği — Mağaza, Depo, Ofis (5973 sayılı Karar m.11)",
        ozet="Türkiye'de üretilen ürünlerin pazarlandığı yurt dışı mağaza, depo, ofis ve benzeri birimlerin kira giderinin "
             "%50'si desteklenir.",
        detay=("Şirketlerin Türkiye'de üretilen ürünlerin pazarlandığı yurt dışı birimlerinin kira giderleri ile paylaşımlı "
               "ofis üyelik giderleri her birim başına %50 oranında desteklenir; her ülke için en fazla 4 yıl, en fazla 25 "
               "birim (Karar m.11). Birim: yurt dışında açılan mağaza, depo, ofis/paylaşımlı ofis, sergi/teşhir salonu, "
               "reyon/raf/köşe/kiosk/stand (Karar m.2). Küresel tedarik zinciri desteğinin depo kirası kaleminden "
               "yararlananlar bu destekten yararlanamaz (m.11/4). 2026 üst limiti: birim başına yıllık 9.862.972 TL "
               "(Karar'daki 2.000.000 TL 2022 tabanıdır)."),
        hedef_kitle="Yurt dışında depo (ör. e-ihracat için ülke içi stok), mağaza ya da ofis kiralayan ihracatçı şirketler",
        tesvil_tutari="%50; 2026'da birim başına yıllık 9.862.972 TL; ülke başına en fazla 4 yıl, en fazla 25 birim",
        tutari_max=9_862_972,
        formul="Kira giderinin %50'si, birim başına yıllık en çok 9.862.972 TL (2026)",
        sartlar=[SIRKET_SARTI, "Birimde Türkiye'de üretilen ürünler pazarlanmalı",
                 "Her ülke için en fazla 4 yıl; şirket başına en fazla 25 birim",
                 "Küresel tedarik zinciri desteğinin (m.10/3) depo kirası kaleminden yararlanılmamış olmalı"],
        sure="Ülke başına en fazla 4 yıl", kaynak_limit=LIMIT_MARKA),
    12: dict(
        baslik="Yurt Dışı Tanıtım ve Pazarlama Desteği (5973 sayılı Karar m.12)",
        ozet="Türkiye'de üretilen ürünlerin yurt dışındaki tanıtım ve pazarlama (reklam) giderlerinin %50'si, en çok 4 yıl "
             "desteklenir; yurt dışı birimi olmayan şirket için hedef ülkede marka tescili ya da başvurusu şart.",
        detay=("Türkiye'de üretilen ürünlerle ilgili yurt dışında yapılan tanıtım ve pazarlama giderleri %50 oranında "
               "desteklenir; en fazla 4 yıl (Karar m.12). Üç durum: (1) yurt dışı birimi olan şirket, birimin bulunduğu her "
               "ülke için; (2) birimi olan şirket, birimi olmayan ülkelerde, yurt içi marka tescili ve o ülkede tescil ya da "
               "tescil başvurusu varsa; (3) birimi olmayan şirket, yurt içi marka tescili ve tanıtım yapılacak ülkede tescil "
               "ya da başvurusu varsa. 2026 üst limitleri: birime bağlı tanıtım ülke başına yıllık 12.329.397 TL; marka "
               "tesciline bağlı tanıtım yıllık 19.728.672 TL (Karar'daki 2.500.000 / 4.000.000 TL 2022 tabanıdır)."),
        hedef_kitle="Yurt dışında dijital reklam, pazaryeri reklamı ya da tanıtım yapan, markası tescilli ihracatçı şirketler",
        tesvil_tutari="%50; 2026'da birime bağlı ülke başına yıllık 12.329.397 TL, marka tesciline bağlı yıllık "
                      "19.728.672 TL; en fazla 4 yıl", tutari_max=19_728_672,
        formul="Tanıtım/pazarlama giderinin %50'si; 2026 yıllık üst limit 12.329.397 TL (birime bağlı, ülke başına) "
               "veya 19.728.672 TL (marka tesciline bağlı)",
        sartlar=[SIRKET_SARTI, "Tanıtımı yapılan ürünler Türkiye'de üretilmiş olmalı",
                 "Yurt dışı birimi yoksa: yurt içi marka tescil belgesi ve tanıtım yapılacak ülkede marka tescili ya da "
                 "tescil başvurusu olmalı",
                 "Destekten en fazla 4 yıl yararlanılabilir"],
        sure="En fazla 4 yıl", kaynak_limit=LIMIT_MARKA),
}


def kaynak(madde: int) -> str:
    return f"{KARAR}#madde-{madde}"


def uygula(db, dry_run: bool = True) -> tuple[int, int]:
    eklenen = atlanan = 0
    for madde, v in KAYITLAR.items():
        if db.query(Tesvik).filter(Tesvik.kaynak_url == kaynak(madde)).first():
            atlanan += 1
            print(f"   m.{madde}: zaten var, atlandı")
            continue
        print(f"[m.{madde}] {v['baslik']}\n      tutar: {v['tesvil_tutari']}\n      şart: {len(v['sartlar'])} madde")
        if not dry_run:
            db.add(Tesvik(
                kurum="Ticaret Bakanlığı", baslik=v["baslik"], ozet=v["ozet"], detay=v["detay"],
                hedef_kitle=v["hedef_kitle"], kaynak_url=kaynak(madde), kategori="e_ticaret_ihracat",
                tesvil_tutari=v["tesvil_tutari"], tutari_max=float(v["tutari_max"]), tutari_hesaplama_kriteri="genel",
                tutari_hesaplama_formulu=v["formul"], uygunluk_kriterleri=dict(ORTAK_KRITER),
                basvuru_sartlari=v["sartlar"], basvuru_yeri=BASVURU_YERI, destek_verilme_suresi=v["sure"],
                aktif_mi=True,
                durum_notu=(f"{NOT}: 5973 sayılı Karar m.{madde} (güncel metin {KARAR}) ve 2026 Destek Üst Limitleri "
                            f"({v['kaynak_limit']}); başvuru süresi ve belge listesi uygulama genelgesinden henüz "
                            f"doldurulmadı")))
        eklenen += 1
    if not dry_run:
        db.commit()
    return eklenen, atlanan


def _self_test() -> int:
    k = KAYITLAR
    kontroller = [
        ("5 madde: 3, 4, 6, 11, 12", sorted(k) == [3, 4, 6, 11, 12]),
        ("2026 limitleri tablodaki değerler", [k[m]["tutari_max"] for m in (3, 4, 6, 11, 12)]
         == [19_728_672, 3_698_274, 490_559, 9_862_972, 19_728_672]),
        ("tutar metni sayıyla tutarlı", all(_tl(v["tutari_max"]).replace(" TL", "") in v["tesvil_tutari"] for v in k.values())),
        ("kaynaklar benzersiz", len({kaynak(m) for m in k}) == len(k)),
        ("şahıs işletmesi şartı her kayıtta", all(SIRKET_SARTI in v["sartlar"] for v in k.values())),
        ("şirket türü kriteri şahıs ve şirketsizi dışlar", "sahis" not in ORTAK_KRITER["sirket_turleri"]
         and "yok" not in ORTAK_KRITER["sirket_turleri"]),
        ("belge listesi ve başvuru süresi uydurulmadı", all("gerekli_belgeler" not in v and "basvuru_suresi" not in v
                                                             for v in k.values())),
        ("fuar (m.7) bilerek dışarıda", 7 not in k),
    ]
    for ad, ok in kontroller:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    gecen = sum(ok for _, ok in kontroller)
    print(f"\nself-test: {gecen}/{len(kontroller)} geçti")
    return 0 if gecen == len(kontroller) else 1


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
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {n} kayıt eklendi, {atlanan} atlandı")
    finally:
        db.close()
