"""KOBİ ölçek sınıflandırması (mikro / küçük / orta / büyük).

Kaynak: Küçük ve Orta Büyüklükteki İşletmeler Yönetmeliği, 7 Ağustos 2025 tarihli
Resmî Gazete değişikliğiyle güncel hâli (KOSGEB duyurusu:
https://www.kosgeb.gov.tr/site/tr/genel/detay/9276/). Eşikler değişirse yalnızca
SINIFLAR tablosu güncellenmeli.

Kural: bir sınıfa girmek için çalışan sayısı eşiğin ALTINDA olmalı VE yıllık net
satış hasılatı ya da mali bilançodan HERHANGİ BİRİ limiti aşmamalı.

Sınırlar (bilerek):
  * Profilde mali bilanço yok; yalnızca yıllık ciro (net satış hasılatı yaklaşımı)
    var. Ciro limiti AŞMIYORSA sınıf kesindir (tek ölçüt yeter). Ciro limiti
    AŞIYORSA bilanço daha düşük olabileceğinden sonuç "kesin değil" döner.
  * Yönetmeliğin ortaklık/bağlılık (bağımsızlık) hesabı modellenmez.
"""
from __future__ import annotations

from dataclasses import dataclass

KAYNAK = "KOBİ Yönetmeliği, 7 Ağustos 2025 değişikliği (KOSGEB duyurusu)"

# sınıf -> (azami çalışan - kendisi hariç, yıllık net satış/bilanço limiti TL - dahil)
SINIFLAR: dict[str, tuple[int, float]] = {
    "mikro": (10, 10_000_000),
    "kucuk": (50, 100_000_000),
    "orta": (250, 1_000_000_000),
}
SIRA: dict[str, int] = {"mikro": 1, "kucuk": 2, "orta": 3, "buyuk": 4}
AD: dict[str, str] = {"mikro": "mikro işletme", "kucuk": "küçük işletme",
                      "orta": "orta büyüklükte işletme", "buyuk": "büyük işletme (KOBİ değil)"}


@dataclass(frozen=True)
class KobiSonucu:
    sinif: str | None        # "mikro" | "kucuk" | "orta" | "buyuk" | None (belirlenemedi)
    kesin: bool
    aciklama: str

    @property
    def kobi_mi(self) -> bool | None:
        """True/False yalnızca sınıf kesinse; aksi hâlde None."""
        if self.sinif is None or not self.kesin:
            return None
        return self.sinif != "buyuk"


def kobi_sinifi(calisan: int | None, ciro: float | None,
                bilanco: float | None = None) -> KobiSonucu:
    """İşletmenin ölçek sınıfı (saf fonksiyon)."""
    if calisan is None:
        return KobiSonucu(None, False, "çalışan sayısı bilinmiyor, ölçek belirlenemedi")
    if calisan < 0:
        raise ValueError("calisan negatif olamaz")
    if calisan >= SINIFLAR["orta"][0]:
        return KobiSonucu("buyuk", True, f"{calisan} çalışan ≥ {SINIFLAR['orta'][0]}: KOBİ değil")

    belirsiz_not = None
    for sinif, (azami_calisan, limit) in SINIFLAR.items():
        if calisan >= azami_calisan:
            continue
        olculer = [d for d in (ciro, bilanco) if d is not None]
        if any(d <= limit for d in olculer):
            limit_metin = f"{limit:,.0f}".replace(",", ".")
            return KobiSonucu(sinif, True, f"{calisan} çalışan, mali büyüklük ≤ {limit_metin} TL: {AD[sinif]}")
        if not olculer:
            return KobiSonucu(None, False, "ciro/bilanço bilinmiyor, ölçek belirlenemedi")
        belirsiz_not = sinif
    # Çalışan sayısına uyan hiçbir sınıfta mali ölçü limitin altında kalmadı.
    if bilanco is not None and ciro is not None:
        return KobiSonucu("buyuk", True, "mali büyüklük orta işletme limitini (1 milyar TL) aşıyor: KOBİ değil")
    return KobiSonucu("buyuk", False,
                      "yıllık ciro limiti aşıyor; mali bilanço daha düşükse sınıf değişebilir "
                      f"(en az {AD.get(belirsiz_not, 'orta büyüklükte işletme')} olarak değerlendirilmeli)")
