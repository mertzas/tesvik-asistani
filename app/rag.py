"""
Anahtar-kelime tabanli retrieval + Claude API ile dogal dil cevap uretimi.

Onceki surumde yerel Ollama (Gemma) denenmisti ama tek cevap 130-140sn
suruyordu (CPU-bound) - interaktif chat icin kullanilamaz oldugu icin
kapatilmisti (OLLAMA_ETKIN=False, kod hala asagida duruyor). Su an
birincil yol Claude API (Anthropic) - ANTHROPIC_API_KEY .env'de tanimliysa
kullanilir; tanimli degilse veya cagri basarisiz olursa OTOMATIK olarak
LLM'siz duz liste formatina (_liste_formati) duser - kullanici hicbir
zaman bos/hatali bir ekranla karsilasmaz.

KRITIK KURAL: LLM'e verilen sistem promptu SADECE veritabanindan (Tesvik
kayitlari + KurumIletisim rehberi + kullanicinin FinancialProfile'i) gelen
bilgiyi kullanmasini, telefon numarasi/oran/tutar gibi somut rakamlari
UYDURMAMASINI acikca soyler. KurumIletisim tablosundaki her telefon
numarasi resmi kurum sayfasindan WebFetch ile tek tek dogrulanmistir
(bkz. scripts/seed_kurum_iletisim.py, app/models.py KurumIletisim
docstring'i) - LLM egitim verisinden gelen "hatirlanan" numaralar degil.
"""
import logging
import re
from typing import NamedTuple

import requests

from sqlalchemy.orm import selectinload
from app.ihtiyac import isletmeye_yonelik_mi, program_ihtiyaclari, soru_ihtiyaclari
from app.match_adapter import company_from_profile, program_from_tesvik
from app.match_scoring import hard_filter
from app.matching import uygunluk_engeli
from app.kobi import kobi_sinifi
from app.girisim import GIRISIM_PROMPT_EKI, girisim_baglam_metni, girisim_modu_mu
from app.nace_extraction import clean_grant_text
from app.tesvik_9903_uygunluk import SIRALAMA_ETKISI as UYGUNLUK_9903_ETKISI, kayit_icin as uygunluk_9903
from app.models import SessionLocal, Tesvik, KurumIletisim, IlTarimMudurlugu, IlKosgebMudurlugu, settings
from sqlalchemy import or_

from app.urun_sektor_anahtarlari import (
    anahtar_kelimeden_sektor_bul,
    govde,
    kucult,
)

logger = logging.getLogger(__name__)

OLLAMA_ETKIN = False  # True yapinca Gemma ile dogal dil cevap tekrar devreye girer
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma4"
OLLAMA_TIMEOUT_SEC = 150

CLAUDE_TIMEOUT_SEC = 90  # 5 başlıklı danışman yanıtı ~3000 token; 30 sn yetmiyordu
# Güncel modeller (claude-sonnet-5) varsayılan olarak adaptif düşünme yapar ve düşünme
# token'ları da max_tokens'tan düşer: 3000 iken ~2100'ü düşünmeye gidip yanıt yarıda
# kesiliyordu (ölçüm 2026-10-07). Bütçe geniş, derinlik effort ile sınırlanıyor.
CLAUDE_MAX_TOKENS = 16000
CLAUDE_EFFORT = "medium"
CEVAP_KAYIT_SAYISI = 8   # danışmana verilen kayıt sayısı (çok ihtiyaçlı sorularda kota için)
DETAY_KARAKTER = 2500    # kayıt başına danışmana giden detay metni (temizlendikten sonra)
HAVUZ_BOYUTU = 60        # ihtiyaç/profil katmanının kelime aramasından aldığı aday sayısı  # low | medium | high; danışman yanıtı için gecikme/kalite dengesi
KESILDI_NOTU = "\n\n*(Yanıt uzunluk sınırında kesildi; sorunuzu daraltarak tekrar sorabilirsiniz.)*"

# Anlamli sinyal tasimayan, aramada gurultu yaratan kisa/genel kelimeler.
# Aramada anlamsiz olan ama ILIKE '%...%' ile veritabaninin cogunluguna
# eslesen kelimeler. Olcum (2026-09-26): "ben" 176 kaydin 46'sina ("benzeri",
# "beklenen" icinde), "ile" 168'ine eslesiyordu - yani kullanici "ben cilek
# yetistiriyorum" yazdiginda sonuc kumesi neredeyse tum veritabani oluyor ve
# siralama anlamsizlasıyordu. Liste bilerek yalnizca islev kelimelerini
# iceriyor; "destek", "hibe", "kredi" gibi anlam tasiyan kelimeler DISARIDA.
DURAK_KELIMELER = {
    # soru ve baglac
    "için", "icin", "ile", "hangi", "hangisi", "nasıl", "nasil", "nedir",
    "neler", "nelerdir", "kimler", "veya", "ya", "yada", "ama", "ancak",
    "ise", "gibi", "kadar", "göre", "gore",
    # zamir
    "ben", "bana", "benim", "sen", "size", "siz", "sizin", "biz", "bize",
    "bizim", "bunu", "bunlar", "bunları", "bunlari", "onlar", "kendi",
    # yaygin dolgu
    "var", "yok", "olan", "olur", "olabilir", "daha", "çok", "cok", "şey",
    "sey", "sonra", "önce", "once", "istiyorum", "istiyoruz", "yapmak",
    "almak", "arıyorum", "ariyorum", "hakkında", "hakkinda", "mı", "mi", "mu", "mü", "bir", "bu",
    "şu", "su",
    "the", "and", "des",
}

