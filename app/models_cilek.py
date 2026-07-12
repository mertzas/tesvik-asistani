"""
Çilek Üretim Yönetim Paneli - Veri Modelleri

Mevcut Organization (multi-tenant) yapisina baglanan, çilek uretimine ozel
operasyonel/finansal veri modelleri.

Tasarim ilkeleri:
- Her parsel (Parsel) bir Organization'a aittir (org_id FK) ve sera/acik
  tarla ayrimi yapar (ortam_tipi) - risk esikleri bu tipe gore degisir
  (sera nemi kontrol altinda oldugu icin acik tarlaya gore farkli
  esiklerle degerlendirilir, bkz. cilek_engine.py).
- Sensor verileri zaman serisi (SensorOkuma) olarak tutulur; "anlik durum"
  kartlari en son okumayi ceker. Sensor kopmesi/gecikmesi normal bir
  durumdur - bu yuzden tum "son deger" sorgulari None donebilir ve cagiran
  taraf (cilek_engine.py, cilek_panel.py) bunu acikca "veri_yok" durumuna
  cevirmelidir. Hicbir yerde sessizce 0 veya varsayilan bir sayisal deger
  KULLANILMAMALIDIR - yanlis guven duygusu don/hastalik riskinin
  kacirilmasi anlamina gelebilir (bkz. RiskSeviyesi.VERI_YOK).
- Ilaclama kayitlari (Ilaclama) PHI (Preharvest Interval) suresini tutar;
  hasat kilidi bu kayittan TURETILIR (bkz. cilek_engine.hasat_kilidi_durumu),
  ayri bir "kilitli mi" boolean alani tutulmaz - boylece bir kayit
  duzeltilirse (yanlis PHI girilmisse) kilit durumu her sorguda yeniden
  ve tutarli hesaplanir, eski/yanlis bir bayrakta takili kalmaz.
"""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Float, Boolean,
    ForeignKey, Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models import Base


class OrtamTipi(str, Enum):
    SERA = "sera"
    ACIK_TARLA = "acik_tarla"


class KaliteSinifi(str, Enum):
    SOFRALIK_PREMIUM = "sofralik_premium"
    SOFRALIK_STANDART = "sofralik_standart"
    SANAYILIK_RECELLIK = "sanayilik_recellik"


class SensorTipi(str, Enum):
    TOPRAK_NEMI = "toprak_nemi"                  # %
    TOPRAK_EC = "toprak_ec"                       # dS/m
    HAVA_SICAKLIGI = "hava_sicakligi"              # °C
    YAS_HAZNE_SICAKLIGI = "yas_hazne_sicakligi"    # °C (wet bulb - don erken uyari)
    NISPI_NEM = "nispi_nem"                        # %
    SERA_SIRKULASYON = "sera_sirkulasyon"          # m/s (fan/hava hareketi hizi)


# ============ PARSEL (merkezi baglanti noktasi) ============

