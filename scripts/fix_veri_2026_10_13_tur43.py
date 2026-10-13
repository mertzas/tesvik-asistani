"""Tur 43 — tarım destekleri 2027 ve çoban desteği, 3308 durumu (2026-10-13).

Tur41'in doğrulama altyapısını, tur42'nin yeni kayıt üreticisini kullanır; kaynak önbelleği
docs/olcum/2026-10-13-tur43/kaynak/. Resmî Gazete'deki Karar PDF'leri taramadır: o sayfalar PNG olarak önbellekte,
alıntılar görüntüden okundu ("gorsel" kanıt). Her değişiklik `--dogrula`'dan geçmeden uygulanmaz.

  YENİ  Sertifikalı Tohum Kullanım Desteği (2027 üretim yılı): 11781 sayılı CK (RG 08.09.2026, 33364) yeni Tablo 4/5,
        destek katsayı değeri 442 TL/da; 2027 belge teslim takvimi ilan edilmedi → aktif_mi belirsiz (None)
  YENİ  Sürü Yöneticisi (Çoban) İstihdam Desteği (2026): 430 TL/baş × 1,8 × 150 baş = 116.100 TL (8760; 10395 ve
        11782 ile değişik — hesap, Bakanlık sayfası henüz 2025 tutarını yazıyor); HAYGEM 2026 talimatı üç evrak dönemi
  365   Fidan: 2026 (367 TL, geriye dönük) ve 2027 (442 TL) dekar tutarları; 2026 belge teslimi 31.07.2026'da bitti,
        2027 takvimi yok → aktif_mi belirsiz
  367   3308 Geçici 12: RG fihristi 01.01.2025–13.10.2026 tarandı, uzatma ya da Kanun değişikliği yok; on yıllık
        yetki 2025-2026 sonunda doldu; Temmuz 2026 tarihli düzenleyici etki notu (taslak) 15 yıla çıkarmayı öneriyor

    python scripts/fix_veri_2026_10_13_tur43.py --self-test
    python scripts/fix_veri_2026_10_13_tur43.py --dogrula
    python scripts/fix_veri_2026_10_13_tur43.py --uygula        (yedek: tesvikler_oncesi_tur43.db.bak)
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

DIZIN = KOK / "docs/olcum/2026-10-13-tur43"
ONBELLEK = DIZIN / "kaynak"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur43.db.bak"
BUGUN = date(2026, 10, 13)
NOT = "Tur43 2026-10-13"


def _yukle(ad: str):
    spec = importlib.util.spec_from_file_location(ad, KOK / f"scripts/fix_veri_2026_10_13_{ad}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ONBELLEK, m.BUGUN = ONBELLEK, BUGUN
    return m


RG_11781 = "https://www.resmigazete.gov.tr/eskiler/2026/09/20260908-7.pdf"
RG_11782 = "https://www.resmigazete.gov.tr/eskiler/2026/09/20260908-8.pdf"
RG_10395 = "https://www.resmigazete.gov.tr/eskiler/2025/09/20250914-7.pdf"
RG_TEBLIG = "https://www.resmigazete.gov.tr/eskiler/2024/12/20241231M5.pdf"
COBAN = "https://www.tarimorman.gov.tr/Konular/Tarimsal-Destekler/Hayvancilik-Desteklemeleri/Suru-Yoneticisi-Istihdam-Destegi"
TALIMAT = ("https://www.tarimorman.gov.tr/HAYGEM/Belgeler/DB_Islah/TAL%C4%B0MATLAR/2026%20YILI/2026%20Y%C4%B1l%C4%B1%20"
           "K%C3%BC%C3%A7%C3%BCkba%C5%9F%20Hayvanc%C4%B1l%C4%B1k%20Desteklemeleri%20Uygulama%20Talimat%C4%B1%20ve%20"
           "%C3%87al%C4%B1%C5%9Fma%20Takvimi.pdf")
M3308 = "https://www.mevzuat.gov.tr/mevzuatmetin/1.5.3308.pdf"
DEA_3308 = "https://koto.org.tr/dokumanlar/9546898b9f91fd79253f810a6740a7fc.pdf"

GORSEL_11781 = [
    ("gorsel", "karar_11781_rg20260908_s1.png", "Resmî Gazete 8 Eylül 2026, Sayı 33364; Karar Sayısı: 11781 (7 Eylül 2026)"),
    ("gorsel", "karar_11781_rg20260908_s2.png",
     "MADDE 1 a) “310 TL olarak” ibaresi “367 TL olarak, 2027 üretim yılı için destek katsayı değeri dekara 442 TL "
     "olarak” şeklinde değiştirilmiştir. Tablo 4 (2027 Üretim Yılı Destek Katsayısı): Aspir, Kolza (Kanola), Susam "
     "0,20; Fiğ 0,50; Arpa, Buğday, Çavdar, Tritikale, Yulaf 0,56; Korunga 0,60; Mercimek 0,80; Nohut, Soya, "
     "Yerfıstığı, Yem Bezelyesi, Yonca 1,00; Çeltik, Fasulye (kuru) 1,50; Patates 2,20. Tablo 5: Ayçiçeği (yağlık) 0,6; "
     "Mısır 1,0; Patates (Tablo 4'e ilave) 2,0; Soya (Tablo 4'e ilave) 1,0"),
    ("gorsel", "karar_11781_rg20260908_s3.png",
     "MADDE 6- (1) a) 1 inci maddesinin (a) ve (ç) bentlerinde yer alan hükümler 1/1/2026 tarihinden itibaren geçerli "
     "olmak üzere yayımı tarihinde, c) Diğer hükümleri 1/1/2027 tarihinde, yürürlüğe girer."),
]
GORSEL_EK2 = ("gorsel", "teblig_2024_39_rg20241231m5_s248.png",
              "EK-2 Destekleme Uygulama Takvimi, 3.1 Sertifikalı Tohum Kullanım Desteği ve 3.2 Sertifikalı/Standart "
              "Fidan Kullanım Desteği: belge teslim başlangıcı “İlgili üretim yılı ÇKS kayıt başlangıç tarihi”, bitişi "
              "“İlgili üretim yılının Temmuz ayı son iş günü”, askı 5 (Beş) Gün, kesin icmal “İlgili üretim yılının "
              "Ağustos ayı”")
# PDF metin katmanında satır sonu tirelemesi var ("EK-/3", "mü-/racaatta"): alıntılar tireleme sınırında kesildi.
TEBLIG_M15 = [(RG_TEBLIG, "3’te yer alan Destekleme Ödemesi Başvuru Dilekçesi ile şahsen veya yasal temsilcisi"),
              (RG_TEBLIG, "Belge teslim bitiş tarihi sona eren desteklemeler için")]

TOHUM_2027 = {
    "sablon": 365, "kurum": "Tarım Bakanlığı", "kategori": "tarim",
    "baslik": "Sertifikalı Tohum Kullanım Desteği (2027 üretim yılı)",
    "ozet": "Sertifikalı tohum kullanan ÇKS'ye kayıtlı çiftçilere dekar başına ödenen üretimi geliştirme desteği. "
            "2027 üretim yılı için tutar = Tablo 4 katsayısı × 442 TL/da; yerli çeşitlerde Tablo 5 katsayısı ayrıca. "
            "2027 belge teslim takvimi henüz ilan edilmedi.",
    "detay": "11781 sayılı Cumhurbaşkanı Kararı (RG 08.09.2026, sayı 33364), 8859 sayılı Kararın 2025-2027 bitkisel "
             "üretim desteklerinde destek katsayı değerini 2026 için 367 TL'ye (1/1/2026'dan geçerli), 2027 için 442 "
             "TL'ye çıkardı ve sertifikalı tohum tablolarını 2027 üretim yılı için yeniden yazdı (1/1/2027'de "
             "yürürlüğe girer). Başvuru, Bitkisel Üretim Desteklemeleri Ödeme Tebliği (2024/39) m.15'e göre ÇKS'de "
             "kayıtlı olunan il/ilçe müdürlüğüne EK-3 dilekçesiyle yapılır; belge teslimi EK-2 takvimine göre ilgili "
             "üretim yılının ÇKS kayıt başlangıcından Temmuz ayının son iş gününe kadardır.",
    "kaynak_url": RG_11781, "basvuru_bicimi": "uretim_odeme", "aktif_mi": None,
    "uygunluk_kriterleri": {"sektorler": ["tarim"], "urun_listesi": [
        "aspir", "kolza", "kanola", "susam", "fiğ", "arpa", "buğday", "çavdar", "tritikale", "yulaf", "korunga",
        "mercimek", "nohut", "soya", "yer fıstığı", "yem bezelyesi", "yonca", "çeltik", "fasulye", "patates",
        "ayçiçeği", "mısır"]},
    "tesvil_tutari": "2027 üretim yılı, dekar başına (katsayı × 442 TL; hesap): aspir, kolza/kanola, susam 0,20 → 88,40 "
                     "TL; fiğ 0,50 → 221,00 TL; arpa, buğday, çavdar, tritikale, yulaf 0,56 → 247,52 TL; korunga 0,60 → "
                     "265,20 TL; mercimek 0,80 → 353,60 TL; nohut, soya, yer fıstığı, yem bezelyesi, yonca 1,00 → 442,00 "
                     "TL; çeltik, fasulye (kuru) 1,50 → 663,00 TL; patates 2,20 → 972,40 TL. Yerli çeşit (Tablo 5): "
                     "ayçiçeği (yağlık) 0,6 → 265,20 TL; mısır 1,0 → 442,00 TL; patates ilave 2,0 → 884,00 TL; soya "
                     "ilave 1,0 → 442,00 TL.",
    "basvuru_yeri": "ÇKS'de kayıtlı olduğunuz il/ilçe tarım ve orman müdürlüğü (EK-3 Destekleme Ödemesi Başvuru "
                    "Dilekçesi).",
    "basvuru_suresi": "2027 üretim yılı belge teslimi: 2027 ÇKS kayıt başlangıcından Temmuz 2027'nin son iş gününe "
                      "kadar (Tebliğ 2024/39 EK-2; kurala göre 30.07.2027). 2027 takvimi Bakanlıkça henüz ilan "
                      "edilmedi; bitiş tarihi geçen destek için başvuru yapılamaz.",
    "basvuru_sartlari": ["ÇKS'ye kayıtlı olmak ve ilgili üretim yılında sertifikalı tohum kullanmak",
                         "Belge teslim bitiş tarihinden önce EK-3 dilekçesiyle il/ilçe müdürlüğüne başvurmak"],
    "kontrol_listesi": [
        {"tur": "bilgi", "metin": "2027 destek katsayı değeri dekara 442 TL (2026: 367 TL)",
         "alinti": "2027 üretim yılı için destek katsayı değeri dekara 442 TL olarak", "kaynak_url": RG_11781,
         "dogrulandi": True},
        {"tur": "sart", "metin": "ÇKS'de kayıtlı olduğunuz il/ilçe müdürlüğüne EK-3 dilekçesiyle başvurun",
         "alinti": "EK-3’te yer alan Destekleme Ödemesi Başvuru Dilekçesi ile şahsen veya yasal temsilcisi "
                   "aracılığıyla başvuruda bulunurlar.", "kaynak_url": RG_TEBLIG, "dogrulandi": True},
        {"tur": "kural", "metin": "Belge teslim bitiş tarihi geçtiyse başvuru yapılamaz",
         "alinti": "Belge teslim bitiş tarihi sona eren desteklemeler için müracaatta bulunulamaz.",
         "kaynak_url": RG_TEBLIG, "dogrulandi": True}],
    "durum_notu": f"{NOT}: 11781 sayılı CK'dan (RG 08.09.2026, {RG_11781}; taranmış sayfa, görüntüden okundu) eklendi. "
                  "TL/da değerleri katsayı × 442 TL hesabıdır; Bakanlık birim fiyat sayfası hâlâ 310 TL tabanlı. "
                  "2027 belge teslim takvimi ilan edilince aktif yapılmalı.",
    "kanitlar": GORSEL_11781 + [GORSEL_EK2] + TEBLIG_M15,
}

COBAN_2026 = {
    "sablon": 76, "kurum": "Tarım Bakanlığı", "kategori": "tarim",
    "baslik": "Sürü Yöneticisi (Çoban) İstihdam Desteği (2026 yılı)",
    "ozet": "En az 150 baş kuzu/oğlağı olan ve sertifikalı çoban istihdam edip SGK primini yıl içinde 5 ay yatıran "
            "küçükbaş işletmelerine, bir sürü yöneticisi için 150 baş üzerinden ödenen destek. 2026 için hesaplanan "
            "tutar 116.100 TL/işletme.",
    "detay": "Dayanak: 2024-2026 Hayvancılık Desteklemeleri Kararı (8760), 10395 sayılı Kararla değişik 2/1-b-4 alt "
             "bendi (150 baş üzerinden ilave 1,8 katsayı) ve 11782 sayılı Karar (2026 kuzu/oğlak temel desteği 430 "
             "TL/baş). Başvuru küçükbaş hayvancılık desteği başvurusuyla başlar; çoban belgeleri HAYGEM 2026 küçükbaş "
             "talimatındaki üç dönemde il/ilçe müdürlüğüne teslim edilir.",
    "kaynak_url": COBAN, "basvuru_bicimi": "uretim_odeme", "aktif_mi": True,
    "uygunluk_kriterleri": {"sektorler": ["tarim"], "alt_kategori": "hayvancilik", "genislik": "dar"},
    "tesvil_tutari": "2026: 116.100 TL/işletme (hesap: 430 TL/baş × ilave 1,8 katsayı × 150 baş; tek sürü yöneticisi, "
                     "yalnız 150 baş üzerinden). Önceki yıllar Bakanlık sayfasından: 2024 için 36.000 TL, 2025 için "
                     "81.000 TL.",
    "basvuru_yeri": "İl/ilçe tarım ve orman müdürlüğü (küçükbaş hayvancılık desteği başvurusuyla başlar; çoban "
                    "evrakı dönem sonuna kadar teslim edilir).",
    "basvuru_suresi": "2026 yılı çoban evrak teslimi (HAYGEM 2026 küçükbaş talimatı): 1. dönem 05/01/2027, 2. dönem "
                      "15/06/2027, 3. dönem 19/11/2027'ye kadar. Küçükbaş 1. dönem başvuruları 01/09/2026–01/12/2026.",
    "basvuru_sartlari": ["Temel destek şartlarını sağlayan en az 150 baş kuzu/oğlak",
                         "Sertifikalı çoban istihdamı ve çobanın SGK primlerinin yıl içinde 5 ay yatırılması",
                         "En fazla bir sürü yöneticisi için, yalnız 150 baş üzerinden ödeme"],
    "kontrol_listesi": [
        {"tur": "sart", "metin": "En az 150 baş kuzu/oğlak, sertifikalı çoban ve 5 ay SGK primi",
         "alinti": "en az 150 baş kuzu/oğlağı bulunan işletmelere en fazla bir sürü yöneticisi için ve sadece 150 baş "
                   "üzerinden sertifikalı çoban istihdamı yapmış olan ve istihdamı yapılan çobanın Sosyal Güvenlik "
                   "Kurumu sigorta primlerini yıl içinde 5 ay süre ile yatıranlar", "kaynak_url": COBAN,
         "dogrulandi": True},
        {"tur": "adim", "metin": "Önce küçükbaş hayvancılık desteğine başvurun",
         "alinti": "Desteklemeye başvurular, Küçükbaş Hayvancılık Desteklemesine başvuru yapılması ile başlamaktadır.",
         "kaynak_url": COBAN, "dogrulandi": True},
        {"tur": "adim", "metin": "1. dönem çoban evrakını 05/01/2027'ye kadar il/ilçe müdürlüğüne teslim edin",
         "alinti": "İl/İlçe Müdürlüklerine Evrakların teslimi: 05/01/2027 ya kadar", "kaynak_url": TALIMAT,
         "dogrulandi": True}],
    "cagrilar": [
        {"ad": "2026 yılı 1. dönem evrak teslimi", "kapanis": date(2027, 1, 5), "kaynak_url": TALIMAT,
         "notlar": "Başvuruların HDS'de onayı 09/01/2027'ye kadar."},
        {"ad": "2026 yılı 2. dönem evrak teslimi", "kapanis": date(2027, 6, 15), "kaynak_url": TALIMAT,
         "notlar": "Başvuruların HDS'de onayı 01/07/2027'ye kadar."},
        {"ad": "2026 yılı 3. dönem evrak teslimi", "kapanis": date(2027, 11, 19), "kaynak_url": TALIMAT,
         "notlar": "Başvuruların HDS'de onayı 30/11/2027'ye kadar."}],
    "durum_notu": f"{NOT}: 2026 tutarı Kararlardan hesaplandı (8760 m.2/1-b-4, 10395 ile değişik; 11782 kuzu/oğlak 430 "
                  f"TL/baş; taranmış sayfalar görüntüden okundu: {RG_10395}, {RG_11782}). Bakanlık sayfası 2026 "
                  "tutarını henüz yazmıyor; takvim HAYGEM 2026 küçükbaş talimatından.",
    "kanitlar": [
        ("gorsel", "karar_10395_rg20250914_s2.png",
         "“4) Temel destek şartlarını sağlayan en az 150 baş kuzu/oğlağı bulunan işletmelere en fazla bir sürü "
         "yöneticisi için ve sadece 150 baş üzerinden ilave 1,8 katsayı.”"),
        ("gorsel", "karar_11782_rg20260908_s2.png",
         "“ve en az 4 ay (120 gün) yaşamış oğlak/kuzularına 2026 yılı için 430 TL/baş”"),
        (COBAN, "Kurumu sigorta primlerini yıl içinde 5 ay süre ile yatıranlar desteklemeye başvuruda "
                "bulunabilmektedir."),
        (COBAN, "Desteklemeye başvurular, Küçükbaş Hayvancılık Desteklemesine başvuru yapılması ile başlamaktadır."),
        (COBAN, "36.000 TL destekleme ödemesi yapılmıştır"),
        (COBAN, "81.000 TL destekleme ödemesi yapılacaktır"),
        (TALIMAT, "Sürü Yöneticisi (Çoban) İstihdamı Desteklemesi Çalışma Takvimi"),
        (TALIMAT, "İl/İlçe Müdürlüklerine Evrakların teslimi: 05/01/2027 ya kadar"),
        (TALIMAT, "İl/İlçe Müdürlüklerine Evrakların teslimi: 15/06/2027 ya kadar"),
        (TALIMAT, "İl/İlçe Müdürlüklerine Evrakların teslimi: 19/11/2027 ya kadar"),
        (TALIMAT, "Başvuruların HDS de onaylanması: 09/01/2027 ya kadar"),
        (TALIMAT, "01/09/2026 tarihinde başlar ve 01/12/2026 tarihi mesai bitiminde son bulur.")],
}

YENI_KAYITLAR: list[dict] = [TOHUM_2027, COBAN_2026]

DEGISIKLIKLER: list[dict] = [
    {"id": 365, "alanlar": {
        "aktif_mi": None,
        "tesvil_tutari": "Dekar başına katsayı × destek katsayı değeri; katsayılar standart fidan 2, sertifikalı fidan "
                         "5 (8859 Tablo 6). 2026 (367 TL, 11781 ile 1/1/2026'dan geçerli): standart 734 TL/da, "
                         "sertifikalı 1.835 TL/da. 2027 (442 TL): standart 884 TL/da, sertifikalı 2.210 TL/da (hesap). "
                         "Tablo 6 türleri: altıntop, armut, asma, ayva, badem, ceviz, dut, elma, erik, fındık, incir, "
                         "kayısı, kestane, kiraz, kivi, limon, mandarin, nektarin, pikan cevizi, portakal, şeftali, "
                         "Trabzon hurması, vişne, zeytin.",
        "basvuru_suresi": "2026 üretim yılı belge teslimi Temmuz 2026'nın son iş gününde (31.07.2026) bitti. 2027 "
                          "üretim yılı: 2027 ÇKS kayıt başlangıcından Temmuz 2027'nin son iş gününe kadar (Tebliğ "
                          "2024/39 EK-2); 2027 takvimi henüz ilan edilmedi."},
     "not": f"{NOT}: 2026 belge teslimi bitti, 2027 takvimi yok → aktif belirsiz; 2026 ve 2027 dekar tutarları 11781 "
            f"sayılı CK'dan (RG 08.09.2026, {RG_11781}; taranmış sayfa) hesaplandı. Fidan tablosu (Tablo 6) "
            "11781 ile değişmedi.",
     "kanitlar": GORSEL_11781 + [GORSEL_EK2] + TEBLIG_M15[1:]},
    {"id": 367, "alanlar": {
        "basvuru_suresi": "Geçici 12. madde ödemeleri Cumhurbaşkanı Kararıyla en fazla on eğitim yılına kadar "
                          "uzatılabilir; son uzatma (5063 sayılı Karar, RG 5/1/2022) 2025-2026 eğitim yılı sonunda "
                          "doldu. 2026-2027 için uzatma ya da Kanun değişikliği Resmî Gazete'de yok (01.01.2025–"
                          "13.10.2026 tarandı). Temmuz 2026 tarihli bir düzenleyici etki notu süreyi 15 eğitim yılına "
                          "çıkaran Kanun değişikliğini değerlendiriyor (taslak). MEB ya da İŞKUR'dan teyit edin."},
     "not": f"{NOT}: Resmî Gazete günlük fihristi 01.01.2025–13.10.2026 (3308/çırak/staj/mesleki eğitim) tarandı; "
            f"Geçici 12 için uzatma ya da değişiklik yok. Taslak bilgi notu (resmî değil, {DEA_3308}) yasalaşmadı; "
            "kayıt kararsız kalır.",
     "kanitlar": [(M3308, "Bu kapsamda yapılacak ödemeleri on eğitim ve öğretim yılına kadar uzatmaya Cumhurbaşkanı "
                          "yetkilidir."),
                  (DEA_3308, "olması, uygulamanın devamı bakımından hukuki belirsizlik oluşturabilecektir."),
                  (DEA_3308, "“15 eğitim ve öğretim yılına kadar” şeklinde değiştirilmesi değerlendirilmektedir.")]},
]


def main() -> int:
    arg = sys.argv[1:]
    if "--self-test" in arg:
        return _self_test()
    t41, t42 = _yukle("tur41"), _yukle("tur42")
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
    t42.NOT = NOT
    db = SessionLocal()
    try:
        for d in DEGISIKLIKLER:
            print(f"[{d['id']}] {t41.uygula(db, d) or 'değişiklik yok'}")
        for t in YENI_KAYITLAR:
            print(f"[yeni] {t42.yeni_kayit(db, t) or 'zaten var: ' + t['baslik']}")
        db.commit()
    finally:
        db.close()
    return 0


def _self_test() -> int:
    tablo4 = {0.20: 88.40, 0.50: 221.00, 0.56: 247.52, 0.60: 265.20, 0.80: 353.60, 1.00: 442.00, 1.50: 663.00,
              2.20: 972.40}
    gorseller = [k[1] for d in DEGISIKLIKLER + YENI_KAYITLAR for k in d["kanitlar"] if k[0] == "gorsel"]
    k = [("her değişikliğin kanıtı var", all(d.get("kanitlar") for d in DEGISIKLIKLER + YENI_KAYITLAR)),
         ("tohum TL/da = katsayı × 442 ve metinde aynı", all(
             round(kat * 442, 2) == tl and f"{kat:.2f} → {tl:.2f} TL".replace(".", ",") in TOHUM_2027["tesvil_tutari"]
             for kat, tl in tablo4.items())),
         ("fidan 2026/2027 = 2 ve 5 × 367/442", [2 * 367, 5 * 367, 2 * 442, 5 * 442] == [734, 1835, 884, 2210]),
         ("çoban 430 × 1,8 × 150 = 116.100", round(430 * 1.8 * 150) == 116_100
                                              and "116.100" in COBAN_2026["tesvil_tutari"]),
         ("tohum ve fidan aktif belirsiz, çoban aktif", TOHUM_2027["aktif_mi"] is None
          and DEGISIKLIKLER[0]["alanlar"]["aktif_mi"] is None and COBAN_2026["aktif_mi"] is True),
         ("görsel kanıt dosyaları önbellekte", all((ONBELLEK / g).exists() for g in gorseller)),
         ("yeni kayıt başlıkları tekil", len({t["baslik"] for t in YENI_KAYITLAR}) == len(YENI_KAYITLAR)),
         ("tur41/tur42 altyapısı yüklenir", callable(_yukle("tur41").dogrula) and callable(_yukle("tur42").yeni_kayit))]
    g = sum(1 for _, ok in k if ok)
    for ad, ok in k:
        print(f"  [{'OK' if ok else 'HATA'}] {ad}")
    print(f"tur43 self-test: {g}/{len(k)}")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    sys.exit(main())
