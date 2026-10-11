"""Dil modeli sağlayıcı katmanı (2026-10-11; üçüncü taraf servisler 2026-10-11'de kaldırıldı).

Danışman yanıtı, yapay zekâ taslağı ve NACE çıkarımı için tek giriş noktası. Veri güvenliği kuralı: kullanıcı ya da
işletme verisi HİÇBİR üçüncü taraf yapay zekâ servisine gitmez (Anthropic, Google Gemini/AI Studio, OpenAI dahil;
Mert, 2026-10-11: "son uçta bile anthropic api kullanma", "google open ai studio da kullanma, ikas veri güvenliğine
önem veriyor").

    LLM_SAGLAYICI=yerel         (varsayılan) dil modeli yok; yanıtı app/yerel_danisman.py kayıtlardan kuralla üretir
    LLM_SAGLAYICI=ozel_sunucu   kendi altyapımızda çalışan açık ağırlıklı model (Ollama, vLLM, llama.cpp sunucusu;
                                Chat Completions protokolü). LLM_BASE_URL ve LLM_MODEL zorunlu, LLM_API_KEY isteğe bağlı.

`ozel_sunucu` yalnız iç ağ adresine bağlanır: LLM_BASE_URL'nin sunucusu loopback/özel IP (10/8, 172.16/12,
192.168/16, 127/8, ::1, fc00::/7) ya da tek etiketli servis adı (Docker ağında `ollama`) olmalıdır; alan adı
(api.openai.com, generativelanguage.googleapis.com …) reddedilir. Her çağrıdan hemen önce ad çözülür ve çözülen
TÜM adresler iç ağda değilse çağrı yapılmaz (DNS ile dışarı yönlendirme engeli). HTTP(S)_PROXY ortam değişkenleri
yok sayılır, yönlendirme izlenmez. Böylece veri sunucumuzun ağından çıkmaz; yurt dışı aktarımı yoktur, KVKK m.9
açık rızası gerekmez (kullanıcı yine de vazgeçebilir). Eski yapılandırma değerleri (gemini, openai_uyumlu,
anthropic) reddedilir ve yerel danışman kullanılır.

Model kuruluş bazında AÇIKÇA açılır (organizations.ai_riza_saglayici == KULLANIM_KAYDI); açılmamış ya da vazgeçmiş
kuruluşun verisi modele hiç verilmez. Kayıt sağlayıcıdan ve sunucu adresinden bağımsızdır: yönetici modeli kapatıp
açsa ya da adresi değiştirse de kullanıcının tercihi korunur (Opus güvenlik incelemesi 2026-10-11).

Modelin yanıtı kullanıcıya gitmeden önce app/dayanak.py ile denetlenir (bağlamda olmayan URL/tutar/oran/tarih
varsa yanıt atılır, yerel danışmana düşülür).

    python -m app.llm_saglayici --self-test
"""
from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

ZAMAN_ASIMI_SN = 90.0   # LLM_ZAMAN_ASIMI_SN ile değiştirilebilir (GPU'suz sunucuda 8B model 90 sn'yi aşabilir)
BAGLANTI_ZAMAN_ASIMI_SN = 10.0
YENIDEN_DENEME = 0   # en kötü bekleme ZAMAN_ASIMI_SN; yerel danışman zaten yedek
# Sunucunun bildirdiği giriş token'ı, istemin karakter sayısından beklenenin bu oranının altındaysa istem sunucuda
# kesilmiştir (Ollama varsayılan bağlam penceresi; 2026-10-11 ölçümünde ~9 bin token'lık istemin 2.051'i görüldü ve
# model kayıtları görmeden yanlış hüküm verdi). Türkçe metinde token başına ~3-4 karakter; eşik muhafazakâr.
KARAKTER_PER_TOKEN = 4.5
KESIK_ISTEM_ORANI = 0.6
KULLANIM_KAYDI = "kabul:ozel_sunucu"   # kuruluş kendi sunucumuzdaki modeli açtı
# İç ağ: açık izin listesi (is_private 6to4/Teredo/NAT64/belgeleme aralıklarını da "özel" sayıyor).
IC_AGLAR = tuple(ipaddress.ip_network(a) for a in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "::1/128", "fc00::/7"))
REDDEDILEN_SAGLAYICILAR = ("gemini", "openai_uyumlu", "openai", "anthropic", "claude", "google")
OZEL_SUNUCU_AD = "Teşvik Asistanı dil modeli (kendi sunucumuz)"
OZEL_SUNUCU_KURUM = "Teşvik Asistanı (kendi sunucumuz; üçüncü tarafa aktarım yok)"


