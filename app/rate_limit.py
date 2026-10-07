"""
Kisa pencereli hiz siniri (sliding window).

NEDEN AYRI BIR KATMAN: app/auth.py'daki check_rate_limit AYLIK KOTA
kontrolu yapar (plan basina sorgu adedi) ve yalnizca /api/sor'da kullanilir.
Bu, dakikalar icinde yuzlerce istek gonderen bir suistimali engellemez -
ornegin /api/ikas/senkronize her cagrildiginda dis API'ye gidip DB yazar,
/api/butce-onerisi ve /api/eslesme her cagrida tum tesvik tablosunu tarar.
Bu endpoint'lerin hicbirinde kisa pencereli koruma YOKTU.

Sayac secimi (2026-10-07): REDIS_URL bos ise sayaclar SUREC BELLEGINDE tutulur (tek
islemci icin yeterli; --workers 2 ile her iscinin kendi sayaci olur, efektif limit
iki katina cikar). REDIS_URL doluysa sayaclar Redis'te (sirali kume, kayan pencere)
tutulur ve tum isciler/instance'lar ayni limiti paylasir. Redis'e ulasilamazsa
istek REDDEDILMEZ, sadece gunluge yazilir (hiz siniri bir guvenlik katmani, servis
kesintisi sebebi olmamali). Cagri noktalari her iki durumda da ayni.
"""
import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

from app.auth import get_current_org
from app.models import Organization, settings

logger = logging.getLogger(__name__)


class _Sayac:
    """Anahtar basina zaman damgasi penceresi tutar. Thread-safe."""

    def __init__(self) -> None:
        self._pencereler: dict[str, deque] = defaultdict(deque)
        self._kilit = threading.Lock()

    def izin_ver(self, anahtar: str, limit: int, pencere_sn: int) -> tuple[bool, int]:
        """(izin_verildi_mi, kac_saniye_sonra_tekrar_denenebilir) doner."""
        simdi = time.monotonic()
        esik = simdi - pencere_sn
        with self._kilit:
            q = self._pencereler[anahtar]
            while q and q[0] < esik:
                q.popleft()
            if len(q) >= limit:
                bekle = int(q[0] + pencere_sn - simdi) + 1
                return False, max(bekle, 1)
            q.append(simdi)
            return True, 0

    def temizle(self) -> None:
        """Testler icin - sayaclari sifirlar."""
        with self._kilit:
            self._pencereler.clear()


class _RedisSayac:
    """Redis sirali kume ile kayan pencere: ZREMRANGEBYSCORE (eski damgalari at) -> ZCARD ->
    sinir altindaysa ZADD + EXPIRE. Tum isciler ayni anahtari gorur."""

    def __init__(self, client) -> None:
        self._r = client

    def izin_ver(self, anahtar: str, limit: int, pencere_sn: int) -> tuple[bool, int]:
        simdi = time.time()
        k = f"hiz:{anahtar}"
        try:
            p = self._r.pipeline()
            p.zremrangebyscore(k, 0, simdi - pencere_sn)
            p.zcard(k)
            p.zrange(k, 0, 0, withscores=True)
            _, adet, en_eski = p.execute()
            if adet >= limit:
                ilk = en_eski[0][1] if en_eski else simdi
                return False, max(int(ilk + pencere_sn - simdi) + 1, 1)
            p = self._r.pipeline()
            p.zadd(k, {f"{simdi:.6f}": simdi})
            p.expire(k, pencere_sn + 1)
            p.execute()
            return True, 0
        except Exception as e:  # baglanti/timeout: acik kal, gunluge yaz
            logger.warning("Redis hiz sayaci erisilemedi, istek sinirlanmadan gecirildi: %s: %s",
                           type(e).__name__, e)
            return True, 0

    def temizle(self) -> None:
        try:
            for k in self._r.scan_iter("hiz:*"):
                self._r.delete(k)
        except Exception:
            pass


def _sayac_kur():
    if not settings.REDIS_URL:
        return _Sayac()
    try:
        import redis
        client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=0.5, socket_connect_timeout=0.5)
        client.ping()
        logger.info("Hiz siniri sayaclari Redis'te (%s)", settings.REDIS_URL.split("@")[-1])
        return _RedisSayac(client)
    except Exception as e:
        logger.error("REDIS_URL tanimli ama baglanilamadi (%s: %s); surec ici sayaca dusuldu. "
                     "Cok iscili dagitimda limit isci sayisi kadar gevser.", type(e).__name__, e)
        return _Sayac()


sayac = _sayac_kur()


def org_hiz_siniri(limit: int, pencere_sn: int = 60):
    """Oturum acmis kullanicinin ORGANIZASYONU basina hiz siniri dependency'si.

    Kullanim:
        @app.get("/api/pahali", dependencies=[Depends(org_hiz_siniri(10))])
    """

    def _kontrol(current_org: Organization = Depends(get_current_org)) -> None:
        izin, bekle = sayac.izin_ver(f"org:{current_org.id}:{limit}:{pencere_sn}", limit, pencere_sn)
        if not izin:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Çok fazla istek gönderdiniz. {bekle} saniye sonra tekrar deneyin.",
                headers={"Retry-After": str(bekle)},
            )

    return _kontrol


def ip_hiz_siniri(limit: int, pencere_sn: int = 60, ad: str = ""):
    """IP basina hiz siniri - kimlik dogrulamasi OLMAYAN endpoint'ler icin
    (orn. Ikas webhook'u: imza dogrulamasi henuz eklenmedigi icin herkes
    cagirabiliyor, en azindan oran sinirlanmali).

    `ad` verilirse sayac o uc noktaya ozeldir; verilmezse ayni limit/pencereli uc noktalar
    sayaci paylasir (login ve signup ayni sayaca dusmesin diye eklendi, 2026-10-07)."""

    def _kontrol(request: Request) -> None:
        ip = (request.client.host if request.client else "bilinmiyor")
        izin, bekle = sayac.izin_ver(f"ip:{ip}:{ad}:{limit}:{pencere_sn}", limit, pencere_sn)
        if not izin:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Çok fazla istek.",
                headers={"Retry-After": str(bekle)},
            )

    return _kontrol
