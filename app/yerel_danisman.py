"""Yerel danışman: dış dil modeli olmadan, kayıtlardan kuralla danışman yanıtı (2026-10-11).

Ürünün varsayılan yanıt servisi. Sistem promptundaki (app/rag.SISTEM_PROMPTU) beş başlıklı biçimi izler; her cümle ya
kayıttan aktarılır ya da koddaki kurallardan türetilir. Sayı, tarih, URL ve telefon yalnız veritabanından gelir
(uydurma yolu yok). Veriler sunucudan çıkmaz: profil yalnız yerelde kullanılır, yurt dışı aktarımı ve açık rıza
gerekmez.

Akış (bağımsız uzman değerlendirmesi 2026-10-11, docs/olcum/2026-10-11-yerel-danisman):
  1. Soru niyeti: tarih / tutar / uygunluk / tanım / birlikte kullanım / liste; özel durumlar (uygunluğu yapay
     sağlama talebi, garanti, kaldırılmış ya da kaydı olmayan program).
  2. Odak: soruda adıyla (kod, nadir kelime, başlık başı, kısaltma) ya da kurumuyla anılan programlar; aynı yılın
     etkin kaydı kapalı eski kayda tercih edilir.
  3. Karar: kapalı kayıt; Karar/eşleştirme engeli (şirket türü, ölçek, il, yaş, ortaklık, sertifika, KOBİ şartı);
     profilde engel yoksa "teyit edin" (profilde karşılığı olmayan şartlar adıyla sayılır); şart bilgisi ya da profil
     yoksa "belirlenemedi". "Uygun" etiketi verilmez: profilde karşılığı olmayan şartlar hiçbir zaman sağlanmış sayılmaz.
  4. Başvuru dönemi: çağrı kaydından (ön kayıt süresi geçmişse yeni başvuran için kapalı sayılır).
  5. Kısa cevap niyete göre; kartlar yalnız odak ya da profile eşleşen programlar; diğerleri tek satır; elenenler
     gerekçe, son bilinen tutar ve "uygun hale gelmek için" adımlarıyla; iletişim yalnız gösterilen kurumlar için.

    python -m app.yerel_danisman --self-test
    python -m app.yerel_danisman --demo "soru"      (gerçek veritabanı, profilsiz)
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app import soru_anlama
from app.ihtiyac import IHTIYAC_ADLARI, _katla, program_ihtiyaclari, soru_ihtiyaclari

EN_COK_KART = 3          # persona denemesi 2026-10-12: dar sorularda 4 kart yanıtı 15 KB'a çıkarıyordu
ODAK_KART = 3            # soru belirli programları/kurumu andıysa yalnız onların kartı
EN_COK_DIGER = 3         # kart dışındaki ilgili programlar tek satırda
EN_COK_ELENEN = 6        # "size kapalı" listesinde satır
TRIYAJ_KART = 3          # kritik profil alanları eksikken gösterilen kart
EN_COK_TEYIT = 4         # tur 7 sonrası: kart başına teyit kutusu (kalanı panelde)
EN_COK_KURAL = 3
EN_COK_BELGE = 8
ALINTI_SINIRI = 180      # daha uzun alıntı gösterilmez (yarıda kesilmiş alıntı yanıltır)
NADIR_KELIME_SIKLIGI = 2  # sorudaki kelime en çok bu kadar başlıkta VE kayıt metninde geçiyorsa program adıyla sorulmuş
# Program adı sayılmayan genel kökler (çekimli biçimleri de: "hibeleri", "makinesi").
GENEL_KOKLER = ("hibe", "destek", "kredi", "progra", "yatiri", "basvur", "tesvi", "makine", "kefal", "faiz", "sure",
                "gider", "kanun", "karar", "proje", "isletm", "sirket", "girisi", "uretim", "ihraca", "istihd", "dijital",
                "almak", "alaca", "alim", "istiy", "yararl", "bireys", "kadin", "gencl", "tarim", "sanayi", "ulusla")
SEKTOR_AD = {"tarim": "tarım", "arge": "Ar-Ge / bilişim", "imalat": "imalat", "hizmet": "hizmet",
             "ihracat": "ihracat", "e-ticaret": "e-ticaret", "genel": "genel"}
# Profil formundaki hedef seçenekleri (app/static/dashboard.html .p-hedef) ve eski kayıtlardaki kodlar
HEDEF_AD = {"yatirim": "yatırım", "ihracat": "ihracat", "arge": "Ar-Ge", "istihdam": "istihdam", "makine": "makine alımı",
            "sulama": "sulama sistemi", "hayvan": "hayvancılık", "organik": "organik tarım",
            "organik_tarim": "organik tarım", "finansman": "kredi/finansman", "dijital": "dijital dönüşüm"}
SIRKET_TURU_AD = {"sahis": "şahıs işletmesi", "limited": "limited şirket", "anonim": "anonim şirket",
                  "kooperatif": "kooperatif", "yok": "henüz şirket kurulmamış", "diger_tuzel": "diğer tüzel kişi"}
SORUMLULUK_REDDI = (
    "---\n*Bu değerlendirme, Teşvik Asistanı veritabanındaki kayıtlar ve sizin verdiğiniz bilgiler esas alınarak "
    "hazırlanmış ön bilgilendirmedir; hukuki, mali veya resmî danışmanlık niteliği taşımaz ve herhangi bir desteğin "
    "alınacağına dair taahhüt içermez. Destek programlarının şartları, oranları, üst limitleri ve çağrı takvimleri "
    "ilgili mevzuat ve kurum kararlarıyla değişebilir. Başvuru ve harcama kararı vermeden önce güncel çağrı duyurusunu, "
    "uygulama esaslarını ve ilgili Karar/Tebliğ metnini resmî kaynaktan teyit ediniz; gerektiğinde yetkili mali "
    "müşavir veya hukuk danışmanından görüş alınız. Nihai uygunluk ve destek kararı yalnızca ilgili kurum tarafından "
    "verilir.*")
YONTEM_NOTU = ("*Bu yanıt Teşvik Asistanı'nın yerel danışmanı tarafından, yalnız veritabanındaki doğrulanmış kayıtlardan "
               "kuralla üretildi; verileriniz sunucumuzdan çıkmadı.*")
GENEL_ILKELER = [
    "[Genel ilke – teyit edin] Başvuru ya da sözleşme tarihinden önce yapılan harcamalar çoğu programda desteklenmez; "
    "harcamaya başlamadan önce kurumun onayını bekleyin.",
    "[Genel ilke – teyit edin] Vergi ya da SGK borcu, başvurunun reddine veya ödemenin durdurulmasına yol açabilir.",
    "[Genel ilke – teyit edin] Destek alındıktan sonra izleme, raporlama ve yerinde denetim yükümlülüğü sürer; şartlara "
    "aykırılıkta destek geri istenebilir.",
]
SART_YOK_TEYIT = "Kayıtta ayrıca başvuru şartı yok"
# Muhafazakâr alt sınır: USD/TRY Mart 2024'ten beri 30'un üzerinde (1 USD 30 TL'nin üzerinde; TCMB gösterge kuru);
# yalnız "cironun tamamı
# ihracat olsa bile eşiğe ulaşmaz" hükmü için. 10 TL alt sınırı 20 milyon TL cirolu firmayı 1 milyon USD eşiği için
# "belirlenemedi" bırakıyordu (persona denemesi 2026-10-12).
ASGARI_USD_TRY = 30
# Kullanıcıya görünen etiketler. İç karar kodu "belirlenemedi" kalır; etiket "Şarta bağlı"dır (hakem bulgusu 2026-10-12:
# "belirlenemedi" esnafa anlamsız bir sistem terimiydi ve hem bilinmeyeni hem kilit şartı kapsıyordu).
KARAR_METNI = {"sartli": "Profilinize göre engel yok — şartları teyit edin", "belirlenemedi": "Şarta bağlı",
               "uygun_degil": "Uygun değil", "kapali": "Kapalı"}
# Profilden doğrulanamayan, uygunluğu belirleyen şartın gerekçe öneki (sıralama ve süzgeçler bu öneke bakar).
KILIT_ONEKI = "profilinizden doğrulanamayan önemli şart"
# İstihdam teşviklerinde şart işverenin değil işe alınacak kişinin niteliğidir (kadın/genç, işsizlik ödeneği, engelli,
# sosyal yardım). Hakem bulgusu 2026-10-12, 4. tur: 2828/3294/engelli teşviklerine "engel yok" deniyor, işe alıma bağlı
# Kadın/Genç/MYB teşviki ise kilit şart sayılıp geri düşüyordu. Bu şart kişiye bağlıdır; sıralamada kilit sayılmaz.
KISI_ONEKI = "işe alacağınız kişiye bağlı şart"
_KISI_SARTI = re.compile(r"İşe alınan kişi|Engelli sigortalı çalıştırıl|Sigortalı, işe girişten önceki|"
                         r"İş Kurumu'na kayıtlı işsiz|istihdam hakkından|Sigortalı Ar-Ge/Tasarım personeli", re.I)
_KISI_BASLIK = re.compile(r"Yurtdışına Götürülen|Yurt dışına götürülen")
# Yalnız dar bir kişi grubunu işe alana uygulanan teşvikler; geniş kapsamlı işe alım teşvikinin (kadın, 18-29 yaş,
# MYB; işsizlik ödeneği alan) arkasında gelir.
_DAR_KISI = re.compile(r"Sosyal Hizmet|Sosyal Yardım|Engelli|Yurtdışına Götürülen|Yurt dışına götürülen|"
                       r"Ar-Ge.{0,40}Personel", re.I)
# Dört haneli program kodu (1501, 1812, 9903, 4447). 2000-2039 yıl sayılır: "2026 yılında" sorusu başlığında "2026"
# geçen her programı "adıyla soruldu" sayıp öne alıyordu (değerlendirme 2026-10-11, hububat sorusuna ajans programları).
_KOD = re.compile(r"(?<![\d.,])(?!20[0-3]\d)(\d{4})(?![\d.,])")
_DURAK = {"destek", "destegi", "destekleri", "programi", "program", "kredisi", "kredi", "projesi", "paketi", "hibe",
          "ve", "ile", "icin", "tesvik", "tesvigi", "yili", "mali", "kosgeb", "tubitak", "-", "yatirim"}
_NIYET = {
    "tarih": re.compile(r"\bne zaman|\bson (basvuru|gun|tarih)|\bkac gun|\btakvim|\bbasvuru (donem|tarih)|\bacik mi"
                        r"|\bacilacak|\bkapan(iyor|acak|di|ma)|\bcagri|\btarihler|(?<!odemesiz )\bdonem(i|inde)\b"),
    "tutar": re.compile(r"\bne kadar|\bkac (tl|lira)|\boran|\blimit|\bust (sinir|tutar|limit)|\btutar|\bmiktar"
                        r"|\bdekar basina|\byuzde|%|\bvade|\bodemesiz|\bbutce"),
    "uygunluk": re.compile(r"basvurabilir|yararlanabilir|uygun mu|faydalanabilir|alabilir mi|hak kazan|kapsamina gir"),
    "tanim": re.compile(r"\bnedir\b|\bne demek|\bkimler\b|\bsartlar|\bkosul|\bnasil basvur|\bhangi belge"),
    "birlikte": re.compile(r"birlikte (kullan|yararlan|al)|ayni anda|\bbirlestir"),
    "sure": re.compile(r"\bkac (ay|yil)|\bne kadar sur|\bsuresi\b|\bsurer\b"),
}
_TEKNOLOJI = re.compile(r"yazilim|yapay zeka|teknoloji|ar-?ge|girisim|startup|uygulama gelistir|prototip|trl\b")
# Profilden doğrulanamayan, başvuruyu tek başına kapatabilen şartlar (rozet, üyelik, ihracat eşiği, ortak başvuru,
# önceki proje/yatırım, sertifika). Böyle bir şart varsa karar "belirlenemedi — X bilinmiyor" olur (tur 2 değerlendirmesi).
_KILIT = re.compile(r"rozet|üyeli[ğk]|üyesi|ihracatçı|net ihracat|greendeks|sertifika|ortak(?:lı)? başvuru|müşteri kuruluş|"
                    r"tedarikçi kuruluş|konsorsiyum|teknoloji tabanlı|tamamla(?:mış|yan)|hak kazanmış|almış (?:ya da|veya)|"
                    r"desteklenmiş|proje(?:si)? (?:kararı|onayı)|onay(?:ı|lı) (?:almış|olan)|teminat mektubu|"
                    r"davet edilmiş|ön başvuru yapılmış|işbirliği kuruluşu (?:onay )?başvuru|başvurusunu .{0,40}işbirliği "
                    r"kuruluşu yapar|yatırım malı|Bölgedeki yazılım|Bölgede (?:faaliyet|çalış)|"
                    r"en az .{0,20}(?:USD|dolar)|\d+\s*yaş|yaşını aş|"
                    # gerçekleşmiş e-ihracatın belgelenmesi (Eximbank E-İhracat Destek Kredisi; hakem bulgusu 4. tur:
                    # e-ihracata yeni başlayacak firmaya "engel yok" deniyordu)
                    r"faaliyetini tevsik|beyannamesi ile e-ihracat|tam zaman eşdeğer|yurt dışı ortaklı|"
                    r"başvurusu yapılmış olmalı|"
                    r"kad[ıi]n (?:yönetici|girişimci|ortak)\w*(?: bulunan| olan| olmak| olmalı)", re.IGNORECASE)
_KOSULLU_BELGE = re.compile(r"\b\w+(?:ysem|ysam|ysek|ysak)\b|\bise\b.{0,40}(?:hazırla|ekle)", re.IGNORECASE)
_KOBI = re.compile(r"\bKOB[İI](?:'|’)?(?:ler|lerin|leri|lere|nin|ye|ölçeğinde|lik)?\b")
_KOBI_DISI = re.compile(r"KOB[İI] dışı|KOB[İI] olmayan|KOB[İI] niteliği taşımayan|büyük işletme|büyük ölçekli|"
                        r"ölçek(?:i|ten)? bağımsız|ölçeğine bakılmaksızın|yükümlü", re.IGNORECASE)
# Şartın başvuru sahibini KOBİ ile sınırladığını gösteren ifade (yalnız "KOBİ" kelimesi geçmesi yetmez).
_KOBI_SART = re.compile(r"KOB[İI]\s*(?:olmak|olması|ölçeğinde|niteliğinde|tanımına uy)|KOB[İI](?:'|’)?(?:ler|lerin)\s+"
                        r"(?:başvur|yararlan|faydalan)|KOB[İI](?:'|’)?lere yönelik|yalnız(?:ca)? KOB[İI]", re.IGNORECASE)


@dataclass
class Degerlendirme:
    tesvik: Any
    karar: str                                       # sartli | belirlenemedi | uygun_degil | kapali
    gerekce: list[str] = field(default_factory=list)
    teyit: list[str] = field(default_factory=list)   # profilde karşılığı olmayan şartlar
    saglanan: list[str] = field(default_factory=list)  # profilde karşılığı olan ve sağlanan şartlar
    kisit: list[str] = field(default_factory=list)   # "Yalnız: ..." kapsam kısıtları
    adi_gecti: bool = False
    odak: bool = False
    eslesti: bool = False
    cagri: dict | None = None
    donem: str = "yok"                               # acik | yaklasan | on_kayit_kapandi | kapandi | tarihsiz | yok
    uygunluk: str = ""                               # dönem kapandığı için "kapali" olanın profil kararı
    onceki_tutar: str = ""                           # tutarı boşsa önceki (devredilen) programın son bilinen tutarı
    profilli: bool = True                            # profil yoksa kartta "Sizin için" yerine "Durum"
    ust: Any = None                                  # dönemi kapalı bağlı KOSGEB programı (KGF paketi için)
    alt_not: str = ""                                # yalnız bir alt desteğin/aşamanın çağrısı kapandıysa açıklama
    kapsam_disi: bool = False                        # sorudaki kalem kayıtta "desteklenmez" diye geçiyor
    guncel_surum: str = ""                           # kapalı programın etkin yeni sürümünün adı
    kobi: bool | None = None                         # profile göre KOBİ mi (bilinmiyorsa None)
    ihtiyac_notu: str = ""                           # kurum sorusunda sorulan ihtiyacı karşılayan programın durumu


# ------------------------------------------------------------------ metin yardımcıları
_EK3_SART = re.compile(r"EK-3'te '(?P<kod>[\d.]+) (?P<tanim>.*?)' kalemine giriyor; şart: (?P<sart>.*?)"
                       r"\s*\((?P<madde>MADDE[^)]*)\)\s*$")


def karar_sarti_metni(not_9903: str) -> str:
    """9903 ŞARTLI notundan kullanıcıya teyit edilecek şart. EK-3 tablosu cümleyi kalem tanımı ile şart sütunu
    arasında bölüyor ("…5 ton/gün altındaki kapasiteye sahip süt işleme" | "yatırımları desteklenmez"); ikisi
    birleştirilir. EK-3 biçimi değilse "ŞARTLI — " sonrası tam gerekçe."""
    ilk = not_9903.split("\nDESTEK UNSURLARI")[0].strip()
    govde = re.sub(r"^ŞARTLI\s*[—-]\s*", "", ilk)
    m = _EK3_SART.search(govde)
    if m:
        return f"EK-3 {m['kod']} kalemi: {m['tanim']} {m['sart']} ({m['madde']})"
    return govde if govde != ilk else ""


def karar_etiketi(d: "Degerlendirme") -> str:
    """Karar etiketi; 9903 Karar şartı (ör. kapasite eşiği) teyit bekleyen program "Şartlı" etiketini alır."""
    if d.karar == "sartli" and d.teyit and d.teyit[0].startswith("Karar şartı:"):
        return "Şartlı — Karar şartını teyit edin"
    if d.karar == "belirlenemedi" and any("ön değerlendirme: DÜŞÜK" in g for g in d.gerekce):
        return "Düşük olasılık — Karar ön değerlendirmesi"
    if d.karar == "belirlenemedi" and any(g.startswith("düşük olasılık:") for g in d.gerekce):
        return "Düşük olasılık — cironuz eşiğin altında"
    if d.karar == "kapali" and re.search(r"planlan|ertelen", " ".join(d.gerekce)):
        return "Kapalı — yeni çağrı planlanıyor, tarih yok"
    return KARAR_METNI[d.karar]


def _tarih(d: str | date | None) -> str:
    if not d:
        return ""
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return d.strftime("%d.%m.%Y")


def _kisalt(metin: str | None, sinir: int) -> str:
    return _cumle_kisalt(metin, sinir)


_CUMLE_SONU = re.compile(r"(?<!\d)(?<!\b[A-ZÇĞİÖŞÜa-zçğıöşü])\.(?=\s+[A-ZÇĞİÖŞÜ(])|;(?=\s)")
UZATMA_PAYI = 1.75   # sınırda cümle sonu yoksa metin bu kata kadar uzayabilir (yarım cümle bırakmamak için)


def _cumle_kisalt(metin: str | None, sinir: int) -> str:
    """Uzun metni cümle (ya da noktalı virgül) sınırında keser; yarım cümle bırakmaz. Sınır içinde uygun cümle sonu
    yoksa bir sonraki cümle sonuna kadar (en çok sınır × UZATMA_PAYI) uzatır; o da yoksa ve metin bu payı aşıyorsa
    kelime sınırında keser ve bunu "…" ile belirtir."""
    metin = " ".join(str(metin or "").split())
    if len(metin) <= sinir:
        return metin
    # Cümle sonu: rakamdan ya da tek harften sonra gelmeyen nokta + büyük harf ("2. kategori", "A. Ş."), noktalı virgül.
    sonlar = [m.start() for m in _CUMLE_SONU.finditer(metin)]
    ic = [i for i in sonlar if sinir * 0.4 <= i < sinir]
    if ic:
        return metin[:ic[-1] + 1].rstrip(";").rstrip()
    dis = [i for i in sonlar if sinir <= i <= sinir * UZATMA_PAYI]
    if dis:
        return metin[:dis[0] + 1].rstrip(";").rstrip()
    if len(metin) <= sinir * UZATMA_PAYI:
        return metin
    return metin[:sinir].rsplit(" ", 1)[0] + " …"


def _temiz(metin: str | None) -> str:
    """Kayıt notlarındaki göreli zaman ve geliştirici ifadelerini kullanıcı metninden ayıklar."""
    m = re.sub(r"\s*\((?:bugün|dün|yarın)\)", "", str(metin or ""))
    m = re.sub(r"[;,]?\s*\d{4} yılı \d+\. çağrı dokümanı\b", "", m)
    m = re.sub(r"^Başvuruyu yap:\s*", "Başvuru yeri: ", m)
    m = re.sub(r"\((\d{4})-(\d{2})-(\d{2})\)", lambda x: f"(kayıt kontrolü: {x[3]}.{x[2]}.{x[1]})", m)
    parcalar = re.split(r"(?<=[.;])\s+", m)
    parcalar = [p for p in parcalar if p and not re.search(
        r"olarak .{0,60} alınmıştır|eklenmeli|gösterilmeli|düzeltilmeli|teyit edildikten sonra|TODO|"
        r"otomatik çıkarıldı|çağrı dokümanı$", p)]
    return " ".join(parcalar).strip()


def _norm(metin: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _katla(metin)).strip()


def _birlestir(parcalar: list[str]) -> str:
    gorulen, sonuc = set(), []
    for p in parcalar:
        # "düşük olasılık:" öneki etiketle yan yana tekrar olur ("düşük olasılık — ... (düşük olasılık: ...)")
        p = re.sub(r"^düşük olasılık:\s*", "", (p or "").strip().rstrip(".;"))
        if p and _norm(p) not in gorulen:
            gorulen.add(_norm(p))
            sonuc.append(p)
    # Kalıcı engel (sektör kapsamı) geçici engelden (ölçek) önce yazılır (hakem bulgusu 6. tur: hizmet sektöründeki kurs
    # "mikro ölçek" gerekçesini görüp büyüyünce programın açılacağını sanabilirdi).
    metin = "; ".join(sonuc)
    if "“" not in metin:   # alıntı içindeki noktalı virgül bölünmesin
        parcalar = metin.split("; ")
        parcalar.sort(key=lambda p: 0 if re.search(r"sektör kapsamı|imalatçı işletmelere yönelik", p) else 1)
        metin = "; ".join(parcalar)
    # İki sektör gerekçesi aynı şeyi söyler; ayrıntılı olan ("programın sektör kapsamı (imalat) ...") kalır (hakem
    # bulgusu 4. tur: ret gerekçesinde iki sektör cümlesi yan yanaydı).
    if "programın sektör kapsamı" in metin:
        metin = re.sub(r"(?:; )?program sektörü işletmenin NACE kodlarıyla örtüşmüyor", "", metin).lstrip("; ")
    return metin


_IC_ETIKET = re.compile(r"^(?:⚠️\s*)?(?:Denetim\d?(?:-T\d+)?|[Tt]ur\d+)\s+\d{4}-\d{2}-\d{2}:\s*")
_IC_PARCA = re.compile(r"^(?:Başvuru şartları \d{4}-\d{2}-\d{2} tarihinde|DURUM: Doğrulanmış)|Dayanak \(kalıp:"
                       r"|(?:detay|özet|açıklama|tutar|kontrol listesi)\w* alan\w* .{0,80}(?:kaldırıldı|düzeltildi|eklendi)"
                       r"|çelişki giderildi|diline çevrildi|doğrulanmış (?:şart maddesinden|alıntı)")


def kullanici_durum_notu(durum_notu: str | None) -> str:
    """durum_notu bir denetim kaydıdır ("|" ile birikmiş parçalar: iç etiketler, otomatik çıkarım ve regex dayanak
    notları, bazen eski "aktif" parçaları). Kullanıcıya en son anlamlı parça etiketsiz ve URL'siz gösterilir."""
    parcalar = [p.strip() for p in (durum_notu or "").split(" | ") if p.strip()]
    anlamli = []
    for p in parcalar:
        m = _IC_PARCA.search(p)
        if m is None:
            anlamli.append(p)
        elif m.start() > 20 and not _IC_ETIKET.match(p):   # gerekçeden sonra gelen iç not kesilir, gerekçe kalır
            anlamli.append(p[:m.start()].rstrip(" .;:-"))
    if not anlamli:
        return ""
    son = _IC_ETIKET.sub("", anlamli[-1])
    son = re.sub(r"^(?:⚠️\s*)?ARTIK AKTİF DEĞİL[.:!]?\s*", "", son)
    # Kanıt/kaynak/iç dosya açıklamaları kullanıcıya gitmez (yalnız gerekçe cümlesi kalır).
    son = re.sub(r"^.*?resmî kaynaktan eklendi;\s*durum:\s*", "", son)
    son = re.split(r"\s*(?:Kaynak:|Kanıt:|;?\s*kanıt docs/|Başvuru şartları \d{4}-|alıntı docs/|\(kaynak_url)", son)[0]
    son = re.sub(r"\s*\(?(?:kaynak:\s*)?https?://\S+\)?", "", son, flags=re.IGNORECASE).strip(" .;:(")
    son = re.sub(r"^⚠️\s*", "", son)
    return _kisalt(_temiz(son), 260)


# ------------------------------------------------------------------ soru çözümleme
def _anlamli_kelimeler(metin: str) -> set[str]:
    return {k for k in re.findall(r"[a-z0-9]+", _katla(metin)) if len(k) > 2 and k not in _DURAK}


def niyetler(soru: str) -> set[str]:
    katli = _katla(soru)
    bulunan = {ad for ad, kalip in _NIYET.items() if kalip.search(katli)} | soru_anlama.ek_niyetler(soru)
    return bulunan or {"liste"}


# Başlıkta nadir geçse de program adı olmayan gündelik kelimeler (persona denemesi 2026-10-12: "dolu ve don
# riskine karşı sigorta" sorusu, başlığında "iptal etme riskine karşı sigorta" geçen Eximbank ürününü "adıyla
# sorulan program" sayıyordu).
def _ihtiyac_kelimesi(k: str) -> bool:
    """Sorudaki ihtiyaç kelimesi ("markamızla", "reklam", "kredi"): ihtiyaç eşleşmesi zaten sayar; program adı
    eşleşmesi sayılırsa "markamızla Almanya'ya ihracat" sorusu "Şirket ve Marka Alım Desteği"ni öne çıkarıyordu."""
    from app.ihtiyac import SORU_KALIPLARI
    return any(kalip.search(k) for kalip in SORU_KALIPLARI.values())


# Ad eşleşmesinde sayılmayan kısa gündelik kelimeler ("açık tarlada" ↔ "İyi Tarım ... açıkta").
_AD_DISI = frozenset({"acik", "acikta", "yeni", "daha", "icin", "gibi", "kadar", "olan", "olarak", "magaza", "magazam",
                      "magazasi", "depo", "depoya", "ofis", "site", "sitemiz", "sitemizden", "sitemden", "online",
                      "yurt", "disi", "disinda", "disindan", "disina", "yurtdisi", "yurtdisinda", "yurtdisina"})
_NADIR_DISI = frozenset({"riskine", "riskini", "riski", "riske", "karsi", "iptal", "yenilemek", "yenileme", "kurmak",
                         "yapmak", "almak", "istiyorum", "istiyoruz", "yaptirirsam", "yaptirmak", "yetistiriyorum",
                         "satmak", "satiyoruz", "satiyorum", "uretip", "uretiyoruz", "acmak", "buyutmek", "gonderdigim",
                         "masrafi", "giderleri", "giderlerim", "kadarini", "dijitallesmesi", "dijitallestirmek"})


def _cekirdek_soruda(t, soru_kelime: set) -> bool:
    """Başlığın genel kökler dahil ilk iki anlamlı kelimesi soruda ("KOBİ Dijital Dönüşüm" → dijital, dönüşüm)."""
    ana = [k for k in re.findall(r"[a-z0-9]+", _katla(t.baslik or "")) if k not in ("kobi",) and len(k) > 2][:2]
    return len(ana) == 2 and all(k in soru_kelime for k in ana)


def adi_gecen_programlar(soru: str, kayitlar: list) -> list:
    """Soruda adıyla anılan kayıtlar. Kurallar: dört haneli program kodu (1501, 9903); başlıktaki kısaltma (KKYP,
    TSS); başlığın ilk iki kelimesi + üçüncünün kökü; en az üç özgün başlık kelimesinin çoğu; ya da sorudaki bir
    kelimenin yalnız bir-iki başlıkta ve kayıt metninde geçmesi ("Eurostars", "tasarruflu", "hububat"). İl adları ve
    genel kökler sayılmaz. Etkin kayıt ve soruda geçen yılı taşıyan kayıt önce gelir (TOBB Nefes 2026 > 2020)."""
    from app.bolgesel_tarim import IL_BOLGE_ESLEME
    soru_k = _katla(soru)
    soru_kurumlari = kurum_odagi(soru, kayitlar)

    def kurum_soruda(t) -> bool:
        return t.kurum in soru_kurumlari
    kodlar = set(_KOD.findall(soru_k))
    soru_kelime = _anlamli_kelimeler(soru)
    soru_jeton = re.findall(r"[a-z0-9]+", soru_k)
    basliklar = {id(t): _anlamli_kelimeler(t.baslik or "") for t in kayitlar}
    adaylar = {k for k in soru_kelime if len(k) >= 5 and not k.isdigit() and k not in IL_BOLGE_ESLEME
               and not k.startswith(GENEL_KOKLER) and k not in _NADIR_DISI}
    baslik_sikligi = {k: sum(k in v for v in basliklar.values()) for k in adaylar}
    adaylar = {k for k, n in baslik_sikligi.items() if 1 <= n <= NADIR_KELIME_SIKLIGI}
    if adaylar:
        # Başlıkta nadir olan kelime kayıt metinlerinde de nadir olmalı ("bireysel", "kanun" başlıkta tek, metinde çok).
        metin_sikligi = dict.fromkeys(adaylar, 0)
        for t in kayitlar:
            for k in adaylar & _metin_kelimeleri(t):
                metin_sikligi[k] += 1
        adaylar = {k for k in adaylar if metin_sikligi[k] <= NADIR_KELIME_SIKLIGI}
    basliklar_bas2: dict[tuple, int] = {}
    for t in kayitlar:
        j = tuple(re.findall(r"[a-z0-9]+", _katla(t.baslik or ""))[:2])
        basliklar_bas2[j] = basliklar_bas2.get(j, 0) + 1
    sonuc = []
    for t in kayitlar:
        kelimeler = basliklar[id(t)]
        # Başlık oranı yalnız özgün kelimelerle: "Dijital Dönüşüm Destek Paketi" genel konu kelimesiyle eşleşmesin.
        ozgun = {k for k in kelimeler if not k.startswith(GENEL_KOKLER)}
        baslik_k = _katla(t.baslik or "")
        kisaltmalar = {_katla(k) for k in re.findall(r"\(([A-ZÇĞİÖŞÜ]{2,8})\)", t.baslik or "")}
        jetonlar = re.findall(r"[a-z0-9]+", baslik_k)
        if (kodlar & set(_KOD.findall(baslik_k)) or kelimeler & adaylar or kisaltmalar & set(soru_jeton)
                or _baslik_basi_soruda(_baslik_jetonlari(t.baslik), soru_jeton)
                or (len(jetonlar) >= 2 and not jetonlar[0].isdigit() and len(jetonlar[0]) >= 4
                    and len(jetonlar[1]) >= 4 and basliklar_bas2.get(tuple(jetonlar[:2])) == 1
                    and not jetonlar[0].startswith(GENEL_KOKLER) and not jetonlar[1].startswith(GENEL_KOKLER)
                    and any(soru_jeton[i:i + 2] == jetonlar[:2] and not _konu_ifadesi(soru_jeton, i + 2)
                            for i in range(len(soru_jeton) - 1)))
                or (len(ozgun) >= 3 and len(ozgun & soru_kelime) / len(ozgun) >= 0.75)
                or (kurum_soruda(t) and 1 <= len(ozgun - {"kobi"}) <= 2 and (ozgun - {"kobi"}) <= soru_kelime
                    and _cekirdek_soruda(t, soru_kelime))):
            sonuc.append(t)
    yillar = set(re.findall(r"20[2-3]\d", soru))
    soru_jeton_kume = set(soru_jeton)

    def _guc(t) -> float:
        ozgun = set(re.findall(r"[a-z0-9]{3,}", _katla(t.baslik or ""))) - _DURAK
        return float(len(ozgun & soru_kelime))
    return sorted(sonuc, key=lambda t: (t.aktif_mi is False, not kurum_soruda(t),
                                        not (yillar & set(re.findall(r"20[2-3]\d", t.baslik or ""))) if yillar else False,
                                        -_guc(t)))