class LLMHatasi(Exception):
    """Model çağrısı yapılamadı ya da boş/kesik yanıt döndü; çağıran yerel danışmana düşer."""


@dataclass(frozen=True)
class Saglayici:
    kod: str            # yerel | ozel_sunucu
    ad: str             # kullanıcıya gösterilen ad
    kurum: str          # veriyi işleyen
    ulke: str
    yurtdisi: bool      # her iki sağlayıcıda da False; alan API uyumluluğu için duruyor
    model: str
    base_url: str
    api_key: str

    @property
    def dis_mi(self) -> bool:
        """Kural tabanlı danışman dışında bir dil modeli mi (iç ağda da olsa ayrı bir servis)."""
        return self.kod != "yerel"

    def sozluk(self) -> dict:
        return {"saglayici": self.kod, "ad": self.ad, "kurum": self.kurum, "ulke": self.ulke,
                "yurtdisi": self.yurtdisi, "model": self.model if self.dis_mi else None,
                "riza_gerekli": False, "ucuncu_taraf": False, "varsayilan_kapali": True, "etkin": etkin_mi(self)}


YEREL = Saglayici("yerel", "Teşvik Asistanı yerel danışmanı", "Teşvik Asistanı (kendi sunucumuz)", "Türkiye",
                  False, "kural-tabanli", "", "")


def _ortam(ad: str, varsayilan: str = "") -> str:
    import os
    return (os.getenv(ad) or varsayilan).strip()


def saglayici(ortam: Callable[[str, str], str] = _ortam) -> Saglayici:
    """Ortam değişkenlerinden etkin sağlayıcı. Üçüncü taraf ya da tanınmayan değer yerel sayılır (günlüğe yazılır)."""
    kod = ortam("LLM_SAGLAYICI", "yerel").lower()
    if kod == "ozel_sunucu":
        return Saglayici("ozel_sunucu", ortam("LLM_AD", OZEL_SUNUCU_AD), OZEL_SUNUCU_KURUM,
                         ortam("LLM_ULKE", "Türkiye"), False,
                         ortam("LLM_MODEL", ""), ortam("LLM_BASE_URL", ""), ortam("LLM_API_KEY", ""))
    if kod in REDDEDILEN_SAGLAYICILAR:
        logger.error("LLM_SAGLAYICI=%r üçüncü taraf bir servis; veri güvenliği kuralı gereği kullanılmaz, yerel "
                     "danışman etkin (kendi sunucunuzdaki model için LLM_SAGLAYICI=ozel_sunucu)", kod)
    elif kod not in ("", "yerel"):
        logger.warning("Tanınmayan LLM_SAGLAYICI=%r; yerel danışman kullanılıyor", kod)
    return YEREL


