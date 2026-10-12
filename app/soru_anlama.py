"""Soru anlama katmanı: maskelenmiş soru metnini Groq'a sınıflandırtır (2026-10-12, Mert onayı: "2. yol").

Danışmanın soru çözümlemesi kelime kalıplarına dayanır (app/yerel_danisman._NIYET, app/ihtiyac.SORU_KALIPLARI);
listede olmayan ifade ("yabancı alıcılara satış", "ekibi büyütmek") tanınmaz. Bu modül soruyu yalnız sabit etiket
listemize eşletir; İHTİYAÇ etiketleri kalıpların bulduklarına EKLENİR (niyet etiketleri ölçülür ama kullanılmaz, bkz.
NIYET_KULLAN). Kayıt arama, karar, hesap ve yanıt
metni yine kural motorunda kalır; Groq'un yanıtı kullanıcıya hiç gösterilmez, yalnız etiket olarak kullanılır.

Veri kuralları (KVKK m.9; Groq'un veri işleme ekinde Türkiye/KVKK standart sözleşmesi yok, 2026-10-12):
  * Groq'a yalnız MASKELENMİŞ soru metni gider (`maskele`): rakamlar, e-posta, telefon, IBAN, web adresi, kullanıcı ve
    kuruluş adı, cümle içinde büyük harfle başlayan özel adlar çıkarılır. Kurum, ülke, il ve platform adları kalır.
    Profil, ciro, İKAS verisi ve kullanıcı kimliği hiçbir durumda gönderilmez.
  * Varsayılan KAPALI. Sunucuda SORU_ANLAMA=groq ve GROQ_API_KEY tanımlı olmalı; kuruluş Ayarlar'dan açıkça açmalı
    (organizations.ai_yurtdisi_riza + ai_riza_tarihi >= RIZA_BASLANGICI; daha eski kayıtlar Gemini dönemindendir ve
    geçersizdir).
  * Yalnız https://api.groq.com adresine bağlanır (adres sabit, ortamdan değiştirilemez); vekil ortam değişkenleri
    yok sayılır, yönlendirme izlenmez. Günlüğe soru metni yazılmaz.
  * Groq hata verirse, ZAMAN_ASIMI_SN içinde dönmezse ya da listede olmayan etiket dönerse etiket eklenmez; yanıt
    bugünkü kelime kalıplarıyla üretilir. Art arda hata olursa bir süre hiç denenmez (yanıt gecikmesin).

    python -m app.soru_anlama --self-test
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Iterator
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

URL = "https://api.groq.com/openai/v1/chat/completions"
IZINLI_HOST = "api.groq.com"
KURUM, ULKE = "Groq, Inc.", "ABD"
VARSAYILAN_MODEL = "openai/gpt-oss-120b"
FIYAT_USD_1M = {"openai/gpt-oss-120b": (0.15, 0.60), "openai/gpt-oss-20b": (0.075, 0.30)}   # GroqCloud, 2026-10-12
ZAMAN_ASIMI_SN = 2.5
BAGLANTI_ZAMAN_ASIMI_SN = 1.5
CIKTI_SINIR = 400          # gpt-oss akıl yürütme token'ları da bu sınıra dahil
AZAMI_UZUNLUK = 600        # karakter; daha uzun soru kesilerek gönderilir
ONBELLEK_BOYUTU = 1000
DEVRE_HATA_ESIGI = 3       # art arda bu kadar hatada …
DEVRE_BEKLEME_SN = 60.0    # … bu süre Groq denenmez
# Bu tarihten önce yazılmış yurt dışı rıza kayıtları eski sürümden (Gemini, 2026-10-11'de kaldırıldı); geçersiz.
RIZA_BASLANGICI = datetime(2026, 10, 12)

# Etiket tanımları. Anahtarlar app/yerel_danisman._NIYET ve app/ihtiyac.SORU_KALIPLARI ile aynı olmalı (self-test).
NIYETLER: dict[str, str] = {
    "tarih": "başvuru tarihi, son gün, çağrının ne zaman açılacağı ya da kapanacağı, dönem",
    "tutar": "destek tutarı, oranı, üst limiti, dekar başı miktar, faiz, vade, ödemesiz dönem, bütçe",
    "uygunluk": "ADI VERİLEN belirli bir desteğe başvurup başvuramayacağı ('X'e başvurabilir miyim', 'X'ten "
                "yararlanabilir miyiz')",
    "tanim": "ADI VERİLEN bir programın ne olduğu, şartları, kimlerin başvurabileceği, nasıl başvurulacağı, hangi "
             "belgeler gerektiği",
    "birlikte": "iki desteğin birlikte ya da aynı anda kullanılıp kullanılamayacağı",
    "sure": "desteğin ya da projenin süresi (kaç ay, kaç yıl sürdüğü)",
}
IHTIYACLAR: dict[str, str] = {
    "yatirim": "makine, ekipman, tesis, fabrika, üretim hattı, bina, kapasite artırımı, işyeri yenileme/tadilat, GES "
               "(TARIMDA traktör, mibzer, sera, tünel, sulama, bahçe/tarla yenileme, fidan bu etikete GİRMEZ; "
               "girişimin 'yatırım alması' da GİRMEZ)",
    "arge": "Ar-Ge, ürün geliştirme, prototip, inovasyon, tasarım, patent geliştirme",
    "ihracat": "ihracat, yurt dışına satış, fuar, dış pazar, e-ihracat, yabancı pazaryerleri, belirli bir ülkeye satış",
    "istihdam": "personel/işçi alımı, çalışan sayısını artırma, SGK prim teşviki, İŞKUR, işveren primi",
    "dijital": "dijital dönüşüm, yazılım, ERP, otomasyon, yapay zekâ, e-ticaret altyapısı/sitesi kurma "
               "(dijital pazarlama/reklam bu etikete GİRMEZ, tanitim'dır)",
    "finansman": "kredi, kefalet, finansman, faiz desteği, işletme sermayesi, nakit ihtiyacı",
    "girisim": "girişim, startup, şirket kurma, şirketleşme öncesi, BİGG, kuluçka, tohum aşaması",
    "sigorta": "ürün, hasat, alacak ya da afet sigortası, TARSİM, dolu/don riski (SGK sigorta primi bu etikete "
               "GİRMEZ, istihdam'dır)",
    "tanitim": "reklam, tanıtım, pazarlama, sosyal medya, Google/Instagram reklamı, marka bilinirliği",
    "tescil": "marka, patent ya da faydalı model tescili",
    "lojistik": "kargo, depo/depolama, fulfillment, sipariş karşılama, nakliye, navlun",
    "tarim_odeme": "çiftçiye dekar/dönüm başı doğrudan ödeme, alan bazlı gelir desteği, temel destek, mazot, gübre "
                   "(yalnız bahçe/tarla sahibi olmak yetmez; ödeme sorulmalı)",
}

SISTEM = (
    "Türkiye'deki devlet destekleri ve teşvikleri hakkında sorulan soruyu sınıflandırıyorsun. Soruyu yanıtlama. "
    "Yalnız aşağıdaki etiketlerden, soruda gerçekten sorulan ya da açıkça ihtiyaç duyulanları seç; emin değilsen "
    "seçme. Soruda [AD], [E-POSTA], [ADRES], [IBAN] ve N yer tutucuları maskelenmiş ad ve sayılardır.\n"
    "NIYET (sorunun türü). 'Hangi destekler var', 'ne alabilirim', 'destek var mı', 'hangi desteklerden "
    "yararlanabilirim' gibi genel liste sorularında niyet BOŞ liste olur:\n"
    + "\n".join(f"- {k}: {v}" for k, v in NIYETLER.items())
    + "\nIHTIYAC (işletmenin parasını harcayacağı ya da desteklenmesini istediği konu):\n"
    + "\n".join(f"- {k}: {v}" for k, v in IHTIYACLAR.items())
    + '\nYalnız şu JSON nesnesini döndür: {"niyet": [...], "ihtiyac": [...]}'
)


def _ortam(ad: str, varsayilan: str = "") -> str:
    return (os.getenv(ad) or varsayilan).strip()


def model_adi(ortam: Callable[[str, str], str] = _ortam) -> str:
    return ortam("SORU_ANLAMA_MODEL", VARSAYILAN_MODEL)


def etkin_mi(ortam: Callable[[str, str], str] = _ortam) -> bool:
    """Sunucuda açık mı: SORU_ANLAMA=groq ve GROQ_API_KEY tanımlı."""
    return ortam("SORU_ANLAMA", "").lower() == "groq" and bool(ortam("GROQ_API_KEY", ""))


def riza_gecerli_mi(org) -> bool:
    """Kuruluş soru anlamayı (yurt dışına maskelenmiş soru aktarımı) açıkça açtı mı."""
    tarih = getattr(org, "ai_riza_tarihi", None)
    return bool(getattr(org, "ai_yurtdisi_riza", False)) and tarih is not None and tarih >= RIZA_BASLANGICI


def kullanilir(org, ortam: Callable[[str, str], str] = _ortam) -> bool:
    return etkin_mi(ortam) and riza_gecerli_mi(org)


def durum(org, ortam: Callable[[str, str], str] = _ortam) -> dict:
    """Panel ve İKAS uygulaması için açıklama (GET /api/yapay-zeka)."""
    return {"etkin": etkin_mi(ortam), "riza": riza_gecerli_mi(org), "kurum": KURUM, "ulke": ULKE,
            "model": model_adi(ortam), "giden_veri": "maskelenmiş soru metni (ad, rakam, e-posta, adres çıkarılır)",
            "gitmeyen_veri": "profil, ciro, İKAS verisi, kullanıcı kimliği", "varsayilan_kapali": True}


# ------------------------------------------------------------------ maskeleme
_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def _katla(metin: str) -> str:
    from app.urun_sektor_anahtarlari import kucult
    return kucult(metin or "").translate(_ASCII)


_HARF = "A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû"
_BUYUK = "A-ZÇĞİÖŞÜÂÎÛ"
_KELIME = re.compile(rf"[{_HARF}][{_HARF}0-9]*(?:-[{_HARF}0-9]+)*(?:['’][{_HARF}]+)?")
_EPOSTA = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|net|org|gov|edu|io|co|tr|de|uk|app|shop|store)"
                  r"(?:\.tr)?(?:/\S*)?", re.I)
_IBAN = re.compile(r"\bTR\s?\d{2}(?:\s?[\dA-Z]{4}){5}\s?[\dA-Z]{2}\b", re.I)
_RAKAM = re.compile(r"\d+(?:[.,:/-]\d+)*")
# Özel ad sayılmayan büyük harfli kelimeler (katlanmış): kurumlar, platformlar, ülkeler, bölgeler, kısaltmalar,
# cümle başında sık geçen sözcükler. İl adları app/bolgesel_tarim.IL_BOLGE_ESLEME'den eklenir.
_ADLAR_DISI = frozenset("""
kosgeb tubitak kgf iskur sgk eximbank turk ziraat halkbank vakifbank vakif tkdk tmo tarsim bigg teknopark tgb
ticaret bakanlik bakanligi sanayi teknoloji tarim orman hazine maliye kalkinma ajans ajansi kredi garanti fonu fon
ihracatcilar birligi birlik tim tobb oda odasi borsa ab avrupa horizon eureka eurostars ipard undp dunya bankasi
turquality yonde kobi kdv otv gib resmi gazete cumhurbaskanligi karar kanun teblig yonetmelik
hepsiburada trendyol n11 amazon etsy ebay walmart shopify ikas instagram google facebook meta tiktok youtube
linkedin alibaba aliexpress zalando wayfair noon ozon cimri ciceksepeti pazarama paypal stripe
turkiye almanya fransa ingiltere abd amerika hollanda belcika italya ispanya portekiz rusya cin japonya kore irak
iran suriye azerbaycan gurcistan kazakistan ozbekistan turkmenistan kirgizistan bulgaristan yunanistan romanya
polonya avusturya isvicre isvec norvec danimarka finlandiya irlanda kanada meksika brezilya arjantin misir fas
tunus cezayir libya suudi arabistan katar kuveyt bae dubai emirlikleri birlesik israil hindistan pakistan
endonezya malezya avustralya afrika ortadogu korfez balkanlar balkan asya kktc kibris ukrayna
marmara ege akdeniz karadeniz anadolu ic dogu guneydogu bati kuzey guney bolge bolgesi
ar-ge cnc erp crm ges ai ui ux b2b b2c saas api iso ce tse haccp tl usd eur euro dolar avro
merhaba selam selamlar iyi gunler tesekkurler tesekkur ederim ben biz bizim benim sirketimiz firmamiz
isletmemiz hangi hangisi nasil ne neler nedir kac bu su o bir var yok mi mu acaba lutfen sayin hocam evet hayir
ayrica peki eger simdi yeni hibe destek destegi destekleri tesvik tesvigi program programi proje projesi
basvuru basvurmak sahis limited anonim kooperatif ltd sti as e-ihracat e-ticaret
""".split())
_UNVAN = re.compile(r"^(?:ltd|sti|as|a\.s|san|tic|ve|ile|sirketi|sirket|limited|anonim|holding|grup|group|"
                    r"gida|tarim|tekstil|insaat|yazilim|teknoloji|bilisim|ticaret|sanayi|turizm|lojistik)$")


def _il_adlari() -> frozenset[str]:
    from app.bolgesel_tarim import IL_BOLGE_ESLEME
    return frozenset(IL_BOLGE_ESLEME)


def _alan_kelimesi(katli: str) -> bool:
    """Danışmanın kalıp listelerinde geçen kelime ("Makine", "İhracat"): özel ad değildir."""
    from app.ihtiyac import SORU_KALIPLARI
    from app.yerel_danisman import _NIYET
    return any(k.search(katli) for k in (*SORU_KALIPLARI.values(), *_NIYET.values()))


def _ad_degil(kelime: str) -> bool:
    katli = _katla(re.split(r"['’]", kelime)[0])
    return (katli in _ADLAR_DISI or katli in _il_adlari() or _alan_kelimesi(katli)
            or all(p in _ADLAR_DISI for p in katli.split("-")))


def _bilinen_ad_kalibi(adlar: Iterable[str]) -> re.Pattern | None:
    parcalar: set[str] = set()
    for ad in adlar:
        for k in re.findall(rf"[{_HARF}0-9]+", ad or ""):
            katli = _katla(k)
            if len(katli) >= 3 and not _UNVAN.match(katli) and katli not in _ADLAR_DISI:
                parcalar.add(re.escape(katli))
    if not parcalar:
        return None
    # Ek alabilir ("Rekortiv'in", "Yılmazlar"); kısa adlarda yalnız kesme işaretli ek (ali → "alım" maskelenmesin).
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(sorted(parcalar, key=len, reverse=True)) +
                      r")(?:['’][a-z]+|(?<=[a-z]{5})[a-z]{0,4})?(?![a-z0-9])")


def maskele(soru: str, adlar: Iterable[str] = ()) -> str:
    """Groq'a gidecek metin. Rakamlar N, adlar [AD]; e-posta, web adresi ve IBAN yer tutucuyla değiştirilir.

    Büyük harfle başlayan kelime cümle başında değilse ve kurum/ülke/il/platform/alan kelimesi değilse özel ad
    sayılır; cümle başındaki büyük harfli kelime ancak hemen ardından maskelenen bir ad geliyorsa ("Ahmet Yılmaz")
    maskelenir. Metnin çoğu büyük harfle yazılmışsa ("ÇİLEK SERASI İÇİN HİBE") büyük harf kuralı uygulanmaz;
    yalnız bilinen adlar (kullanıcı, kuruluş) ve kalıp kuralları uygulanır."""
    metin = (soru or "")[:AZAMI_UZUNLUK]
    metin = _EPOSTA.sub(" [E-POSTA] ", metin)
    metin = _URL.sub(" [ADRES] ", metin)
    metin = _IBAN.sub(" [IBAN] ", metin)
    metin = _RAKAM.sub("N", metin)
    kalip = _bilinen_ad_kalibi(adlar)
    kelimeler = [m for m in _KELIME.finditer(metin) if not re.fullmatch(r"N|AD|ADRES|IBAN|E-POSTA", m.group())]
    buyuk_harfli = [m for m in kelimeler if len(m.group()) > 1 and m.group().upper() == m.group()]
    buyuk_metin = len(kelimeler) >= 3 and len(buyuk_harfli) / len(kelimeler) > 0.5
    maske: list[bool] = []
    for i, m in enumerate(kelimeler):
        k = m.group()
        katli = _katla(k)
        if kalip and kalip.fullmatch(katli):
            maske.append(True)
            continue
        if buyuk_metin or not re.match(rf"[{_BUYUK}]", k) or _ad_degil(k):
            maske.append(False)
            continue
        onceki = metin[:m.start()].rstrip()
        cumle_basi = not onceki or onceki[-1] in ".!?\n:;\"("
        maske.append(not cumle_basi)
    for i in range(len(kelimeler) - 2, -1, -1):
        # "Ahmet Yılmaz", "Ayşe Kaya Gıda": cümle başındaki büyük harfli kelime, ardındaki maskeli adla birlikte gider.
        sonraki = kelimeler[i + 1]
        if (maske[i + 1] and not maske[i] and re.match(rf"[{_BUYUK}]", kelimeler[i].group()) and not buyuk_metin
                and not _ad_degil(kelimeler[i].group())
                and metin[kelimeler[i].end():sonraki.start()].strip() == ""):
            maske[i] = True
    parcalar, son = [], 0
    for m, gizle in zip(kelimeler, maske):
        if gizle:
            parcalar += [metin[son:m.start()], "[AD]"]
            son = m.end()
    parcalar.append(metin[son:])
    metin = "".join(parcalar)
    metin = re.sub(r"\[AD\](?:\s*\[AD\])+", "[AD]", metin)
    return re.sub(r"\s+", " ", metin).strip()


# ------------------------------------------------------------------ sınıflandırma
@dataclass(frozen=True)
class Etiketler:
    soru_anahtari: str          # etiketlerin ait olduğu soru (boşluk sadeleştirilmiş); başka metne uygulanmaz
    niyetler: frozenset[str]
    ihtiyaclar: tuple[str, ...]
    model: str
    gonderildi: bool            # bu istekte maskeli metin Groq'a gitti mi (önbellekten geldiyse False); yöntem notu


_ONBELLEK: OrderedDict[tuple[str, str], tuple[frozenset[str], tuple[str, ...]]] = OrderedDict()
_KILIT = threading.Lock()
_DEVRE = {"hata": 0, "acilis": 0.0}
SAYAC = {"cagri": 0, "hata": 0, "onbellek": 0, "giris_token": 0, "cikis_token": 0}


def _anahtar(soru: str) -> str:
    return " ".join((soru or "").split())


def istem(maskeli: str) -> list[dict]:
    return [{"role": "system", "content": SISTEM}, {"role": "user", "content": f"SORU: {maskeli}"}]


def ayristir(icerik: str) -> tuple[frozenset[str], tuple[str, ...]]:
    """Model yanıtından yalnız listemizdeki etiketler; biçim bozuksa ValueError."""
    veri = json.loads(icerik)
    if not isinstance(veri, dict):
        raise ValueError("JSON nesnesi değil")
    niyet = veri.get("niyet") or []
    ihtiyac = veri.get("ihtiyac") or []
    if not isinstance(niyet, list) or not isinstance(ihtiyac, list):
        raise ValueError("liste değil")
    n = frozenset(x for x in niyet if isinstance(x, str) and x in NIYETLER)
    i = tuple(dict.fromkeys(x for x in ihtiyac if isinstance(x, str) and x in IHTIYACLAR))
    return n, i


def groq_cagir(mesajlar: list[dict], api_key: str, model: str, *, tasima=None,
               zaman_asimi: float = ZAMAN_ASIMI_SN) -> tuple[str, int, int]:
    """Chat Completions çağrısı; (içerik, giriş token, çıkış token). Adres sabittir ve doğrulanır."""
    import httpx
    if urlparse(URL).hostname != IZINLI_HOST or not URL.startswith("https://"):
        raise RuntimeError("izin verilmeyen adres")
    govde = {"model": model, "messages": mesajlar, "temperature": 0, "max_completion_tokens": CIKTI_SINIR,
             "response_format": {"type": "json_object"}}
    if model.startswith("openai/gpt-oss"):
        govde |= {"reasoning_effort": "low", "include_reasoning": False}
    ek = {"transport": tasima} if tasima is not None else {}
    zaman = httpx.Timeout(zaman_asimi, connect=min(BAGLANTI_ZAMAN_ASIMI_SN, zaman_asimi))
    with httpx.Client(timeout=zaman, trust_env=False, follow_redirects=False, **ek) as c:
        r = c.post(URL, headers={"Authorization": f"Bearer {api_key}"}, json=govde)
    if r.status_code >= 400:
        # Gövde günlüğe yazılmaz (istemi yansıtabilir); yalnız durum kodu.
        raise RuntimeError(f"Groq HTTP {r.status_code}")
    veri = r.json()
    kul = veri.get("usage") or {}
    return (veri["choices"][0]["message"]["content"] or "", int(kul.get("prompt_tokens", 0)),
            int(kul.get("completion_tokens", 0)))


def siniflandir(soru: str, adlar: Iterable[str] = (), *, ortam: Callable[[str, str], str] = _ortam,
                tasima=None, saat: Callable[[], float] = time.monotonic) -> Etiketler | None:
    """Sorunun Groq etiketleri. Kapalıysa, devre açıksa ya da bağlantı kurulamadıysa None (hiçbir şey gönderilmedi).
    Gönderimden sonra hata, zaman aşımı ya da bozuk yanıt olursa etiketsiz ama `gonderildi=True` döner: yanıt kelime
    kalıplarıyla üretilir, yöntem notu yine de gönderimi söyler. Çağıran kuruluş rızasını `kullanilir` ile
    denetlemiş olmalıdır."""
    import httpx
    if not etkin_mi(ortam) or not (soru or "").strip():
        return None
    model = model_adi(ortam)
    maskeli = maskele(soru, adlar)
    with _KILIT:
        bulunan = _ONBELLEK.get((model, maskeli))
        if bulunan is not None:
            _ONBELLEK.move_to_end((model, maskeli))
            SAYAC["onbellek"] += 1
            return Etiketler(_anahtar(soru), bulunan[0], bulunan[1], model, False)
        if _DEVRE["hata"] >= DEVRE_HATA_ESIGI and saat() - _DEVRE["acilis"] < DEVRE_BEKLEME_SN:
            return None
    try:
        icerik, giris, cikis = groq_cagir(istem(maskeli), ortam("GROQ_API_KEY", ""), model, tasima=tasima,
                                          zaman_asimi=float(ortam("SORU_ANLAMA_ZAMAN_ASIMI_SN", str(ZAMAN_ASIMI_SN))))
        niyet, ihtiyac = ayristir(icerik)
    except Exception as e:   # ağ, zaman aşımı, HTTP, biçim: hepsinde kalıplarla devam
        with _KILIT:
            SAYAC["hata"] += 1
            _DEVRE["hata"] += 1
            if _DEVRE["hata"] >= DEVRE_HATA_ESIGI:
                _DEVRE["acilis"] = saat()
        logger.warning("Soru anlama (Groq) kullanılamadı: %s", type(e).__name__)
        if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
            return None
        return Etiketler(_anahtar(soru), frozenset(), (), model, True)
    with _KILIT:
        _DEVRE["hata"] = 0
        SAYAC["cagri"] += 1
        SAYAC["giris_token"] += giris
        SAYAC["cikis_token"] += cikis
        _ONBELLEK[(model, maskeli)] = (niyet, ihtiyac)
        while len(_ONBELLEK) > ONBELLEK_BOYUTU:
            _ONBELLEK.popitem(last=False)
    logger.info("Soru anlama (Groq): %d+%d token, %d niyet, %d ihtiyaç", giris, cikis, len(niyet), len(ihtiyac))
    return Etiketler(_anahtar(soru), niyet, ihtiyac, model, True)


def maliyet_usd(model: str, giris: int, cikis: int) -> float:
    fg, fc = FIYAT_USD_1M.get(model, FIYAT_USD_1M[VARSAYILAN_MODEL])
    return round(giris / 1e6 * fg + cikis / 1e6 * fc, 6)


# ------------------------------------------------------------------ istek bağlamı
_ETIKET: ContextVar[Etiketler | None] = ContextVar("soru_anlama_etiket", default=None)


@contextmanager
def baglam(etiket: Etiketler | None) -> Iterator[None]:
    """Bu blokta çalışan niyet/ihtiyaç çözümlemesi, `etiket`in sorusu için Groq etiketlerini ekler. Blok bir
    üreteçte `yield` içermemelidir (akışta her adım ayrı bağlamda çalışabilir)."""
    belirtec = _ETIKET.set(etiket)
    try:
        yield
    finally:
        _ETIKET.reset(belirtec)


def etkin_etiket() -> Etiketler | None:
    return _ETIKET.get()


# Groq'un niyet etiketleri KULLANILMAZ (ölçüm 2026-10-12, docs/olcum/2026-10-12-soru-anlama): istem "genel liste
# sorusunda niyet boş" dese de "destek var mı / neler" sorularına "tanim"/"uygunluk" ekliyor; niyet yanıtın yapısını
# değiştirdiği için bu fazlalar zararlı, kalıplar niyette yeterli. Etiket yine istenir ve ölçülür.
NIYET_KULLAN = False


def ek_niyetler(soru: str) -> frozenset[str]:
    e = _ETIKET.get()
    if not NIYET_KULLAN or e is None or _anahtar(soru) != e.soru_anahtari:
        return frozenset()
    return e.niyetler


def ek_ihtiyaclar(soru: str) -> tuple[str, ...]:
    """Groq'un bu soru için bulduğu ihtiyaçlar. Adıyla anılan program kelimeleri çıkarılmış türev metne
    (yerel_danisman._adlari_cikar) uygulanmaz: o çıkarım program adındaki "ihracat" gibi kelimeyi bilerek siler."""
    e = _ETIKET.get()
    return e.ihtiyaclar if e is not None and _anahtar(soru) == e.soru_anahtari else ()


YONTEM_NOTU = ("*Bu yanıt Teşvik Asistanı'nın yerel danışmanı tarafından, yalnız veritabanındaki doğrulanmış kayıtlardan "
               "kuralla üretildi. Sorunuzun konusunu belirlemek için soru metni, adlar ve rakamlar çıkarılarak Groq'a "
               "(ABD) gönderildi; profiliniz ve işletme verileriniz gönderilmedi. Ayarlar'dan kapatabilirsiniz.*")


# ------------------------------------------------------------------ self-test
def _self_test() -> int:
    import httpx
    from types import SimpleNamespace

    from app.ihtiyac import SORU_KALIPLARI, soru_ihtiyaclari
    from app.yerel_danisman import _NIYET, niyetler

    acik = {"SORU_ANLAMA": "groq", "GROQ_API_KEY": "test-anahtar"}

    def ortam(ad, v=""):
        return acik.get(ad, v)

    giden: list[httpx.Request] = []

    def sunucu(yanit: str, durum: int = 200):
        def _f(r: httpx.Request):
            giden.append(r)
            return httpx.Response(durum, json={"choices": [{"message": {"content": yanit}}],
                                               "usage": {"prompt_tokens": 500, "completion_tokens": 40}})
        return httpx.MockTransport(_f)

    m1 = maskele("Merhaba, ben Ahmet Yılmaz. Rekortiv Ltd. için 1.250.000 TL kredi; ahmet@rekortiv.com, "
                 "0532 111 22 33, www.rekortiv.com. KOSGEB ve Almanya'ya ihracat, Konya'da makine.",
                 adlar=["Ahmet Yılmaz", "Rekortiv Yazılım Ltd. Şti."])
    m2 = maskele("Mehmet Bey olarak Ünye'deki fındık bahçem için dekar başı ne alırım?")
    m3 = maskele("ÇİLEK SERASI İÇİN HİBE VAR MI")
    m4 = maskele("Ayşe Demir Tekstil olarak TÜBİTAK 1501 ve Ar-Ge desteği istiyoruz", adlar=["Ayşe Demir"])
    m5 = maskele("IBAN TR33 0006 1005 1978 6457 8413 26 hesabıma ödeme ne zaman yatar")

    e = siniflandir("Yabancı alıcılara satış yapmak istiyoruz, ne kadar destek var?", ortam=ortam,
                    tasima=sunucu('{"niyet": ["tutar", "uydurma"], "ihtiyac": ["ihracat", "x", "ihracat"]}'))
    istek = json.loads(giden[-1].content)
    with baglam(e):
        ih_baglamda = soru_ihtiyaclari("Yabancı alıcılara satış yapmak istiyoruz, ne kadar destek var?")
        ih_baska = soru_ihtiyaclari("başka bir soru")
        ni_baglamda = niyetler("Yabancı alıcılara satış yapmak istiyoruz, ne kadar destek var?")
    ih_disari = soru_ihtiyaclari("Yabancı alıcılara satış yapmak istiyoruz, ne kadar destek var?")

    def _baglamda(soru, niyet=(), ihtiyac=()):
        with baglam(Etiketler(_anahtar(soru), frozenset(niyet), tuple(ihtiyac), "t", True)):
            return niyetler(soru), soru_ihtiyaclari(soru)
    liste_niyet = _baglamda("Hangi destekler var?", niyet=["tanim"])[0]
    sera = _baglamda("Çilek tarlamı alçak tünel ya da sera yapmak istiyorum", ihtiyac=["yatirim"])[1]
    seramik = _baglamda("Seramik fırını almak istiyorum", ihtiyac=["yatirim"])[1]

    # Önbellek: aynı maskeli metin ikinci kez gönderilmez.
    n_once = len(giden)
    siniflandir("Yabancı alıcılara satış yapmak istiyoruz, ne kadar destek var?", ortam=ortam,
                tasima=sunucu("{}"))
    onbellek = len(giden) == n_once

    # Gönderim sonrası hata / bozuk yanıt → etiketsiz (gönderildi); anahtar yok → None; devre kesici.
    hata = siniflandir("soru a", ortam=ortam, tasima=sunucu("{}", 500))
    bozuk = siniflandir("soru b", ortam=ortam, tasima=sunucu("bu json değil"))
    kapali = siniflandir("soru c", ortam=lambda a, v="": {"SORU_ANLAMA": "groq"}.get(a, v), tasima=sunucu("{}"))

    def etiketsiz(x):
        return x is not None and x.gonderildi and not x.niyetler and not x.ihtiyaclar

    def baglanamadi(_r):
        raise httpx.ConnectError("yok")
    _DEVRE["hata"] = 0
    baglanti = siniflandir("soru h", ortam=ortam, tasima=httpx.MockTransport(baglanamadi))
    _DEVRE["hata"] = 0
    with baglam(siniflandir("Yabancı alıcılara satış yapmak istiyoruz, ne kadar destek var?", ortam=ortam,
                            tasima=sunucu("{}"))):
        onbellek_gonderilmedi = not etkin_etiket().gonderildi
    zaman = [1000.0]
    for s in ("soru d1", "soru d2", "soru d3"):
        siniflandir(s, ortam=ortam, tasima=sunucu("{}", 503), saat=lambda: zaman[0])
    n_devre = len(giden)
    devre_acik = siniflandir("soru e", ortam=ortam, tasima=sunucu('{"niyet": []}'), saat=lambda: zaman[0])
    devre_cagri_yok = len(giden) == n_devre
    zaman[0] += DEVRE_BEKLEME_SN + 1
    devre_kapandi = siniflandir("soru f", ortam=ortam, tasima=sunucu('{"niyet": ["tarih"]}'),
                                saat=lambda: zaman[0]) is not None

    def zaman_asimi(_r):
        raise httpx.ReadTimeout("yavaş")
    gec = siniflandir("soru g", ortam=ortam, tasima=httpx.MockTransport(zaman_asimi))

    eski = SimpleNamespace(ai_yurtdisi_riza=True, ai_riza_tarihi=datetime(2026, 10, 1))
    yeni = SimpleNamespace(ai_yurtdisi_riza=True, ai_riza_tarihi=datetime(2026, 10, 12, 9))

    sonuc = [
        ("etiket anahtarları kalıplarla aynı", set(NIYETLER) == set(_NIYET) and set(IHTIYACLAR) == set(SORU_KALIPLARI)),
        ("rakam, e-posta, telefon, adres maskeli", not re.search(r"\d|@|rekortiv\.com|www", m1)),
        ("kullanıcı ve kuruluş adı maskeli", not re.search(r"(?i)ahmet|yılmaz|rekortiv", m1)),
        ("kurum, ülke, il, alan kelimesi korunur", all(k in m1 for k in ("KOSGEB", "Almanya'ya", "Konya'da", "makine"))),
        ("büyük harfli ad + unvan maskeli", "Mehmet" not in m2 and "Bey" not in m2 and "fındık" in m2),
        ("ilçe adı maskeli, soru kalır", "Ünye" not in m2 and "dekar başı ne alırım" in m2),
        ("büyük harfli metin korunur", m3 == "ÇİLEK SERASI İÇİN HİBE VAR MI"),
        ("bilinen ad + alan kelimesi", "Ayşe" not in m4 and "Demir" not in m4 and "TÜBİTAK N" in m4 and "Ar-Ge" in m4),
        ("IBAN maskeli", "[IBAN]" in m5 and not re.search(r"\d", m5)),
        ("yalnız api.groq.com, maskeli metin", giden[0].url.host == IZINLI_HOST and giden[0].url.scheme == "https"),
        ("istekte profil yok, yalnız soru", [x["role"] for x in istek["messages"]] == ["system", "user"]
         and istek["messages"][1]["content"].startswith("SORU: ") and istek["temperature"] == 0),
        ("listede olmayan etiket atılır", e is not None and e.niyetler == {"tutar"} and e.ihtiyaclar == ("ihracat",)),
        ("bağlamda ihtiyaç eklenir", "ihracat" in ih_baglamda and "tutar" in ni_baglamda),
        ("Groq niyeti kullanılmaz", liste_niyet == {"liste"}),
        ("tarımda Groq 'yatirim' atılır, seramikte kalır", "yatirim" not in sera and "yatirim" in seramik),
        ("başka soruya ve bağlam dışına eklenmez", "ihracat" not in ih_baska and "ihracat" not in ih_disari),
        ("önbellek: ikinci çağrı yok", onbellek),
        ("HTTP hata / bozuk yanıt → etiketsiz, gönderildi", etiketsiz(hata) and etiketsiz(bozuk)),
        ("anahtar yok / bağlantı yok → None", kapali is None and baglanti is None),
        ("önbellekten gelen: bu istekte gönderilmedi", onbellek_gonderilmedi),
        ("zaman aşımı → etiketsiz", etiketsiz(gec)),
        ("devre kesici: art arda hatada çağrı yok", devre_acik is None and devre_cagri_yok and devre_kapandi),
        ("rıza: eski tarihli kayıt geçersiz", not riza_gecerli_mi(eski) and riza_gecerli_mi(yeni)
         and not riza_gecerli_mi(SimpleNamespace(ai_yurtdisi_riza=False, ai_riza_tarihi=datetime(2026, 10, 13)))),
        ("varsayılan kapalı", not etkin_mi(lambda a, v="": v) and not kullanilir(yeni, lambda a, v="": v)),
    ]
    gecen = sum(1 for _, ok in sonuc if ok)
    for ad, ok in sonuc:
        print(f"  [{'OK' if ok else 'HATA'}] {ad}")
    print(f"soru_anlama self-test: {gecen}/{len(sonuc)}")
    if gecen != len(sonuc):
        print("maskeler:", m1, "|", m2, "|", m3, "|", m4, "|", m5, sep="\n")
    return 0 if gecen == len(sonuc) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        # `python -m` modülü __main__ olarak yükler; app.ihtiyac ise app.soru_anlama'yı ayrıca içe aktarır. Bağlam
        # değişkeni tek olsun diye test paket modülünden çalışır.
        from app.soru_anlama import _self_test as _paket_testi
        sys.exit(_paket_testi())
    print(__doc__)
