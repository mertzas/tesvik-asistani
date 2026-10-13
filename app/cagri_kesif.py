"""Yeni çağrı keşif hattı (2026-10-13).

Program ve çağrı kayıtları elle, resmî metinde birebir doğrulanarak eklenir (scripts/fix_veri_*). Bu modül o işin girdisini
üretir: resmî duyuru/çağrı sayfalarını (app/data/cagri_kaynaklari.json) ve Resmî Gazete'nin günlük fihristini tarar,
önceki taramada görülmemiş ilanları bulur, veritabanıyla karşılaştırır ve bir KUYRUĞA yazar. Veritabanına hiçbir şey
yazmaz; kuyruktaki aday, doğrulama hattından (alıntı resmî metinde birebir) geçmeden kayda girmez.

Sınıflar:
  bilinen          ilanın adresi zaten bir kaydın ya da çağrının kaynağı
  cagri_adayi      mevcut bir programa ait görünüyor (program kodu ya da aynı kurumda başlık örtüşmesi): yeni dönem/çağrı
  yeni_program     veritabanında karşılığı yok
Yeni ilanın sayfası okunur (en çok AYRINTI_SINIRI); "son başvuru / başvuru tarihi / kapanış / ön kayıt" yakınındaki
tarihler alıntı adayıyla birlikte kuyruğa eklenir.

İlk tarama bir kaynağın TABANINI kurar: o anda listelenen ilanlar "görüldü" sayılır ve yalnız bu yıl ya da gelecek yıl
anılan, veritabanında karşılığı olmayanlar rapora girer (eski arşiv taşmasın). Sonraki taramalar yalnız yeni ilanı
raporlar. Durum: data/cagri_kesif/durum.json, kuyruk: kuyruk.json, okunur rapor: rapor_YYYY-AA-GG.md (git dışı).

    python -m app.cagri_kesif --self-test
    python -m app.cagri_kesif --calistir [--kaynak AD]      (ağ; veritabanını yalnız okur)
    python -m app.cagri_kesif --kuyruk                       (bekleyen adaylar)
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse, urlunparse

logger = logging.getLogger(__name__)

KOK = Path(__file__).resolve().parent.parent
KAYNAK_DOSYASI = Path(__file__).resolve().parent / "data" / "cagri_kaynaklari.json"
DIZIN = KOK / "data" / "cagri_kesif"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0 Safari/537.36 TesvikAsistani-CagriKesif"}
ZAMAN_ASIMI_SN = 30
BEKLEME_SN = 1.0               # aynı sunucuya ardışık istek arası
AYRINTI_SINIRI = 30            # bir taramada okunacak en çok ilan sayfası
RESMI_GAZETE_GUN = 7           # geriye dönük taranan gün
AYLAR = ["ocak", "subat", "mart", "nisan", "mayis", "haziran", "temmuz", "agustos", "eylul", "ekim", "kasim", "aralik"]

# İlan sayılan bağlantı metni (katlanmış). Menü ve kurumsal sayfalar dışarıda kalır.
ILAN = re.compile(r"cagri|duyuru|destek(?:leme)? program|mali destek|basvuru|hibe|kredi|tesvik|ilan|acil(?:di|mistir)|"
                  r"son gun|teblig|karar|fon|yatirim|program(?:i|inin)?\b|uzatil|sonuc")
MENU = re.compile(r"^(?:ana ?sayfa|iletisim|hakkimizda|kurumsal|haberler|duyurular|tum duyurular|devamini oku|daha fazla|"
                  r"detay|tikla|english|en|tr|sss|site haritasi|kvkk|gizlilik|cerez|arsiv|tumu|geri|ileri|\d+|»|«|>|<)$")
# İlan sayılmayanlar (ilk taramanın gürültüsü, 2026-10-13): sonuç ve değerlendirme duyuruları, sınav/personel/ihale/satın
# alma, fuar-sergi-etkinlik, başvuru rehberi belgesi, yıl arşivi bağlantısı ve işletmeye değil bireye/akademisyene yönelik
# burs, öğrenci ve araştırmacı programları (TÜBİTAK BİDEB). Kayıtlı akademik programların (2223, 2224) yeni dönemi kalır.
ELE = re.compile(r"sonuc|basarili basvuru|hak kazanan|desteklenmeye hak|sinav|personel|mulakat|ihale|satin alma|"
                 r"hizmet alim|toplanti|calistay|bilgilendirme|tanitim gunu|egitimi basliyor|egitim programi|sergi|"
                 r"fuar|kamp|okulu|rapor(?:u)? yayim|basvuru rehber|teknik sartname|^\d{4} yili duyurulari$|"
                 r"burs|doktora|yuksek lisans|ogrenci|akademisyen|bilim soylesi|arastirmaci|stajyer")
# Resmî Gazete fihristinde ilgilendiren kararlar.
RG_ILGILI = re.compile(r"destek|tesvik|hibe|kredi|kefalet|ihracat|yatirim|hayvancilik|tarim|kobi|kosgeb|ar-?ge|"
                       r"istihdam|prim|girisim|e-ihracat|turizm|organize sanayi|bolgesel")
TARIH_ANAHTAR = re.compile(r"son basvuru|basvuru (?:tarih|suresi|donemi|takvimi)|kapanis|son gun|on kayit|"
                           r"basvurular[^.]{0,60}(?:arasinda|kadar|itibaren)|tarihine kadar|tarihleri arasinda")
TARIH = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b|\b(\d{1,2})\s+(" + "|".join(AYLAR) + r")\s+(20\d{2})\b")
KOD = re.compile(r"(?<![\d.,])(?!20[0-3]\d)(\d{4})(?![\d.,])")
DURAK = {"ve", "ile", "icin", "destek", "destegi", "programi", "program", "yili", "yilina", "ait", "olan", "bir", "bu",
         "da", "de", "2025", "2026", "2027", "cagrisi", "cagri", "duyuru", "basvuru", "kapsaminda", "hakkinda"}


def _katla(metin: str) -> str:
    from app.ihtiyac import _katla as katla
    return re.sub(r"\s+", " ", katla(metin or "")).strip()


def adres_normal(url: str) -> str:
    """Kimlik için adres: şema ve "www." farkı, sondaki "/" ve parça (#) yok sayılır."""
    p = urlparse(url.strip())
    host = (p.hostname or "").lower().removeprefix("www.")
    return urlunparse(("", host, p.path.rstrip("/") or "/", "", p.query, ""))


@dataclass
class Ilan:
    kaynak: str
    kurum: str
    metin: str
    url: str
    sinif: str = ""
    tesvik_id: int | None = None
    tarihler: list[dict] = field(default_factory=list)
    hata: str | None = None
    kurum_filtresi: bool = True     # toplayıcı kaynakta (ka.gov.tr) kayıtlar kurum ayrımı yapılmadan karşılaştırılır

    def sozluk(self) -> dict:
        return {"kaynak": self.kaynak, "kurum": self.kurum, "metin": self.metin, "url": self.url, "sinif": self.sinif,
                "tesvik_id": self.tesvik_id, "tarihler": self.tarihler, "hata": self.hata}


# ------------------------------------------------------------------ ayrıştırma (saf)
GENEL_METIN = re.compile(r"^(?:indir|detay|detayli bilgi|devamini oku|incele|tiklayiniz|daha fazla|goruntule|oku)$")


def slug_metni(url: str) -> str:
    """Adresin son parçasından başlık ("/Dokuman/ipard-iii-12-basvuru-cagri-ilani-1612" → "ipard iii 12 basvuru cagri
    ilani"): bağlantı metni "İndir", "Detaylı Bilgi" gibi genel olan listeler için (TKDK, Eximbank)."""
    son = [x for x in urlparse(url).path.split("/") if x]
    if not son:
        return ""
    parca = re.sub(r"\.(?:pdf|aspx?|php|html?)$", "", son[-1], flags=re.I)
    parca = re.sub(r"-\d+$", "", parca)
    return parca.replace("-", " ").replace("_", " ").strip() if "-" in parca or "_" in parca else ""


def baglantilar(html: str, taban_url: str) -> list[tuple[str, str]]:
    """Sayfadaki (metin, mutlak adres) çiftleri; aynı adres bir kez (en uzun metinle). Metin genelse ("İndir")
    başlık adresten türetilir."""
    from bs4 import BeautifulSoup
    s = BeautifulSoup(html, "html.parser")
    for x in s(["script", "style", "noscript", "header", "footer", "nav"]):
        x.decompose()
    sonuc: dict[str, str] = {}
    for a in s.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        metin = " ".join(a.get_text(" ").split()) or (a.get("title") or "").strip()
        url = urljoin(taban_url, href)
        if urlparse(url).scheme not in ("http", "https"):
            continue
        if len(metin) < 4 or GENEL_METIN.match(_katla(metin)):
            metin = slug_metni(url) or metin
        if len(metin) > len(sonuc.get(url, "")):
            sonuc[url] = metin
    return [(m, u) for u, m in sonuc.items()]


def ilan_mi(metin: str) -> bool:
    k = _katla(metin)
    return len(k) >= 15 and not MENU.match(k) and bool(ILAN.search(k)) and not ELE.search(k)


def resmi_gazete_ilgili_mi(metin: str) -> bool:
    k = _katla(metin)
    return "karar" in k or "teblig" in k or "yonetmelik" in k if RG_ILGILI.search(k) else False


_TEK_HARF = str.maketrans("ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZQWXÂÎÛçğıöşüâîû",
                          "abccdefgghiijklmnooprsstuuvyzqwxaiucgiosuaiu")


def katla_ayni_uzunluk(metin: str) -> str:
    """Harf harf küçültüp Türkçe harfleri düzleştirir; uzunluk değişmez ("İ".lower() iki karakter olurdu)."""
    return metin.translate(_TEK_HARF).lower()


def tarih_alintilari(metin: str, bugun: date) -> list[dict]:
    """Başvuru tarihi anahtar sözcüğünün çevresindeki (±160 karakter) bugünden sonraki tarihler; alıntı adayıyla.
    Tarih ISO; alıntı metnin özgün yazımı (doğrulama hattında birebir aranacak)."""
    sade = re.sub(r"\s+", " ", metin or "")
    katli = katla_ayni_uzunluk(sade)   # konumlar özgün metinle aynı: alıntı özgün yazımla verilir
    sonuc, gorulen = [], set()
    for a in TARIH_ANAHTAR.finditer(katli):
        bas, son = max(0, a.start() - 160), min(len(katli), a.end() + 160)
        for t in TARIH.finditer(katli, bas, son):
            try:
                if t.group(1):
                    d = date(int(t.group(3)), int(t.group(2)), int(t.group(1)))
                else:
                    d = date(int(t.group(6)), AYLAR.index(t.group(5)) + 1, int(t.group(4)))
            except ValueError:
                continue
            if d < bugun or d in gorulen:
                continue
            gorulen.add(d)
            i, j = max(0, min(a.start(), t.start()) - 40), min(len(sade), max(a.end(), t.end()) + 40)
            if i > 0 and " " in sade[i:min(a.start(), t.start())]:
                i = sade.index(" ", i) + 1          # kelime başından
            if j < len(sade) and " " in sade[max(a.end(), t.end()):j]:
                j = sade.rindex(" ", 0, j)          # kelime sonunda
            sonuc.append({"tarih": d.isoformat(), "alinti": sade[i:j].strip()})
    return sorted(sonuc, key=lambda x: x["tarih"])


def anilan_yil(metin: str, bugun: date) -> bool:
    return bool(re.search(rf"\b(?:{bugun.year}|{bugun.year + 1})\b", metin))


# ------------------------------------------------------------------ veritabanıyla karşılaştırma
@dataclass
class Katalog:
    adresler: set[str]
    kayitlar: list[tuple[int, str, str]]     # (id, kurum, katlanmış başlık)
    cagri_tarihleri: dict[int, set[str]] = field(default_factory=dict)   # kayıt → kayıtlı çağrı kapanış/ön kayıt günleri

    @classmethod
    def yukle(cls, db) -> "Katalog":
        from app.models import Tesvik, TesvikCagrisi
        adresler = set()
        kayitlar = []
        for t in db.query(Tesvik).all():
            if t.kaynak_url:
                adresler.add(adres_normal(t.kaynak_url.split("#")[0]))
            for m in t.kontrol_listesi or []:
                if m.get("kaynak_url"):
                    adresler.add(adres_normal(m["kaynak_url"].split("#")[0]))
            kayitlar.append((t.id, t.kurum or "", _katla(t.baslik)))
        tarihler: dict[int, set[str]] = {}
        for c in db.query(TesvikCagrisi).all():
            adresler.add(adres_normal(c.kaynak_url.split("#")[0]))
            for g in (c.kapanis, c.on_kayit_son):
                if g:
                    tarihler.setdefault(c.tesvik_id, set()).add(g.isoformat())
        return cls(adresler, kayitlar, tarihler)

    def cagri_kayitli_mi(self, ilan: Ilan) -> bool:
        """İlandaki son başvuru tarihi, bağlandığı programın kayıtlı bir çağrısının tarihiyle aynı mı (duyuru adresi
        kayıtlı olmasa da çağrı zaten girilmiş; ilk tarama 2026-10-13: TÜBİTAK 2223/2224)."""
        kayitli = self.cagri_tarihleri.get(ilan.tesvik_id or -1, set())
        return any(t["tarih"] in kayitli for t in ilan.tarihler)

    def siniflandir(self, ilan: Ilan) -> None:
        if adres_normal(ilan.url) in self.adresler:
            ilan.sinif = "bilinen"
            return
        metin = _katla(ilan.metin)
        kodlar = set(KOD.findall(metin))
        kurum = _katla(ilan.kurum)
        en_iyi, skor = None, 0.0
        sozler = {w for w in re.findall(r"[a-z0-9]+", metin) if len(w) > 2 and w not in DURAK}
        for tid, k, baslik in self.kayitlar:
            if kodlar and kodlar & set(KOD.findall(baslik)):
                ilan.sinif, ilan.tesvik_id = "cagri_adayi", tid
                return
            if ilan.kurum_filtresi and kurum and _katla(k)[:12] != kurum[:12]:
                continue
            b = {w for w in re.findall(r"[a-z0-9]+", baslik) if len(w) > 2 and w not in DURAK}
            if sozler and b:
                ortak = len(sozler & b)
                # Jaccard ya da kayıt başlığının ilanda geçme oranı: toplayıcı başlıkları tarih, ajans adı ve "ilan
                # edildi" ekler; KUDAKA programı (kayıt 218) Jaccard 0,41 ile kaçıyordu (ilk tarama 2026-10-13).
                j = max(ortak / len(sozler | b), ortak / len(b) if ortak >= 4 else 0.0)
                if j > skor:
                    en_iyi, skor = tid, j
        if skor >= (0.5 if ilan.kurum_filtresi else 0.6):   # toplayıcıda kurum süzgeci yok: eşik yüksek
            ilan.sinif, ilan.tesvik_id = "cagri_adayi", en_iyi
        else:
            ilan.sinif = "yeni_program"


# ------------------------------------------------------------------ ağ ve durum
def getir(url: str) -> tuple[str, str | None]:
    """(metin, hata). HTML ham döner; PDF metin katmanına çevrilir."""
    import io

    import requests
    try:
        r = requests.get(url, headers=HEADERS, timeout=ZAMAN_ASIMI_SN)
        r.raise_for_status()
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"[:200]
    if "pdf" in r.headers.get("Content-Type", "") or r.content[:4] == b"%PDF":
        try:
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages), None
        except Exception as e:
            return "", f"pdf {type(e).__name__}"
    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "latin-1"):
        m = re.search(rb"charset=[\"']?([\w-]+)", r.content[:4000], re.I)
        r.encoding = m.group(1).decode("ascii") if m else (r.apparent_encoding or "utf-8")
    return r.text, None