SISTEM_PROMPTU = """Sen; Ar-Ge, inovasyon, dijital dönüşüm, ihracat, istihdam, tarım ve yatırım \
teşvikleri (KOSGEB, TÜBİTAK, Sanayi ve Teknoloji Bakanlığı, Ticaret Bakanlığı, Tarım ve \
Orman Bakanlığı, KGF vb.) konusunda uzmanlaşmış kıdemli bir Teşvik ve Hibe Danışmanısın. \
Görevin; kullanıcının şirket yapısını, projesini veya harcama kalemlerini analiz ederek \
en doğru teşvik programlarıyla eşleştirmek, uygunluk kriterlerini netleştirmek ve \
başvuru stratejisi oluşturmaktır.

MUTLAK KURAL - UYDURMA YASAK: Sana aşağıda "BAĞLAM" başlığı altında verilen \
teşvik kayıtları ve kullanıcı profili DIŞINDA hiçbir somut bilgi (telefon \
numarası, destek oranı, üst limit, tutar, tarih, çağrı dönemi, kurum adı) UYDURMA. \
Bağlamda olmayan bir bilgiye ihtiyaç varsa "bu bilgi elimde yok, ilgili çağrı \
rehberinden / kurumun resmi sitesinden teyit edin" de ve varsa bağlamdaki kaynak \
URL'sini ver. Sayısal bir rakam (telefon, oran, TL tutarı, TRL eşiği, süre) bağlamda \
geçmiyorsa ASLA kendi bilginden tahmin/icat etme. Genel mevzuat bilgisi (ör. bir \
platformun adı) kullandığında bunun bağlamdan değil genel bilgiden geldiğini ve \
teyit edilmesi gerektiğini belirt.

AKTİFLİK KURALI: Bir kaydın yanında "⚠️ DURUM: ARTIK AKTİF DEĞİL" yazıyorsa, \
bu programı kullanıcıya başvurabileceği bir seçenek gibi SUNMA - varlığından \
bahsedebilirsin ama açıkça "bu program artık kapalı/geçmiş" de. "DURUM: \
Doğrulanmış, güncel/aktif program" yazan kayıtları güvenle önerebilirsin. \
Hiçbir durum notu yoksa (aktiflik hiç kontrol edilmemişse), kullanıcıya \
"bu programın hâlâ açık olup olmadığını kurumun kendi sayfasından teyit edin" \
diye açıkça hatırlat.

SİSTEM ÖN DEĞERLENDİRMESİ: Bazı kayıtların altında "SİSTEM ÖN DEĞERLENDİRMESİ" satırı \
bulunur; bu, Karar metnindeki listelerden (EK-1, EK-3) ve profilden hesaplanmıştır. "UYGUN \
DEĞİL" ise programı önermeyip gerekçesini (madde numarasıyla) söyle; "ŞARTLI" ve "DÜŞÜK \
OLASILIK" için şartı açıkça yaz; "BELİRLENEMEDİ" için hangi listenin teyit edilmesi \
gerektiğini belirt. Bu değerlendirmeyi kendi tahmininle çelişecek biçimde değiştirme. \
"SİSTEMİN ELEDİĞİ 9903 PROGRAMLARI" bloğu varsa, kullanıcı yatırım teşviki sorduğunda bu \
programlara neden başvuramayacağını gerekçe ve madde numarasıyla açıkça söyle; yürürlükten \
kalkmış eski sistemleri (Genel/Bölgesel Teşvik vb.) seçenek gibi sunma.

NET VE DÜRÜST ELEME: Şirket veya proje bir program için uygun değilse bunu doğrudan, \
gerekçesiyle söyle; hangi şartı sağlamadığını (NACE/sektör, KOBİ ölçeği, çalışan/ciro \
sınırı, il/bölge, hedef kitle, teknoloji düzeyi) belirt. Umut tacirliği yapma. Profilde \
"KOBİ ölçeği" verilmişse onu kullan; "kesin değil" notu varsa bunu söyle.

ÇİFT YÖNLÜ ANALİZ: Her öneri için yalnızca kazancı değil; teminat/kefalet, geri ödeme, \
bürokrasi ve raporlama yükü, denetim ve geri alma riskini de belirt. Bu riskler bağlamda \
somut olarak geçmiyorsa genel uyarı olarak ifade et, rakam verme.

Yanıtını şu 5 başlık altında yapılandır (soru tek bir küçük ayrıntıyla ilgiliyse \
ilgili başlıkları kısa tut, boş başlık doldurmak için bilgi üretme):

### 1. Şirket & Proje Uygunluk Özeti
NACE/sektör uygunluğu, ölçek (Mikro/Küçük/Orta/Büyük), projenin niteliği (Ar-Ge mi, \
yatırım mı, operasyonel mi). Profilde olmayanı varsayma; "bilinmiyor" de.

### 2. Eşleşen Teşvik ve Hibe Programları
Bağlamdaki programlardan uygun olanlar: kurum ve program adı, destek türü (hibe, faiz/kar \
payı desteği, kefalet, vergi/SGK), oran ve üst limit (SADECE bağlamda geçiyorsa), \
desteklenen kalemler (bağlamda geçiyorsa). Uygun OLMAYAN ama akla gelebilecek programları \
gerekçesiyle ayrıca eleyebilirsin.

### 3. Darboğazlar ve Kritik Şartlar
Reddedilmeye yol açabilecek noktalar; ön koşul kayıtlar, özkaynak, asgari personel gibi \
şartlar (bağlamdaki başvuru şartlarından); teminat, geri ödeme ve denetim riskleri.

### 4. Adım Adım Yol Haritası
Başvuru öncesi hazırlık (kayıt sistemleri, e-imza vb.), dokümantasyon ve bütçe, \
başvuru yeri/kanalı (bağlamdaki kaynak URL ve iletişim bilgileriyle). Değerlendirme \
süresi bağlamda yoksa tahmin etme.

### 5. Bilgi Eksikliği / Netleştirme
Eşleştirme için profilde eksik olan en kritik 3-4 bilgiyi soru olarak sor (ör. NACE kodu, \
çalışan ve ciro, projenin somut çıktısı, şirket türü). Profil yeterliyse bu başlığı tek \
cümleyle geç.

İletişim tonu: doğrudan, net, operasyonel. Motivasyon cümlesi kurma; mevzuat, bütçe ve \
süreç odaklı konuş. Kısa maddeler ve kalın vurgular kullan. Emin olmadığın her yerde \
bunu açıkça belirt ve teyit iste. Türkçe yanıt ver."""


def _terimlere_ayir(query: str) -> list[str]:
    # kucult() kullaniliyor, str.lower() DEGIL: Python'da "İ".lower() tek harf
    # degil "i̇" (i + U+0307 birlesik nokta) uretiyor, dolayisiyla caps lock
    # ile yazan kullanicinin terimleri hicbir kayda eslesmiyordu
    # (dogrulandi 2026-09-26, bkz. app/urun_sektor_anahtarlari.kucult).
    terms = [kucult(t.strip(".,!?:;\"'()")) for t in query.split()]
    return [t for t in terms if len(t) > 2 and t not in DURAK_KELIMELER]