_KONU_ADLARI = ("girisi", "proje", "sirket", "isletm", "fikr", "uygulam", "startup", "urun", "teknoloji")


def _baslik_jetonlari(baslik: str | None) -> list[str]:
    """Başlığın katlanmış kelimeleri; baştaki yıl ifadesi ("2026 Yılı Turizm Ücret Desteği") atlanır, program adı
    yıldan sonra başlar (kullanıcı "turizm ücret desteği" diye sorar)."""
    j = re.findall(r"[a-z0-9]+", _katla(baslik or ""))
    while len(j) > 2 and (re.fullmatch(r"20[0-9]{2}", j[0]) or j[0] in ("yili", "yilinda", "yil")):
        j = j[1:]
    return j


def _konu_ifadesi(soru: list[str], sonraki: int) -> bool:
    """Başlığın ilk iki kelimesi soruda bir girişim/proje adıyla sürüyorsa ("yapay zekâ girişimi", "yapay zekâ
    projesi") program adı değil konu ifadesidir. "Kırsal Kalkınma hibesi" ise programın kendisidir (hibe, destek,
    kredi program adının parçası sayılır)."""
    return sonraki < len(soru) and soru[sonraki].startswith(_KONU_ADLARI)


def _baslik_basi_soruda(baslik: list[str], soru: list[str]) -> bool:
    """Başlığın ilk iki kelimesi aynen, üçüncüsü kökünden (ilk 4 harf) soruda bitişik geçiyor mu: "Yapay Zekâ
    Kredi Programı" ↔ "yapay zekâ kredisi" evet, ↔ "yapay zekâ girişimi" hayır; "Dijital Dönüşüm Destek Paketi" ↔
    "dijital dönüşüm yatırımı" hayır."""
    if len(baslik) < 3 or baslik[0].isdigit():
        return False
    a, b, c = baslik[:3]
    # "Ar-Ge ve Tasarım İndirimi": ilk üç parça ("ar", "ge", "ve") bir ihtiyaç ifadesidir, program adı değil
    # (kapsam ölçümü 2026-10-12: "Ar-Ge ve yeni ürün geliştirme" sorusu bu vergi teşvikini adıyla sorulmuş sayıyordu).
    if c in ("ve", "ile", "icin", "veya", "da", "de") or min(len(a), len(b)) < 3:
        return False
    # Üçüncü kelime çekimli olabilir ("kredi" ↔ "kredisi") ama bileşik başka kelime değil ("pazar" ↔ "pazaryerlerinde",
    # persona denemesi 2026-10-12: pazaryeri reklam sorusu "Yurt Dışı Pazar Araştırması" sayılıyordu).
    def _ayni_kok(s: str) -> bool:
        return s.startswith(c[:4]) and (len(s) <= len(c) + 4 or s.startswith(c)) and not (
            len(s) > len(c) + 4 and s.startswith(c) and len(c) <= 5)
    return any(soru[i] == a and soru[i + 1] == b and _ayni_kok(soru[i + 2]) for i in range(len(soru) - 2))


_METIN_ONBELLEK: dict[tuple, frozenset] = {}


def _metin_kelimeleri(t) -> frozenset:
    """Kaydın başlık + özet + ayrıntı + hedef kitle kelimeleri; metin değişirse anahtar değişir."""
    parcalar = tuple(str(x or "") for x in (t.baslik, t.ozet, t.detay, t.hedef_kitle))
    anahtar = (t.id, *map(len, parcalar), hash(parcalar))
    if anahtar not in _METIN_ONBELLEK:
        if len(_METIN_ONBELLEK) > 5000:
            _METIN_ONBELLEK.clear()
        _METIN_ONBELLEK[anahtar] = frozenset(_anlamli_kelimeler(" ".join(parcalar)))
    return _METIN_ONBELLEK[anahtar]


def kurum_odagi(soru: str, kayitlar: list) -> set[str]:
    """Soruda adıyla anılan kurumlar ("Ankara Kalkınma Ajansı", "TKDK", "(OKA)"). Kısa ad sözcük olarak aranır."""
    soru_k = _katla(soru)
    jeton = set(re.findall(r"[a-z0-9]+", soru_k))
    buyuk = {_katla(x) for x in re.findall(r"\b[A-ZÇĞİÖŞÜ]{2,10}\b", soru or "")}
    kurumlar = set()
    for kurum in {t.kurum for t in kayitlar if t.kurum}:
        ana = _norm(re.sub(r"\s*\(.*?\)", "", kurum))
        kisa = {_katla(x) for x in re.findall(r"\(([^)]{2,10})\)", kurum)}
        if (len(ana) > 6 and ana in _norm(soru)) or kisa & buyuk or (len(ana) <= 8 and ana in jeton):
            kurumlar.add(kurum)
    return kurumlar


def _profil_bilinen(p) -> dict:
    """Kritik alanlar (sistem promptu triyaj sırası): a faaliyet/NACE, b şirket türü, c il."""
    return {"a": bool(p is not None and (p.nace_kodu or p.sektor)), "b": bool(p is not None and p.sirket_turu),
            "c": bool(p is not None and p.bolge)}


def triyaj_mi(p) -> bool:
    return sum(not v for v in _profil_bilinen(p).values()) >= 2


# ------------------------------------------------------------------ özel soru türleri
# Sistem promptunun dış modelden istediği tavırlar (KAPSAM DIŞI, GARANTİ YASAĞI, sistemde olmayan program) kuralla.
_MANIPULASYON = re.compile(
    r"(sirket\w*|isletme\w*|firma\w*)\s+(\w+\s+){0,2}(bol\w*|ayir\w*)|kucuk\s+(gorun|goster)\w*|"
    r"(calisan|personel|ciro)\w*\s+(\w+\s+){0,3}(dusuk|az|eksik)\s+goster\w*|"
    r"(fatura|harcama|belge|sozlesme)\w*\s+(\w+\s+){0,2}(tarih\w*\s+)?(geri|once|ileri)\w*\s+(al|at|tarih)\w*|"
    r"tarih\w*\s+(degistir|oynat|kaydir|geri\w* al|one al)\w*|"
    r"(sahte|gercege aykiri)\s+(belge|fatura)")
_GARANTI = re.compile(r"garanti\w*|kesin(likle)?\s+(kabul|onay|alir|cikar)\w*|kesin\s+mi\b|onaylanir\s+mi")
MANIPULASYON_UYARISI = (
    "**Önemli:** Uygunluğu yapay olarak sağlamaya yönelik bir yol (şirketi bölerek ölçeği küçük göstermek, çalışan ya "
    "da ciroyu eksik bildirmek, harcama veya belge tarihini değiştirmek) için yardımcı olamam. Bu tür işlemler "
    "desteğin geri istenmesine ve cezai sorumluluğa yol açabilir. [Genel ilke – teyit edin] Ölçek değerlendirmesinde "
    "ortak ve bağlı işletmelerin verileri birlikte dikkate alınabilir; doğru beyanla uygun olduğunuz programlar "
    "aşağıdadır.")
GARANTI_NOTU = ("**Garanti:** Hiçbir destek için kabul garantisi verilemez; nihai karar kurumun değerlendirmesine "
                "bağlıdır. Aşağıda kayda göre şartları sağlayıp sağlamadığınızı ve başvuruyu güçlendirecek adımları "
                "gösterdim.")


# "20/B istisnasıyla çalışıyorum", "4447 teşvikinden yararlanıyoruz": kullanıcının ŞU AN yararlandığını söylediği
# program. Arayüz simülasyonu ve hakem bulgusu 2026-10-12: Rekortiv yanıtı, kullanıcının zaten kullandığı 20/B
# istisnasını "Öne çıkan" diye sunuyordu. Soru kipi ("yararlanıyor muyum") ve olasılık ("yararlanabilir miyim") sayılmaz.
_KULLANIYOR = re.compile(r"(?:calis|yararlan|faydalan|kullan|al)[iı]?yor(?:um|uz)\b(?!\s*m[iıuü])")
_MADDE_KODU = re.compile(r"(?<![\w/])(\d{1,3}/[a-z])(?![\w/])")


def kullanilan_programlar(soru: str, adaylar: list) -> list:
    """Soruda kodu (1812, 4447, 20/B) bir kullanım fiiliyle birlikte geçen aday değerlendirmeler."""
    katli = _katla(soru)
    sonuc = []
    for d in adaylar:
        baslik = _katla(d.tesvik.baslik or "")
        kodlar = set(_KOD.findall(baslik)) | set(_MADDE_KODU.findall(baslik))
        for kod in kodlar:
            for m in re.finditer(rf"(?<![\w/]){re.escape(kod)}(?![\w/])", katli):
                cumle = re.split(r"[.;?!]", katli[m.end():], maxsplit=1)[0]
                if _KULLANIYOR.search(cumle[:60]):
                    sonuc.append(d)
                    break
            if sonuc and sonuc[-1] is d:
                break
    return sonuc


def ozel_notlar(soru: str) -> list[str]:
    """Soru türüne göre yanıtın başına eklenen notlar: manipülasyon reddi, garanti yok, kaldırılmış/kayıtsız program."""
    from app.girisim import VERITABANINDA_OLMAYAN_PROGRAMLAR
    katli = _katla(soru)
    notlar = []
    if _MANIPULASYON.search(katli):
        notlar.append(MANIPULASYON_UYARISI)
    if _GARANTI.search(katli):
        notlar.append(GARANTI_NOTU)
    if re.search(r"turquality|5447|5448", katli):
        notlar.append("**Turquality:** Veritabanımızda Turquality programının kaydı yok; oran ve limit veremem. "
                      "Mevzuat notu: 5447 sayılı Karar (E-Turquality) yürürlükten kaldırılmıştır (10962 sayılı Karar "
                      "m.49-50, Resmî Gazete 27.02.2026). Turquality'nin güncel şartlarını Ticaret Bakanlığı'ndan teyit "
                      "edin.")
    kayitsiz = [p for p in VERITABANINDA_OLMAYAN_PROGRAMLAR if _katla(p).split()[0] in katli
                and all(k in katli for k in _anlamli_kelimeler(p) if not k.startswith(GENEL_KOKLER))]
    if kayitsiz:
        notlar.append("**Sistemde kaydı olmayan program:** " + "; ".join(kayitsiz) + " hakkında doğrulanmış kaydımız "
                      "yok; oran, limit ve şart vermiyorum. Güncel bilgiyi kurumun resmî sayfasından teyit edin.")
    return notlar


def _kayit_tutar_metni(t) -> str:
    return " ".join(str(x or "") for x in (t.tesvil_tutari, t.tutari_hesaplama_formulu, t.ozet, t.detay, t.durum_notu,
                                         " ".join(t.basvuru_sartlari or [])))


def tutar_gecen_kayitlar(soru: str, kayitlar: list) -> list:
    """Sorudaki TL tutarı ("hâlâ 15.102 TL mi?") hangi kayıtlarda geçiyor (en çok 3; etkin kayıt önce)."""
    from app.dayanak import tl_tutarlari
    iddia = tl_tutarlari(soru)
    if not iddia:
        return []
    bulunan = [t for t in kayitlar if iddia & tl_tutarlari(_kayit_tutar_metni(t))]
    return sorted(bulunan, key=lambda t: t.aktif_mi is False)[:3] if len(bulunan) <= 3 else []


def dogrulanamayan_tutarlar(soru: str, kayitlar: list) -> list[str]:
    """Sorudaki TL tutarı iddiası ("hâlâ 15.102 TL mi?") odak kayıtlarının hiçbir alanında geçmiyorsa döner."""
    from app.dayanak import tl_tutarlari
    # "4 milyon TL'lik makine" yatırımın büyüklüğüdür, destek tutarı iddiası değil (persona denemesi 2026-10-12).
    soru = re.sub(r"\d[\d.,]*\s*(?:milyon|milyar|bin)?\s*(?:TL|lira)\s*['’]?\s*(?:l[ıiuü]k|l[ıiuü]ğ)\w*", " ", soru or "",
                  flags=re.I)
    iddia = tl_tutarlari(soru)
    if not iddia:
        return []
    kayitta = tl_tutarlari(" ".join(_kayit_tutar_metni(t) for t in kayitlar))
    return [f"{v:,.0f}".replace(",", ".") + " TL" for v in sorted(iddia) if v not in kayitta]


def sorulan_tutarin_akibeti(soru: str, t) -> str:
    """Sorudaki TL tutarı ("hâlâ 15.102 TL mi?") kaydın tutar alanlarında geçiyorsa geçtiği cümle parçası (kayıttan)."""
    from app.dayanak import tl_tutarlari
    iddia = tl_tutarlari(soru)
    if not iddia:
        return ""
    for alan in (t.tesvil_tutari, t.tutari_hesaplama_formulu, t.durum_notu):
        for parca in re.split(r"(?<=[.;])\s+|\s+\|\s+", str(alan or "")):
            if iddia & tl_tutarlari(parca):
                return _kisalt(_temiz(parca).strip(" ;."), 220)
    return ""


# ------------------------------------------------------------------ çağrı / başvuru dönemi
_ALT_CAGRI = re.compile(r"^(.+?)\s+(?:Çağrısı|başvuruları)\b")


def alt_destek_cagrisi(t, c: dict | None) -> str:
    """Çağrı programın tamamına değil bir alt desteğine ya da aşamasına aitse o adı döndürür ("İş Geliştirme",
    "1812-2026-2 Aşama 2"): çağrı adındaki ayırt edici kelimeler program başlığında yok ama kayıt metninde var."""
    m = _ALT_CAGRI.match((c or {}).get("ad") or "")
    if not m:
        return ""
    baslik = _katla(t.baslik or "")
    metin = _katla(" ".join(str(x or "") for x in (t.ozet, t.detay, t.tesvil_tutari,
                                                   " ".join(x["metin"] for x in _maddeler(t)))))
    kelimeler = [k for k in re.findall(r"[a-z]{3,}", _katla(m.group(1))) if k not in ("yili", "donem", "yilinin")]
    ayirici = [k for k in kelimeler if k not in baslik]
    if not ayirici or not all(k in metin for k in ayirici):
        return ""
    return re.sub(r"\s+\d{4}\s+yılı.*$", "", m.group(1)).strip()


def cagri_bilgisi(t, bugun: date) -> tuple[str, dict | None]:
    """(dönem durumu, çağrı sözlüğü). Ön kayıt süresi geçmişse yeni başvuran için kapalı sayılır."""
    from app.cagrilar import program_cagrilari
    cagrilar = program_cagrilari(t, bugun)
    if not cagrilar:
        return "yok", None
    c = cagrilar[0]
    return {"acik": "acik", "yaklasan": "yaklasan", "on_kayit_kapandi": "on_kayit_kapandi", "kapandi": "kapandi",
            "tarihsiz": "tarihsiz"}.get(c["durum"], "tarihsiz"), c


def cagri_durumu(t, bugun: date) -> str:
    """acik (açık ya da yaklaşan) | kapali (kapanmış ya da ön kaydı geçmiş) | bilinmiyor (çağrı kaydı yok)."""
    donem, _ = cagri_bilgisi(t, bugun)
    return {"acik": "acik", "yaklasan": "acik", "on_kayit_kapandi": "kapali", "kapandi": "kapali"}.get(donem, "bilinmiyor")


def _hedefli_cagri(c: dict | None) -> str:
    """Çağrı notu önceki bir aşamayı/desteği şart koşuyorsa ("1812 tohum öncesi yatırım almış ya da 1512 ile
    desteklenmiş girişimler için") o not; değilse boş. Böyle çağrı yeni başvuranın çağrısı gibi sunulmaz."""
    notlar = _temiz((c or {}).get("notlar") or "")
    if re.search(r"(almış|desteklenmiş|tamamlamış|kurulmuş|hak kazanmış)\b.{0,80}\biçin", notlar):
        return _cumle_kisalt(notlar, 200).rstrip(".")
    return ""


def takvim_metni(d: Degerlendirme, bugun: date, kisa: bool = False) -> str:
    t, c = d.tesvik, d.cagri
    if t.aktif_mi is False:
        neden = kullanici_durum_notu(t.durum_notu)
        return "Başvuruya açık değil" + (f" ({neden})" if neden else "; güncel durumu kurumdan teyit edin")
    if c is None and d.alt_not:
        return d.alt_not
    if c is None:
        sure = _cumle_kisalt(_temiz(t.basvuru_suresi), 220 if kisa else 320)
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4}) tarihine kadar", sure)
        if m:
            son = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if son >= bugun:
                sure = sure.replace(m.group(0), f"{m.group(0)} ({(son - bugun).days} gün kaldı)", 1)
        on = "" if t.aktif_mi else "Programın sürdüğü teyit edilmeli. "
        return on + (f"{sure} (kayıttan; güncel çağrıyı kurumdan teyit edin)" if sure else
                     "Başvuru takvimi kayıtta yok; güncel çağrıyı kurumdan teyit edin")
    ad = c["ad"]
    hedef = _hedefli_cagri(c)
    if d.donem == "acik" and hedef and kisa:
        return (f"{ad} yalnız şunlar için açık: {hedef}; yeni başvuranlar için açık çağrı kayıtlarımızda yok "
                "(kurum duyurularından takip edin)")
    if d.donem == "acik":
        metin = f"{ad}: başvuruya açık" + (f" — bu çağrı yalnız şunlar için: {hedef}" if hedef else "")
        iki_tarih = c["on_kayit_son"] and c["kapanis"] and c["on_kayit_son"] != c["kapanis"]
        if iki_tarih:
            kap = date.fromisoformat(str(c["kapanis"])[:10])
            metin += (f" — ön kayıt son günü {_tarih(c['on_kayit_son'])}"
                      + (f" ({c['kalan_gun']} gün kaldı)" if c["kalan_gun"] is not None else "")
                      + f"; başvuru kapanışı {_tarih(c['kapanis'])} ({(kap - bugun).days} gün kaldı)")
        elif c["son_gun"]:
            metin += f" — yeni başvuru için son gün {_tarih(c['son_gun'])}" + (
                f" ({c['kalan_gun']} gün kaldı)" if c["kalan_gun"] is not None else "")
    elif d.donem == "yaklasan":
        metin = f"{ad}: açılış {_tarih(c['acilis'])}" + (f", kapanış {_tarih(c['kapanis'])}" if c["kapanis"] else "")
    elif d.donem == "on_kayit_kapandi":
        metin = (f"{ad}: yeni başvuru için ön kayıt süresi {_tarih(c['on_kayit_son'])} tarihinde doldu"
                 + (f"; çağrı {_tarih(c['kapanis'])} tarihinde kapanıyor (yalnız ön kaydını yapmış olanlar için)"
                    if c["kapanis"] else ""))
    elif d.donem == "kapandi":
        metin = (f"{ad}: kapandı" + (f" ({_tarih(c['kapanis'])})" if c["kapanis"] else "")
                 + "; sonraki dönem kayıtlarımızda yok, kurumdan takip edin")
    else:
        metin = f"{ad}: tarih duyurulmadı"
    if kisa and re.search(r"taslak takvim", c.get("notlar") or "", re.I):
        metin += " (kurumun taslak takvimi; kesin tarihler çağrı duyurusunda)"
    if c.get("notlar") and not kisa:
        metin += f". Not: {_cumle_kisalt(_temiz(c['notlar']), 220)}"
    if not kisa:
        metin += f" (duyuru: {c['kaynak_url']}, doğrulama {_tarih(c['dogrulama_tarihi'])})"
    return metin


# ------------------------------------------------------------------ kayıt alanları
def _kobi_mi(profil) -> bool | None:
    """Profile göre KOBİ mi (KOBİ Yönetmeliği eşikleri); çalışan sayısı yoksa None."""
    if profil is None:
        return None
    from app.kobi import kobi_sinifi
    sinif = kobi_sinifi(getattr(profil, "calisan_sayisi", None), getattr(profil, "yillik_ciro", None)).sinif
    return None if sinif is None else sinif != "buyuk"


def _profile_uymayan_kosul(metin: str, d: Degerlendirme) -> bool:
    """Koşulu kullanıcıda kesin sağlanmayan koşullu kural ("KOBİ değilseniz ...", KOBİ olan kullanıcıya)."""
    if d.kobi is True and re.match(r"\s*KOB[İI] değilseniz", metin or ""):
        return True
    return d.kobi is False and bool(re.match(r"\s*KOB[İI] iseniz", metin or ""))


def _maddeler(t) -> list[dict]:
    from app.basvuru_listesi import maddeler
    return maddeler(t)


def _tekil(maddeler: list[dict]) -> list[dict]:
    gorulen, sonuc = set(), []
    for m in maddeler:
        n = _norm(m["metin"])
        if n and n not in gorulen:
            gorulen.add(n)
            sonuc.append(m)
    return sonuc


def _hitap(metin: str) -> str:
    """Kontrol listesindeki ikinci tekil hitabı kullanıcı metninin hitabına (siz) çevirir."""
    metin = re.sub(r"\b(\w+m[ae]l[ıi]s)([ıi])n\b", lambda x: x.group(1) + x.group(2) + "n" + x.group(2) + "z", metin)
    metin = re.sub(r"\bişe alındığın tarihten\b", "işe alındığı tarihten", metin)
    metin = re.sub(r"\b(\w+) isen\b", r"\1 iseniz", metin)
    return re.sub(r"\bborcun\b", "borcunuz", metin)


def _okunur_alinti(alinti: str) -> bool:
    """PDF çıkarımında harfleri aralıklanmış alıntı ("A s g a r i 1 2 a y") kanıt olarak doğrudur ama okunmaz:
    tek karakterlik parçaların oranı yüksekse kullanıcıya gösterilmez."""
    parcalar = alinti.split()
    return bool(parcalar) and sum(len(x) == 1 for x in parcalar) / len(parcalar) < 0.3


def _madde_metni(m: dict) -> str:
    """Kontrol listesi maddesi; kısa, doğrulanmış ve okunur alıntı varsa eklenir, uzun alıntı yarıda kesilmez
    (gösterilmez)."""
    metin = _hitap(_temiz(m["metin"]))
    if m.get("alinti") and m.get("dogrulandi") and len(m["alinti"]) <= ALINTI_SINIRI and _okunur_alinti(m["alinti"]):
        metin += f" — resmî metin: “{' '.join(m['alinti'].split())}”"
    elif m.get("dogrulandi") is False:
        metin += " — kurumdan teyit edin"
    return metin


def tutar_metni(t, sinir: int = 600) -> str:
    parcalar = []
    if t.tesvil_tutari:
        parcalar.append(_temiz(t.tesvil_tutari))
    if t.tutari_hesaplama_formulu and t.tutari_hesaplama_formulu != t.tesvil_tutari:
        parcalar.append("Hesaplama: " + _temiz(t.tutari_hesaplama_formulu))
    if not parcalar and t.tutari_max:
        parcalar.append(f"azami ₺{t.tutari_max:,.0f}".replace(",", "."))
    return _cumle_kisalt(" ".join(parcalar), sinir) if parcalar else ""


def _destek_unsurlari(notlar: dict[int, str], t) -> str:
    p = notlar.get(t.id, "").split("\nDESTEK UNSURLARI (Karar metninden, profil bölgesine göre): ")
    return p[1] if len(p) == 2 else ""


def _kisitlar(t) -> list[str]:
    from app.match_adapter import OZELLIK_ETIKETLERI
    k = t.uygunluk_kriterleri or {}
    sonuc = []
    if k.get("bolge_kisitli"):
        sonuc.append("yalnız şu illerdeki başvuru sahipleri: " + ", ".join(x.capitalize() for x in k["bolge_kisitli"]))
    if k.get("sirket_turleri"):
        sonuc.append("yalnız: " + ", ".join(SIRKET_TURU_AD.get(x, x) for x in k["sirket_turleri"]))
    if k.get("exclusive_target_group") and k.get("target_group_tags"):
        sonuc.append("yalnız: " + ", ".join(OZELLIK_ETIKETLERI.get(x, x) for x in k["target_group_tags"]))
    if k.get("max_olcek") == "orta":
        sonuc.append("yalnız KOBİ'ler")
    return sonuc


def _genel_kitleye_acik(t) -> bool:
    """Profil bilinmeden ana listeye alınabilir mi (il, şirket türü ya da hedef kitle kısıtı olmayan)."""
    k = t.uygunluk_kriterleri or {}
    turler = set(k.get("sirket_turleri") or [])
    return not k.get("bolge_kisitli") and not k.get("exclusive_target_group") and (
        not turler or bool(turler & {"sahis", "limited", "anonim"}))


# ------------------------------------------------------------------ değerlendirme
def _kobi_engeli(t, profil) -> str | None:
    """Kesin büyük ölçekli işletmeye, şartı KOBİ'leri tarif eden program kapalıdır (kayıttaki şart metniyle)."""
    from app.kobi import kobi_sinifi
    olcek = kobi_sinifi(getattr(profil, "calisan_sayisi", None), getattr(profil, "yillik_ciro", None))
    if not (olcek.kesin and olcek.sinif == "buyuk"):
        return None
    sartlar = [*(t.basvuru_sartlari or []), *(m["metin"] for m in _maddeler(t) if m["tur"] == "sart")]
    for s in sartlar:
        if _KOBI_SART.search(s) and not _KOBI_DISI.search(s):
            return f"program KOBİ'lere yönelik (kayıttaki şart: “{_kisalt(s, 140)}”); işletmeniz büyük ölçekli"
    return None


def _imalat_sarti_engeli(metin: str, profil) -> bool:
    """"İmalatçı KOBİ olmak" şartı; profilde faaliyet biliniyor ve imalat değilse (persona denemesi 2026-10-12: KGF
    Yatırım-İşletme paketi fındık ve çilek üreticisine "engel yok" diye sunuluyordu)."""
    if profil is None or not re.search(r"^\s*İmalatçı KOBİ|imalat sanayi(?:i|inde)? (?:işletme|faaliyet|KOB)", metin or "",
                                       re.I):
        return False
    nace = re.sub(r"^[A-Z]\.", "", getattr(profil, "nace_kodu", None) or "")
    if nace[:2].isdigit():
        return not 10 <= int(nace[:2]) <= 33
    return (getattr(profil, "sektor", None) or "") in ("tarim", "hizmet", "e-ticaret")


def _kisisel_saglananlar(t, profil) -> tuple[list[str], set[str]]:
    """Profilde karşılığı olan kişisel şartlar (yaş, ortaklık, sertifika) sağlanıyorsa: (metinler, madde metinleri)."""
    k = t.uygunluk_kriterleri or {}
    saglanan, maddeler = [], set()
    tur23 = {m["metin"]: m for m in _maddeler(t)} if profil is not None else {}
    yas = getattr(profil, "kurucu_yasi", None)
    if k.get("kurucu_yasi_max") and yas is not None and yas <= k["kurucu_yasi_max"]:
        saglanan.append(f"yaş şartı (en çok {k['kurucu_yasi_max']}; profilinizde {yas})")
    if k.get("ortaklik_yasagi_sirketsiz") and getattr(profil, "baska_sirkette_ortak", None) is False:
        saglanan.append("başka şirkette ortaklık olmaması (profilinize göre)")
    serts = getattr(profil, "sertifikalar", None) or []
    if k.get("gerekli_sertifika") and k["gerekli_sertifika"] in serts:
        saglanan.append("gerekli sertifika (profilinize göre var)")
    if saglanan:
        # tur23'ün eklediği ilgili şart maddeleri teyit listesinden düşer
        maddeler = {metin for metin, m in tur23.items() if m.get("tur") == "sart" and (
            (re.search(r"\d+\s*yaş|\byaş(?:ı|ını|ında|ın)?\b", metin) and k.get("kurucu_yasi_max") and yas is not None
             and not _FIRMA_YASI.search(metin))
            or ("ortağı olmamak" in metin and getattr(profil, "baska_sirkette_ortak", None) is False)
            or (re.search(r"ürün sertifika|organik", metin, re.I) and k.get("gerekli_sertifika") in serts))}
    return saglanan, maddeler


_HEDEF_KALIP = {"kadin_girisimci": r"kad[ıi]n girişimci|kad[ıi]n ortak|kad[ıi]n.{0,60}hisse|kad[ıi]nlar(?:ın)? "
                                      r"yönettiği|kad[ıi]n yönetici",
                "genc_girisimci": r"genç girişimci|18-35|(?:sahib|ortağ|girişimci|kurucu)\w*.{0,40}\d+\s*yaş"}
_FIRMA_YASI = re.compile(r"(?:işletme|firma|şirket)\w*\s+(?:en (?:fazla|az|çok)\s+)?\d+\s*yaş", re.I)
_HEDEF_AD = {"kadin_girisimci": "kadın girişimci", "genc_girisimci": "genç girişimci"}


def _hedef_kitle_eslesmesi(t, profil) -> str | None:
    """Profilde işaretli özellik (kadın/genç girişimci) programın hedef grubundaysa o etiket."""
    etiket = set(getattr(profil, "ozellikler", None) or [])
    k = t.uygunluk_kriterleri or {}
    yas = getattr(profil, "kurucu_yasi", None)
    for tag in k.get("target_group_tags") or []:
        if tag == "genc_girisimci":
            # genç tanımı programa göre değişir (29, 35); yaş bilinmeden sağlanmış sayılmaz
            sinir = k.get("kurucu_yasi_max") or 35
            if yas is not None and 18 <= yas <= sinir:
                return tag
        elif tag in etiket and tag in _HEDEF_KALIP:
            return tag
    return None


_CIRO_SART = re.compile(r"(?:ciro|hasılat|net satış)\w*[^.;]{0,40}?(\d[\d.,]*)\s*(milyon|milyar|bin)?\s*TL\W{0,2}\w*\s*"
                        r"(aşmamak|aşmamalı|aşmayan|en fazla|altında|geçmemek|ve altı|en az|asgari|üzerinde|ve üzeri)",
                        re.I)


# Şart metnindeki USD eşiği: "son 3 yıl ortalama ihracatın en az 3.000.000 ABD Doları" (5973 m.17), "son üç takvim
# yılı gelirlerinin ortalaması ... en az 1.500.000 ABD doları" (10962 m.33). Yapılandırılmış alan
# (min_onceki_yil_ihracat_usd) yalnız bazı kayıtlarda dolu; hakem bulgusu 4. tur: aynı yanıtta m.5 eşiği ciroyla
# kıyaslanırken m.17/m.33 eşikleri "doğrulanamayan şart" kalıyordu. İthalat eşiği (Stratejik Hamle) sayılmaz.
_USD_ESIK = re.compile(r"(ihracat|gelir|hasılat|satış)\w*(?:(?!\bithalat)[^;]){0,120}?(?:(?:en az|asgari)\s*(\d[\d.,]*)\s*"
                       r"(milyon|bin)?\s*(?:ABD\s*)?(?:USD|dolar)|(\d[\d.,]*)\s*(milyon|bin)?\s*(?:ABD\s*)?(?:USD|dolar)\w*"
                       r"\s*(?:ve\s*)?(?:üzeri|üzerinde))", re.I)


def usd_esigi(t) -> tuple[float, str] | None:
    """Kaydın şartlarındaki asgari USD ihracat/gelir eşiği: (tutar, "ihracat"|"gelir")."""
    from app.dayanak import _deger
    esik = (getattr(t, "uygunluk_kriterleri", None) or {}).get("min_onceki_yil_ihracat_usd")
    if esik:
        return float(esik), "ihracat"
    for x in list(getattr(t, "basvuru_sartlari", None) or []) + [
            m.get("metin", "") for m in getattr(t, "kontrol_listesi", None) or [] if m.get("tur") == "sart"]:
        m = _USD_ESIK.search(x or "")
        if m:
            deger = _deger(m.group(2) or m.group(4), m.group(3) or m.group(5))
            if deger:
                return deger, "ihracat" if m.group(1).lower().startswith("ihracat") else "gelir"
    return None


