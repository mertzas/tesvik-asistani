"""
Merkezi gunlukleme yapilandirmasi.

SORUN: 27 modulden yalnizca 2'si logging kullaniyordu ve kritik akislarda
hatalar sessizce yutuluyordu - ornegin rag.py'da Claude API cagrisi
basarisiz oldugunda `except Exception: return None` ile yedek listeye
dusuluyor ama HICBIR iz birakilmiyordu. Uretimde "AI cevap vermiyor"
sikayeti geldiginde sebebi (kota bitti mi? anahtar mi gecersiz? ag mi?)
anlamanin hicbir yolu yoktu.

Kullanim: app/main.py acilisinda bir kez kur(), modullerde
    logger = logging.getLogger(__name__)
"""
import logging
import os
import sys

_KURULDU = False


def kur(seviye: str | None = None) -> None:
    """Kok logger'i yapilandirir. Birden fazla cagrilirsa ilkinden sonrasi
    yok sayilir (uvicorn --reload ile iki kez cagrilabiliyor)."""
    global _KURULDU
    if _KURULDU:
        return

    seviye = (seviye or os.getenv("LOG_LEVEL", "INFO")).upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    kok = logging.getLogger()
    kok.setLevel(getattr(logging, seviye, logging.INFO))
    # uvicorn kendi handler'ini ekliyor; ciftlemeyi onlemek icin once temizle
    for h in list(kok.handlers):
        kok.removeHandler(h)
    kok.addHandler(handler)

    # Gurultuyu kis. anthropic/httpcore DEBUG seviyesinde istek govdesinin
    # TAMAMINI (sistem prompt + kullanici profili dahil) log'a dokuyor;
    # LOG_LEVEL=DEBUG ile calisildiginda bu hem okunamaz hem de kisisel
    # veriyi log dosyasina sizdirir. Bu yuzden INFO tavaninda tutuluyorlar.
    for gurultulu in ("httpx", "httpcore", "urllib3", "anthropic"):
        logging.getLogger(gurultulu).setLevel(logging.WARNING)

    _KURULDU = True
    logging.getLogger(__name__).info("Gunlukleme kuruldu (seviye=%s)", seviye)
