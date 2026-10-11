"""Dış dil modeli sağlayıcı katmanı (2026-10-11).

Danışman yanıtı ve yapay zekâ taslağı için tek giriş noktası. Varsayılan sağlayıcı `yerel`: hiçbir dış servis
çağrılmaz, yanıtı app/yerel_danisman.py kayıtlardan kuralla üretir. Anthropic API'si bu üründe kullanılmaz
(Mert, 2026-10-11: "son uçta bile anthropic api kullanma").

    LLM_SAGLAYICI=yerel           (varsayılan) dış çağrı yok
    LLM_SAGLAYICI=gemini          Google Gemini, OpenAI uyumlu uç; LLM_API_KEY zorunlu, LLM_MODEL isteğe bağlı
    LLM_SAGLAYICI=openai_uyumlu   OpenAI Chat Completions uyumlu herhangi bir uç (kendi sunucunuzdaki vLLM/Ollama
                                  dahil); LLM_BASE_URL ve LLM_MODEL zorunlu, LLM_API_KEY isteğe bağlı.
                                  LLM_KURUM / LLM_ULKE KVKK metninde gösterilir; LLM_YURTDISI=false ise sunucu
                                  Türkiye'dedir ve yurt dışı aktarımı yoktur.

Dış servisin yanıtı (akışsız alınır) kullanıcıya gitmeden önce app/dayanak.py ile denetlenir (bağlamda olmayan URL/tutar/oran/tarih
varsa yanıt atılır, yerel danışmana düşülür).

    python -m app.llm_saglayici --self-test
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_VARSAYILAN_MODEL = "gemini-2.5-flash"
ZAMAN_ASIMI_SN = 90.0
BAGLANTI_ZAMAN_ASIMI_SN = 10.0
YENIDEN_DENEME = 0   # en kötü bekleme ZAMAN_ASIMI_SN; yerel danışman zaten yedek


class LLMHatasi(Exception):
    """Dış servis çağrısı yapılamadı ya da boş/kesik yanıt döndü; çağıran yerel danışmana düşer."""


@dataclass(frozen=True)
class Saglayici:
    kod: str            # yerel | gemini | openai_uyumlu
    ad: str             # kullanıcıya gösterilen ad
    kurum: str          # veri işleyen / alıcı
    ulke: str
    yurtdisi: bool      # True ise KVKK m.9 açık rızası gerekir
    model: str
    base_url: str
    api_key: str

    @property
    def dis_mi(self) -> bool:
        return self.kod != "yerel"

    @property
    def riza_anahtari(self) -> str:
        """Rıza bu değere verilir; sağlayıcı, kurum, ülke ya da sunucu değişirse eski rıza geçersiz olur."""
        from urllib.parse import urlparse
        return f"{self.kod}:{self.kurum}:{self.ulke}:{urlparse(self.base_url).hostname or '-'}"[:200]

    def sozluk(self) -> dict:
        return {"saglayici": self.kod, "ad": self.ad, "kurum": self.kurum, "ulke": self.ulke,
                "yurtdisi": self.yurtdisi, "model": self.model if self.dis_mi else None,
                "riza_gerekli": self.dis_mi and self.yurtdisi, "etkin": etkin_mi(self)}


YEREL = Saglayici("yerel", "Teşvik Asistanı yerel danışmanı", "Teşvik Asistanı (kendi sunucumuz)", "Türkiye",
                  False, "kural-tabanli", "", "")


def _ortam(ad: str, varsayilan: str = "") -> str:
    return (os.getenv(ad) or varsayilan).strip()


def saglayici(ortam: Callable[[str, str], str] = _ortam) -> Saglayici:
    """Ortam değişkenlerinden etkin sağlayıcı. Tanınmayan değer yerel sayılır (günlüğe yazılır)."""
    kod = ortam("LLM_SAGLAYICI", "yerel").lower()
    if kod == "gemini":
        return Saglayici("gemini", "Google Gemini", "Google LLC", "ABD", True,
                         ortam("LLM_MODEL", GEMINI_VARSAYILAN_MODEL), GEMINI_URL, ortam("LLM_API_KEY", ""))
    if kod == "openai_uyumlu":
        yurtdisi = ortam("LLM_YURTDISI", "true").lower() != "false"
        return Saglayici("openai_uyumlu", ortam("LLM_AD", "Dil modeli servisi"),
                         ortam("LLM_KURUM", "servis sağlayıcı (LLM_KURUM tanımlanmamış)"),
                         ortam("LLM_ULKE", "belirtilmemiş"), yurtdisi, ortam("LLM_MODEL", ""),
                         ortam("LLM_BASE_URL", ""), ortam("LLM_API_KEY", ""))
    if kod not in ("", "yerel"):
        logger.warning("Tanınmayan LLM_SAGLAYICI=%r; yerel danışman kullanılıyor", kod)
    return YEREL


def etkin_mi(s: Saglayici | None = None) -> bool:
    """Dış sağlayıcı çağrılabilir durumda mı (yapılandırma tam ve istemci kütüphanesi kurulu)."""
    s = s or saglayici()
    if not s.dis_mi or not s.model or not s.base_url:
        return False
    if s.kod == "gemini" and not s.api_key:
        return False
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


def riza_gecerli_mi(org: Any, s: Saglayici | None = None) -> bool:
    """Kuruluşun rızası BU sağlayıcıya mı verilmiş. Yurt dışı aktarımı olmayan sağlayıcıda rıza gerekmez."""
    s = s or saglayici()
    if not s.dis_mi:
        return False
    if not s.yurtdisi:
        # Yurt içi işleme: açık rıza aranmaz; kuruluş bu sağlayıcıdan vazgeçtiyse kullanılmaz.
        return getattr(org, "ai_riza_saglayici", None) != ret_anahtari(s)
    return bool(getattr(org, "ai_yurtdisi_riza", False)) and getattr(org, "ai_riza_saglayici", None) == s.riza_anahtari


def ret_anahtari(s: Saglayici) -> str:
    """Yurt içi sağlayıcıdan vazgeçme kaydı (organizations.ai_riza_saglayici)."""
    return ("ret:" + s.riza_anahtari)[:200]


def _istemci(s: Saglayici):
    import httpx
    import openai
    return openai.OpenAI(api_key=s.api_key or "yok", base_url=s.base_url, max_retries=YENIDEN_DENEME,
                         timeout=httpx.Timeout(ZAMAN_ASIMI_SN, connect=BAGLANTI_ZAMAN_ASIMI_SN))


def _mesajlar(sistem: str, kullanici: str) -> list[dict]:
    return [{"role": "system", "content": sistem}, {"role": "user", "content": kullanici}]


def tamamla(sistem: str, kullanici: str, max_tokens: int = 8000, s: Saglayici | None = None,
            istemci: Any = None) -> tuple[str, dict]:
    """Tek seferlik yanıt. (metin, kullanım) döner; hata, boş yanıt ya da uzunluk sınırında kesilme LLMHatasi."""
    s = s or saglayici()
    if not etkin_mi(s) and istemci is None:
        raise LLMHatasi("dış dil modeli yapılandırılmamış")
    try:
        yanit = (istemci or _istemci(s)).chat.completions.create(
            model=s.model, messages=_mesajlar(sistem, kullanici), max_tokens=max_tokens)
    except Exception as e:  # ağ, kota, anahtar, zaman aşımı
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
    if durma == "length":
        raise LLMHatasi("yanıt uzunluk sınırında kesildi")
    if durma is None:
        raise LLMHatasi("yanıtın bitiş bilgisi yok (bağlantı yarıda kopmuş olabilir)")
    return metin, bilgi


# ------------------------------------------------------------------ self-test
class _Nesne:
    def __init__(self, **k):
        self.__dict__.update(k)


class _SahteIstemci:
    """OpenAI istemcisinin chat.completions.create arayüzü; ağ yok."""

    def __init__(self, metin: str = "yanıt", durma: str = "stop", hata: Exception | None = None):
        self.metin, self.durma, self.hata, self.cagrilar = metin, durma, hata, []
        self.chat = _Nesne(completions=_Nesne(create=self._create))

    def _create(self, **k):
        self.cagrilar.append(k)
        if self.hata:
            raise self.hata
        return _Nesne(choices=[_Nesne(message=_Nesne(content=self.metin), finish_reason=self.durma)],
                      usage=_Nesne(prompt_tokens=10, completion_tokens=5))


def _self_test() -> int:
    def ortam(d):
        return lambda ad, v="": d.get(ad, v)

    gem = saglayici(ortam({"LLM_SAGLAYICI": "gemini", "LLM_API_KEY": "k"}))
    yerel = saglayici(ortam({}))
    tr = saglayici(ortam({"LLM_SAGLAYICI": "openai_uyumlu", "LLM_BASE_URL": "http://10.0.0.5:8000/v1",
                          "LLM_MODEL": "qwen", "LLM_YURTDISI": "false", "LLM_KURUM": "Biz"}))
    org_eski = _Nesne(ai_yurtdisi_riza=True, ai_riza_saglayici=None)
    org_gem = _Nesne(ai_yurtdisi_riza=True, ai_riza_saglayici=gem.riza_anahtari)
    k = [("varsayılan yerel ve dış değil", yerel.kod == "yerel" and not yerel.dis_mi and not etkin_mi(yerel)),
         ("tanınmayan değer yerel", saglayici(ortam({"LLM_SAGLAYICI": "anthropic"})).kod == "yerel"),
         ("gemini anahtarsız etkin değil", not etkin_mi(saglayici(ortam({"LLM_SAGLAYICI": "gemini"})))),
         ("gemini ABD, rıza gerekli", gem.yurtdisi and gem.sozluk()["riza_gerekli"] and gem.base_url == GEMINI_URL),
         ("eski (sağlayıcısız) rıza geçersiz", not riza_gecerli_mi(org_eski, gem)),
         ("sağlayıcıya verilen rıza geçerli", riza_gecerli_mi(org_gem, gem)),
         ("yurt içi sunucuda rıza gerekmez", riza_gecerli_mi(org_eski, tr) and not tr.sozluk()["riza_gerekli"]),
         ("yurt içinde vazgeçme geçerli", not riza_gecerli_mi(_Nesne(ai_yurtdisi_riza=False,
                                                                     ai_riza_saglayici=ret_anahtari(tr)), tr)),
         ("rıza anahtarı ülke ve sunucuyu içerir", gem.riza_anahtari.endswith(":ABD:generativelanguage.googleapis.com"))]
    ist = _SahteIstemci("merhaba dünya")
    metin, bilgi = tamamla("s", "k", s=gem, istemci=ist)
    k.append(("tamamla metin ve kullanım", metin == "merhaba dünya" and bilgi["giris"] == 10
              and ist.cagrilar[0]["messages"][0]["role"] == "system"))
    for ad, ist2 in (("kesik yanıt hata", _SahteIstemci("x", durma="length")),
                     ("bitiş bilgisi yok hata", _SahteIstemci("x", durma=None)),
                     ("ağ hatası LLMHatasi", _SahteIstemci(hata=TimeoutError("t")))):
        try:
            tamamla("s", "k", s=gem, istemci=ist2)
            k.append((ad, False))
        except LLMHatasi:
            k.append((ad, True))
    try:
        tamamla("s", "k", s=yerel)
        k.append(("yerelde dış çağrı yok", False))
    except LLMHatasi:
        k.append(("yerelde dış çağrı yok", True))
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