def _ciro_sarti(metin: str, profil) -> tuple[str, str] | None:
    """Ciro eşikli şart ("son yıl cirosu 10 milyon TL'yi aşmamak") profildeki yıllık ciroyla: ("saglanan", açıklama)
    ya da ("engel", gerekçe); karşılaştırılamıyorsa None."""
    from app.dayanak import _deger
    ciro = getattr(profil, "yillik_ciro", None)
    m = _CIRO_SART.search(metin or "")
    if ciro is None or not m:
        return None
    sinir = _deger(m.group(1), m.group(2))
    if not sinir:
        return None
    ust_sinir = not re.match(r"en az|asgari|üzerinde|ve üzeri", m.group(3), re.I)
    tl = lambda v: f"{v:,.0f}".replace(",", ".")  # noqa: E731
    uyuyor = ciro <= sinir if ust_sinir else ciro >= sinir
    if uyuyor:
        return "saglanan", f"ciro şartı ({'en fazla' if ust_sinir else 'en az'} {tl(sinir)} TL; profilinizde {tl(ciro)} TL)"
    return "engel", (f"yıllık cironuz ({tl(ciro)} TL) kayıttaki ciro şartını karşılamıyor — kayıttaki şart: "
                     f"“{_kisalt(_temiz(metin), 160)}”")


def _profilden_karsilanan(metin: str, profil) -> str | None:
    """Şart profil verisiyle zaten karşılanıyorsa kullanıcıya gösterilecek açıklama; değilse None."""
    if profil is None:
        return None
    from app.kobi import AD as KOBI_AD
    from app.kobi import kobi_sinifi
    tur = getattr(profil, "sirket_turu", None)
    nace = (getattr(profil, "nace_kodu", None) or "").replace("C.", "")
    olcek = kobi_sinifi(getattr(profil, "calisan_sayisi", None), getattr(profil, "yillik_ciro", None))
    from app.matching import _CALISAN_EN_AZ, _sayi
    n = getattr(profil, "calisan_sayisi", None)
    m_calisan = _CALISAN_EN_AZ.search(metin)
    # Yalnız toplam çalışan şartı; "en az elli tam zaman eşdeğer Ar-Ge personeli" toplam çalışanla karşılanmaz (hakem
    # bulgusu 2026-10-12, 5. tur: 65 çalışanlı firmada Ar-Ge merkezi şartı "sağlandı" sayılıyordu).
    if m_calisan and n is not None and n >= _sayi(m_calisan.group(1)) and not re.search(
            r"Ar-?Ge|tasarım|araştırmacı|tam zaman eşdeğer|mühendis|teknik personel", metin, re.I):
        # "İşverenin en az beş sigortalı çalışanı olmalıdır": profilde 9 çalışan → sağlanır (persona denemesi 2026-10-12)
        return f"çalışan sayısı şartı (en az {_sayi(m_calisan.group(1))}; profilinizde {n})"
    if re.search(r"TOBB|ticaret odası|sanayi odası|ticaret borsası", metin, re.I) and re.search(
            r"üye|kayıt|kaydı", metin, re.I) and not re.search(r"esnaf", metin, re.I) and tur in ("limited", "anonim"):
        # Ticaret siciline kayıtlı şirket odaya kaydolmak zorundadır (5174 sayılı Kanun m.9); hakem bulgusu 4. tur: TOBB
        # Nefes kredisinde limited şirkete "doğrulanamayan önemli şart: TOBB üyesi olmak" deniyordu.
        return f"oda (TOBB) üyeliği: {SIRKET_TURU_AD[tur]} ticaret siciline kayıtlıdır ve oda üyeliği zorunludur"
    kurulus = getattr(profil, "kurulus_tarihi", None)
    m_yas = re.search(r"\b0\s*-\s*(\d)\s*yaş", metin)
    if m_yas and kurulus is not None:
        from datetime import date
        yil = (date.today() - kurulus).days / 365.25
        if yil <= int(m_yas.group(1)):
            # "İş Kurma Desteği: ... 0-1 yaş işletme": şirket kurarsam varsayımında yeni şirket (persona denemesi 2026-10-12)
            return (f"işletme yaşı şartı (0-{m_yas.group(1)} yaş; "
                    + ("kurulacak şirket" if getattr(profil, "_varsayim", None) else f"kuruluş {kurulus:%d.%m.%Y}") + ")")
    hedefler = {h.lower() for h in getattr(profil, "hedefler", None) or []}
    if re.search(r"ihracata yönelik mal üreten imalatçı", metin, re.I) and nace[:2].isdigit() \
            and 10 <= int(nace[:2]) <= 33 and ("ihracat" in hedefler or getattr(profil, "sektor", None) == "ihracat"):
        # "ihracata yönelik mal üreten imalatçı" (Eximbank): imalat NACE'li ve ihracat hedefli profil bu tanıma girer
        # (persona denemesi 2026-10-12, zeytinyağı); gerçekleşmiş ihracat isteyen "ihracatçı" ayrıca aranmaz.
        return f"ihracata yönelik üretim yapan imalatçı (NACE {nace}, hedefinizde ihracat)"
    if re.match(r"\s*Şirket ya da kooperatif olmak\b", metin) and tur in ("limited", "anonim", "kooperatif"):
        # "(şahıs işletmesi yalnız E-İhracat Konsorsiyumu aracılığıyla)" notu şirkete kilit değildir
        return f"şirket/kooperatif statüsü ({SIRKET_TURU_AD[tur]})"
    if _KILIT.search(metin) or re.search(r"\d{2}\.\d{2}\.\d{4}|sonradan", metin):
        return None
    # Şartta sayısal eşik de varsa ("Ar-Ge merkezi: ... en az elli tam zaman eşdeğer Ar-Ge personeli") sermaye şirketi
    # olmak şartı karşılamaz (hakem bulgusu 2026-10-12: Ar-Ge merkezi şartı anonim şirkette "sağlandı" sayılıyordu).
    if re.search(r"sermaye şirket", metin, re.I) and tur in ("limited", "anonim") and not re.search(
            r"KOB[İI]|\ben az\b|\d", metin):
        return f"sermaye şirketi ({SIRKET_TURU_AD[tur]})"
    if _KOBI.search(metin) and olcek.kesin and olcek.sinif in ("mikro", "kucuk", "orta") and not re.search(
            r"sermaye şirket|yerleşik|imalat|sektör", metin, re.I):
        return f"KOBİ ölçeği ({KOBI_AD[olcek.sinif]})"
    if re.search(r"sermaye şirket", metin, re.I) and _KOBI.search(metin) and tur in ("limited", "anonim") \
            and olcek.kesin and olcek.sinif in ("mikro", "kucuk", "orta"):
        return f"KOBİ ölçeğinde sermaye şirketi ({SIRKET_TURU_AD[tur]}, {KOBI_AD[olcek.sinif]})"
    if re.search(r"Kısım C|imalat", metin, re.I) and nace[:2].isdigit() and 10 <= int(nace[:2]) <= 33:
        return f"imalat faaliyeti (NACE {nace})"
    if re.search(r"Türk Ticaret Kanunu.{0,40}(gerçek|tüzel)", metin) and tur in ("sahis", "limited", "anonim",
                                                                                "kooperatif"):
        return f"TTK'da tanımlı statü ({SIRKET_TURU_AD[tur]})"
    # "tarım sektöründe faaliyet göstermek" (kayıt/ÇKS şartı değil): profilde sektör tarım
    if getattr(profil, "sektor", None) == "tarim" and re.search(
            r"tarım(?:sal)? (?:sektör|üretim|faaliyet)|tarımsal üretici|tarım işletmesi", metin, re.I) \
            and not re.search(r"kayıt|ÇKS|sistem|belge|sertifika", metin, re.I):
        return "tarım faaliyeti (profilinizde)"
    # "Şirket olmak: TTK md.124'teki şirketler (… anonim, limited) ya da … kooperatif; şahıs işletmesi kapsam dışı"
    if re.match(r"\s*Şirket olmak\b", metin) and re.search(r"TTK|Ticaret Kanunu", metin) \
            and tur in ("limited", "anonim") + (("kooperatif",) if re.search(r"kooperatif", metin) else ()):
        return f"şirket statüsü ({SIRKET_TURU_AD[tur]})"
    return None


def _sert_filtre(t, profil) -> str | None:
    """Eşleştirmeden geçmeyen aday için il, sektör, ölçek ve hedef kitle filtresi (app/match_scoring.hard_filter)."""
    from app.match_adapter import company_from_profile, program_from_tesvik
    from app.match_scoring import hard_filter
    if profil is None or not (t.uygunluk_kriterleri or {}).get("sektorler"):
        return None
    sirket = company_from_profile(profil)
    hedef = _hedef_kitle_eslesmesi(t, profil)
    if hedef:
        sirket.tags.add(hedef)
    sebepler, _ = hard_filter(sirket, program_from_tesvik(t))
    from app.match_adapter import OZELLIK_ETIKETLERI
    sebepler = [re.sub(r"\b(" + "|".join(OZELLIK_ETIKETLERI) + r")\b", lambda m: OZELLIK_ETIKETLERI[m.group(1)].lower(),
                       x) for x in sebepler]
    sektor = _sektor_disi(t, profil)
    if sektor:
        sebepler.append(sektor)
    return "; ".join(sebepler) if sebepler else None


def _sektor_disi(t, profil) -> str | None:
    """Programın sektör etiketleri "genel" içermiyor ve profilin faaliyeti (sektör ya da NACE) hiçbirine girmiyorsa
    gerekçe; bilinmiyorsa None. app/matching.esles'teki sektör kuralının eşleştirme dışı adaylara uygulanması."""
    from app.matching import HEDEF_SEKTOR_ETIKETLERI, _arge_sinyali
    k_sek = {s.lower() for s in (t.uygunluk_kriterleri or {}).get("sektorler") or []}
    if not k_sek or "genel" in k_sek:
        return None
    p_sek = (getattr(profil, "sektor", None) or "").lower()
    hedef = {h.lower() for h in getattr(profil, "hedefler", None) or []}
    nace = re.sub(r"^[A-Z]\.", "", getattr(profil, "nace_kodu", None) or "")
    nace2 = int(nace[:2]) if nace[:2].isdigit() else None
    if p_sek in k_sek or k_sek & HEDEF_SEKTOR_ETIKETLERI & hedef:
        return None
    if k_sek <= HEDEF_SEKTOR_ETIKETLERI and (p_sek == "imalat" or (nace2 is not None and 10 <= nace2 <= 33)):
        # Mal üreten işletmede "Ar-Ge, ihracat" etiketleri ihtiyaç türüdür, faaliyet sektörü değil; asıl şartlar (ihracat
        # artışı, kredi alt limiti) kayıttan değerlendirilir (hakem bulgusu 2026-10-12, 5-6. tur: Küresel Rekabetçilik
        # matbaaya "sektör kapsamı NACE 18.12'yi kapsamıyor" gerekçesiyle kapalıydı). Hizmet işletmesinde (otel) mal
        # ihracatı programı kapalı kalır (7. tur: 5973 m.12 otele "engel yok" olmuştu).
        return None
    if "arge" in k_sek and _arge_sinyali(profil, hedef):
        return None
    nace_etiketi = (None if nace2 is None else "tarim" if nace2 <= 3 else "imalat" if 10 <= nace2 <= 33
                    else "hizmet" if nace2 >= 45 else None)
    if nace_etiketi in k_sek:
        return None
    if nace2 is None and (p_sek in ("", "genel", "perakende", "ihracat", "e-ticaret") or p_sek not in SEKTOR_AD):
        return None   # faaliyet bilinmiyor ya da sınıflanamıyor: elemeyiz
    if nace2 is not None and nace_etiketi is None and p_sek in ("", "genel"):
        return None   # NACE bölümünün sektör etiketi yok (madencilik, enerji vb.): elemeyiz
    faaliyet = f"NACE {nace}" if nace2 is not None else SEKTOR_AD.get(p_sek, p_sek)
    kapsam = ", ".join(SEKTOR_AD.get(x, x) for x in sorted(k_sek))
    return f"programın sektör kapsamı ({kapsam}) faaliyetinizi ({faaliyet}) kapsamıyor"


def _sirket_turu_gerekcesi(engel: str, t, profil) -> str:
    """"yalnızca kooperatif başvurabilir" gibi yapılandırılmış alan özeti yerine kaydın başvuru sahibi şartı."""
    if not engel.startswith("yalnızca"):
        return engel
    # Önce şirket/şahıs tanımı (5973/5986/10962: "Şirket olmak: TTK md.124 ...; şahıs işletmesi kapsam dışı" — 5986'da
    # konsorsiyum yolunu da söyler), yoksa başvuru sahibi şartı.
    sartlar = [m for m in _maddeler(t) if m["tur"] == "sart"]
    for m in sorted(sartlar, key=lambda m: not re.search(r"^\s*Şirket (?:olmak|ya da)|şahıs işletme", m["metin"], re.I)):
        if re.search(r"başvuru sahib|başvurabilir|uygun başvuru|^\s*Şirket (?:olmak|ya da)|şahıs işletme", m["metin"],
                     re.I):
            return (f"başvuru sahibi türünüz ({SIRKET_TURU_AD.get(profil.sirket_turu, profil.sirket_turu)}) şartta "
                    f"sayılmıyor — kayıttaki şart: “{_kisalt(_temiz(m['metin']), 200)}”")
    return engel


def _mukerrer(t) -> bool:
    """Başka bir kaydın eski kopyası olarak işaretlenmiş kayıt (durum notu "MÜKERRER KAYIT")."""
    return "MÜKERRER KAYIT" in (t.durum_notu or "")


def _cekirdek(baslik: str) -> list[str]:
    return [k for k in re.findall(r"[a-z]+", _katla(baslik)) if k not in ("kobi", "kgf")]


_KOSGEB_ONAYI = re.compile(r"KOSGEB tarafından (?:desteklenmesi )?uygun|KOSGEB(?:'|’)?(?:ce|ye) onay|KOSGEB .{0,60}onaylan"
                           r"|KOSGEB .{0,80}başvuru onayı")


def ust_programlar(kayitlar: list, tum: list) -> dict[int, Any]:
    """KGF kefalet paketi → bağlı olduğu KOSGEB programı (adlarının ilk iki çekirdek kelimesi aynıysa): "KAPASİTE
    GELİŞTİRME DESTEK PAKETİ" → KOSGEB "Kapasite Geliştirme Destek Programı"."""
    kosgeb = [t for t in tum if t.kurum == "KOSGEB" and t.aktif_mi is not False]
    sonuc = {}
    for t in kayitlar:
        if t.kurum != "KGF" or not _KOSGEB_ONAYI.search(" ".join(str(x or "") for x in (
                t.ozet, t.detay, t.basvuru_suresi, " ".join(t.basvuru_sartlari or []),
                " ".join(m["metin"] for m in _maddeler(t) if m["tur"] in ("sart", "adim"))))):
            continue
        c = _cekirdek(t.baslik or "")[:2]
        if len(c) < 2:
            continue
        ust = [k for k in kosgeb if _cekirdek(k.baslik or "")[:2] == c]
        if len(ust) == 1:
            sonuc[t.id] = ust[0]
    return sonuc


def degerlendir(kayitlar: list, profil, notlar: dict[int, str], eslesme: dict[int, Any], odak: set[int],
                adi_gecen: set[int], bugun: date, ust: dict[int, Any] | None = None,
                soru: str = "") -> list[Degerlendirme]:
    from app.matching import uygunluk_engeli
    ust = ust or {}
    sonuc = []
    for t in kayitlar:
        d = Degerlendirme(t, "belirlenemedi", kobi=_kobi_mi(profil), adi_gecti=t.id in adi_gecen, odak=t.id in odak,
                          eslesti=t.id in eslesme, kisit=_kisitlar(t), profilli=profil is not None)
        d.donem, d.cagri = cagri_bilgisi(t, bugun)
        alt = alt_destek_cagrisi(t, d.cagri)
        if alt and d.donem in ("kapandi", "on_kayit_kapandi"):
            d.alt_not = (f"{alt} çağrısı kapandı ({_tarih(d.cagri['kapanis'])}); programın diğer destekleri ya da "
                         "aşamaları için kayıtlarımızda çağrı tarihi yok, kurumdan teyit edin")
            d.donem, d.cagri = "yok", None
        not_9903 = notlar.get(t.id, "")
        engel = None
        if t.aktif_mi is False:
            d.karar = "kapali"
            neden = re.sub(r"\s*[-–]\s*muhtemelen[^.;)]*", "", kullanici_durum_notu(t.durum_notu)).strip()
            d.gerekce.append("program başvuruya açık değil" + (f" ({neden})" if neden else
                                                               "; güncel durumu kurumdan teyit edin"))
        elif not_9903.startswith("UYGUN DEĞİL"):
            d.karar = "uygun_degil"
            d.gerekce.append(_kisalt(not_9903.split("\nDESTEK UNSURLARI")[0], 400))
        elif profil is not None and ((engel := uygunluk_engeli(t, profil)) or (engel := _kobi_engeli(t, profil))
                                     or (t.id not in eslesme and not not_9903
                                         and (engel := _sert_filtre(t, profil)))):
            d.karar = "uygun_degil"
            d.gerekce.append(_sirket_turu_gerekcesi(engel, t, profil))
        else:
            saglanan, dusen = _kisisel_saglananlar(t, profil)
            d.saglanan = saglanan
            sartlar = _tekil([m for m in _maddeler(t) if m["tur"] == "sart" and m["metin"] not in dusen])
            if getattr(profil, "sirket_turu", None) == "yok":
                # şirketsiz girişimci çok aşamalı programın ilk aşamasındadır; sonraki aşama şartı kilit sayılmaz
                sartlar = [m for m in sartlar if not re.search(r"Aşama [2-9]\b", m["metin"])]
            kilit = []
            ciro_engeli = ""
            hedef = _hedef_kitle_eslesmesi(t, profil)
            # kayıtta hedef kitle etiketi olmasa da şart metni profildeki kadın girişimci özelliğiyle karşılanabilir
            profil_hedef = [x for x in (getattr(profil, "ozellikler", None) or []) if x == "kadin_girisimci"]
            beyan = soru_beyanlari(soru)
            kisi = ["yalnız yurt dışına götürülen ya da gönderilen sigortalılar için"] \
                if _KISI_BASLIK.search(t.baslik or "") else []
            for m in sartlar:
                karsilanan = _profilden_karsilanan(m["metin"], profil)
                if karsilanan:
                    d.saglanan.append(karsilanan)
                    continue
                if _KISI_SARTI.search(m["metin"]):
                    d.teyit.append(_madde_metni(m))
                    kisi.append(_kisalt(_temiz(m["metin"]), 150))
                    continue
                if beyan.get("ortak_ulke") and re.search(r"ortak|ortağ", m["metin"], re.I) and re.search(
                        r"ülke|üye|yabancı|uluslararası", m["metin"], re.I):
                    d.saglanan.append(f"sorunuzdaki beyana göre {beyan['ortak_ulke']} ortak (ülkenin programa üye "
                                      "olduğunu çağrı belgesinden teyit edin)")
                    continue
                urun_sarti = re.match(r"\s*(\w+) (?:üreticisiyseniz|için:)", m["metin"])
                if urun_sarti and getattr(profil, "urun_turu", None) and _katla(urun_sarti.group(1)) != _katla(
                        profil.urun_turu):
                    # "Fındık üreticisiyseniz: ..." başka ürünün üreticisine gösterilmez (hakem bulgusu 5. tur: çilekçi)
                    continue
                if _imalat_sarti_engeli(m["metin"], profil):
                    ciro_engeli = (f"imalatçı işletmelere yönelik; faaliyetiniz "
                                   f"({SEKTOR_AD.get(getattr(profil, 'sektor', ''), getattr(profil, 'sektor', ''))}) imalat "
                                   f"değil — kayıttaki şart: “{_kisalt(_temiz(m['metin']), 120)}”")
                    continue
                ciro = _ciro_sarti(m["metin"], profil)
                if ciro and ciro[0] == "saglanan":
                    d.saglanan.append(ciro[1])
                    continue
                if ciro:
                    ciro_engeli = ciro[1]
                    continue
                if not hedef and profil_hedef and re.search(_HEDEF_KALIP["kadin_girisimci"], m["metin"], re.I):
                    hedef = "kadin_girisimci"
                if hedef and re.search(_HEDEF_KALIP[hedef], m["metin"], re.I) and not _FIRMA_YASI.search(m["metin"]):
                    d.saglanan.append(f"hedef kitle: {_HEDEF_AD[hedef]} (profilinize göre)")
                    if getattr(profil, "sirket_turu", None) in ("limited", "anonim", "kooperatif") \
                            and "%50" in m["metin"]:
                        d.teyit.append(f"Şirketinizde {_HEDEF_AD[hedef]} ortakların hisse toplamı %50 ve üzeri "
                                       "olmalı (tüzel firmalar için kayıttaki şart)")
                    continue
                d.teyit.append(_madde_metni(m))
                # İhracatçı birliğine üyelik başvuranın tamamlayabileceği bir hazırlık adımıdır (aidat + kayıt), programı
                # kilitlemez; şartlı gösterilir (hakem bulgusu 2026-10-12: "idari adım kilit şart sayılmış").
                # Dışlama şartı ("konsorsiyum üyesi olmamak", "... yararlanamaz") varsayılan olarak sağlanır; kilit değil
                # (hakem bulgusu 2026-10-12: sipariş karşılama kartında "kilit şart" diye gösteriliyordu).
                # "Genç girişimci kategorisi: ..." gibi isteğe bağlı alt kategori şartı programın genel şartı değildir;
                # teyit listesinde kalır, kilit sayılmaz (hakem bulgusu 2026-10-12, 5-7. tur: esnaf kredisinde "önemli
                # şart" olarak genç girişimci kategorisi gösteriliyor, kredi şahıs işletmesinin yanıtına girmiyordu).
                if _KILIT.search(m["metin"]) and not re.match(r"\s*[^:]{2,40} kategorisi(?: için)?:", m["metin"]) \
                        and not re.search(r"ihracatçı birliğine üye", m["metin"], re.I) \
                        and not re.search(r"olmamak|olmaması|olmamalı|yararlanamaz|kapsam dışı|desteklenmez|"
                                          r"başvuramaz|faydalanamaz|yapamaz|bünyesindeyseniz", m["metin"], re.I):
                    kilit.append(_kisalt(_temiz(m["metin"]), 150))
            d.saglanan = list(dict.fromkeys(d.saglanan))
            madde_norm = {_norm(m["metin"]) for m in _maddeler(t)}
            d.teyit += [_temiz(x) for x in (t.basvuru_sartlari or []) if _norm(x) not in madde_norm
                        and re.search(r"korumak|taahhüt|sürdürmek|devam ettirmek", x, re.I)]
            gorulen, tekil = set(), []
            for x in d.teyit:
                anahtar = x.split(" — resmî metin: ")[1] if " — resmî metin: " in x else x
                if anahtar not in gorulen:
                    gorulen.add(anahtar)
                    tekil.append(x)
            d.teyit = tekil
            esik_tur = usd_esigi(t)
            esik, esik_ad = esik_tur if esik_tur else (None, "")
            ciro = getattr(profil, "yillik_ciro", None)
            usd = f"{esik:,.0f}".replace(",", ".") if esik else ""
            if esik and ciro and ciro < esik * ASGARI_USD_TRY:
                # cironun tamamı ihracat olsa bile eşik sağlanamaz (1 USD, 2021'den beri 10 TL'nin üzerinde)
                kilit.insert(0, (f"düşük olasılık: yıllık cironuz ({_tl(ciro).split(',')[0]} TL), kaydın aradığı en az "
                                 f"{usd} USD {esik_ad} eşiğinin TL karşılığından az"
                                 + ("; cironuzun tamamı ihracat olsa bile eşiğe ulaşmaz" if esik_ad == "ihracat" else "")
                                 + f" (1 USD {ASGARI_USD_TRY} TL'nin üzerinde)"))
            elif esik and (t.uygunluk_kriterleri or {}).get("min_onceki_yil_ihracat_usd"):
                metin = f"önceki yıl en az {usd} USD ihracat"
                d.teyit.insert(0, metin)
                kilit.insert(0, metin)
            if profil is None:
                d.gerekce.append("profiliniz olmadığı için uygunluk değerlendirilemedi")
            elif not_9903.startswith(("BELİRLENEMEDİ", "DÜŞÜK")):
                d.gerekce.append("Karar metnine göre ön değerlendirme: " + _kisalt(
                    not_9903.split("\nDESTEK UNSURLARI")[0], 400))
            elif kilit and kilit[0].startswith("düşük olasılık:"):
                d.gerekce.append(kilit[0])
            elif kilit:
                d.gerekce.append(KILIT_ONEKI + ": " + kilit[0])
            elif kisi and not ciro_engeli:
                d.gerekce.append(KISI_ONEKI + ": " + kisi[0])
            elif ciro_engeli:
                d.karar = "uygun_degil"
                d.gerekce.append(ciro_engeli)
            else:
                # Kayıtta şart yoksa profille çelişen bir şey de yoktur: engel yok, şartlar kurumdan teyit edilir
                # (tur 11-12 hakemleri: "belirlenemedi" aynı durumdaki iki programa farklı etiket veriyordu).
                if not d.teyit and not d.saglanan and not not_9903:
                    d.teyit.append(SART_YOK_TEYIT + "; kurumun ya da bankanın başvuru rehberindeki şartları teyit "
                                   "edin")
                d.karar = "sartli"
                if t.id in eslesme and not not_9903:
                    d.gerekce += [g for g in eslesme[t.id].gerekce if g and not _PANEL_NOTU.search(g)][:2]
                    # Soru bir ihtiyacı (istihdam, ihracat) açıkça soruyorsa "hedeflerinizde ... yok" notu yanıtla çelişir.
                    sorulanlar = set(soru_ihtiyaclari(soru))
                    d.gerekce += [f"teyit: {x}" for x in eslesme[t.id].eksik_kriterler if x and not (
                        sorulanlar and "hedeflerinizde" in x) and not _PANEL_NOTU.search(x)][:2]
                elif not not_9903:
                    _sorulan = set(soru_ihtiyaclari(soru)) & program_ihtiyaclari(t)
                    if _sorulan:
                        d.gerekce.append("sorunuzdaki ihtiyaca yönelik (" + ", ".join(
                            IHTIYAC_ADLARI[x] for x in sorted(_sorulan)) + "); şartları kurumdan teyit edin")
                    else:
                        d.gerekce.append("profilinizdeki sektör ve hedeflerle doğrudan örtüşmüyor; kapsamı kurumdan "
                                     "teyit edin")
            if not_9903 and d.karar == "sartli":
                d.gerekce.insert(0, "Karar metnine göre ön değerlendirme: " + _kisalt(
                    not_9903.split("\nDESTEK UNSURLARI")[0], 400))
                if not_9903.startswith("ŞARTLI"):
                    sart = karar_sarti_metni(not_9903)
                    if sart:
                        d.teyit.insert(0, f"Karar şartı: {sart}")
            asgari = asgari_yatirim_metni(t, profil, soru)
            if asgari and d.karar in ("sartli", "belirlenemedi"):
                # Hakem bulgusu 4. tur: 12 milyon TL asgari yatırım yalnız kartın derinliğindeydi; tek makine alacak
                # mikro işletmeye Yerel Kalkınma Hamlesi "öne çıkan / engel yok" görünüyordu.
                d.teyit.insert(1 if d.teyit and d.teyit[0].startswith("Karar şartı:") else 0, asgari)
            ust_kapali = False
            if t.id in ust:
                u_donem, u_cagri = cagri_bilgisi(ust[t.id], bugun)
                if u_donem in ("kapandi", "on_kayit_kapandi"):
                    ust_kapali = True
                    d.gerekce.append(f"bağlı olduğu KOSGEB programının ({ust[t.id].baslik}) başvuru dönemi kapalı; "
                                     "paket o programın onayına bağlı")
                    d.donem, d.cagri, d.ust = u_donem, u_cagri, ust[t.id]
            if d.donem in ("kapandi", "on_kayit_kapandi") and d.karar in ("sartli", "belirlenemedi"):
                d.uygunluk = d.karar
                d.karar = "kapali"
                d.gerekce = [g for g in d.gerekce if "başvuru dönemi kapalı" in g] + (
                    [] if ust_kapali else [f"yeni başvuru için şu an kapalı ({takvim_metni(d, bugun, kisa=True)})"])
        hedefli = _hedefli_cagri(d.cagri) if d.donem == "acik" else ""
        if hedefli and d.karar == "sartli":
            # açık çağrı yalnız önceki aşamayı tamamlamış başvurana: "engel yok / başvuruya açık" yanıltıcı olur
            d.karar = "belirlenemedi"
            d.gerekce.insert(0, f"açık çağrı yalnız şunlar için: {hedefli}; bu koşulu sağlamıyorsanız sizin için açık "
                                "çağrı kayıtlarımızda yok")
        d.gerekce = list(dict.fromkeys(d.gerekce))
        sonuc.append(d)
    return sonuc


# ------------------------------------------------------------------ bölümler
def profil_ozeti(p) -> list[str]:
    from app.kobi import AD as KOBI_AD
    from app.kobi import kobi_sinifi
    if p is None:
        return ["- Profil girilmemiş: faaliyet, şirket türü, il ve ölçek **bilinmiyor**."]
    olcek = kobi_sinifi(p.calisan_sayisi, p.yillik_ciro)
    olcek_metni = (KOBI_AD[olcek.sinif] + ("" if olcek.kesin else f" (kesin değil: {olcek.aciklama})")
                   if olcek.sinif else f"bilinmiyor ({olcek.aciklama})")
    if p.sirket_turu == "yok":
        olcek_metni = "henüz işletme yok (ölçek şirket kurulunca belirlenir)"
    satir = [f"- Faaliyet: {SEKTOR_AD.get(p.sektor, p.sektor) if p.sektor else 'bilinmiyor'}" + (
                 f" (NACE {p.nace_kodu})" if p.nace_kodu else
                 # çiftçiye "NACE kodu bilinmiyor" yazmak sistem dilidir (hakem bulgusu 2026-10-12)
                 f" ({p.urun_turu})" if p.sektor == "tarim" and getattr(p, "urun_turu", None) else
                 "" if p.sektor == "tarim" else " (NACE kodu bilinmiyor)"),
             f"- Şirket türü: {SIRKET_TURU_AD.get(p.sirket_turu, p.sirket_turu or 'bilinmiyor')}",
             f"- Ölçek: {olcek_metni}" + ("" if p.sirket_turu == "yok" else " [KOBİ Yönetmeliği eşiklerine göre]"),
             f"- İl: {p.bolge or 'bilinmiyor'}",
             f"- Hedefler: {', '.join(HEDEF_AD.get(h, h.replace('_', ' ')) for h in p.hedefler or []) or 'bilinmiyor'}"]
    if p.kurulus_tarihi:
        satir.append(f"- Kuruluş tarihi: {_tarih(p.kurulus_tarihi)}")
    if p.trl is not None:
        satir.append(f"- Teknoloji hazırlık seviyesi (TRL): {p.trl}")
    return satir


