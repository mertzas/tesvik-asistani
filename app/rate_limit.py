"""
Kisa pencereli hiz siniri (sliding window).

NEDEN AYRI BIR KATMAN: app/auth.py'daki check_rate_limit AYLIK KOTA
kontrolu yapar (plan basina sorgu adedi) ve yalnizca /api/sor'da kullanilir.
Bu, dakikalar icinde yuzlerce istek gonderen bir suistimali engellemez -
ornegin /api/ikas/senkronize her cagrildiginda dis API'ye gidip DB yazar,
/api/butce-onerisi ve /api/eslesme her cagrida tum tesvik tablosunu tarar.
Bu endpoint'lerin hicbirinde kisa pencereli koruma YOKTU.

SINIRLAMA - bilincli tercih: sayaclar SUREC BELLEGINDE tutulur. Tek
surecli calismada yeterli; birden fazla worker/instance ile calisildiginda
her surecin kendi sayaci olur ve efektif limit worker sayisi kadar artar.
Gercek dagitik limit icin Redis gerekir - o asamaya gelindiginde
_Sayac sinifi Redis'e tasinmali, cagri noktalari degismez.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

from app.auth import get_current_org
from app.models import Organization


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


sayac = _Sayac()


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


def ip_hiz_siniri(limit: int, pencere_sn: int = 60):
    """IP basina hiz siniri - kimlik dogrulamasi OLMAYAN endpoint'ler icin
    (orn. Ikas webhook'u: imza dogrulamasi henuz eklenmedigi icin herkes
    cagirabiliyor, en azindan oran sinirlanmali)."""

    def _kontrol(request: Request) -> None:
        ip = (request.client.host if request.client else "bilinmiyor")
        izin, bekle = sayac.izin_ver(f"ip:{ip}:{limit}:{pencere_sn}", limit, pencere_sn)
        if not izin:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Çok fazla istek.",
                headers={"Retry-After": str(bekle)},
            )

    return _kontrol
