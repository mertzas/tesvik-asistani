"""
Open-Meteo entegrasyonu - saha sensoru olmadiginda/koptugunda bolgesel
don ve hastalik riski tahmini icin YEDEK veri kaynagi.

ONEMLI: Bu modul saha sensorunun YERINE GECMEZ. Open-Meteo bir bolgesel
tahmin servisidir (birkac km cozunurluklu); parselin gercek mikro-iklimini
(sera ici, ruzgara kapali vadi, vs.) yansitmaz. cilek_engine.py bu veriyi
SADECE sensor verisi yoksa/bayatsa kullanir ve donen sonucta veri_kaynagi
alaniyla acikca "bolgesel_tahmin" olarak isaretler - ciftci gercek sensor
okumasi ile bolgesel tahmini asla birbirine karistirmamalidir.

API key gerekmez, ucretsiz, rate limit cok cömerttir (bkz.
https://open-meteo.com/en/docs). Agdan/servis tarafindan herhangi bir
hata durumunda None doner - hicbir zaman exception yukselmez, cagiran
taraf (cilek_engine) bunu "veri_yok" olarak ele almaya devam eder.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
ISTEK_TIMEOUT_SANIYE = 5


@dataclass
class BolgeselHavaDurumu:
    sicaklik: float
    nispi_nem: float
    ciy_noktasi: Optional[float]


@dataclass
class SaatlikTahmin:
    zaman: datetime
    sicaklik: float
    nispi_nem: Optional[float]


def bolgesel_hava_durumu_getir(enlem: float, boylam: float) -> Optional[BolgeselHavaDurumu]:
    """
    Verilen konum icin anlik bolgesel sicaklik/nem cek. Ag hatasi, timeout
    veya beklenmeyen yanit formatinda None doner - crash ETMEZ.
    """
    try:
        yanit = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": enlem,
                "longitude": boylam,
                "current": "temperature_2m,relative_humidity_2m,dew_point_2m",
                "timezone": "auto",
            },
            timeout=ISTEK_TIMEOUT_SANIYE,
        )
        yanit.raise_for_status()
        veri = yanit.json()
        guncel = veri.get("current")
        if not guncel or guncel.get("temperature_2m") is None:
            return None

        return BolgeselHavaDurumu(
            sicaklik=guncel["temperature_2m"],
            nispi_nem=guncel.get("relative_humidity_2m"),
            ciy_noktasi=guncel.get("dew_point_2m"),
        )
    except (requests.RequestException, ValueError, KeyError):
        return None


def bolgesel_saatlik_tahmin_getir(enlem: float, boylam: float, saat_sayisi: int = 48) -> list[SaatlikTahmin]:
    """
    Onumuzdeki `saat_sayisi` saat icin saatlik sicaklik/nem TAHMINI ceker
    (erken uyari icin - "su an" degil "bu gece/yarin ne olacak" sorusuna
    cevap verir). Ag hatasi/beklenmeyen format durumunda BOS LISTE doner,
    crash etmez.
    """
    try:
        yanit = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": enlem,
                "longitude": boylam,
                "hourly": "temperature_2m,relative_humidity_2m",
                "forecast_hours": saat_sayisi,
                "timezone": "auto",
            },
            timeout=ISTEK_TIMEOUT_SANIYE,
        )
        yanit.raise_for_status()
        veri = yanit.json()
        saatlik = veri.get("hourly")
        if not saatlik or not saatlik.get("time"):
            return []

        zamanlar = saatlik["time"]
        sicakliklar = saatlik.get("temperature_2m", [])
        nemler = saatlik.get("relative_humidity_2m", [])

        sonuc = []
        for i, zaman_str in enumerate(zamanlar):
            if i >= len(sicakliklar) or sicakliklar[i] is None:
                continue
            sonuc.append(SaatlikTahmin(
                zaman=datetime.fromisoformat(zaman_str),
                sicaklik=sicakliklar[i],
                nispi_nem=nemler[i] if i < len(nemler) else None,
            ))
        return sonuc
    except (requests.RequestException, ValueError, KeyError):
        return []


def yas_hazne_sicakligi_tahmin_et(sicaklik: float, nispi_nem: float) -> float:
    """
    Stull (2011) yaklasik yas hazne sicakligi formulu - dogrudan bir
    yas hazne sensoru OLMADIGINDA hava sicakligi+nemden kaba bir tahmin
    uretir. Gercek bir yas hazne olcumunun yerini tutmaz, sadece
    sensor+Open-Meteo ikisi de yoksa hicbir sey gostermemek yerine
    kaba bir yon gostergesi saglar.

    Kaynak: Stull, R. (2011). "Wet-Bulb Temperature from Relative Humidity
    and Air Temperature." Journal of Applied Meteorology and Climatology.
    """
    import math

    T, RH = sicaklik, nispi_nem
    return (
        T * math.atan(0.151977 * math.sqrt(RH + 8.313659))
        + math.atan(T + RH)
        - math.atan(RH - 1.676331)
        + 0.00391838 * RH ** 1.5 * math.atan(0.023101 * RH)
        - 4.686035
    )