def _ic_ip_mi(adres: str) -> bool:
    try:
        ip = ipaddress.ip_address(adres.split("%")[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.teredo or ip.sixtofour:
            return False
        if ip.ipv4_mapped:
            ip = ip.ipv4_mapped
    return any(ip.version == ag.version and ip in ag for ag in IC_AGLAR)


def ic_ag_adresi_mi(url: str) -> bool:
    """URL iç ağdaki bir sunucuyu mu gösteriyor (ad çözmeden; çözüm denetimi çağrı anında ayrıca yapılır)."""
    p = urlparse(url or "")
    host = (p.hostname or "").lower()
    if p.scheme not in ("http", "https") or not host or p.username or p.password:
        return False
    if _ic_ip_mi(host):
        return True
    try:
        ipaddress.ip_address(host)
        return False          # genel IP
    except ValueError:
        pass
    # tek etiketli servis adı: ASCII, harfle başlar (sayısal "134744072", "0x7f000001" ve Unicode adlar reddedilir)
    return host == "localhost" or bool(re.fullmatch(r"[a-z][a-z0-9_-]{0,62}", host))


def cozumlenen_adresler(url: str, cozucu: Callable = socket.getaddrinfo) -> list[str]:
    """Sunucu adının çözüldüğü adresler; çözülemezse boş."""
    p = urlparse(url or "")
    try:
        kayitlar = cozucu(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return []
    return list(dict.fromkeys(k[4][0] for k in kayitlar))


def cozumlenen_adresler_ic_agda_mi(url: str, cozucu: Callable = socket.getaddrinfo) -> bool:
    """Sunucu adının çözüldüğü tüm adresler iç ağda mı (DNS ile dış adrese yönlendirmeyi engeller)."""
    adresler = cozumlenen_adresler(url, cozucu)
    return bool(adresler) and all(_ic_ip_mi(a) for a in adresler)


_UYARILAN: set[str] = set()


def etkin_mi(s: Saglayici | None = None) -> bool:
    """Kendi sunucumuzdaki model çağrılabilir durumda mı (yapılandırma tam ve adres iç ağda)."""
    s = s or saglayici()
    if s.kod != "ozel_sunucu" or not s.model or not s.base_url:
        return False
    if not ic_ag_adresi_mi(s.base_url):
        if s.base_url not in _UYARILAN:      # her istekte değil, bir kez
            _UYARILAN.add(s.base_url)
            logger.error("LLM_BASE_URL (sunucu %r) iç ağ adresi değil; veri dışarı çıkmasın diye model kullanılmıyor",
                         urlparse(s.base_url).hostname)
        return False
    return True


def riza_gecerli_mi(org: Any, s: Saglayici | None = None) -> bool:
    """Kuruluş kendi sunucumuzdaki modeli açtı mı. Yalnız açık kullanım kaydı geçerlidir; eski üçüncü taraf rıza
    kayıtları ("gemini:…", "anthropic:…") ve vazgeçme kayıtları ("ret:…") modeli açmaz."""
    s = s or saglayici()
    return s.dis_mi and getattr(org, "ai_riza_saglayici", None) == KULLANIM_KAYDI


# ------------------------------------------------------------------ HTTP istemcisi (SDK yok)
def _nesne(x: Any) -> Any:
    """JSON yanıtını öznitelikle okunur nesneye çevirir (yanit.choices[0].message.content)."""
    if isinstance(x, dict):
        return SimpleNamespace(**{k: _nesne(v) for k, v in x.items()})
    if isinstance(x, list):
        return [_nesne(v) for v in x]
    return x


class _Tamamlama:
    """Chat Completions uç noktası (POST {base_url}/chat/completions). Ollama, vLLM ve llama.cpp sunucusu bu
    protokolü konuşur; istemci kütüphanesi gerekmez."""

    def __init__(self, s: Saglayici, eszamansiz: bool, cozucu: Callable = socket.getaddrinfo, tasima: Any = None):
        self.s, self.eszamansiz, self.cozucu, self.tasima = s, eszamansiz, cozucu, tasima

    def _hazirla(self, govde: dict) -> tuple[str, dict, dict]:
        """İç ağ denetimi + DNS sabitleme. http'de ad bir kez çözülür ve istek denetlenen IP'ye gider (Host başlığı
        özgün ad); böylece denetim ile bağlantı arasında DNS yanıtı değişse de trafik dışarı çıkamaz. https'te
        sertifika adı gerektiği için sabitleme yapılmaz (denetim yine yapılır; iç ağda http önerilir)."""
        url = self.s.base_url
        adresler = cozumlenen_adresler(url, self.cozucu) if ic_ag_adresi_mi(url) else []
        if not adresler or not all(_ic_ip_mi(a) for a in adresler):
            raise LLMHatasi("model sunucusu iç ağda değil; çağrı yapılmadı")
        if govde.get("stream"):
            raise LLMHatasi("akışlı istek desteklenmiyor")
        basliklar = {"Content-Type": "application/json"}
        if self.s.api_key:
            basliklar["Authorization"] = f"Bearer {self.s.api_key}"
        p = urlparse(url)
        if p.scheme == "http":
            ip = adresler[0]
            hedef = f"[{ip}]" if ":" in ip else ip
            basliklar["Host"] = p.netloc
            url = p._replace(netloc=f"{hedef}:{p.port}" if p.port else hedef).geturl()
        return url.rstrip("/") + "/chat/completions", basliklar, govde

    @staticmethod
    def _coz(yanit) -> Any:
        if yanit.status_code >= 400:
            # gövde günlüğe/hataya yazılmaz (istem içeriği yansıtılmış olabilir; KVKK metni bölüm 8)
            raise LLMHatasi(f"model sunucusu HTTP {yanit.status_code} döndü")
        try:
            return _nesne(yanit.json())
        except (ValueError, json.JSONDecodeError) as e:
            raise LLMHatasi("yanıt JSON değil") from e

    def create(self, **govde):
        import httpx
        zaman = httpx.Timeout(zaman_asimi(), connect=BAGLANTI_ZAMAN_ASIMI_SN)
        ek = {"transport": self.tasima} if self.tasima is not None else {}
        if self.eszamansiz:
            async def _calis():
                import asyncio
                url, basliklar, istek = await asyncio.to_thread(self._hazirla, govde)   # DNS olay döngüsünü kilitlemez
                async with httpx.AsyncClient(timeout=zaman, trust_env=False, follow_redirects=False, **ek) as c:
                    return self._coz(await c.post(url, json=istek, headers=basliklar))
            return _calis()
        url, basliklar, istek = self._hazirla(govde)
        with httpx.Client(timeout=zaman, trust_env=False, follow_redirects=False, **ek) as c:
            return self._coz(c.post(url, json=istek, headers=basliklar))


def zaman_asimi() -> float:
    """Model yanıtı için bekleme sınırı (sn); geçersiz değerde varsayılan."""
    try:
        return max(5.0, float(_ortam("LLM_ZAMAN_ASIMI_SN", str(ZAMAN_ASIMI_SN))))
    except ValueError:
        return ZAMAN_ASIMI_SN


def istemci(s: Saglayici | None = None, eszamansiz: bool = False, cozucu: Callable = socket.getaddrinfo,
            tasima: Any = None):
    """`.chat.completions.create(**istek)` arayüzlü istemci (eşzamansızda create bir coroutine döndürür).
    `tasima`: testlerde httpx.MockTransport (ağ yok)."""
    s = s or saglayici()
    return SimpleNamespace(chat=SimpleNamespace(completions=_Tamamlama(s, eszamansiz, cozucu, tasima)))


def _istemci(s: Saglayici):
    return istemci(s)


def _mesajlar(sistem: str, kullanici: str) -> list[dict]:
    return [{"role": "system", "content": sistem}, {"role": "user", "content": kullanici}]


def tamamla(sistem: str, kullanici: str, max_tokens: int = 8000, s: Saglayici | None = None,
            istemci: Any = None) -> tuple[str, dict]:
    """Tek seferlik yanıt. (metin, kullanım) döner; hata, boş yanıt ya da uzunluk sınırında kesilme LLMHatasi."""
    s = s or saglayici()
    if not etkin_mi(s) and istemci is None:
        raise LLMHatasi("kendi sunucumuzda dil modeli yapılandırılmamış")
    try:
        yanit = (istemci or _istemci(s)).chat.completions.create(
            model=s.model, messages=_mesajlar(sistem, kullanici), max_tokens=max_tokens)
    except LLMHatasi:
        raise
    except Exception as e:  # ağ, zaman aşımı
        logger.warning("%s çağrısı başarısız: %s: %s", s.ad, type(e).__name__, e)
        raise LLMHatasi(f"{type(e).__name__}") from e
    secim = (getattr(yanit, "choices", None) or [None])[0]
    metin = ((getattr(getattr(secim, "message", None), "content", None)) or "").strip()
    durma = getattr(secim, "finish_reason", None)
    kullanim = getattr(yanit, "usage", None)
    bilgi = {"giris": getattr(kullanim, "prompt_tokens", None), "cikis": getattr(kullanim, "completion_tokens", None),
             "durma": durma, "model": s.model}
    if not metin:
        raise LLMHatasi("boş yanıt")
    beklenen = (len(sistem) + len(kullanici)) / KARAKTER_PER_TOKEN
    if bilgi["giris"] is not None and beklenen >= 500 and bilgi["giris"] < beklenen * KESIK_ISTEM_ORANI:
        logger.error("%s istemi kesmiş görünüyor (giriş %s token, beklenen en az ~%d); bağlam penceresini büyütün "
                     "(Ollama: OLLAMA_CONTEXT_LENGTH)", s.ad, bilgi["giris"], beklenen * KESIK_ISTEM_ORANI)
        raise LLMHatasi("istem model sunucusunda kesildi (bağlam penceresi küçük)")
    if durma == "length":
        raise LLMHatasi("yanıt uzunluk sınırında kesildi")
    if durma is None:
        raise LLMHatasi("yanıtın bitiş bilgisi yok (bağlantı yarıda kopmuş olabilir)")
    return metin, bilgi


# ------------------------------------------------------------------ self-test
class _SahteIstemci:
    """chat.completions.create arayüzü; ağ yok."""

    def __init__(self, metin: str = "yanıt", durma: str = "stop", hata: Exception | None = None):
        self.metin, self.durma, self.hata, self.cagrilar = metin, durma, hata, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **k):
        self.cagrilar.append(k)
        if self.hata:
            raise self.hata
        return _nesne({"choices": [{"message": {"content": self.metin}, "finish_reason": self.durma}],
                       "usage": {"prompt_tokens": 10, "completion_tokens": 5}})


def _self_test() -> int:
    def ortam(d):
        return lambda ad, v="": d.get(ad, v)

    def cozucu(adres):
        return lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (adres, 80))]

    yerel = saglayici(ortam({}))
    oz = saglayici(ortam({"LLM_SAGLAYICI": "ozel_sunucu", "LLM_BASE_URL": "http://ollama:11434/v1",
                          "LLM_MODEL": "qwen"}))
    k = [("varsayılan yerel ve dış değil", yerel.kod == "yerel" and not yerel.dis_mi and not etkin_mi(yerel)),
         ("gemini reddedilir", saglayici(ortam({"LLM_SAGLAYICI": "gemini", "LLM_API_KEY": "k"})).kod == "yerel"),
         ("openai_uyumlu reddedilir", saglayici(ortam({"LLM_SAGLAYICI": "openai_uyumlu"})).kod == "yerel"),
         ("anthropic reddedilir", saglayici(ortam({"LLM_SAGLAYICI": "anthropic"})).kod == "yerel"),
         ("özel sunucu etkin, yurt içi, rıza gerekmez", etkin_mi(oz) and not oz.yurtdisi
          and not oz.sozluk()["riza_gerekli"] and not oz.sozluk()["ucuncu_taraf"]),
         ("özel IP ve loopback kabul", all(ic_ag_adresi_mi(u) for u in (
             "http://10.0.0.5:8000/v1", "http://127.0.0.1:11434/v1", "http://[::1]:8000/v1", "http://localhost:8080",
             "http://192.168.1.20/v1", "http://172.20.0.3:8000/v1"))),
         ("alan adı ve genel IP reddedilir", not any(ic_ag_adresi_mi(u) for u in (
             "https://api.openai.com/v1", "https://generativelanguage.googleapis.com/v1beta/openai/",
             "http://8.8.8.8/v1", "http://ollama.example.com/v1", "ftp://10.0.0.5/", "http://u:p@10.0.0.5/",
             "http://0.0.0.0:8000/v1", "http://169.254.169.254/latest"))),
         ("6to4, Teredo, NAT64, belgeleme ve CGNAT reddedilir", not any(ic_ag_adresi_mi(u) for u in (
             "http://[2002:808:808::1]/v1", "http://[2001:0:4136:e378:8000:63bf:3fff:fdd2]/v1",
             "http://[64:ff9b:1::808:808]/v1", "http://198.18.0.1/v1", "http://192.0.2.1/v1", "http://100.64.0.1/v1",
             "http://240.0.0.1/v1"))),
         ("sayısal ve Unicode tek etiketli adlar reddedilir", not any(ic_ag_adresi_mi(u) for u in (
             "http://134744072/v1", "http://0x7f000001/v1", "http://ｏｌｌａｍａ/v1"))),
         ("dış adrese çözülen servis adı reddedilir",
          not cozumlenen_adresler_ic_agda_mi("http://ollama:11434/v1", cozucu("93.184.216.34"))
          and cozumlenen_adresler_ic_agda_mi("http://ollama:11434/v1", cozucu("172.18.0.4"))),
         ("genel adresli özel sunucu etkin değil", not etkin_mi(saglayici(ortam({
             "LLM_SAGLAYICI": "ozel_sunucu", "LLM_BASE_URL": "https://api.openai.com/v1", "LLM_MODEL": "x"})))),
         ("model yalnız açıkça açılınca", riza_gecerli_mi(SimpleNamespace(ai_riza_saglayici=KULLANIM_KAYDI), oz)
          and not riza_gecerli_mi(SimpleNamespace(ai_riza_saglayici=None), oz)
          and not riza_gecerli_mi(SimpleNamespace(ai_riza_saglayici="ret:x"), oz)
          and not riza_gecerli_mi(SimpleNamespace(ai_riza_saglayici="gemini:Google LLC:ABD:x"), oz)
          and not riza_gecerli_mi(SimpleNamespace(ai_riza_saglayici=KULLANIM_KAYDI), yerel))]
    ist = _SahteIstemci("merhaba dünya")
    metin, bilgi = tamamla("s", "k", s=oz, istemci=ist)
    k.append(("tamamla metin ve kullanım", metin == "merhaba dünya" and bilgi["giris"] == 10
              and ist.cagrilar[0]["messages"][0]["role"] == "system"))
    try:
        tamamla("s", "k" * 40000, s=oz, istemci=_SahteIstemci("y"))     # sahte istemci 10 giriş token'ı bildirir
        k.append(("sunucuda kesilen istem reddedilir", False))
    except LLMHatasi:
        k.append(("sunucuda kesilen istem reddedilir", True))
    for ad, ist2 in (("kesik yanıt hata", _SahteIstemci("x", durma="length")),
                     ("bitiş bilgisi yok hata", _SahteIstemci("x", durma=None)),
                     ("ağ hatası LLMHatasi", _SahteIstemci(hata=TimeoutError("t")))):
        try:
            tamamla("s", "k", s=oz, istemci=ist2)
            k.append((ad, False))
        except LLMHatasi:
            k.append((ad, True))
    try:
        istemci(oz, cozucu=cozucu("93.184.216.34")).chat.completions.create(model="q", messages=[])
        k.append(("dışa çözülen adrese HTTP isteği gitmez", False))
    except LLMHatasi:
        k.append(("dışa çözülen adrese HTTP isteği gitmez", True))
    import httpx
    gelen = []

    def _sunucu(istek):
        gelen.append(istek)
        return httpx.Response(200, json={"choices": [{"message": {"content": "tamam"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 5, "completion_tokens": 1}})
    yanit = istemci(oz, cozucu=cozucu("172.18.0.4"), tasima=httpx.MockTransport(_sunucu)).chat.completions.create(
        model="q", messages=[{"role": "user", "content": "x"}])
    k.append(("http isteği denetlenen IP'ye sabitlenir, Host özgün ad", gelen[0].url.host == "172.18.0.4"
              and gelen[0].headers["host"] == "ollama:11434" and yanit.choices[0].message.content == "tamam"))
    hata_govdesi = istemci(oz, cozucu=cozucu("172.18.0.4"), tasima=httpx.MockTransport(
        lambda r: httpx.Response(500, text="GİZLİ PROFİL")))
    try:
        hata_govdesi.chat.completions.create(model="q", messages=[])
        k.append(("hata gövdesi hataya yazılmaz", False))
    except LLMHatasi as e:
        k.append(("hata gövdesi hataya yazılmaz", "GİZLİ" not in str(e)))
    try:
        tamamla("s", "k", s=yerel)
        k.append(("yerelde model çağrısı yok", False))
    except LLMHatasi:
        k.append(("yerelde model çağrısı yok", True))
    for ad, ok in k:
        print(f"  {'OK ' if ok else 'HATA'} {ad}")
    g = sum(ok for _, ok in k)
    print(f"\nself-test: {g}/{len(k)} geçti")
    return 0 if g == len(k) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(saglayici().sozluk())