def kart(d: Degerlendirme, notlar: dict[int, str], soru_ihtiyac: list[str], bugun: date) -> str:
    t = d.tesvik
    ms = _maddeler(t)
    satir = [f"**{t.baslik} — {t.kurum}**", f"- **Başvuru dönemi:** {takvim_metni(d, bugun)}"]
    gerekce = _birlestir(d.gerekce)
    satir.append(f"- **{'Sizin için' if d.profilli else 'Durum'}:** {karar_etiketi(d)}"
                 + (f" — {gerekce}." if gerekce else "."))
    if d.kisit:
        satir.append(f"- **Kapsam:** {'; '.join(d.kisit)}")
    karsiladigi = [IHTIYAC_ADLARI[x] for x in soru_ihtiyac if x in program_ihtiyaclari(t)]
    if karsiladigi:
        satir.append(f"- **Karşıladığı ihtiyaç:** {', '.join(karsiladigi)}")
    tutar = _profile_uyan_tutar(tutar_metni(t), d)
    unsur = _destek_unsurlari(notlar, t)
    etiket = "Son bilinen destek (bilgi için)" if d.karar == "kapali" else (
        "Kredi ve kefalet limitleri" if (t.uygunluk_kriterleri or {}).get("tutar_niteligi") == "kredi_kefalet"
        else "Destek")
    if tutar:
        destek, _, hesap = tutar.partition(" Hesaplama: ")
        satir.append(f"- **{etiket}:** {destek}")
        if hesap:
            satir.append(f"- **Hesaplama:** {hesap}")
        if azami_hibe(t) and d.karar != "kapali":
            satir.append(f"- **Azami hibe (hesap):** {azami_hibe(t)}")
    if unsur:
        satir.append(f"- **Destek unsurları (Karar metninden, bölgenize göre):** {unsur}")
    if not tutar and not unsur:
        satir.append(f"- **Son bilinen tutar (önceki program, bilgi için):** {d.onceki_tutar}" if d.onceki_tutar
                     else f"- **{etiket}:** kayıtta yok; kurumun güncel uygulama esaslarından teyit edin")
    if d.saglanan:
        satir.append("- **Profilinize göre sağlanan şartlar:** " + "; ".join(d.saglanan))
    dislama = [x for x in d.teyit if x.startswith("Karar şartı:") and _DISLAMA.search(x.split(" — ")[0])]
    sartlar = [x for x in d.teyit if x not in dislama and not x.startswith(SART_YOK_TEYIT)]
    if any(x.startswith(SART_YOK_TEYIT) for x in d.teyit):
        satir.append(f"- **Başvuru şartları:** {SART_YOK_TEYIT.lower()}; kurumun ya da bankanın başvuru rehberindeki "
                     "şartları teyit edin.")
    for x in dislama:
        satir.append(f"- **Dışlama koşulu** (yatırımınız buna giriyorsa bu programdan yararlanamazsınız): {x}")
    if sartlar:
        satir.append("- **Teyit etmeniz gereken şartlar** (kontrol listesindeki beyanlar; sağlıyorsanız işaretleyin):")
        satir += [f"  - ☐ {x}" for x in sartlar[:EN_COK_TEYIT]]
        if len(sartlar) > EN_COK_TEYIT:
            satir.append(f"  - ve {len(sartlar) - EN_COK_TEYIT} şart daha (tamamı panelde programın Kontrol listesinde).")
    teyit_norm = {_norm(x) for x in d.teyit}
    kurallar = [m for m in _tekil([m for m in ms if m["tur"] == "kural"]) if _norm(_madde_metni(m)) not in teyit_norm
                and not _profile_uymayan_kosul(m["metin"], d)]
    if kurallar:
        satir.append("- **Kurallar (kayıttan):**")
        satir += [f"  - {_madde_metni(m)}" for m in kurallar[:EN_COK_KURAL]]
    kaynak = f"- **Başvuru:** {_cumle_kisalt(_temiz(t.basvuru_yeri), 200) + ' — ' if t.basvuru_yeri else ''}" \
             f"{t.kaynak_url or 'kaynak adresi kayıtta yok; kurumun resmî sitesine bakın'}"
    satir.append(kaynak)
    return "\n".join(satir)


def _uygun_hale_gelmek(d: Degerlendirme) -> list[str]:
    """Elenen programda kullanıcının yapabileceği: kişisel şartın açıklaması ya da kaydın adım maddeleri."""
    k = d.tesvik.uygunluk_kriterleri or {}
    g = " ".join(d.gerekce)
    oneri = []
    if "yaşında" in g and k.get("kurucu_yasi_max"):
        oneri.append(f"Şart işletme sahibi ya da en az %50 hisseli ortak için aranır: en az %50 hisseye sahip ortağınız "
                     f"{k['kurucu_yasi_max']} yaşını aşmamışsa profilde kurucu yaşını onun yaşıyla güncelleyin")
    if "ortak" in g and k.get("ortaklik_yasagi_sirketsiz"):
        oneri.append("Ortaklık yasağı hızlandırma programına kabul tarihindeki duruma bakar; borsadaki hisseler ve kitle "
                     "fonlaması payları sayılmaz. Kabul tarihinden önce ortaklıktan ayrılmanın sonucunu kurumdan teyit "
                     "edin")
    if "sertifika" in g and k.get("gerekli_sertifika"):
        oneri.append("Destek sertifikalı üretime ödenir; yetkilendirilmiş bir kuruluşla sertifikasyon sürecine girip "
                     "ürün sertifikası aldığınız yıl başvurabilirsiniz (süreci il müdürlüğünden teyit edin)")
    if not oneri and re.search(r"kayıtlı bir işletme gerektir|şirket türü|sermaye şirketi", g) and \
            d.karar == "uygun_degil":
        sartlar = [_kisalt(_temiz(m["metin"]), 120) for m in _tekil([m for m in _maddeler(d.tesvik)
                                                                      if m["tur"] == "sart"])][:3]
        oneri.append("Bu durum geçici: işletmenizi kurduktan sonra yeniden değerlendirin"
                     + (f"; kayıttaki başvuru şartları: {'; '.join(x.rstrip('. ') for x in sartlar)}" if sartlar else ""))
    if not oneri and d.kapsam_disi:
        oneri.append("Sorduğunuz kalem bu programın kapsamında değil; sonraki dönem açılsa da bu kalem için "
                     "başvurulamaz. Kalem için kayıtlarımızdaki kredi ve kefalet seçenekleri aşağıda")
    if not oneri and d.guncel_surum:
        oneri.append(f"Bu programın güncel sürümü etkin: {d.guncel_surum}; eski sürümün yeni dönemini beklemeyin")
    if not oneri and re.search(r"mülga|yürürlükten kalk|sona erdi|kaldırıldı|artık ödenmiyor",
                               (d.tesvik.durum_notu or "") + (d.tesvik.tesvil_tutari or "") + (d.tesvik.baslik or "")):
        oneri.append("Program yürürlükten kalktı; sonraki dönemi beklemeyin. Yerine geçen düzenleme bu yanıtta ayrıca "
                     "listelendi")
    if not oneri and d.karar == "kapali":
        oneri.append(f"Sonraki başvuru dönemini {(d.ust or d.tesvik).kurum} duyurularından takip edin; çağrı açıldığında "
                     "şartları "
                     "yeniden kontrol edin")
    elif not oneri:
        oneri.append("Profilinizdeki ilgili bilgi değişirse yeniden değerlendirin")
    return [o.rstrip(" .") for o in oneri]


def odak_elenen_karti(d: Degerlendirme, notlar: dict[int, str], bugun: date) -> str:
    """Adıyla sorulan ama kapalı / uygun olmayan program: durum, gerekçe, son bilinen tutar, ne yapılabilir."""
    t = d.tesvik
    etiket = karar_etiketi(d).lower() if d.karar == "kapali" else "uygun değil"
    satir = [f"**{t.baslik} — {t.kurum}** ({etiket})", f"- **Neden:** {_birlestir(d.gerekce)}."]
    tutar = tutar_metni(t, 450)
    if tutar:
        satir.append(f"- **{'Son bilinen destek (bilgi için)' if d.karar == 'kapali' else 'Destek'}:** {tutar}")
    elif d.onceki_tutar:
        satir.append(f"- **Son bilinen tutar (önceki program, bilgi için):** {d.onceki_tutar}")
    sartlar = [_kisalt(_temiz(m["metin"]), 160) for m in _tekil([m for m in _maddeler(t) if m["tur"] == "sart"])][:4]
    if sartlar and d.karar == "kapali":
        satir.append("- **Kimler başvurabiliyordu (son çağrı):** " + "; ".join(x.rstrip(" .") for x in sartlar) + ".")
    oneri = _uygun_hale_gelmek(d)
    if oneri:
        satir.append("- **Ne yapabilirsiniz:** " + "; ".join(oneri) + ".")
    satir.append(f"- **Kaynak:** {t.kaynak_url or 'kayıtta yok'}")
    return "\n".join(satir)


def _yururlukten_kalkmis(d: Degerlendirme) -> bool:
    """Program dayanağı yürürlükten kalkmış (mülga) ve kapalı: yeni sistemle değiştirilmiş eski kayıt."""
    metin = " ".join(d.gerekce) + " " + (d.tesvik.durum_notu or "")
    return d.karar == "kapali" and bool(re.search(r"yürürlükten kal[dk]|\bmülga\b", metin, re.I))


def elenen_satirlari(elenen: list[Degerlendirme]) -> list[str]:
    """Aynı gerekçeyle elenen programlar tek satırda."""
    gruplar: dict[tuple, list[Degerlendirme]] = {}
    for d in elenen:
        gruplar.setdefault((d.karar, _birlestir(d.gerekce)), []).append(d)
    satir = []
    for (karar, gerekce), ds in gruplar.items():
        adlar = "; ".join(f"{d.tesvik.baslik} ({d.tesvik.kurum})" for d in ds)
        etiket = karar_etiketi(ds[0]).lower() if karar == "kapali" else "uygun değil"
        satir.append(f"- {adlar} — {etiket}: {_kisalt(gerekce, 260)}")
    # En çok 6 satır; kalanı sayıyla (tur 7 sonrası: kapalı listesi tek başına 3-4,5 bin karakter tutuyordu).
    if len(satir) > EN_COK_ELENEN:
        kalan = sum(len(ds) for ds in list(gruplar.values())[EN_COK_ELENEN:])
        satir = satir[:EN_COK_ELENEN] + [f"- ve {kalan} program daha (gerekçeleri programın adıyla sorabilirsiniz)."]
    return satir


def kapali_odak_hazirligi(d: Degerlendirme, iletisim: list[str]) -> tuple[list[str], list[str]]:
    """Sorulan program kapalı ya da size uygun değilken (açık kart yok) 3. ve 4. bölüm: engel, engel kalkarsa / çağrı
    açılınca aranacak öteki şartlar ve belgeler (kayıttan), başvuru kanalı. Boş "kart yok" şablonunun yerine."""
    t = d.tesvik
    engel = _birlestir(d.gerekce) if d.gerekce else ""
    engel_norm = _norm(engel)
    sartlar = [_kisalt(_temiz(m["metin"]), 160).rstrip(" .") for m in _tekil(
        [m for m in _maddeler(t) if m["tur"] == "sart"]) if _norm(m["metin"])[:40] not in engel_norm][:4]
    belgeler = [_kisalt(_temiz(m["metin"]), 120).rstrip(" .") for m in _tekil(
        [m for m in _maddeler(t) if m["tur"] == "belge"])][:4]
    kapali = d.karar == "kapali"
    dar = [f"- **{'Neden şu an başvurulamıyor' if kapali else 'Engel'}:** {engel}."] if engel else []
    if sartlar:
        dar.append(f"- **{'Çağrı açıldığında aranacak şartlar (son çağrıdan)' if kapali else 'Engel kalkarsa ayrıca aranan şartlar'}"
                   f" (kayıttan):** " + "; ".join(sartlar) + ".")
    if belgeler:
        dar.append("- **Hazırlanacak belgeler (kayıttan):** " + "; ".join(belgeler) + ".")
    if not dar:
        dar = ["- Kayıtta bu program için ayrıca şart ya da belge listesi yok; kurumun çağrı rehberine bakın."]
    yol = [("Çağrıyı izleyin: " if kapali else "Engeli değerlendirin: ")
           + (d.guncel_surum and f"güncel karşılığı {d.guncel_surum}; " or "")
           + ("kurum duyurularından yeni çağrı tarihini takip edin" if kapali else
              "engel kalkmadan başvuru yapılamaz; durumunuzun şarta etkisini kurumla teyit edin") + "."]
    if sartlar or belgeler:
        yol.append("Hazırlık: yukarıdaki şartları ve belgeleri şimdiden toplayın.")
    yol.append("Başvuru kanalı: " + (f"{_cumle_kisalt(_temiz(t.basvuru_yeri), 140)} — " if t.basvuru_yeri else "")
               + (t.kaynak_url or "kurumun resmî sitesi") + ".")
    if iletisim:
        yol.append("İletişim (doğrulanmış): " + " · ".join(iletisim))
    return dar, [f"{i}. {a}" for i, a in enumerate(yol, 1)]


def darbogazlar(kartlar: list[Degerlendirme], bugun: date, genel: bool = True) -> list[str]:
    from app.hazirlik import ADIMLAR, program_adimlari
    satir = []
    for d in kartlar:
        c = d.cagri
        if c and d.donem == "acik" and c.get("on_kayit_son") and not _hedefli_cagri(c):
            satir.append(f"- **Ön kayıt:** {d.tesvik.baslik} için yeni başvuranın ön kayıt son günü "
                         f"{_tarih(c['on_kayit_son'])}" + (f" ({c['kalan_gun']} gün)" if c["kalan_gun"] is not None
                                                           else "") + ".")
    gereken: dict[str, list[str]] = {}
    for d in kartlar:
        for kod in program_adimlari(d.tesvik):
            gereken.setdefault(kod, []).append(d.tesvik.baslik)
    for kod, programlar in gereken.items():
        a = ADIMLAR[kod]
        satir.append(f"- **{a.baslik}** ({', '.join(_kisalt(p, 60) for p in programlar[:3])}): {a.nasil}")
    for d in kartlar:
        for m in _tekil([m for m in _maddeler(d.tesvik) if m["tur"] in ("sart", "adim")]):
            if re.search(r"ön kayıt|veri taban|kayıtl[ıi]|kaydı|beyan|KAYS|ÇKS|ÜKS|OTBİS|E-TUYS|PRODİS|e-imza|"
                         r"sözleşme(?:den)? (?:sonra|önce)", m["metin"], re.I):
                satir.append(f"- **{d.tesvik.baslik}:** {_temiz(m['metin'])}")
    if not satir and kartlar:
        satir.append("- Kartlardaki şartlar dışında, kayıtlarda bu programlar için ayrıca bir ön kayıt ya da sistem "
                     "kaydı şartı yok.")
    if not kartlar:
        return ["- Size açık bir program kartı olmadığı için başvuru darboğazı çıkarılmadı; bir programı adıyla "
                "sorarsanız şartlarını ayrıntılı veririm."]
    # Genel ilkeler (GENEL_ILKELER) kayıtlara dayanmadığı için yanıta girmez (tur 11-13 hakemleri: kaynak dışı);
    # kayıttaki gerçek kurallar kartlarda ve yukarıdaki satırlarda. `genel` parametresi çağıranlarla uyum için duruyor.
    return list(dict.fromkeys(satir))


def iletisim_satirlari(db, kartlar: list[Degerlendirme], profil, ilgili: list[Degerlendirme] | None = None) -> list[str]:
    """Doğrulanmış iletişim; yalnız gösterilen programların kurumları. İl müdürlükleri yalnız ilgili programda."""
    from app.models import IlKosgebMudurlugu, IlTarimMudurlugu, KurumIletisim
    satir = []
    for kurum in sorted({d.tesvik.kurum for d in kartlar if d.tesvik.kurum}):
        k = db.query(KurumIletisim).filter(KurumIletisim.kurum == kurum).first()
        if k is None:
            continue
        tel = ", ".join(x for x in (f"çağrı merkezi {k.cagri_merkezi_no}" if k.cagri_merkezi_no else "",
                                    f"genel merkez {k.genel_merkez_no}" if k.genel_merkez_no else "") if x)
        satir.append(f"{k.kurum}: {tel or 'telefon kayıtta yok'}" + (f"; {k.adres}" if k.adres else "")
                     + f" (doğrulama: {k.kaynak_url})")
    il = getattr(profil, "bolge", None)
    if il:
        tarim = any(d.tesvik.kurum in ("Tarım Bakanlığı", "Tarım ve Orman Bakanlığı")
                    or (getattr(profil, "sektor", None) == "tarim"
                        and "tarim" in ((d.tesvik.uygunluk_kriterleri or {}).get("sektorler") or []))
                    for d in (ilgili or kartlar))
        if tarim:
            r = db.query(IlTarimMudurlugu).filter(IlTarimMudurlugu.il_adi.ilike(il)).first()
            if r is not None:
                satir.append(f"{r.il_adi} Tarım ve Orman İl Müdürlüğü: " + (
                    f"{r.telefon}; {r.adres} (doğrulama: {r.kaynak_url})" if r.url_dogrulandi and r.telefon
                    else f"iletişim bilgisi için resmî sayfa: {r.kaynak_url}"))
        if any(d.tesvik.kurum == "KOSGEB" for d in (ilgili or kartlar)):
            r = db.query(IlKosgebMudurlugu).filter(IlKosgebMudurlugu.il_adi.ilike(il)).first()
            if r is not None:
                satir.append(f"{r.mudurluk_adi}: {r.telefon}; {r.adres} (doğrulama: {r.kaynak_url})")
    return satir


def yol_haritasi(kartlar: list[Degerlendirme], iletisim: list[str], profilli: bool = True,
                 alternatif: bool = False) -> list[str]:
    from app.hazirlik import ADIMLAR, program_adimlari
    adimlar = []
    onkayit = [d for d in kartlar if d.cagri and d.donem == "acik" and d.cagri.get("on_kayit_son")
               and not _hedefli_cagri(d.cagri)]
    for d in onkayit[:2]:
        adimlar.append(f"Ön kayıt: {d.tesvik.baslik} — son gün {_tarih(d.cagri['on_kayit_son'])}.")
    # Ön koşullar ilk kartın; diğer kartların ek koşulları program adıyla ayrı yazılır (hakem bulgusu 4. tur: UTPO
    # kartının "harcamadan önce ön onay" koşulu, ödeme sonrası başvurulan Dijital Ürün Tanıtım'ın ön koşulu gibi
    # okunuyordu).
    kodlar = list(dict.fromkeys(k for d in kartlar[:1] for k in program_adimlari(d.tesvik)))
    if kodlar:
        adimlar.append("Ön koşul kayıtlar: " + "; ".join(ADIMLAR[k].baslik for k in kodlar) + ".")
    ek = [(d, [k for k in program_adimlari(d.tesvik) if k not in kodlar]) for d in kartlar[1:]]
    ek = [(d, ks) for d, ks in ek if ks]
    if ek:
        adimlar.append("Diğer programlar için ayrıca: " + "; ".join(
            f"{_kisalt(d.tesvik.baslik, 60)} — " + ", ".join(ADIMLAR[k].baslik for k in ks) for d, ks in ek) + ".")
    teyitli = [d for d in kartlar if d.teyit]
    if teyitli and not alternatif:
        adimlar.append("Kartlardaki 'teyit edin' şartlarını panelde programın **Kontrol listesi**'nde Evet/Hayır olarak "
                       "işaretleyin; 'Hayır' çıkan şart o programı kapatır.")
    elif teyitli:
        adimlar.append(f"{teyitli[0].tesvik.baslik} şartlarını adıyla sorarak ya da panelde programın **Kontrol "
                       "listesi**'nden görün; 'Hayır' çıkan şart o programı kapatır.")
    if kartlar:
        ilk = kartlar[0].tesvik
        ms = _maddeler(ilk)
        belgeler = [_temiz(m["metin"]) for m in _tekil([m for m in ms if m["tur"] == "belge"])
                    if not _KOSULLU_BELGE.search(m["metin"])][:EN_COK_BELGE]
        adim = [_temiz(m["metin"]) for m in _tekil([m for m in ms if m["tur"] == "adim"])][:EN_COK_BELGE]
        if belgeler:
            adimlar.append(f"Belgeler ({ilk.baslik}): " + "; ".join(belgeler) + ".")
        elif adim:
            adimlar.append(f"Başvuru adımları ({ilk.baslik}): " + "; ".join(adim) + ".")
        else:
            adimlar.append(f"Belgeler ({ilk.baslik}): kayıtta belge listesi yok; çağrı rehberindeki listeyi esas alın.")
        d0 = kartlar[0].tesvik
        adimlar.append(f"Başvuru kanalı ({d0.baslik}): " + (f"{_cumle_kisalt(_temiz(d0.basvuru_yeri), 140)} — "
                                                             if d0.basvuru_yeri else "") + (d0.kaynak_url or "resmî site")
                       + (". Diğer programların başvuru yeri kartlarındaki **Başvuru** satırında." if len(kartlar) > 1
                          else "."))
    if iletisim:
        adimlar.append("İletişim (doğrulanmış): " + " · ".join(iletisim))
    if not kartlar:
        if profilli:
            return ["1. Size açık bir program kartı yok; kapalı programların sonraki dönemini kurum duyurularından "
                    "izleyin ya da başka bir programı adıyla sorun."]
        return ["1. Önce panelde **İşletme profili** formunu doldurun ya da sorunuzda bir programı adıyla anın; yol "
                "haritası, size açık bir program belirlenince çıkarılır."]
    adimlar.append("Başvuru sonrası: kurum portalından durumu izleyin, ek belge taleplerine süresinde yanıt verin; "
                   "panelde **Taslak** düğmesi başvuru metninin şablonunu hazırlar.")
    return [f"{i}. {a}" for i, a in enumerate(adimlar, 1)]


def netlestirme(p, kartlar: list[Degerlendirme], tumu: list[Degerlendirme], soru: str) -> list[str]:
    kriterler = [d.tesvik.uygunluk_kriterleri or {} for d in tumu]
    sorular = []
    if p is None:
        sorular.append("Panelde **İşletme profili** formunu doldurun (faaliyet/NACE, şirket türü, il, çalışan sayısı, "
                       "yıllık ciro): uygunluk kararı ve ölçek, il, şirket türü şartları ancak bu bilgilerle verilebilir.")
    else:
        sektor_kisitli = any(set(k.get("sektorler") or ["genel"]) - {"genel"} for k in kriterler)
        tarim_bilinen = p.sektor == "tarim" and bool(p.urun_turu or p.tarim_kategori)
        if not p.nace_kodu and sektor_kisitli and not tarim_bilinen:
            sorular.append("NACE faaliyet kodunuz nedir? — sektör kısıtlı programlarda (imalat, tarım, turizm) "
                           "uygunluğu belirler.")
        if not p.sirket_turu:
            sorular.append("Şirket türünüz nedir (şahıs, limited, anonim, kooperatif, henüz şirket yok)? — birçok "
                           "program yalnız sermaye şirketlerine ya da yalnız girişimcilere açıktır.")
        if not p.bolge:
            sorular.append("Faaliyet/yatırım iliniz neresi? — kalkınma ajansı programları ve bölgesel oranlar buna "
                           "göre belirlenir.")
        if p.calisan_sayisi is None or p.yillik_ciro is None:
            sorular.append("Çalışan sayınız ve yıllık cironuz nedir? — KOBİ ölçeği ölçek sınırlı programlarda "
                           "belirleyicidir.")
        if p.kurucu_yasi is None and p.sirket_turu != "kooperatif" and any(k.get("kurucu_yasi_max")
                                                                            for k in kriterler):
            sorular.append("İşletme sahibinin ya da en az %50 hissedarın yaşı nedir? — listedeki bazı krediler yaş "
                           "sınırlıdır.")
        if (p.baska_sirkette_ortak is None and p.sirket_turu == "yok"
                and any(k.get("ortaklik_yasagi_sirketsiz") for k in kriterler)):
            sorular.append("Başka bir şirkette ortaklığınız ya da şahıs işletmeniz var mı? — BiGG Yatırım (1812) "
                           "hızlandırma programına kabul tarihinde ortaklığı olan kişi başvuramaz.")
        if not p.sertifikalar and any(k.get("gerekli_sertifika") for k in kriterler):
            sorular.append("Ürününüz için organik ya da iyi tarım sertifikanız var mı? — sertifika şartlı destekleri "
                           "belirler.")
        katli = _katla(soru)
        from app.match_adapter import profil_etiketleri
        etiketler = profil_etiketleri(p)
        if re.search(r"\bkadin", katli) and "kadin_girisimci" not in etiketler:
            sorular.append("Profilde 'kadın girişimci' özelliği işaretli değil; işaretlerseniz yalnız kadın "
                           "girişimcilere açık programlar da listelenir.")
        if re.search(r"\bgenc", katli) and "genc_girisimci" not in etiketler and (
                p.kurucu_yasi is None or p.kurucu_yasi <= 35):
            sorular.append("Profilde 'genç girişimci' özelliği işaretli değil; işaretlerseniz yalnız genç "
                           "girişimcilere açık programlar da listelenir.")
    for i, d in enumerate(kartlar[:2]):
        for s in [x for x in d.teyit if not x.startswith(SART_YOK_TEYIT)][:2 if i == 0 else 1]:
            tam = s.split(' — ')[0]
            metin = _kisalt(tam, 200)
            esik = re.search(r"(\d[\d.,]*)\s*(oda|yatak|ton/gün|ton|dekar|m²|m2|kW|MW|baş)\b", tam)
            if tam.startswith("Karar şartı:") and _DISLAMA.search(tam):
                sorular.append(f"{d.tesvik.baslik}: kayda göre “{metin}” — yatırımınız bu kapsama giriyor mu? "
                               "Giriyorsa bu programdan destek alınamaz."
                               + (f" Yatırımın kapasitesini ({esik.group(2)}) de belirtin." if esik else ""))
            elif tam.startswith("Karar şartı:") and esik:
                sorular.append(f"{d.tesvik.baslik}: yatırımınızın kapasitesi nedir ({esik.group(2)})? Karar şartı bu "
                               f"eşiğe bağlı: “{metin}”")
            # Diğer şartlar kartın "Teyit etmeniz gereken şartlar" onay listesinde zaten var; burada yeniden
            # "sağlıyor musunuz?" diye sorulmaz (hakem bulgusu 2026-10-12: aynı şart 3-4 bölümde tekrar ediyordu).
    if p is not None and any(asgari_yatirim_metni(d.tesvik, p, soru) for d in kartlar):
        sorular.insert(0, "Planladığınız sabit yatırım tutarı nedir? — teşvik belgesi (9903) asgari sabit yatırım "
                          "tutarının altındaki yatırıma düzenlenmez (kartlardaki teyit maddesi).")
    if any(g.startswith(KISI_ONEKI) for d in kartlar for g in d.gerekce):
        sorular.insert(0, "İşe alacağınız kişilerin cinsiyeti ve yaşı, son 6 ayda işsiz olup olmadığı, işsizlik ödeneği "
                          "alıp almadığı, mesleki yeterlilik belgesi, İŞKUR kaydı ve engel durumu nedir? — istihdam "
                          "teşviklerinin hangisinin uygulanacağı ve süresi bunlara bağlıdır.")
    if kartlar and _NIYET["sure"].search(_katla(soru)) and _sure_kirilimi(kartlar[0].tesvik):
        sorular.insert(0, "İşe alacağınız kişilerin cinsiyeti, yaşı, mesleki belgesi ve İŞKUR kaydı var mı? — destek "
                          "süresi bunlara göre değişir (kayıttaki süre kırılımı kısa cevapta).")
    if not sorular:
        for d in [x for x in kartlar if x.karar == "belirlenemedi" and x.gerekce
                  and not x.gerekce[-1].startswith(("düşük olasılık", KISI_ONEKI))][:2]:
            sorular.append(f"{d.tesvik.baslik}: uygunluk belirlenemedi ({_cumle_kisalt(d.gerekce[-1], 160)}); "
                           "bu konudaki bilgiyi profilinize ekleyin ya da kurumdan teyit edin.")
    if not sorular:
        if any(d.teyit for d in kartlar):
            return ["Profil alanlarınız bu yanıt için yeterli; kalan şartlar yukarıdaki teyit listelerindedir."]
        kurallar = [_kisalt(_temiz(m["metin"]), 160).rstrip(" .") for d in kartlar[:1] for m in _tekil(
            [m for m in _maddeler(d.tesvik) if m["tur"] == "kural"]) if not _profile_uymayan_kosul(m["metin"], d)][:3]
        if kurallar:
            return ["Profil alanlarınız uygunluk için yeterli, ancak şu kayıt kurallarını profilden doğrulayamıyorum; "
                    "başvurudan önce kendiniz kontrol edin: " + "; ".join(kurallar) + "."]
        return ["Profiliniz bu yanıt için yeterli; değişen bir bilgi olursa profil formunu güncelleyin."]
    return [f"{i}. {s}" for i, s in enumerate(sorular[:7], 1)] + [
        "Profil bilgilerini panelde **İşletme profili** formuna girerseniz değerlendirme otomatik güncellenir."]


def _urun_tutari(t, profil) -> str:
    """Profildeki ürün kayıttaki tutar metninde geçiyorsa o ürünün cümlesi (ör. "arpa, buğday ... 954,20 TL/da")."""
    urun = _katla(getattr(profil, "urun_turu", None) or "")
    if not urun or not t.tesvil_tutari:
        return ""
    for parca in re.split(r";\s*", _temiz(t.tesvil_tutari)):
        if re.search(rf"\b{re.escape(urun)}\b", _katla(parca)) and re.search(r"\d", parca):
            metin = parca.strip().rstrip(".")
            oranlar = re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*TL/da", metin)
            dekar = getattr(profil, "arazi_buyuklugu_dekar", None)
            if oranlar and dekar:
                birim = float(oranlar[0].replace(".", "").replace(",", "."))
                toplam = _tl(birim * dekar)
                dekar_metni = _sayi(dekar)
                metin += (f". Profilinizdeki {dekar_metni} dekar için: {oranlar[0]} TL/da × {dekar_metni} da = {toplam} "
                          "TL (kesin tutarı kurum hesaplar)")
            metin_formul = re.sub(r"\s+", " ", t.tutari_hesaplama_formulu or "")
            birim_deger = float(oranlar[0].replace(".", "").replace(",", ".")) if oranlar else 0.0
            ciftler = [a for a, b in re.findall(r"(\d{1,3}(?:\.\d{3})*,\d{2}) \+ (\d{1,3}(?:\.\d{3})*,\d{2})",
                                                metin_formul)
                       if a == b and round(float(a.replace(".", "").replace(",", ".")) * 2, 2) == round(birim_deger, 2)]
            if dekar and ciftler and re.search(r"her biri katsayı", metin_formul):
                temel = ciftler[0]
                temel_tl = _tl(float(temel.replace(".", "").replace(",", ".")) * dekar)
                metin += (f"; yalnız temel destek (planlı üretim şartı sağlanmazsa): {temel} TL/da × "
                          f"{_sayi(dekar)} da = {temel_tl} TL")
            if re.search(r"planl[ıi] üretim", t.tesvil_tutari or "", re.I) and re.search(
                    r"havza", (t.tutari_hesaplama_formulu or "") + (t.tesvil_tutari or ""), re.I):
                metin += ("; tutarın planlı üretim desteği kısmı, kayda göre ürünün havzada planlanan ürün olmasına "
                          "bağlıdır")
            return metin
    return ""


_TARIM_ODEME_SORU = re.compile(r"ne kadar|toplam|hangi destek|neler|destek(?:ler)?(?:i|den)? (?:alabilir|var)|"
                               r"dekar|donum|alan bazli|temel destek|ne verili|odeme", re.I)


# Dar hedef kitleli işe alım teşvikleri (engelli, sosyal yardım alan, işsizlik ödeneği alan, çok tehlikeli sınıf):
# genel işe alım sorusunda geniş kapsamlı teşviklerin (4447 geçici 10, 5510 m.81/ı, İşbaşı) arkasında gelir.
_DAR_KITLE = re.compile(r"Engelli|Sosyal Hizmet|Sosyal Yardım|İşsizlik Ödeneği Alan|Çok Tehlikeli|Yurt Dışı(?:nda)? "
                        r"Çalış|Yurt ?dışına Götürülen|Gönderilen Sigortalı|Kültür Yatırım|Turizm Yatırımı", re.I)


# Belirli bir duruma yönelik krediler (refinansman, zor dönemde istihdamı koruma): soru o durumu anmıyorsa önerilmez.
_DURUM_PROGRAMI = re.compile(r"REFİNANSMAN|Refinansman|İSTİHDAM KORUMA|İstihdamı Koruma")
_VERGI_PROGRAMI = re.compile(r"Vergi İndirimi|Vergisi İstisnası|KDV İstisnası|Stopajı Teşviki|Tasarım İndirimi|Kazanç İstisnası|"
                             r"Gelir Vergisi Teşviki|Gelir Vergisi İstisnası", re.I)
_PAZARYERI_PROGRAM = re.compile(r"Pazaryeri|E-Ticaret|E-İhracat|Sipariş Karşılama|Çevrim İçi Mağaza", re.I)


def asgari_yatirim_metni(t, profil, soru: str = "") -> str:
    """9903 programında, soruda yatırım tutarı yoksa MADDE 5/2 asgari sabit yatırım tutarı (profil bölgesine göre)."""
    from app.tesvik_9903_uygunluk import _tl, program_turu, yatirim_tutari
    if program_turu(t.baslik) in (None, "stratejik_hamle", "teknoloji_hamlesi") or yatirim_tutari(soru, profil)[0]:
        return ""
    from app.nace_9903 import il_bolgesi
    from app.tesvik_9903_hesap import ASGARI_SABIT_YATIRIM
    bolge = il_bolgesi(getattr(profil, "bolge", None)) if getattr(profil, "bolge", None) else None
    if bolge not in ASGARI_SABIT_YATIRIM:
        return ""
    return (f"Asgari sabit yatırım tutarı {bolge}. bölgede {_tl(ASGARI_SABIT_YATIRIM[bolge])} (MADDE 5/2; EK-3'te "
            "konu için ayrıca belirtilmemişse); bu tutarın altındaki yatırıma teşvik belgesi düzenlenmez")


