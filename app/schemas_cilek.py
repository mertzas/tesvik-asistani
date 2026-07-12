"""
Çilek Üretim Yönetim Paneli - Pydantic Şemaları

Onemli kural: sensor/hesaplama kaynakli TUM alanlar Optional'dir. Sensor
kopmesi, henuz veri girilmemis olmasi veya hesaplama icin yetersiz veri
(orn. hasat yoksa birim maliyet hesaplanamaz) gayet normal calisma
durumlaridir - bunlar hata degil, "veri_yok" RiskSeviyesi/durum olarak
modellenir ve frontend bunu ayri (gri) bir kart durumu olarak gosterir.
Hicbir response modeli, eksik veriyi gizlemek icin varsayilan 0/False
DEGERI ile doldurulmaz.
"""
from datetime import datetime, date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RiskSeviyesi(str, Enum):
    GUVENLI = "guvenli"      # yeşil
    RISKLI = "riskli"        # sarı
    KRITIK = "kritik"        # kırmızı
    VERI_YOK = "veri_yok"    # gri - sensör/veri kopukluğu, GÜVENLİ ile KARIŞTIRILMAMALI


# ============ ORTAK / PARSEL ============

class ParselCreate(BaseModel):
    ad: str
    ortam_tipi: str = "acik_tarla"
    alan_dekar: Optional[float] = None
    cesit: Optional[str] = None
    dikim_tarihi: Optional[date] = None
    enlem: Optional[float] = None
    boylam: Optional[float] = None


class ParselResponse(BaseModel):
    id: int
    ad: str
    ortam_tipi: str
    alan_dekar: Optional[float] = None
    cesit: Optional[str] = None
    dikim_tarihi: Optional[date] = None
    aktif: bool
    enlem: Optional[float] = None
    boylam: Optional[float] = None

    class Config:
        from_attributes = True


# ============ 1. KRİTİK TARIMSAL VERİLER ============

class SensorOkumaCreate(BaseModel):
    parsel_id: int
    sensor_tipi: str
    deger: float
    birim: Optional[str] = None
    kaynak: Optional[str] = None


class SensorKart(BaseModel):
    """Tek bir sensör değeri için gösterim kartı - anlık değer + tazelik + risk durumu."""
    sensor_tipi: str
    deger: Optional[float] = None
    birim: Optional[str] = None
    olcum_zamani: Optional[datetime] = None
    veri_yasi_dakika: Optional[float] = None
    bayat_mi: bool = False  # veri var ama eski (sensör muhtemelen koptu)
    risk_seviyesi: RiskSeviyesi = RiskSeviyesi.VERI_YOK
    mesaj: Optional[str] = None


class DonRiskiDurumu(BaseModel):
    risk_seviyesi: RiskSeviyesi
    hava_sicakligi: Optional[float] = None
    yas_hazne_sicakligi: Optional[float] = None
    veri_kaynagi: str = "sensor"  # "sensor" | "bolgesel_tahmin" - saha sensoru her zaman onceliklidir
    mesaj: str


class MantarRiskiDurumu(BaseModel):
    """Botrytis (gri küf) + külleme için birleşik risk skoru (0-100)."""
    risk_seviyesi: RiskSeviyesi
    skor: Optional[float] = None
    botrytis_bileseni: Optional[float] = None
    kulleme_bileseni: Optional[float] = None
    kullanilan_sicaklik: Optional[float] = None
    kullanilan_nem: Optional[float] = None
    veri_kaynagi: str = "sensor"
    mesaj: str


class ErkenUyariPaneli(BaseModel):
    """
    Open-Meteo SAATLIK TAHMIN verisiyle onumuzdeki 24-48 saat icin don ve
    hastalik riski on-gorusu. don_riski/mantar_riski (SensorKart tabanli)
    'su an ne durumdayiz' sorusuna cevap verirken, bu panel 'bu gece/yarin
    ne olabilir' sorusuna cevap verir - saha sensoru olsa BILE anlamlidir
    (sensor gelecegi bilemez), bu yuzden VERI_YOK/bolgesel_tahmin ayrimina
    tabi degildir; sadece parselin konumu (enlem/boylam) tanimliysa calisir.
    """
    kullanilabilir: bool
    saat_sayisi: int = 48
    don_riski_bekleniyor_mu: bool = False
    min_beklenen_sicaklik: Optional[float] = None
    min_sicaklik_zamani: Optional[datetime] = None
    en_yuksek_hastalik_riski_skoru: Optional[float] = None
    en_yuksek_risk_zamani: Optional[datetime] = None
    mesaj: str


# ============ 2. AKILLI SULAMA & FERTİGASYON ============

class TankDurumu(BaseModel):
    tank_tipi: str
    doluluk_yuzde: Optional[float] = None
    doluluk_litre: Optional[float] = None
    kapasite_litre: float
    risk_seviyesi: RiskSeviyesi
    son_guncelleme: Optional[datetime] = None


class SulamaDurumuKart(BaseModel):
    durum: Optional[str] = None
    sonraki_sulama_zamani: Optional[datetime] = None
    geri_sayim_dakika: Optional[float] = None
    verilen_su_ph: Optional[float] = None
    verilen_su_ec: Optional[float] = None
    mesaj: Optional[str] = None


class FertigasyonPaneli(BaseModel):
    tanklar: list[TankDurumu] = Field(default_factory=list)
    sulama: SulamaDurumuKart