class Parsel(Base):
    """Bir isletmeye ait tekil uretim alani (sera bolmesi veya acik tarla parseli)."""
    __tablename__ = "cilek_parseller"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True, nullable=False)

    ad = Column(String, nullable=False)  # "Sera 1 - A Blok" gibi
    ortam_tipi = Column(SQLEnum(OrtamTipi), default=OrtamTipi.ACIK_TARLA)
    alan_dekar = Column(Float, nullable=True)
    cesit = Column(String, nullable=True)  # "Albion", "Sabrina", "Fortuna" gibi cesit
    dikim_tarihi = Column(Date, nullable=True)
    aktif = Column(Boolean, default=True)

    # Bolgesel hava tahmini yedegi (Open-Meteo) icin konum - opsiyonel, girilmezse
    # sadece saha sensorlerine guvenilir, bolgesel yedek devre disi kalir.
    enlem = Column(Float, nullable=True)
    boylam = Column(Float, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sensor_okumalari = relationship("SensorOkuma", back_populates="parsel", cascade="all, delete-orphan")
    fertigasyon_tanklari = relationship("FertigasyonTank", back_populates="parsel", cascade="all, delete-orphan")
    sulama_donguleri = relationship("SulamaDongusu", back_populates="parsel", cascade="all, delete-orphan")
    ilaclamalar = relationship("Ilaclama", back_populates="parsel", cascade="all, delete-orphan")
    hasatlar = relationship("HasatKaydi", back_populates="parsel", cascade="all, delete-orphan")
    giderler = relationship("GiderKalemi", back_populates="parsel", cascade="all, delete-orphan")


# ============ 1. KRITIK TARIMSAL VERILER (sensor zaman serisi) ============

class SensorOkuma(Base):
    """Zaman serisi sensor verisi. Her okuma tek bir sensor tipine ve degere aittir."""
    __tablename__ = "cilek_sensor_okumalari"

    id = Column(Integer, primary_key=True, index=True)
    parsel_id = Column(Integer, ForeignKey("cilek_parseller.id"), index=True, nullable=False)

    sensor_tipi = Column(SQLEnum(SensorTipi), nullable=False, index=True)
    deger = Column(Float, nullable=False)
    birim = Column(String, nullable=True)
    olcum_zamani = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    kaynak = Column(String, nullable=True)  # sensor/cihaz id, "manuel" vs.

    parsel = relationship("Parsel", back_populates="sensor_okumalari")


# ============ 2. AKILLI SULAMA & FERTIGASYON ============

class TankTipi(str, Enum):
    AZOT = "azot"
    FOSFOR = "fosfor"
    POTASYUM = "potasyum"


class FertigasyonTank(Base):
    """NPK sivi gubre tanklari - doluluk takibi."""
    __tablename__ = "cilek_fertigasyon_tanklari"

    id = Column(Integer, primary_key=True, index=True)
    parsel_id = Column(Integer, ForeignKey("cilek_parseller.id"), index=True, nullable=False)

    tank_tipi = Column(SQLEnum(TankTipi), nullable=False)
    kapasite_litre = Column(Float, nullable=False)
    doluluk_litre = Column(Float, nullable=True)  # None = sensor okunamiyor
    son_guncelleme = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    parsel = relationship("Parsel", back_populates="fertigasyon_tanklari")


class SulamaDurumu(str, Enum):
    BEKLEMEDE = "beklemede"
    SULUYOR = "suluyor"
    TAMAMLANDI = "tamamlandi"
    HATA = "hata"


class SulamaDongusu(Base):
    """Otomatik sulama/fertigasyon dongu kaydi; bir sonraki donguye geri sayim buradan turetilir."""
    __tablename__ = "cilek_sulama_donguleri"

    id = Column(Integer, primary_key=True, index=True)
    parsel_id = Column(Integer, ForeignKey("cilek_parseller.id"), index=True, nullable=False)

    son_sulama_zamani = Column(DateTime, nullable=True)
    sonraki_sulama_zamani = Column(DateTime, nullable=True)
    durum = Column(SQLEnum(SulamaDurumu), default=SulamaDurumu.BEKLEMEDE)

    verilen_su_ph = Column(Float, nullable=True)
    verilen_su_ec = Column(Float, nullable=True)
    verilen_su_litre = Column(Float, nullable=True)

    parsel = relationship("Parsel", back_populates="sulama_donguleri")


# ============ 3. ZARARLI & HASTALIK / MRL-PHI TAKIBI ============

class Ilaclama(Base):
    """
    Yapilan ilaclama kaydi. Hasat kilidi (PHI) bu kayittaki
    uygulama_tarihi + phi_gun degerinden TURETILIR (bkz. cilek_engine.py);
    ayri bir "kilitli" alani YOKTUR - tutarlilik icin.
    """
    __tablename__ = "cilek_ilaclamalar"

    id = Column(Integer, primary_key=True, index=True)
    parsel_id = Column(Integer, ForeignKey("cilek_parseller.id"), index=True, nullable=False)

    ilac_adi = Column(String, nullable=False)
    etken_madde = Column(String, nullable=True)
    uygulama_tarihi = Column(DateTime, nullable=False)
    phi_gun = Column(Integer, nullable=False)  # Preharvest interval - urun etiketinden
    doz = Column(String, nullable=True)
    uygulayan = Column(String, nullable=True)
    hedef = Column(String, nullable=True)  # "Botrytis", "kirmizi orumcek" gibi

    parsel = relationship("Parsel", back_populates="ilaclamalar")


# ============ 4. ANLIK PAZAR & TICARI BORSA ============

class PazarKaynagi(str, Enum):
    HAL = "hal"
    ZINCIR_MARKET = "zincir_market"
    IHRACAT = "ihracat"


class PazarFiyati(Base):
    """Gunluk cilek fiyat/hacim verisi (hal, zincir market, ihracat kanali)."""
    __tablename__ = "cilek_pazar_fiyatlari"

    id = Column(Integer, primary_key=True, index=True)

    tarih = Column(Date, nullable=False, index=True)
    kaynak = Column(SQLEnum(PazarKaynagi), nullable=False)
    kalite_sinifi = Column(SQLEnum(KaliteSinifi), nullable=False)
    bolge = Column(String, nullable=True)  # "Antalya Hali" gibi

    fiyat_kg = Column(Float, nullable=False)
    hacim_kg = Column(Float, nullable=True)


# ============ 5. HASAT & SOGUK ZINCIR LOJISTIGI ============

class HasatKaydi(Base):
    """Toplanan urun kaydi - isci performansi ve toplam hasat miktari icin taban veri."""
    __tablename__ = "cilek_hasat_kayitlari"

    id = Column(Integer, primary_key=True, index=True)
    parsel_id = Column(Integer, ForeignKey("cilek_parseller.id"), index=True, nullable=False)

    tarih = Column(Date, nullable=False, index=True)
    isci_adi = Column(String, nullable=True)
    toplanan_kasa = Column(Float, nullable=False)  # kasa adedi (yarim kasa da olabilir)
    kasa_agirlik_kg = Column(Float, default=5.0)   # standart kasa agirligi (kg)
    sure_saat = Column(Float, nullable=True)
    saatlik_ucret = Column(Float, nullable=True)
    kalite_sinifi = Column(SQLEnum(KaliteSinifi), nullable=True)

    parsel = relationship("Parsel", back_populates="hasatlar")


class SogukZincirOkuma(Base):
    """Soguk hava deposu / soklama odasi sicaklik takibi (org genelinde, parsel bagimsiz olabilir)."""
    __tablename__ = "cilek_soguk_zincir_okumalari"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True, nullable=False)

    depo_adi = Column(String, nullable=False)  # "Soklama Odasi 1", "Soguk Depo A"
    sicaklik = Column(Float, nullable=True)
    hedef_sicaklik_min = Column(Float, default=0.0)
    hedef_sicaklik_max = Column(Float, default=2.0)  # cilek icin tipik 0-2°C
    olcum_zamani = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    parti_no = Column(String, nullable=True)


# ============ 6. MIKRO FINANSAL SAGLIK ============

class GiderKategorisi(str, Enum):
    FIDE = "fide"
    GUBRE = "gubre"
    ILAC = "ilac"
    MAZOT = "mazot"
    ISCILIK = "iscilik"
    SULAMA_ENERJI = "sulama_enerji"
    AMBALAJ = "ambalaj"
    DIGER = "diger"


class GiderKalemi(Base):
    """Parsel bazinda gider kaydi - birim maliyet ve nakit akisi hesaplarinin taban verisi."""
    __tablename__ = "cilek_gider_kalemleri"

    id = Column(Integer, primary_key=True, index=True)
    parsel_id = Column(Integer, ForeignKey("cilek_parseller.id"), index=True, nullable=False)

    kategori = Column(SQLEnum(GiderKategorisi), nullable=False)
    tutar = Column(Float, nullable=False)
    tarih = Column(Date, nullable=False, index=True)
    aciklama = Column(String, nullable=True)

    parsel = relationship("Parsel", back_populates="giderler")
