"""Tur 42 — çağrı keşif kuyruğu ve KGF özetleri (2026-10-13).

Tur41'in doğrulama altyapısını kullanır (scripts/fix_veri_2026_10_13_tur41.py: dogrula, uygula, yeni kayıt); kaynak
önbelleği docs/olcum/2026-10-13-tur42/kaynak/. Her değişiklik resmî kaynakta birebir alıntıyla `--dogrula`'dan geçmeden
uygulanmaz.

  KGF 93, 116, 125, 153, 154, 171, 173: özet site menüsüydü → kaynak sayfanın "Ürün açıklaması" metni
  KUYRUK: app/cagri_kesif kuyruğundaki adaylar (çağrı satırları, yeni kayıtlar) — aşağıda DEGISIKLIKLER/YENI_KAYITLAR

    python scripts/fix_veri_2026_10_13_tur42.py --self-test
    python scripts/fix_veri_2026_10_13_tur42.py --dogrula
    python scripts/fix_veri_2026_10_13_tur42.py --uygula        (yedek: tesvikler_oncesi_tur42.db.bak)
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DIZIN = KOK / "docs/olcum/2026-10-13-tur42"
ONBELLEK = DIZIN / "kaynak"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur42.db.bak"
BUGUN = date(2026, 10, 13)
NOT = "Tur42 2026-10-13"


def _tur41():
    spec = importlib.util.spec_from_file_location("tur41", KOK / "scripts/fix_veri_2026_10_13_tur41.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ONBELLEK, m.BUGUN = ONBELLEK, BUGUN
    return m


DEGISIKLIKLER: list[dict] = [
    {"id": 93, "alanlar": {"ozet": "1136 sayılı Avukatlık Kanunu’nun 43’üncü maddesinin son fıkrası gereğince finansmana erişimde güçlük yaşayan avukatların mevcut bürolarının veya yeni büro kurma giderlerinin karşılanması için uygun şartlarda finansman desteği sunulması amaçlanmaktadır."},
     "not": f"{NOT}: özet kaynak sayfanın 'Ürün açıklaması' bölümünden (önceki özet site menüsüydü).",
     "kanitlar": [("https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/vakifbank-hukuk-burosu-destek-paketi", "1136 sayılı Avukatlık Kanunu’nun 43’üncü maddesinin son fıkrası gereğince finansmana erişimde güçlük yaşayan avukatların mevcut bürolarının veya yeni büro kurma giderlerinin karşılanması için uygun şartlarda finansman desteği sunulması amaçlanmaktadır.")]},
    {"id": 116, "alanlar": {"ozet": "Kooperatif ve kooperatif birliği tüzel kişilerinin finansmana erişimlerinin kolaylaştırılarak Kredi Verenlerden ödemesiz dönem imkanıyla kredi kullanmaları yoluyla nakit akışlarının etkinliğinin arttırılması amaçlanmaktadır."},
     "not": f"{NOT}: özet kaynak sayfanın 'Ürün açıklaması' bölümünden (önceki özet site menüsüydü).",
     "kanitlar": [("https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/kgf-kooperatif-destek-paketi", "Kooperatif ve kooperatif birliği tüzel kişilerinin finansmana erişimlerinin kolaylaştırılarak Kredi Verenlerden ödemesiz dönem imkanıyla kredi kullanmaları yoluyla nakit akışlarının etkinliğinin arttırılması amaçlanmaktadır.")]},
    {"id": 125, "alanlar": {"ozet": "İmalat sektöründe faaliyet gösteren KOBİ’lerin dijital dönüşüm için yapacakları yatırımlarına yönelik finansman desteği sağlanması amaçlanmaktadır."},
     "not": f"{NOT}: özet kaynak sayfanın 'Ürün açıklaması' bölümünden (önceki özet site menüsüydü).",
     "kanitlar": [("https://www.kgf.com.tr/index.php/tr/urunlerimiz/hazine-destekli-kefaletler/aktif-destek-paketleri-2025/2024-dijital-donusum-destek-paketi", "İmalat sektöründe faaliyet gösteren KOBİ’lerin dijital dönüşüm için yapacakları yatırımlarına yönelik finansman desteği sağlanması amaçlanmaktadır.")]},
    {"id": 153, "alanlar": {"ozet": "Avrupa İmar ve Kalkınma Bankasından (EBRD) sağlanan kaynağa istinaden TURYIB Programı kapsamında genç sahibi ve/veya yöneticisi bulunan işletmelere destek sağlanarak gençlerin iş hayatına daha fazla katılımı amaçlanmaktadır."},
     "not": f"{NOT}: özet kaynak sayfanın 'Ürün açıklaması' bölümünden (önceki özet site menüsüydü).",
     "kanitlar": [("https://www.kgf.com.tr/index.php/tr/urunlerimiz/hazine-destekli-kefaletler/aktif-destek-paketleri-2025/turyib-programi-destek-paketi", "Avrupa İmar ve Kalkınma Bankasından (EBRD) sağlanan kaynağa istinaden TURYIB Programı kapsamında genç sahibi ve/veya yöneticisi bulunan işletmelere destek sağlanarak gençlerin iş hayatına daha fazla katılımı amaçlanmaktadır.")]},
    {"id": 154, "alanlar": {"ozet": "Kurumumuzca Bankalardan yoğun bir şekilde alınan kefalet limiti taleplerini karşılayabilmek ve KOBİ’lere sağlanan desteğin devamlılığını temin etmek amacıyla, Kurumumuz özkaynaklarından verilmek üzere oluşturulan KGF Genel Destek Programı devreye alınmıştır."},
     "not": f"{NOT}: özet kaynak sayfanın 'Ürün açıklaması' bölümünden (önceki özet site menüsüydü).",
     "kanitlar": [("https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/kgf-genel-destek-programi", "Kurumumuzca Bankalardan yoğun bir şekilde alınan kefalet limiti taleplerini karşılayabilmek ve KOBİ’lere sağlanan desteğin devamlılığını temin etmek amacıyla, Kurumumuz özkaynaklarından verilmek üzere oluşturulan KGF Genel Destek Programı devreye alınmıştır.")]},
    {"id": 171, "alanlar": {"ozet": "Katılım Bankacılığı ilke ve esaslarına uygun finansman modeline kefalet sağlanması amaçlanmaktadır."},
     "not": f"{NOT}: özet kaynak sayfanın 'Ürün açıklaması' bölümünden (önceki özet site menüsüydü).",
     "kanitlar": [("https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/ziraat-katilim-bankasi-katilim-finans-destek-paketi", "Katılım Bankacılığı ilke ve esaslarına uygun finansman modeline kefalet sağlanması amaçlanmaktadır.")]},
    {"id": 173, "alanlar": {"ozet": "Basın İlan Kurumu’ndan resmi ilan ve reklam alma hakkına haiz süreli yayınların, bankalardan alacakları nakdi ve/veya gayrinakdi krediye erişimlerini kolaylaştırmak amaçlanmaktadır."},
     "not": f"{NOT}: özet kaynak sayfanın 'Ürün açıklaması' bölümünden (önceki özet site menüsüydü).",
     "kanitlar": [("https://www.kgf.com.tr/index.php/tr/urunlerimiz/ozkaynak-kefaletlerimiz/banka-kredileri/kgf-tematik-destek-programlari/vakifbank-basin-ilan-kurumu-destek-paketi", "Basın İlan Kurumu’ndan resmi ilan ve reklam alma hakkına haiz süreli yayınların, bankalardan alacakları nakdi ve/veya gayrinakdi krediye erişimlerini kolaylaştırmak amaçlanmaktadır.")]},
]
YENI_KAYITLAR: list[dict] = []

AHIKA_DUYURU = ("https://www.ahika.gov.tr/duyurular/2026-yili-sanayide-verimlilik-kalite-ve-kurumsallasma-teknik-destek-"
                "programi-ilan-edildi")
GLOBALSTARS = "https://tubitak.gov.tr/tr/duyuru/eureka-globalstars-japonya-2026-cagrisi-acildi"
SBEP = ("https://tubitak.gov.tr/tr/duyuru/ufuk-avrupa-programi-surdurulebilir-mavi-ekonomi-ortakligi-sbep-2026-yili-cok-"
        "uluslu-ortak-cagrisi-basvuruya-acildi")
DIKA_TD = "https://www.dika.org.tr/duyuru/2026-yili-teknik-destek-programi-ilani/298"
DIKA_REHBER = "docs/olcum/2026-10-13-tur42/kaynak/dika_td_2026_rehber.txt"
DIKA_REHBER_URL = "https://www.dika.org.tr/assets/user_files/TD_BA%C5%9EVURU_REHBER%C4%B0.rar"

KUYRUK: list[dict] = [
    {"id": 197, "not": f"{NOT}: Eylül-Ekim dönemi çağrı satırı (çağrı keşif kuyruğu).",
     "cagrilar": [{"ad": "2026 Eylül-Ekim dönemi", "acilis": date(2026, 9, 7), "kapanis": date(2026, 10, 30),
                   "kaynak_url": AHIKA_DUYURU,
                   "notlar": "Son başvuru 30.10.2026 saat 17.00 (KAYS); Kasım-Aralık dönemi 31.12.2026 17.00."}],
     "kanitlar": [(AHIKA_DUYURU, "Eylül - Ekim Dönemi Son Başvuru Günü: 30.10.2026 Saat: 17.00"),
                  (AHIKA_DUYURU, "Kasım – Aralık Dönemi Son Başvuru Günü: 31.12.2026 Saat: 17.00")]},
    {"id": 39, "not": f"{NOT}: Eureka Globalstars Japonya 2026 çağrısı 1509 üzerinden (çağrı keşif kuyruğu).",
     "cagrilar": [{"ad": "Eureka Globalstars Japonya 2026 (uluslararası takvim)", "acilis": date(2026, 10, 7),
                   "kapanis": date(2027, 1, 20), "kaynak_url": GLOBALSTARS,
                   "notlar": "Türkiye ve Japonya'dan en az birer şirketle konsorsiyum; Türkiye'den yalnız sermaye "
                             "şirketleri. Ulusal (1509, PRODİS) tarihler TÜBİTAK tarafından e-postayla bildirilecek."}],
     "kanitlar": [(GLOBALSTARS, "Uluslararası Başvuruların Başlangıç Tarihi: 7 Ekim 2026"),
                  (GLOBALSTARS, "Uluslararası Başvuru Son Tarihi: 20 Ocak 2027"),
                  (GLOBALSTARS, "Ulusal başvuruya ilişkin tarihler TÜBİTAK tarafından e-posta yoluyla bildirilecektir."),
                  (GLOBALSTARS, "Türkiye'den başvuracak kuruluşların Türkiye'de kurulmuş sermaye şirketi statüsünde "
                                "olması gerekmektedir.")]},
    {"id": 29, "not": f"{NOT}: SBEP 2026 ortak çağrısı 1071 üzerinden (çağrı keşif kuyruğu).",
     "cagrilar": [{"ad": "Ufuk Avrupa SBEP 2026 ortak çağrısı (1. aşama ön proje)", "kapanis": date(2026, 11, 23),
                   "kaynak_url": SBEP,
                   "notlar": "Uluslararası ön proje son günü 16.11.2026 15:00 CET; ulusal başvuru 23.11.2026 23:59; "
                             "e-imza 26.11.2026 23:59. En az üç ülkeden konsorsiyum."}],
     "kanitlar": [(SBEP, "1. Aşama (Ön-Proje) Uluslararası Başvuru Son Tarihi: 16 Kasım 2026 (15:00, CET)"),
                  (SBEP, "1. Aşama (Ön-Proje) Ulusal Başvuru Son Tarihi: 23 Kasım 2026 (23:59, TSİ)"),
                  (SBEP, "1. Aşama (Ön-Proje) Ulusal Başvuru E-imza için Son Tarihi: 26 Kasım 2026 (23:59, TSİ)")]},
]
DEGISIKLIKLER += KUYRUK

YENI_KAYITLAR.append({
    "sablon": 197, "kurum": "Dicle Kalkınma Ajansı (DİKA)",
    "baslik": "DİKA 2026 Yılı Teknik Destek Programı (TRC3/26/TD)",
    "ozet": "Batman, Mardin, Siirt ve Şırnak'ta eğitim ve danışmanlık ihtiyacını Ajansın karşıladığı teknik destek; "
            "doğrudan ödeme ve eş finansman yok. Kâr amacı güden gerçek ve tüzel kişiler yılda bir başvurabilir.",
    "detay": "Öncelikler: tarım ve yerel ürünler, turizm, yatırım ortamı ve girişimcilik, yerel kalkınma ve kurumsal "
             "kapasite. Başvurular yıl boyunca KAYS üzerinden alınır, iki aylık dönemler hâlinde değerlendirilir.",
    "kaynak_url": DIKA_TD, "basvuru_bicimi": "diger",
    "uygunluk_kriterleri": {"sektorler": ["genel"], "bolge_kisitli": ["batman", "mardin", "siirt", "şırnak"]},
    "tesvil_tutari": "Teknik destek hizmeti (doğrudan ödeme yok): eğitim için 250.000 TL'ye, danışmanlık için 350.000 "
                     "TL'ye kadar (KDV hariç); 2026 toplam yıllık tutar 5.000.000 TL; eş finansman yok; en fazla 6 ay.",
    "basvuru_yeri": "Kalkınma Ajansları Yönetim Sistemi (KAYS)",
    "basvuru_suresi": "Yıl boyunca sürekli; Eylül-Ekim dönemi son başvuru 30.10.2026, Kasım-Aralık dönemi 31.12.2026.",
    "kontrol_listesi": [
        {"tur": "sart", "metin": "Başvuru sahibi TRC3 Bölgesi'nde (Batman, Mardin, Siirt, Şırnak) kayıtlı olmalı",
         "alinti": "TRC3 Düzey 2 Bölgesi’nde (Batman, Mardin, Siirt, Şırnak),", "kaynak_url": DIKA_TD,
         "dogrulandi": True},
        {"tur": "kural", "metin": "Kâr amacı güden gerçek ve tüzel kişiler yılda en fazla 1 başvuru ile desteklenir",
         "alinti": "kâr amacı güden diğer gerçek ve tüzel kişiler için 1 (bir) adet ile sınırlandırılmıştır.",
         "kaynak_url": DIKA_REHBER_URL, "dogrulandi": True},
        {"tur": "bilgi", "metin": "Doğrudan ödeme yapılmaz; eğitim ya da danışmanlık hizmeti Ajans tarafından sağlanır",
         "alinti": "Program kapsamında yararlanıcı kuruluşa herhangi bir doğrudan mali destek verilmemektedir",
         "kaynak_url": DIKA_TD, "dogrulandi": True},
        {"tur": "bilgi", "metin": "Yararlanıcıdan eş finansman (nakdi katkı) istenmez",
         "alinti": "yararlanıcı kuruluştan herhangi bir eş finansman (nakdi katkı) talep edilmemektedir.",
         "kaynak_url": DIKA_REHBER_URL, "dogrulandi": True},
        {"tur": "adim", "metin": "Başvuruyu yap: Kalkınma Ajansları Yönetim Sistemi (KAYS)"}],
    "cagrilar": [{"ad": "2026 Eylül-Ekim dönemi", "kapanis": date(2026, 10, 30), "kaynak_url": DIKA_TD,
                  "notlar": "KAYS son başvuru 30.10.2026; taahhütname 06.11.2026 17:00. Kasım-Aralık dönemi 31.12.2026."},
                 {"ad": "2026 Kasım-Aralık dönemi", "acilis": date(2026, 11, 1), "kapanis": date(2026, 12, 31),
                  "kaynak_url": DIKA_TD, "notlar": "Taahhütname 08.01.2027 17:00."}],
    "kanitlar": [(DIKA_TD, "Kâr amacı güden diğer gerçek ve tüzel kişiler"),
                 (DIKA_TD, "TRC3 Düzey 2 Bölgesi’nde (Batman, Mardin, Siirt, Şırnak),"),
                 (DIKA_TD, "Program kapsamında yararlanıcı kuruluşa herhangi bir doğrudan mali destek verilmemektedir"),
                 (DIKA_TD, "Eğitim için: 250.000 TL (KDV hariç)"),
                 (DIKA_TD, "Danışmanlık vb. için: 350.000 TL (KDV hariç)"),
                 (DIKA_TD, "toplam yıllık tutar 5.000.000 TL’dir."),
                 (DIKA_TD, "Teknik destek başvuruları yıl boyunca sürekli olarak alınır."),
                 (DIKA_TD, "30.10.2026"), (DIKA_TD, "31.12.2026"),
                 ("dosya", DIKA_REHBER, "kâr amacı güden diğer gerçek ve tüzel kişiler için 1 (bir) adet ile "
                                        "sınırlandırılmıştır."),
                 ("dosya", DIKA_REHBER, "yararlanıcı kuruluştan herhangi bir eş finansman (nakdi katkı) talep "
                                        "edilmemektedir."),
                 ("dosya", DIKA_REHBER, "En fazla 6 ay")]})


def main() -> int:
    arg = sys.argv[1:]
    if "--self-test" in arg:
        return _self_test()
    t41 = _tur41()
    tur21 = t41._tur21()
    hata_var = False
    for d in DEGISIKLIKLER + YENI_KAYITLAR:
        hatalar = t41.dogrula(d, tur21.metin_al, tur21.norm)
        print(f"[{d.get('id') or d['baslik'][:44]}] {'GEÇTİ' if not hatalar else 'KALDI'} "
              f"({len(d.get('kanitlar', []))} kanıt)")
        for h in hatalar:
            print(f"    {h}")
        hata_var |= bool(hatalar)
    if "--uygula" not in arg:
        return 1 if hata_var else 0
    if hata_var:
        print("Kanıtı geçmeyen değişiklik var; hiçbir şey uygulanmadı.")
        return 1
    from app.models import SessionLocal, settings
    if not YEDEK.exists():
        shutil.copy2(Path(settings.DATABASE_URL.replace("sqlite:///", "")), YEDEK)
        print(f"yedek: {YEDEK}")
    db = SessionLocal()
    try:
        for d in DEGISIKLIKLER:
            print(f"[{d['id']}] {t41.uygula(db, d) or 'değişiklik yok'}")
        for t in YENI_KAYITLAR:
            print(f"[yeni] {yeni_kayit(db, t) or 'zaten var: ' + t['baslik']}")
        db.commit()
    finally:
        db.close()
    return 0


def yeni_kayit(db, tanim: dict) -> str | None:
    """Başlığı olmayan kaydı şablon kayıttan (tanim["sablon"]) üretir; varsa dokunmaz."""
    from app.models import Tesvik
    if db.query(Tesvik).filter(Tesvik.baslik == tanim["baslik"]).first() is not None:
        return None
    sablon = db.get(Tesvik, tanim["sablon"])
    alanlar = {k: v for k, v in tanim.items() if k not in ("kanitlar", "sablon", "cagrilar")}
    alanlar.setdefault("kurum", sablon.kurum)
    alanlar.setdefault("kategori", sablon.kategori)
    alanlar.setdefault("uygunluk_kriterleri", dict(sablon.uygunluk_kriterleri or {}))
    alanlar.setdefault("basvuru_bicimi", sablon.basvuru_bicimi)
    alanlar.setdefault("aktif_mi", True)
    alanlar.setdefault("durum_notu", f"{NOT}: çağrı keşif kuyruğundan, resmî ilan ve rehberden eklendi.")
    t = Tesvik(**alanlar)
    db.add(t)
    db.flush()
    from app.models import TesvikCagrisi
    for c in tanim.get("cagrilar", []):
        db.add(TesvikCagrisi(tesvik_id=t.id, dogrulama_tarihi=BUGUN, **c))
    return tanim["baslik"]


def _self_test() -> int:
    kimlikler = [d["id"] for d in DEGISIKLIKLER]
    k = [("her değişikliğin kanıtı var", all(d.get("kanitlar") for d in DEGISIKLIKLER + YENI_KAYITLAR)),
         ("kimlikler tekil", len(kimlikler) == len(set(kimlikler))),
         ("yeni kayıt başlıkları tekil", len({t["baslik"] for t in YENI_KAYITLAR}) == len(YENI_KAYITLAR)),
         ("yeni kayıtların şablonu var", all(isinstance(t.get("sablon"), int) for t in YENI_KAYITLAR)),
         ("KGF özetleri alıntıyla aynı", all(d["alanlar"]["ozet"] == d["kanitlar"][0][1]
                                            for d in DEGISIKLIKLER if d["id"] in (93, 116, 125, 153, 154, 171, 173))),
         ("tur41 altyapısı yüklenir", callable(_tur41().dogrula))]
    g = sum(1 for _, ok in k if ok)
    for ad, ok in k:
        print(f"  [{'OK' if ok else 'HATA'}] {ad}")
    print(f"tur42 self-test: {g}/{len(k)}")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    sys.exit(main())