def duz_metin(html: str) -> str:
    from bs4 import BeautifulSoup
    s = BeautifulSoup(html, "html.parser")
    for x in s(["script", "style", "noscript"]):
        x.decompose()
    return s.get_text(" ")


def kaynaklar() -> list[dict]:
    return json.loads(KAYNAK_DOSYASI.read_text(encoding="utf-8"))["kaynaklar"]


def _oku(yol: Path, varsayilan):
    return json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else varsayilan


def _yaz(yol: Path, veri) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
    gecici.replace(yol)


def kaynak_ilanlari(k: dict, bugun: date, getirici: Callable[[str], tuple[str, str | None]]) -> tuple[list[Ilan], str | None]:
    """Bir kaynağın o anki ilan bağlantıları."""
    if k.get("tur") == "resmi_gazete":
        ilanlar, hatalar = [], []
        for g in range(RESMI_GAZETE_GUN):
            gun = bugun - timedelta(days=g)
            url = f"https://www.resmigazete.gov.tr/eskiler/{gun:%Y/%m}/{gun:%Y%m%d}.htm"
            html, hata = getirici(url)
            if hata:
                if "404" not in hata:
                    hatalar.append(f"{gun}: {hata}")
                continue
            ilanlar += [Ilan(k["ad"], k["kurum"], m, u) for m, u in baglantilar(html, url) if resmi_gazete_ilgili_mi(m)]
        return ilanlar, ("; ".join(hatalar) or None)
    url = k["url"].replace("{yil}", str(bugun.year))
    html, hata = getirici(url)
    if hata:
        return [], hata
    ilanlar, metinler = [], set()
    for m, u in baglantilar(html, url):
        if ilan_mi(m) and _katla(m) not in metinler:   # aynı başlık iki adreste (liste + kart) bir kez
            metinler.add(_katla(m))
            ilanlar.append(Ilan(k["ad"], k["kurum"], m, u, kurum_filtresi=not k.get("toplayici")))
    alan = k.get("alan_adi")
    if alan:   # kurum dışı bağlantılar (paylaşım, başka site) ilan sayılmaz
        ilanlar = [i for i in ilanlar if (urlparse(i.url).hostname or "").endswith(alan)]
    return ilanlar, None


