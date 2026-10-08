"""Tur 12 — İhracat/e-ihracat kayıtlarının genelge düzeyinde tamamlanması (2026-10-08).

Kaynaklar (hepsi ticaret.gov.tr, 2026-10-08'de indirildi; PDF PyMuPDF, docx python-docx, xlsx openpyxl ile okundu):
  5973 genelgeleri: Pazara Giriş Belgesi (30.06.2025), Yurt Dışı Marka Tescil (30.06.2025), Yurt Dışı Pazar
  Araştırması (02.03.2026), Birim Kira, Tanıtım; ekleri (EK-1/A, EK-1, EK-A, Ek-1A/1B/1C, EK-2).
  5986 sayılı E-İhracat Destekleri Kararı (son değişiklik RG 17.01.2026), E-İhracat Genelgesi 13.04.2026,
  Genelge Ekleri ZIP (24.04.2026), 2026 Yılına İlişkin E-İhracat Destekleri Üst Limitleri (xlsx).

Yapılanlar
  (a) Tur 11'in 5 kaydı (5973 m.3/4/6/11/12): genelgeden başvuru yeri, başvuru süresi ve belge listesi; "üyesi olunan
      İhracatçı Birliği Genel Sekreterliği" incelemeci kuruluş olduğu için ihracatçı birliği üyeliği şartı (m.6 hariç:
      orada incelemeci kuruluş Bakanlıkça görevlendirilen İBGS); m.11'e e-ticaret deposu hükmü (genelge m.5/A).
  (b) 5986'dan 5 yeni kayıt (m.4, m.5, m.6, m.8, m.9). 2026 üst limitleri resmi xlsx'in "ŞİRKETLER" sütunundan
      (m.5 yalnız statü sahiplerine açık: "PERAKENDE E-TİCARET SİTELERİ" sütunu).
  (c) Kayıt 162 (5986 şemsiye): ikincil kaynaklı metin resmi Karar/Genelge/limit tablosuyla değiştirilir; şahıs
      işletmesi için E-İhracat Konsorsiyumu yolu (genelge m.33/7) eklenir. Şahıs için bu yol açık olduğundan kayda
      sirket_turleri kısıtı KONMAZ; madde düzeyindeki kayıtlara konur.
  (d) Kayıt 163: dayanağı 2573 sayılı Karar 18.08.2022'de mülga (Bakanlık sayfası "MÜLGA" yazıyor) -> aktif_mi=False.

Idempotent: durum_notu'nda "Tur12" varsa güncelleme atlanır; yeni kayıtlar kaynak_url ile denetlenir.

    python scripts/fix_veri_2026_10_08_eihracat_tur12.py             (dry-run, varsayılan)
    python scripts/fix_veri_2026_10_08_eihracat_tur12.py --uygula
    python scripts/fix_veri_2026_10_08_eihracat_tur12.py --self-test
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import SessionLocal, Tesvik  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOT = "Tur12 2026-10-08"
T = "https://ticaret.gov.tr/data/"
KARAR_5973 = T + "69afdacb269de120c032b73a/5973%20Say%C4%B1l%C4%B1%20Karar.pdf"
KARAR_5986 = T + "632b13e013b8767974670b91/E-ihracat%20Karar.pdf"
GENELGE_5986 = (T + "6447baf113b8761694f892bb/E-%C4%B0HRACAT%20DESTEKLER%C4%B0NE%20%C4%B0L%C4%B0%C5%9EK%C4%B0N%20"
                "GENELGE%2013.04.2026.pdf")
LIMIT_5986 = (T + "632b145a13b8767974670b9a/2026%20Y%C4%B1l%C4%B1na%20%C4%B0li%C5%9Fkin%20E-%C4%B0hracat%20"
              "Destekleri%20%C3%9Cst%20Limitleri.xlsx")
EKLER_5986 = T + "632b145a13b8767974670b9a/Genelge%20Ekleri-24.04.2026.zip"
SAYFA_163 = "https://ticaret.gov.tr/destekler/ihracat-destekleri/pazara-giriste-dijital-faaliyetlerin-desteklenmesi"

UYELIK = "Bir ihracatçı birliğine üye olmak (başvuru üyesi olunan İhracatçı Birliği Genel Sekreterliğine yapılır)"
DYS = "Ticaret Bakanlığı Destek Yönetim Sistemi (DYS) kaydı"
SIRKET = ("Şirket olmak: 6102 sayılı TTK md.124'teki şirketler ya da ticari/sınai faaliyette bulunan kooperatif "
          "(5986 sayılı Karar m.2); şahıs işletmesi doğrudan yararlanamaz")
TURK_URUN = ("Ürün Türk ürünü olmalı (üretimin tamamı ya da bir bölümü Türkiye'de); pazaryeri listelemesinde KTÜN, "
             "üretim yeri (Türkiye) ve tescilli marka bilgisi girilmeli (el işi/kişiselleştirilmiş ürünlerde KTÜN ve "
             "marka aranmayabilir)")
MADRID = ("Ön onay için WIPO Madrid Sistemi'ne taraf en az bir ülkede tescilli yurt dışı marka (yoksa önce 5973 m.4 "
          "Yurt Dışı Marka Tescil Desteği)")
YER_5986 = ("Önce ön onay, sonra ödeme başvurusu; ikisi de üyesi olunan İhracatçı Birliği Genel Sekreterliğine "
            "(incelemeci kuruluş) DYS üzerinden. İlk başvuruda EK-Şirket Başvuru Formu verilir.")
SURE_5986 = ("Destek süresi ön onay tarihini izleyen ayın ilk günü başlar; ödeme başvurusu ödeme belgesi tarihinden "
             "itibaren en geç 6 ay içinde, çeyrek dönemler itibarıyla")
HEDEF = ("Hedef ülkeler (EK-Hedef Ülkeler Listesi, 35 ülke): ABD, Almanya, Avustralya, Azerbaycan, BAE, Brezilya, "
         "Cezayir, Çin, Endonezya, Fas, Filipinler, Fransa, Güney Afrika, Güney Kore, Hindistan, İspanya, İtalya, "
         "Japonya, Kanada, Katar, Kenya, Kuveyt, Malezya, Meksika, Mısır, Nijerya, Portekiz, Romanya, Rusya, "
         "Sırbistan, Suudi Arabistan, Şili, Tayland, Tunus, Vietnam")
KRITER_SIRKET = {"sektorler": ["ihracat", "e-ticaret"], "tutar_niteligi": "hibe",
                 "sirket_turleri": ["limited", "anonim", "kooperatif"]}

# ------------------------------------------------------------------ (a) 5973 kayıtlarının genelge düzeyi bilgileri
GENELGE_5973 = {
    3: dict(kaynak=T + "63341ce713b8769ec0647ebe/30.06.2025%20PAZARA%20G%C4%B0R%C4%B0%C5%9E%20BELGES%C4%B0NE%20"
                       "%C4%B0L%C4%B0%C5%9EK%C4%B0N%20GENELGE.pdf",
            ek=T + "5b8d8f3013b876125c08b3a8/EK%201-A.pdf",
            yer="Üyesi olunan İhracatçı Birliği Genel Sekreterliğine (İBGS) DYS üzerinden",
            sure=("Pazara giriş belgesinin düzenlenme tarihinden (denetim/gözetimde rapor tarihinden, ruhsatlandırma ve "
                  "kayıtta ödeme belgesi tarihinden) itibaren 6 ay içinde"),
            belgeler=["Kapasite raporu / ekspertiz raporu / faaliyet belgesi", "Sözleşme ya da hizmet fiyat listesi",
                      "Test/analiz raporları için EK-2 icmal tablosu", "Pazara giriş belgesi (sertifika)",
                      "Belgeyi düzenleyen kuruluşun akreditasyon belgesi", "Fatura",
                      "Ödeme belgeleri (banka dekontu, kredi kartı ekstresi vb.)",
                      "İngilizce dışındaki belgelerin tercümeleri", "Sicil tasdiknamesi"],
            uyelik=True),
    4: dict(kaynak=T + "63341fab13b8769ec0647ed5/30.06.2025%20Yurtd%C4%B1%C5%9F%C4%B1%20Marka%20Tescil%20"
                       "Deste%C4%9Fine%20%C4%B0li%C5%9Fkin%20Genelge.pdf",
            ek=T + "63341fab13b8769ec0647ed5/Y5973M_Yurt_Disi_Marka_Tescil_EK1.doc",
            yer="Üyesi olunan İhracatçı Birliği Genel Sekreterliğine (incelemeci kuruluş) DYS üzerinden",
            sure="Ödeme belgesi tarihinden itibaren 6 ay içinde",
            belgeler=["Yurt içi marka tescil belgesi",
                      "Yurt dışı marka tescil belgesi ya da tescil başvurusu belgesi (İngilizce dışındaysa yeminli tercüme)",
                      "Fatura", "Tescile ilişkin ödeme belgeleri (banka dekontu, kredi kartı ekstresi, hesap dökümü)",
                      "Varsa avukatlık/hukuki danışmanlık faturası ve ödeme belgeleri",
                      "Varsa hukuki sürece ilişkin belgeler (ihtar yazısı, dava dilekçesi)"],
            uyelik=True, ek_sart="Yurt içi tescil ile yurt dışı tescil başvurusu aynı şirket adına olmalı"),
    6: dict(kaynak=T + "63403f5e13b87692b0e3b9fe/02.03.2026%20Yurt%20D%C4%B1%C5%9F%C4%B1%20Pazar%20Ara%C5%9Ft%C4%B1"
                       "rmas%C4%B1%20Deste%C4%9Fine%20%C4%B0li%C5%9Fkin%20Genelge.pdf",
            ek=T + "63403f5e13b87692b0e3b9fe/YDPA%20Genelge%20Ek-A-De%C4%9Fi%C5%9Fiklikler%20Derc%20edilmi%C5%9F%2015-04-2024.docx",
            yer="Bakanlıkça görevlendirilen İhracatçı Birliği Genel Sekreterliğine (incelemeci kuruluş) DYS üzerinden",
            sure="Şirket çalışanının Türkiye'ye giriş tarihinden itibaren en geç 3 ay içinde",
            belgeler=["Katılan personel için faaliyet ayına ait SGK bildirgesi (şirket ortağıysa ticaret sicili gazetesi "
                      "ya da pay cetveli)",
                      "Elektronik uçak bileti (ekonomi sınıfı) ve uçuşu kanıtlayan belge: biniş kartı, pasaportun giriş-"
                      "çıkış sayfaları ya da havayolu yazısı",
                      "Bilet acenteden alındıysa acentenin ayrıntılı faturası",
                      "Konaklama faturası (oda-kahvaltı tutarını gösteren ayrıntılı fatura)",
                      "Ödemenin bankacılık kanalıyla yapıldığını gösteren banka onaylı belge",
                      "Beyanname (EK A-2)", "Nüfus aile kayıt örneği (e-Devlet)"],
            uyelik=False),
    11: dict(kaynak=T + "633420e513b8769ec0647ee9/Birim%20Kira%20Deste%C4%9Fine%20%C4%B0li%C5%9Fkin%20Genelge.pdf",
             ek=T + "633420e513b8769ec0647ee9/Birim%20Kira%20Deste%C4%9Fine%20%C4%B0li%C5%9Fkin%20Genelge%20Ek1.docx",
             yer=("Üyesi olunan İhracatçı Birliği Genel Sekreterliğine (incelemeci kuruluş) DYS üzerinden; "
                  "e-ticaret depoları için KEP üzerinden"),
             sure="Ödeme belgesi tarihinden itibaren 6 ay içinde",
             belgeler=["Kapsama alınma: yurt dışı şirketin ortaklık yapısı ve tescil belgesi (yeminli tercümeli)",
                       "Kapsama alınma: kira ya da paylaşımlı ofis sözleşmesi (yeminli tercümeli)",
                       "Kapsama alınma: birimin fotoğraf/videoları (giriş, iç mekân)",
                       "Ödeme: kira/üyelik ya da reyon-stant komisyon ödemelerine ilişkin banka dekontu, kredi kartı "
                       "ekstresi, hesap dökümü",
                       "Ödeme: depo kirası ve depolama hizmeti için palet miktarını gösteren ayrıntılı fatura",
                       "E-ticaret deposu (KEP ile): Kapsama Alma Başvuru Formu, Ödeme Başvuru Formu, Ödeme Bilgileri "
                       "Formu, Yerinde İnceleme Formu"],
             uyelik=True,
             ek_detay=(" E-ticaret deposu (Birim Kira Genelgesi m.5/A): 5986 kapsamında Perakende E-Ticaret Sitesi, "
                       "Pazaryeri ya da E-İhracat Konsorsiyumu statüsü almış şirketlerin ürün depolama ve iade için "
                       "kiraladığı yurt dışı depolar; destek, depodaki Türkiye'de üretilmiş ürünlerin satış/çıkış oranı "
                       "üzerinden hesaplanır ve depo yönetim sisteminin çalışır olması gerekir.")),
    12: dict(kaynak=T + "6334210013b8769ec0647eec/Tan%C4%B1t%C4%B1m%20Deste%C4%9Fine%20%C4%B0li%C5%9Fkin%20Genelge.pdf",
             ek=T + "6334210013b8769ec0647eec/5973M_Tanitim_Destegi_EK2.docx",
             yer="Üyesi olunan İhracatçı Birliği Genel Sekreterliğine (incelemeci kuruluş) DYS üzerinden",
             sure="Ödeme belgesi tarihinden itibaren 6 ay içinde",
             belgeler=["Tanıtım, sponsorluk ya da PR sözleşmesi (yeminli tercümeli)",
                       "Fatura (faturalandırma özeti niteliğindeki ekstre kabul edilir)",
                       "Ödeme belgeleri (banka dekontu, kredi kartı ekstresi, hesap dökümü)",
                       "Tanıtım malzemeleri ve reklam görselleri",
                       "Dijital reklamlarda yayın ekran görüntüleri; arama motoru ve sosyal medya reklamlarında tıklama "
                       "sayısını ve tıklanan ülkeleri gösteren işlem raporu",
                       "Yurt dışı birimi yoksa: yurt içi marka tescil belgesi ve tanıtım ülkesindeki marka tescil belgesi "
                       "ya da başvurusu"],
             uyelik=True),
}

# --------------------------------------------------------------------------------- (b) 5986 madde düzeyi kayıtlar
ORTAK_SART_5986 = [SIRKET, UYELIK, DYS + "; MERSİS kaydı güncel ve NACE kodu doğru", TURK_URUN]

YENI_5986 = {
    4: dict(
        baslik="Dijital Pazaryeri Tanıtım (Reklam) Desteği (5986 sayılı Karar m.4)",
        ozet="Amazon, Etsy gibi yurt dışı pazaryerlerinde verilen reklamların giderinin %50'si (hedef ülkelerde %70), "
             "her pazaryeri için 3 yıl desteklenir.",
        detay=("Yurt dışı pazaryerlerinde tıklama başına ödeme, sipariş başına ödeme, görüntüleme reklamı ve ürün yorum "
               "hizmeti giderleri desteklenir; komisyon, üyelik ve diğer ücretler kapsam dışıdır (Genelge m.13). "
               "Reklamdan dönen satışların %20'sini aşmayan tanıtım gideri esas alınır: Satışların Reklam Maliyet Oranı "
               "(SRMO) en fazla %20, Reklam Dönüşüm Katsayısı (RDK) en az 5 (Karar m.4, Genelge m.13). Oran %50; hedef "
               "ülkelerde 20 puan artar (Genelge m.29). Her pazaryeri için 3 yıl. 2026 yıllık üst limit (şirketler, "
               "kademeye göre): 36.993.646 TL. " + HEDEF + "."),
        hedef_kitle="Ürünlerini yurt dışı pazaryerlerinde satan ve orada reklam veren şirketler",
        tutar="%50 (hedef ülkelerde %70); 2026 yıllık üst limit şirketler için 36.993.646 TL; pazaryeri başına 3 yıl",
        tutari_max=36_993_646,
        formul="Uygun reklam giderinin %50'si (hedef ülkede %70), SRMO ≤ %20; şirketler için 2026 yıllık en çok 36.993.646 TL",
        sartlar=[*ORTAK_SART_5986, MADRID, "Reklamlar yurt dışı pazaryerinde verilmeli; SRMO en fazla %20, RDK en az 5",
                 "Destekten önce ön onay alınmalı"],
        belgeler=["EK-Şirket Başvuru Formu (ilk başvuruda)", "EK-Dijital Pazaryeri Tanıtım Desteği Ön Onay Başvuru Formu",
                  "Madrid Sistemi'ne taraf bir ülkede yurt dışı marka tescil belgesi",
                  "Pazaryerinin bu hizmet için daha önce düzenlediği fatura örneği",
                  "Ödeme başvurusu: EK-Dijital Pazaryeri Tanıtım Desteği Ödeme Başvuru Formu, pazaryerinden alınan dönem "
                  "raporu, fatura/ekstre, ödeme belgeleri, pazaryeri ile sözleşme"],
        sure="Pazaryeri başına 3 yıl"),
    6: dict(
        baslik="Sipariş Karşılama (Fulfillment) Hizmeti Desteği (5986 sayılı Karar m.6)",
        ozet="Yurt dışında pazaryerinden ya da listedeki firmalardan alınan sipariş karşılama ve depolama hizmetinin "
             "%50'si (hedef ülkelerde %70), ülke başına 3 yıl desteklenir.",
        detay=("Birim başına sipariş karşılama (iade kabul dâhil) ve depolama giderleri desteklenir; komisyon, üyelik, "
               "ürün geri çekme/imha kapsam dışıdır (Genelge m.15). Hizmet, Bakanlığın 'Sipariş Karşılama Hizmeti Sunan "
               "Firma Listesi'ndeki firmalardan ya da doğrudan ilgili pazaryerinden alınmalıdır. Destek, ilgili ülkedeki "
               "toplam e-ticaret satışının %10'una kadar; AB ülkeleri için tek ön onay tüm AB'de süre hesabına sayılır. "
               "Oran %50, hedef ülkelerde 20 puan artar. 2026 yıllık üst limit (şirketler): 36.993.646 TL."),
        hedef_kitle="Yurt dışı pazaryerinde ya da kendi sitesinden satış yapıp yurt dışında fulfillment hizmeti alan şirketler",
        tutar="%50 (hedef ülkelerde %70); ülkedeki e-ticaret satışlarının %10'una kadar; 2026 şirketler için yıllık "
              "36.993.646 TL; ülke başına 3 yıl", tutari_max=36_993_646,
        formul="Fulfillment gideri × %50 (hedef ülkede %70), ülke e-ticaret satışının %10'u ve 2026 yıllık 36.993.646 TL ile sınırlı",
        sartlar=[*ORTAK_SART_5986, MADRID, "Hizmet Bakanlık listesindeki firmalardan ya da pazaryerinden alınmalı",
                 "Destekten önce ön onay alınmalı"],
        belgeler=["EK-Şirket Başvuru Formu (ilk başvuruda)", "EK-Sipariş Karşılama Hizmeti Desteği Ön Onay Başvuru Formu",
                  "Madrid Sistemi'ne taraf bir ülkede yurt dışı marka tescil belgesi",
                  "Hizmet sağlayıcının daha önce düzenlediği fatura örneği",
                  "Ödeme başvurusu: ürün başına sipariş karşılama giderlerini gösteren dönem raporu, fatura, ödeme "
                  "belgeleri, pazaryeri dışı sağlayıcıda hizmet sözleşmesi, ülkedeki e-ticaret satışları tablosu"],
        sure="Ülke başına 3 yıl"),
    9: dict(
        baslik="Yurt Dışı Pazaryeri Komisyon Gideri Desteği (5986 sayılı Karar m.9)",
        ozet="Hedef ülkelerdeki yurt dışı pazaryerlerine ödenen satış komisyonlarının %50'si 3 yıl desteklenir.",
        detay=("EK-Hedef Ülkeler Listesi'ndeki ülkelerde faaliyet gösteren yurt dışı pazaryerlerinin komisyon giderleri "
               "%50 oranında, 3 yıl desteklenir (Karar m.9, Genelge m.19). Hak ediş aylık hesaplanır, harcama belgeleri "
               "çeyrek dönemler itibarıyla sunulur. 2026 yıllık üst limit (şirketler): 3.698.274 TL. " + HEDEF + "."),
        hedef_kitle="Hedef ülkelerdeki yurt dışı pazaryerlerinde satış yapan şirketler",
        tutar="%50; 2026 şirketler için yıllık 3.698.274 TL; 3 yıl", tutari_max=3_698_274,
        formul="Komisyon giderinin %50'si; şirketler için 2026 yıllık en çok 3.698.274 TL",
        sartlar=[*ORTAK_SART_5986, MADRID, "Pazaryeri hedef ülkelerden birinde olmalı", "Destekten önce ön onay alınmalı"],
        belgeler=["EK-Şirket Başvuru Formu (ilk başvuruda)", "EK-Pazaryeri Komisyon Desteği Ön Onay Başvuru Formu",
                  "Madrid Sistemi'ne taraf bir ülkede yurt dışı marka tescil belgesi",
                  "E-İhracat Konsorsiyumu bünyesindeyse ilişkiyi gösteren belge (pazarlama sözleşmesi)",
                  "Ödeme başvurusu: EK-Pazaryeri Komisyon Desteği Ödeme Başvuru Formu, fatura/ekstre, ödeme belgeleri, "
                  "pazaryerinden alınan dönem raporu"],
        sure="3 yıl"),
    8: dict(
        baslik="Çevrim İçi Mağaza ve Hedef Ülke E-Ticaret Paydaşı Hizmet Desteği (5986 sayılı Karar m.8)",
        ozet="Hedef ülkelerdeki yurt dışı pazaryerlerinde mağaza açılışı, tasarımı, yıllık ödemeleri ve listedeki "
             "danışmanlık hizmetleri %50 oranında, ülke başına 3 yıl desteklenir; şirketlerde 1 milyon USD ihracat şartı var.",
        detay=("Şirketler için şart: önceki takvim yılında gümrük beyannamesi (GB) ile ihracat ve basitleştirilmiş gümrük "
               "beyannamesinde (BGB) e-ticaret olarak beyan edilen ihracat toplamı 1.000.000 ABD dolarının üzerinde olmalı "
               "(Genelge m.18). Hedef ülkelerdeki pazaryerlerinde mağaza hesabı açılışı, tasarım, yıllık ödemeler ve "
               "'E-Ticaret Paydaşından Alınabilecek Danışmanlık Hizmetleri Listesi'ndeki giderler desteklenir; satış "
               "komisyonu ve depozito kapsam dışı. Aynı pazaryeri için birden fazla paydaştan destek alınamaz. "
               "2026 yıllık üst limit (şirketler): 7.396.548 TL."),
        hedef_kitle="Önceki yıl 1 milyon USD üzeri ihracatı olan ve hedef ülke pazaryerlerinde mağaza açan şirketler",
        tutar="%50; 2026 şirketler için yıllık 7.396.548 TL; ülke başına 3 yıl", tutari_max=7_396_548,
        formul="Uygun giderin %50'si; şirketler için 2026 yıllık en çok 7.396.548 TL",
        sartlar=[*ORTAK_SART_5986,
                 "Önceki yıl GB + BGB (e-ticaret) ihracat toplamı 1.000.000 ABD dolarının üzerinde olmalı",
                 "Pazaryeri hedef ülkelerden birinde olmalı", "Destekten önce ön onay alınmalı"],
        belgeler=["EK-Şirket Başvuru Formu (ilk başvuruda)", "EK-Çevrim İçi Mağaza Desteği Ön Onay Başvuru Formu ve ekleri",
                  "EK-Çevrim İçi Mağaza Desteği Ödeme Başvuru Formu ve ekleri"],
        sure="Ülke başına 3 yıl"),
    5: dict(
        baslik="E-İhracat Tanıtım Desteği — Perakende E-Ticaret Sitesi Statüsü (5986 sayılı Karar m.5)",
        ozet="Kendi e-ticaret sitesinin yurt dışı pazarlama giderleri %50 (hedef ülkelerde %70) desteklenir; yalnız "
             "Perakende E-Ticaret Sitesi, pazaryeri, B2B ya da konsorsiyum statüsü alanlar yararlanır.",
        detay=("Destek yalnız statü sahiplerine açıktır (Genelge m.14); statüsüz şirketin kendi sitesinin yurt dışı reklamı "
               "için yol 5973 m.12 Tanıtım Desteğidir. Perakende E-Ticaret Sitesi statüsü şartları (Genelge m.7): önceki "
               "yıl satış hasılatının en az 2/3'ü çevrim içi; satışların en az 1/4'ü kendi (ya da organik bağlı) "
               "markaları; faturalandırma kendi tüzel kişiliği üzerinden; iş merkezi Türkiye'de; en az bir sitenin son "
               "2 yılda faaliyette olması; güven damgası ya da uluslararası altyapı sağlayıcı hizmeti; ödeme ve lojistik "
               "entegrasyonu; önceki yıl ihracat en az 500.000 ABD doları ya da ETBİS net satışları en az 1.000.000.000 TL. "
               "Statü başvurusu E-İhracat Sekretaryasına yapılır. Oran %50, hedef ülkelerde 20 puan artar; ülke başına "
               "3 yıl. 2026 yıllık üst limit (perakende e-ticaret siteleri): 123.315.792 TL."),
        hedef_kitle="Kendi e-ticaret sitesiyle yurt dışına satan ve Perakende E-Ticaret Sitesi statüsü şartlarını "
                    "karşılayan (önceki yıl ≥500.000 USD ihracat vb.) şirketler",
        tutar="%50 (hedef ülkelerde %70); 2026 perakende e-ticaret siteleri için yıllık 123.315.792 TL; ülke başına 3 yıl",
        tutari_max=123_315_792,
        formul="Uygun pazarlama giderinin %50'si (hedef ülkede %70); statü sahibi perakende sitelerde 2026 yıllık en çok 123.315.792 TL",
        sartlar=[*ORTAK_SART_5986,
                 "Perakende E-Ticaret Sitesi (ya da pazaryeri/B2B/konsorsiyum) statüsü alınmış olmalı",
                 "Statü için: önceki yıl ihracat ≥ 500.000 USD ya da ETBİS net satış ≥ 1.000.000.000 TL; satışların en az "
                 "2/3'ü çevrim içi; en az 1/4'ü kendi markaları; en az bir site son 2 yıldır faaliyette; güven damgası",
                 "Giderler EK-E-İhracat Tanıtım Faaliyetleri Listesi'nde olmalı; destekten önce ön onay alınmalı"],
        belgeler=["EK-Perakende E-Ticaret Sitesi Başvuru Formu (statü; E-İhracat Sekretaryasına)",
                  "EK-E-İhracat Tanıtım Desteği Ön Onay Formu",
                  "EK-E-İhracat Tanıtım Desteği Ödeme Başvuru Formu ve ekleri"],
        sure="Ülke başına 3 yıl"),
}

# ------------------------------------------------------------------------------- (c) 162 şemsiye kaydın düzeltmesi
KAYIT_162 = dict(
    ozet=("E-ihracat yapan şirketlerin yurt dışı pazaryeri reklamı, sipariş karşılama, pazaryeri komisyonu, çevrim içi "
          "mağaza ve (statü sahiplerinde) kendi sitesinin tanıtım giderleri %50 oranında (bazı kalemlerde hedef "
          "ülkelerde %70) 3 yıl desteklenir."),
    detay=("5986 sayılı E-İhracat Destekleri Hakkında Karar ve 13.04.2026 tarihli Genelge. Yararlanıcılar: şirketler "
           "(TTK md.124 şirketleri ve kooperatifler), perakende e-ticaret siteleri, pazaryerleri, B2B platformları ve "
           "E-İhracat Konsorsiyumları; her biri tek statüyle yararlanır. Statüsüz şirketin yararlanabildiği kalemler: "
           "dijital pazaryeri reklamı, sipariş karşılama, pazaryeri komisyonu, (önceki yıl 1 milyon USD üzeri ihracatla) "
           "çevrim içi mağaza. Kendi sitesinin yurt dışı pazarlaması (e-ihracat tanıtım) yalnız Perakende E-Ticaret "
           "Sitesi statüsüyle (önceki yıl ≥500.000 USD ihracat vb.). Şahıs işletmesi (esnaf muafiyetli ya da sicile "
           "kayıtlı) doğrudan yararlanamaz; bir E-İhracat Konsorsiyumu onun adına açtığı pazaryeri hesaplarıyla belirli "
           "bir süre aracılık edebilir, süre sonunda ancak şirket ya da kooperatif üyesi olarak devam edilir (Genelge "
           "m.33/7). 2026 toplam yıllık üst limitler: şirketler 73.990.019 TL; perakende e-ticaret siteleri, pazaryerleri "
           "ve konsorsiyumlar 221.970.061 TL. Kalemlere göre ayrıntı ayrı kayıtlarda (5986 m.4, m.5, m.6, m.8, m.9)."),
    tesvil_tutari=("%50 (dijital pazaryeri reklamı, e-ihracat tanıtımı ve sipariş karşılamada hedef ülkelerde %70); 2026 "
                   "toplam yıllık üst limit şirketler için 73.990.019 TL"),
    tutari_max=73_990_019.0,
    tutari_hesaplama_formulu=("Kalem bazında giderin %50'si (hedef ülkelerde bazı kalemlerde %70); 2026 yıllık toplam "
                              "en çok 73.990.019 TL (şirketler) — kalem limitleri ilgili kayıtlarda"),
    basvuru_sartlari=[UYELIK, DYS + "; MERSİS kaydı güncel ve NACE kodu doğru",
                      "Şirket ya da kooperatif olmak (şahıs işletmesi yalnız E-İhracat Konsorsiyumu aracılığıyla, sınırlı süre)",
                      TURK_URUN, "Her destek kalemi için önce ön onay alınmalı"],
    gerekli_belgeler=["EK-Şirket Başvuru Formu (ilk başvuruda; marka tescil belgesi, tedarik ediliyorsa tedarik belgesi, "
                      "üreticiyse kapasite raporu)", "Kaleme özel ön onay ve ödeme başvuru formları (Genelge Ekleri)"],
    basvuru_yeri=YER_5986,
    basvuru_suresi=SURE_5986,
)


def kaynak_5986(madde: int) -> str:
    return f"{KARAR_5986}#madde-{madde}"


def _not(t: Tesvik, metin: str) -> None:
    t.durum_notu = ((t.durum_notu + " | ") if t.durum_notu else "") + f"{NOT}: {metin}"


def uygula(db, dry_run: bool = True) -> dict:
    say = {"guncellenen": 0, "eklenen": 0, "pasif": 0, "atlanan": 0}
    # (a)
    for madde, v in GENELGE_5973.items():
        t = db.query(Tesvik).filter(Tesvik.kaynak_url == f"{KARAR_5973}#madde-{madde}").first()
        if t is None:
            raise SystemExit(f"5973 m.{madde} kaydı yok: önce tur11 uygulanmalı")
        if NOT in (t.durum_notu or ""):
            say["atlanan"] += 1
            continue
        print(f"[5973 m.{madde}] {t.baslik[:60]}: yer/süre/{len(v['belgeler'])} belge"
              + (" + üyelik şartı" if v["uyelik"] else ""))
        if not dry_run:
            t.basvuru_yeri, t.basvuru_suresi, t.gerekli_belgeler = v["yer"], v["sure"], v["belgeler"]
            sartlar = list(t.basvuru_sartlari or [])
            if v["uyelik"] and UYELIK not in sartlar:
                sartlar.insert(1, UYELIK)
            if v.get("ek_sart") and v["ek_sart"] not in sartlar:
                sartlar.append(v["ek_sart"])
            t.basvuru_sartlari = sartlar
            if v.get("ek_detay") and "E-ticaret deposu" not in (t.detay or ""):
                t.detay = (t.detay or "") + v["ek_detay"]
            _not(t, f"başvuru yeri/süresi/belgeler genelgeden ({v['kaynak']}; ek {v['ek']})")
        say["guncellenen"] += 1
    # (b)
    for madde, v in YENI_5986.items():
        if db.query(Tesvik).filter(Tesvik.kaynak_url == kaynak_5986(madde)).first():
            say["atlanan"] += 1
            continue
        print(f"[5986 m.{madde}] YENİ {v['baslik']} — {v['tutar']}")
        if not dry_run:
            db.add(Tesvik(
                kurum="Ticaret Bakanlığı", baslik=v["baslik"], ozet=v["ozet"], detay=v["detay"],
                hedef_kitle=v["hedef_kitle"], kaynak_url=kaynak_5986(madde), kategori="e_ticaret_ihracat",
                tesvil_tutari=v["tutar"], tutari_max=float(v["tutari_max"]), tutari_hesaplama_kriteri="genel",
                tutari_hesaplama_formulu=v["formul"], uygunluk_kriterleri=dict(KRITER_SIRKET),
                basvuru_sartlari=v["sartlar"], gerekli_belgeler=v["belgeler"], basvuru_yeri=YER_5986,
                basvuru_suresi=SURE_5986, destek_verilme_suresi=v["sure"], aktif_mi=True,
                durum_notu=(f"{NOT}: 5986 sayılı Karar m.{madde} ({KARAR_5986}), Genelge 13.04.2026 ({GENELGE_5986}), "
                            f"2026 üst limit tablosu ({LIMIT_5986}), Genelge ekleri ({EKLER_5986})")))
        say["eklenen"] += 1
    # (c)
    t = db.get(Tesvik, 162)
    if t is None or "5986" not in t.baslik:
        raise SystemExit("162 beklenen 5986 kaydı değil; durduruldu")
    if NOT not in (t.durum_notu or ""):
        print("[162] 5986 şemsiye kaydı resmi Karar/Genelge/limitlerle düzeltiliyor")
        if not dry_run:
            for alan, deger in KAYIT_162.items():
                setattr(t, alan, deger)
            _not(t, f"metin resmi Karar ({KARAR_5986}), Genelge 13.04.2026 ve 2026 limit tablosuyla değiştirildi; "
                    f"önceki not 'ikincil kaynaklar' idi")
        say["guncellenen"] += 1
    else:
        say["atlanan"] += 1
    # (d)
    t = db.get(Tesvik, 163)
    if t is None or "Dijital Faaliyet" not in t.baslik:
        raise SystemExit("163 beklenen kayıt değil; durduruldu")
    if t.aktif_mi:
        print("[163] 2573 sayılı Karar mülga (18.08.2022) -> pasif")
        if not dry_run:
            t.aktif_mi = False
            _not(t, f"dayanağı 2573 sayılı Karar 18.08.2022'de mülga (Bakanlık sayfası: {SAYFA_163}); güncel "
                    f"karşılığı 5986 m.8 Çevrim İçi Mağaza ve m.4 Dijital Pazaryeri Tanıtım desteği")
        say["pasif"] += 1
    else:
        say["atlanan"] += 1
    if not dry_run:
        db.commit()
    return say


def _self_test() -> int:
    k = [
        ("5973 genelge bilgisi 5 kaydın hepsinde", sorted(GENELGE_5973) == [3, 4, 6, 11, 12]
         and all(v["yer"] and v["sure"] and v["belgeler"] for v in GENELGE_5973.values())),
        ("süreler genelgeyle tutarlı (m.6 3 ay, diğerleri 6 ay)", "3 ay" in GENELGE_5973[6]["sure"]
         and all("6 ay" in GENELGE_5973[m]["sure"] for m in (3, 4, 11, 12))),
        ("üyelik şartı m.6 hariç", [m for m, v in GENELGE_5973.items() if not v["uyelik"]] == [6]),
        ("5986 2026 limitleri xlsx 'ŞİRKETLER' sütunu", {m: v["tutari_max"] for m, v in YENI_5986.items() if m != 5}
         == {4: 36_993_646, 6: 36_993_646, 9: 3_698_274, 8: 7_396_548}),
        ("m.5 yalnız statü sahipleri, limit perakende sütunu", YENI_5986[5]["tutari_max"] == 123_315_792
         and any("statüsü alınmış" in s for s in YENI_5986[5]["sartlar"])),
        ("m.8 1 milyon USD şartı", any("1.000.000 ABD" in s for s in YENI_5986[8]["sartlar"])),
        ("komisyon (m.9) hedef ülke artışı yazılmadı (Genelge m.29 kapsamı dışında)", "%70" not in YENI_5986[9]["tutar"]),
        ("madde kayıtlarında şirket türü kısıtı, şemsiyede yok", "sirket_turleri" in KRITER_SIRKET
         and "sirket_turleri" not in KAYIT_162),
        ("şahıs için konsorsiyum yolu yazıldı", "Konsorsiyumu" in KAYIT_162["detay"] and "m.33/7" in KAYIT_162["detay"]),
        ("tutar metni sayıyla tutarlı", all(f"{v['tutari_max']:,}".replace(",", ".") in v["tutar"] for v in YENI_5986.values())),
        ("hedef ülke listesi 35 ülke", len(HEDEF.split("): ", 1)[1].split(", ")) == 35),
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
        s = uygula(db, dry_run=not a.uygula)
        print(f"\n{'UYGULANDI' if a.uygula else 'DRY-RUN'}: {s}")
    finally:
        db.close()
