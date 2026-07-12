"""
81 il icin KOSGEB Mudurlugu iletisim rehberini doldurur.

TARIM'IN AKSINE BURADA HEPSI DOGRULANDI: her satir KOSGEB'in kendi
"mudurluktekil?ID={plaka}" sayfasindan WebFetch ile TEK TEK cekildi
(2026-07-12) - il adi -> plaka kodu -> gercek sayfa icerigi. Deseni
tahmin edip URL uretmedik.

Calistirma: python scripts/seed_il_kosgeb_mudurlugu.py
Idempotent: mevcut il satirlarini gunceller.
"""
from datetime import date

from app.models import SessionLocal, IlKosgebMudurlugu, init_db

DOGRULAMA_TARIHI = date(2026, 7, 12)


def _kaynak(il_kodu: int) -> str:
    return f"https://www.kosgeb.gov.tr/site/tr/genel/mudurluktekil?ID={il_kodu}"


# il_kodu: (il_adi, mudurluk_adi, telefon, adres, eposta, ek_mudurlukler)
VERI = {
    1: ("Adana", "KOSGEB ADANA MÜDÜRLÜĞÜ", "0 (322) 455 42 99", "Yeşiloba Mahallesi Sanayi Sitesi 1150/58 Sokak 34.Blok No:28 P.K.:01110 Seyhan/ADANA", "adana@kosgeb.gov.tr", None),
    2: ("Adıyaman", "KOSGEB ADIYAMAN MÜDÜRLÜĞÜ", "0 (416) 219 20 52", "Petrol Mahallesi, Organize Sanayi Bölgesi, 1.Cadde No:6 ADIYAMAN", "adiyaman@kosgeb.gov.tr", None),
    3: ("Afyonkarahisar", "KOSGEB Afyonkarahisar Müdürlüğü", "0 (272) 219 50 10", "Karaman Mahallesi Albay Reşat Çiğiltepe Caddesi Karaman İş Merkezi No: 9 Kat: 5 Merkez/AFYONKARAHİSAR", None, None),
    4: ("Ağrı", "KOSGEB Ağrı Müdürlüğü", "0 (472) 217 16 45", "Gazi Mahallesi Erzurum Caddesi Kültür ve Kongre Merkezi Kat:4 Merkez/AĞRI", "agri@kosgeb.gov.tr", None),
    5: ("Amasya", "KOSGEB AMASYA MÜDÜRLÜĞÜ", "0 (358) 211 01 00", "İhsaniye Mahallesi Zübeyde Hanım Caddesi Kat:2 No: 101 Merkez/AMASYA", "amasya@kosgeb.gov.tr", None),
    6: ("Ankara", "KOSGEB Ankara OSTİM Müdürlüğü", "0 312 595 25 83", "Uzayçağı Cad. No:146 Ostim - Yenimahalle / ANKARA", "ankaraostim@kosgeb.gov.tr",
        [{"ad": "KOSGEB Ankara Sincan Müdürlüğü", "telefon": "0 312 595 25 85", "adres": "1. Organize Sanayi Bölgesi Dökümcüler Sitesi No:203 06935 Sincan / ANKARA", "eposta": "ankarasincan@kosgeb.gov.tr"}]),
    7: ("Antalya", "KOSGEB ANTALYA MÜDÜRLÜĞÜ", "0 (242) 595 01 10", "Yenigün Mahallesi Mevlana Kavşağı Kızılırmak Caddesi No:6 ANTALYA", "antalya@kosgeb.gov.tr", None),
    8: ("Artvin", "KOSGEB ARTVİN MÜDÜRLÜĞÜ", "0 (466) 215 11 00", "Çarşı Mah. Sabit Osman Avcı Cad. No:33 ARTVİN", "artvin@kosgeb.gov.tr", None),
    9: ("Aydın", "KOSGEB AYDIN MÜDÜRLÜĞÜ", "0 (256) 218 24 30", "Aydın Ticaret Borsası Binası 7. Katı (Ata Mah. Denizli Bulvarı No:18) P.K:09010", None, None),
    10: ("Balıkesir", "KOSGEB BALIKESİR MÜDÜRLÜĞÜ", "0 (266) 289 23 30", "Kasaplar Mahallesi 11004 Sokak No: 6A, 10100, Altıeylül/BALIKESİR", None, None),
    11: ("Bilecik", "KOSGEB BİLECİK MÜDÜRLÜĞÜ", "0 (228) 214 20 00", "İstiklal Mahallesi, Tevfik Bey Caddesi No:55 Merkez/BİLECİK", "bilecik@kosgeb.gov.tr", None),
    12: ("Bingöl", "KOSGEB Bingöl Müdürlüğü", "0 (426) 219 01 10", "Simani Mah. Bingöl Muş Bulvarı Blok No:167 Bingöl TSO Binası Kat:2", None, None),
    13: ("Bitlis", "KOSGEB BİTLİS MÜDÜRLÜĞÜ", "0 (434) 222 93 50", "Taş Mah. Kız Meslek Lisesi Bitişiği Merkez / BİTLİS", None, None),
    14: ("Bolu", "KOSGEB BOLU MÜDÜRLÜĞÜ", "0 (374) 254 38 70", "Tabaklar Mah. İzzet Baysal Cad. No:75 BOLU", "bolu@kosgeb.gov.tr", None),
    15: ("Burdur", "KOSGEB BURDUR MÜDÜRLÜĞÜ", "0 (248) 213 48 50", "Çeşmedamı Mah. Çiloğlu Sok. No:12", "burdur@kosgeb.gov.tr", None),
    16: ("Bursa", "KOSGEB Bursa Müdürlüğü", "0 (224) 275 77 70", "Üçevler Mah 2. Sk. No 12 KOSGEB Binası 16120 Nilüfer/BURSA", "bursa@kosgeb.gov.tr", None),
    17: ("Çanakkale", "KOSGEB ÇANAKKALE MÜDÜRLÜĞÜ", "0 (286) 295 32 00", "Troya Caddesi No:136/A ÇANAKKALE", None, None),
    18: ("Çankırı", "KOSGEB ÇANKIRI MÜDÜRLÜĞÜ", "0 (376) 218 94 00", "Abdulhalik Renda Mahallesi Ankara Caddesi Hükümet Konağı No:38 H1 Blok Kat:4 Merkez/ÇANKIRI", "cankiri@kosgeb.gov.tr", None),
    19: ("Çorum", "KOSGEB ÇORUM MÜDÜRLÜĞÜ", "0 (364) 211 17 30", "Karakeçili Mahallesi, Gazi Caddesi, No:55 (Çorum Valiliği Ek Bina Kat:1)", "corum@kosgeb.gov.tr", None),
    20: ("Denizli", "KOSGEB DENİZLİ MÜDÜRLÜĞÜ", "0 (258) 295 80 49", "Muratdede Mahallesi Merkezefendi Caddesi No:30 Merkezefendi/DENİZLİ", "denizli@kosgeb.gov.tr", None),
    21: ("Diyarbakır", "KOSGEB DİYARBAKIR MÜDÜRLÜĞÜ", "0 (412) 383 20 00", "Topraktaş Mah. Topraktaş Cad. No: 71/A Şanlıurfa Karayolu 20. Km. Bağlar/DİYARBAKIR", "diyarbakir@kosgeb.gov.tr", None),
    22: ("Edirne", "KOSGEB Edirne Müdürlüğü", "0 (284) 215 38 69", "Çavuşbey Mah. Hükümet Cad. Edirne Valiliği Kompleksi Vilayet Binası Kat:2 EDİRNE", None, None),
    23: ("Elazığ", "KOSGEB ELAZIĞ MÜDÜRLÜĞÜ", "0 (424) 234 65 66", "Cumhuriyet Mahallesi Korgeneral Hulusi Sayın Caddesi No: 117 Merkez/ELAZIĞ", None, None),
    24: ("Erzincan", "KOSGEB ERZİNCAN MÜDÜRLÜĞÜ", "0 (446) 221 30 00", "Atatürk Mahallesi Muhsin Yazıcıoğlu Caddesi No:10 Kat:2 Merkez/ERZİNCAN", None, None),
    25: ("Erzurum", "KOSGEB Erzurum Müdürlüğü", "0 (442) 232 03 89", "Organize Sanayi Bölgesi Yönetim Cad. P.K.:25090", "erzurum@kosgeb.gov.tr", None),
    26: ("Eskişehir", "KOSGEB Eskişehir Müdürlüğü", "0 (222) 211 02 30", "Sümer Mahallesi Basın Şehitleri Caddesi No: 341 Odunpazarı/ESKİŞEHİR", None, None),
    27: ("Gaziantep", "KOSGEB GAZİANTEP MÜDÜRLÜĞÜ", "0 (342) 211 15 65", "Gaziantep Üniversitesi Teknopark Yerleşkesi Blok No:4/C 27260 Şahinbey/GAZİANTEP", "gaziantep@kosgeb.gov.tr", None),
    28: ("Giresun", "KOSGEB GİRESUN MÜDÜRLÜĞÜ", "0 (454) 210 25 00", "Gedikkaya Mah. Nihatbey Cad. No:6 28100", "giresun@kosgeb.gov.tr", None),
    29: ("Gümüşhane", "KOSGEB GÜMÜŞHANE MÜDÜRLÜĞÜ", "0 (456) 270 55 00", "Hasanbey Mahallesi Cumhuriyet Caddesi No:99/B", "gumushane@kosgeb.gov.tr", None),
    30: ("Hakkari", "KOSGEB HAKKARİ MÜDÜRLÜĞÜ", "0 (438) 216 00 16", "Bulak Mah. Kayacan Caddesi No:16 Kat:4 HATSO Binası / HAKKARİ", "hakkari@kosgeb.gov.tr", None),
    31: ("Hatay", "KOSGEB HATAY MÜDÜRLÜĞÜ", "0 (326) 219 10 33", "Yenişehir Mah. Atatürk Bulvarı No:47/B İskenderun/HATAY", "hatay@kosgeb.gov.tr", None),
    32: ("Isparta", "KOSGEB ISPARTA MÜDÜRLÜĞÜ", "0 (246) 211 68 99", "Sanayi Mah. 153. Cad. No:32 / ISPARTA", "isparta@kosgeb.gov.tr", None),
    33: ("Mersin", "KOSGEB MERSİN MÜDÜRLÜĞÜ", "0 324 241 11 69", "Bahçelievler Mah. Okan Merzeci Bulvarı Numara 470 Yenişehir/MERSİN", "mersin@kosgeb.gov.tr", None),
    34: ("İstanbul", "KOSGEB İstanbul İkitelli Müdürlüğü", "0 (212) 405 41 50", "İkitelli Organize Sanayi Bölgesi ESKOOP Sanayi Sitesi P.K.:34306 İkitelli/İSTANBUL", None,
        [{"ad": "KOSGEB İstanbul İMES Müdürlüğü", "telefon": "0 (216) 528 02 40", "adres": "İMES Sanayi Sitesi 308.Sok. C Blok No:46 Y.Dudullu P.K:81230 İSTANBUL", "eposta": None}]),
    35: ("İzmir", "KOSGEB İZMİR MÜDÜRLÜĞÜ", "0 (232) 270 15 60", "Atatürk OSB 10013 Sok. P.K:35477 Çiğli/İZMİR", "izmir@kosgeb.gov.tr",
        [{"ad": "İzmir Müdürlüğü Ek Bina", "telefon": "0 312 595 25 35", "adres": "Ege Üniversitesi Kampüsü, Erzene Mah. Ege Üniversitesi No: 172/47 Bornova/İZMİR", "eposta": "izmir@kosgeb.gov.tr"}]),
    36: ("Kars", "KOSGEB KARS MÜDÜRLÜĞÜ", "0 (474) 229 15 95", "Yenişehir Mahallesi Ali Gaffar Okkan Bulvarı No: 6A Merkez/KARS", None, None),
    37: ("Kastamonu", "KOSGEB KASTAMONU MÜDÜRLÜĞÜ", "0 (366) 213 90 60", "Hepkebirler Mah. Adalet Cad. No: 2 PK:37100", None, None),
    38: ("Kayseri", "KOSGEB KAYSERİ MÜDÜRLÜĞÜ", "0 (352) 315 44 99", "Organize Sanayi Bölgesi 9.Cad No:1/A Anbar/KAYSERİ", "kayseri@kosgeb.gov.tr", None),
    39: ("Kırklareli", "KOSGEB KIRKLARELİ MÜDÜRLÜĞÜ", "0 (288) 221 99 99", "Karacaibrahim Mah. Kurtuluş Cad. Uzunlar Apt. No: 48/B Merkez/KIRKLARELİ", "kirklareli@kosgeb.gov.tr", None),
    40: ("Kırşehir", "KOSGEB KIRŞEHİR MÜDÜRLÜĞÜ", "0 (386) 211 20 14", "Güldiken Mahallesi Şehit Metin Koca Caddesi No:17 Kat:2", "kirsehir@kosgeb.gov.tr", None),
    41: ("Kocaeli", "KOSGEB Kocaeli Müdürlüğü", "0 (262) 315 19 20", "Mehmet Ali Paşa Mah. Adnan Menderes Bulvarı No:11 İzmit/KOCAELİ", None, None),
    42: ("Konya", "KOSGEB KONYA MÜDÜRLÜĞÜ", "0 (332) 310 19 30", "Ferhuniye Mahallesi Mümtazkoru Sokak No:10/1 Selçuklu/KONYA", "konya@kosgeb.gov.tr", None),
    43: ("Kütahya", "KOSGEB KÜTAHYA MÜDÜRLÜĞÜ", "0 (274) 229 50 30", "75. Yıl Mh. Bekir Sıtkı Paşa Cd. No:37/2 Merkez/KÜTAHYA", None, None),
    44: ("Malatya", "KOSGEB MALATYA MÜDÜRLÜĞÜ", "0 (422) 328 73 30", "1. Organize Sanayi Bölgesi İdare Merkezi P.K.:44200", "malatya@kosgeb.gov.tr", None),
    45: ("Manisa", "KOSGEB MANİSA MÜDÜRLÜĞÜ", "0 (236) 226 18 11", "Manisa Ticaret ve Sanayi Odası Mimar Sinan Bulvarı No:127 1. Kat Yunusemre/MANİSA", "manisa@kosgeb.gov.tr", None),
    46: ("Kahramanmaraş", "KOSGEB Kahramanmaraş Müdürlüğü", "0 (344) 228 88 15", "Menderes Mah. Trabzon Bulvarı 46044. Sokak No: 14 Dulkadiroğlu/KAHRAMANMARAŞ", None, None),
    47: ("Mardin", "KOSGEB MARDİN MÜDÜRLÜĞÜ", "0 (482) 213 98 60", "Organize Sanayi Bölgesi 1.Bulvar MARDİN", "mardin@kosgeb.gov.tr", None),
    48: ("Muğla", "KOSGEB MUĞLA MÜDÜRLÜĞÜ", "0 (252) 211 23 60", "Muslihittin Mah. Mehmet Polatoğlu Cad. No:22/12 Menteşe/MUĞLA", "mugla@kosgeb.gov.tr", None),
    49: ("Muş", "KOSGEB MUŞ MÜDÜRLÜĞÜ", "0 (436) 214 14 49", "Saray Mah. Hürriyet Cad. No:312 P.K:49200 Merkez/MUŞ", "mus@kosgeb.gov.tr", None),
    50: ("Nevşehir", "KOSGEB Nevşehir Müdürlüğü", "0 (384) 228 26 33", "Cevher Dudayev Mahallesi Vatan Caddesi No:42 Kat:3 Merkez/NEVŞEHİR", "nevsehir@kosgeb.gov.tr", None),
    51: ("Niğde", "KOSGEB NİĞDE MÜDÜRLÜĞÜ", "0 (388) 214 14 01", "Niğde Bor Karayolu 7. Km. Niğde Organize Sanayi Bölgesi 8. Cadde No:7/B NİĞDE", None, None),
    52: ("Ordu", "KOSGEB ORDU MÜDÜRLÜĞÜ", "0 (452) 226 10 60", "Karşıyaka Mah. Atatürk Bulv. No:336-C Altınordu/ORDU", "ordu@kosgeb.gov.tr", None),
    53: ("Rize", "KOSGEB Rize Müdürlüğü", "0 (464) 213 53 80", "Rize Ticaret Borsası Binası İslampaşa Mah. Menderes Bulv. No:522 Kat:1 53100 RİZE", "rize@kosgeb.gov.tr", None),
    54: ("Sakarya", "KOSGEB SAKARYA MÜDÜRLÜĞÜ", "0 (264) 289 45 95", "Hanlı Sakarya Mah. Şehit Onbaşı Zekeriya Gözyuman Cad. No:19/1 Hanlı/Arifiye/SAKARYA (SATSO Ek Binası)", "sakarya@kosgeb.gov.tr", None),
    55: ("Samsun", "KOSGEB SAMSUN MÜDÜRLÜĞÜ", "0 (362) 311 07 00", "Organize Sanayi Bölgesi Sosyal Tesis Alanı P.K.29 P.K.:55300 Kutlukent/SAMSUN", "samsun@kosgeb.gov.tr", None),
    56: ("Siirt", "KOSGEB SİİRT MÜDÜRLÜĞÜ", "0 (484) 212 11 50", "Kooperatif Mahallesi Hükümet Bulvarı Kurtalan Yolu Üzeri No:100 Valilik Binası, Merkez/SİİRT", None, None),
    57: ("Sinop", "KOSGEB SİNOP MÜDÜRLÜĞÜ", "0 (368) 265 09 90", "Camikebir Mahallesi Sakarya Caddesi No: 59 K:4 SİNOP", "sinop@kosgeb.gov.tr", None),
    58: ("Sivas", "KOSGEB Sivas Müdürlüğü", "0 (346) 258 57 65", "Mevlana Mah. Bahar Sok. Akasya Sitesi B Blok. No:11/A Merkez/SİVAS", "sivas@kosgeb.gov.tr", None),
    59: ("Tekirdağ", "KOSGEB TEKİRDAĞ MÜDÜRLÜĞÜ", "0 (282) 258 15 30", "Değirmenaltı Mah. Hukukçular Sokak No:20 Merkez/TEKİRDAĞ", None, None),
    60: ("Tokat", "KOSGEB TOKAT MÜDÜRLÜĞÜ", "0 (356) 217 00 10", "Derbent Mahallesi, Osmangazi Caddesi No:45 Merkez/TOKAT", "tokat@kosgeb.gov.tr", None),
    61: ("Trabzon", "KOSGEB TRABZON MÜDÜRLÜĞÜ", "0 (462) 455 51 00", "Sanayi Mah. Yaren Sok. No 4 Kat 4 TRABZON", "trabzon@kosgeb.gov.tr", None),
    62: ("Tunceli", "KOSGEB TUNCELİ MÜDÜRLÜĞÜ", "0 (428) 213 83 15", "Aktuluk Mahallesi, Munzur Üniversitesi Merkez Yerleşkesi, Nadir Toprak Elementleri Uygulama ve Araştırma Merkezi Binası, Kat:2 TUNCELİ", "tunceli@kosgeb.gov.tr", None),
    63: ("Şanlıurfa", "KOSGEB Şanlıurfa Müdürlüğü", "0 (414) 318 49 80", "Organize Sanayi Bölgesi 1.Cad. P.K:63000 ŞANLIURFA", None, None),
    64: ("Uşak", "KOSGEB UŞAK MÜDÜRLÜĞÜ", "0 (276) 221 38 60", "Kemalöz Mah. Atatürk Bulvarı No: 97 UŞAK", "usak@kosgeb.gov.tr", None),
    65: ("Van", "KOSGEB VAN MÜDÜRLÜĞÜ", "0 (432) 486 55 10", "Bahçıvan Mah. Sıhke Cad. 1702 Sk. No:93 Selçuk Ecza Deposu Üstü Kat:4 VAN", None, None),
    66: ("Yozgat", "KOSGEB YOZGAT MÜDÜRLÜĞÜ", "0 (354) 219 00 77", "Karatepe Mah. Hoca Ahmet Yesevi Cad. Yeni Hükümet Konağı Hizmet Binası B Blok Kat:3 Merkez/YOZGAT", "yozgat@kosgeb.gov.tr", None),
    67: ("Zonguldak", "KOSGEB ZONGULDAK MÜDÜRLÜĞÜ", "0 (372) 259 20 90", "Çaydamar Mah. Ahmet Taner Kışlalı Cad. No:7 Merkez/ZONGULDAK", None, None),
    68: ("Aksaray", "KOSGEB AKSARAY MÜDÜRLÜĞÜ", "0 (382) 288 03 00", "Yeni Sanayi, Aksaray Valiliği Ek-3 Hizmet Binası, Sanayi Kavşağı/AKSARAY", "aksaray@kosgeb.gov.tr", None),
    69: ("Bayburt", "KOSGEB BAYBURT MÜDÜRLÜĞÜ", "0 (458) 455 13 01", "Cumhuriyet Cad. Şeyhhayran Mah. Esnaf ve Sanatkarlar Koop. İş Hanı Kat:2 Merkez/BAYBURT", None, None),
    70: ("Karaman", "KOSGEB KARAMAN MÜDÜRLÜĞÜ", "0 (338) 216 39 90", "Karaman Organize Sanayi Bölgesi 1.Cadde No:12", None, None),
    71: ("Kırıkkale", "KOSGEB Kırıkkale Müdürlüğü", "0 (318) 201 19 00", "Ulubatlı Hasan Cad. No:39 Kırıkkale Valiliği A Blok/KIRIKKALE", "kirikkale@kosgeb.gov.tr", None),
    72: ("Batman", "KOSGEB BATMAN MÜDÜRLÜĞÜ", "0 (488) 217 14 10", "Kültür Mahallesi 2608 Sokak No:2 (Kat: 2-3) Batman/Merkez", "batman@kosgeb.gov.tr", None),
    73: ("Şırnak", "KOSGEB ŞIRNAK MÜDÜRLÜĞÜ", "0 (486) 216 92 03", "Vakıfkent Mah. Uludere Caddesi TSO Binası Kat:3 Merkez/ŞIRNAK", "sirnak@kosgeb.gov.tr", None),
    74: ("Bartın", "KOSGEB BARTIN MÜDÜRLÜĞÜ", "0 (378) 221 20 30", "Gecen Mahallesi Aşağıdüz Mevkii Toptancılar Sitesi No: 30 Merkez/BARTIN", "bartin@kosgeb.gov.tr", None),
    75: ("Ardahan", "KOSGEB Ardahan Müdürlüğü", "0 (478) 212 09 99", "Kaptanpaşa Mahallesi Hamam Caddesi İl Özel İdaresi Binası No:1/ARDAHAN", "ardahan@kosgeb.gov.tr", None),
    76: ("Iğdır", "KOSGEB IĞDIR MÜDÜRLÜĞÜ", "0 (476) 223 00 70", "Atatürk Mah. Kanuni Cad. No:8 Merkez/IĞDIR", "igdir@kosgeb.gov.tr", None),
    77: ("Yalova", "KOSGEB YALOVA MÜDÜRLÜĞÜ", "0 (226) 815 11 30", "Laledere Köyü Merkez Mevkii, Mustafa Varank Caddesi No:4/1 Çiftlikköy/YALOVA", "yalova@kosgeb.gov.tr", None),
    78: ("Karabük", "KOSGEB Karabük Müdürlüğü", "0 (370) 419 33 50", "Hürriyet Mah. Zonguldak Cad. Çağrı İş Merkezi A Blok No:34 Kat:3 Merkez/KARABÜK", None, None),
    79: ("Kilis", "KOSGEB KİLİS MÜDÜRLÜĞÜ", "0 (348) 801 16 90", "Mehmet Rıfat Kazancıoğlu Mh. Turgut Keleş Sk. No:2 Merkez/KİLİS", "kilis@kosgeb.gov.tr", None),
    80: ("Osmaniye", "KOSGEB Osmaniye Müdürlüğü", "0 (328) 816 14 10", "Adnan Menderes Mah. 2. K.S.S. KOSGEB Hizmet Binası/OSMANİYE", "osmaniye@kosgeb.gov.tr", None),
    81: ("Düzce", "KOSGEB DÜZCE MÜDÜRLÜĞÜ", "0 (380) 529 15 49", "Camikebir Mah. Mehmet Gösterişli Sk. 13. Cadde No:5/DÜZCE", "duzce@kosgeb.gov.tr", None),
}


def main():
    init_db()
    db = SessionLocal()
    try:
        for il_kodu, (il_adi, mudurluk_adi, telefon, adres, eposta, ek) in VERI.items():
            mevcut = db.query(IlKosgebMudurlugu).filter(IlKosgebMudurlugu.il_kodu == il_kodu).first()
            kayit = dict(
                il_adi=il_adi,
                mudurluk_adi=mudurluk_adi,
                telefon=telefon,
                adres=adres,
                eposta=eposta,
                ek_mudurlukler=ek,
                kaynak_url=_kaynak(il_kodu),
                dogrulama_tarihi=DOGRULAMA_TARIHI,
            )
            if mevcut:
                for alan, deger in kayit.items():
                    setattr(mevcut, alan, deger)
            else:
                db.add(IlKosgebMudurlugu(il_kodu=il_kodu, **kayit))
        db.commit()
        toplam = db.query(IlKosgebMudurlugu).count()
        print(f"{toplam} il KOSGEB müdürlüğü eklendi/güncellendi (81 bekleniyordu).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
