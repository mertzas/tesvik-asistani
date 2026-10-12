"""Tur 41 — açık kalan veri boşlukları (2026-10-13, eksik envanteri: DURUM.md "Açık" + veritabanı taraması).

Her değişiklik resmî kaynaktaki birebir alıntıya dayanır. `--dogrula` kaynakları indirir (önbellek
docs/olcum/2026-10-13-tur41/kaynak/, tur21 metin_al) ve her alıntıyı normalleştirilmiş metinde arar; geçmeyen değişiklik
uygulanmaz. Taranmış Resmî Gazete sayfaları (metin katmanı yok) görüntü olarak saklanır ve "görüntüden doğrulandı"
işaretlidir (insan okuması 2026-10-13).

  37  TÜBİTAK 4003: açık çağrı (4003-T Millî Teknoloji Atölyeleri) → aktif; başvuru yeri, süre, üst limit
  73  TÜBİTAK 1000: açık çağrı yok (son bulunan 2015/2016) → pasif
  48  1709 Eurostars: 2026/2 ulusal çağrısı (kapandı) ve Eurostars Call 12 (17.12.2026 – 4.3.2027) çağrı satırları
  13  4007 Bilim Şenlikleri: 2026 başvuru dönemi 2 Mart 2026'da kapandı → pasif, çağrı satırı, başvuru yeri
  18, 41, 57, 64, 71  başvuru yeri (PRODİS / UİDB PBS / KEP)
  76  Hayvancılık: 2026 birim tutarları (8760 sayılı Karar, 11782 sayılı Kararla değişik, RG 08.09.2026)
  174 1512 BiGG: yanıltıcı "sayfaya erişilemiyor" notu yerine pasiflik gerekçesi

    python scripts/fix_veri_2026_10_13_tur41.py --self-test
    python scripts/fix_veri_2026_10_13_tur41.py --dogrula        (indirir, alıntıları denetler; DB'ye yazmaz)
    python scripts/fix_veri_2026_10_13_tur41.py --uygula         (yedek: tesvikler_oncesi_tur41.db.bak)
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

DIZIN = KOK / "docs/olcum/2026-10-13-tur41"
ONBELLEK = DIZIN / "kaynak"
YEDEK = KOK / "docs/olcum/2026-10-07-denetim2/tesvikler_oncesi_tur41.db.bak"
BUGUN = date(2026, 10, 13)
NOT = "Tur41 2026-10-13"

TUBITAK = "https://www.tubitak.gov.tr/tr/destekler"
MTA = "https://tubitak.gov.tr/tr/destekler/bilim-toplum/ulusal-destek-programlari/milli-teknoloji-atolyeleri-proje-destegi"
MTA_CAGRI = "https://tubitak.gov.tr/sites/default/files/2026-08/Cagri_Metni_21.08.2026_tarihinde_guncellenmistir.pdf"
P1000 = (f"{TUBITAK}/akademik/ulusal-destek-programlari/1000-universitelerin-arastirma-ve-gelistirme-potansiyelinin-"
         "artirilmasina-yonelik-destek-programi")
EUROSTARS_PDF = "https://tubitak.gov.tr/sites/default/files/2026-09/1709-EUREKA-EUROSTARS_CAGRI_DUYURUSU_20262.pdf"
EUROSTARS_12 = ("https://www.eurekanetwork.org/programmes-and-calls/eurostars/eurostars-call-12-for-projects-deadline-"
                "march-2027/")
P4007 = f"{TUBITAK}/bilim-toplum/ulusal-destek-programlari/4007-bilim-senlikleri-destekleme-programi"
C4007 = "https://tubitak.gov.tr/sites/default/files/2026-01/4007_Cagri_Metni_2026_27012026.pdf"
K11782 = "https://www.resmigazete.gov.tr/eskiler/2026/09/20260908-8.pdf"
K8760 = "https://www.resmigazete.gov.tr/eskiler/2024/07/20240726-4.pdf"
M3308 = "https://www.mevzuat.gov.tr/mevzuatmetin/1.5.3308.pdf"
MEB_3308 = "https://www.meb.gov.tr/staj-ucretine-devlet-katkisi-5-egitim-yili-uzatildi/haber/24993/tr"
M2634 = "https://www.mevzuat.gov.tr/mevzuatmetin/1.5.2634.pdf"
BKK_2010_478 = "https://izmir.ktb.gov.tr/Eklenti/7027,bkk2010-478-enerji-destegi-bakanlar-kurulu-kararipdf.pdf?0"
EIHR_KARAR = "https://ticaret.gov.tr/data/632b13e013b8767974670b91/E-ihracat%20Karar.pdf"
EIHR_GENELGE = ("https://ticaret.gov.tr/data/6447baf113b8761694f892bb/E-%C4%B0HRACAT%20DESTEKLER%C4%B0NE%20%C4%B0L"
                "%C4%B0%C5%9EK%C4%B0N%20GENELGE%2013.04.2026.pdf")
EIHR_LIMIT = ("https://ticaret.gov.tr/data/632b145a13b8767974670b9a/2026%20Y%C4%B1l%C4%B1na%20%C4%B0li%C5%9Fkin%20"
              "E-%C4%B0hracat%20Destekleri%20%C3%9Cst%20Limitleri.xlsx")

# Değişiklikler: alanlar (tam değer), not (durum_notu başına eklenir), çağrılar (yoksa eklenir), kanıtlar.
# Kanıt: (url, alıntı) — alıntı indirilen metinde aranır; ("gorsel", dosya, okunan metin) — taranmış sayfa.
DEGISIKLIKLER: list[dict] = [
    {"id": 37, "alanlar": {
        "aktif_mi": True, "basvuru_bicimi": "proje", "tutari_max": 30_000_000.0,
        "basvuru_yeri": "Bilim ve Toplum Proje Başvuru Sistemi (https://bilimtoplum-pbs.tubitak.gov.tr/); 4003-T "
                        "Millî Teknoloji Atölyeleri çağrısında başvuru dosyası Müşteri Kurum (üniversite, kamu kurumu) "
                        "ile Proje Yürütücüsü Kurum tarafından sisteme girilir.",
        "basvuru_suresi": "4003-T Millî Teknoloji Atölyeleri: açık çağrı, son başvuru tarihi yok (çağrı metni "
                          "21.08.2026'da güncellendi). Bilim merkezi kurulumu için açık çağrı bulunamadı.",
        "tesvil_tutari": "4003-T Millî Teknoloji Atölyeleri: proje toplam bütçe üst limiti 30.000.000 TL; Atölye "
                         "Kurulum ve Faaliyet Dönemi Projesi en fazla 36 ay."},
     "not": f"{NOT}: açık çağrı 4003-T Millî Teknoloji Atölyeleri ({MTA}); aktife alındı.",
     "kanitlar": [(MTA_CAGRI, "Çağrı Türü: Açık Çağrı"),
                  (MTA_CAGRI, "toplam bütçe üst limiti 30.000.000 TL"),
                  (MTA_CAGRI, "Bu proje için süre en fazla 36 aydır."),
                  (MTA_CAGRI, "Destek Programı: 4003 Bilim Merkezi ve Atölye Destek Programını"),
                  (MTA, "https://bilimtoplum-pbs.tubitak.gov.tr/"),
                  (MTA, "Çağrı Metni (21 Ağustos 2026 tarihinde güncellenmiştir.)")]},
    {"id": 73, "alanlar": {
        "aktif_mi": False,
        "basvuru_suresi": "Çağrılı: çağrı başlıkları ve başvuru koşulları TÜBİTAK Başkanlığınca ilan edilir; program "
                          "sayfasında açık çağrı yok (TÜBİTAK duyurularında bulunan son 1000 çağrısı 2015/2016)."},
     "not": f"{NOT}: açık çağrı yok, pasife alındı; çağrı ilan edilirse yeniden aktife alınmalı.",
     "kanitlar": [(P1000, "Program çağrılı sistemle çevrimiçi başvuru almaktadır."),
                  (P1000, "Proje süresinin üst sınırı çağrı duyurusunda belirtilir, ancak 36 ayı geçemez.")]},
    {"id": 48, "alanlar": {
        "basvuru_suresi": "Çağrı dönemli: 2026/2 ulusal çağrısı kapandı (kuruluş bazlı ön kayıt 21 Eylül, ön proje "
                          "başvurusu 24 Eylül 2026; uluslararası kapanış 10 Eylül 2026). Sonraki Eurostars çağrısı "
                          "(Call 12) 17 Aralık 2026'da açılıyor, uluslararası kapanış 4 Mart 2027; TÜBİTAK ulusal "
                          "takvimi çağrı duyurusunda ilan edilecek."},
     "not": f"{NOT}: çağrı satırları eklendi (2026/2 kapandı; Call 12 uluslararası takvim).",
     "cagrilar": [
         {"ad": "1709-EUREKA-EUROSTARS 2026/2 ulusal çağrısı", "acilis": date(2026, 7, 17),
          "on_kayit_son": date(2026, 9, 21), "kapanis": date(2026, 9, 24), "kaynak_url": EUROSTARS_PDF,
          "notlar": "Uluslararası kapanış 10 Eylül 2026 14:00 (Brüksel); kuruluş bazlı ön kayıt 21 Eylül, ön proje "
                    "başvurusu 24 Eylül 2026 23:59 (PRODİS)."},
         {"ad": "Eurostars Call 12 (uluslararası takvim)", "acilis": date(2026, 12, 17), "kapanis": date(2027, 3, 4),
          "kaynak_url": EUROSTARS_12,
          "notlar": "Uluslararası kapanış 4 Mart 2027 14:00 CET. Türk kuruluşları TÜBİTAK'a ulusal ön başvuru ve "
                    "tam başvuru da yapar; ulusal takvim TÜBİTAK çağrı duyurusunda ilan edilecek."}],
     "kanitlar": [(EUROSTARS_PDF, "10 Eylül 2026 (14:00 Brüksel saati)"),
                  (EUROSTARS_PDF, "17 Temmuz 2026"),
                  (EUROSTARS_PDF, "21 Eylül 2026 (23:59 Türkiye saati)"),
                  (EUROSTARS_PDF, "24 Eylül 2026 (23:59 Türkiye Saati)"),
                  (EUROSTARS_12, "17 December 2026: Call opens"),
                  (EUROSTARS_12, "4 March 2027, 14:00 CET: Deadline")]},
    {"id": 13, "alanlar": {
        "aktif_mi": False,
        "basvuru_yeri": "Çevrimiçi: ARBİS kaydı gerekir; başvuru Bilim ve Toplum Proje Başvuru Sistemi "
                        "(http://bilimtoplum-pbs.tubitak.gov.tr) üzerinden.",
        "basvuru_suresi": "Yıllık çağrı: 2026 başvuru dönemi 30 Ocak – 2 Mart 2026 (kapandı; çağrı sonuçlandı); "
                          "etkinlik dönemi 21 Mayıs – 30 Kasım 2026. Sonraki çağrı tarihi duyurulmadı."},
     "not": f"{NOT}: 2026 başvuru dönemi kapandı, pasife alındı; 2027 çağrısı açılınca yeniden aktife alınmalı.",
     "cagrilar": [{"ad": "4007 Bilim Şenlikleri 2026 çağrısı", "acilis": date(2026, 1, 30),
                   "kapanis": date(2026, 3, 2), "kaynak_url": C4007,
                   "notlar": "Kapanış saati 17:30; etkinlik dönemi 21 Mayıs – 30 Kasım 2026."}],
     "kanitlar": [(P4007, "Programa başvuru sadece Çevrimiçi olarak yapılır."),
                  (P4007, "bilimtoplum-pbs.tubitak.gov.tr"),
                  (P4007, "ÇAĞRISI SONUÇLANDI"),
                  (C4007, "30 Ocak 2026"), (C4007, "2 Mart 2026"), (C4007, "21 Mayıs 2026"), (C4007, "30 Kasım 2026")]},
    {"id": 18, "alanlar": {"basvuru_yeri": "PRODİS üzerinden çevrimiçi (TÜBİTAK); çağrı, ayrıca duyuru yapılana kadar "
                                           "sürekli başvuruya açık."},
     "kanitlar": [(f"{TUBITAK}/sanayi/ulusal-destek-programlari/1613-teknoloji-transferi-profesyoneli-cagrisi",
                   "çevrimiçi olarak PRODİS üzerinden gönderilecektir."),
                  (f"{TUBITAK}/sanayi/ulusal-destek-programlari/1613-teknoloji-transferi-profesyoneli-cagrisi",
                   "Çağrı sürekli başvuruya açıktır.")]},
    {"id": 41, "alanlar": {"basvuru_yeri": "UİDB elektronik başvuru sistemi (http://uidb-pbs.tubitak.gov.tr/); "
                                           "başvuru sistemi sürekli açık."},
     "kanitlar": [("html", f"{TUBITAK}/uluslararasi-birlikleri/ikili-birligi-programlari/2501-abd-ulusal-bilim-vakfi-nsf-ile-"
                   "ikili-isbirligi-programi", "uidb-pbs.tubitak.gov.tr"),
                  (f"{TUBITAK}/uluslararasi-birlikleri/ikili-birligi-programlari/2501-abd-ulusal-bilim-vakfi-nsf-ile-"
                   "ikili-isbirligi-programi", "elektronik başvuru sistemi"),
                  (f"{TUBITAK}/uluslararasi-birlikleri/ikili-birligi-programlari/2501-abd-ulusal-bilim-vakfi-nsf-ile-"
                   "ikili-isbirligi-programi", "başvuru sistemi sürekli olarak açıktır")]},
    {"id": 57, "alanlar": {"basvuru_yeri": "Kayıtlı Elektronik Posta (KEP) ile TÜBİTAK'a; başvurular sürekli açık."},
     "kanitlar": [(f"{TUBITAK}/sanayi/ulusal-destek-programlari/1503-proje-pazarlari-destekleme-programi",
                   "Başvurular Kayıtlı Elektronik Posta (KEP) yolu ile yapılmaktadır."),
                  (f"{TUBITAK}/sanayi/ulusal-destek-programlari/1503-proje-pazarlari-destekleme-programi",
                   "Başvurular sürekli açıktır")]},
    {"id": 64, "alanlar": {"basvuru_yeri": "UİDB elektronik başvuru sistemi (http://uidb-pbs.tubitak.gov.tr/); "
                                           "başvuru toplama tarihleri 31 Ocak, 31 Mayıs ve 30 Eylül."},
     "kanitlar": [("html", f"{TUBITAK}/uluslararasi-birlikleri/ikili-birligi-programlari/2502-bulgaristan-bilimler-akademisi-"
                   "bas-ile-ikili-isbirligi-programi", "uidb-pbs.tubitak.gov.tr"),
                  (f"{TUBITAK}/uluslararasi-birlikleri/ikili-birligi-programlari/2502-bulgaristan-bilimler-akademisi-"
                   "bas-ile-ikili-isbirligi-programi", "elektronik başvuru sistemi"),
                  (f"{TUBITAK}/uluslararasi-birlikleri/ikili-birligi-programlari/2502-bulgaristan-bilimler-akademisi-"
                   "bas-ile-ikili-isbirligi-programi", "(31 Ocak, 31 Mayıs ve 30 Eylül)")]},
    {"id": 71, "alanlar": {"basvuru_yeri": "UİDB elektronik başvuru sistemi (http://uidb-pbs.tubitak.gov.tr/); proje "
                                           "ekibinin ARBİS kaydı güncel olmalı."},
     "kanitlar": [("html", f"{TUBITAK}/uluslararasi-birlikleri/ikili-birligi-programlari/2507-almanya-arastirmalar-konseyi-"
                   "dfg-ile-ikili-isbirligi-programi", "uidb-pbs.tubitak.gov.tr"),
                  (f"{TUBITAK}/uluslararasi-birlikleri/ikili-birligi-programlari/2507-almanya-arastirmalar-konseyi-"
                   "dfg-ile-ikili-isbirligi-programi", "elektronik başvuru sistemi")]},
    {"id": 76, "alanlar": {
        "tesvil_tutari": "2026 yılı birim tutarları (8760 sayılı Cumhurbaşkanı Kararı, 11782 sayılı Kararla değişik, "
                         "RG 08.09.2026): buzağı 2.000 TL/baş, malak 4.000 TL/baş (programlı aşıları tamamlanmış, yılı "
                         "içinde doğan, 4 ay (120 gün) ve üzeri yaşta; hastalıktan ari işletmeler hariç en fazla 500 "
                         "baş); kuzu/oğlak 430 TL/baş (en az 4 ay yaşamış); atık desteği sığır ve manda 20.000 TL/baş, "
                         "koyun ve keçi 4.000 TL/baş; arıcılık 250 TL/kovan (örgüt üyesi olmayana 200 TL); ipek böceği "
                         "1.500 TL/kg; tiftik 220 TL/kg. İlave katsayılar Kararda (ör. suni tohumlama ilave 1,0, "
                         "embriyo transferi/cinsiyeti belirli sperma ilave 2,5)."},
     "not": f"{NOT}: 2026 birim tutarları 11782 sayılı Karardan (RG 08.09.2026, {K11782}; taranmış sayfa, görüntüden "
            "okundu); 8760'taki tutarlar 2024 içindir.",
     "kanitlar": [("gorsel", "karar_11782_rg20260908_s2.png",
                   "“2026 yılı için buzağılara 2.000 TL/baş, malaklara 4.000 TL/baş”; “2026 yılı için 430 TL/baş”; "
                   "“2026 yılında sığır ve mandalar için 20.000 TL/baş, koyun ve keçiler için 4.000 TL/baş”; “2026 "
                   "yılı için 250 TL, üye olmayanlara 200 TL”; “2026 yılı için 1.500 TL/kg”; “2026 yılı için 220 "
                   "TL/kg”; suni tohumlama ilave 1,0, embriyo transferi/cinsiyeti belirli sperma ilave 2,5 katsayı"),
                  ("gorsel", "karar_8760_rg20240726_s2.png",
                   "“yılı içinde doğan, 4 ay (120 gün) ve üzeri yaşta buzağı/malaklara hastalıktan ari işletmeler "
                   "hariç en fazla 500 baş ile sınırlı olmak üzere”")]},
    {"id": 367, "alanlar": {
        "basvuru_suresi": "Geçici 12. madde ödemeleri Cumhurbaşkanı Kararıyla uzatılır: son uzatma (5063 sayılı Karar, "
                          "RG 5/1/2022) 2021-2022 eğitim yılından itibaren beş eğitim yılı, yani 2025-2026 sonuna "
                          "kadar. 2026-2027 için uzatma kararı bulunamadı; MEB ya da İŞKUR'dan teyit edin."},
     "not": f"{NOT}: uzatma zinciri doğrulandı (Kanun Geçici 12 + 5063 sayılı CK; MEB duyurusu {MEB_3308}); "
            "2026-2027 için yeni CK bulunamadı (Resmî Gazete fihristi taranmadı), kayıt kararsız bırakıldı.",
     "kanitlar": [(M3308, "Bu kapsamda yapılacak ödemeleri on eğitim ve öğretim yılına kadar uzatmaya Cumhurbaşkanı "
                          "yetkilidir."),
                  (M3308, "yirmiden az personel çalıştıran işletmeler için üçte ikisi"),
                  (MEB_3308, "2021-2022 eğitim yılından itibaren 5 eğitim yılı uzatılmasına karar verildi.")]},
    {"id": 270, "alanlar": {
        "aktif_mi": True,
        "tesvil_tutari": "Elektrik enerjisi desteği: tesisin bulunduğu ildeki mesken ve sanayi abonelerine uygulanan "
                         "tarifelerden en düşüğü ile kendi abone grubuna uygulanan tarife arasındaki fark kadardır; "
                         "Bakanlık (Kültür ve Turizm) bütçesine konulan ödenekten karşılanır (2010/478 sayılı Bakanlar "
                         "Kurulu Kararı m.3, 2634 sayılı Kanun m.16). Diğer teşvikler 2634 sayılı Kanun ve teşvik "
                         "belgesi alınırsa yatırım teşvik kararlarına dayanır."},
     "not": f"{NOT}: 2634 m.16 yürürlükte (mevzuat.gov.tr metni, 7565 sayılı Kanuna kadar işlenmiş); fark 2010/478 "
            "sayılı BKK'ya göre Bakanlık bütçesinden karşılanır (kayıttaki 'Hazinece' ifadesi 2005 tebliğindendi). "
            "2024-2026 fiilî ödeme duyurusu bulunamadı; il kültür ve turizm müdürlüğünden teyit edilmeli.",
     "kanitlar": [(M2634, "Turizm belgeli yatırım ve işletmeler elektrik, gaz ve su ücretlerini o bölgedeki sanayi ve "
                          "meskenlere uygulanan tarifelerden en düşüğü üzerinden öderler."),
                  (BKK_2010_478, "kendi abone grubuna uygulanan tarife arasındaki fark kadardır."),
                  (BKK_2010_478, "Bakanlık bütçesine konulacak ödenekten karşılanır.")]},
    {"id": 174, "alanlar": {
        "basvuru_suresi": "Yeni başvuru alınmıyor: BiGG 1. aşaması 2026-2028 döneminde 1812 Yatırım Tabanlı "
                          "Girişimcilik Destek Programı (BiGG Yatırım) çağrılarıyla yürütülüyor."},
     "not_degistir": ("⚠️ SAYFAYA ŞU AN ERİŞİLEMİYOR", f"{NOT}: program pasif — BiGG 1. aşaması 2026-2028'de 1812 BiGG "
                      "Yatırım altında (kanıt docs/olcum/2026-10-10-tur22/tubitak_1612_en.txt); yeni başvuru için "
                      "1812. Eski not (2026-09-29): sayfaya erişilemiyordu"),
     "kanitlar": [("dosya", "docs/olcum/2026-10-10-tur22/tubitak_1612_en.txt",
                   "within the framework of the 1812 Investment-Based Entrepreneurship Support Program")]},
]

# 5986 sayılı Karar m.3 ve m.7: yalnız E-İhracat Konsorsiyumu, perakende e-ticaret sitesi ve pazaryeri statüsündekiler
# yararlanır (2026 limit tablosunda "Şirketler" sütunu "-"). İkas mağazası Perakende E-Ticaret Sitesi statüsünü alırsa
# (önceki yıl en az 500.000 USD ihracat vb.) yararlanabilir; bu yüzden şablon m.5 kaydıdır (196: aynı statü şartı,
# statu_ile_muaf). Şablonun ortak maddeleri (şirket, birlik üyeliği, DYS, Türk ürünü, statü, kendi sitesi, mükerrer
# destek) alıntı ve kaynaklarıyla kopyalanır.
SABLON, SABLON_MADDE = 196, 7
BASVURU_YERI = ("Üyesi olunan İhracatçı Birliği Genel Sekreterliğine DYS üzerinden; ön onay gerekip gerekmediği ve "
                "başvuru formları E-İhracat Genelgesi'nden (13.04.2026) teyit edilmeli.")
YENI_KAYITLAR: list[dict] = [
    {"baslik": "Pazara Giriş Rapor Desteği (5986 sayılı Karar m.3)",
     "ozet": "E-İhracat Konsorsiyumu, perakende e-ticaret sitesi ve pazaryeri statüsündekilerin satın aldığı sektör, "
             "ülke ve e-ihracat odaklı raporların giderleri %50 oranında desteklenir; statüsüz şirkete açık değildir.",
     "detay": "Yurt dışında e-ticarete ilişkin pazara giriş stratejisi ve eylem planı oluşturmak için satın alınan "
              "sektör, ülke ve e-ihracat odaklı rapor giderleri; en fazla 20 rapor ve 20 üyelik (yıllık üyelik "
              "ücreti) için (Genelge m.12/7). Destek üst limitleri her yıl (TÜFE + Yİ-ÜFE)/2 oranında güncellenir.",
     "hedef_kitle": "Perakende E-Ticaret Sitesi, pazaryeri ya da E-İhracat Konsorsiyumu statüsündeki işletmeler",
     "kaynak_url": f"{EIHR_KARAR}#madde-3",
     "tesvil_tutari": "%50; 2026 yıllık üst limit 7.396.548 TL (perakende e-ticaret siteleri, pazaryerleri ve "
                      "E-İhracat Konsorsiyumları için; şirketler sütununda '-'). Karar'daki taban limit yıllık "
                      "1.500.000 TL'dir.",
     "tutari_max": 7_396_548.0,
     "tutari_hesaplama_formulu": "Rapor/üyelik gideri × %50, 2026 yıllık 7.396.548 TL ile sınırlı",
     "destek_verilme_suresi": "Yıllık (süre sınırı yok); en fazla 20 rapor ve 20 üyelik",
     "maddeler": [
         {"tur": "kural", "metin": "En fazla 20 rapor ve 20 üyelik (yıllık üyelik ücreti) için destekten "
                                   "yararlanılır (Genelge m.12/7).",
          "alinti": "en fazla 20 (yirmi) adet rapor ve 20 (yirmi) adet üyelik (yıllık üyelik ücreti) için "
                    "destekten yararlanır.", "kaynak_url": EIHR_GENELGE},
         {"tur": "bilgi", "metin": "Yararlanıcılar: E-İhracat Konsorsiyumları, perakende e-ticaret siteleri ve "
                                   "pazaryerleri (Genelge m.12/1).",
          "alinti": "Karar kapsamında bu destekten E-İhracat Konsorsiyumları, perakende e-ticaret siteleri ve "
                    "pazaryerleri yararlanır.", "kaynak_url": EIHR_GENELGE}],
     "kanitlar": [(EIHR_KARAR, "Pazara giriş rapor desteği"),
                  # PDF metin katmanında "e -ihracat" bölünmesi var; alıntı bozulmamış parçalarla aranır.
                  (EIHR_KARAR, "odaklı raporlara ilişkin giderleri %50 oranında ve yıllık 1.500.000"),
                  (EIHR_KARAR, "TL’ye kadar desteklenir."),
                  (EIHR_KARAR, "(TÜFE + Yİ-ÜFE)/2 oranında güncellenir."),
                  (EIHR_GENELGE, "en fazla 20 (yirmi) adet rapor ve 20 (yirmi) adet üyelik (yıllık üyelik ücreti) "
                                 "için destekten yararlanır."),
                  (EIHR_GENELGE, "Karar kapsamında bu destekten E-İhracat Konsorsiyumları, perakende e-ticaret "
                                 "siteleri ve pazaryerleri yararlanır."),
                  ("xlsx", EIHR_LIMIT, "Pazara Giriş Rapor Desteği | - | 7396548 | - | 7396548 | 7396548")]},
    {"baslik": "Yurt Dışı Pazaryeri Entegrasyon Desteği (5986 sayılı Karar m.7)",
     "ozet": "E-İhracat Konsorsiyumu, perakende e-ticaret sitesi ve pazaryeri statüsündekilerin yurt dışı "
             "pazaryerlerine entegrasyon hizmeti giderleri %50 oranında, en fazla 6 pazaryeri için ve pazaryeri "
             "başına 3 yıl desteklenir; statüsüz şirkete açık değildir.",
     "detay": "Yurt dışı pazaryerleri ve onlara ilişkin yurt içinde alınan entegrasyon hizmetleri. Entegrasyon "
              "desteği alınacak pazaryerinde en az 1.000 SKU listelenmeli (Genelge m.17/3). Destek yalnız "
              "Bakanlığın belirlediği ülkelere yöneliktir; hedef ülke ilave puanı uygulanmaz (Karar m.16).",
     "hedef_kitle": "Perakende E-Ticaret Sitesi, pazaryeri ya da E-İhracat Konsorsiyumu statüsündeki işletmeler",
     "kaynak_url": f"{EIHR_KARAR}#madde-7",
     "tesvil_tutari": "%50; en fazla 6 pazaryeri, pazaryeri başına 3 yıl; Karar'da entegrasyon başına en fazla "
                      "200.000 TL (taban, yıllık güncellenir); 2026 üst limit tablosunda 983.844 TL (yıllık; "
                      "perakende e-ticaret siteleri, pazaryerleri ve konsorsiyumlar için; şirketler sütununda '-').",
     "tutari_max": 983_844.0,
     "tutari_hesaplama_formulu": "Entegrasyon gideri × %50; 2026 tablosunda 983.844 TL ile sınırlı",
     "destek_verilme_suresi": "Pazaryeri başına 3 yıl, en fazla 6 pazaryeri",
     "maddeler": [
         {"tur": "sart", "metin": "Entegrasyon desteği alınacak yurt dışı pazaryerinde en az 1.000 SKU listelenmeli ve "
                                  "ürünlerin entegrasyon hizmetiyle listelendiği tespit edilmeli (Genelge m.17/3).",
          "alinti": "en az 1.000 (bin) adet stok tutma biriminin (SKU) listelenmesi", "kaynak_url": EIHR_GENELGE},
         {"tur": "kural", "metin": "Destek yalnız Bakanlığın belirlediği ülkelere yönelik verilir; hedef ülke ilave "
                                   "puanı uygulanmaz (Karar m.16).",
          "alinti": "7 nci, 8 inci, 9 uncu ve 12 nci maddelerdeki destekler için hedef ülke ilave puanı uygulanmaz.",
          "kaynak_url": EIHR_KARAR}],
     "kanitlar": [(EIHR_KARAR, "Yurt dışı pazaryeri entegrasyon desteği"),
                  # PDF metin katmanında "p azaryeri ba şına" bölünmesi var; alıntı parçalarla aranır.
                  (EIHR_KARAR, "en fazla 6 (altı) pazaryeri entegrasyonu için %50 oranında"),
                  (EIHR_KARAR, "3 (üç) yıl süresince, bir entegrasyon için en fazla 200.000 TL’ye kadar desteklenir."),
                  (EIHR_KARAR, "7 nci, 8 inci, 9 uncu ve 12 nci maddelerdeki destekler için hedef ülke ilave puanı "
                               "uygulanmaz."),
                  (EIHR_GENELGE, "en az 1.000 (bin) adet stok tutma biriminin (SKU) listelenmesi"),
                  ("xlsx", EIHR_LIMIT, "Yurt Dışı Pazaryeri Entegrasyon Desteği | - | 983844 | 983844 | 983844")]},
]


def yeni_kayit(db, tanim: dict) -> str | None:
    """Başlığı olmayan kaydı şablondan (196) üretir; varsa dokunmaz. Oluşturulan kaydın başlığı ya da None."""
    from app.models import Tesvik
    if db.query(Tesvik).filter(Tesvik.baslik == tanim["baslik"]).first() is not None:
        return None
    sablon = db.get(Tesvik, SABLON)
    ortak = [dict(m) for m in (sablon.kontrol_listesi or [])[:SABLON_MADDE]]
    maddeler = ortak + [dict(m, dogrulandi=True) for m in tanim["maddeler"]] + [
        {"tur": "adim", "metin": f"Başvuruyu yap: {BASVURU_YERI}"}]
    alanlar = {k: v for k, v in tanim.items() if k not in ("maddeler", "kanitlar")}
    db.add(Tesvik(kurum=sablon.kurum, kategori=sablon.kategori, aktif_mi=True, basvuru_bicimi=sablon.basvuru_bicimi,
                  uygunluk_kriterleri=dict(sablon.uygunluk_kriterleri or {}), tutari_hesaplama_kriteri="genel",
                  basvuru_sartlari=[m["metin"] for m in maddeler if m["tur"] == "sart"], gerekli_belgeler=[],
                  basvuru_yeri=BASVURU_YERI, basvuru_suresi="Sürekli (dönemsel çağrı yok); destek üst limitleri "
                  "takvim yılı başında güncellenir.", kontrol_listesi=maddeler,
                  durum_notu=f"{NOT}: 5986 sayılı Karar ve Genelge 13.04.2026'dan eklendi (şablon kayıt {SABLON}, "
                             "ortak şartlar oradan).", **alanlar))
    return tanim["baslik"]


def _tur21():
    spec = importlib.util.spec_from_file_location("tur21", KOK / "scripts/fix_veri_2026_10_10_tkdk_ka_tur21.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ONBELLEK, m.BUGUN = ONBELLEK, BUGUN
    return m


def ham_html(url: str) -> tuple[str, str | None]:
    """Sayfanın ham HTML'i (önbellekli): görünür metinde olmayan bağlantı adresi ("elektronik başvuru sistemi"
    bağlantısının hedefi) burada aranır."""
    import hashlib

    import requests
    yol = ONBELLEK / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")
    if yol.exists():
        return yol.read_text(encoding="utf-8"), None
    try:
        r = requests.get(url, headers=_tur21().HEADERS, timeout=60)
        r.raise_for_status()
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"[:200]
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    yol.write_text(r.text, encoding="utf-8")
    return r.text, None


def xlsx_metni(url: str) -> tuple[str, str | None]:
    """Excel tablosunun satırları "hücre | hücre" biçiminde (önbellekli .xlsx)."""
    import hashlib
    import io

    import openpyxl
    import requests
    yol = ONBELLEK / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".xlsx")
    if not yol.exists():
        try:
            r = requests.get(url, headers=_tur21().HEADERS, timeout=60)
            r.raise_for_status()
        except Exception as e:
            return "", f"{type(e).__name__}: {e}"[:200]
        yol.write_bytes(r.content)
    wb = openpyxl.load_workbook(io.BytesIO(yol.read_bytes()), data_only=True)
    satirlar = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            hucre = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if hucre:
                satirlar.append(" | ".join(hucre))
    return "\n".join(satirlar), None


def dogrula(degisiklik: dict, getir, norm, ham_getir=None) -> list[str]:
    """Geçmeyen kanıtların açıklaması (boş liste: hepsi geçti). Kanıt türleri: (url, alıntı) görünür metin;
    ("html", url, alıntı) ham HTML; ("dosya", depo yolu, alıntı); ("gorsel", dosya, okunan metin)."""
    hatalar = []
    for k in degisiklik.get("kanitlar", []):
        if k[0] == "gorsel":
            if not (ONBELLEK / k[1]).exists():
                hatalar.append(f"görsel kanıt dosyası yok: {k[1]}")
            continue
        if k[0] == "xlsx":
            kaynak, alinti = k[1], k[2]
            metin, hata = xlsx_metni(kaynak)
        elif k[0] == "dosya":
            kaynak, alinti = k[1], k[2]
            metin, hata = (KOK / kaynak).read_text(encoding="utf-8"), None
        elif k[0] == "html":
            kaynak, alinti = k[1], k[2]
            metin, hata = (ham_getir or ham_html)(kaynak)
        else:
            kaynak, alinti = k
            metin, hata = getir(kaynak)
        if hata:
            hatalar.append(f"{kaynak}: indirilemedi ({hata})")
        elif norm(alinti) not in norm(metin):
            hatalar.append(f"{kaynak}: alıntı bulunamadı: {alinti!r}")
    return hatalar


def uygula(db, degisiklik: dict) -> list[str]:
    """Değişikliği oturuma yazar (commit çağıran yapar); yapılanların listesi. İdempotent."""
    from app.models import Tesvik, TesvikCagrisi
    t = db.get(Tesvik, degisiklik["id"])
    yapilan = []
    for alan, deger in degisiklik.get("alanlar", {}).items():
        if getattr(t, alan) != deger:
            setattr(t, alan, deger)
            yapilan.append(alan)
    if degisiklik.get("not") and degisiklik["not"] not in (t.durum_notu or ""):
        t.durum_notu = degisiklik["not"] + (" | " + t.durum_notu if t.durum_notu else "")
        yapilan.append("durum_notu")
    if degisiklik.get("not_degistir"):
        eski, yeni = degisiklik["not_degistir"]
        if (t.durum_notu or "").startswith(eski):
            t.durum_notu = yeni + (t.durum_notu or "")[len(eski):]
            yapilan.append("durum_notu")
    for c in degisiklik.get("cagrilar", []):
        if not any(x.ad == c["ad"] for x in t.cagrilar):
            db.add(TesvikCagrisi(tesvik_id=t.id, dogrulama_tarihi=BUGUN, **c))
            yapilan.append(f"çağrı: {c['ad']}")
    return yapilan


def main() -> int:
    arg = sys.argv[1:]
    if "--self-test" in arg:
        return _self_test()
    tur21 = _tur21()
    hata_var = False
    for d in DEGISIKLIKLER + YENI_KAYITLAR:
        hatalar = dogrula(d, tur21.metin_al, tur21.norm)
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
    kaynak = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    if not YEDEK.exists():
        shutil.copy2(kaynak, YEDEK)
        print(f"yedek: {YEDEK}")
    db = SessionLocal()
    try:
        for d in DEGISIKLIKLER:
            print(f"[{d['id']}] {uygula(db, d) or 'değişiklik yok'}")
        for t in YENI_KAYITLAR:
            print(f"[yeni] {yeni_kayit(db, t) or 'zaten var: ' + t['baslik']}")
        db.commit()
    finally:
        db.close()
    return 0


def _self_test() -> int:
    from types import SimpleNamespace as N
    tur21 = _tur21()
    sahte = {"u1": ("Başvurular sürekli açıktır ve yılın her günü", None), "u2": ("", "HTTPError 404")}
    getir = lambda u: sahte.get(u, ("", "yok"))  # noqa: E731
    gec = dogrula({"kanitlar": [("u1", "Başvurular   sürekli açıktır")]}, getir, tur21.norm)
    kal = dogrula({"kanitlar": [("u1", "kapalıdır")]}, getir, tur21.norm)
    ind = dogrula({"kanitlar": [("u2", "x")]}, getir, tur21.norm)
    gorsel = dogrula({"kanitlar": [("gorsel", "yok.png", "x")]}, getir, tur21.norm)

    class Db:
        def __init__(self):
            self.eklenen = []

        def get(self, model, i):
            return kayit

        def add(self, x):
            self.eklenen.append(x)
            kayit.cagrilar.append(x)

    kayit = N(id=1, aktif_mi=None, basvuru_yeri=None, durum_notu="eski", cagrilar=[])
    db = Db()
    d = {"id": 1, "alanlar": {"aktif_mi": True}, "not": "Tur41: x",
         "cagrilar": [{"ad": "C1", "acilis": None, "kapanis": date(2026, 3, 2), "kaynak_url": "u"}]}
    ilk = uygula(db, d)
    ikinci = uygula(db, d)
    kayit2 = N(id=2, durum_notu="⚠️ SAYFAYA ŞU AN ERİŞİLEMİYOR (HTTP 403)", cagrilar=[])
    db.get = lambda m, i: kayit2
    uygula(db, {"id": 2, "not_degistir": ("⚠️ SAYFAYA ŞU AN ERİŞİLEMİYOR", "Tur41: pasif. Eski not: erişilemiyordu")})
    kimlikler = [x["id"] for x in DEGISIKLIKLER]
    k = [("alıntı boşluk ve harf farkına duyarsız bulunur", gec == []),
         ("bulunmayan alıntı kalır", len(kal) == 1),
         ("indirme hatası kalır", len(ind) == 1 and "indirilemedi" in ind[0]),
         ("görsel kanıt dosyası aranır", len(gorsel) == 1),
         ("alan, not ve çağrı uygulanır", ilk == ["aktif_mi", "durum_notu", "çağrı: C1"] and kayit.aktif_mi is True
          and kayit.durum_notu == "Tur41: x | eski"),
         ("idempotent", ikinci == [] and len(db.eklenen) == 1),
         ("yanıltıcı not başı değiştirilir", kayit2.durum_notu.startswith("Tur41: pasif. Eski not: erişilemiyordu (HTTP")),
         ("her değişikliğin kanıtı var, kimlikler tekil", all(x.get("kanitlar") for x in DEGISIKLIKLER)
          and len(kimlikler) == len(set(kimlikler))),
         ("görsel kanıt dosyaları depoda", all((ONBELLEK / x[1]).exists() for d in DEGISIKLIKLER
                                               for x in d["kanitlar"] if x[0] == "gorsel"))]
    g = sum(1 for _, ok in k if ok)
    for ad, ok in k:
        print(f"  [{'OK' if ok else 'HATA'}] {ad}")
    print(f"tur41 self-test: {g}/{len(k)}")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    sys.exit(main())