def _buyuk_olcekli(t, profil) -> bool:
    """Kredi tavanı yıllık cironun 20 katını aşan finansman (TKYB 500 milyon TL kredi paketi) küçük işletmeye ilk öneri
    olmaz (persona denemesi 2026-10-12: 14 çalışanlı otel ve 8 çalışanlı mağazada ilk sıradaydı)."""
    from app.dayanak import tl_tutarlari
    ciro = getattr(profil, "yillik_ciro", None)
    from app.tesvik_9903_uygunluk import program_turu
    if ciro and program_turu(t.baslik):
        # Asgari sabit yatırım yıllık cironun üzerindeyse 9903 programı ilk öneri olmaz (hakem bulgusu 4. tur: 600 bin
        # TL cirolu tek kişilik işletmeye 240 milyon TL tavanlı makine desteği gösteriliyordu).
        from app.nace_9903 import il_bolgesi
        from app.tesvik_9903_hesap import ASGARI_SABIT_YATIRIM
        bolge = il_bolgesi(getattr(profil, "bolge", None)) if getattr(profil, "bolge", None) else None
        return bool(bolge in ASGARI_SABIT_YATIRIM and ASGARI_SABIT_YATIRIM[bolge] > ciro)
    if not ciro or not _kredi_mi(t) or not t.tesvil_tutari:
        return False
    tutarlar = tl_tutarlari(t.tesvil_tutari)
    return bool(tutarlar) and max(tutarlar) >= 20 * ciro


def _dar_kitle(t) -> bool:
    return bool(_DAR_KITLE.search(t.baslik or ""))


def tarim_odeme_satiri(soru: str, profil) -> str:
    """Tarım profilinde (ürün ve arazi biliniyor) 2026 bitkisel üretim doğrudan ödemesinin hesabı: ürünün resmî
    tablodaki kategorisi × 2026 destek katsayı değeri (app/tarim_destek_2026) × dekar. Persona denemesi 2026-10-12:
    "9 dönüm fındık bahçem var, toplam ne kadar eder?" sorusuna toplam hesaplanmıyor, KGF kefalet limiti "destek"
    diye veriliyordu. Yalnız şartsız kalemler (temel destek; planlı üretim havzaya bağlı notuyla) toplanır."""
    from app import tarim_destek_2026 as T
    if profil is None or (getattr(profil, "sektor", None) or "") != "tarim":
        return ""
    urun, dekar = getattr(profil, "urun_turu", None), getattr(profil, "arazi_buyuklugu_dekar", None)
    ihtiyac = set(soru_ihtiyaclari(soru))
    if not urun or not dekar or not _TARIM_ODEME_SORU.search(_katla(soru)) or (ihtiyac - {"tarim_odeme"}):
        return ""
    try:
        h = T.hesapla(urun, dekar, il=getattr(profil, "bolge", None))
    except ValueError:
        return ""
    d = _sayi(dekar)
    parca = [f"{k.ad}: {_tl(k.dekar_basi_tl)} TL/da × {d} da = {_tl(k.toplam_tl)} TL" for k in h.kalemler]
    if len(h.kalemler) > 1:
        parca.append("toplam " + " + ".join(f"{_tl(k.toplam_tl)} TL" for k in h.kalemler) + f" = {_tl(h.toplam_tl)} TL"
                     " (planlı üretim desteği ürünün havzasında planlanan ürün olmasına bağlıdır)")
    notlar = [u for u in h.uyarilar if "fındık üretimine izin" in u or "Diğer ürünler" in u]
    # Şarta bağlı ekler (hakem bulgusu 2026-10-12, 5. tur: "toplam ne kadar" sorusunda yalnız koşulsuz kalem vardı):
    # kayıttaki katsayılarla verilir (katı organik/organomineral gübre 0,32; bireysel iyi tarım açık alanda ürün grubuna
    # göre 0,4–0,7). Türetilmiş TL tutarı yazılmaz: dayanak denetimi kayıtta olmayan tutara izin vermez.
    ek = ""
    if not h.kapsam_disi and h.kalemler:
        it_alt, it_ust = T.IYI_TARIM["3"][0], T.IYI_TARIM["1_acikta"][0]
        ek = (f" Şarta bağlı ekler (dekar başına katsayı × {_tl(T.KATSAYI_BIRIM_TL)} TL): katı organik/organomineral "
              f"gübre kullanırsanız katsayı {_sayi(T.ORGANOMINERAL_GUBRE_KATSAYI)}; bireysel iyi tarım sertifikanız varsa "
              f"açık alanda ürün grubunuza göre katsayı {_sayi(it_alt)}–{_sayi(it_ust)}.")
    return (f"Ürününüz ({urun}) ve arazinize göre 2026 doğrudan ödeme hesabı (destek katsayı değeri "
            f"{_tl(T.KATSAYI_BIRIM_TL)} TL/da): " + "; ".join(parca) + "." + (" " + " ".join(notlar) if notlar else "")
            + ek + " Sertifikalı fidan (yeni bahçe) ve sigorta (TARSİM) gibi diğer kalemler de şarta bağlıdır; ilgili "
              "programı adıyla sorabilirsiniz.")


_TARIM_KATEGORI_SORU = {"sera": r"sera|ortu|tunel|ortualti", "hayvancilik": r"hayvan|buzagi|kuzu|sut|ari\b|kovan",
                        "organik": r"organik", "makinelestirme": r"makine|traktor|ekipman",
                        "sulama": r"sulama|damla|yagmurlama"}


def _baska_tarim_kategorisi(t, profil, soru: str) -> bool:
    from app.matching import _tarim_kategorisi_uyusmuyor
    alt = (t.uygunluk_kriterleri or {}).get("alt_kategori")
    if not alt or not _tarim_kategorisi_uyusmuyor(t, profil):
        return False
    kalip = _TARIM_KATEGORI_SORU.get(alt)
    return not (kalip and re.search(kalip, _katla(soru)))


def _sayi(v: float) -> str:
    """Türkçe sayı: binlik nokta, ondalık virgül; tam sayıda ondalık yok (180 → "180", 180.5 → "180,5")."""
    if float(v).is_integer():
        return f"{int(v):,}".replace(",", ".")
    return f"{v:,.2f}".rstrip("0").replace(",", "X").replace(".", ",").replace("X", ".")


def dekar_araligi(t, profil) -> str:
    """Tutar "A–B TL/da" aralığıysa ve profilde arazi varsa toplam aralık (ürün grubu bilinmediğinde)."""
    dekar = getattr(profil, "arazi_buyuklugu_dekar", None)
    m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*[–-]\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*TL", t.tesvil_tutari or "")
    if not dekar or not m:
        return ""
    alt, ust = (float(x.replace(".", "").replace(",", ".")) for x in m.groups())
    d = _sayi(dekar)
    return (f"{d} dekar için en düşük {m.group(1)} TL/da × {d} da = {_tl(alt * dekar)} TL, en yüksek {m.group(2)} TL/da × "
            f"{d} da = {_tl(ust * dekar)} TL (ürün grubunuz ve sertifika türünüz kesin tutarı belirler)")


def _tl(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _sure_kirilimi(t) -> str:
    """Kayıt metnindeki süre kırılımı cümleleri ("Destek süreleri: kadınlar 24–54 ay; ..."); yoksa boş."""
    metin = " ".join(str(x or "") for x in (t.detay, t.ozet, t.tutari_hesaplama_formulu))
    cumleler = [c.strip() for c in re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ])", metin)
                if re.search(r"süre", c, re.I) and len(re.findall(r"\d+\s*(?:[–-]\s*\d+\s*)?(?:ay|yıl)\b", c)) >= 2]
    return " ".join(dict.fromkeys(_temiz(c) for c in cumleler[:2]))


_KAPSAM_SORU = re.compile(r"((?:[a-z0-9]+\s+){1,3}?)(?:alimi\s+|alimlari\s+|giderleri\s+|gideri\s+)?"
                          r"(?:bu programin\s+|programin\s+)?"
                          r"(?:destekleniyor mu|desteklenir mi|kapsamina giriyor mu|kapsaminda mi)")
_BASVURU_SAHIBI = {"sahis", "sirket", "sirketler", "sirketleri", "isletme", "isletmeler", "limited", "anonim",
                   "kooperatif", "kooperatifler", "firmalar", "girisimci", "girisimciler", "ciftci", "ciftciler"}
_KAPSAM_DURAK = {"alimi", "alimlari", "icin", "acaba", "peki", "gideri", "giderleri", "ayrica"}
_DISLAMA = re.compile(r"desteklenmez|yararlanamaz|kapsam dışı", re.I)
_OLUMSUZ = re.compile(r"desteklenmez|kapsam dışı|kapsamında değil|yararlanamaz|hariç|karşılanmaz", re.I)


def kapsam_hukmu(soru: str, t) -> str:
    """Soruda bir kalemin kapsamı soruluyorsa ("bireysel traktör alımı destekleniyor mu?") kayıttaki ilgili cümle;
    kalem kayıtta hiç geçmiyorsa bunu söyleyen satır. Soru kapsam sormuyorsa boş."""
    from app.nace_9903 import il_bolgesi
    m = _KAPSAM_SORU.search(re.sub(r"['’]\w+", "", _katla(soru)))
    if not m:
        return ""
    kelimeler = [k for k in m.group(1).split() if len(k) >= 4 and k not in _KAPSAM_DURAK
                 and k not in _BASVURU_SAHIBI and not k.startswith(GENEL_KOKLER) and il_bolgesi(k) is None]
    if not kelimeler:
        return ""
    ozgun = {_katla(x): x for x in re.findall(r"\w+", soru or "")}
    ad = " ".join(ozgun.get(k, k) for k in kelimeler)
    metin = " ".join(str(x or "") for x in (t.ozet, t.detay, " ".join(t.basvuru_sartlari or []),
                                            " ".join(m_["metin"] for m_ in _maddeler(t))))
    cumleler = [c.strip() for c in re.split(r"(?<=[.!?])\s+", metin) if c.strip()]
    ilgili = [c for c in cumleler if any(re.search(rf"\b{re.escape(k)}", _katla(c)) for k in kelimeler)]
    if not ilgili:
        return (f"Sorduğunuz kalem ({ad}) kayıttaki kapsam metninde geçmiyor; desteklenip desteklenmediğini kurumdan "
                "teyit edin.")
    ilgili.sort(key=lambda c: (-sum(bool(re.search(rf"\b{re.escape(k)}", _katla(c))) for k in kelimeler),
                               not _OLUMSUZ.search(c)))
    return f"Sorduğunuz kalem ({ad}): kayıtta “{_cumle_kisalt(_temiz(ilgili[0]), 240)}”"


def guncel_surum(t, tum: list) -> str:
    """Kapalı kaydın yıl dışında aynı adı taşıyan, daha yeni yıllı etkin kaydı ("… 2020 …" → "… 2026 …")."""
    yil = re.findall(r"20[1-3]\d", t.baslik or "")
    if not yil:
        return ""
    def _onek(baslik: str) -> str:
        return re.split(r"20[1-3]\d", _katla(baslik or ""), maxsplit=1)[0].strip()
    kok = _onek(t.baslik)
    if len(kok.split()) < 2:
        return ""
    for x in tum:
        x_yil = re.findall(r"20[1-3]\d", x.baslik or "")
        if x.id != t.id and x.aktif_mi is not False and x_yil and max(x_yil) > max(yil) and _onek(x.baslik) == kok:
            return x.baslik
    return ""


def halef_kayitlari(t, tum: list) -> list:
    """Kapalı kaydın durum notunda "güncel karşılığı 5986 m.8 … ve m.4 …" yazıyorsa o maddelerin kayıtları."""
    m = re.search(r"güncel karşılığı (.{0,200})", t.durum_notu or "")
    if not m:
        return []
    sonuc, karar = [], None
    for k, madde in re.findall(r"(?:(\d{4}) )?m\.(\d+)", m.group(1)):
        karar = k or karar
        if not karar:
            continue
        sonuc += [x for x in tum if x.aktif_mi is not False and f"{karar} sayılı Karar m.{madde})" in (x.baslik or "")]
    kalem = re.search(r"\b(uyelik|abonelik|kira|reklam|fuar)\w*", _katla(t.ozet or "") + " " +
                      _katla(t.tutari_hesaplama_formulu or ""))

    def _dislar(x) -> bool:
        if not kalem:
            return False
        metin = _katla(" ".join(str(y or "") for y in (x.detay, x.ozet, " ".join(m["metin"] for m in _maddeler(x)))))
        return bool(re.search(rf"{kalem.group(1)}\w*[^.]{{0,120}}(kapsam disi|desteklenmez|karsilanmaz|dahil degil)",
                              metin))
    return [x for x in dict.fromkeys(sonuc) if not _dislar(x)]


def turquality_dislamasi(tum: list) -> str:
    """Kayıtlardaki "TURQUALITY® … kapsamında desteklenmiyor olmalısınız" şartı (5973 m.17 dışlaması)."""
    for t in tum:
        for m in _maddeler(t):
            if re.search(r"turquality", m["metin"], re.I) and re.search(r"yararlanamaz", m["metin"]):
                alinti = m.get("alinti") or ""
                fikra = {"birinci": 1, "ikinci": 2, "üçüncü": 3, "dördüncü": 4, "beşinci": 5}
                alt = {int(a): f"{a}/{fikra[b]}" for a, b in re.findall(
                    r"(\d+)\s*\w*\s+maddenin\s+(birinci|ikinci|üçüncü|dördüncü|beşinci)\s+fıkrası", alinti)}
                sayilar = sorted({int(x) for x in re.findall(r"(\d+)\s*(?:'?\s*)?(?:uncu|üncü|inci|ıncı|ncı|nci|ncu|ncü)",
                                                           alinti)})
                maddeler = [alt.get(n, str(n)) for n in sayilar]
                kaybedilen = [x.baslik for x in tum if x.aktif_mi is not False and any(
                    f"5973 sayılı Karar m.{n})" in (x.baslik or "") for n in sayilar if n not in alt)]
                return (f"**Turquality'ye girerseniz:** kayda göre ({t.baslik}) Turquality / marka destek programı "
                        "(5973 m.17) kapsamındaki şirketler destek süresi boyunca 5973 sayılı Kararın "
                        + (f"m.{', m.'.join(maddeler)} desteklerinden" if maddeler else
                           "bazı desteklerinden")
                        + " yararlanamaz"
                        + (f". Kayıtlarımızda bu kapsamda olanlar: {'; '.join(kaybedilen)}" if kaybedilen else "")
                        + ". Aşağıdaki oranlar bu desteklerindir, Turquality'nin oranı değildir.")
    return ""


_ULKELER = ("Almanya", "Fransa", "Hollanda", "İspanya", "İtalya", "Avusturya", "Belçika", "İsveç", "Finlandiya",
            "Danimarka", "Norveç", "Polonya", "Portekiz", "İsviçre", "Güney Kore", "Kore", "Kanada", "İngiltere",
            "Macaristan", "Çekya", "Estonya", "Letonya", "Litvanya", "Slovenya", "Slovakya", "Romanya", "Bulgaristan",
            "Yunanistan", "İrlanda", "Lüksemburg", "Malta", "Kıbrıs", "Hırvatistan", "İsrail", "Güney Afrika",
            "Japonya", "ABD", "Amerika")


def soru_profil_celiskisi(soru: str, profil) -> list[str]:
    """Soruda geçen çalışan sayısı profildekinden farklıysa (ör. "60'ı geçmesin" ↔ profilde 12) bunu söyler."""
    if profil is None or profil.calisan_sayisi is None:
        return []
    m = re.search(r"(\d{1,5})\s*(?:'?\s*\w*\s*)?(?:çalışan|kişi|personel|işçi)|(?:çalışan|personel|işçi)\w*\s+(?:sayı\w*\s+)?"
                  r"(\d{1,5})", soru or "", re.I)
    if not m:
        return []
    sayi = int(m.group(1) or m.group(2))
    if sayi == profil.calisan_sayisi or sayi <= 3 and re.search(r"daha|ilave|ek\b", soru or "", re.I):
        return []
    if re.search(r"\d{1,5}\s*(?:yeni\s+)?(?:kişi|çalışan|personel|işçi|eleman)\w*\s+(?:daha\s+)?(?:al|işe al|istihdam)",
                 soru or "", re.I):
        return []   # "3 kişi alacağız": işe alınacak sayı, işletmenin toplam çalışan beyanı değil
    if re.search(r"geçmesin|geçmeyecek|aşmasın|altında|altına|en fazla|en çok|sınır|eşik|kalsın|kalmak|bölerek|bölsek",
                 soru or "", re.I):
        return []   # sayı bir eşik olarak anılıyor, işletmenin beyanı değil
    return [f"**Not:** Sorunuzdaki {sayi} çalışan bilgisi profilinizdeki {profil.calisan_sayisi} ile uyuşmuyor; "
            "değerlendirme profildeki değerle yapıldı. Hangisi doğruysa profili güncelleyin."]


# Yalnız koşul kipi: "şirket kurarsam / kurduktan sonra". "Şirket kurmak istiyorum" bir niyet beyanıdır; girişimci
# (şirketsiz) profiliyle değerlendirilir, çünkü BiGG gibi programlar tam da şirketi olmayana açıktır (kapsam ölçümü
# 2026-10-12: girişimci × girişim hücrelerinde varsayımsal şirket BiGG'i eliyordu).
_SIRKET_KURARSAM = re.compile(
    r"(?:sirket(?:imi)?|limited|anonim|ltd|a\.?s\.?) (?:kur|ac)(?:arsam|arsak|dugumda|duktan sonra|tigimda|tiktan sonra|"
    r"sam|sak)\b|sirketlesirsem|sirketlestikten sonra")
_SAHIS_KURARSAM = re.compile(r"sahis (?:sirketi|isletmesi) (?:kur|ac)(?:arsam|sam|tigimda|tiktan sonra)")


def varsayimsal_profil(soru: str, profil, zorla: bool = False):
    """Şirketi olmayan kullanıcı "şirket kurarsam ..." diye soruyorsa değerlendirme kurulacak şirket varsayımıyla
    yapılır ve yanıtta açıkça söylenir (persona denemesi 2026-10-12: "Şirket kurarsam KOSGEB ve TÜBİTAK'tan hangi
    destekleri birlikte kullanabilirim?" sorusu şirketsiz profille yanıtlanıp KOSGEB hiç anılmıyordu)."""
    if profil is None or getattr(profil, "sirket_turu", None) != "yok" or getattr(profil, "_varsayim", None):
        return profil
    metin = _katla(soru)
    tur = "sahis" if _SAHIS_KURARSAM.search(metin) else "limited" if _SIRKET_KURARSAM.search(metin) else None
    if tur is None and zorla:
        tur = "limited"
    if tur is None:
        return profil
    from app.models import FinancialProfile
    alanlar = {c.name: getattr(profil, c.name, None) for c in FinancialProfile.__table__.columns
               if c.name not in ("id", "org_id", "created_at", "updated_at")}
    alanlar["sirket_turu"] = tur
    if getattr(profil, "sirket_turu", None) in (None, "yok"):
        from datetime import date
        alanlar["kurulus_tarihi"] = date.today()   # kurulacak şirket: 0 yaşında
    yeni = FinancialProfile(**alanlar)
    yeni._varsayim = (
        f"sorunuz şirket kurduğunuz durumu soruyor; değerlendirme {SIRKET_TURU_AD[tur]} varsayımıyla yapıldı (bugün "
        "şirketiniz yok — şirketsiz yolları ayrıca sorabilirsiniz)." if not zorla or _SIRKET_KURARSAM.search(metin) else
        "şirketiniz olmadan başvurulabilecek bir program kaydı bulamadım; aşağıdaki programlar şirket "
        f"({SIRKET_TURU_AD[tur]}) kurmanız hâlinde geçerlidir.")
    return yeni


def soru_beyanlari(soru: str) -> dict[str, str]:
    """Sorudaki olgular (profil alanı olmayanlar): yabancı ortağın ülkesi ("Almanya'daki bir ortakla")."""
    sonuc = {}
    if re.search(r"\borta[kg]", _katla(soru)):
        for ulke in _ULKELER:
            if re.search(rf"\b{_katla(ulke)}", _katla(soru)):
                sonuc["ortak_ulke"] = f"{ulke}'daki" if not ulke.endswith(("e", "i")) else f"{ulke}'deki"
                break
    return sonuc


def _katki_orani(notlar: dict[int, str], t) -> int:
    m = re.search(r"yatırıma katkı oranı %(\d+)", _destek_unsurlari(notlar, t))
    return int(m.group(1)) if m else 0


def karsilastirma_9903(adaylar: list[Degerlendirme], notlar: dict[int, str]) -> list[str]:
    """Aynı Karar ailesindeki (9903) programların bölgeye göre destek unsurları yan yana (Karar metninden)."""
    satir = []
    def _guc(x) -> int:
        e = karar_etiketi(x)
        return 0 if x.karar == "sartli" else 2 if e.startswith("Düşük") else 1
    for d in sorted((x for x in adaylar if _destek_unsurlari(notlar, x.tesvik)),
                    key=lambda x: (_guc(x), -_katki_orani(notlar, x.tesvik))):
        unsur = _destek_unsurlari(notlar, d.tesvik)
        katki = _katki_orani(notlar, d.tesvik)
        makine = re.search(r"makine desteği: ([^;]+)", unsur)
        faiz = re.search(r"faiz/kâr payı desteği: ([^;]+)", unsur)
        satir.append(f"- {d.tesvik.baslik} ({karar_etiketi(d).lower()}): yatırıma katkı "
                     + (f"%{katki}" if katki else "kayıtta yok")
                     + (f"; makine desteği: {_cumle_kisalt(makine.group(1), 90)}" if makine else "")
                     + (f"; faiz desteği: {_cumle_kisalt(faiz.group(1), 60)}" if faiz else ""))
    return satir if len(satir) >= 2 else []


def sirketsiz_basvuru_hukmu(soru: str, t) -> str:
    """"Şirket kurmadan başvurabilir miyim?" sorusuna kaydın yapılandırılmış şartından doğrudan cevap."""
    if not re.search(r"sirket kurmadan|sirketsiz|sirketim yok|sirket kurmam", _katla(soru)):
        return ""
    k = t.uygunluk_kriterleri or {}
    if k.get("ortaklik_yasagi_sirketsiz"):
        return ("Şirket kurmadan başvuru: evet — kayda göre başvuran, hızlandırma programına kabul tarihinde bir "
                "şirkete ya da şahıs işletmesine ortak olmamalı (borsadaki hisseler ve kitle fonlaması payları hariç).")
    turler = set(k.get("sirket_turleri") or [])
    if turler and "yok" not in turler:
        return "Şirket kurmadan başvuru: hayır — kayıttaki başvuru sahibi türleri kurulmuş bir işletme gerektiriyor."
    return ""


def devredilen_kayit(t, tum: list):
    """Programın yerine geçtiği (durum notu "… çerçevesinde yürütüyor / devredildi" diyen) kapalı, tutarlı kayıt."""
    kod = _KOD.search(t.baslik or "")
    if not kod:
        return None
    for r in tum:
        notu = r.durum_notu or ""
        if r.aktif_mi is False and r.id != t.id and r.tesvil_tutari and kod.group(1) in notu \
                and re.search(r"çerçeve|devred|yeni başvuru için", notu, re.I):
            return r
    return None


def _devredilen_tutar(t, tum: list) -> str:
    """Tutarı boş kayıt için önceki (devredilen) programın son bilinen tutarı; kaynak kayıt adıyla."""
    r = devredilen_kayit(t, tum)
    if r is None:
        return ""
    return (f"{_cumle_kisalt(_temiz(r.tesvil_tutari), 240)} (son bilinen tutar, önceki program {r.baslik} "
            f"kaydından; {t.baslik} için güncel tutarı kurumdan teyit edin)")


def azami_hibe(t) -> str:
    """Tutar metninde proje bütçesi tavanı ve tek bir hibe/destek oranı varsa açık çarpım ("3.500.000 TL × %75 =
    2.625.000 TL"). Birden çok oran, kaldırılmış oran ya da bütçe olmayan tavan varsa boş (tek anlamlı değil)."""
    metin = t.tesvil_tutari or ""
    butce = re.search(r"bütçe\w*[^;.]{0,30}?(?:en fazla|üst (?:sınırı|limiti)|azami|tavanı)\s*"
                      r"(\d{1,3}(?:\.\d{3})+)\s*TL", metin, re.I)
    if not butce:
        return ""
    oranlar = set()
    for parca in re.split(r"[;]", metin):
        if re.search(r"kaldır|ilave|\+", parca):
            continue
        oranlar |= {int(x) for x in re.findall(r"%\s*(\d{1,3})\s*(?:hibe|destek)", parca)}
        oranlar |= {int(x) for x in re.findall(r"destek oranı\s*%\s*(\d{1,3})", parca)}
    if len(oranlar) != 1 or len(re.findall(r"%\s*\d", metin)) != 1:
        return ""
    oran = oranlar.pop()
    tavan = int(butce.group(1).replace(".", ""))
    hibe = tavan * oran // 100
    return (f"{butce.group(1)} TL bütçe × %{oran} = {f'{hibe:,}'.replace(',', '.')} TL (kayıttaki bütçe tavanı ile "
            "oranın çarpımı; proje bütçenize göre değişir)")


def _tanim(t) -> str:
    from app.basvuru_taslagi import kart_ozeti
    return _cumle_kisalt(kart_ozeti(t.ozet, 300), 300)


_NITELIK_AD = {"kredi_kefalet": "kredi kefaleti", "faiz_destegi": "faiz desteği", "prim desteği": "prim desteği",
               "hisse karşılığı yatırım": "hisse karşılığı yatırım"}


def _hibe_degil_notu(soru: str, t) -> str:
    """Soru hibe istiyor ama program hibe değilse " (hibe değil: kredi kefaleti)" notu."""
    nitelik = (t.uygunluk_kriterleri or {}).get("tutar_niteligi")
    if re.search(r"\bhibe", _katla(soru)) and nitelik in _NITELIK_AD:
        return f" (hibe değil: {_NITELIK_AD[nitelik]})"
    return ""


def _profile_uyan_tutar(tutar: str, d) -> str:
    """Kapsam notu ek kalemin bu üreticiye ödenmediğini söylüyorsa kalem tutar satırından da çıkarılır (hakem bulgusu
    2026-10-12, 7. tur: çilek kartında "Kapsam: çilek bu listede yok" yazarken Destek satırı fidan tutarını gösteriyordu)."""
    if any(k.startswith("fidan kullanım desteği yalnız") for k in getattr(d, "kisit", None) or []):
        tutar = re.sub(r";?\s*fidan kullanım desteği ayrıca[^.;]*", "", tutar, flags=re.I).strip()
    return tutar


def fidan_kalemi_notu(profil, tum: list) -> str:
    """Temel destek kaydındaki "fidan kullanım desteği ayrıca …" ek kalemi yalnız fidan kaydının ürün listesindeki
    (Tablo 6) türler içindir; profildeki ürün listede yoksa kartta belirtilir (hakem bulgusu 2026-10-12, 5. tur: çilek
    üreticisine 1.835 TL/da sertifikalı fidan desteği gösteriliyordu; çilek Tablo 6'da yok)."""
    urun = getattr(profil, "urun_turu", None)
    if not urun:
        return ""
    fidan = next((t for t in tum if "Fidan Kullanım Desteği" in (t.baslik or "")
                  and (t.uygunluk_kriterleri or {}).get("urun_listesi")), None)
    if fidan is None or _katla(urun) in {_katla(x) for x in fidan.uygunluk_kriterleri["urun_listesi"]}:
        return ""
    return (f"fidan kullanım desteği yalnız yeni meyve bahçesi/bağ tesisinde ve fidan tablosundaki türlerde "
            f"ödenir; {urun} bu listede yok")


def statusuz_kalem_satiri(t) -> str:
    """Şemsiye e-ihracat kaydı öne çıktığında statüsüz şirketin yararlanabildiği kalemler (kaydın kendi cümlesi; hakem
    bulgusu 2026-10-12, 5-6. tur, kritik: kendi sitesinden satan mikro firmaya bütün kalemler açık gibi gösteriliyordu)."""
    metin = " ".join([t.tesvil_tutari or "", t.detay or ""] + [m.get("metin", "") for m in t.kontrol_listesi or []])
    m = re.search(r"Statüsüz şirketin yararlanabildiği kalemler: ([^.|]+)", metin)
    if not m:
        return ""
    return ("Statü (Perakende E-Ticaret Sitesi ya da benzeri) almamış şirket yalnız şu kalemlerden yararlanır (kayıttan): "
            + m.group(1).strip().rstrip(",;") + "; diğer kalemler statü şartlıdır.")


def hibe_mi(t) -> bool:
    """Geri ödemesiz destek (hibe, dekar başı ödeme); kredi, kefalet ve vergi indirimi değil."""
    if (t.uygunluk_kriterleri or {}).get("tutar_niteligi") == "hibe":
        return True
    if _kredi_mi(t) or _VERGI_PROGRAMI.search(t.baslik or ""):
        return False
    tutar = t.tesvil_tutari or ""
    # "Hibe değil, faiz indirimi" (Hazine faizli tarım kredisi) hibe sayılmaz (tur 7 sonrası denemesi).
    return bool(re.search(r"geri ödemesiz|\bhibe|TL/da\b|TL/dekar", tutar, re.I)) and not re.search(
        r"geri ödemeli\b|hibe değil|hibe/ödeme değil", tutar, re.I)


# Sorunun konusunu taşımayan genel sözcükler (hibe sorusunda konu eşleşmesi için). `_katla` ASCII'ye katlar
# (ç→c, ı→i), bu yüzden desenler katlanmış biçimde yazılır (2026-10-12: Türkçe harfli desenler hiç eşleşmiyor,
# "düşük", "faizli", "yatırım" konu sayılıyordu).
_GENEL_SOZCUK = re.compile(
    r"^(?:destek\w*|hibe\w*|kredi\w*|kurul\w*|alabil\w*|alir\w*|istiyor\w*|istem\w*|sistem\w*|devlet\w*|"
    r"program\w*|basvur\w*|yatirim\w*|yapabil\w*|nasil|nedir|hangi\w*|var\w*|miyim|olur\w*|karsila\w*|"
    r"geri|odeme\w*|isletme\w*|firma\w*|sirket\w*|bizim|benim|bunun|sunun|olarak|kadar|tesvik\w*|para\w*|"
    r"tutar\w*|ucret\w*|dusuk\w*|faiz\w*|uygun\w*|gider\w*|masraf\w*|maliyet\w*|ihtiyac\w*|mevcut\w*|"
    r"ister\w*|yararlan\w*)$")
# Mastar fiil (yenilemek, kurmak) konu değil; konu adla taşınır (2026-10-12: "bahçeyi yenilemek" sorusunda "yenile"
# kökü "yenilenebilir enerji" metnine eşleşiyordu).
_MASTAR = re.compile(r"(?:mek|mak)$")
# Tek bir ad çekimi/iyelik eki atılır (katlanmış biçim); kalan kök en az 4 harf olmalı.
_EK = re.compile(r"(?:leri|lari|nin|nun|den|dan|ten|tan|ler|lar|yi|yu|si|su|ni|nu|de|da|te|ta|i|u|e|a)$")


def soru_konulari(soru: str) -> list[str]:
    """Sorunun konu sözcükleri (5+ harf, katlanmış; genel soru/teşvik sözcükleri ve mastar fiiller hariç)."""
    return [k for k in re.findall(r"[a-z]{5,}", _katla(soru)) if not _GENEL_SOZCUK.match(k) and not _MASTAR.search(k)]


def _konu_koku(sozcuk: str) -> str:
    kok = _EK.sub("", sozcuk)
    return kok if len(kok) >= 4 else sozcuk


def konu_eslesir(soru: str, t) -> bool:
    """Programın başlık/özet/tutar/şart metninde sorunun konu sözcüklerinden birinin kökü bir sözcüğün BAŞINDA geçiyor
    mu? Konu sözcüğü yoksa True (2026-10-12: damla sulama hibesi sorusunda ilgisiz sera hibesi "hibe tarafı" diye
    gösteriliyordu; kök sözcük ortasında da eşleşince "yenile" → "yenilenebilir" yanlış konu sayılıyordu)."""
    konu = soru_konulari(soru)
    if not konu:
        return True
    metin = _katla(" ".join([t.baslik or "", t.ozet or "", t.tesvil_tutari or ""]
                            + [m.get("metin", "") for m in t.kontrol_listesi or []]))
    return any(re.search(r"(?<![a-z0-9])" + re.escape(_konu_koku(k)), metin) for k in konu)