def tara(db, bugun: date | None = None, sadece: str | None = None,
         getirici: Callable[[str], tuple[str, str | None]] = getir, bekle: Callable[[float], None] = time.sleep,
         dizin: Path | None = None) -> dict:
    """Bütün kaynakları tarar; durum, kuyruk ve raporu yazar. Özet döner."""
    dizin = dizin or DIZIN
    bugun = bugun or date.today()
    durum = _oku(dizin / "durum.json", {})
    kuyruk = _oku(dizin / "kuyruk.json", [])
    kuyrukta = {adres_normal(x["url"]) for x in kuyruk}
    katalog = Katalog.yukle(db)
    ozet = {"tarih": bugun.isoformat(), "kaynak": 0, "hata": [], "yeni": [], "taban": []}
    ayrinti = 0
    for k in kaynaklar():
        if sadece and k["ad"] != sadece:
            continue
        ozet["kaynak"] += 1
        ilanlar, hata = kaynak_ilanlari(k, bugun, getirici)
        bekle(BEKLEME_SN)
        if hata:
            ozet["hata"].append(f"{k['ad']}: {hata}")
        if not ilanlar and hata:
            continue
        d = durum.setdefault(k["ad"], {"gorulen": {}, "ilk_tarama": bugun.isoformat()})
        taban = not d["gorulen"]
        d["son_tarama"] = bugun.isoformat()
        for ilan in ilanlar:
            anahtar = adres_normal(ilan.url)
            if anahtar in d["gorulen"]:
                continue
            d["gorulen"][anahtar] = {"metin": ilan.metin[:200], "ilk": bugun.isoformat()}
            katalog.siniflandir(ilan)
            if ilan.sinif == "bilinen" or anahtar in kuyrukta:
                continue
            if taban and not anilan_yil(ilan.metin, bugun):
                continue
            if ayrinti < AYRINTI_SINIRI:
                ayrinti += 1
                metin, h = getirici(ilan.url)
                bekle(BEKLEME_SN)
                ilan.hata = h
                if not h:
                    ilan.tarihler = tarih_alintilari(duz_metin(metin) if "<" in metin[:2000] else metin, bugun)
                if ilan.sinif == "cagri_adayi" and katalog.cagri_kayitli_mi(ilan):
                    ilan.sinif = "bilinen"
                    continue
            kayit = ilan.sozluk() | {"bulunma": bugun.isoformat(), "durum": "beklemede", "taban": taban}
            kuyruk.append(kayit)
            kuyrukta.add(anahtar)
            (ozet["taban"] if taban else ozet["yeni"]).append(kayit)
    _yaz(dizin / "durum.json", durum)
    _yaz(dizin / "kuyruk.json", kuyruk)
    (dizin / f"rapor_{bugun.isoformat()}.md").write_text(rapor_md(ozet, kuyruk), encoding="utf-8")
    return ozet


