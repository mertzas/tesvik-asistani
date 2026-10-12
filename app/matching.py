"""
Finansal profil (FinancialProfile) ile tesvikler tablosundaki
uygunluk_kriterleri arasinda skor bazli esleme yapar.

/api/sor endpoint'indeki serbest metin RAG aramasindan farkli olarak, burada
kullanicinin yapilandirilmis profili (sektor, hedef, ciro, calisan sayisi)
uzerinden deterministik bir skorlama yapilir; LLM sadece sonucu insan
diline cevirmek icin kullanilabilir (bkz. rag.answer), skorlama kendisi
kural tabanlidir ve tekrarlanabilir/aciklanabilir olmalidir.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session, selectinload

import re

from app.girisim import SIRKET_TURLERI
from app.ihtiyac import isletmeye_yonelik_mi, program_ihtiyaclari
from app.match_adapter import company_from_profile, program_from_tesvik
from app.match_scoring import hard_filter, score_program
from app.kobi import kobi_sinifi
from app.tesvik_9903_uygunluk import kayit_icin as uygunluk_9903
from app.nace_hiyerarsi import kisim_duzeyinde, sector_match
from app.models import FinancialProfile, Tesvik
from app.urun_sektor_anahtarlari import (
    BELIRTILMEMIS_KATEGORILER,
    urun_turunden_tarim_kategorisi,
)

# Turkce karakterleri sadelestirerek esnek eslesme yapmak icin (bkz. app/ihracat_fiyatlari.py).
_TR_CEVIRI = str.maketrans("çÇğĞıİöÖşŞüÜ", "cCgGiIoOsSuU")


def _sadelestir(metin: str) -> str:
    return metin.translate(_TR_CEVIRI).lower().strip()


@dataclass
class TesvikEslesmeSonucu:
    tesvik: Tesvik
    skor: float
    gerekce: list[str] = field(default_factory=list)
    eksik_kriterler: list[str] = field(default_factory=list)
    # app/match_scoring.py'nin 0-100 puanı (NACE uyumu %45, bölge %25, ölçek %20, destek
    # türü %10). Ana skor eşit kaldığında sıralamayı belirler; ana skoru değiştirmez.
    ince_skor: float = 0.0
    # Sıralama puanı: 1,0 tavanı uygulanmadan önceki toplam eksi cezalar. Tavan (görüntü) "sektör + hedef + çalışan"
    # toplayan her programı 1,0'da eşitleyip hedef uyumu farkını siliyordu (persona denemesi 2026-10-12: makine
    # hedefli matbaada Refinansman Kefalet 1., KGF yatırım kredisi 18.).
    siralama: float = 0.0


# "₺100.000", "100.000 TL", "₺100.000 - ₺500.000", "100.000–500.000 TL" (başta/sonda boşluk serbest).
_SADE_TUTAR = re.compile(r"₺?\s*\d[\d.,]*\s*(?:TL)?(?:\s*[-–]\s*₺?\s*\d[\d.,]*\s*(?:TL)?)?", re.IGNORECASE)


def _tutari_parse(tesvil_tutari: str | None) -> tuple[float | None, float | None]:
    """'₺100.000 - ₺500.000' gibi bir araligi (min, max) TL olarak cikarmaya calisir.

    YALNIZCA metnin tamamı sade bir tutar ya da aralıksa okunur. Denetim 2'de bu alana kaynaktan
    açıklayıcı metin yazıldı ("5973 sayılı Karar ...; 15.102 TL ifadesi 2022 yılına aitti", "%100 geri
    ödemesiz; program üst limiti toplam 700.000 TL ..."); içindeki TÜM sayıları toplamak karar numarası,
    yıl ve yüzdeyi tutar sanıyordu (tarayıcı denemesi 2026-10-07: metal işleme KOBİ'sine "tahmini toplam
    ₺2.022 - ₺15.102", çiftçinin toplamına YÖNDE'den 100-700.000 TL). Açıklayıcı metin toplama girmez."""
    if not tesvil_tutari:
        return None, None

    import re

    if not _SADE_TUTAR.fullmatch(tesvil_tutari.strip()):
        return None, None
    sayilar = re.findall(r"[\d.,]+", tesvil_tutari.replace("₺", ""))
    degerler = []
    for s in sayilar:
        temiz = s.replace(".", "").replace(",", ".")
        try:
            degerler.append(float(temiz))
        except ValueError:
            continue

    if not degerler:
        return None, None
    if len(degerler) == 1:
        return degerler[0], degerler[0]
    return min(degerler), max(degerler)


def _kurum_ile_cesitlendir(sonuclar: list["TesvikEslesmeSonucu"]) -> list["TesvikEslesmeSonucu"]:
    """Ayni skora sahip sonuclar arasinda TEK bir kurumun listeye hakim
    olmasini engeller. Ornegin TUBITAK basliklari rakamla basladigi icin
    ("1000 - ...") alfabetik siralamada KOSGEB/KGF'den (harfle baslayan)
    HER ZAMAN once gelir; 66 TUBITAK kaydi karsisinda 9 KOSGEB + 79 KGF
    kaydi limit=10'a hic giremezdi. Bunun yerine esit-skorlu bloklar
    icinde kurumlara gore round-robin dagitim yapiyoruz (skor sirasi
    bloklar arasinda korunur, sadece ayni blok icinde kurum cesitliligi
    saglanir)."""
    sonuc: list[TesvikEslesmeSonucu] = []
    i = 0
    n = len(sonuclar)
    while i < n:
        j = i
        while j < n and sonuclar[j].skor == sonuclar[i].skor:
            j += 1
        blok = sonuclar[i:j]

        kurum_gruplari: dict[str, list[TesvikEslesmeSonucu]] = {}
        for s in blok:
            kurum_gruplari.setdefault(s.tesvik.kurum, []).append(s)

        # Her turda kurumlar, sıradaki kayıtlarının ince_skor'una göre dizilir; eşitlikte
        # kurum adı. Böylece round-robin kurum çeşitliliğini korur ama bloğun ince_skor
        # sırasını (NACE/bölge/ölçek uyumu) kurumlar arasında da ezmez. Ölçüm 2026-10-07:
        # alfabetik tur sırası (KGF → TÜBİTAK → Ticaret Bakanlığı) NACE 62 uyumlu 10962
        # kaydını (ince 76.5) 49.5'lik KGF/TÜBİTAK kayıtlarının arkasına atıyordu.
        while any(kurum_gruplari.values()):
            tur = sorted((k for k, g in kurum_gruplari.items() if g),
                         key=lambda k: (-kurum_gruplari[k][0].ince_skor, k))
            for k in tur:
                sonuc.append(kurum_gruplari[k].pop(0))

        i = j
    return sonuc


HEDEF_SEKTOR_ETIKETLERI = {"ihracat", "arge", "e-ticaret"}

# 9903 ön değerlendirmesinin esles skoruna etkisi (0-1 ölçek). "dusuk" bir programı
# KGF/KOSGEB genel programlarının (0.30-0.60) altına indirir ama gizlemez.
UYGUNLUK_9903_SKOR_ETKISI = {"uygun": 0.10, "sartli": 0.0, "bilinmiyor": -0.05, "dusuk": -0.45}

# Kayit metninden (hedef_kitle + basvuru_sartlari) okunan uygunluk kaliplari.
# Her kalip, veritabanindaki gercek sart cumlelerinden alinmistir (2026-10-07):
#   - araci/ekosistem kurulusu: "TEKMER işletici kuruluşu ve TGB yönetici şirketi
#     yararlanabilir" (KOSGEB Teknoloji Merkezi), "Teknoloji Transfer Ofisleri" (1513,
#     1612), "üniversiteye bağlı birimler" -> son kullanici isletmeye verilmez
#   - sirketi olana kapali: "HERHANGİ BİR İŞLETMENİN ortaklık yapısında yer almamak
#     (şirket kurulduysa başvurulamaz)" (1512), "ortaklık yapısında yer alan kişiler
#     başvuru yapamaz" (1812)
#   - sirketsize kapali: "sermaye şirketi statüsünde/olmak" (1507, 1501, 1601),
#     "bireysel girişimci başvuramaz" (1601), "şirketleşmemiş girişim yararlanıcı
#     tanımına girmez" (10962), "KOSGEB veri tabanına kayıtlı" (KOSGEB), "KOBİ
#     niteliklerine sahip olması" (KGF)
_ARACI_KURULUS = re.compile(
    r"işletici kuruluş|yönetici şirket|teknoloji transfer ofis|uygulayıcı kuruluş|"
    r"üniversiteye bağlı birim", re.I)
# "yer almamak" (1512) ve "yer alan kişiler başvuru yapamaz" (1812) ikisini de kapsar.
_SIRKETI_OLANA_KAPALI = re.compile(
    r"ortaklık yapısında yer al|şirket kurulduysa başvurulamaz", re.I)
_SIRKETSIZE_KAPALI = re.compile(
    r"sermaye şirketi (?:statüsünde|olmak|olması)|bireysel girişimci başvuramaz|"
    r"yararlanıcı tanımına girmez|KOSGEB veri tabanı|KOBİ (?:niteliklerine|olmak|olması|tanımın)", re.I)
# Kefalet/kredi ve KOSGEB programlari tanim geregi bir ISLETMEYE verilir; SGK/ISKUR istihdam
# tesvikleri de ISVERENE verilir (Denetim 2 Asama B, 2026-10-07: sirketsiz girisimciye
# "Issizlik Odenegi Alanlarin Istihdami Tesviki" ilk 3'te geliyordu).
_ISLETME_GEREKTIREN_KURUMLAR = {"KGF", "KOSGEB", "SGK / İŞKUR",
                                # 9903 yatırım teşvik belgesi bir işletmeye düzenlenir (persona denemesi
                                # 2026-10-08: şirketsiz girişimciye 9903 kayıtları skor 0 ile listeleniyordu).
                                "Sanayi ve Teknoloji Bakanlığı",
                                # 5973/5986/10962 sayılı Kararlar başvuranı "TTK'ya göre kurulmuş şirket" diye tanımlar;
                                # Eximbank kredileri ihracatçı firmaya, KTB teşvikleri belgeli işletmeye verilir (kapsam
                                # ölçümü 2026-10-12: şirketsiz girişimciye tasarım şirketi ve Eximbank destekleri çıkıyordu).
                                "Ticaret Bakanlığı", "Türk Eximbank", "Kültür ve Turizm Bakanlığı"}
_SAHIS_URUNU = re.compile(r"şahıs\s+işletmeleri", re.IGNORECASE)
_BUYUK_ISLETMEYE_ACIK = re.compile(r"büyük\s+işletme", re.IGNORECASE)


ILGI_CEZASI = 0.3
_ARGE_NACE = ("62", "63", "72")
_BUYUK_9903 = re.compile(r"Stratejik Hamle|Öncelikli Yatırımlar|Teknoloji Hamlesi", re.IGNORECASE)


def _arge_sinyali(profil, hedefler: set[str]) -> bool:
    nace = str(getattr(profil, "nace_kodu", None) or "").split(".")[0]
    return getattr(profil, "sektor", None) == "arge" or "arge" in hedefler or nace in _ARGE_NACE


def _ilgi_engeli(t, profil, hedefler: set[str], olcek_sinifi: str | None) -> str | None:
    """Program bu profile uygun olabilir ama ilgisi zayıf: sıralamada geri alınır (eşleşmeden atılmaz)."""
    baslik = t.baslik or ""
    sektor = getattr(profil, "sektor", None)
    if re.search(r"Yapay Zek", baslik, re.IGNORECASE) and not _arge_sinyali(profil, hedefler):
        return "Yapay zekâ yatırımına yönelik; profilinizde Ar-Ge/yazılım hedefi yok."
    if t.kurum == "SGK / İŞKUR" and hedefler and "istihdam" not in hedefler:
        return "İşe alım teşviki; hedeflerinizde istihdam yok."
    if t.kurum == "KOSGEB" and sektor == "tarim" and re.search(r"YÖNDE|Yönderlik", baslik):
        return "Yönderlik/yalın dönüşüm hizmeti sanayi işletmelerine yöneliktir."
    if t.kurum in ("TUBITAK", "TÜBİTAK") and sektor not in ("imalat", "arge") and not _arge_sinyali(profil, hedefler):
        return "Ar-Ge projesi desteği; profilinizde Ar-Ge hedefi yok."
    if t.kurum == "Sanayi ve Teknoloji Bakanlığı" and _BUYUK_9903.search(baslik) and olcek_sinifi in ("mikro", "kucuk"):
        return "Büyük ölçekli yatırım programı (yüksek asgari yatırım tutarı); işletme ölçeğiniz mikro/küçük."
    # Belirli bir duruma yönelik krediler: mevcut kredinin yeniden yapılandırılması, istihdamı koruma (zor dönem).
    # Hedefte karşılığı yoksa genel öneri değildir (persona denemesi 2026-10-12, matbaa).
    if re.search(r"Stratejik Ürün", baslik) and not _arge_sinyali(profil, hedefler):
        return "Stratejik ürün listesindeki yüksek teknolojili ürünlerin üretimine yönelik; profilinizde Ar-Ge hedefi yok."
    if re.search(r"REFİNANSMAN|Refinansman", baslik):
        return "Mevcut kredilerinizin yeniden finansmanı içindir; yeni yatırım ya da işletme kredisi değildir."
    if re.search(r"İSTİHDAM KORUMA|İstihdamı Koruma", baslik) and "istihdam" not in hedefler:
        return "Zor dönemde çalışan sayısını korumaya yönelik; hedeflerinizde istihdam yok."
    return None


def _ihracat_engeli(t, profil) -> str | None:
    """Kayıtta asgari önceki yıl ihracatı (USD) varsa ve profilin hazırlık kaydındaki bilinen ihracat altındaysa
    program kapalıdır (5986 m.8: 1 milyon USD; m.5 statüsü: 500 bin USD). Bilinmiyorsa elemez. Statü sahibi
    (perakende_statusu) m.5 için muaftır."""
    asgari = (t.uygunluk_kriterleri or {}).get("min_onceki_yil_ihracat_usd")
    e = ((getattr(profil, "hazirlik", None) or {}).get("eihracat") or {})
    bilinen = e.get("onceki_yil_ihracat_usd")
    if asgari is None or bilinen is None or bilinen >= asgari:
        return None
    if (t.uygunluk_kriterleri or {}).get("statu_ile_muaf") and e.get("perakende_statusu"):
        return None
    return f"önceki yıl en az {asgari:,.0f} USD ihracat gerekir (beyanınız {bilinen:,.0f} USD)".replace(",", ".")


def _sart_metni(t) -> str:
    return " ".join([t.hedef_kitle or "", *(t.basvuru_sartlari or [])])


def _sart_maddeleri(t) -> list[str]:
    """Kontrol listesindeki şart maddeleri ve eski başvuru şartları (ölçülebilir eşikler için)."""
    return [*(t.basvuru_sartlari or []),
            *(m.get("metin") or "" for m in (t.kontrol_listesi or []) if isinstance(m, dict) and m.get("tur") == "sart")]


_SAYI_KELIME = {"bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9,
                "on": 10, "yirmi": 20, "otuz": 30, "elli": 50, "yüz": 100}
_SAYI = r"(\d[\d.]*|" + "|".join(_SAYI_KELIME) + r")"
_CALISAN_EN_AZ = re.compile(rf"en az {_SAYI}\s+(?:tam zaman eşdeğer\s+)?(?:sigortalı\s+)?(?:çalışan|işçi)", re.I)
_CALISAN_FAZLA = re.compile(r"\b(on|beş|yirmi|elli|yüz)(?:dan|den|tan|ten) fazla (?:çalışan|işçi|sigortalı)", re.I)
_CALISAN_ARALIK = re.compile(r"(\d[\d.]*)\s*(?:ile|-|–)\s*(\d[\d.]*)\s*arasında\s+(?:çalışan|personel|işçi)", re.I)
_MAGAZA_EN_AZ = re.compile(rf"en az {_SAYI}\s+(?:fiziksel\s+)?(?:perakende\s+)?mağaza", re.I)


def _sayi(x: str) -> int:
    x = x.lower()
    return _SAYI_KELIME[x] if x in _SAYI_KELIME else int(x.replace(".", ""))


def _olcek_esigi_engeli(t, profil) -> str | None:
    """Şart metnindeki çalışan/mağaza eşiği profildeki çalışan sayısıyla karşılaştırılır (persona denemesi
    2026-10-12: 6 çalışanlı matbaaya "ondan fazla çalışan" isteyen SGK teşviki, 15 çalışanlı mağazaya "en az 100
    fiziksel mağaza" isteyen zincir mağaza desteği, KOBİ'ye 250-3.000 çalışanlı firmalara açık AYB kredisi "engel
    yok" diye sunuluyordu). Çalışan sayısı bilinmiyorsa elemez."""
    n = getattr(profil, "calisan_sayisi", None)
    if n is None:
        return None
    for metin in _sart_maddeleri(t):
        m = _CALISAN_ARALIK.search(metin)
        if m:
            alt, ust = int(m.group(1).replace(".", "")), int(m.group(2).replace(".", ""))
            if not alt <= n <= ust:
                return f"{alt}-{ust} arasında çalışanı olan işletmelere yönelik (profilinizde {n})"
        m = _CALISAN_EN_AZ.search(metin)
        if m and n < _sayi(m.group(1)):
            return f"en az {_sayi(m.group(1))} çalışan şartı (profilinizde {n})"
        m = _CALISAN_FAZLA.search(metin)
        if m and n <= _sayi(m.group(1)):
            return f"şartta “{m.group(0)}” aranıyor (profilinizde {n} çalışan)"
        m = _MAGAZA_EN_AZ.search(metin)
        if m and n < _sayi(m.group(1)):
            return (f"en az {_sayi(m.group(1))} mağazalı zincirlere yönelik; {n} çalışanlı bir işletme bu ölçekte "
                    "mağaza ağına sahip olamaz")
    return None


# 10962 sayılı Karar, Hizmet Sektörleri Atılım Programı: "bilişim, danışmanlık, dijital aracılık, eğitim, finansal
# teknolojiler, fuarcılık ve kongre turizmi, kültürel ve kreatif endüstriler, lojistik ve taşımacılık, sağlık ve spor
# turizmi, teknik müşavirlik veya uygunluk değerlendirme sektörlerinde faaliyet gösteren" yararlanıcılar (Karar metni,
# kayıtların bilgi maddesinde alıntılı). NACE Rev.2 karşılıkları; liste dışı faaliyet (konaklama 55, perakende 47,
# imalat 10-33, tarım 01-03) kapsam dışıdır. Persona denemesi 2026-10-12: butik otele ve e-ticaret mağazasına
# Atılım desteklerinde "engel yok" deniyordu.
ATILIM_SEKTORLERI = ("bilişim, danışmanlık, dijital aracılık, eğitim, finansal teknolojiler, fuarcılık ve kongre "
                     "turizmi, kültürel ve kreatif endüstriler, lojistik ve taşımacılık, sağlık ve spor turizmi, teknik "
                     "müşavirlik, uygunluk değerlendirme")
ATILIM_NACE = ("58", "59", "60", "62", "63", "64", "66", "69", "70.2", "71", "73", "74.1", "74.2", "79", "82.3", "85",
               "86", "90", "91", "93", "49", "50", "51", "52", "53")
_SEKTOR_ATILIM_DISI = {"tarim", "imalat", "e-ticaret", "perakende"}


def _atilim_kapsam_engeli(t, profil) -> str | None:
    if not (t.kurum == "Ticaret Bakanlığı" and re.search(r"Atılım Programı|10962 sayılı Karar, Hizmet Sektörleri Atılım",
                                                          t.baslik or "")):
        return None
    nace = re.sub(r"^[A-Z]\.", "", getattr(profil, "nace_kodu", None) or "")
    if nace[:2].isdigit():
        if any(nace.startswith(k) for k in ATILIM_NACE):
            return None
        return f"Hizmet Sektörleri Atılım Programı yalnız şu sektörlere açık: {ATILIM_SEKTORLERI} (NACE {nace} kapsam dışı)"
    if (getattr(profil, "sektor", None) or "").lower() in _SEKTOR_ATILIM_DISI:
        return f"Hizmet Sektörleri Atılım Programı yalnız şu sektörlere açık: {ATILIM_SEKTORLERI}"
    return None


# Kültür ve Turizm Bakanlığı belgeli işletme programları: turizm belgeli tesis (2634 sayılı Kanun) ve kültür yatırım/
# girişim belgesi (5225 sayılı Kanun). Faaliyet bu alanlarda değilse kapalıdır (persona denemesi 2026-10-12: sürücü
# kursunun panelinde iki program ilk sıradaydı). NACE: konaklama 55, yiyecek-içecek 56, seyahat acentesi 79, spor/
# eğlence 93; kültür: film 59, yayıncılık 58.1/60, yaratıcı sanatlar 90, kütüphane/müze 91.
_TURIZM_NACE = ("55", "56", "79", "93")
_KULTUR_NACE = ("58.1", "59", "60", "90", "91")


def _kultur_turizm_engeli(t, profil) -> str | None:
    baslik = t.baslik or ""
    # Turizm işletme belgeli tesislere verilen destekler başka kurumlarda da var (SGK Turizm Ücret Desteği; hakem
    # bulgusu 2026-10-12: sürücü kursuna "engel yok" deniyordu).
    if t.kurum != "Kültür ve Turizm Bakanlığı" and not re.search(r"Turizm Ücret|turizm işletme belgeli", baslik, re.I):
        return None
    kapsam = _KULTUR_NACE if re.search(r"Kültür Yatırım|Kültür Girişim|5225", baslik) else _TURIZM_NACE
    alan = "kültür yatırım/girişim belgeli işletmeler" if kapsam is _KULTUR_NACE else "turizm belgeli tesisler"
    nace = re.sub(r"^[A-Z]\.", "", getattr(profil, "nace_kodu", None) or "")
    if nace[:2].isdigit():
        return None if any(nace.startswith(k) for k in kapsam) else f"{alan} içindir (NACE {nace} kapsam dışı)"
    if (getattr(profil, "sektor", None) or "").lower() in {"tarim", "imalat", "e-ticaret", "arge"}:
        return f"{alan} içindir"
    return None


# İhracata bağlı programlar (Eximbank ürünleri, Ticaret Bakanlığı ihracat/e-ihracat/hizmet ihracatı Kararları):
# profilde ihracat sinyali yoksa sıralamada geri alınır. Persona denemesi 2026-10-12: "finansman" hedefli matbaa,
# sürücü kursu ve otelde ilk 6 sıra Eximbank ihracat kredisiydi.
_IHRACAT_KARARI = re.compile(r"\b(5973|5986|10962) sayılı Karar")
# İhracat programı ihracatı olmayan profilde genel KOBİ kredilerinin (≈0,45) altına insin.
IHRACAT_ILGI_CEZASI = 0.8


def ihracat_odakli(t) -> bool:
    sektorler = {s.lower() for s in (t.uygunluk_kriterleri or {}).get("sektorler", [])}
    return (t.kurum == "Türk Eximbank" or bool(_IHRACAT_KARARI.search(t.baslik or ""))
            or bool(re.search(r"İHRACAT|İhracat|ihracat", t.baslik or ""))
            or (bool(sektorler) and sektorler <= {"ihracat", "e-ticaret"} and "ihracat" in sektorler))


# 10962 Atılım Programı'nın bazı destek unsurları tek bir hizmet sektörüne verilir ("Destek yalnız sağlık turizmi
# sektöründeki yararlanıcının ...", "bilişim sektöründeki yararlanıcının yazılım ... pazarlamasına"). Persona
# denemesi 2026-10-12: sürücü kursuna (eğitim, NACE 85.53) bilişime özgü Yazılım Lisans Desteği öneriliyordu.
_ALT_SEKTOR_NACE = {
    "bilişim": ("58.2", "62", "63"), "dijital aracılık": ("63", "47.91"), "sağlık turizmi": ("86", "79"),
    "eğitim": ("85",), "teknik müşavirlik": ("71.1",), "kültürel ve kreatif": ("58.1", "59", "60", "90", "74.1"),
    "lojistik ve taşımacılık": ("49", "50", "51", "52", "53"), "fuarcılık": ("82.3",),
    "uygunluk değerlendirme": ("71.2",), "finansal teknoloji": ("64", "66"), "danışmanlık": ("69", "70.2", "73"),
}
_ALT_SEKTOR_SART = re.compile(r"(?:yalnız\s+)?([a-zçğıöşü ,ve]+?)\s+sektör(?:ünde|ündeki|ünde faaliyet)", re.I)


# Başlığı ve kural maddesi belirli bir sektörü adlandıran 5973 programı: m.16 "Gemi ve yat sektöründeki şirketlerin
# aldıkları tasarım hizmeti giderleri" (kayıt 306 kural maddesi, Karar metni). NACE Rev.2 30.1 gemi ve tekne yapımı,
# 33.15 gemi ve teknelerin bakım-onarımı. Hakem bulgusu 2026-10-12, 7. tur: kayıt "genel" etiketli olduğu için halı,
# zeytinyağı ve e-ticaret panellerinde görünüyordu.
_BASLIK_SEKTORU = {"Gemi ve Yat Sektöründe": ("gemi ve yat", ("30.1", "33.15"))}


def _alt_sektor_engeli(t, profil) -> str | None:
    nace = re.sub(r"^[A-Z]\.", "", getattr(profil, "nace_kodu", None) or "")
    for anahtar, (ad, kodlar) in _BASLIK_SEKTORU.items():
        if anahtar in (t.baslik or ""):
            if nace[:2].isdigit() and not any(nace.startswith(k) for k in kodlar):
                return f"destek yalnız {ad} sektöründeki şirketlere (NACE {nace} kapsam dışı)"
            if not nace[:2].isdigit() and (getattr(profil, "sektor", None) or "") not in ("", "imalat", "genel"):
                return f"destek yalnız {ad} sektöründeki şirketlere"
    if t.kurum != "Ticaret Bakanlığı" or "10962" not in (t.baslik or ""):
        return None
    if not nace[:2].isdigit():
        return None
    for metin in _sart_maddeleri(t):
        if not re.match(r"\s*(?:Destek|Rapor desteği|Program)\b", metin):
            continue
        m = _ALT_SEKTOR_SART.search(metin)
        if not m:
            continue
        adlar = [a for a in _ALT_SEKTOR_NACE if a in m.group(1).lower()]
        if adlar and not any(nace.startswith(k) for a in adlar for k in _ALT_SEKTOR_NACE[a]):
            return f"destek yalnız şu sektördeki yararlanıcıya: {', '.join(adlar)} (NACE {nace} kapsam dışı)"
    return None


# Başlığı belirli bir ürünle başlayan tarım programı ("Fındık Temel Desteği", "Fındık Alan Bazlı ...") başka ürün
# yetiştiren çiftçiye önerilmez (persona denemesi 2026-10-12: çilek üreticisinin listesinde fındık desteği).
_URUN_BASLIGI = re.compile(r"^(Fındık|Çay|Pamuk|Zeytin|Ayçiçeği|Fındığın)\b")


def _urun_listesi_engeli(t, profil) -> str | None:
    """Kayıtta ürün listesi varsa (ör. fidan desteği Tablo 6 türleri) ve profildeki ürün listede yoksa engel
    (persona denemesi 2026-10-12: çilek üreticisine sertifikalı fidan desteği öneriliyordu; çilek listede yok)."""
    k = t.uygunluk_kriterleri or {}
    liste = k.get("urun_listesi")
    urun = _sadelestir(getattr(profil, "urun_turu", None) or "")
    haric = k.get("urun_haric")
    if urun and haric and any(_sadelestir(u) in urun for u in haric):
        return f"ürününüz ({getattr(profil, 'urun_turu', '')}) bu kaydın kapsamında değil, kendi kategorisinde ayrı destek var"
    if not liste or not urun:
        return None
    if any(_sadelestir(u) in urun for u in liste):
        return None
    return f"yalnız şu ürünlerde: {', '.join(liste)} ({getattr(profil, 'urun_turu', '')} listede yok)"


def _baska_urun_programi(t, profil) -> bool:
    m = _URUN_BASLIGI.match(t.baslik or "")
    urun = _sadelestir(getattr(profil, "urun_turu", None) or "")
    return bool(m and urun) and _sadelestir(m.group(1))[:5] not in urun


def ihracat_sinyali(profil) -> bool:
    hedefler = {h.lower() for h in (getattr(profil, "hedefler", None) or [])}
    e = ((getattr(profil, "hazirlik", None) or {}).get("eihracat") or {})
    return ("ihracat" in hedefler or (getattr(profil, "sektor", None) or "").lower() == "ihracat"
            or bool(e.get("onceki_yil_ihracat_usd")))


def _kisisel_engel(t, profil, tur: str | None) -> str | None:
    """Kurucu/ortaklık/sertifika şartları (2026-10-10). Kayıtta yapılandırılmış şart ve profilde bilgi varsa karar
    verir; ikisinden biri yoksa elemez. Şartlar resmî metinden alıntıyla girilir
    (scripts/fix_veri_2026_10_10_profil_sart_tur23.py)."""
    k = t.uygunluk_kriterleri or {}
    yas, yas_siniri = getattr(profil, "kurucu_yasi", None), k.get("kurucu_yasi_max")
    if yas is not None and yas_siniri is not None and yas > yas_siniri:
        return f"işletme sahibi ya da en az %50 hissedarı en çok {yas_siniri} yaşında olmalı (beyan: {yas})"
    # 1812 BiGG Yatırım hızlandırma aşaması: şirketi olmayan girişimci, kabul tarihinde başka şirkette ortak olamaz.
    if k.get("ortaklik_yasagi_sirketsiz") and tur == "yok" and getattr(profil, "baska_sirkette_ortak", None) is True:
        return ("hızlandırma programına kabul tarihinde herhangi bir sermaye şirketinin ya da şahıs işletmesinin "
                "ortağı olmamak şartı (beyan: ortaklığınız var; borsadaki hisseler ve kitle fonlaması payları sayılmaz)")
    sertifikalar = getattr(profil, "sertifikalar", None) or []
    gerekli = k.get("gerekli_sertifika")
    if gerekli and sertifikalar and gerekli not in sertifikalar:
        from app.match_adapter import SERTIFIKA_ETIKETLERI
        return f"{SERTIFIKA_ETIKETLERI.get(gerekli, gerekli)} gerekir (beyan: yok)"
    return None


def uygunluk_engeli(t, profil) -> str | None:
    """Kayit metnine gore programin bu profile kapali olma sebebi; None = engel yok.

    Akademik TÜBİTAK çağrıları (araştırmacı/öğretmen) ve aracı kuruluş programları
    (TTO, TEKMER işleticisi) hiçbir işletme profiline önerilmez. Şirketleşme durumu
    profilde biliniyorsa, onunla çelişen şartlar eler; bilinmiyorsa elemez."""
    if not isletmeye_yonelik_mi(t):
        return "akademik/araştırmacı çağrısı"
    metin = _sart_metni(t)
    if _ARACI_KURULUS.search(metin) or (t.uygunluk_kriterleri or {}).get("araci_kurulus"):
        return "aracı/ekosistem kuruluşu programı"
    tur = getattr(profil, "sirket_turu", None)
    # KOSGEB programları KOBİ'lere yöneliktir; kayıtta ölçek kriteri olmasa da (ör. Küresel Rekabetçilik) kesin
    # büyük ölçekli profile önerilmez. Şartında büyük işletmeyi açıkça sayan program (İstihdamı Koruma) istisna.
    # Persona denemesi 2026-10-08: 320 çalışanlı A.Ş.'ye Küresel Rekabetçilik 8. sıradaydı.
    olcek = kobi_sinifi(getattr(profil, "calisan_sayisi", None), getattr(profil, "yillik_ciro", None))
    if t.kurum == "KOSGEB" and olcek.kesin and olcek.sinif == "buyuk" and not _BUYUK_ISLETMEYE_ACIK.search(metin):
        return "KOSGEB programları KOBİ'lere yöneliktir (250 çalışan altı)"
    # "Şahıs işletmeleri" kredi ürünleri: şirket türü biliniyor ve şahıs değilse kapalı (kooperatife ve A.Ş.'ye
    # Halkbank Şahıs İşletmeleri kredisi öneriliyordu).
    if tur and tur != "sahis" and _SAHIS_URUNU.search(t.baslik or ""):
        return "yalnız şahıs işletmelerine yönelik ürün"
    ihracat = _ihracat_engeli(t, profil)
    if ihracat:
        return ihracat
    kisisel = _kisisel_engel(t, profil, tur)
    if kisisel:
        return kisisel
    # Kayıtta açık şirket türü listesi varsa (ör. 5973 sayılı İhracat Destekleri Kararı m.2: "şirket" = TTK md.124
    # şirketleri + kooperatifler; şahıs işletmesi yok) bilinen tür listede değilse program kapalıdır (2026-10-08).
    izinli = (t.uygunluk_kriterleri or {}).get("sirket_turleri")
    if tur and izinli and tur not in izinli:
        return (f"yalnızca {', '.join(SIRKET_TURLERI.get(x, x) for x in izinli)} başvurabilir "
                f"({SIRKET_TURLERI.get(tur, tur)} kapsam dışı)")
    if tur == "yok" and izinli and "yok" in izinli:
        pass   # kayıt şirketi olmayan girişimciye açık (ör. KOSGEB girişimcilik eğitimi, GVK 20/B istisnası)
    elif tur == "yok":
        if t.kurum in _ISLETME_GEREKTIREN_KURUMLAR:
            return f"{t.kurum} programları kayıtlı bir işletme gerektirir"
        if _SIRKETSIZE_KAPALI.search(metin):
            return "şirketleşme/KOBİ şartı"
        # TÜBİTAK TEYDEB sanayi programları (1501, 1505, 1507, 1509, 1511, 1702, 1707,
        # 1711...) başvuranın Türkiye'de yerleşik sermaye şirketi olmasını ister; şart
        # alanı boş kayıtlarda bu metin yoktur. Şirketleşme öncesi tek istisna BiGG
        # (1512/1812) "girisim" türüyle etiketlidir.
        if t.kurum in ("TUBITAK", "TÜBİTAK") and "girisim" not in program_ihtiyaclari(t):
            return "TÜBİTAK sanayi programları sermaye şirketi gerektirir (şirketleşme öncesi tek yol BiGG)"
    elif tur in SIRKET_TURLERI and tur != "yok":
        if _SIRKETI_OLANA_KAPALI.search(metin):
            return "şirketi olanlara kapalı (ortaklık yasağı)"
        # Şahıs işletmesi ve kooperatif sermaye şirketi değildir (TTK md.124: sermaye şirketleri
        # anonim, limited ve sermayesi paylara bölünmüş komandit). Tarayıcı denemesi 2026-10-07:
        # şahıs çiftçiye TÜBİTAK 1501 öneriliyordu.
        if (tur in ("sahis", "kooperatif") and t.kurum in ("TUBITAK", "TÜBİTAK")
                and "girisim" not in program_ihtiyaclari(t)):
            return "TÜBİTAK sanayi programları sermaye şirketi (Ltd./A.Ş.) gerektirir"
    # Faaliyet kapsamı ve ölçek eşikleri (persona denemesi 2026-10-12): şirket türü gerekçesi önce gelir.
    kapsam = (_olcek_esigi_engeli(t, profil) or _atilim_kapsam_engeli(t, profil) or _alt_sektor_engeli(t, profil)
              or _kultur_turizm_engeli(t, profil) or _urun_listesi_engeli(t, profil)
              or ("başka bir ürüne özel destek" if _baska_urun_programi(t, profil) else None))
    if kapsam:
        return kapsam
    yas_siniri = _isletme_yas_siniri(metin)
    kurulus = getattr(profil, "kurulus_tarihi", None)
    if yas_siniri is not None and kurulus is not None:
        yas = (date.today() - kurulus).days / 365.25
        if yas > yas_siniri:
            return f"{yas_siniri:g} yaşına kadar işletmelere açık (işletmeniz yaklaşık {yas:.0f} yaşında)"
    return None


# "0-1 yaş aralığındaki işletme", "0-3 yaş işletme" (KOSGEB Girişimci Destek Programı, kosgeb.gov.tr
# destekdetay/1231, 2026-10-07). Kişi yaşı ("18-29 yaş erkekler", 4447 SGK teşviki) EŞLEŞMEZ: kalıp
# "işletme" kelimesini şart koşar. Birden fazla aralık varsa (İş Kurma 0-1, İş Geliştirme 0-3) en
# genişi alınır: program, en geniş bileşeniyle hâlâ başvurulabilirdir.
_ISLETME_YASI = re.compile(r"(\d+)\s*-\s*(\d+)\s*yaş(?:\s+aralığındaki)?\s+işletme", re.IGNORECASE)


def _isletme_yas_siniri(metin: str) -> float | None:
    sinirlar = [float(m.group(2)) for m in _ISLETME_YASI.finditer(metin or "")]
    return max(sinirlar) if sinirlar else None


# KOSGEB programına kabul edilmeye BAĞLI KGF kefalet paketleri (Kapasite Geliştirme, Küresel Rekabetçilik,
# Dijital Dönüşüm, Girişimci kredi faizi, İstihdam Koruma, KOSGEB geri ödemeli destekler). Bunlar ayrı bir
# seçenek değil, KOSGEB onayından sonra kullanılan finansman ayağıdır; eşit skorda asıl programın önüne
# geçiyorlardı (2026-10-07: Bursa metal KOBİ'sinde KGF Kapasite paketi 1., KOSGEB Kapasite Geliştirme 2.).
_KOSGEB_BAGIMLI = re.compile(
    r"KOSGEB tarafından[^.]{0,60}(?:onaylan|uygun bulunan)|KOSGEB[^.]{0,60}hak kazanan|"
    r"KOSGEB’den destek ödemesi almaya|Destek Programı kapsamında kullandırılacak kredi", re.IGNORECASE)
KOSGEB_BAGIMLI_CEZA = 0.05
KOSGEB_BAGIMLI_NOTU = ("Bu KGF paketi, ilgili KOSGEB programına kabul edildikten sonra kullanılabilir; "
                       "önce KOSGEB programına başvurun.")


def _kosgeb_onayina_bagli_mi(t) -> bool:
    if (t.kurum or "").strip() != "KGF":
        return False
    metin = " ".join([t.ozet or "", " ".join(t.basvuru_sartlari or []), (t.detay or "")[:2000]])
    return bool(_KOSGEB_BAGIMLI.search(metin))


# Kartta "hedef eşleşmesi" gerekçesinin öneki; ölçüm betikleri (docs/olcum/.../G_persona_esles.py) bu sabite bakar.
HEDEF_GEREKCE_ONEKI = "Belirttiğiniz hedeflerle eşleşiyor:"
# Gerekçede iç anahtar ("yatirim") yerine paneldeki etiket (dashboard.html .p-hedef) gösterilir.
HEDEF_ETIKETLERI = {"yatirim": "yatırım", "ihracat": "ihracat", "arge": "Ar-Ge", "istihdam": "istihdam",
                    "makine": "makine alımı", "sulama": "sulama sistemi", "hayvan": "hayvancılık",
                    "organik": "organik tarım", "e-ticaret": "e-ticaret"}


def _etiketler(anahtarlar) -> str:
    return ", ".join(HEDEF_ETIKETLERI.get(a, a) for a in anahtarlar)

# Profildeki tarım hedefi -> kaydın tarım alt kategorisi.
HEDEF_TARIM_KATEGORISI = {"makine": "makinelestirme", "sulama": "sulama", "hayvan": "hayvancilik",
                          "organik": "organik"}


def _hedef_eslesmeleri(t, hedefler: set[str], alt_kategori: str | None) -> list[str]:
    """Profil hedeflerinden bu programın hizmet ettikleri.

    Eskiden hedef değeri ("yatirim") kayıt başlığında harfiyen aranıyordu; kayıtlar Türkçe yazıldığı
    için ("Yatırım") yatırım hedefi HİÇBİR programla eşleşmiyor, her kartta "hedeflerle eşleşme
    bulunamadı" yazıyordu (tarayıcı denemesi 2026-10-07: Bursa metal işleme KOBİ'sinde 9903 Hedef
    Yatırımlar ve Kapasite Geliştirme hedef bonusu alamadı, Kapasite Geliştirme 17. sıradaydı).
    Program ihtiyaçları ortak sınıflandırıcıdan (app.ihtiyac.program_ihtiyaclari) gelir; tarım
    hedefleri kaydın alt kategorisiyle ya da aksansız başlık/özet metniyle eşleşir."""
    ihtiyac = program_ihtiyaclari(t)
    # Yalnızca BAŞLIK: kazınmış kayıtların özet alanında site menüsü duruyor ("İhracat Destek Paketi",
    # "İstihdamı Koruma..."); özette aramak her KGF/KOSGEB kaydını ihracat/istihdam hedefiyle eşleştiriyordu.
    metin = _sadelestir(t.baslik or "")
    sonuc = []
    for h in sorted(hedefler):
        if h in ihtiyac:
            sonuc.append(h)
        elif h == "makine" and "yatirim" in ihtiyac and alt_kategori is None:
            sonuc.append(h)   # sanayide makine alımı yatırım programının konusudur (tarımda makineleştirme kategorisi)
        elif h in HEDEF_TARIM_KATEGORISI and (alt_kategori == HEDEF_TARIM_KATEGORISI[h] or h in metin):
            sonuc.append(h)
        elif h in ("ihracat", "istihdam") and h in metin:
            sonuc.append(h)
    return sonuc


def esles(profil: FinancialProfile, db: Session, limit: int = 20,
          ilgi_cezalari: bool = True) -> list[TesvikEslesmeSonucu]:
    """ilgi_cezalari=False: ihracat/yaş/hedef kitle sıralama cezaları uygulanmaz (uygunluğun karşı-olgusu, ör.
    app/hazirlik "şirkete geçerseniz açılan programlar": ilgi değil uygunluk sayılır)."""
    profil_sektorler = {(profil.sektor or "").lower()}
    profil_hedefler = {h.lower() for h in (profil.hedefler or [])}

    sonuclar: list[TesvikEslesmeSonucu] = []
    sirket = company_from_profile(profil)
    _olcek = kobi_sinifi(profil.calisan_sayisi, profil.yillik_ciro)
    olcek_sinifi = _olcek.sinif if _olcek.kesin else None

    from datetime import date as _date
    bugun = _date.today()
    for t in db.query(Tesvik).options(selectinload(Tesvik.nace_kayitlari), selectinload(Tesvik.cagrilar)).all():
        # KAPANDIGI DOGRULANMIS programlari hic onerme. Bunlar bir firsat
        # degil; kullanici arayip "bu program bitti" cevabi alir ve sistemin
        # tamamina olan guveni sarsilir. (Tespit: imalat profiline gelen ilk
        # 20 onerinin 5'i kapali programdi - 2021 Nefes Kredisi, 6 Subat
        # paketleri gibi.) Kapali programlar RAG/arama tarafinda hala
        # bilgi amacli gorunur, orada "artik aktif degil" diye isaretleniyor.
        if t.aktif_mi is False:
            continue

        kriterler = t.uygunluk_kriterleri or {}
        tesvik_sektorler = {s.lower() for s in kriterler.get("sektorler", [])}

        if not tesvik_sektorler:
            continue

        # Katı eleme (app/match_scoring.py Aşama 1): zorunlu hedef kitle,
        # çalışan sayısı ve il kısıtı. Profilde olmayan veri ELEMEZ (yokluk
        # ihlal değildir); yalnızca olumlu beyan gerektiren hedef kitle
        # etiketi eksikse elenir. Sektör kontrolü aşağıdaki mevcut mantıkta.
        program = program_from_tesvik(t)
        sebepler, _ = hard_filter(sirket, program, strict_sector=True)
        if sebepler:
            continue

        # Kayit metnine dayali uygunluk kurallari (bkz. uygunluk_engeli):
        # akademik cagrilar, araci/ekosistem kurulus programlari, sirketlesme
        # durumuyla celisen sartlar. Olcum 2026-10-07: 8 personanin 6'sinda
        # 1002-A/B gibi arastirmaci cagrilari, sirketsiz girisime KGF kefaleti,
        # sirketi olan isletmeye ortaklik yasakli BiGG ilk 10'a giriyordu.
        if uygunluk_engeli(t, profil):
            continue

        # 9903: EK-3 şartı aranan programda yatırım konusu listede yoksa kesin olarak
        # desteklenmez (MADDE 5/1); diğer sonuçlar kullanıcıya not olarak düşülür.
        u9903 = uygunluk_9903(t, getattr(profil, "nace_kodu", None), profil.bolge, olcek_sinifi)
        if u9903 is not None and u9903.durum == "uygun_degil":
            continue

        skor = 0.0
        gerekce: list[str] = []
        eksik: list[str] = []

        ortak_sektor = tesvik_sektorler & profil_sektorler
        # Sektor etiketleri aslinda ihtiyac turunu de kodluyor ("ihracat", "arge",
        # "e-ticaret"): hedefi ihracat olan bir imalatci, e-ihracat programlarini
        # gormeliydi ama etiketi yalnizca "ihracat" olan kayit sektor uyusmadi
        # diye hic listelenmiyordu (olcum 2026-10-07, Izmir tekstil personasi).
        hedef_sektor = (tesvik_sektorler & HEDEF_SEKTOR_ETIKETLERI & profil_hedefler) - ortak_sektor
        if ortak_sektor or "genel" in tesvik_sektorler or hedef_sektor:
            if ortak_sektor:
                sektor_bonusu = 0.6
                gerekce.append(f"Sektörünüz ({profil.sektor}) bu desteğin kapsamına uygun.")
            elif hedef_sektor:
                # Etiketleri yalnız ihtiyaç türü (ihracat, Ar-Ge, e-ticaret) ve "genel" olan program (5973 fuar,
                # tanıtım, marka tescil) için hedef eşleşmesi sektör eşleşmesi kadar güçlüdür; programın "sektörü"
                # o ihtiyaçtır (hakem bulgusu 2026-10-12, 4-7. tur: ihracat hedefli halı ve zeytinyağı panelinde 5973
                # tanıtım/fuar ailesi ilk 20'de yoktu, sektör etiketi taşıyan Eximbank kredileri öndeydi).
                sektor_bonusu = 0.6 if tesvik_sektorler <= HEDEF_SEKTOR_ETIKETLERI | {"genel"} else 0.3
                gerekce.append(f"Hedefiniz ({_etiketler(sorted(hedef_sektor))}) bu desteğin alanına giriyor.")
            else:
                sektor_bonusu = 0.2
                gerekce.append("Bu destek sektörden bağımsız genel bir programdır.")
            skor += sektor_bonusu
        else:
            continue  # sektor hic uyusmuyorsa listeye alma

        # NACE: program sektörlüyse ve işletmenin kodu biliniyorsa uyum gerekçeye
        # yazılır (eleme yukarıda yapıldı). Kod girilmemişse ve program kapsamı kısım
        # düzeyinden DAR ise (62/63/58.2 gibi bölüm/dal kodları) geniş sektör etiketi
        # ("hizmet") bunu temsil edemez: sektör puanının yarısı düşülür. Kısım düzeyi
        # kapsam ("A" tarım, "C" imalat) sektör etiketiyle zaten eş anlamlıdır; NACE'siz
        # çiftçi cezalandırılmaz. Ölçüm 2026-10-07: NACE'siz Hatay hizmet işletmesine
        # 10962 Bilişim Hizmet İhracatı 0.70 ile 1. sırada geliyordu.
        if program.nace_codes:
            if sirket.nace_codes:
                uyum = sector_match(sirket.nace_codes[0], program.nace_codes)
                gerekce.append(f"Faaliyet kodunuz: {uyum.aciklama}.")
            else:
                if not all(kisim_duzeyinde(k) for k in program.nace_codes):
                    skor -= sektor_bonusu / 2
                eksik.append(
                    "Bu destek belirli sektörlere özeldir. Profilinize faaliyet (NACE) "
                    "kodunuzu girerseniz uygunluğu netleşir."
                )

        if program.excluded_nace_codes and not sirket.nace_codes:
            eksik.append(
                "Bu destekte bazı faaliyet kolları kapsam dışıdır (" +
                ", ".join(program.excluded_nace_codes) + "). Faaliyet (NACE) kodunuzu "
                "girerseniz uygunluğu netleşir."
            )

        if u9903 is not None:
            # Ön değerlendirme sıralamayı da etkiler (ölçüm 2026-10-07: ekmek üreticisine
            # beş 9903 programı "DÜŞÜK OLASILIK" notuyla 0.70 ile en üstte geliyordu).
            skor += UYGUNLUK_9903_SKOR_ETKISI[u9903.durum]
            if u9903.durum in ("uygun", "sartli"):
                gerekce.append(f"9903 ön değerlendirmesi: {u9903.metin()}.")
            else:
                eksik.append(f"9903 ön değerlendirmesi: {u9903.metin()}.")

        bolge_kisitli = kriterler.get("bolge_kisitli")
        if bolge_kisitli:
            profil_bolge = (profil.bolge or "").strip().lower()
            if profil_bolge:
                bolge_uyumlu = any(
                    il in profil_bolge or profil_bolge in il for il in bolge_kisitli
                )
                if not bolge_uyumlu:
                    continue  # bu program baska illere ozel, kullaniciya gosterme
                gerekce.append(f"Bölgeniz ({profil.bolge}) bu programın kapsamındaki iller arasında.")
            else:
                skor *= 0.5
                eksik.append(
                    "Bu destek yalnızca belirli illerde faaliyet gösteren/yatırım yapacak "
                    "işletmeler içindir (" + ", ".join(il.title() for il in bolge_kisitli) + "). "
                    "Bölgenizi girerseniz size uygun olup olmadığını netleştirebiliriz."
                )

        hedef_metni = f"{t.baslik} {t.ozet}".lower()

        if profil_hedefler:
            hedef_eslesme = _hedef_eslesmeleri(t, profil_hedefler, kriterler.get("alt_kategori"))
            if hedef_eslesme:
                # Özgül hedef (makine, ihracat, Ar-Ge, istihdam ...) genel "finansman" hedefinden güçlü sinyaldir;
                # her ek özgül hedef küçük bir artı.
                ozgul = [h for h in hedef_eslesme if h != "finansman"]
                skor += (0.3 + 0.1 * (len(ozgul) - 1)) if ozgul else 0.15
                gerekce.append(f"{HEDEF_GEREKCE_ONEKI} {_etiketler(hedef_eslesme)}.")
            else:
                eksik.append("Belirttiğiniz hedeflerle doğrudan eşleşme bulunamadı, ayrıntıları kontrol edin.")

        urun_turu = (profil.urun_turu or "").strip().lower()
        if urun_turu and urun_turu in (t.baslik or "").lower():
            # Ürüne özel program (fındık temel desteği, fındık kira desteği) genel tarım programından önce gelir.
            skor += 0.3
            gerekce.append(f"Yetiştirdiğiniz ürün/faaliyet ({profil.urun_turu}) bu destekte geçiyor.")

        # Bazi tarim destekleri dar bir alt kategoriye ozeldir (orn. sadece
        # hayvancilik). Kullanicinin profilinde YAPILANDIRILMIS bir kategori
        # secimi (tarim_kategori dropdown - serbest metin degil) varsa bunu
        # kesin sinyal olarak kullaniyoruz: tam eslesirse guclu bonus, tam
        # eslesmezse ceza. Yapilandirilmis secim YOKSA (kullanici bos
        # birakti) eski serbest-metin (urun_turu/hedefler) ipucuna bakariz;
        # o da yoksa CEZA UYGULAMIYORUZ artik - eskiden kategori sinyali
        # hic yokken bile sabit ceza uygulaniyordu, bu da 5 tarim destegini
        # ayni skora dusurup alfabetik sirada hep "Hayvancilik"in kazanmasina
        # yol aciyordu. Bunun yerine sadece "genislik" etiketine gore hafif
        # bir ayrim yapiyoruz: dar/spesifik programlar (orn. hayvancilik,
        # sera) belirsizlikte hafif geride kalir, genis/genel programlar
        # (orn. sulama, makinelestirme, organik) etkilenmez.
        alt_kategori = kriterler.get("alt_kategori")
        if alt_kategori:
            tarim_kategori = (profil.tarim_kategori or "").strip().lower()
            genislik = kriterler.get("genislik", "genis")

            # "genel" / "Belirtmek istemiyorum" GERCEK bir kategori degil:
            # hicbir tesvik kaydinda alt_kategori="genel" yok, dolayisiyla
            # bunu gercek bir secim gibi islemek "hicbiriyle eslesmedi"
            # sayilip her kategorili kaydin skorunu 0.25 dusuruyordu. Sonuc:
            # kullanici "Belirtmek istemiyorum" secince ALANI BOS
            # BIRAKMAKTAN DAHA KOTU sonuc aliyordu (olcum 2026-09-26: tum
            # tarim destekleri 0.70/0.60 -> 0.45). Belirtilmemis kabul edip
            # asagidaki serbest-metin ipucu yoluna dusuyoruz.
            if tarim_kategori in BELIRTILMEMIS_KATEGORILER:
                tarim_kategori = ""

            # Kategori secilmemis ama urun adi girilmisse kategoriyi urunden
            # cikar: "bugday" -> tahil_baklagil. Eskiden yalnizca
            # "alt_kategori metni urun_turu icinde geciyor mu" bakiliyordu ve
            # "tahil_baklagil" ifadesi "bugday" icinde gecmedigi icin bu ipucu
            # hic calismiyordu - urun_turu="bugday" girmis bir ciftci icin tam
            # uyan "Hububat ve Baklagil Uretim Destekleri" kaydi, alakasiz
            # "Hayvancilik Destekleri" ile ayni skoru aliyordu.
            urunden_kategori = None
            if not tarim_kategori:
                urunden_kategori = urun_turunden_tarim_kategorisi(profil.urun_turu)

            if tarim_kategori:
                if tarim_kategori == alt_kategori:
                    skor += 0.3
                    gerekce.append(f"Seçtiğiniz tarım kategorisi ('{tarim_kategori}') bu destekle tam eşleşiyor.")
                elif genislik == "dar":
                    # Kullanıcı kategorisini açıkça seçti ve bu dar program başka bir faaliyete özel:
                    # hedeflerinde de bu alan yoksa öneri değil gürültüdür (tarayıcı denemesi
                    # 2026-10-07: tahıl üreticisine Meyve-Sebze mazot-gübre ve Sera destekleri 45%
                    # ile listeleniyordu). Hedefte varsa (ör. hayvancılığa geçmek isteyen tahıl
                    # üreticisi) cezayla birlikte gösterilir.
                    hedefteki_kategoriler = {HEDEF_TARIM_KATEGORISI[h] for h in profil_hedefler
                                             if h in HEDEF_TARIM_KATEGORISI}
                    if alt_kategori not in hedefteki_kategoriler:
                        continue
                    skor -= 0.25
                    eksik.append(
                        f"Bu destek '{alt_kategori}' kategorisine özeldir; seçtiğiniz kategori "
                        f"('{tarim_kategori}') farklı."
                    )
                # genislik == "genis" olan programlar (sulama, makinelestirme,
                # organik) URUN TURUNDEN BAGIMSIZDIR: bugday eken bir ciftci de
                # organik sertifikasyon alabilir, sulama yatirimi yapabilir,
                # traktor destegine basvurabilir. Bunlari "kategori uyusmadi"
                # diye cezalandirmak somut bir hataya yol aciyordu (olcum
                # 2026-09-26): tahil_baklagil secen ciftci icin Organik/Sulama/
                # Makinelestirme destekleri 0.70'ten 0.45'e dusuyor, yani
                # kategoriyi DOGRU secmek bu uc gecerli destegin siralamasini
                # kotulestiriyordu. Uyusmazlik cezasi artik yalnizca gercekten
                # dislayici ("dar") programlara uygulaniyor.
            elif urunden_kategori == alt_kategori:
                # Urun adindan cikarilan kategori: acilir listeden gelen kesin
                # secim kadar guvenilir degil (kullanici birden fazla urun
                # yetistiriyor olabilir), bu yuzden bonus daha dusuk ve
                # uyusmayan kayitlara CEZA UYGULANMIYOR.
                skor += 0.25
                gerekce.append(
                    f"Girdiğiniz ürün ('{profil.urun_turu}') bu desteğin kategorisine "
                    f"('{alt_kategori}') giriyor."
                )
            else:
                urun_turu_sade = _sadelestir(urun_turu)
                hedefler_sade = {_sadelestir(h) for h in profil_hedefler}
                serbest_metin_isareti = (
                    alt_kategori in urun_turu_sade
                    or any(alt_kategori in h for h in hedefler_sade)
                )
                if serbest_metin_isareti:
                    skor += 0.2
                    gerekce.append(f"'{alt_kategori}' kategorisiyle eşleşiyor.")
                elif urunden_kategori is not None:
                    # Urun baska bir kategoriye isaret ediyor. Ceza yerine
                    # sadece bonus vermiyoruz: urun bilgisi acilir liste kadar
                    # kesin olmadigi icin yanlis olma ihtimali var.
                    eksik.append(
                        f"Bu destek '{alt_kategori}' kategorisine özeldir; girdiğiniz "
                        f"ürün ('{profil.urun_turu}') '{urunden_kategori}' kategorisine "
                        "işaret ediyor."
                    )
                elif genislik == "dar":
                    skor -= 0.1
                    eksik.append(
                        f"Bu destek '{alt_kategori}' kategorisine özeldir. Profilinizde 'Tarım "
                        "Kategorisi' alanını doldurursanız size gerçekten uygun olup olmadığı netleşir."
                    )

        if profil.calisan_sayisi is not None:
            skor += 0.1
            if profil.calisan_sayisi == 0 and getattr(profil, "sirket_turu", None) != "yok":
                gerekce.append("Şahıs işletmesi / tek kişilik faaliyet olarak değerlendirildi.")
        else:
            eksik.append("Çalışan sayınızı girerseniz eşleşme doğruluğu artar.")

        # Persona denemesi 2026-10-08 (docs/olcum/2026-10-08-persona/RAPOR.md) sıralama düzeltmeleri:
        # (a) Zorunlu hedef kitleli program ve profil o etiketi taşıyor: yalnız ona açık olduğu için öne çıkar
        #     (kadın girişimciye Ziraat Kadın ve Genç Girişimci paketi 20., kooperatife KGF Kooperatif paketi 18.).
        ortak_etiket = sirket.tags & program.target_group_tags if program.exclusive_target_group else set()
        if ortak_etiket:
            from app.match_adapter import OZELLIK_ETIKETLERI
            skor += 0.3
            gerekce.append("Yalnız sizin hedef kitlenize açık: "
                           + ", ".join(OZELLIK_ETIKETLERI.get(x, x) for x in sorted(ortak_etiket)) + ".")
        # (b) 9903 yatırım teşvikleri teşvik belgesi ve asgari yatırım ister; yatırım/makine hedefi yoksa geride
        #     (2 kişilik kuaföre Yerel Kalkınma Hamlesi 1. sıradaydı). Hedef hiç girilmemişse ceza yok: yokluk
        #     ihlal değildir (hedefsiz imalatçıya 9903 ön değerlendirmesiyle gösterilmeye devam eder).
        if (t.kurum == "Sanayi ve Teknoloji Bakanlığı" and profil_hedefler
                and not ({"yatirim", "makine"} & profil_hedefler)):
            skor -= 0.3
            eksik.append("Yatırım teşviki: teşvik belgesi ve asgari yatırım tutarı gerekir; hedeflerinizde yatırım yok.")
        # (c) Organik tarım desteği yalnız sertifikalı organik üretime ödenir; geçiş seçeneği olarak kalır ama
        #     organik beyanı yoksa hazır destekleri geçmez (3 tarım personasında ilk 3'teydi).
        if kriterler.get("alt_kategori") == "organik" and not (
                (profil.tarim_kategori or "").lower() == "organik" or "organik" in profil_hedefler):
            skor -= 0.2
            eksik.append("Yalnız organik sertifikalı üretim desteklenir; organik tarıma geçerseniz uygun olur.")

        # (d) İlgi cezaları (100 sentetik ajan denemesi 2026-10-09, docs/olcum/2026-10-09-100-ajan): ilk 10'daki
        #     önerilerin %18'i profile ilgisizdi; hepsi yalnız "genel" sektör etiketiyle 0,30 alıyordu. Ceza uygunluğu
        #     değil ilgiyi ölçer; zayıf (yalnız genel) eşleşmeyi 0'a indirip gizler, güçlü sinyali olanı yalnız geriye alır.
        ilgi_notu = _ilgi_engeli(t, profil, profil_hedefler, olcek_sinifi)
        if ilgi_notu:
            # Durum programları (refinansman, istihdamı koruma) genel öneri değildir: ek ceza.
            skor -= ILGI_CEZASI + (0.2 if re.search(r"yeniden finansman|Zor dönemde", ilgi_notu) else 0.0)
            eksik.append(ilgi_notu)

        # Ceza 1,0 tavanından SONRA düşülür: tavan öncesi düşülse 1,3 -> 1,25 -> 1,0 olur, etkisi kalmaz.
        ceza = 0.0
        sira_cezasi = 0.0
        if _kosgeb_onayina_bagli_mi(t):
            ceza = KOSGEB_BAGIMLI_CEZA
            eksik.append(KOSGEB_BAGIMLI_NOTU)
        if ilgi_cezalari and ihracat_odakli(t) and not ihracat_sinyali(profil):
            ceza += IHRACAT_ILGI_CEZASI
            eksik.append("İhracat yapan ya da yapacak işletmelere yönelik; hedeflerinizde ihracat yok.")
        if (ilgi_cezalari and program.target_group_tags and not program.exclusive_target_group
                and not sirket.tags & program.target_group_tags):
            # Zorunlu olmayan hedef kitle (ör. kadın yönetici bulunan işletme): o özelliği taşımayan profilde geride.
            from app.match_adapter import OZELLIK_ETIKETLERI
            ceza += 0.2
            eksik.append("Öncelikle şu işletmelere yönelik: " + ", ".join(
                OZELLIK_ETIKETLERI.get(x, x) for x in sorted(program.target_group_tags)) + ".")
        # (e) Hakem bulgusu 2026-10-12, 4. tur (eşleşme listeleri): ilk 10'da çağrısı kapanmış program, asgari
        #     yatırımı yıllık cironun üzerindeki 9903 programı ve cironun tamamı ihracat olsa bile USD eşiğine
        #     ulaşılamayan program vardı. Uygunluk değil ilgi/zamanlama: liste dışına atılmaz, geriye alınır.
        if ilgi_cezalari:
            from app import yerel_danisman as _yd
            donem, c = _yd.cagri_bilgisi(t, bugun)
            if donem in ("kapandi", "on_kayit_kapandi"):
                ceza += 0.3
                eksik.append("Başvuru dönemi şu an kapalı" + (f" ({c['ad']})" if c and c.get("ad") else "")
                             + "; yeni çağrıyı izleyin.")
            if _yd._buyuk_olcekli(t, profil):
                ceza += 0.2
                eksik.append("Program ölçeği (asgari yatırım ya da kredi tavanı) yıllık cironuza göre çok büyük.")
            usd = _yd.usd_esigi(t)
            if usd and profil.yillik_ciro and profil.yillik_ciro < usd[0] * _yd.ASGARI_USD_TRY:
                ceza += 0.3
                eksik.append(f"Kaydın aradığı en az {usd[0]:,.0f} USD {usd[1]} eşiği yıllık cironuzun üzerinde."
                             .replace(",", "."))
        if ilgi_cezalari and re.search(r"Teknoloji Geliştirme Bölgesi|Teknopark", t.baslik or "") \
                and not _arge_sinyali(profil, profil_hedefler):
            # Teknopark vergi istisnaları yalnız bölgede Ar-Ge/yazılım faaliyeti yürüten firmalar içindir (hakem bulgusu
            # 5-7. tur: sürücü kursu panelinin ilk 10'unda iki teknopark kaydı).
            ceza += 0.3
            eksik.append("Yalnız teknoloji geliştirme bölgesinde Ar-Ge/yazılım faaliyeti yürüten firmalar içindir.")
        if ilgi_cezalari and "finansman" not in profil_hedefler and profil_hedefler and _yd._kredi_mi(t):
            # Hedefinde finansman olmayan profilde kredi/kefalet ürünü hibe ve destek programlarının arkasında
            # (4-7. tur: halı panelinde 3-16. sıralar 12 Eximbank kredisiydi). Yalnız sıralama: görünen uygunluk
            # skoru değişmez (KOSGEB'e bağlı paketin asıl programdan 0,05 geride kalma kuralı korunur).
            sira_cezasi += 0.25
        if ilgi_cezalari and kriterler.get("kurucu_yasi_max") and getattr(profil, "kurucu_yasi", None) is None:
            # Yaş şartlı ürün (genç girişimci kredisi) yaşı bilinmeyen profilde lider olmasın (otel denemesi).
            ceza += 0.2
            eksik.append(f"İşletme sahibinin en çok {kriterler['kurucu_yasi_max']} yaşında olması gerekir; yaşınızı "
                         "profile girerseniz netleşir.")

        # Görünen skor: ilgi cezaları programı listeden düşürmez, en alta iter (sıralama `siralama` ile).
        gorunen = min(skor, 1.0) - ceza
        if skor > 0 and gorunen <= 0:
            gorunen = 0.05
        sonuclar.append(TesvikEslesmeSonucu(
            tesvik=t, skor=round(max(gorunen, 0.0), 2), gerekce=gerekce, eksik_kriterler=eksik,
            ince_skor=score_program(sirket, program).total_score, siralama=round(skor - ceza - sira_cezasi, 3)))

    # Skor esitliginde veritabani ekleme sirasina (id) gore rastgele/anlamsiz
    # bir siralama olusmasin diye ikincil olarak baslige gore alfabetik
    # siraliyoruz - en azindan ongorulebilir ve kullaniciya aciklanabilir.
    # Ayni skorda: aktif oldugu DOGRULANMIS program, aktifligi hic kontrol
    # edilmemis olanin onune gecer. Skoru degistirmiyoruz (aciklanabilirlik
    # bozulmasin) - sadece esitlik bozma sirasi.
    # Esit ana skorda once NACE/bolge/olcek uyumu (ince_skor), sonra dogrulanmis aktiflik,
    # sonra baslik. Olcum 2026-10-07: SaaS profilinde 10 kayit 0.70 ile esitti ve NACE 62
    # etiketli 10962 kaydi alfabetik sirada 7. geliyordu.
    sonuclar.sort(key=lambda s: (-s.siralama, -s.ince_skor, 0 if s.tesvik.aktif_mi is True else 1,
                                 (s.tesvik.baslik or "").lower()))
    sonuclar = _kurum_ile_cesitlendir(sonuclar)
    # Skoru 0'a düşen kayıt öneri değildir (persona denemesi 2026-10-08: "0,00" ile listelenen 9903 kayıtları).
    return [s for s in sonuclar if s.skor > 0][:limit]


def _tutar_olcek_faktoru(kriter: str, profil: FinancialProfile) -> float | None:
    """tutari_min/tutari_max (TL cinsinden BIRIM fiyat - orn. 'dekar basina')
    ile kullanicinin profilindeki gercek buyuklugu carparak MUTLAK tahmini
    tutara cevirmek icin kullanilan olcek katsayisini doner. Ilgili profil
    alani eksikse None doner - cagiran taraf bu durumda tahmin uretmemeli,
    aksi halde 'dekar basina 500 TL' 500 TL toplam gibi gosterilir (bkz.
    toplam_tahmini_destek'teki eski hata)."""
    kriter = kriter.lower()
    if kriter == "dekar":
        return profil.arazi_buyuklugu_dekar if profil.arazi_buyuklugu_dekar else None
    elif kriter == "calisan":
        return (profil.calisan_sayisi or 1) if profil.calisan_sayisi is not None else None
    elif kriter in ("ciro", "genel"):
        # tutari_min/max zaten MUTLAK TL toplami (birim fiyat degil) - olcek 1.
        return 1.0
    return None


def _tarim_kategorisi_uyusmuyor(tesvik, profil: FinancialProfile) -> bool:
    """Tarım programı, kullanıcının bilinen faaliyetinden farklı bir alt kategoriye mi ait?

    Faaliyet bilinmiyorsa (kategori seçilmemiş, ürün yazılmamış) False: tahmin engellenmez. Hedeflerde
    o alan varsa (ör. organik tarıma geçmek isteyen) uyuşmazlık sayılmaz. Tarayıcı denemesi
    2026-10-07: organik üretim yapmayan buğday üreticisine "Organik Tarım Destekleri" için
    57.970 TL tahmini tutar yazılıyor ve toplam tahmini desteğe ekleniyordu."""
    alt = (tesvik.uygunluk_kriterleri or {}).get("alt_kategori")
    if not alt:
        return False
    kategori = (profil.tarim_kategori or "").strip().lower()
    if kategori in BELIRTILMEMIS_KATEGORILER:
        kategori = ""
    kategori = kategori or (urun_turunden_tarim_kategorisi(profil.urun_turu) or "")
    if not kategori or kategori == alt:
        return False
    hedefteki = {HEDEF_TARIM_KATEGORISI[h] for h in (h.lower() for h in (profil.hedefler or []))
                 if h in HEDEF_TARIM_KATEGORISI}
    return alt not in hedefteki


def tutari_tahmini_hesapla(tesvik, profil: FinancialProfile) -> float | None:
    """Teşvik tutarı ve profil bilgisine göre tahmini destek tutarı hesapla.

    Örn: 50 dekar arazi, makineleştirme desteği (dekar başına ₺X-Y) -> tahmini
    """
    if not tesvik.tutari_hesaplama_kriteri or tesvik.tutari_min is None:
        return None
    if _tarim_kategorisi_uyusmuyor(tesvik, profil):
        return None
    # Kredi/kefalet limiti ve proje bazlı program tavanı "alacağınız destek" değildir; toplam tahmin
    # (toplam_tahmini_destek) bunları zaten dışarıda tutuyordu ama kartta ayrı ayrı "Tahmini" diye
    # gösteriliyordu (tarayıcı denemesi 2026-10-07: çiftçinin kartında Kapasite Geliştirme kredisi
    # için "Tahmini: ₺10.500.000").
    if _kredi_kefaleti_mi(tesvik) or _proje_bazli_tavan_mi(tesvik):
        return None

    ort_tutar = (tesvik.tutari_min + (tesvik.tutari_max or tesvik.tutari_min)) / 2
    olcek = _tutar_olcek_faktoru(tesvik.tutari_hesaplama_kriteri, profil)
    if olcek is None:
        return None
    return olcek * ort_tutar


KREDI_KEFALET_KURUMLARI = {"kgf"}


def _proje_bazli_tavan_mi(tesvik) -> bool:
    """Kaydin tutari, programin UST SINIRI mi (kullanicinin alacagi tutar degil)?

    Metinden tahmin etmiyoruz - veride acikca isaretli olmasi gerekiyor:
        uygunluk_kriterleri["tutar_niteligi"] == "proje_bazli_tavan"
    Boylece hangi kaydin neden toplama girmedigi denetlenebilir kaliyor
    (bkz. scripts/backfill_tarim_tutar_2026.py).
    """
    return _tutar_niteligi(tesvik) == "proje_bazli_tavan"


# uygunluk_kriterleri["tutar_niteligi"] degerleri. Tutarin NE oldugunu
# soyler; "toplam tahmini destek"e hangi kaydin girecegini bu belirler.
#   "hibe"              -> geri odemesiz, cepten alinir. TOPLAMA GIRER.
#   "kredi_kefalet"     -> kredi ana parasi / kefalet limiti. Girmez.
#   "faiz_destegi"      -> kurum kredinin FAIZINI odiyor, ana parayi degil;
#                          bastaki buyuk rakam kredi limitidir. Girmez.
#   "proje_bazli_tavan" -> programin ust siniri, kullaniciya ozel degil. Girmez.
TOPLAMA_GIRMEYEN_NITELIKLER = {"kredi_kefalet", "faiz_destegi", "proje_bazli_tavan"}

_NITELIK_ACIKLAMALARI = {
    "kredi_kefalet": "Bu bir kredi/kefalet ürünü: rakam bankadan "
                     "kullanabileceğiniz kredinin üst sınırıdır, size "
                     "ödenecek hibe değildir.",
    "faiz_destegi": "Kurum kredinin ANA PARASINI değil FAİZİNİ karşılıyor; "
                    "baştaki büyük rakam kredi limitidir. Eline geçen destek "
                    "ödenen faiz kadardır.",
    "proje_bazli_tavan": "Tutar proje bazlı belirlenir; metindeki rakam "
                         "programın üst sınırıdır, sizin alacağınız tutar "
                         "değildir.",
}


def _tutar_niteligi(tesvik) -> str | None:
    return (tesvik.uygunluk_kriterleri or {}).get("tutar_niteligi")


def _kredi_kefaleti_mi(tesvik) -> bool:
    """Bu kaydin tutari hibe DISI mi (kredi/kefalet/faiz destegi)?

    ONCE acik isarete bakar. Isaret yoksa metin sezgisine duser, ama bu sezgi
    KAYIP VERIYOR: "kredi" kelimesi gecen her kayit tamamen disari atiliyordu
    ve boylece KOSGEB Girisimci Destek Programi'ndaki GERI ODEMESIZ 10.000 TL
    kurulus destegi de toplamdan dusuyordu (olcum 2026-09-26; metinde "%80
    geri odemeli" ve "Faiz/Kar Payi" ifadeleri geciyor diye). Bu yuzden
    kayitlarin tutar_niteligi ile acikca isaretlenmesi gerekiyor
    (bkz. scripts/backfill_tutar_niteligi.py).
    """
    nitelik = _tutar_niteligi(tesvik)
    if nitelik:
        return nitelik in TOPLAMA_GIRMEYEN_NITELIKLER
    if (tesvik.kurum or "").strip().lower() in KREDI_KEFALET_KURUMLARI:
        return True
    metin = (tesvik.tesvil_tutari or "") + " " + (tesvik.tutari_hesaplama_formulu or "")
    return "kredi" in metin.lower()


def toplam_tahmini_destek(sonuclar: list[TesvikEslesmeSonucu], profil: FinancialProfile) -> tuple[float, float]:
    """Eslesen tesviklerin tutar araliklarini toplayarak kaba bir 'toplam
    alinabilecek destek' araligi verir.

    ONCEKI HATA: bu fonksiyon tesvil_tutari SERBEST METNINI (orn. 'Dekar
    basina 500-2000 TL') duz metin olarak parse edip MUTLAK bir tutarmis
    gibi topluyordu - yani 50 dekarlik bir ciftci icin gercekte
    50*500=25.000 TL olmasi gereken bir destek, ekranda 500 TL olarak
    gorunuyordu (kullanicinin arazi buyuklugu hic carpilmiyordu). Simdi
    yapisal tutari_min/tutari_max + tutari_hesaplama_kriteri alanlari
    doluysa (guvenilir, olcekli hesap) o kullanilir; sadece bu alanlar bos
    olan eski/is-lenmemis kayitlar icin metin parse'ina (yaklasik, olceksiz)
    dusulur.

    IKINCI HATA (bununla birlikte duzeltildi): KGF'nin urunleri HIBE degil
    KREDI KEFALETIDIR (bkz. app/models.py KurumIletisim dokumantasyonu,
    scripts/seed_kurum_iletisim.py) - "₺20.000.000'a kadar kredi" bir
    banka kredisinin ust siniridir, cepten alinacak bir para degildir.
    Bunlari diger kurumlarin (KOSGEB, Tarim Bakanligi, TUBITAK) gercek
    hibe/nakit destekleriyle toplamak kategori hatasidir ve "toplam
    tahmini destek" rakamini anlamsiz sekilde sisirir (test: genel bir
    tarim profiline 20 kayit eslesip toplam ₺43 milyona cikiyordu, buyuk
    kismi KGF kredi limitlerinden). KGF kayitlari bu toplamdan haric
    tutulur; kullanici bunlari ayri bir 'kredi/kefalet secenekleri'
    listesi olarak gormelidir, nakit destek toplamiyla karistirilmamalidir."""
    # UCUNCU HATA: birbirini DISLAYAN kayitlar birlikte toplaniyordu. 50 dekar
    # bugday eken bir ciftcinin toplamina "Meyve-Sebze Uretim Destekleri" ve
    # "Sera/Ortualti Tarim Destekleri" de ekleniyordu (olcum 2026-09-26) - ayni
    # tarlada hem bugday hem serada sebze yetistirmiyor. Kaydin alt_kategori'si
    # kullanicinin kategorisiyle celisiyorsa toplama KATILMIYOR. Kayit listede
    # gorunmeye devam eder (bilgi degerli), yalnizca toplama girmez.
    #
    # DORDUNCU HATA: proje bazli hibelerin PROGRAM TAVANI toplama giriyordu.
    # "Sulama Yatirimi Destekleri" metninde 100.000-1.000.000 TL yaziyor ama bu
    # programin ust siniri; 50 dekarlik bir ciftcinin alacagi tutar degil.
    # Boyle iki kayit, o ciftcinin toplamini 1,6 milyon TL'ye cikariyordu
    # (olcum 2026-09-26) - KGF kredi limitleriyle ayni kategori hatasi.
    #
    # Cozum metinden TAHMIN ETMEK degil, veride ISARETLEMEK: proje bazli
    # kayitlarda uygunluk_kriterleri["tutar_niteligi"] == "proje_bazli_tavan".
    # Mutlak hibe araliklari (orn. KOSGEB "100.000-200.000 TL") toplama
    # girmeye devam eder, cunku bunlar gercekten alinabilecek tutarlardir.
    # Isaretli kayitlar proje_bazli_destekler() ile ayri sunulur.
    profil_kategorisi = (profil.tarim_kategori or "").strip().lower()
    if profil_kategorisi in BELIRTILMEMIS_KATEGORILER:
        profil_kategorisi = urun_turunden_tarim_kategorisi(profil.urun_turu) or ""

    toplam_min = 0.0
    toplam_max = 0.0
    for s in sonuclar:
        tesvik = s.tesvik
        if _kredi_kefaleti_mi(tesvik):
            continue
        if tesvik.aktif_mi is False:
            continue  # kapanmis programin tutari toplama girmemeli

        alt_kategori = (tesvik.uygunluk_kriterleri or {}).get("alt_kategori")
        if (alt_kategori and profil_kategorisi
                and alt_kategori != profil_kategorisi
                and (tesvik.uygunluk_kriterleri or {}).get("genislik") == "dar"):
            # Yalnizca "dar" (dislayici) programlar atlanir; sulama/organik/
            # makinelestirme gibi "genis" programlar urun turunden bagimsizdir.
            continue

        if _proje_bazli_tavan_mi(tesvik):
            continue

        if tesvik.tutari_hesaplama_kriteri and tesvik.tutari_min is not None:
            olcek = _tutar_olcek_faktoru(tesvik.tutari_hesaplama_kriteri, profil)
            if olcek is None:
                continue  # profildeki ilgili alan (dekar/calisan) eksik
            toplam_min += olcek * tesvik.tutari_min
            toplam_max += olcek * (tesvik.tutari_max or tesvik.tutari_min)
            continue

        alt, ust = _tutari_parse(tesvik.tesvil_tutari)
        if alt is not None:
            toplam_min += alt
            toplam_max += ust

    return round(toplam_min, 2), round(toplam_max, 2)


def proje_bazli_destekler(sonuclar: list[TesvikEslesmeSonucu]) -> list[dict]:
    """Yapisal (olceklenebilir) tutari olmayan, proje bazli degerlendirilen
    destekler.

    Bunlar toplam tahmini destege KATILMAZ cunku metinlerindeki rakam
    kullanicinin olcegiyle iliskili degil, programin ust siniridir. Ama
    kullanicinin bu programlari gormesi gerekir - sadece "bu tutar sizin
    icin hesaplanamaz" bilgisiyle birlikte.
    """
    liste = []
    for s in sonuclar:
        t = s.tesvik
        if t.aktif_mi is False:
            continue
        if not (_kredi_kefaleti_mi(t) or _proje_bazli_tavan_mi(t)):
            continue  # toplama girdi, burada tekrar gosterilmez
        metin = (t.tesvil_tutari or "").strip()
        if not metin:
            continue
        liste.append({
            "baslik": t.baslik,
            "kurum": t.kurum,
            "program_tutari_metni": metin,
            "kredi_kefalet_mi": _kredi_kefaleti_mi(t),
            "tutar_niteligi": _tutar_niteligi(t),
            "not": _NITELIK_ACIKLAMALARI.get(
                _tutar_niteligi(t) or "",
                "Bu kaydın tutarı sizin ölçeğinize göre hesaplanamıyor; "
                "metindeki rakam programın üst sınırı olabilir."),
        })
    return liste