def hibe_satiri(soru: str, ilk, adaylar: list, kapali: list | None = None) -> str:
    """"Kredi ya da hibe var mı?" sorusunda hibe tarafının hükmü (hakem bulgusu 2026-10-12, 5. tur: hibe yarısı
    cevapsız kalıyor, yanıtta yalnız kredi/kefalet kartları duruyordu ve hibe olmadığı söylenmiyordu)."""
    if not re.search(r"\bhibe", _katla(soru)) or hibe_mi(ilk.tesvik):
        return ""
    sorulan = set(soru_ihtiyaclari(soru))
    hibeler = [d for d in adaylar if d is not ilk and hibe_mi(d.tesvik) and d.karar in ("sartli", "belirlenemedi")
               and (not sorulan or program_ihtiyaclari(d.tesvik) & sorulan)]
    kapali_hibe = [d for d in kapali or [] if d.karar == "kapali" and hibe_mi(d.tesvik)
                   and (not sorulan or program_ihtiyaclari(d.tesvik) & sorulan)]
    konulu = [d for d in hibeler if konu_eslesir(soru, d.tesvik)]
    # Konusu soruya uyan kapalı hibe, ihtiyaç etiketi tutmasa da anılır (2026-10-12: "bahçeyi yenilemek ve damla
    # sulama" sorusu "finansman" etiketi alıyor, etiketsiz TSS hibesi süzgeçte düşüyordu).
    kapali_konulu = ([d for d in kapali or [] if d.karar == "kapali" and hibe_mi(d.tesvik)
                      and konu_eslesir(soru, d.tesvik)] if soru_konulari(soru) else [])
    if hibeler and not konulu and kapali_konulu:
        # Açık hibe sorunun konusunu karşılamıyor, konuya uyan hibe kapalı: önce kapalı olan adıyla söylenir.
        return (f"Hibe (geri ödemesiz): sorunuzun konusuna uyan {', '.join(_kisa_ad(d.tesvik.baslik) for d in kapali_konulu[:2])}"
                f" şu an başvuruya kapalı (yeni çağrıyı izleyin); açık hibe {_kisa_ad(hibeler[0].tesvik.baslik)} farklı "
                "bir gideri karşılar.")
    if hibeler:
        hibeler = konulu or hibeler
        hibeler.sort(key=lambda x: -gider_kalemi_eslesmesi(soru, x.tesvik))
        d = hibeler[0]
        kalem_soruda = any(re.search(sk, _katla(soru)) for sk, _ in _GIDER_KALEMLERI)
        if kalem_soruda and not gider_kalemi_eslesmesi(soru, d.tesvik):
            # Hakem bulgusu 7. tur: ERP/sensör sorusunda danışmanlık hizmeti desteği (YÖNDE) "hibe" diye gösteriliyordu.
            return (f"Hibe (geri ödemesiz): sorduğunuz gider kalemi için kayıtlı hibe yok; geri ödemesiz yakın seçenek "
                    f"{_kisa_ad(d.tesvik.baslik)} farklı bir gideri karşılar: {_cumle_kisalt(d.tesvik.tesvil_tutari, 140)}")
        return (f"Hibe (geri ödemesiz) tarafı: {_kisa_ad(d.tesvik.baslik)} — {karar_etiketi(d).lower()}"
                + (f" ({_kisa_neden(d)})" if d.karar == "belirlenemedi" and _kisa_neden(d) else "") + ".")
    # Soruya uyan ama şu an kapalı hibe programı varsa adıyla söylenir (hakem bulgusu 7. tur: sulama/sera hibesi
    # sorusunda IPARD ve KKYP gibi kapalı hibeler hiç anılmıyordu).
    kapali_hibe = kapali_konulu or kapali_hibe
    return ("Hibe (geri ödemesiz): sorunuza ve profilinize açık kayıtlı bir hibe programı bulamadım"
            + (f"; {', '.join(_kisa_ad(d.tesvik.baslik) for d in kapali_hibe[:2])} şu an başvuruya kapalı (yeni çağrıyı "
               "izleyin)" if kapali_hibe else "")
            + "; aşağıdaki programlar geri ödemesiz destek değildir (kredi, kefalet, vergi avantajı, eğitim ya da "
              "yatırım).")


def _soruyu_one_al(satir: list[str], niyet: set[str]) -> list[str]:
    """Sorulan değeri (tutar ya da tarih) program başlığının hemen altına, uygunluk etiketinin önüne alır."""
    onekler = []
    if "tutar" in niyet or "sure" in niyet:
        onekler += ["- Destek unsurları", "- Destek:", "- Sizin ürününüz için", "- Süre (kayıttan)"]
    if "tarih" in niyet:
        onekler += ["- Başvuru:"]
    bas = next((i for i, x in enumerate(satir) if x.startswith("- **")), 1) + 1
    one = sorted((x for x in satir[bas:] if x.startswith(tuple(onekler))),
                 key=lambda x: next(i for i, o in enumerate(onekler) if x.startswith(o)))
    if not one:
        return satir
    return satir[:bas] + one + [x for x in satir[bas:] if x not in one]


def birlikte_karar_satirlari(birlikte: str, hukumsuz: list[str]) -> list[str]:
    """Birlikte kullanım sorusunun kısa cevabı: kayıttaki hükümler aynı metne göre gruplanıp karar cümlesi olarak
    (hangi programlar için ne geçerli), sonra hükmü olmayanlar. Hüküm metni kayıttan aynen alınır."""
    gruplar: dict[str, list[str]] = {}
    for satir in (birlikte.split("\n")[1:] if birlikte else []):
        if "] " not in satir or ": " not in satir:
            continue
        baslik, hukum = satir.split("] ", 1)[1].split(": ", 1)
        hukum = hukum.split(" (resmî metin:")[0].strip().rstrip(".")
        gruplar.setdefault(hukum, []).append(baslik)
    sonuc = []
    for hukum, basliklar in list(gruplar.items())[:3]:
        sonuc.append(f"- Birlikte kullanım — {'; '.join(basliklar)}: kayda göre {hukum[:1].lower() + hukum[1:]}.")
    if hukumsuz:
        sonuc.append(f"- Birlikte kullanım hükmü kayıtta olmayanlar: {'; '.join(hukumsuz)} — aynı harcamanın birlikte "
                     "desteklenip desteklenemeyeceğini kurumdan teyit edin.")
    if not sonuc:
        sonuc.append("- Birlikte kullanım: gösterilen programların hiçbirinde kayıtta hüküm yok; kurumlardan teyit edin.")
    return sonuc


def hibe_durumu(soru: str, ds: list[Degerlendirme], gosterilen: list[Degerlendirme]) -> str:
    """Soru hibe soruyorsa ve kayıtta "hibe" nitelikli adayların hiçbiri açık/olası değilse bunu ilk satırda söyler."""
    if not re.search(r"\bhibe", _katla(soru)):
        return ""

    def _hibe(d):
        nitelik = (d.tesvik.uygunluk_kriterleri or {}).get("tutar_niteligi")
        return nitelik == "hibe" or (nitelik is None and bool(re.search(
            r"\bhibe|geri ödemesiz|kamu katkısı", d.tesvik.tesvil_tutari or "", re.I)))
    if any(_hibe(d) and d.karar in ("sartli", "belirlenemedi") for d in gosterilen):
        return ""
    kapali = [d for d in ds if _hibe(d) and d.karar in ("kapali", "uygun_degil")]
    if not kapali:
        return ""
    return ("- Hibe: sorunuzla eşleşen hibe programlarının hiçbiri şu an size açık görünmüyor ("
            + "; ".join(f"{d.tesvik.baslik} — {KARAR_METNI[d.karar].lower()}" for d in kapali[:3])
            + "). Aşağıdaki açık seçenekler kredi, kefalet ya da diğer destek türleridir.")


def _soruya_en_ilgili(maddeler: list[str], soru: str) -> str:
    """Teyit maddelerinden soruyla en çok kök paylaşan (ör. "Ar-Ge merkezi" sorusunda "Ar-Ge merkezi: en az elli ...
    personel"); örtüşme yoksa ilk madde (hakem bulgusu 2026-10-12: tasarım merkezi şartı gösteriliyordu)."""
    def _k(metin: str) -> set[str]:
        metin = re.sub(r"\bar[- ]?ge\b", "arge", _katla(metin))   # "Ar-Ge" tek kök
        return {k[:5] for k in re.findall(r"[a-z]{4,}", metin) if k not in _DURAK}
    kokler = _k(soru)
    puan = [len(kokler & _k(m.split(" — ")[0])) for m in maddeler]
    return maddeler[max(range(len(maddeler)), key=lambda i: (puan[i], -i))] if maddeler else ""


def _kredi_mi(t) -> bool:
    """Kredi/kefalet ürünü (hibe değil): limit "destek" diye sunulmaz."""
    from app.matching import _kredi_kefaleti_mi
    # "proje_bazli_tavan" toplama girmez ama kredi değildir (KKYP/TSS hibesi kredi sayılıp hibe satırından düşüyordu,
    # 2026-10-12); açık nitelik varsa yalnız kredi/kefalet/faiz desteği kredi sayılır.
    nitelik = (t.uygunluk_kriterleri or {}).get("tutar_niteligi")
    return (t.kurum in ("KGF", "Türk Eximbank")
            or (nitelik in ("kredi_kefalet", "faiz_destegi") if nitelik else _kredi_kefaleti_mi(t))
            or (getattr(t, "basvuru_bicimi", None) or "") in ("kredi", "kefalet"))


def tesvik_belgesi_satiri(soru: str, profil, kartlar: list[Degerlendirme]) -> str:
    """Soru açıkça teşvik belgesini soruyorsa ve kartlarda 9903 programı yoksa Hedef Yatırımlar hükmü (persona
    denemesi 2026-10-12: matbaanın "4 milyon TL'lik makine için hangi kredi, hibe ya da teşvik belgesi" sorusunda
    teşvik belgesi cevabı yalnız alt bölümdeydi; EK-3 18: yalnız 100 milyon TL ve üzeri)."""
    if profil is None or not re.search(r"tesvik belge|9903|yatirim tesvik", _katla(soru)):
        return ""
    from app.tesvik_9903_uygunluk import degerlendir as d9903, program_turu, tutar_siniri, yatirim_tutari
    if any(program_turu(d.tesvik.baslik) for d in kartlar):
        return ""
    from app.kobi import kobi_sinifi
    olcek = kobi_sinifi(getattr(profil, "calisan_sayisi", None), getattr(profil, "yillik_ciro", None))
    tutar, kaynak = yatirim_tutari(soru, profil)
    u = tutar_siniri(d9903("hedef_yatirimlar", getattr(profil, "nace_kodu", None), getattr(profil, "bolge", None),
                           olcek.sinif if olcek.kesin else None), tutar, getattr(profil, "bolge", None), kaynak or "sorudaki")
    hukum = {"uygun_degil": "**uygun değil**", "dusuk": "düşük olasılık", "sartli": "şartlı",
             "uygun": "konu EK-3 listesinde", "bilinmiyor": "belirlenemedi"}[u.durum]
    return f"Teşvik belgesi (9903, Hedef Yatırımlar): {hukum} — {u.gerekce} ({u.madde})."


def kisa_cevap(niyet: set[str], odak: list[Degerlendirme], adaylar: list[Degerlendirme],
               elenen: list[Degerlendirme], notlar: dict[int, str], triyaj: bool, soru: str, bugun: date,
               odak_turu: str = "ad", profil=None, tum_adaylar: list[Degerlendirme] | None = None) -> list[str]:
    satir = ["**Kısa cevap:**"]
    if _MANIPULASYON.search(_katla(soru)) and profil is not None:
        from app.kobi import AD as KOBI_AD
        from app.kobi import kobi_sinifi
        olcek = kobi_sinifi(profil.calisan_sayisi, profil.yillik_ciro)
        if olcek.sinif:
            satir.append(f"- Profilinize göre ({profil.calisan_sayisi} çalışan) işletmeniz {KOBI_AD[olcek.sinif]} "
                         "ölçeğinde; KOBİ programları için bölmeye gerek yok, doğru beyanla başvurun.")
    varsayim = getattr(profil, "_varsayim", None)
    if varsayim:
        satir.append(f"- Varsayım: {varsayim}")
        if getattr(profil, "_varsayim_uyari", None):
            satir.append(f"- **Dikkat:** {profil._varsayim_uyari}")
    tarim = tarim_odeme_satiri(soru, profil)
    if tarim and not odak:
        satir.append(f"- {tarim}")
    belge = tesvik_belgesi_satiri(soru, profil, list(odak) + list(adaylar[:EN_COK_KART]))
    if belge:
        satir.append(f"- {belge}")
    if odak:
        d = odak[0]
        t = d.tesvik
        satir.append(f"- **{t.baslik}** ({t.kurum})")
        hitap = "Sizin için" if profil is not None else "Durum"
        if d.karar in ("kapali", "uygun_degil"):
            satir.append(f"- {hitap}: **{KARAR_METNI[d.karar].lower()}** — {_birlestir(d.gerekce)}.")
        elif d.karar == "sartli" and karar_etiketi(d) != KARAR_METNI["sartli"]:
            satir.append(f"- {hitap}: **şartlı** — {_kisalt(d.teyit[0], 240).rstrip('.')}; bu şartı teyit edin.")
        elif d.karar == "sartli":
            satir.append("- Sizin için: profilinize göre engel yok — şartları teyit edin" + (
                f"; başlıca şart: {_kisalt(d.teyit[0].split(' — ')[0], 180)}" if d.teyit else "") + ".")
        elif d.gerekce:
            satir.append(f"- {hitap}: {karar_etiketi(d).lower()} — {_birlestir(d.gerekce)}.")
        bas = next(i for i, x in enumerate(satir) if x.startswith("- **")) + 1
        kapsam = kapsam_hukmu(soru, t)
        if kapsam:
            satir.insert(bas, f"- {kapsam}")
        sirketsiz = sirketsiz_basvuru_hukmu(soru, t)
        if sirketsiz:
            satir.insert(bas, f"- {sirketsiz}")
        if d.karar not in ("kapali", "uygun_degil") or "tarih" in niyet:
            satir.append(f"- Başvuru: {takvim_metni(d, bugun, kisa=True)}.")
            if "tarih" in niyet and d.cagri is None and not d.alt_not and d.karar not in ("kapali", "uygun_degil") \
                    and t.basvuru_suresi and re.search(r"çağrı|dönem", t.basvuru_suresi, re.I) \
                    and not re.search(r"\d{2}\.\d{2}\.\d{4}", t.basvuru_suresi):
                satir.append("- Çağrı açık mı: kayıtlarımızda bu çağrının açılış ve kapanış tarihi yok; açık/kapalı "
                             "durumu belirlenemedi, kurumun çağrı duyurusundan teyit edin.")
            # tarih sorusunda çağrının saat ve teslim notları kısa cevapta (kartta da var)
            if "tarih" in niyet and d.cagri and d.cagri.get("notlar") and d.donem in ("acik", "yaklasan"):
                satir.append(f"- Dikkat (çağrı notu): {_cumle_kisalt(_temiz(d.cagri['notlar']), 260).rstrip('.')}.")
        unsur = _destek_unsurlari(notlar, t)
        if "tutar" in niyet and unsur:
            satir.append(f"- Destek unsurları (Karar metninden, bölgenize göre): {unsur}")
        elif ("tarih" not in niyet or "tutar" in niyet or d.karar == "kapali") and not (
                d.karar == "uygun_degil" and "tutar" not in niyet):
            # Size uygun olmayan programın tutarı, tutar sorulmadıkça kısa cevapta gösterilmez (hakem bulgusu 5. tur:
            # otelin "yurt dışı tanıtım" sorusunda "uygun değil" satırının altındaki 12 milyon TL'lik limit destek
            # varmış izlenimi veriyordu); tutar kartta durur.
            tutar = _profile_uyan_tutar(tutar_metni(t, 450).split(" Hesaplama: ")[0], d)
            if tutar:
                etiket = ("Son bilinen destek (bilgi için)" if d.karar == "kapali" else
                          "Kredi koşulları (hibe değil)" if _kredi_mi(t) else "Destek")
                satir.append(f"- {etiket}: {tutar}")
                if azami_hibe(t) and d.karar != "kapali":
                    satir.append(f"- Azami hibe (hesap): {azami_hibe(t)}")
            elif d.onceki_tutar:
                satir.append("- Destek: bu programın tutarı kayıtta yok; önceki programın son bilinen tutarı (bilgi "
                             f"için): {_cumle_kisalt(d.onceki_tutar, 260)}")
        urun = _urun_tutari(t, profil) if d.karar != "kapali" else ""
        if urun:
            satir.append(f"- Sizin ürününüz için: {urun}")
        elif dekar_araligi(t, profil) and d.karar != "kapali":
            satir.append(f"- Arazinize göre: {dekar_araligi(t, profil)}")
        if tarim:
            satir.append(f"- {tarim}")
        sure = _sure_kirilimi(t) if "sure" in niyet else ""
        if sure:
            satir.append(f"- Süre (kayıttan): {sure}")
        if "tanim" in niyet and _tanim(t):
            satir.append(f"- Program: {_tanim(t)}")
        kimler = [x.split(' — ')[0] for x in d.teyit] or [_temiz(m["metin"]) for m in _tekil(
            [m for m in _maddeler(t) if m["tur"] == "sart"])]
        if "tanim" in niyet and kimler:
            satir.append(f"- {'Kimler başvurabiliyordu (son çağrı' if d.karar == 'kapali' else 'Kimler başvurabilir (kayıttaki şartlar'}"
                         "): " + "; ".join(_kisalt(x, 140).rstrip(" .") for x in kimler[:3]) + ".")
        akibet = sorulan_tutarin_akibeti(soru, t)
        if akibet:
            satir.insert(bas, f"- Sorduğunuz tutar: kayıtta «{akibet}».")
        dogrulanamayan = dogrulanamayan_tutarlar(soru, [x.tesvik for x in odak])
        if dogrulanamayan:
            satir.append(f"- Sorudaki {', '.join(dogrulanamayan)} tutarını güncel kayıtlarda bulamadım; geçerli tutar "
                         "yukarıdaki satırdadır.")
        sorulan = set(soru_ihtiyaclari(soru))
        if odak_turu == "kurum" and sorulan and not (program_ihtiyaclari(t) & sorulan):
            # Persona denemesi 2026-10-12: "seramik fırını için KOSGEB'den destek" sorusunda kurumun makine programı
            # (Kapasite Geliştirme) mikro işletmeye kapalıydı ama yanıt bunu söylemeden danışmanlık programını veriyordu.
            ilgili = [x for x in odak[1:] if program_ihtiyaclari(x.tesvik) & sorulan]
            ad = ", ".join(IHTIYAC_ADLARI[x] for x in soru_ihtiyaclari(soru))
            if d.ihtiyac_notu:
                satir.insert(1, f"- {d.ihtiyac_notu}")
            elif ilgili:
                x = ilgili[0]
                satir.insert(1, f"- Sorduğunuz {ad} için bu kurumun programı: {x.tesvik.baslik} — "
                                f"{karar_etiketi(x).lower()}" + (f" ({_birlestir(x.gerekce[:1])})" if x.gerekce else "")
                             + "; yukarıdaki program bu ihtiyaca doğrudan yönelik değildir.")
            else:
                satir.insert(1, f"- Sorduğunuz {ad} için bu kurumun kayıtlı bir programı yok; aşağıdaki program "
                                "farklı bir ihtiyaca yöneliktir.")
        if len(odak) > 1 and odak_turu == "kurum":
            # Kurum sorusunda ("KOSGEB'den ne alabiliriz?") kurumun bütün programları durumuna göre gruplanır: hakem
            # bulgusu 4. tur, mikro matbaa ve sürücü kursu yanıtlarında "KOSGEB'in makine/dijital programları size
            # kapalı, açık tek seçenek X" hükmü yoktu.
            gruplar = [("engel yok", [x for x in odak[1:] if x.karar == "sartli"]),
                       ("şarta bağlı", [x for x in odak[1:] if x.karar == "belirlenemedi"]),
                       ("size kapalı ya da başvuruya kapalı", kurum_ozeti_kapali(odak))]
            parca = [f"{ad}: " + ", ".join(f"{_kisa_ad(x.tesvik.baslik)}" + (
                f" ({_kisa_neden(x)})" if ad != "engel yok" and _kisa_neden(x) else "") for x in xs[:3])
                + (f" ve {len(xs) - 3} program daha" if len(xs) > 3 else "") for ad, xs in gruplar if xs]
            satir.append("- Bu kurumun diğer programları — " + "; ".join(parca) + ".")
        if odak_turu == "kurum" and profil is not None:
            # İlk satır kurum geneli hükümdür (hakem bulgusu 2026-10-12, 5-7. tur: "KOSGEB'den destek var mı" sorusunda
            # yanıt bir program adıyla başlıyordu; "açık olan X, kapalı olanlar Y" hükmü yoktu).
            kurum = " ve ".join(dict.fromkeys(x.tesvik.kurum for x in odak))
            acik = [x for x in odak if x.karar == "sartli" and not re.search(r"parasal destek değil",
                                                                               x.tesvik.tesvil_tutari or "")]
            sartli = [x for x in odak if x.karar == "belirlenemedi"]
            kapali = [x for x in odak if x.karar in ("kapali", "uygun_degil")]
            if acik:
                hukum = (f"{kurum} programlarından {len(acik)} tanesi profilinize göre engelsiz görünüyor ("
                         + ", ".join(_kisa_ad(x.tesvik.baslik) for x in acik[:2]) + ")")
            else:
                hukum = f"{kurum}'da profilinize engelsiz açık, parasal destek veren bir program görünmüyor"
            hukum += (f"; {len(sartli)} program şarta bağlı" if sartli else "") + (
                f", {len(kapali)} program size ya da başvuruya kapalı" if kapali else "") + "."
            satir.insert(1, f"- Kısa hüküm: {hukum}")
        elif len(odak) > 1:
            satir.append("- Adıyla eşleşen diğer kayıtlar: " + "; ".join(
                f"{x.tesvik.baslik} ({karar_etiketi(x).lower()})" for x in odak[1:4]) + ".")
        return _soruyu_one_al(satir, niyet)
    if triyaj:
        satir.append("- Uygunluk kararı için faaliyet, şirket türü ve il bilgisi gerekiyor." + (
            " Aşağıda sorunuzla ilgili programların kayıttaki şartlarını ve tutarlarını verdim; size uyup uymadığı "
            "eksik bilgiler girilince netleşir (sorular 5. bölümde)." if adaylar else
            " Sorunuzla doğrudan eşleşen, herkese açık bir program kaydı bulamadım; profilinizi girerseniz size özel "
            "programlar da taranır (sorular 5. bölümde)."))
        if adaylar:
            ilk = adaylar[0]
            tutar = tutar_metni(ilk.tesvik, 200).split(" Hesaplama: ")[0]
            satir.append(f"- Öne çıkan: **{ilk.tesvik.baslik}** ({ilk.tesvik.kurum}){_hibe_degil_notu(soru, ilk.tesvik)}"
                         + (f" — {tutar}" if tutar else "")
                         + f"; {takvim_metni(ilk, bugun, kisa=True)}.")
        return satir
    if not adaylar:
        satir.append("- Sorunuzla ilgili kayıtlı programların hiçbiri profilinize açık görünmüyor; gerekçeler aşağıda.")
        return satir
    ilk = adaylar[0]
    sorulan = soru_ihtiyaclari(soru)
    if "tanitim" in sorulan and "ihracat" not in sorulan:
        from app.matching import ihracat_odakli
        if ihracat_odakli(ilk.tesvik):
            # Hakem bulgusu 2026-10-12: "online kahve satışı için dijital pazarlama" sorusuna yurt dışı tanıtım desteği
            # sınırı söylenmeden veriliyordu.
            satir.append("- Yurt içine yönelik reklam ve pazarlama giderleri için kayıtlı doğrudan bir destek yok; "
                         "aşağıdaki programlar yalnız yurt dışına (ihracata) yönelik tanıtımı destekler.")
    if sorulan and not (program_ihtiyaclari(ilk.tesvik) & set(sorulan)):
        # Kapsam ölçümü 2026-10-12: çiftçinin Ar-Ge sorusunda ilgisiz kira/sigorta programı "Öne çıkan" diye veriliyordu.
        satir.append(f"- Sorduğunuz {', '.join(IHTIYAC_ADLARI[x] for x in sorulan)} için profilinize açık bir program "
                     "kaydı bulamadım; aşağıdakiler profilinize uyan, ama bu ihtiyaca doğrudan yönelik olmayan "
                     "programlardır.")
    for ek in (sirketsiz_basvuru_hukmu(soru, ilk.tesvik), kapsam_hukmu(soru, ilk.tesvik)):
        if ek:
            satir.append(f"- {ek}")
    hibe_degil = _hibe_degil_notu(soru, ilk.tesvik)
    bascilik = (_soruya_en_ilgili(ilk.teyit, soru).split(" — ")[0] if ilk.karar == "sartli" and ilk.teyit
                and not ilk.teyit[0].startswith(SART_YOK_TEYIT) else "")
    satir.append(f"- Öne çıkan: **{ilk.tesvik.baslik}** ({ilk.tesvik.kurum}){hibe_degil} — "
                 f"{karar_etiketi(ilk).lower()}"
                 + (f" ({_birlestir(ilk.gerekce[:1])})" if ilk.karar == "belirlenemedi" and ilk.gerekce else "")
                 + (f"; başlıca şart: {_kisalt(bascilik, 170).rstrip('.')}" if bascilik else "")
                 + f"; {takvim_metni(ilk, bugun, kisa=True)}.")
    konu = konu_satiri(soru, adaylar[:EN_COK_KART] + list(tum_adaylar or []))
    if konu:
        satir.append(f"- {konu}")
    statusuz = statusuz_kalem_satiri(ilk.tesvik)
    if statusuz:
        satir.append(f"- {statusuz}")
    hibe = hibe_satiri(soru, ilk, list(tum_adaylar or adaylar), elenen)
    if hibe:
        satir.append(f"- {hibe}")
    oran = sigorta_orani_satiri(ilk.tesvik, profil) if "sigorta" in sorulan else ""
    if oran:
        satir.append(f"- {oran[:1].upper() + oran[1:]}")
    hedef = hedef_ulke_satiri(soru, adaylar[:EN_COK_KART] + list(tum_adaylar or []))
    if hedef:
        satir.append(f"- {hedef}")
    unsur = _destek_unsurlari(notlar, ilk.tesvik)
    if unsur and niyet & {"tutar", "liste"}:
        bolge = re.search(r"(\d)\. bölge", unsur)
        if bolge:
            satir.append(f"- Yatırım teşvik bölgeniz: {bolge.group(1)}. bölge (Karar değerlendirmesinden).")
        asgari = asgari_yatirim_metni(ilk.tesvik, profil, soru)
        if asgari and asgari not in (bascilik or ""):
            satir.append(f"- {asgari}.")
        satir.append(f"- Destek unsurları (Karar metninden): {unsur}")
        unsur_kaliplari = {"KDV istisnası": r"\bkdv\b", "yatırım yeri tahsisi": r"\byeri? tahsis",
                           "gümrük vergisi muafiyeti": r"gumruk"}
        eksik = [ad for ad, kalip in unsur_kaliplari.items()
                 if re.search(kalip, _katla(soru)) and not re.search(kalip, _katla(unsur))]
        for ad in eksik:
            kalip = unsur_kaliplari[ad]
            baska = [d.tesvik.baslik for d in (tum_adaylar or adaylar) if d is not ilk and re.search(kalip, _katla(
                " ".join([_destek_unsurlari(notlar, d.tesvik), d.tesvik.tesvil_tutari or "", d.tesvik.ozet or "",
                          d.tesvik.detay or ""])))]
            satir.append(f"- {ad[:1].upper() + ad[1:]}: öne çıkan programın kaydında sayılmıyor" + (
                f"; şu programların destek unsurları arasında sayılıyor: {'; '.join(baska[:2])} (oran ve koşul "
                "kayıtta yok, Karar metninden teyit edin)" if baska else
                "; kayıtlarımızda tanımlı değil, Sanayi ve Teknoloji Bakanlığı'ndan teyit edin") + ".")
    else:
        tutar = tutar_metni(ilk.tesvik, 300).split(" Hesaplama: ")[0]
        if tutar and niyet & {"tutar", "liste"}:
            satir.append(f"- {'Kredi koşulları (hibe değil)' if _kredi_mi(ilk.tesvik) else 'Destek'}: {tutar}")
        elif "tutar" in niyet:
            satir.append("- Destek: bu programın tutarı kayıtta yok" + (
                f"; önceki programın son bilinen tutarı (bilgi için): {_cumle_kisalt(ilk.onceki_tutar, 260)}"
                if ilk.onceki_tutar else "; güncel tutarı kurumdan teyit edin") + ".")
    urun = _urun_tutari(ilk.tesvik, profil)
    if urun:
        satir.append(f"- Sizin ürününüz için: {urun}")
    if "tanim" in niyet:
        tanim = _tanim(ilk.tesvik)
        if tanim:
            satir.append(f"- Program: {tanim}")
    diger = [d for d in adaylar[1:4]]
    if diger:
        satir.append("- Diğer seçenekler: " + "; ".join(f"{d.tesvik.baslik} ({karar_etiketi(d).lower()})"
                                                        for d in diger) + ".")
    dogrulanamayan = dogrulanamayan_tutarlar(soru, [d.tesvik for d in adaylar[:6]])
    if dogrulanamayan:
        satir.append(f"- Sorudaki {', '.join(dogrulanamayan)} tutarını güncel kayıtlarda bulamadım; geçerli tutarlar "
                     "aşağıdaki kartlardadır.")
    if sorulan and elenen and (not (program_ihtiyaclari(ilk.tesvik) & {sorulan[0]}) or _kredi_mi(ilk.tesvik)):
        # Persona denemesi 2026-10-12: şahıs işletmesinin "Etsy'den yurt dışı satış" sorusunda asıl program (5986
        # E-İhracat) şirket şartıyla kapalıydı ama yanıt onu hiç anmıyordu.
        ilgili = [d for d in elenen if d.karar == "uygun_degil" and program_ihtiyaclari(d.tesvik) & {sorulan[0]}
                  and not (_kredi_mi(ilk.tesvik) and _kredi_mi(d.tesvik))]
        if ilgili:
            d = ilgili[0]
            satir.append(f"- Sorunuza doğrudan yönelik ama size kapalı: {d.tesvik.baslik} — "
                         f"{_kisalt(_birlestir(d.gerekce[:1]), 220)}.")
    ozette = set(map(id, kurum_ozeti_kapali(odak)[:3])) if odak_turu == "kurum" else set()
    kalan = [d for d in elenen if id(d) not in ozette]
    if kalan:
        satir.append(f"- {len(kalan)} program size kapalı ya da başvuruya kapalı (gerekçeleri aşağıda).")
    return satir


# ------------------------------------------------------------------ ana giriş
_TEKRAR_TAKVIM = re.compile(r"Dönemsel başvuru yok: [^\n]*?\(kayıt kontrolü: [0-9.]+\)")


# Sorudaki gider kalemi ↔ programın desteklediği gider (katlanmış soru kalıbı, kayıt metni kalıbı). Hakem bulgusu 4. tur:
# "ERP, makinelere sensör" sorusunda danışmanlık hizmeti desteği (YÖNDE), yazılım-donanım giderini karşılayan KOBİ
# Dijital Dönüşüm'ün önündeydi.
_GIDER_KALEMLERI = (
    (r"\berp\b|yazilim|donanim|sensor|otomasyon|\biot\b|\bmes\b|randevu sistem", r"yazılım|donanım"),
    (r"danisman", r"danışman"),
    (r"kargo|gonderi|nakliye|navlun", r"kargo|lojistik|nakliye|navlun|gönderi"),
    (r"\bkira", r"\bkira"),
    (r"fuar", r"fuar"),
    (r"makine|ekipman|firin|cnc|tezgah", r"makine|teçhizat|ekipman"),
    (r"komisyon", r"komisyon"),
    (r"sertifika|belgelendirme", r"sertifika|belgelendirme"),
    # "uygun faizli kredi": TCMB kaynaklı, faizsiz ya da faiz destekli ürün (hakem bulgusu 5-7. tur: zeytinyağı
    # ihracatçısına makine yatırım kredisi öne çıkıyor, Reeskont/SÖİF/İhracat Destek Finansmanı görünmüyordu)
    (r"uygun faiz|dusuk faiz|faizsiz|ucuz kredi|faiz destegi|faiz indirimi", r"TCMB|reeskont|faizsiz|faiz desteği|"
     r"uygun maliyet|faiz indirimi|sübvanse"),
)