def rapor_md(ozet: dict, kuyruk: list[dict] | None = None) -> str:
    """Bu taramanın yenileri ve kuyrukta bekleyen BÜTÜN adaylar (aynı gün ikinci tarama raporu boşaltmasın)."""
    sat = [f"# Çağrı keşfi — {ozet['tarih']}", "",
           f"Taranan kaynak {ozet['kaynak']}; yeni ilan {len(ozet['yeni'])}; ilk taramada (taban) güncel aday "
           f"{len(ozet['taban'])}; hata {len(ozet['hata'])}.", "",
           "Adaylar veritabanına yazılmadı. Kayda girmeden önce resmî metinde birebir doğrulanmalı "
           "(scripts/fix_veri_* hattı).", ""]
    bu_tarama = {x["url"] for x in ozet["yeni"] + ozet["taban"]}
    bekleyen = [x for x in (kuyruk or []) if x.get("durum") == "beklemede" and x["url"] not in bu_tarama]
    for baslik, liste in (("Yeni ilanlar", ozet["yeni"]), ("İlk taramada bulunan güncel adaylar", ozet["taban"]),
                          (f"Önceki taramalardan bekleyen adaylar ({len(bekleyen)})", bekleyen)):
        if not liste:
            continue
        sat += [f"## {baslik}", ""]
        for x in liste:
            ek = f" → kayıt {x['tesvik_id']}" if x.get("tesvik_id") else ""
            sat.append(f"- [{x['sinif']}{ek}] **{x['kurum']}**: [{x['metin'][:160]}]({x['url']})")
            for t in x.get("tarihler", [])[:3]:
                sat.append(f"  - {t['tarih']}: “{t['alinti'][:220]}”")
            if x.get("hata"):
                sat.append(f"  - sayfa okunamadı: {x['hata']}")
        sat.append("")
    if ozet["hata"]:
        sat += ["## Okunamayan kaynaklar", ""] + [f"- {h}" for h in ozet["hata"]] + [""]
    return "\n".join(sat)