def retrieve(query: str, limit: int = 5, profil_kaydi=None) -> list[Tesvik]:
    """Soruyla ilgili teşvik kayıtları.

    İki katman:
      1. Kelime araması (_metin_aramasi): Türkçe gövde, program kodu, sektör
         genişlemesi. Soruda ihtiyaç türü yoksa ve profil verilmemişse sonuç
         doğrudan budur.
      2. İhtiyaç + profil katmanı: sorudaki ihtiyaç türleri (makine yatırımı,
         Ar-Ge, ihracat...) kelime eşleşmesi olmayan ama o ihtiyaca hizmet eden
         programları da havuza katar; profil verilmişse uygun olmayan programlar
         (sektör etiketi, NACE, KOBİ ölçeği, il, hedef kitle) aramadan önce elenir.
         Birden çok ihtiyaç varsa her birine kota ayrılır.

    Ölçüm (2026-10-07): "ekmek hattı için makine + ürün geliştirme" sorusunda
    kelime araması 5 kaydın 3'ünü tarım programlarına veriyor, 9903 yatırım
    teşviklerini hiç getirmiyordu.
    """
    ihtiyaclar = soru_ihtiyaclari(query)
    if not ihtiyaclar and profil_kaydi is None:
        return _metin_aramasi(query, limit)

    metin_sonucu = _metin_aramasi(query, HAVUZ_BOYUTU)
    sira = {t.id: i for i, t in enumerate(metin_sonucu)}
    havuz = list(metin_sonucu)
    if ihtiyaclar:
        aranan = set(ihtiyaclar)
        db = SessionLocal()
        try:
            for t in db.query(Tesvik).options(selectinload(Tesvik.nace_kayitlari)).all():
                if t.id not in sira and program_ihtiyaclari(t) & aranan:
                    db.expunge(t)
                    havuz.append(t)
        finally:
            db.close()

    # Akademik/etkinlik TÜBİTAK çağrıları işletme sorularında kotayı doldurmasın
    # ("yurt dışı fuar" sorusu 2224 bilimsel etkinlik çağrılarını getiriyordu);
    # kullanıcı program kodunu yazdıysa (ör. "2224") korunur.
    kodlar = [x for x in _terimlere_ayir(query) if x.isdigit()]
    havuz = [t for t in havuz if isletmeye_yonelik_mi(t)
             or any(kucult(t.baslik or "").startswith(k) for k in kodlar)]

    degerlendirme_9903: dict[int, object] = {}
    if profil_kaydi is not None:
        sirket = company_from_profile(profil_kaydi)
        havuz = [t for t in havuz if _profile_uygun_mu(t, sirket, profil_kaydi)]
        # 9903 programları: EK-3 şartı aranan programda konu listede yoksa (kesin hukuki
        # sonuç) elenir; diğer sonuçlar sıralamayı etkiler (bkz. app/tesvik_9903_uygunluk.py).
        degerlendirme_9903 = profil_9903_degerlendirmesi(havuz, profil_kaydi)
        havuz = [t for t in havuz
                 if getattr(degerlendirme_9903.get(t.id), "durum", None) != "uygun_degil"]

    aranan = set(ihtiyaclar)
    profil_sektor = (getattr(profil_kaydi, "sektor", None) or "").lower()

    def puan(t: Tesvik) -> float:
        # İhtiyaç eşleşmesi kelime sırasından baskın: kelime araması "geliştirme",
        # "kapasite" gibi genel kelimelerle alakasız programları öne taşıyordu.
        p = 0.0
        if t.id in sira:
            p += 1.0 * (1 - sira[t.id] / max(len(metin_sonucu), 1))
        p += 3.0 * len(program_ihtiyaclari(t) & aranan)
        etiketler = {x.lower() for x in (t.uygunluk_kriterleri or {}).get("sektorler", [])}
        if profil_sektor and profil_sektor in etiketler and "genel" not in etiketler:
            p += 1.0  # sektöre özgü program, "genel" programdan daha isabetli
        if t.aktif_mi is True:
            p += 0.3
        elif t.aktif_mi is False:
            p -= 5.0  # kapalı programı başvurulabilir seçeneklerin önüne koyma
        u = degerlendirme_9903.get(t.id)
        if u is not None:
            p += UYGUNLUK_9903_ETKISI[u.durum]
        return p

    havuz.sort(key=lambda t: (-puan(t), t.id))
    secilen: list[Tesvik] = []
    if len(ihtiyaclar) > 1:
        kota = max(1, limit // len(ihtiyaclar))
        for ihtiyac in ihtiyaclar:
            adaylar = [t for t in havuz if ihtiyac in program_ihtiyaclari(t) and t not in secilen]
            secilen.extend(adaylar[:kota])
    for t in havuz:
        if len(secilen) >= limit:
            break
        if t not in secilen:
            secilen.append(t)
    secilen = secilen[:limit]
    secilen.sort(key=lambda t: (-puan(t), t.id))
    return secilen


def profil_9903_degerlendirmesi(kayitlar, profil_kaydi) -> dict:
    """{tesvik_id: Uygunluk9903} - yalnızca 9903 program kayıtları için."""
    if profil_kaydi is None:
        return {}
    olcek = kobi_sinifi(profil_kaydi.calisan_sayisi, profil_kaydi.yillik_ciro)
    sonuc = {}
    for t in kayitlar:
        u = uygunluk_9903(t, getattr(profil_kaydi, "nace_kodu", None), profil_kaydi.bolge,
                          olcek.sinif if olcek.kesin else None)
        if u is not None:
            sonuc[t.id] = u
    return sonuc


ESKI_SISTEM_NOTU = (
    "2012/3305 sayılı Karar (Genel, Bölgesel, Büyük Ölçekli ve Stratejik Yatırımların Teşviki) "
    "9903 sayılı Karar ile yürürlükten kalkmıştır; bu eski sistemlere başvurulamaz.")


# Kullanıcının adıyla sorduğu, yürürlükten kalkmış yatırım teşvik sistemleri. Bu kayıtlar
# kapalı (aktif_mi=False) olduğu için bağlama girmiyor; model genel bilgisiyle cevaplamak
# zorunda kalıyordu (ölçüm 2026-10-07: "2012/3305 Bölgesel Teşvik'ten yararlanabilir miyim?").
_ESKI_SISTEM = re.compile(r"3305|bolgesel\s+tesvik|bölgesel\s+teşvik|genel\s+tesvik|genel\s+teşvik|"
                          r"buyuk\s+olcekli|büyük\s+ölçekli")


def eski_sistem_notu(query: str) -> str:
    """Soru eski sistemi (2012/3305) anıyorsa danışmana giden kesin not; yoksa ''."""
    return f"Not: {ESKI_SISTEM_NOTU}" if _ESKI_SISTEM.search(kucult(query)) else ""


def elenen_9903_metni(query: str, profil_kaydi) -> str:
    """Profil nedeniyle elenen 9903 programları - danışman 'neden yok' sorusunu yanıtlayabilsin.

    Elenen kayıt bağlama hiç girmezse model "bu program hakkında bilgim yok" diyor ve
    kullanıcının asıl sorusuna ("teşvik belgesi alabilir miyim?") cevap veremiyordu
    (ölçüm 2026-10-07). Yalnızca yatırım ihtiyacı olan sorularda eklenir."""
    if profil_kaydi is None or "yatirim" not in soru_ihtiyaclari(query):
        return ""
    db = SessionLocal()
    try:
        kayitlar = [t for t in db.query(Tesvik).all() if t.aktif_mi is not False]
        degerlendirme = profil_9903_degerlendirmesi(kayitlar, profil_kaydi)
        satirlar = [f"- {t.baslik}: {degerlendirme[t.id].metin()}"
                    for t in kayitlar
                    if t.id in degerlendirme and degerlendirme[t.id].durum == "uygun_degil"]
    finally:
        db.close()
    if not satirlar:
        return ""
    return ("SİSTEMİN ELEDİĞİ 9903 PROGRAMLARI (Karar metnine göre bu profil için uygun değil):\n"
            + "\n".join(satirlar) + f"\nNot: {ESKI_SISTEM_NOTU}")


def _profile_uygun_mu(t: Tesvik, sirket, profil_kaydi) -> bool:
    """esles() ile aynı eleme kuralları: sektör etiketi + katı eleme + kayıt metnine
    dayalı uygunluk engelleri (akademik çağrı, aracı kuruluş, şirketleşme şartları).

    Ölçüm 2026-10-07 (15 soruluk bağlam denetimi): şirketsiz girişimciye 10962 (TTK
    şirketi şart), KOSGEB kredisi, TEKMER işletici programı ve KGF; limited şirkete
    ortaklık yasaklı BiGG 1512/1812 danışman bağlamına giriyordu."""
    etiketler = {s.lower() for s in (t.uygunluk_kriterleri or {}).get("sektorler", [])}
    profil_sektor = (getattr(profil_kaydi, "sektor", None) or "").lower()
    if etiketler and profil_sektor and profil_sektor not in etiketler and "genel" not in etiketler:
        return False
    sebepler, _ = hard_filter(sirket, program_from_tesvik(t), strict_sector=True)
    if sebepler:
        return False
    return uygunluk_engeli(t, profil_kaydi) is None


def _metin_aramasi(query: str, limit: int = 5) -> list[Tesvik]:
    db = SessionLocal()
    terms = _terimlere_ayir(query)
    q = db.query(Tesvik).options(selectinload(Tesvik.nace_kayitlari))
    if terms:
        # Her terim icin hem tam hali hem govdesi araniyor (bkz. govde()).
        aranacak = []
        for t in terms:
            aranacak.append(t)
            g = govde(t)
            if g != t:
                aranacak.append(g)
        conditions = [
            Tesvik.baslik.ilike(f"%{t}%") | Tesvik.ozet.ilike(f"%{t}%") | Tesvik.detay.ilike(f"%{t}%")
            for t in aranacak
        ]
        q = q.filter(or_(*conditions))
    candidates = q.order_by(Tesvik.guncelleme_tarihi.desc()).limit(200).all()
    db.close()

    if not terms:
        return candidates[:limit]

    def skor(t: Tesvik) -> float:
        # Ham terim sayimi, uzun "detay" metinli kayitlari (genel gecer
        # kelimeleri cok kez tekrarladiklari icin) tam program kodu eslesmesi
        # (orn. "1507") yapan kisa kayitlara karsi haksiz yere on plana
        # cikariyordu - detay/ozet katkisini metin uzunluguna gore normalize
        # ediyoruz, baslik eslesmesine (ozellikle program kodu gibi tam
        # eslesmelere) çok daha yuksek agirlik veriyoruz.
        metin = kucult(f"{t.ozet or ''} {t.detay or ''}")
        baslik_kucuk = kucult(t.baslik or "")
        # Tam terim eslesmesi govde eslesmesinden daha degerli: "serası" ile
        # birebir eslesen kayit, yalnizca "sera" govdesiyle eslesenin onunde
        # olmali.
        metin_skoru = 0.0
        baslik_skoru = 0.0
        for term in terms:
            g = govde(term)
            metin_skoru += metin.count(term) * 1.0
            baslik_skoru += 10 if term in baslik_kucuk else 0
            if g != term:
                metin_skoru += metin.count(g) * 0.5
                baslik_skoru += 6 if g in baslik_kucuk else 0
        metin_skoru = metin_skoru / max(len(metin), 1) * 1000
        tam_kod_bonus = sum(20 for term in terms
                            if term.isdigit() and baslik_kucuk.startswith(term))
        return metin_skoru + baslik_skoru + tam_kod_bonus

    candidates.sort(key=skor, reverse=True)

    # SEKTOR GENISLEMESI
    #
    # Sorguda taninan bir urun/faaliyet adi geciyorsa (orn. "cilek", "sut"),
    # o sektore etiketli kayitlar gevsek bir ILIKE eslesmesinden DAHA
    # alakalidir. Program adlari nadiren urun adi gecirdigi icin
    # (bkz. app/urun_sektor_anahtarlari.py) literal arama tek basina
    # yaniltici sonuc veriyor.
    #
    # Iki somut hata bu blokla kapandi (ikisi de 2026-09-26'da olculdu):
    #
    # 1) Genisleme yalnizca app/main.py sor() icinde, kullaniciya gosterilen
    #    SONUC LISTESI icin yapiliyordu; answer() ham soruyla cagrildigi icin
    #    Claude bu kayitlari HIC gormuyordu. "CILEK SERASI ICIN HIBE VAR MI"
    #    sorgusu listede 10 dogru kayit ("Sera/Ortualti Tarim Destekleri"
    #    dahil) gosterirken ayni yanitin mesaj alani "eslesen bir tesvik
    #    bulamadim" diyordu - ayni ekranda birbiriyle celisen iki cevap.
    #
    # 2) Genislemeyi "literal sonuc azsa ekle" seklinde yazmak yetmiyor:
    #    ayni sorguda "hibe" kelimesi 5 alakasiz KGF kredi kaydina eslesip
    #    kotayi doldurdugu icin genisleme HIC tetiklenmiyordu. Bu yuzden
    #    sektor eslesmelerine kotanin bir kismi AYRILIYOR.
    hedef_sektor = anahtar_kelimeden_sektor_bul(query)
    if not hedef_sektor:
        return candidates[:limit]

    literal_idler = {t.id for t in candidates}
    sektor_kayitlari = _sektor_kayitlari(hedef_sektor, skor)

    # Kotanin en az %60'i sektor eslesmelerine ayrilir; kalan yer literal
    # eslesmelere kalir, boylece program kodu gibi tam eslesmeler kaybolmaz.
    sektor_payi = max(1, round(limit * 0.6))
    secilen = sektor_kayitlari[:sektor_payi]
    secilen_idler = {t.id for t in secilen}
    for t in candidates:
        if len(secilen) >= limit:
            break
        if t.id not in secilen_idler:
            secilen.append(t)
            secilen_idler.add(t.id)

    # Kota dolmadiysa kalan sektor kayitlariyla tamamla.
    for t in sektor_kayitlari[sektor_payi:]:
        if len(secilen) >= limit:
            break
        if t.id not in secilen_idler:
            secilen.append(t)
            secilen_idler.add(t.id)

    # Sektor kayitlari kendi metin skoruna gore one gecsin, ama literal
    # eslesme yapanlar (ayni zamanda sektorde olanlar) en ustte kalsin.
    secilen.sort(key=lambda t: (t.id not in literal_idler, -skor(t)))
    return secilen[:limit]


def _sektor_kayitlari(sektor: str, skor) -> list[Tesvik]:
    """Verilen sektore etiketli tesvikleri, metin skoruna gore sirali doner."""
    db = SessionLocal()
    try:
        bulunan = []
        for t in db.query(Tesvik).options(selectinload(Tesvik.nace_kayitlari)).all():
            if t.aktif_mi is False:
                continue  # kapanmis programi one cikarmanin anlami yok
            etiketler = {
                x.lower()
                for x in (t.uygunluk_kriterleri or {}).get("sektorler", [])
            }
            if sektor in etiketler:
                db.expunge(t)  # oturum kapandiktan sonra alanlar okunabilsin
                bulunan.append(t)
        bulunan.sort(key=skor, reverse=True)
        return bulunan
    finally:
        db.close()


def _kisalt(metin: str, uzunluk: int = 220) -> str:
    metin = " ".join(metin.split())
    if len(metin) <= uzunluk:
        return metin
    return metin[:uzunluk].rsplit(" ", 1)[0] + "…"


def _liste_formati(matches: list[Tesvik]) -> str:
    """LLM'siz fallback: kayitlari duz liste olarak formatlar."""
    baslik_satiri = f"Sorunuzla ilgili {len(matches)} destek/teşvik programı buldum:\n"
    satirlar = [baslik_satiri]
    for i, m in enumerate(matches, start=1):
        satirlar.append(
            f"\n{i}. [{m.kurum}] {m.baslik}\n"
            f"   {_kisalt(m.ozet)}\n"
            f"   Kaynak: {m.kaynak_url}"
        )
    satirlar.append(
        "\n\nNot: Bu cevap veritabanındaki kayıtlardan otomatik oluşturuldu, "
        "kesin başvuru şartları için ilgili kurumun sayfasını kontrol edin."
    )
    return "".join(satirlar)


def _kurum_iletisim_metni(matches: list[Tesvik]) -> str:
    """Bulunan kayitlarin ait oldugu kurumlarin dogrulanmis iletisim
    bilgilerini doner - bos ise (kurum rehberde yoksa) o kurum icin
    satir eklenmez, LLM'in numara icat etmesine gerek kalmaz."""
    kurumlar = sorted({m.kurum for m in matches if m.kurum})
    if not kurumlar:
        return ""

    db = SessionLocal()
    try:
        satirlar = []
        for kurum in kurumlar:
            k = db.query(KurumIletisim).filter(KurumIletisim.kurum == kurum).first()
            if k is None:
                continue
            satirlar.append(
                f"- {k.kurum} ({k.kurum_tam_ad or ''}): Çağrı merkezi {k.cagri_merkezi_no or '—'}, "
                f"Genel merkez {k.genel_merkez_no or '—'}, Adres: {k.adres or '—'}. "
                f"(Doğrulama kaynağı: {k.kaynak_url}, doğrulama tarihi: {k.dogrulama_tarihi})"
            )
        return "\n".join(satirlar)
    finally:
        db.close()


def _il_iletisim_metni(profil: dict | None) -> str:
    """Kullanicinin profilindeki 'bölge' (il adi) alaniyla eslesen Tarim Il
    Mudurlugu satirini doner. Telefon/adres o il icin dogrulanmamissa
    (url_dogrulandi=False) SADECE resmi linki verir, numara/adres uydurmaz -
    LLM'e "bu ilin telefonu dogrulanmadi, linke yonlendir" bilgisini de
    acikca gecirir."""
    if not profil:
        return ""
    il_adi = (profil.get("bölge") or "").strip()
    if not il_adi:
        return ""

    db = SessionLocal()
    try:
        il = db.query(IlTarimMudurlugu).filter(IlTarimMudurlugu.il_adi.ilike(il_adi)).first()
        if il is None:
            return ""
        if il.url_dogrulandi:
            return (
                f"{il.il_adi} Tarım ve Orman İl Müdürlüğü: Telefon {il.telefon}, "
                f"Adres: {il.adres}. (Doğrulama kaynağı: {il.kaynak_url}, "
                f"doğrulama tarihi: {il.dogrulama_tarihi})"
            )
        return (
            f"{il.il_adi} Tarım ve Orman İl Müdürlüğü için telefon/adres henüz "
            f"doğrulanmadı - kullanıcıyı resmi sayfaya yönlendir: {il.kaynak_url} "
            f"(telefon numarası UYDURMA, sadece bu linki ver)."
        )
    finally:
        db.close()


def _kosgeb_il_iletisim_metni(profil: dict | None) -> str:
    """Kullanicinin 'bölge' alaniyla eslesen KOSGEB Il Mudurlugu satirini
    doner. IlTarimMudurlugu'ndan farkli olarak buradaki 81 ilin TAMAMI
    dogrulandi (bkz. scripts/seed_il_kosgeb_mudurlugu.py), o yuzden burada
    "dogrulanmadi" dalina hic gerek yok."""
    if not profil:
        return ""
    il_adi = (profil.get("bölge") or "").strip()
    if not il_adi:
        return ""

    db = SessionLocal()
    try:
        il = db.query(IlKosgebMudurlugu).filter(IlKosgebMudurlugu.il_adi.ilike(il_adi)).first()
        if il is None:
            return ""
        metin = (
            f"{il.mudurluk_adi}: Telefon {il.telefon}, Adres: {il.adres}"
            + (f", E-posta: {il.eposta}" if il.eposta else "")
            + f". (Doğrulama kaynağı: {il.kaynak_url}, doğrulama tarihi: {il.dogrulama_tarihi})"
        )
        if il.ek_mudurlukler:
            for ek in il.ek_mudurlukler:
                metin += f"\nAyrıca: {ek.get('ad')}: Telefon {ek.get('telefon')}, Adres: {ek.get('adres')}"
        return metin
    finally:
        db.close()


# KGF/KOSGEB sayfalarında asıl içerik bu başlıklardan biriyle başlar; öncesi site menüsü
# dökümüdür (ölçüm 2026-10-07: 2024 Dijital Dönüşüm paketinde içerik 8.901. karakterde).
_ICERIK_BASLIKLARI = ("Ürün Açıklaması", "Ürün açıklaması", "Programın Amacı", "Program Amacı",
                      "PROGRAMIN KAPSAMI VE AMACI", "Programın Kapsamı")
_ALT_BILGI = "Buradasınız"


def _icerik_govdesi(detay: str | None) -> str:
    """Menü dökümünü atlayıp içerik başlığından başlar, sayfa alt bilgisinde keser."""
    metin = detay or ""
    konumlar = [i for i in (metin.find(b) for b in _ICERIK_BASLIKLARI) if i > 0]
    bas = min(konumlar) if konumlar else 0
    son = metin.find(_ALT_BILGI, bas + 1)
    return metin[bas: son if son > bas else None]


def _tesvik_detay_metni(m: Tesvik) -> str:
    """Tesvik kaydinin TUM yapilandirilmis alanlarini (sadece serbest metin
    detay degil) LLM baglamina yazar - basvuru_sartlari/tutar/aktif_mi gibi
    Faz 3'te doldurulan alanlar bu fonksiyon olmadan LLM'e hic gorunmezdi."""
    # 500 karakterlik kesme, mevzuat kayıtlarının (9903, 10962) madde bazlı oran/limit
    # listesini yarıda bırakıyordu; model "madde numarası bağlamda yok" diyordu (ölçüm
    # 2026-10-07). Menü/footer gürültüsü ayıklanıp daha uzun bir pencere verilir.
    satirlar = [f"[{m.kurum}] {m.baslik}", f"Kaynak: {m.kaynak_url}",
                _kisalt(clean_grant_text(_icerik_govdesi(m.detay), baslik=m.baslik), DETAY_KARAKTER)]

    if m.aktif_mi is False:
        satirlar.append(f"⚠️ DURUM: ARTIK AKTİF DEĞİL. {m.durum_notu or ''}")
    elif m.aktif_mi is True:
        satirlar.append(f"DURUM: Doğrulanmış, güncel/aktif program. {m.durum_notu or ''}")

    if m.basvuru_sartlari:
        satirlar.append("Başvuru şartları: " + "; ".join(m.basvuru_sartlari))
    if m.gerekli_belgeler:
        satirlar.append("Gerekli belgeler: " + "; ".join(m.gerekli_belgeler))
    if m.basvuru_yeri:
        satirlar.append(f"Başvuru yeri: {m.basvuru_yeri}")
    if m.basvuru_suresi:
        satirlar.append(f"Başvuru süresi/dönemi: {m.basvuru_suresi}")
    if m.destek_verilme_suresi:
        satirlar.append(f"Destek/proje süresi: {m.destek_verilme_suresi}")
    if m.tutari_hesaplama_formulu:
        satirlar.append(f"Tutar/oran: {m.tutari_hesaplama_formulu}")
    elif m.tutari_max:
        satirlar.append(f"Azami tutar: ₺{m.tutari_max:,.0f}")

    return "\n".join(satirlar)


def _baglam_metni(matches: list[Tesvik], profil: dict | None,
                  notlar: dict[int, str] | None = None, elenen: str = "") -> str:
    notlar = notlar or {}
    kayitlar = "\n\n".join(
        _tesvik_detay_metni(m) + (f"\nSİSTEM ÖN DEĞERLENDİRMESİ (profilinize göre, Karar metninden): "
                                  f"{notlar[m.id]}" if m.id in notlar else "")
        for m in matches)
    iletisim = _kurum_iletisim_metni(matches)
    iletisim_blogu = (
        f"\n\nDOĞRULANMIŞ KURUM İLETİŞİM BİLGİLERİ (bu numaraları/adresleri "
        f"kullanabilirsin, kaynağı gösterilmiştir):\n{iletisim}"
        if iletisim else ""
    )

    il_iletisim = _il_iletisim_metni(profil)
    il_blogu = f"\n\nKULLANICININ İLİNE ÖZEL TARIM İLETİŞİMİ: {il_iletisim}" if il_iletisim else ""

    kosgeb_il_iletisim = _kosgeb_il_iletisim_metni(profil)
    kosgeb_il_blogu = (
        f"\n\nKULLANICININ İLİNE ÖZEL KOSGEB MÜDÜRLÜĞÜ: {kosgeb_il_iletisim}"
        if kosgeb_il_iletisim else ""
    )

    if elenen:
        kayitlar = f"{kayitlar}\n\n{elenen}"
    if not profil:
        return f"TEŞVİK KAYITLARI:\n{kayitlar}{iletisim_blogu}\n\nKULLANICI PROFİLİ: (henüz girilmemiş)"

    profil_satirlari = "\n".join(f"- {k}: {v}" for k, v in profil.items() if v not in (None, "", []))
    return (
        f"TEŞVİK KAYITLARI:\n{kayitlar}{iletisim_blogu}{il_blogu}{kosgeb_il_blogu}\n\n"
        f"KULLANICI PROFİLİ:\n{profil_satirlari or '(profil alanları boş)'}"
    )


def _claude_cevap(query: str, matches: list[Tesvik], profil: dict | None,
                  notlar: dict[int, str] | None = None, elenen: str = "",
                  sistem_eki: str = "") -> str | None:
    """Claude API ile bulunan kayitlari + kullanici profilini yorumlayip
    yapilandirilmis cevap uretir. API anahtari yoksa veya cagri basarisiz
    olursa None doner - cagiran taraf liste formatina duser, hicbir zaman
    crash etmez."""
    if not settings.ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    baglam = _baglam_metni(matches, profil, notlar, elenen)

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=SISTEM_PROMPTU + sistem_eki,
            messages=[{
                "role": "user",
                "content": f"BAĞLAM:\n{baglam}\n\nKULLANICI SORUSU: {query}",
            }],
            output_config={"effort": CLAUDE_EFFORT},
            timeout=CLAUDE_TIMEOUT_SEC,
        )
        parcalar = [blok.text for blok in resp.content if getattr(blok, "type", None) == "text"]
        cevap = "".join(parcalar).strip()
        if getattr(resp, "stop_reason", None) == "max_tokens":
            logger.warning("Claude yanıtı max_tokens sınırında kesildi (%s token)",
                           getattr(getattr(resp, "usage", None), "output_tokens", "?"))
            if cevap:
                cevap += KESILDI_NOTU
        return cevap or None
    except Exception as e:
        # Ag hatasi, rate limit, gecersiz anahtar, timeout - hepsi ayni
        # sekilde ele alinir: KULLANICI acisindan sessizce fallback'e dus,
        # onu hata mesajiyla degil cevapla karsila. Ama sebebi MUTLAKA
        # gunluge yaz - aksi halde "AI cevap vermiyor" sikayetinin sebebini
        # (kota? anahtar? ag?) anlamanin hicbir yolu kalmiyor.
        logger.warning("Claude cagrisi basarisiz, liste formatina dusuluyor: %s: %s",
                       type(e).__name__, e)
        return None


