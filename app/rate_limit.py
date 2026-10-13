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

Istemci IP'si (2026-10-08): uretimde istekler nginx kapsayicisindan gelir; request.client.host
dogrudan kullanildiginda TUM ziyaretciler nginx'in IP'sini paylasiyordu (login 10/dk herkes icin
ortak: tek saldirgan herkesi kilitleyebiliyordu). istemci_ip() vekil basliklarini YALNIZCA dogrudan
bagli taraf settings.TRUSTED_PROXIES icindeyse okur.
"""
import ipaddress
import logging
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache

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

    def iade(self, anahtar: str) -> None:
        """Son izni geri verir (izin alindiktan sonra is basarisiz olduysa hak dusmesin)."""
        with self._kilit:
            q = self._pencereler.get(anahtar)
            if q:
                q.pop()

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

    def iade(self, anahtar: str) -> None:
        try:
            self._r.zpopmax(f"hiz:{anahtar}")
        except Exception as e:  # iade edilemezse hak yalnizca pencere sonuna kadar dusuk kalir
            logger.warning("Redis hiz sayaci iadesi yapilamadi: %s: %s", type(e).__name__, e)

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


@lru_cache(maxsize=8)
def _guvenilir_aglar(ham: str) -> tuple:
    """TRUSTED_PROXIES metnini aga cevirir. Gecersiz girdi yok sayilir ve gunluge yazilir ('*' bilerek
    desteklenmez: herkese guvenmek istemcinin X-Forwarded-For ile sayac secmesine izin verir)."""
    aglar = []
    for parca in ham.split(","):
        parca = parca.strip()
        if not parca:
            continue
        try:
            aglar.append(ipaddress.ip_network(parca, strict=False))
        except ValueError:
            logger.error("TRUSTED_PROXIES icinde gecersiz girdi yok sayildi: %r", parca)
    return tuple(aglar)


def _ip_coz(deger: str):
    """Gecerli IP ise ipaddress nesnesi (IPv4-eslemeli IPv6 -> IPv4), degilse None."""
    try:
        ip = ipaddress.ip_address(deger.strip())
    except ValueError:
        return None
    if ip.version == 6 and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _guvenilir_mi(ip, aglar: tuple) -> bool:
    return any(ip.version == ag.version and ip in ag for ag in aglar)


def istemci_ip(request: Request) -> str:
    """Hiz siniri anahtari icin istemci adresi.

    Dogrudan bagli taraf (request.client.host) guvenilir bir vekil DEGILSE baslik okunmaz, onun
    adresi doner: dogrudan baglanan biri X-Forwarded-For yazarak baskasinin sayacina dusemez ya da
    her istekte yeni sayac acamaz. Guvenilir vekilse X-Forwarded-For SAGDAN sola taranir ve ilk
    guvenilmeyen adres alinir (nginx $proxy_add_x_forwarded_for istemcinin yazdiginin SONUNA kendi
    gordugu adresi ekler; soldaki girdiler istemci kontroludur). Baslik yoksa/bozuksa nginx'in
    ustune yazdigi X-Real-IP, o da yoksa vekilin kendi adresi kullanilir."""
    es = request.client.host if request.client else ""
    aglar = _guvenilir_aglar(settings.TRUSTED_PROXIES)
    es_ip = _ip_coz(es) if es else None
    if not aglar or es_ip is None or not _guvenilir_mi(es_ip, aglar):
        return es or "bilinmiyor"

    xff = ",".join(request.headers.getlist("x-forwarded-for"))
    for parca in reversed([p for p in xff.split(",") if p.strip()]):
        ip = _ip_coz(parca)
        if ip is None:
            break  # bozuk girdi: bunun solundakiler dogrulanamaz
        if not _guvenilir_mi(ip, aglar):
            return str(ip)

    gercek = _ip_coz(request.headers.get("x-real-ip", ""))
    if gercek is not None:
        return str(gercek)
    return es


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
        ip = istemci_ip(request)
        izin, bekle = sayac.izin_ver(f"ip:{ip}:{ad}:{limit}:{pencere_sn}", limit, pencere_sn)
        if not izin:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Çok fazla istek.",
                headers={"Retry-After": str(bekle)},
            )

    return _kontrol