# ------------------------------------------------------------------ self-test
def _self_test() -> int:
    import tempfile
    from types import SimpleNamespace as N

    bugun = date(2026, 10, 13)
    liste = """<html><nav><a href="/x">Duyurular</a></nav><body>
      <a href="/duyuru/1">2026 Yılı Mali Destek Programı Başvuruları Açıldı</a>
      <a href="https://www.kurum.gov.tr/duyuru/2">1501 Sanayi Ar-Ge 2026-3 Çağrısı Açıldı</a>
      <a href="/hakkimizda">Hakkımızda</a><a href="/duyuru/3">2019 Yılı Kredi Programı Sonuçları</a>
      <a href="https://twitter.com/x">Destek programı duyurusu paylaş</a>
      <a href="/eski">Bilinen Program Duyurusu 2026</a></body></html>"""
    ayrinti = ("<p>Programın son başvuru tarihi 14.11.2026 saat 18:00'dir. Ön kayıt 3 Kasım 2026 tarihine kadar "
               "yapılır.</p><p>2025 yılı sonuçları 1.2.2025 tarihinde ilan edilmiştir.</p>")
    rg = ('<a href="/eskiler/2026/10/20261013-5.pdf">2024-2026 Yıllarında Yapılacak Hayvancılık Desteklemelerine '
          'İlişkin Kararda Değişiklik Yapılmasına Dair Karar (Karar Sayısı: 11800)</a>'
          '<a href="/eskiler/2026/10/20261013-1.htm">Spor Kulüpleri Yönetmeliği</a>')
    sayfalar = {"https://www.kurum.gov.tr/duyurular": liste,
                "https://www.kurum.gov.tr/duyuru/1": ayrinti, "https://www.kurum.gov.tr/duyuru/2": ayrinti,
                "https://www.resmigazete.gov.tr/eskiler/2026/10/20261013.htm": rg}
    istekler = []

    def sahte(url):
        istekler.append(url)
        return (sayfalar[url], None) if url in sayfalar else ("", "HTTPError: 404")

    db = N(query=lambda model: N(all=lambda: (
        [N(id=7, kurum="TUBITAK", baslik="1501 - TÜBİTAK Sanayi Ar-Ge Projeleri", kaynak_url="https://a.gov.tr/p",
           kontrol_listesi=[]),
         N(id=9, kurum="Kurum", baslik="Bilinen Program", kaynak_url="https://kurum.gov.tr/eski/",
           kontrol_listesi=[])] if model.__name__ == "Tesvik" else [])))
    global kaynaklar
    asil_kaynaklar = kaynaklar
    kaynaklar = lambda: [{"ad": "kurum", "kurum": "Kurum", "url": "https://www.kurum.gov.tr/duyurular",  # noqa: E731
                          "alan_adi": "kurum.gov.tr"},
                         {"ad": "rg", "kurum": "Resmî Gazete", "tur": "resmi_gazete"}]
    try:
        with tempfile.TemporaryDirectory() as g:
            ilk = tara(db, bugun, getirici=sahte, bekle=lambda s: None, dizin=Path(g))
            n_ilk = len(istekler)
            liste_ek = liste.replace("</body>", '<a href="/duyuru/4">2026 Yılı İkinci Dönem Hibe Çağrısı</a></body>')
            sayfalar["https://www.kurum.gov.tr/duyurular"] = liste_ek
            ikinci = tara(db, bugun + timedelta(days=7), getirici=sahte, bekle=lambda s: None, dizin=Path(g))
            kuyruk = json.loads((Path(g) / "kuyruk.json").read_text(encoding="utf-8"))
            rapor = (Path(g) / f"rapor_{bugun.isoformat()}.md").read_text(encoding="utf-8")
            rapor_ikinci = (Path(g) / f"rapor_{(bugun + timedelta(days=7)).isoformat()}.md").read_text(encoding="utf-8")
    finally:
        kaynaklar = asil_kaynaklar
    tabandaki = {x["metin"]: x for x in ilk["taban"]}

    def bul(onek: str) -> dict:
        return next((x for m, x in tabandaki.items() if m.startswith(onek)), {})
    k = [
        ("menü, kurum dışı ve kısa bağlantı ilan sayılmaz", all("Hakkımızda" not in x and "paylaş" not in x
                                                              for x in tabandaki)),
        ("ilk tarama: yalnız bu/gelecek yıl anılan, bilinmeyen", not bul("2019 Yılı") and not bul("Bilinen Program")
         and len(ilk["taban"]) == 3),
        ("program kodu → mevcut kayda çağrı adayı", bul("1501 Sanayi").get("sinif") == "cagri_adayi"
         and bul("1501 Sanayi").get("tesvik_id") == 7),
        ("karşılığı yok → yeni program", bul("2026 Yılı Mali Destek").get("sinif") == "yeni_program"),
        ("tarih alıntısı: gelecek tarihler, eski yok", [t["tarih"] for t in bul("2026 Yılı Mali Destek").get("tarihler", [])]
         == ["2026-11-03", "2026-11-14"]),
        ("Resmî Gazete: ilgili karar alınır, ilgisiz alınmaz", any("Hayvancılık" in x for x in tabandaki)
         and not any("Spor" in x for x in tabandaki)),
        ("ikinci tarama yalnız yeni ilanı raporlar", len(ikinci["yeni"]) == 1
         and ikinci["yeni"][0]["metin"].startswith("2026 Yılı İkinci Dönem Hibe")
         and ikinci["taban"] == []),
        ("kuyruk birikir, tekrar etmez", len(kuyruk) == 4 and len({x["url"] for x in kuyruk}) == 4),
        ("rapor yazılır, veritabanına yazılmaz uyarısı", "veritabanına yazılmadı" in rapor and "14.11.2026" in rapor),
        ("sonraki taramanın raporu bekleyenleri de gösterir", "Önceki taramalardan bekleyen adaylar (3)" in rapor_ikinci),
        ("bulunamayan sayfa (404) hata sayılmaz", ilk["hata"] == []),
        ("ilk taramada istek sınırlı", n_ilk <= 2 + RESMI_GAZETE_GUN + AYRINTI_SINIRI),
        ("sonuç, burs ve araştırmacı duyurusu ilan sayılmaz; kayıtlı akademik programın yeni dönemi sayılır",
         not ilan_mi("OKA Teknik Destek Programı 4. Dönem Sonuçları Açıklandı")
         and not ilan_mi("2211-Yurt İçi Doktora Burs Programları 2026 Çağrısı")
         and ilan_mi("2224-Bilimsel Etkinliklere Katılımı 2026 Yılı 3. Dönem Çağrıları Açıldı")),
        ("tarih alıntısı özgün yazımla", any("Son başvuru" in t["alinti"] or "son başvuru" in t["alinti"]
                                            for t in tarih_alintilari("İLAN: Son başvuru tarihi 14.11.2026'dır.", bugun))),
        ("genel bağlantı metninde başlık adresten", slug_metni("https://x.gov.tr/Dokuman/ipard-iii-12-cagri-ilani-1612")
         == "ipard iii 12 cagri ilani"),
        ("kayıtlı çağrı tarihiyle aynı ilan bilinen sayılır",
         Katalog(set(), [], {7: {"2026-11-03"}}).cagri_kayitli_mi(
             Ilan("k", "K", "m", "u", tesvik_id=7, tarihler=[{"tarih": "2026-11-03", "alinti": "x"}]))),
        ("toplayıcı başlığı kayıt başlığını kapsıyorsa çağrı adayı", _kapsama_testi()),
        ("adres normal: www, / ve # farkı yok", adres_normal("https://www.a.gov.tr/x/#y") == adres_normal("http://a.gov.tr/x")),
    ]
    g_ = sum(1 for _, ok in k if ok)
    for ad, ok in k:
        print(f"  [{'OK' if ok else 'HATA'}] {ad}")
    print(f"cagri_kesif self-test: {g_}/{len(k)}")
    return 0 if g_ == len(k) else 1