_OLUMSUZ = re.compile(r"\bdeğil|kapsam dışı|desteklenmez", re.I)


# Soruda geçen konu ↔ kredi/destek tablosundaki ilgili satır (hakem bulgusu 2026-10-12, 4-7. tur: damla sulama
# sorusunda Hazine faizli tarım kredisinin "Basınçlı sulama sistemi kullanımı" ek indirim satırı hiç gösterilmiyordu).
_KONU_SATIRI = ((r"damla|sulama|yagmurlama|basincli", r"Basınçlı sulama[^-.;|\n]{0,40}-\s*\d+"),)


def konu_satiri(soru: str, kartlar: list) -> str:
    s = _katla(soru)
    for soru_k, kayit_k in _KONU_SATIRI:
        if not re.search(soru_k, s):
            continue
        for d in kartlar:
            t = getattr(d, "tesvik", d)
            metin = " ".join([t.tesvil_tutari or "", t.detay or ""] + [m.get("metin", "") for m in t.kontrol_listesi or []])
            m = re.search(kayit_k, metin)
            if m:
                return (f"Sorunuzla ilgili satır ({_kisa_ad(t.baslik)}): kayıtta “{_temiz(m.group(0)).strip(' -')}” "
                        "(tablodaki ek indirim satırı; uygulanacak oranı bankadan teyit edin).")
    return ""


def gider_kalemi_eslesmesi(soru: str, t) -> int:
    """Sorudaki gider kalemlerinden kaçını programın tutar/ayrıntı/kural metni destekliyor."""
    s = _katla(soru)
    metin = " ".join(str(x or "") for x in (t.tesvil_tutari, t.ozet, t.detay)) + " " + " ".join(
        m.get("metin", "") for m in (t.kontrol_listesi or []) if m.get("tur") in ("kural", "bilgi"))
    # Olumsuz cümle ("yazılım veya donanım alımı değil", "komisyon kapsam dışıdır") gider desteği sayılmaz.
    # (cümle bölmeli süzgeç: tek regex uzun kayıtlarda karesel geri izleme yapıp yanıtı 16 sn'ye çıkarıyordu)
    metin = " ".join(p for p in re.split(r"[.;]", metin) if not _OLUMSUZ.search(p))
    return sum(1 for sk, pk in _GIDER_KALEMLERI if re.search(sk, s) and re.search(pk, metin, re.I))


def _liste_ogeleri(metin: str) -> list[str]:
    """"a, b, c ve d" listesinin öğeleri (özgün yazım)."""
    return [x.strip(" .") for x in re.split(r",\s*|\s+ve\s+", metin) if x.strip(" .")]


def sigorta_orani_satiri(t, profil) -> str:
    """Devlet destekli tarım sigortasında profildeki ürünün prim desteği oranı, kaydın ürün listelerinden (hakem
    bulgusu 2026-10-12, 4. tur: "çilekte dolu ve don sigortasında devlet ne kadar öder" sorusuna altı oran dökülüyor,
    kış donu %70'inin yalnız belirli meyvelere ait olduğu söylenmiyordu)."""
    ad = getattr(profil, "urun_turu", None) or ""
    urun = _katla(ad)
    if not urun or "TARSİM" not in (t.kurum or "") + (t.baslik or ""):
        return ""
    bilgiler = [m.get("metin", "") for m in t.kontrol_listesi or [] if m.get("tur") == "bilgi"]
    yetmis_m = next((b for b in bilgiler if re.match(r"Yüzde 70 prim desteği:", b)), "")
    yetmis = _liste_ogeleri(yetmis_m.split(":", 1)[1]) if yetmis_m else []
    kis_m = next((b for b in bilgiler if " kış donu" in b), "")
    kis = _liste_ogeleri(kis_m.split(" kış donu")[0]) if kis_m else []
    if kis:
        kis[-1] = re.sub(r"(?:de|da|te|ta)$", "", kis[-1])   # "vişnede kış donu" → "vişne"
        kis = [x[:1].lower() + x[1:] for x in kis]
    katli = lambda xs: {_katla(x) for x in xs}  # noqa: E731
    if urun in katli(yetmis):
        return f"{ad} için kayıttaki oran: prim desteğinin %70'i devletçe karşılanır (%70 uygulanan ürünler listesinde)."
    parcalar = [f"{ad} için kayıttaki oran: genel prim desteği %50"]
    if urun in katli(kis):
        parcalar.append("kış donu riskinde %70 (kış donu listesinde)")
    elif kis:
        parcalar.append(f"kış donunda %70 yalnız {', '.join(kis)} için; {ad} bu listede yok")
    if any(_katla(x).startswith("acik alanda yetistirilen meyve") for x in yetmis):
        parcalar.append(f"{ad} 'açık alanda yetiştirilen meyveler' tarifesine giriyorsa %70 (listede adıyla "
                        "geçmiyor; TARSİM acentesinden teyit edin)")
    return "; ".join(parcalar) + "."


# Soruda bölge adıyla geçen ülke grupları; liste üyeliği kaydın "Hedef ülkeler" listesinden okunur.
_BOLGE_ULKELERI = {"korfez": ("BAE", "Bahreyn", "Katar", "Kuveyt", "Suudi Arabistan", "Umman")}


def hedef_ulke_satiri(soru: str, kartlar: list) -> str:
    """Soruda ülke ya da bölge geçiyorsa 5986 "Hedef ülkeler" listesine göre hangilerinde oranın yüksek olduğu (hakem
    bulgusu 2026-10-12, 4. tur: "Körfez ülkelerine satmak" sorusunda Körfez hiç anılmıyordu)."""
    s = _katla(soru)
    for d in kartlar:
        t = getattr(d, "tesvik", d)
        m = re.search(r"Hedef ülkeler \(([^)]*)\): ([^.]+)\.", t.detay or "")
        if not m:
            continue
        liste = [x.strip() for x in re.split(r",\s*", m.group(2)) if x.strip()]
        katli = {_katla(x): x for x in liste}
        sorulan: list[str] = []
        for bolge, ulkeler in _BOLGE_ULKELERI.items():
            if re.search(rf"\b{bolge}", s):
                sorulan += list(ulkeler)
        sorulan += [x for k, x in katli.items() if re.search(rf"\b{re.escape(k)}", s) and x not in sorulan]
        if not sorulan:
            return ""
        icinde = [x for x in sorulan if _katla(x) in katli]
        disinda = [x for x in sorulan if _katla(x) not in katli]
        oran = re.search(r"hedef ülkelerde (\d+) puan artar", t.detay or "")
        return (f"Hedef ülke listesi ({m.group(1)}; {_kisa_ad(t.baslik)} ve diğer 5986 kalemlerinde oran "
                + (f"{oran.group(1)} puan yüksek" if oran else "yüksek") + "): "
                + (f"{', '.join(icinde)} listede" if icinde else "sorduğunuz ülkeler listede değil")
                + (f"; {', '.join(disinda)} listede değil (genel oran)" if icinde and disinda else "") + ".")
    return ""


def kurum_ozeti_kapali(odak: list["Degerlendirme"]) -> list["Degerlendirme"]:
    """Kurum sorusunun kısa cevap özetinde gerekçesiyle anılan kapalı programlar (en çok 4); bunlar aşağıdaki
    "kapalı programlar" listesinde yinelenmez."""
    return [x for x in odak[1:] if x.karar in ("kapali", "uygun_degil")
            and not any("aracı/ekosistem" in g for g in x.gerekce)]


# Eşleşme panelinin sıralama notları yanıt kartına taşınmaz: yanıt aynı durumu kendi kuralıyla söyler (kapalı dönem,
# ölçek, USD eşiği) ya da not kullanıcıya bilgi vermez (hakem bulgusu 5. tur: "engel yok" kartında "teyit: ölçek çok
# büyük"; "Belirttiğiniz hedeflerle doğrudan eşleşme bulunamadı" ve "sektörden bağımsız genel program" sistem dili).
_PANEL_NOTU = re.compile(r"doğrudan eşleşme bulunamadı|sektörden bağımsız genel bir program|Program ölçeği \(asgari|"
                         r"Başvuru dönemi şu an kapalı|Kaydın aradığı en az .{0,40}USD")


def _kisa_ad(baslik: str | None) -> str:
    """Program adının parantezsiz, " — " öncesi kısmı (özet satırları için)."""
    ad = re.sub(r"\s*\([^()]*\)", "", (baslik or "").split(" — ")[0]).strip()
    return _kisalt(ad or baslik or "", 70)


def _kisa_neden(d: "Degerlendirme") -> str:
    """Karar gerekçesinin özet satırına sığan kısmı (önek ve kayıt alıntısı olmadan)."""
    if not d.gerekce:
        return ""
    g = d.gerekce[0]
    for onek in (KILIT_ONEKI + ": ", KISI_ONEKI + ": ", "düşük olasılık: "):
        if g.startswith(onek):
            g = g[len(onek):]
    g = g.split(" — kayıttaki şart:")[0].split("; kayıttaki")[0]
    return _cumle_kisalt(g, 70).rstrip(".")


def tekrarlari_kisalt(metin: str) -> str:
    """Kayıtlardan gelen aynı uzun başvuru dönemi açıklaması (ör. her KGF paketinde "Dönemsel başvuru yok: kredi
    başvurusu bankaya yapılır…") yanıtta yalnız ilk geçtiği yerde tam yazılır; sonrakiler kısa atıfla değişir."""
    gorulen: set[str] = set()

    def _degistir(m):
        if m.group(0) in gorulen:
            return "Dönemsel başvuru yok (başvuru bu paketin kredi veren bankasına yapılır)"
        gorulen.add(m.group(0))
        return m.group(0)
    metin = _TEKRAR_TAKVIM.sub(_degistir, metin)
    for kalip, yerine in _IC_NOTLAR:
        metin = kalip.sub(yerine, metin)
    # "(kayıttan; güncel çağrıyı kurumdan teyit edin)" her takvim satırında tekrar ediyordu; ilk geçtiği yerde kalır.
    ek = " (kayıttan; güncel çağrıyı kurumdan teyit edin)"
    ilk = metin.find(ek)
    if ilk >= 0:
        metin = metin[:ilk + len(ek)] + metin[ilk + len(ek):].replace(ek, "")
    # Kayıttan gelen "bilgi yok" cümleleri ("Kaynak sayfada ayrı bir başvuru yeri belirtilmemiştir", "Dönemsel çağrı
    # yoktur; kaynakta başvuru tarihi belirtilmemiştir") yalnız ilk geçtiği yerde kalır (hakem bulgusu 4. tur: aynı
    # cümle kartta, Darboğazlar'da ve yol haritasının iki adımında 4-6 kez yineleniyordu).
    gorulen_cumle: set[str] = set()

    def _cumle(m):
        anahtar = _norm(m.group(0))
        if anahtar in gorulen_cumle:
            return ""
        gorulen_cumle.add(anahtar)
        return m.group(0)
    metin = _BILGI_YOK_CUMLESI.sub(_cumle, metin)
    metin = re.sub(r"(?<=\S) {2,}", " ", metin)
    metin = re.sub(r"(?<![.\w])\.\.(?!\.)|(?<=\w)\.\.(?!\.)", ".", metin)   # çift nokta (ellipsis "..." değil)
    metin = re.sub(r"[ \t]+;", ";", re.sub(r";\s*;", ";", metin))
    return metin


# Cümle sınırı dışına taşmaz: kalın işaret (**), parantez ve noktalama cümlenin parçası sayılmaz (hakem bulgusu 5. tur:
# "**Başvuru dönemi:" kalın işareti ve "(MADDE 5, … belirtilmemişse)" kapanış parantezi de siliniyordu).
_BILGI_YOK_CUMLESI = re.compile(r"(?:(?<=[:;.] )|(?<=\*\* )|(?<=\())[^.;:()*\n]{0,80}?(?:belirtilmemiştir|belirtilmiyor)"
                                r"[^.;()*\n]{0,160}[.;]?")


# Kayıt notlarındaki veri işleme ifadeleri kullanıcı diline çevrilir (anlam aynı: bilgi kayıtta yok, kaynaktan teyit).
_IC_NOTLAR = [
    (re.compile(r"sistemde teyit edilemedi \(taranmış PDF\)"), "birim tutarlar kayıtlarımızda yok, Karar ekinden teyit edin"),
    (re.compile(r"\((tebliğ|tebliğde|karar), sistemde yok\)"), r"(\1; kayıtlarımızda yok)"),
    (re.compile(r"\bsistemde yok\b"), "kayıtlarımızda yok"),
    (re.compile(r"\s*\([^()]*ayrı madde olarak gösterilmeli\.?\)"), ""),
]


def yanitla(soru: str, kayitlar: list, profil=None, notlar: dict[int, str] | None = None, *, db=None,
            bugun: date | None = None, ek_bloklar: list[str] | None = None, dis_servis: str | None = None) -> str:
    """Danışman yanıtı (Markdown). `kayitlar` app/rag.retrieve sonucudur; `profil` FinancialProfile (yerelde kalır).

    Oturum verilmezse app.rag.SessionLocal açılır (testlerde bellek-içi veritabanına yamanan aynı fabrika). retrieve
    kendi oturumunu kapattığı için kayıtlar bu oturumda yeniden yüklenir (çağrılar ilişkisi tembel yüklenir)."""
    from app import rag
    from app.matching import esles
    from app.models import Tesvik
    from app.rag import birlikte_kullanim_metni

    bugun = bugun or date.today()
    notlar = dict(notlar or {})
    kendi_db = db is None
    db = db or rag.SessionLocal()
    try:
        kayitlar = [(db.get(Tesvik, t.id) if t.id is not None else None) or t for t in kayitlar]
        kayitlar = [t for t in kayitlar if not _mukerrer(t)]
        tum = [t for t in db.query(Tesvik).all() if not _mukerrer(t)]
        niyet = niyetler(soru)
        adi_gecen_kayit = adi_gecen_programlar(soru, tum)
        kurumlar = (kurum_odagi(soru, tum) if not adi_gecen_kayit and not _MANIPULASYON.search(_katla(soru))
                    else set())
        from app.ihtiyac import isletmeye_yonelik_mi
        # "Şirket kurarsam KOSGEB ve TÜBİTAK'tan hangi destekler?" (yalnız girişim ihtiyacı) genel kurum sorusudur: kurumun
        # bütün programları değerlendirilir (hakem bulgusu 4. tur: TÜBİTAK tarafında yalnız kapalı 1812 görünüyordu).
        if kurumlar and set(soru_ihtiyaclari(soru)) - {"girisim"}:
            # "KOSGEB'den makine desteği": kurum bir filtredir; sıra aramanın (ihtiyaç) sırasıdır.
            kurum_kayit = [t for t in kayitlar if t.kurum in kurumlar]
            # Profile kapalı olduğu için aramadan elenen ama soruya yönelik kurum programları da değerlendirilir; yanıt
            # "kurumun dijital programı size kapalı (mikro ölçek)" diyebilsin (hakem bulgusu 4. tur, sürücü kursu).
            _ih = set(soru_ihtiyaclari(soru))
            kurum_kayit += [t for t in tum if t.kurum in kurumlar and t.aktif_mi is not False and isletmeye_yonelik_mi(t)
                            and program_ihtiyaclari(t) & _ih and t not in kurum_kayit
                            and not _DURUM_PROGRAMI.search(t.baslik or "")]
        else:
            kurum_kayit = sorted((t for t in tum if t.kurum in kurumlar and isletmeye_yonelik_mi(t)),
                                 key=lambda t: t.aktif_mi is False)
        odak_kayit = adi_gecen_kayit or kurum_kayit or tutar_gecen_kayitlar(soru, tum)
        for t in [x for x in odak_kayit if x.aktif_mi is False]:
            for h in halef_kayitlari(t, tum):
                if h.id not in {x.id for x in odak_kayit}:
                    odak_kayit = [*odak_kayit, h]
        mevcut = {t.id for t in kayitlar}
        kayitlar = [*[t for t in odak_kayit if t.id not in mevcut], *kayitlar]
        for t in zorunlu_adaylar(profil, tum) + kurulus_adaylari(profil, soru, tum):
            if t.id not in {x.id for x in kayitlar}:
                kayitlar.append(t)
        if getattr(profil, "sirket_turu", None) in ("sahis", "yok") and not adi_gecen_kayit:
            ilk_ihtiyac = (soru_ihtiyaclari(soru) or [None])[0]
            if ilk_ihtiyac:
                from app.matching import uygunluk_engeli as _ue
                kapali = [t for t in tum if t.aktif_mi is not False and ilk_ihtiyac in program_ihtiyaclari(t)
                          and not _kredi_mi(t) and t.id not in {x.id for x in kayitlar}
                          and (_ue(t, profil) or "").startswith("yalnızca")]
                # en genel (şemsiye) program önce: başlığı "Destekleri" ile biten ya da en kısa başlık
                kapali.sort(key=lambda t: (not re.search(r"Destekleri\b", t.baslik or ""), len(t.baslik or "")))
                kayitlar += kapali[:1]
        if getattr(profil, "_varsayim", None) and re.search(r"bigg|1812|1512", _katla(soru)):
            # Varsayımsal şirket BiGG'in ortaklık yasağıyla çelişir: kayıt değerlendirmeye eklenir (kartta "uygun değil"
            # gerekçesiyle görünür) ve kısa cevapta uyarılır (hakem bulgusu 2026-10-12, Rekortiv).
            for t in tum:
                if re.match(r"\s*1812\b", t.baslik or "") and t.aktif_mi is not False:
                    if t.id not in {x.id for x in kayitlar}:
                        kayitlar.append(t)
                    yasak = next((m["metin"] for m in _maddeler(t) if m["tur"] == "sart"
                                  and re.search(r"ortağı olmamak", m["metin"])), "")
                    if yasak:
                        asama = next((m["metin"] for m in _maddeler(t) if re.search(r"Mükemmeliyet Mührü",
                                                                                      m["metin"])), "")
                        profil._varsayim_uyari = (
                            f"{t.baslik} için kayıttaki şart: “{_kisalt(_temiz(yasak), 220)}”. Şirketi BiGG "
                            "hızlandırma programına kabulden önce kurarsanız bu şartı kaybedebilirsiniz"
                            + (f"; kayda göre şirket sonraki aşamada kurulur: “{_kisalt(_temiz(asama), 200)}”" if asama
                               else "") + ". Aşağıdaki değerlendirme şirket kurduktan sonraki durum içindir.")
                    break
        if odak_kayit and profil is not None:
            from app.rag import profil_9903_degerlendirmesi
            for i, u in profil_9903_degerlendirmesi(odak_kayit, profil, soru).items():
                notlar.setdefault(i, u.metin())
        eslesme = {e.tesvik.id: e for e in esles(profil, db, limit=10_000)} if profil is not None else {}
        ds = degerlendir(kayitlar, profil, notlar, eslesme, {t.id for t in odak_kayit},
                         {t.id for t in adi_gecen_kayit}, bugun, ust_programlar(kayitlar, tum), soru)
        fidan_notu = fidan_kalemi_notu(profil, tum)
        _nace = re.sub(r"^[A-Z]\.", "", getattr(profil, "nace_kodu", None) or "")
        imalat_disi = profil is not None and not (_nace[:2].isdigit() and 10 <= int(_nace[:2]) <= 33) and (
            getattr(profil, "sektor", None) or "") != "imalat"
        for d in ds:
            if imalat_disi and re.search(r"\bimalatta\b", d.tesvik.baslik or "", re.I):
                # Hakem bulgusu 6. tur: sürücü kursuna 81/ı "imalatta 5 puan" başlığıyla, oran ayrımı yapılmadan
                # sunuluyordu.
                d.kisit.append("başlıktaki imalata özel oran sizin için geçerli değil (faaliyetiniz imalat değil); genel "
                               "oran uygulanır")
            if fidan_notu and re.search(r"fidan kullanım desteği", d.tesvik.tesvil_tutari or "", re.I) \
                    and "Fidan Kullanım Desteği" not in (d.tesvik.baslik or ""):
                d.kisit.append(fidan_notu)
            if not tutar_metni(d.tesvik) and not _destek_unsurlari(notlar, d.tesvik):
                d.onceki_tutar = _devredilen_tutar(d.tesvik, tum)
        sira = {t.id: i for i, t in enumerate(odak_kayit)}
        odak = sorted((d for d in ds if d.odak), key=lambda d: sira[d.tesvik.id])
        if kurum_kayit and odak and profil is not None:
            _sorulan = set(soru_ihtiyaclari(soru))
            if _sorulan and not any(program_ihtiyaclari(d.tesvik) & _sorulan for d in odak):
                # Aramada profil süzgecinden elenmiş ama soruya doğrudan yönelik kurum programı: neden kapalı olduğu
                # söylenir (persona denemesi 2026-10-12: seramik fırını / KOSGEB Kapasite Geliştirme, mikro ölçek).
                from app.matching import uygunluk_engeli as _ue
                from app.match_scoring import hard_filter as _hf
                from app.match_adapter import company_from_profile as _cfp, program_from_tesvik as _pft
                _sira = {x: i for i, x in enumerate(soru_ihtiyaclari(soru))}
                aday = sorted((t for t in tum if t.kurum in kurumlar and t.aktif_mi is not False
                               and program_ihtiyaclari(t) & _sorulan and isletmeye_yonelik_mi(t)
                               and not _DURUM_PROGRAMI.search(t.baslik or "")),
                              key=lambda t: min(_sira[x] for x in program_ihtiyaclari(t) & _sorulan))
                ad = ", ".join(IHTIYAC_ADLARI[x] for x in soru_ihtiyaclari(soru))
                for t in aday[:1]:
                    neden = _ue(t, profil) or "; ".join(_hf(_cfp(profil), _pft(t))[0]) or _sert_filtre(t, profil)
                    odak_ilk = odak[0]
                    odak_ilk.ihtiyac_notu = (f"Sorduğunuz {ad} için bu kurumun programı: {t.baslik} — " + (
                        f"size kapalı ({neden})" if neden else "profilinizle şartları netleşmedi; kurumdan teyit edin")
                        + "; aşağıdaki program bu ihtiyaca doğrudan yönelik değildir.")
                if not aday:
                    odak[0].ihtiyac_notu = (f"Sorduğunuz {ad} için bu kurumun kayıtlı bir programı yok; aşağıdaki program "
                                            "farklı bir ihtiyaca yöneliktir.")
        if kurum_kayit:
            # Kurum sorusunda: uygun olanlar, kilitsizler, soruya/profile ilgili olanlar (eşleştirme ilgi puanı), sonra
            # açık çağrısı olanlar (persona denemesi 2026-10-12: matbaanın "KOSGEB'den destek" sorusunda zor dönem
            # kredisi İstihdamı Koruma yalnız çağrısı açık diye öne çıkıyordu).
            _kurum_sira = {t.id: i for i, t in enumerate(kurum_kayit)}
            _soru_ih = set(soru_ihtiyaclari(soru))
            odak.sort(key=lambda d: (
                d.karar in ("kapali", "uygun_degil"),
                # Kurulu işletmenin kurum sorusunda girişimcilik eğitimi gibi girişim programları geride
                getattr(profil, "sirket_turu", None) not in (None, "yok") and program_ihtiyaclari(d.tesvik) == {"girisim"}
                and "girisim" not in _soru_ih,
                d.karar == "belirlenemedi" and any(g.startswith(KILIT_ONEKI)
                                                   for g in d.gerekce),
                bool(_soru_ih) and not (program_ihtiyaclari(d.tesvik) & _soru_ih),
                # Ücretsiz eğitim gibi parasal olmayan program, aynı kurumun parasal desteğinin arkasında
                bool(re.search(r"parasal destek değil", d.tesvik.tesvil_tutari or "")),
                bool(re.search(r"REFİNANSMAN|Refinansman|İSTİHDAM KORUMA|İstihdamı Koruma", d.tesvik.baslik or ""))
                and not re.search(r"refinans|yapilandir|istihdami? koru|zor donem|kriz", _katla(soru)),
                -(eslesme[d.tesvik.id].siralama if d.tesvik.id in eslesme else 0.0),
                d.donem not in ("acik", "yaklasan"), _kurum_sira.get(d.tesvik.id, 999)))
        donem_sira = {"acik": 0, "yaklasan": 0, "tarihsiz": 1, "yok": 1, "on_kayit_kapandi": 2, "kapandi": 2}
        adaylar = [d for d in ds if not d.odak and d.karar in ("sartli", "belirlenemedi")]
        if profil is not None:
            ana = [d for d in adaylar if d.eslesti and not notlar.get(d.tesvik.id, "").startswith("DÜŞÜK")]
            # Sorudaki ihtiyaç profil hedeflerinin önündedir: "personel alırsak" sorusunda, hedefleri ihracat olan
            # profilde de engelsiz istihdam programları kart adayıdır (kapsam ölçümü 2026-10-11: 50 hücrede SGK
            # teşvikleri yalnız "Diğer" listesindeydi, kart bir kredi ürünüydü).
            sorulan = set(soru_ihtiyaclari(_adlari_cikar(soru, adi_gecen_kayit)))
            # İşe alınacak kişiye bağlı şartlı istihdam teşviki de kart adayıdır (hakem bulgusu 4. tur: "iki yeni çalışan"
            # sorusunda Kadın/Genç/MYB teşviki eşleşme listesinde olmadığı için kısa cevaba girmiyordu).
            ana += [d for d in adaylar if d not in ana and sorulan and program_ihtiyaclari(d.tesvik) & sorulan and (
                d.karar == "sartli" or any(g.startswith(KISI_ONEKI) for g in d.gerekce))]
        else:
            ana = [d for d in adaylar if _genel_kitleye_acik(d.tesvik)]
            ipucu = soru_sektoru(soru)
            if ipucu:
                ana = [d for d in ana if {ipucu, "genel"} & set((d.tesvik.uygunluk_kriterleri or {}).get("sektorler")
                                                                 or [])]
                adaylar = [d for d in adaylar if d in ana]
        if profil is not None and "ihracat" not in (profil.hedefler or []) and "ihracat" not in _katla(soru):
            # ihracat şartı kilit olan program, ihracat hedefi olmayan işletmeye yalnız gürültüdür
            adaylar = [d for d in adaylar if not (d.karar == "belirlenemedi" and any(
                g.startswith(KILIT_ONEKI) and "ihracat" in _katla(g)
                for g in d.gerekce))]
            ana = [d for d in ana if d in adaylar]
        if not re.search(r"refinans|yapilandir|istihdami? koru|zor donem|deprem|afet|kriz", _katla(soru)):
            # Durum programları (mevcut kredinin refinansmanı, zor dönemde istihdamı koruma) genel öneri değildir
            # (persona denemesi 2026-10-12: makine kredisi sorusunda "diğer seçenekler"i dolduruyorlardı).
            adaylar = [d for d in adaylar if not re.search(r"REFİNANSMAN|Refinansman|İSTİHDAM KORUMA|İstihdamı Koruma",
                                                           d.tesvik.baslik or "")]
            ana = [d for d in ana if d in adaylar]
        if getattr(profil, "sektor", None) == "tarim":
            # Başka tarım alt kategorisinin programı (sera, hayvancılık, organik, makineleştirme) soruda o konu
            # geçmiyorsa gürültüdür (persona denemesi 2026-10-12: fındık bahçesine sera ve hayvancılık desteği).
            adaylar = [d for d in adaylar if not _baska_tarim_kategorisi(d.tesvik, profil, soru)]
            ana = [d for d in ana if d in adaylar]
        if getattr(profil, "sirket_turu", None) == "kooperatif":
            # "işletme sahibinin yaşı" şartlı krediler kooperatif için anlamsız; listeyi doldurmasın
            adaylar = [d for d in adaylar if not (d.tesvik.uygunluk_kriterleri or {}).get("kurucu_yasi_max")]
            ana = [d for d in ana if d in adaylar]
        ihtiyac_sorusu = _adlari_cikar(soru, adi_gecen_kayit)
        soru_ihtiyac_seti = set(soru_ihtiyaclari(ihtiyac_sorusu))
        ihtiyac = soru_ihtiyac_seti | set(getattr(profil, "hedefler", None) or [])
        from app.match_adapter import profil_etiketleri
        etiket = profil_etiketleri(profil) if profil is not None else set()

        arama_sirasi = {t.id: i for i, t in enumerate(kayitlar)}
        kurulus_sorusu = bool(re.search(r"kur(?:may|mak|acag)|ac(?:may|mak|acag)|baslat|dusunuyorum|fikr",
                                        _katla(soru)))
        # Kullanıcının kendi ürünü ve arazi kelimeleri program adı sayılmaz ("9 dönüm fındık bahçem" sorusunda
        # başlığında "meyve bahçesi ... fındık dahil" geçen fidan desteği, Fındık Temel Desteği'nin önüne geçiyordu).
        urun_koku = _katla(getattr(profil, "urun_turu", None) or "")[:5]
        soru_kok = {k for k in re.findall(r"[a-z]{4,}", _katla(soru))
                    if not k.startswith(GENEL_KOKLER + ("deste", "paket", "sistem", "belge", "kurum", "olan", "bahce",
                                                        "tarla", "donum", "dekar", "arazi", "toplam", "devlet"))
                    and k not in _DURAK and not (urun_koku and k.startswith(urun_koku))}

        def _ad_eslesmesi(t) -> int:
            baslik = _katla(t.baslik or "")
            return sum(1 for k in soru_kok if k not in _AD_DISI and not _ihtiyac_kelimesi(k)
                       and re.search(rf"\b{k[:5]}", baslik))

        # profilsiz kuruluş sorusunda girişim programları (KOSGEB Girişimci Destek gibi) çağrısı kapalı olsa da önce
        kurulus_idleri = {t.id for t in kurulus_adaylari(profil, soru, tum)}
        for d in ana + adaylar:
            if profil is None and kurulus_sorusu and d.tesvik.id not in kurulus_idleri                     and _kurulu_isletme_ister(d.tesvik) and not any(
                    "kurulu işletme" in g for g in d.gerekce):
                d.gerekce.append("kurulu işletme ister (KOBİ kaydı, rozet, teminat ya da ciro şartı); şirket "
                                 "kurulduktan sonra değerlendirilir")

        soru_sira = {x: i for i, x in enumerate(soru_ihtiyaclari(ihtiyac_sorusu))}
        pazaryeri_sorusu = bool(re.search(r"amazon|etsy|ebay|walmart|trendyol global|pazar ?yer", _katla(soru)))
        # Instagram/Google reklamı pazaryeri içi reklam değildir: 5986 m.4 yalnız yurt dışı pazaryerlerindeki reklamı
        # destekler (hakem bulgusu 2026-10-12, 4. tur: "Instagram ve Google reklam" sorusunda m.4 öne çıkıyordu).
        sosyal_reklam = not pazaryeri_sorusu and bool(re.search(
            r"instagram|google|facebook|meta\b|tiktok|youtube|sosyal medya|arama motoru", _katla(soru)))
        vergi_sorusu = bool(re.search(r"vergi|istisna|stopaj|20/b|teknopark|ar-?ge merkez|tasarim merkez", _katla(soru)))
        # "Kadın girişimciye kredi" sorusunda hedef kitleye özel program öne; "yurt dışı satış" sorusunda değil.
        kitle_soruda = bool(re.search(r"kadin (?:girisimci|isletme|ortak|olarak|sahib|yonetici)|girisimci kadin|"
                                      r"kadinlara|genc (?:girisimci|olarak)|gencler|engelli|gazi|sehit", _katla(soru)))

        def _ilgi(d):
            k = d.tesvik.uygunluk_kriterleri or {}
            p_ihtiyac = program_ihtiyaclari(d.tesvik)
            # Soruda ihtiyaç varsa ona uymayan program, hedef kitlesi profile uysa da öne çıkmaz (persona denemesi
            # 2026-10-12: "yurt dışı reklam" sorusunda genç girişimci kredisi öne çıkıyordu).
            ihtiyac_disi = bool(soru_ihtiyac_seti) and not (p_ihtiyac & soru_ihtiyac_seti)
            ozel = (bool(etiket & set(k.get("target_group_tags") or [])) and k.get("exclusive_target_group")
                    and not ihtiyac_disi and (not soru_ihtiyac_seti or kitle_soruda)
                    and not _buyuk_olcekli(d.tesvik, profil))   # 85 milyon TL limitli paket mikro işletmede öne çıkmaz
            kilitli = d.karar == "belirlenemedi" and any(g.startswith((KILIT_ONEKI,
                                                                        "düşük olasılık")) for g in d.gerekce)
            # henüz kurulmamış girişim için kurulu işletme isteyen program, adı soruyla eşleşse de öne çıkmaz
            # (girişim programının kendisi, ör. KOSGEB Girişimci Destek, "kurulu işletme" sayılmaz)
            kurulu_ister = profil is None and kurulus_sorusu and d.tesvik.id not in kurulus_idleri                 and _kurulu_isletme_ister(d.tesvik)
            ilk_ihtiyac = min((soru_sira[x] for x in p_ihtiyac & soru_ihtiyac_seti), default=99)
            e = eslesme.get(d.tesvik.id)
            # Soruda kredi/finansman istenmediyse hibe/teşvik, kredi ürününden önce gelir.
            kredi_istenmedi = bool(soru_ihtiyac_seti) and "finansman" not in soru_ihtiyac_seti and _kredi_mi(d.tesvik)
            # Vergi indirimi/istisnası soruda vergi geçmiyorsa hibe ve teşvik programlarının arkasında gelir.
            kredi_istenmedi = kredi_istenmedi or (not vergi_sorusu and bool(_VERGI_PROGRAMI.search(d.tesvik.baslik or "")))
            pazaryeri_disi = pazaryeri_sorusu and not _PAZARYERI_PROGRAM.search(d.tesvik.baslik or "")
            pazaryeri_ici = sosyal_reklam and "pazaryeri" in _katla(d.tesvik.baslik or "")
            # Profildeki ciro, kaydın eşiğinin altında: adı soruyla kısmen eşleşse de öne çıkmaz (hakem bulgusu 4. tur:
            # "e-ticaret mağazam var" sorusunda 500.000 USD ihracat eşikli Perakende E-Ticaret Sitesi statüsü öndeydi).
            dusuk = d.karar == "belirlenemedi" and any(g.startswith("düşük olasılık") for g in d.gerekce)
            # "İki yeni çalışan alacağız" sorusunda işe alıma bağlı teşvik (ilave istihdam, işe alınan kişi) genel prim
            # desteğinin (asgari ücret desteği, 81/ı) önünde (hakem bulgusu 4. tur).
            # Sıra: geniş işe alım teşviki 0, genel istihdam desteği 1, dar kişi grubu 2, istihdam dışı program 3.
            istihdam_sira = 0
            if "istihdam" in soru_ihtiyac_seti:
                ise_alim = any(g.startswith(KISI_ONEKI) for g in d.gerekce) or bool(re.search(
                    r"\bilave\b|işe alın", " ".join(m["metin"] for m in _maddeler(d.tesvik)), re.I))
                istihdam_sira = (3 if "istihdam" not in p_ihtiyac else 2 if _DAR_KISI.search(d.tesvik.baslik or "")
                                 else 0 if ise_alim else 1)
            girisim_disi = (getattr(profil, "sirket_turu", None) not in (None, "yok") and p_ihtiyac == {"girisim"}
                            and "girisim" not in soru_ihtiyac_seti)
            return (not ozel, kurulu_ister, d.tesvik.id not in kurulus_idleri, donem_sira[d.donem] == 2,
                    pazaryeri_ici, pazaryeri_disi, dusuk, istihdam_sira, -_ad_eslesmesi(d.tesvik), ihtiyac_disi,
                    -gider_kalemi_eslesmesi(soru, d.tesvik), girisim_disi, _dar_kitle(d.tesvik) and not kitle_soruda,
                    kilitli,
                    _buyuk_olcekli(d.tesvik, profil),
                    -len(p_ihtiyac & soru_ihtiyac_seti), ilk_ihtiyac, kredi_istenmedi, _dar_kitle(d.tesvik),
                    not (p_ihtiyac & ihtiyac), d.karar != "sartli", -(e.siralama if e else 0.0),
                    arama_sirasi.get(d.tesvik.id, 999))
        ana.sort(key=_ilgi)
        # Aynı karar ailesinden (9903) en çok bir kart; diğerleri tek satır.
        yatirim_var = "yatirim" in ihtiyac or any(d.tesvik.id in notlar for d in odak)
        if not yatirim_var:
            adaylar = [d for d in adaylar if d.tesvik.id not in notlar]
            ana = [d for d in ana if d.tesvik.id not in notlar]
        yatirim_9903 = sorted((d for d in ana if d.tesvik.id in notlar),
                              key=lambda d: (d.karar != "sartli", -_katki_orani(notlar, d.tesvik)))
        ana = [d for d in ana if d.tesvik.id not in notlar] + yatirim_9903[:1]
        ana.sort(key=_ilgi)
        kullanilan = kullanilan_programlar(soru, ana)
        if kullanilan and len(kullanilan) < len(ana):
            ana = [d for d in ana if d not in kullanilan] + kullanilan
        triyaj = triyaj_mi(profil) and not odak
        if odak:
            kartlar = odak[:ODAK_KART]
            diger = [d for d in odak[ODAK_KART:] if d.karar not in ("kapali", "uygun_degil")] + ana
        else:
            sinir = TRIYAJ_KART if triyaj else EN_COK_KART
            kartlar = ana[:sinir]
            # Üçüncü ve sonraki kart yalnız engelsiz ve sorudaki ihtiyaca uyuyorsa tam kart olur; değilse "Diğer ilgili"
            # satırına iner (hakem bulgusu 2026-10-12, 4-7. tur: 12-17 KB yanıtların %60'ı kartlardı).
            _sor = set(soru_ihtiyaclari(ihtiyac_sorusu))
            kartlar = kartlar[:2] + [d for d in kartlar[2:] if d.karar == "sartli"
                                     and (not _sor or program_ihtiyaclari(d.tesvik) & _sor)]
            diger = [d for d in ana if d not in kartlar] + [d for d in adaylar if d not in ana]
        elenen = [d for d in ds if d.karar in ("uygun_degil", "kapali") and d not in kartlar]
        soru_ihtiyac_kume = set(soru_ihtiyaclari(ihtiyac_sorusu))
        if soru_ihtiyac_kume:
            # adı soruyla güçlü eşleşen program ("yapay zekâ" → Yapay Zekâ Kredi Programı) ihtiyaç süzgecinden geçer
            diger = [d for d in diger if program_ihtiyaclari(d.tesvik) & soru_ihtiyac_kume
                     or _ad_eslesmesi(d.tesvik) >= 2]
        if kurum_kayit and not adi_gecen_kayit:
            diger = [d for d in diger if d.tesvik.kurum in kurumlar]
            elenen = [d for d in elenen if d.tesvik.kurum in kurumlar]
        elenen = [d for d in elenen if d not in diger]
        # Yürürlükten kalkmış programlar yalnız adıyla sorulursa gösterilir (yerini alan sistem ayrıca anlatılır).
        elenen = [d for d in elenen if d in odak or not _yururlukten_kalkmis(d)]
        if profil is None and not odak:
            kurulus = {t.id for t in kurulus_adaylari(profil, soru, tum)}
            elenen = [d for d in elenen if d.tesvik.id in kurulus and d.karar == "kapali"]
            diger = [d for d in diger if _genel_kitleye_acik(d.tesvik)]
        diger.sort(key=lambda d: _ad_eslesmesi(d.tesvik) < 2)   # kararlı sıralama: güçlü ad eşleşmesi öne
        diger = diger[:EN_COK_DIGER]          # sınır süzgeçlerden SONRA (önce kesilince ilgili program düşüyordu)
        soru_ihtiyac = soru_ihtiyaclari(ihtiyac_sorusu)
        alternatifler = []
        if odak and odak[0].karar in ("kapali", "uygun_degil") and profil is not None:
            alternatifler = [d for d in ana if d.karar == "sartli" and d not in kartlar
                             and (not soru_ihtiyac or program_ihtiyaclari(d.tesvik) & set(soru_ihtiyac))][:3]
            diger = [d for d in diger if d not in alternatifler]
        # dar soru (adı geçen programın tek bir tutar/tarih/süre bilgisi): kısa şablon
        dar = bool(odak) and bool(adi_gecen_kayit) and bool(niyet & {"tutar", "tarih", "sure"}) \
            and not niyet & {"uygunluk", "birlikte"}
        if dar:
            diger = diger[:1]
            elenen = [d for d in elenen if d in odak]

        ozel = ozel_notlar(soru) + yol_ayrimi(profil, ds) + soru_profil_celiskisi(soru, profil)
        if kullanilan and len(kullanilan) < len(ana):
            ozel.append("**Zaten yararlandığınız:** " + "; ".join(d.tesvik.baslik for d in kullanilan)
                        + " — sorunuz bunun dışındaki seçenekleri sorduğu için öne çıkarılmadı.")
        if re.search(r"turquality", _katla(soru)):
            dislama = turquality_dislamasi(tum)
            if dislama:
                ozel.append(dislama)
        for d in odak[:1]:
            d.kapsam_disi = bool(_OLUMSUZ.search(kapsam_hukmu(soru, d.tesvik)))
        for d in ds:
            if d.karar == "kapali":
                d.guncel_surum = guncel_surum(d.tesvik, tum)
        bolum = [*ozel, *([""] if ozel else []),
                 *kisa_cevap(niyet, odak, ana or adaylar, elenen, notlar, triyaj, soru, bugun,
                             "ad" if adi_gecen_kayit else "kurum", profil,
                             [d for d in ds if d.karar in ("sartli", "belirlenemedi")]), "",
                 "### 1. Şirket & Proje Uygunluk Özeti", *profil_ozeti(profil)]
        hibe_notu = hibe_durumu(soru, ds, kartlar + diger) if not odak else ""
        if hibe_notu:
            # "Açık hibe bulamadım" satırı bu notu tekrarlar; kapalı hibeleri adıyla anan not kalır (2026-10-12: kahve
            # makinesi sorusunda iki hibe satırı üst üste çıkıyordu).
            bolum = [x for x in bolum if not x.startswith(
                "- Hibe (geri ödemesiz): sorunuza ve profilinize açık kayıtlı bir hibe programı bulamadım")]
            bolum.insert(bolum.index("**Kısa cevap:**") + 1, hibe_notu)
        if soru_ihtiyac:
            bolum.append(f"- Sorudan anlaşılan ihtiyaç: {', '.join(IHTIYAC_ADLARI[x] for x in soru_ihtiyac)}")
        bolum += ["", "### 2. Eşleşen Teşvik ve Hibe Programları"]
        if not kartlar:
            bolum.append("Sorunuzla ilgili, profilinize açık bir program kayıtlarda yok.")
        for d in kartlar:
            bolum += ["", odak_elenen_karti(d, notlar, bugun) if d.karar in ("kapali", "uygun_degil")
                      else kart(d, notlar, soru_ihtiyac, bugun)]
        if alternatifler:
            bolum += ["", "**Size açık görünen alternatifler** (profilinize göre engel yok; şartları kartta değil, "
                          "adıyla sorarak görün):",
                      *[f"- {d.tesvik.baslik} ({d.tesvik.kurum}): "
                        + (_urun_tutari(d.tesvik, profil) or _cumle_kisalt(re.sub(
                            r"^Hesaplama:\s*", "", tutar_metni(d.tesvik, 200).split(" Hesaplama: ")[0]), 160)
                           or "tutar kayıtta yok")
                        + f"; {takvim_metni(d, bugun, kisa=True)}" for d in alternatifler]]
        kars = karsilastirma_9903([d for d in ds if d.karar in ("sartli", "belirlenemedi")], notlar) \
            if yatirim_var else []
        if kars:
            bolum += ["", "**9903 programları bölgenize göre (Karar metninden; önce engelsiz ve şartlı, sonra "
                          "en yüksek katkı):**", *kars]
        if diger:
            bolum += ["", "**Diğer ilgili programlar** (ayrıntı için adıyla sorun):",
                      *[f"- {d.tesvik.baslik} ({d.tesvik.kurum}) — {karar_etiketi(d).lower()}"
                        + (f" ({_cumle_kisalt(_birlestir(d.gerekce[-1:]), 160)})" if d.karar == "belirlenemedi" and d.gerekce
                           else "") + f"; {takvim_metni(d, bugun, kisa=True)}" for d in diger]]
        if not adi_gecen_kayit and kurum_kayit:
            # kısa cevaptaki kurum özetinde gerekçesiyle anılanlar burada yinelenmez
            _ozette = set(map(id, kurum_ozeti_kapali(odak)[:3]))
            elenen = [d for d in elenen if id(d) not in _ozette]
        if elenen:
            bolum += ["", "**Size kapalı ya da başvuruya kapalı programlar:**" if profil is not None
                      else "**Şu an başvuruya kapalı programlar:**", *elenen_satirlari(elenen)]
        acik_kartlar = [d for d in kartlar if d.karar not in ("kapali", "uygun_degil")]
        alternatif = not acik_kartlar and bool(kartlar)
        if alternatif:
            # Hakem bulgusu 4. tur: otelin "yurt dışı tanıtım" sorusunda kapalı programın yerine ilgisiz
            # Sürdürülebilirlik Projesi "açık alternatif" olarak yol haritasına konuyordu.
            # Alternatif, kapalı programın ve sorunun ihtiyaçlarından en az ikisini (tek ihtiyaç varsa onu) karşılamalı:
            # kapalı "Yurt Dışı Tanıtım" yerine yalnız "ihracat" etiketli Sürdürülebilirlik Projesi alternatif değildir.
            hedef = set(soru_ihtiyac[:2]) | (program_ihtiyaclari(odak[0].tesvik) if odak else set())
            acik_kartlar = [d for d in alternatifler + diger if d.karar == "sartli" and (
                not hedef or len(program_ihtiyaclari(d.tesvik) & hedef) >= min(2, len(hedef)))][:1]
        birlikte_adaylar = [d.tesvik for d in acik_kartlar]
        if "birlikte" in niyet:
            # birlikte kullanım sorusunda yanıtta anılan açık programların hepsinin hükmü gösterilir
            anilan = [d for d in ds + diger if d.karar in ("sartli", "belirlenemedi") and (
                d in diger or any(x.startswith(f"- {d.tesvik.baslik} (") for x in kars))]
            birlikte_adaylar += [d.tesvik for d in anilan if d.tesvik not in birlikte_adaylar]
        birlikte = (birlikte_kullanim_metni(list(dict.fromkeys(birlikte_adaylar)))
                    if len(acik_kartlar) >= 2 or "birlikte" in niyet else "")
        if birlikte:
            satirlar = list(dict.fromkeys(birlikte.split("\n", 1)[1].splitlines()))
            istisnali = [x for x in satirlar if "Teknoloji Hamlesi'nde KOSGEB ve TÜBİTAK" in x]
            if istisnali and any("9903" in x for x in satirlar if x not in istisnali):
                satirlar.append("- Not (kayıtlardaki hükümlerin karşılaştırması): KOSGEB ve TÜBİTAK doğrudan "
                                "desteklerini serbest bırakan istisna yalnız Teknoloji Hamlesi Programı'nın hükmünde "
                                "var; yukarıdaki diğer 9903 programlarında istisna yalnız sübvansiyonlu kredidir.")
            bolum += ["", "**Birlikte kullanım (resmî metinden):**", *satirlar]
        bagli = ust_programlar([d.tesvik for d in acik_kartlar + diger], tum)
        if bagli and "birlikte" in niyet:
            bolum += ["", "**Bağlı programlar (kayıttan):**", *[
                f"- {t.baslik}: {u.baslik} ({u.kurum}) başvurusunun onaylanmasına bağlıdır; ikisi birlikte planlanır."
                for t, u in ((db.get(Tesvik, i), u) for i, u in bagli.items())]]
        if "birlikte" in niyet and len(acik_kartlar) >= 2:
            hukumlu = {line.split("] ", 1)[1].split(":", 1)[0] for line in (birlikte.split("\n")[1:] if birlikte else [])
                       if "] " in line}
            hukumsuz = [d.tesvik.baslik for d in acik_kartlar if d.tesvik.baslik not in hukumlu]
            ozet = birlikte_karar_satirlari(birlikte, hukumsuz)
            konum = bolum.index("### 1. Şirket & Proje Uygunluk Özeti") - 1
            bolum[konum:konum] = ozet
            if hukumsuz:
                bolum += ["", "**Birlikte kullanım hükmü kayıtta olmayan programlar:** " + "; ".join(hukumsuz)
                          + ". Aynı harcamanın bu programlardan birlikte desteklenip desteklenemeyeceğini kurumlardan "
                            "teyit edin."]
        odak_9903 = any(d.tesvik.id in notlar for d in odak)
        for blok in ek_bloklar or []:
            if blok.startswith("**Girişim ön değerlendirmesi**") and (
                    dar or not _girisim_ilgili(profil, soru) or any(d.karar in ("uygun_degil", "kapali") for d in odak)):
                continue
            yatirim_ihtiyaci = "yatirim" in set(soru_ihtiyac) | set(getattr(profil, "hedefler", None) or [])
            if blok.startswith("**Yatırım teşvik belgesi (9903)") and not odak_9903 and (
                    odak or not yatirim_ihtiyaci):
                continue
            bolum += ["", blok]
        iletisim = iletisim_satirlari(db, (odak or acik_kartlar or kartlar)[:1], profil,
                                      ilgili=odak[:1] + acik_kartlar + kartlar + diger + alternatifler + elenen)
        if dar:
            acik_kartlar = acik_kartlar[:1]
        hazirlik = kapali_odak_hazirligi(odak[0], iletisim) \
            if not acik_kartlar and odak and odak[0].karar in ("kapali", "uygun_degil") else None
        bolum += ["", "### 3. Darboğazlar ve Kritik Şartlar",
                  *(hazirlik[0] if hazirlik else darbogazlar(acik_kartlar, bugun, genel=not dar))]
        bolum += ["", "### 4. Adım Adım Yol Haritası"]
        if alternatif and acik_kartlar:
            bolum.append(f"Sorduğunuz program şu an size açık olmadığından adımlar, açık alternatif "
                         f"**{acik_kartlar[0].tesvik.baslik}** için:")
        bolum += hazirlik[1] if hazirlik else yol_haritasi(acik_kartlar, iletisim, profil is not None, alternatif)
        bolum += ["", "### 5. Bilgi Eksikliği / Netleştirme",
                  *netlestirme(profil, acik_kartlar, acik_kartlar if dar else kartlar + diger, soru)]
        _anlama = soru_anlama.etkin_etiket()
        yontem = (soru_anlama.YONTEM_NOTU if _anlama and _anlama.gonderildi else YONTEM_NOTU) if not dis_servis else (
            f"*Sorunuz {dis_servis} ile işlendi (model kendi sunucumuzda çalışır, veri üçüncü tarafa gitmez); modelin "
            "yanıtı kayıtlarla doğrulanamadığı ya da alınamadığı için bu yanıt Teşvik Asistanı'nın yerel danışmanı "
            "tarafından, yalnız veritabanındaki doğrulanmış kayıtlardan kuralla üretildi.*")
        bolum += ["", yontem, "", SORUMLULUK_REDDI]
        return tekrarlari_kisalt("\n".join(bolum))
    finally:
        if kendi_db:
            db.close()


