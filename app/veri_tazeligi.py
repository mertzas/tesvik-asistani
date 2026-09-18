"""
Veri tazeligi (freshness) raporu.

SORUN: Uygulama hal fiyatlarini, TUFE'yi ve sektor kar oranlarini kullaniciya
"guncel gercek" gibi sunuyordu ama bu verilerin ne zaman cekildigi hicbir yerde
gorunmuyordu. Olcum (2026-09-18): macro_indicators ve sector_benchmarks 69 gun
oncesine aitti - yani butce onerisindeki TUFE projeksiyonu iki aylik eski bir
enflasyon rakamiyla yapiliyordu ve kullanicinin bunu anlamasinin yolu yoktu.
Scraper'lar sessizce basarisiz oldugunda da hicbir uyari cikmiyordu.

Bu modul her veri kaynagi icin "en son ne zaman guncellendi" bilgisini ve
beklenen tazeleme araligina gore bir durum etiketi uretir.

Kullanim:
    from app.veri_tazeligi import tazelik_raporu, kaynak_tazeligi
    rapor = tazelik_raporu(db)                 # tum kaynaklar
    makro = kaynak_tazeligi(db, "makro")       # tek kaynak
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    HalFiyati,
    IhracatFiyati,
    MacroIndicator,
    SectorBenchmark,
    Tesvik,
)

logger = logging.getLogger(__name__)


# Durum esikleri: yas <= taze_gun ise "taze", <= uyari_gun ise "eskiyor",
# ustu "bayat". Esikler kaynagin GERCEK yayin sikligina gore secildi,
# hepsine ayni esigi uygulamak yaniltici olurdu: hal fiyatlari her is gunu
# yayinlanir, TUIK enflasyonu ayda bir, TCMB sektor bilancolari yilda bir.
@dataclass(frozen=True)
class KaynakTanimi:
    anahtar: str
    baslik: str
    model: type
    tarih_alani: str
    taze_gun: int
    uyari_gun: int
    aciklama: str
    # Veri bayatladiginda kullanicinin ne yapmasi gerektigi.
    tazeleme_komutu: str | None = None


KAYNAKLAR: tuple[KaynakTanimi, ...] = (
    KaynakTanimi(
        anahtar="hal_fiyatlari",
        baslik="Hal fiyatlari (HKS)",
        model=HalFiyati,
        tarih_alani="tarih",
        taze_gun=7,
        uyari_gun=30,
        aciklama="Ticaret Bakanligi Hal Kayit Sistemi gunluk toptan fiyatlari. "
                 "Hafta sonu ve resmi tatillerde yayin olmadigi icin 1-3 gunluk "
                 "gecikme normaldir.",
        tazeleme_komutu="python -m app.scrapers.hal_urun_fiyat",
    ),
    KaynakTanimi(
        anahtar="ihracat_fiyatlari",
        baslik="Ihracat referans fiyatlari",
        model=IhracatFiyati,
        tarih_alani="tarih",
        taze_gun=14,
        uyari_gun=45,
        aciklama="HKS Ihracat Fiyat Bulteni - gumruk beyaninda kullanilan "
                 "resmi referans fiyatlar.",
        tazeleme_komutu="python -m app.scrapers.hal_ihracat_fiyat",
    ),
    KaynakTanimi(
        anahtar="makro",
        baslik="Makro gostergeler (TUFE, faiz)",
        model=MacroIndicator,
        tarih_alani="guncelleme_tarihi",
        # TUIK enflasyonu her ayin basinda aciklanir; 45 gunu asmissa en az
        # bir yayin kacirilmis demektir.
        taze_gun=35,
        uyari_gun=70,
        aciklama="TUIK tuketici fiyat endeksi ve TCMB politika faizi. Butce "
                 "onerisindeki enflasyon projeksiyonu bu degerlere dayanir.",
        tazeleme_komutu="python -m app.scrapers.tuik_macro",
    ),
    KaynakTanimi(
        anahtar="sektor_benchmark",
        baslik="Sektor kar oranlari (TCMB)",
        model=SectorBenchmark,
        tarih_alani="guncelleme_tarihi",
        # TCMB Sektor Bilancolari YILDA BIR yayinlanir; burada 1 yillik
        # veri bayat degil, normaldir.
        taze_gun=400,
        uyari_gun=550,
        aciklama="TCMB Sektor Bilancolari'ndan net kar/net satis oranlari. "
                 "Kaynak yilda bir yayinlandigi icin bir yila kadar eski "
                 "olmasi beklenen durumdur.",
        tazeleme_komutu="python -m app.scrapers.tuik_macro",
    ),
    KaynakTanimi(
        anahtar="tesvikler",
        baslik="Tesvik kayitlari",
        model=Tesvik,
        tarih_alani="guncelleme_tarihi",
        taze_gun=30,
        uyari_gun=90,
        aciklama="KOSGEB/TUBITAK/KGF/Tarim Bakanligi program kayitlari. "
                 "Programlarin acilis-kapanis takvimi degistigi icin duzenli "
                 "tazelenmesi gerekir.",
        tazeleme_komutu="python -m app.scrapers.run_all",
    ),
)

_KAYNAK_INDEKS = {k.anahtar: k for k in KAYNAKLAR}


@dataclass
class Tazelik:
    anahtar: str
    baslik: str
    son_guncelleme: datetime | None
    yas_gun: int | None
    durum: str  # "taze" | "eskiyor" | "bayat" | "veri_yok"
    kayit_sayisi: int
    aciklama: str
    tazeleme_komutu: str | None = None
    uyari: str | None = None

    @property
    def sorunlu_mu(self) -> bool:
        return self.durum in ("bayat", "veri_yok")

    def sozluk(self) -> dict:
        return {
            "anahtar": self.anahtar,
            "baslik": self.baslik,
            "son_guncelleme": self.son_guncelleme.isoformat() if self.son_guncelleme else None,
            "yas_gun": self.yas_gun,
            "durum": self.durum,
            "kayit_sayisi": self.kayit_sayisi,
            "aciklama": self.aciklama,
            "tazeleme_komutu": self.tazeleme_komutu,
            "uyari": self.uyari,
        }


def _simdi() -> datetime:
    return datetime.now(timezone.utc)


def _yas_gun(deger: datetime | date | None) -> int | None:
    """Tarih alanlari veritabaninda hem DateTime hem Date olabiliyor
    (hal_fiyatlari.tarih bir Date, macro_indicators.guncelleme_tarihi bir
    DateTime). Ayrica SQLite'tan gelen DateTime'lar naive; UTC varsayiyoruz."""
    if deger is None:
        return None
    if isinstance(deger, datetime):
        if deger.tzinfo is None:
            deger = deger.replace(tzinfo=timezone.utc)
        return max(0, (_simdi() - deger).days)
    if isinstance(deger, date):
        return max(0, (_simdi().date() - deger).days)
    return None


def kaynak_tazeligi(db: Session, anahtar: str) -> Tazelik | None:
    tanim = _KAYNAK_INDEKS.get(anahtar)
    if tanim is None:
        return None
    return _olc(db, tanim)


def _olc(db: Session, tanim: KaynakTanimi) -> Tazelik:
    sutun = getattr(tanim.model, tanim.tarih_alani)
    try:
        en_son = db.query(func.max(sutun)).scalar()
        sayi = db.query(func.count()).select_from(tanim.model).scalar() or 0
    except Exception as e:
        # Tablo henuz goc edilmemis olabilir; rapor tek bir kaynak yuzunden
        # tamamen patlamamali.
        logger.warning("Tazelik olculemedi (%s): %s: %s", tanim.anahtar, type(e).__name__, e)
        return Tazelik(
            anahtar=tanim.anahtar, baslik=tanim.baslik, son_guncelleme=None,
            yas_gun=None, durum="veri_yok", kayit_sayisi=0,
            aciklama=tanim.aciklama, tazeleme_komutu=tanim.tazeleme_komutu,
            uyari="Veri tablosu okunamadi.",
        )

    yas = _yas_gun(en_son)

    if sayi == 0 or yas is None:
        durum = "veri_yok"
        uyari = "Bu kaynakta hic veri yok; ilgili toplayici hic calistirilmamis olabilir."
    elif yas <= tanim.taze_gun:
        durum, uyari = "taze", None
    elif yas <= tanim.uyari_gun:
        durum = "eskiyor"
        uyari = (f"Veri {yas} gunluk. Beklenen tazeleme araligi {tanim.taze_gun} gun; "
                 f"yakinda guncellenmeli.")
    else:
        durum = "bayat"
        uyari = (f"Veri {yas} gunluk ve beklenen {tanim.taze_gun} gunluk araligi "
                 f"asmis durumda. Bu kaynaga dayanan hesaplamalari eski veri "
                 f"uyarisiyla degerlendirin.")

    son = en_son if isinstance(en_son, datetime) else (
        datetime.combine(en_son, datetime.min.time(), tzinfo=timezone.utc)
        if isinstance(en_son, date) else None
    )

    return Tazelik(
        anahtar=tanim.anahtar, baslik=tanim.baslik, son_guncelleme=son,
        yas_gun=yas, durum=durum, kayit_sayisi=sayi,
        aciklama=tanim.aciklama, tazeleme_komutu=tanim.tazeleme_komutu,
        uyari=uyari,
    )


def tazelik_raporu(db: Session) -> list[Tazelik]:
    """Tum kaynaklarin tazelik durumu; en sorunlu olan basta."""
    sonuc = [_olc(db, t) for t in KAYNAKLAR]
    oncelik = {"veri_yok": 0, "bayat": 1, "eskiyor": 2, "taze": 3}
    sonuc.sort(key=lambda t: (oncelik.get(t.durum, 9), -(t.yas_gun or 0)))
    return sonuc


def genel_durum(rapor: list[Tazelik]) -> str:
    """Rapordaki en kotu durum - rozet/gosterge icin."""
    for seviye in ("veri_yok", "bayat", "eskiyor"):
        if any(t.durum == seviye for t in rapor):
            return seviye
    return "taze"