def _ollama_cevap(query: str, matches: list[Tesvik]) -> str | None:
    """Yerel Ollama (gemma4) ile bulunan kayitlari dogal dilde yorumlar.
    Ollama'ya erisilemezse (kapali, model yok, timeout) None doner --
    cagiran taraf bu durumda liste formatina duser."""
    baglam = "\n\n".join(
        f"[{m.kurum}] {m.baslik}\nKaynak: {m.kaynak_url}\n{_kisalt(m.detay, 500)}"
        for m in matches
    )
    prompt = (
        "Sen Turkiye'deki KOSGEB, TUBITAK, KGF ve Hazine/Ticaret Bakanligi "
        "tesvik/destek programlari konusunda kullaniciya rehberlik eden bir "
        "asistansin. SADECE asagida verilen baglami kullanarak cevap ver, "
        "baglamda olmayan bilgi uydurma. Her bahsettigin programin yaninda "
        "kaynak URL'sini de belirt. Emin olmadigin durumda kullaniciyi "
        "ilgili kurumun resmi sitesine yonlendir. Kisa ve net Turkce cevap ver.\n\n"
        f"Baglam:\n{baglam}\n\nKullanici sorusu: {query}"
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        data = resp.json()
        cevap = data.get("response", "").strip()
        return cevap or None
    except (requests.RequestException, ValueError):
        return None


def profil_sozlugu(profil_row) -> dict:
    """Rıza varken danışmana (Anthropic'e) giden profil sözlüğü. /api/sor ve ölçüm
    betikleri aynı sözlüğü kullanır; alan ekleme/çıkarma yalnızca burada yapılır."""
    from app.kobi import AD as KOBI_AD
    from app.tesvik_9903_hesap import il_bolgesi

    profil = {
        "sektör": profil_row.sektor,
        "bölge": profil_row.bolge,
        "çalışan sayısı": profil_row.calisan_sayisi,
        "yıllık ciro": profil_row.yillik_ciro,
        "hedefler": profil_row.hedefler,
        "ilk yıl mı": profil_row.ilk_yil_mi,
        "tarım kategorisi": profil_row.tarim_kategori,
        "ürün türü": profil_row.urun_turu,
        "arazi büyüklüğü (dekar)": profil_row.arazi_buyuklugu_dekar,
        "NACE kodu": profil_row.nace_kodu,
        "şirket türü": profil_row.sirket_turu,
        "kuruluş tarihi": (profil_row.kurulus_tarihi.isoformat()
                           if profil_row.kurulus_tarihi else None),
        "TRL (teknoloji hazırlık seviyesi)": profil_row.trl,
    }
    # Ölçek sınıfı türetilmiş bir değerdir (çalışan + ciro); yeni kişisel
    # veri aktarmaz. "kesin değil" ise model bunu kullanıcıya söylesin.
    olcek = kobi_sinifi(profil_row.calisan_sayisi, profil_row.yillik_ciro)
    if olcek.sinif:
        profil["KOBİ ölçeği"] = (KOBI_AD[olcek.sinif]
                                + ("" if olcek.kesin else " (kesin değil: " + olcek.aciklama + ")")
                                + " [KOBİ Yönetmeliği, 7 Ağustos 2025 eşiklerine göre hesaplandı]")
    bolge_no = il_bolgesi(profil_row.bolge) if profil_row.bolge else None
    if bolge_no:
        profil["yatırım teşvik bölgesi (9903 sayılı Karar EK-2)"] = f"{bolge_no}. bölge"
    return profil


BULUNAMADI_METNI = (
    "Bu soruyla eşleşen bir teşvik/destek programı bulamadım. "
    "Farklı anahtar kelimelerle (örn. kurum adı, sektör, \"girişimci\", "
    "\"dijital dönüşüm\" gibi) tekrar deneyebilir ya da doğrudan "
    "KOSGEB, TÜBİTAK, KGF veya Ticaret Bakanlığı'nın resmi sitelerine "
    "bakabilirsiniz."
)


class Hazirlik(NamedTuple):
    matches: list
    notlar: dict
    elenen: str
    girisim: bool


def _hazirla(query: str, llm_kullan: bool, profil_kaydi) -> Hazirlik:
    """answer() ve answer_akis() için ortak hazırlık: kayıtlar, 9903 ön değerlendirme
    notları, elenen/eski sistem bloğu, girişim modu.

    profil_kaydi yalnızca YEREL eleme için kullanılır (dışarı gönderilmez); dışarı giden
    profil, rızaya bağlı olan `profil` sözlüğüdür."""
    matches = retrieve(query, limit=CEVAP_KAYIT_SAYISI, profil_kaydi=profil_kaydi)
    if not matches:
        return Hazirlik([], {}, "", False)
    notlar = {i: u.metin() for i, u in profil_9903_degerlendirmesi(matches, profil_kaydi).items()}
    elenen = elenen_9903_metni(query, profil_kaydi) if llm_kullan else ""
    eski = eski_sistem_notu(query) if llm_kullan else ""
    if eski and ESKI_SISTEM_NOTU not in elenen:
        elenen = (elenen + "\n" if elenen else "") + eski
    girisim = bool(llm_kullan and girisim_modu_mu(profil_kaydi, query))
    if girisim:
        # HUKS kodda hesaplanır; blok ek bağlam olarak gider, format eki sistem prompt'una eklenir.
        elenen = (elenen + "\n\n" if elenen else "") + girisim_baglam_metni(profil_kaydi)
    return Hazirlik(matches, notlar, elenen, girisim)


def answer(query: str, profil: dict | None = None,
           llm_kullan: bool = True, profil_kaydi=None) -> str:
    """Soruya yanit uretir.

    llm_kullan=False ise HICBIR dis LLM cagrisi yapilmaz ve yalnizca
    veritabanindaki kayitlarin liste formati doner. Bunun sebebi KVKK:
    yapay zeka cagrisi isletme profilini VE sorunun metnini Anthropic'e
    (ABD) gonderiyor; bu yurt disina aktarimdir ve acik riza gerektirir.
    Riza yoksa cagri hic yapilmaz (bkz. app/main.py sor()).
    """
    h = _hazirla(query, llm_kullan, profil_kaydi)
    if not h.matches:
        return BULUNAMADI_METNI

    if llm_kullan:
        if h.girisim:
            claude_cevap = _claude_cevap(query, h.matches, profil, h.notlar, h.elenen,
                                         sistem_eki=GIRISIM_PROMPT_EKI)
        else:
            claude_cevap = (_claude_cevap(query, h.matches, profil, h.notlar, h.elenen)
                            if (h.notlar or h.elenen) else _claude_cevap(query, h.matches, profil))
        if claude_cevap is not None:
            return claude_cevap

    if llm_kullan and OLLAMA_ETKIN:
        llm_cevap = _ollama_cevap(query, h.matches)
        if llm_cevap is not None:
            return llm_cevap

    return _liste_formati(h.matches)


def _claude_akis(query: str, matches: list[Tesvik], profil: dict | None,
                 notlar: dict[int, str] | None = None, elenen: str = "", sistem_eki: str = ""):
    """_claude_cevap'ın akış (streaming) karşılığı: yanıt metnini parça parça üretir.

    Hiç parça üretmeden biterse (anahtar yok, ağ/kota hatası) çağıran taraf liste formatına
    düşer; parça ürettikten SONRA kesilirse kullanıcıya kesildiği açıkça söylenir (sessizce
    yarım yanıt bırakılmaz). Hata sebebi her durumda günlüğe yazılır."""
    if not settings.ANTHROPIC_API_KEY:
        return
    try:
        import anthropic
    except ImportError:
        return

    baglam = _baglam_metni(matches, profil, notlar, elenen)
    uretildi = False
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        with client.messages.stream(
            model=settings.CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=SISTEM_PROMPTU + sistem_eki,
            messages=[{"role": "user", "content": f"BAĞLAM:\n{baglam}\n\nKULLANICI SORUSU: {query}"}],
            output_config={"effort": CLAUDE_EFFORT},
            timeout=CLAUDE_TIMEOUT_SEC,
        ) as akis:
            for parca in akis.text_stream:
                uretildi = True
                yield parca
            son = akis.get_final_message()
        if getattr(son, "stop_reason", None) == "max_tokens":
            logger.warning("Claude akış yanıtı max_tokens sınırında kesildi (%s token)",
                           getattr(getattr(son, "usage", None), "output_tokens", "?"))
            yield KESILDI_NOTU
    except Exception as e:
        logger.warning("Claude akışı başarısız (%s): %s: %s",
                       "parça üretildikten sonra" if uretildi else "başlamadan",
                       type(e).__name__, e)
        if uretildi:
            yield "\n\n*(Yanıt bağlantı hatası nedeniyle kesildi; lütfen tekrar deneyin.)*"


def answer_akis(query: str, profil: dict | None = None,
                llm_kullan: bool = True, profil_kaydi=None):
    """answer()'ın akış sürümü: önce ("kayitlar", [Tesvik]) sonra ("parca", str) olayları.

    Aynı KVKK kuralı: llm_kullan=False ise dış çağrı yapılmaz, liste formatı tek parça
    olarak gelir. Claude hiç parça üretmezse de liste formatına düşülür."""
    h = _hazirla(query, llm_kullan, profil_kaydi)
    yield "kayitlar", h.matches
    if not h.matches:
        yield "parca", BULUNAMADI_METNI
        return
    if llm_kullan:
        uretildi = False
        for parca in _claude_akis(query, h.matches, profil, h.notlar, h.elenen,
                                  sistem_eki=GIRISIM_PROMPT_EKI if h.girisim else ""):
            uretildi = True
            yield "parca", parca
        if uretildi:
            return
    yield "parca", _liste_formati(h.matches)