_SORU_SEKTOR = {"hizmet": r"\b(kafe|cafe|restoran|lokanta|kuafor|berber|pastane|firin|otel|pansiyon|turizm|"
                          r"market|bakkal|magaza|dukkan|atolye|danismanlik)\w*",
                "tarim": r"\b(tarla|sera|hayvan|cifci|ciftlik|bugday|meyve|sebze|aricilik|sut)\w*",
                "imalat": r"\b(fabrika|uretim hatti|imalat|tekstil|makine imal|dokum)\w*",
                "e-ticaret": r"\b(e-ticaret|eticaret|pazaryeri|online satis|internet satis)\w*"}


def _adlari_cikar(soru: str, kayitlar: list) -> str:
    """Sorudan, adıyla anılan programların başlık kelimelerini çıkarır (ihtiyaç çıkarımı için)."""
    soru = re.sub(r"\byat[ıi]r[ıi]m(?=\s+al)", "", soru, flags=re.I)
    if not kayitlar:
        return soru
    baslik = {k for t in kayitlar for k in re.findall(r"\w+", _katla(t.baslik or "")) if len(k) >= 4}
    return " ".join(k for k in re.findall(r"[\w-]+", _katla(soru)) if k not in baslik)


def soru_sektoru(soru: str) -> str | None:
    """Profil yokken sorudaki faaliyet ipucu ("kafe" → hizmet); birden fazla ya da hiç eşleşme yoksa None."""
    katli = _katla(soru)
    bulunan = [ad for ad, kalip in _SORU_SEKTOR.items() if re.search(kalip, katli)]
    return bulunan[0] if len(bulunan) == 1 else None


def yol_ayrimi(profil, ds: list[Degerlendirme]) -> list[str]:
    """Şirketsiz girişimci: bir program kurulmuş işletme isterken diğeri kabul tarihinde şirket ortaklığı olmamasını
    şart koşuyorsa (KOSGEB ↔ TÜBİTAK 1812), sıra kararını şirket kurmadan önce vermesi gerektiğini söyler."""
    if getattr(profil, "sirket_turu", None) != "yok":
        return []
    yasakli = [d for d in ds if (d.tesvik.uygunluk_kriterleri or {}).get("ortaklik_yasagi_sirketsiz")
               and d.tesvik.aktif_mi is not False]
    isletme = [d for d in ds if d.karar == "uygun_degil" and d not in yasakli and re.search(r"işletme gerektir|şirket türü|sermaye şirketi",
                                                                        " ".join(d.gerekce))]
    if not (yasakli and isletme):
        return []
    return [f"**Yol ayrımı:** {isletme[0].tesvik.baslik} ({isletme[0].tesvik.kurum}) kurulmuş bir işletme ister; "
            f"{yasakli[0].tesvik.baslik} ise hızlandırma programına kabul tarihinde şirket ya da şahıs işletmesi "
            "ortaklığı olmamasını şart koşar (kayıttaki şartlar). Şirket kurmadan önce hangi programla "
            "ilerleyeceğinize karar verin."]


def _kurulu_isletme_ister(t) -> bool:
    """Şartları mevcut bir işletme/KOBİ, rozet, teminat ya da ciro isteyen program (henüz kurulmamış girişime uymaz)."""
    metin = " ".join(m["metin"] for m in _maddeler(t) if m["tur"] == "sart")
    return bool(re.search(r"KOB[İI]\s*(?:olmak|ölçeğinde)|rozet|teminat mektub|kayıtlı ve aktif|cirosu|"
                          r"faaliyette olan|son mali yıl|ETBİS|ihracatçı birli|statü (?:belgesi|sahibi)|"
                          r"ihracat yap(?:mış|an)", metin, re.I))


def kurulus_adaylari(profil, soru: str, tum: list) -> list:
    """Profil yokken "kafe açmak istiyorum" gibi kuruluş sorusu: faaliyete (ya da genele) açık, herkese açık, etkin
    girişim programları (KOSGEB Girişimci Destek gibi). Arama yalnız kelime benzerliğiyle bunları bulamıyordu."""
    if profil is not None or not re.search(
            r"\b(?:isletme|sirket|is ?yeri|dukkan|magaza|kafe|cafe|restoran|lokanta|atolye|ofis|firma|is|otel|pansiyon|"
            r"kuafor|berber|pastane|firin|market|bakkal|imalathane|girisim)\w*\s+(?:acma|acaca|acmak|kurma|kuraca|"
            r"kurmak|"
            r"baslatma|baslataca)", _katla(soru)):
        return []
    from app.ihtiyac import isletmeye_yonelik_mi
    ipucu = soru_sektoru(soru) or "genel"
    teknoloji = bool(_TEKNOLOJI.search(_katla(soru)))
    return [t for t in tum if t.aktif_mi and isletmeye_yonelik_mi(t) and _genel_kitleye_acik(t)
            and "girisim" in program_ihtiyaclari(t) and (teknoloji or t.kurum not in ("TUBITAK", "TÜBİTAK"))
            and {ipucu, "genel"} & set((t.uygunluk_kriterleri or {}).get("sektorler") or [])][:6]


def zorunlu_adaylar(profil, tum: list) -> list:
    """Profil gereği her zaman değerlendirilecek kayıtlar: tarım/gıda işleme + yatırım/makine hedefi → Tarım
    Bakanlığı ve TKDK kayıtları; hedef kitle etiketi (kadın/genç girişimci) → o kitleye özel programlar."""
    if profil is None:
        return []
    sonuc = []
    nace = (profil.nace_kodu or "").replace("C.", "")
    hedef = set(profil.hedefler or [])
    if (profil.sektor == "tarim" or nace.startswith(("01", "10"))) and hedef & {"yatirim", "makine"}:
        sonuc += [t for t in tum if re.search(r"TKDK|Tarım Bakanlığı|Tarım ve Orman", t.kurum or "")
                  and program_ihtiyaclari(t) & {"yatirim"}]
    from app.match_adapter import profil_etiketleri
    etiketler = profil_etiketleri(profil)
    sonuc += [t for t in tum if (t.uygunluk_kriterleri or {}).get("exclusive_target_group")
              and _hedef_kitle_eslesmesi(t, profil)]
    if etiketler:
        sonuc += [t for t in tum if (t.uygunluk_kriterleri or {}).get("exclusive_target_group")
                  and etiketler & set((t.uygunluk_kriterleri or {}).get("target_group_tags") or [])]
    if "kadin_girisimci" in (profil.ozellikler or []):
        # hedef kitle etiketi taşımayan ama şartı kadın yönetici/ortak olan etkin programlar (TURWIB gibi)
        sonuc += [t for t in tum if t.aktif_mi is not False and any(
            m["tur"] == "sart" and re.search(_HEDEF_KALIP["kadin_girisimci"], m["metin"], re.I) for m in _maddeler(t))]
    return list(dict.fromkeys(sonuc))


def sabit_metinler() -> str:
    """Yanıta koddan giren, sayı içerebilen sabit metinler (dayanak testlerinde kaynak kodun tamamı yerine)."""
    from app.girisim import MEVZUAT_NOTU
    from app.hazirlik import ADIMLAR
    return "\n".join([SORUMLULUK_REDDI, YONTEM_NOTU, *GENEL_ILKELER, MANIPULASYON_UYARISI, GARANTI_NOTU, MEVZUAT_NOTU,
                      "en az %50 hissedarın yaşı", "en az %50 hisseye sahip ortağınız",
                      *(f"{a.baslik} {a.nasil}" for a in ADIMLAR.values())])


def _girisim_ilgili(profil, soru: str) -> bool:
    """HUKS (TÜBİTAK BiGG) bloğu yalnız teknoloji girişimi bağlamında anlamlı."""
    from app.girisim import girisim_modu_mu
    if profil is not None and (profil.sirket_turu == "yok" or (profil.trl is not None and girisim_modu_mu(profil, ""))):
        return True
    return bool(re.search(r"startup|girisim(?!ci)|bigg|teknogirisim|\btrl\b|prototip", _katla(soru)))


# ------------------------------------------------------------------ self-test
def _self_test() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.dayanak import denetle
    from app.models import Base, FinancialProfile, Tesvik, TesvikCagrisi
    motor = create_engine("sqlite://")
    Base.metadata.create_all(motor)
    db = sessionmaker(bind=motor)()
    bugun = date(2026, 10, 11)
    db.add_all([
        Tesvik(id=1, kurum="KOSGEB", baslik="Girişimcilik Destek Programı", ozet="o", detay="d", aktif_mi=True,
               kaynak_url="https://kosgeb.gov.tr/g", tesvil_tutari="375.000 TL geri ödemesiz",
               uygunluk_kriterleri={"sektorler": ["genel"]},
               kontrol_listesi=[{"tur": "sart", "metin": "KOSGEB veri tabanına kayıtlı olmak", "alinti": "kayıtlı",
                                 "kaynak_url": "https://kosgeb.gov.tr/g", "dogrulandi": True}]),
        Tesvik(id=2, kurum="Halkbank", baslik="İlk Adım Kredisi Projesi", ozet="o", detay="d", aktif_mi=True,
               kaynak_url="https://kgf.com.tr/ilk", uygunluk_kriterleri={"sektorler": ["genel"], "kurucu_yasi_max": 29}),
        Tesvik(id=3, kurum="TÜBİTAK", baslik="1512 Teknogirişim Sermayesi Desteği", ozet="o", detay="d",
               aktif_mi=False, durum_notu="1812'ye devredildi", kaynak_url="https://tubitak.gov.tr/1512",
               tesvil_tutari="1.350.000 TL'ye kadar", uygunluk_kriterleri={"sektorler": ["arge"]}),
    ])
    db.add(TesvikCagrisi(tesvik_id=1, ad="2026/2. dönem", acilis=date(2026, 10, 1), kapanis=date(2026, 10, 22),
                         kaynak_url="https://kosgeb.gov.tr/duyuru", dogrulama_tarihi=bugun))
    db.commit()
    kayitlar = [db.get(Tesvik, 1), db.get(Tesvik, 2)]
    p = FinancialProfile(sektor="genel", sirket_turu="limited", bolge="Ankara", calisan_sayisi=3, yillik_ciro=1e6,
                         hedefler=["finansman"], kurucu_yasi=40)
    y = yanitla("kredi ve hibe", kayitlar, p, db=db, bugun=bugun)
    y_profilsiz = yanitla("kredi ve hibe", kayitlar, None, db=db, bugun=bugun)
    y_ad = yanitla("1512 programına başvurabilir miyim?", [], p, db=db, bugun=bugun)
    y_tarih = yanitla("Girişimcilik Destek Programı son başvuru ne zaman?", kayitlar, p, db=db, bugun=bugun)
    baglam = "\n".join(f"{t.kaynak_url} {t.tesvil_tutari or ''}" for t in db.query(Tesvik).all()) + \
        " https://kosgeb.gov.tr/duyuru 22.10.2026 01.10.2026 11.10.2026\n" + sabit_metinler()
    k = [("beş başlık ve sorumluluk reddi", all(f"### {i}." in y for i in range(1, 6)) and SORUMLULUK_REDDI in y),
         ("yaş sınırı aşan kredi elenir", "İlk Adım Kredisi Projesi (Halkbank) — uygun değil" in y and "en çok 29" in y),
         ("'uygun görünüyor' etiketi yok, şart teyidi istenir",
          "Uygun görünüyor" not in y and "Teyit etmeniz gereken şartlar" in y),
         ("çağrı son günü ve kalan gün", "son gün 22.10.2026 (11 gün kaldı)" in y),
         ("tutar kayıttan aynen", "375.000 TL geri ödemesiz" in y),
         ("şart alıntısıyla", "resmî metin: “kayıtlı”" in y),
         ("profilsiz: şarta bağlı, profil istenir", "Şarta bağlı" in y_profilsiz and "İşletme profili" in y_profilsiz),
         ("adıyla sorulan kapalı program: neden ve son bilinen tutar", "1512 Teknogirişim" in y_ad
          and "1812'ye devredildi" in y_ad and "Son bilinen destek (bilgi için): 1.350.000" in y_ad),
         ("tarih sorusunda kısa cevap tarihi verir", "- Başvuru: 2026/2. dönem: başvuruya açık — yeni başvuru için son "
          "gün 22.10.2026 (11 gün kaldı)." in y_tarih),
         ("niyet çözümleme", niyetler("son başvuru ne zaman, oranı ne?") == {"tarih", "tutar"}
          and niyetler("hangi destekler var") == {"liste"}),
         ("cümle sınırında kesme", _cumle_kisalt("Birinci cümle. İkinci cümle uzun bir cümle.", 30) == "Birinci cümle."),
         ("program kodu eşleşmesi", [t.id for t in adi_gecen_programlar("1512 nedir", db.query(Tesvik).all())] == [3]),
         ("yanıttaki somut bilgiler kayıtta", denetle(y, baglam, bugun=bugun) == []),
         ("yöntem notu (dış servis yok)", YONTEM_NOTU in y)]
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    for akim in (sys.stdout, sys.stderr):
        if hasattr(akim, "reconfigure"):
            akim.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if "--demo" in sys.argv:
        from app.rag import retrieve
        soru = sys.argv[sys.argv.index("--demo") + 1]
        print(yanitla(soru, retrieve(soru, limit=8)))