def kuyruk_isaretle(onek: str, durum: str, aciklama: str, dizin: Path | None = None) -> int:
    """Adresi `onek` ile başlayan bekleyen adayları işaretler (eklendi / bilinen / eklenmedi); işaretlenen sayısı."""
    yol = (dizin or DIZIN) / "kuyruk.json"
    kuyruk = _oku(yol, [])
    n = 0
    for x in kuyruk:
        if x["url"].startswith(onek) and x.get("durum") == "beklemede":
            x["durum"], x["aciklama"], x["isaretlenme"] = durum, aciklama, date.today().isoformat()
            n += 1
    _yaz(yol, kuyruk)
    return n


def _kapsama_testi() -> bool:
    k = Katalog(set(), [(218, "Kuzeydoğu Anadolu Kalkınma Ajansı (KUDAKA)", _katla(
        "KUDAKA 2026 Yılı Anadoludakiler Coğrafi İşaretli Ürünlerin Üretimi ve Tanıtımı Mali Destek Programı"))])
    ilan = Ilan("t", "Kalkınma ajansları", "22 Eylül 2026 KUDAKA 2026 Yılı Anadoludakiler Coğrafi İşaretli Ürünlerin "
                "Üretimi ve Tanıtımı MDP İlan Edildi Kuzeydoğu Anadolu Kalkınma Ajansı", "u", kurum_filtresi=False)
    k.siniflandir(ilan)
    baska = Ilan("t", "Kalkınma ajansları", "8 Ekim 2026 GEKA Kadın Kooperatifleri Destek Programı İlan Edildi", "u2",
                 kurum_filtresi=False)
    k.siniflandir(baska)
    return ilan.sinif == "cagri_adayi" and ilan.tesvik_id == 218 and baska.sinif == "yeni_program"