class GubreDozOnerisiSchema(BaseModel):
    dikim_tarihi: Optional[date] = None
    gun_sayisi: Optional[int] = None
    evre: Optional[str] = None
    evre_aciklama: Optional[str] = None
    n_kg_da: Optional[float] = None
    p2o5_kg_da: Optional[float] = None
    k2o_kg_da: Optional[float] = None
    cao_kg_da: Optional[float] = None
    haftalik_uygulama_sikligi: Optional[int] = None
    dikkat: Optional[str] = None
    alan_dekar: Optional[float] = None
    toplam_n_kg: Optional[float] = None
    toplam_p2o5_kg: Optional[float] = None
    toplam_k2o_kg: Optional[float] = None
    toplam_cao_kg: Optional[float] = None
    notlar: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ============ 3. ZARARLI & HASTALIK / MRL-PHI ============

class HasatKilidiDurumu(BaseModel):
    kilitli: bool
    ilac_adi: Optional[str] = None
    uygulama_tarihi: Optional[datetime] = None
    serbest_kalma_tarihi: Optional[datetime] = None
    kalan_saat: Optional[float] = None
    mesaj: str


# ============ 4. PAZAR / BORSA ============

class PazarFiyatiCreate(BaseModel):
    tarih: date
    kaynak: str
    kalite_sinifi: str
    bolge: Optional[str] = None
    fiyat_kg: float
    hacim_kg: Optional[float] = None


class PazarFiyatNoktasi(BaseModel):
    tarih: date
    fiyat_kg: float
    hacim_kg: Optional[float] = None


class KaliteBazliTalep(BaseModel):
    kalite_sinifi: str
    ortalama_fiyat_kg: Optional[float] = None
    toplam_hacim_kg: Optional[float] = None


class PazarPaneli(BaseModel):
    guncel_fiyat_kg: Optional[float] = None
    guncel_fiyat_tarihi: Optional[date] = None
    trend: str = "veri_yok"  # yukselen | dusen | sabit | veri_yok
    son_7_gun: list[PazarFiyatNoktasi] = Field(default_factory=list)
    kalite_bazli_talep: list[KaliteBazliTalep] = Field(default_factory=list)
    mesaj: Optional[str] = None


# ============ 5. HASAT & SOĞUK ZİNCİR ============

class HasatKaydiCreate(BaseModel):
    parsel_id: int
    tarih: date
    isci_adi: Optional[str] = None
    toplanan_kasa: float
    kasa_agirlik_kg: float = 5.0
    sure_saat: Optional[float] = None
    saatlik_ucret: Optional[float] = None
    kalite_sinifi: Optional[str] = None


class IsciPerformansi(BaseModel):
    isci_adi: str
    toplanan_kg: float
    sure_saat: Optional[float] = None
    kasa_saat_hizi: Optional[float] = None
    iscilik_maliyeti: Optional[float] = None


class HasatPerformansiPaneli(BaseModel):
    bugunku_toplam_kg: float = 0.0
    bugunku_toplam_iscilik_maliyeti: Optional[float] = None
    isciler: list[IsciPerformansi] = Field(default_factory=list)
    mesaj: Optional[str] = None


class SogukZincirOkumaCreate(BaseModel):
    depo_adi: str
    sicaklik: float
    hedef_sicaklik_min: float = 0.0
    hedef_sicaklik_max: float = 2.0
    parti_no: Optional[str] = None


class SogukZincirKart(BaseModel):
    depo_adi: str
    sicaklik: Optional[float] = None
    hedef_sicaklik_min: float
    hedef_sicaklik_max: float
    risk_seviyesi: RiskSeviyesi
    olcum_zamani: Optional[datetime] = None
    mesaj: Optional[str] = None


# ============ 6. MİKRO FİNANSAL SAĞLIK ============

class GiderKalemiCreate(BaseModel):
    parsel_id: int
    kategori: str
    tutar: float
    tarih: date
    aciklama: Optional[str] = None


class IlaclamaCreate(BaseModel):
    parsel_id: int
    ilac_adi: str
    etken_madde: Optional[str] = None
    uygulama_tarihi: datetime
    phi_gun: int
    doz: Optional[str] = None
    uygulayan: Optional[str] = None
    hedef: Optional[str] = None


class FinansalSaglikPaneli(BaseModel):
    donem_baslangic: date
    donem_bitis: date
    toplam_gider: float = 0.0
    gider_dagilimi: dict[str, float] = Field(default_factory=dict)
    toplam_hasat_kg: float = 0.0
    birim_maliyet_kg: Optional[float] = None
    tahmini_gelir: Optional[float] = None
    net_kar_marji_yuzde: Optional[float] = None
    notlar: list[str] = Field(default_factory=list)


# ============ ANA PANEL (agregat - tek çağrıda tüm dashboard) ============

class CilekPaneliResponse(BaseModel):
    parsel_id: int
    parsel_ad: str
    ortam_tipi: str
    guncelleme_zamani: datetime

    kritik_uyarilar: list[str] = Field(default_factory=list)

    # 1. Kritik tarımsal veriler
    toprak_nemi: SensorKart
    toprak_ec: SensorKart
    don_riski: DonRiskiDurumu
    mantar_riski: MantarRiskiDurumu
    erken_uyari: ErkenUyariPaneli

    # 2. Sulama & Fertigasyon
    fertigasyon: FertigasyonPaneli
    gubre_onerisi: GubreDozOnerisiSchema

    # 3. Zararlı & Hastalık / PHI
    hasat_kilidi: HasatKilidiDurumu

    # 4. Pazar
    pazar: PazarPaneli

    # 5. Hasat & Soğuk Zincir
    hasat_performansi: HasatPerformansiPaneli
    soguk_zincir: list[SogukZincirKart] = Field(default_factory=list)

    # 6. Finansal Sağlık
    finansal_saglik: FinansalSaglikPaneli