def main() -> int:
    arg = sys.argv[1:]
    if "--gunluk" in arg:
        # Windows görevi konsolsuz pythonw.exe ile koşar (konsol penceresi kapanınca süreç Ctrl+C ile kesiliyordu,
        # 2026-10-13); pythonw'da stdout yoktur, çıktı ve hatalar bu dosyaya eklenir.
        gunluk = open(arg[arg.index("--gunluk") + 1], "a", encoding="utf-8")
        sys.stdout = sys.stderr = gunluk
        logging.basicConfig(stream=gunluk, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        print(f"--- {date.today().isoformat()} çağrı keşfi")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in arg:
        return _self_test()
    if "--rapor" in arg:
        kuyruk = _oku(DIZIN / "kuyruk.json", [])
        ozet = {"tarih": date.today().isoformat(), "kaynak": 0, "hata": [], "yeni": [], "taban": []}
        yol = DIZIN / f"rapor_{ozet['tarih']}.md"
        yol.write_text(rapor_md(ozet, kuyruk), encoding="utf-8")
        print(f"rapor (ağsız, kuyruktan): {yol}")
        return 0
    if "--isaretle" in arg:
        i = arg.index("--isaretle")
        onek, durum, aciklama = arg[i + 1], arg[i + 2], arg[i + 3]
        print(f"{kuyruk_isaretle(onek, durum, aciklama)} aday işaretlendi: {durum}")
        return 0
    if "--kuyruk" in arg:
        for x in _oku(DIZIN / "kuyruk.json", []):
            if x["durum"] == "beklemede":
                print(f"[{x['sinif']}] {x['kurum']}: {x['metin'][:100]} | {x['url']} | "
                      f"{[t['tarih'] for t in x['tarihler']]}")
        return 0
    if "--calistir" in arg:
        from app.models import SessionLocal
        sadece = arg[arg.index("--kaynak") + 1] if "--kaynak" in arg else None
        db = SessionLocal()
        try:
            ozet = tara(db, sadece=sadece)
        finally:
            db.close()
        print(f"kaynak {ozet['kaynak']}, yeni {len(ozet['yeni'])}, taban adayı {len(ozet['taban'])}, "
              f"hata {len(ozet['hata'])}; rapor: {DIZIN / ('rapor_' + ozet['tarih'] + '.md')}")
        for h in ozet["hata"]:
            print(f"  okunamadı: {h}")
        return 1 if ozet["kaynak"] and len(ozet["hata"]) == ozet["kaynak"] else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
