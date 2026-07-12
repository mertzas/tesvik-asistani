import os
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, create_engine, ForeignKey, Enum as SQLEnum, JSON, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./tesvik.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_PRO: str = os.getenv("STRIPE_PRICE_PRO", "")
    STRIPE_PRICE_BUSINESS: str = os.getenv("STRIPE_PRICE_BUSINESS", "")
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")
    APP_NAME: str = "Teşvik Asistanı SaaS"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Database setup
if settings.DATABASE_URL.startswith("postgresql"):
    engine = create_engine(settings.DATABASE_URL)
else:
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Enums
class PlanType(str, Enum):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


# Organization (Multi-Tenant)
class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    plan = Column(SQLEnum(PlanType), default=PlanType.FREE)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    webhook_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    queries = relationship("Query", back_populates="organization", cascade="all, delete-orphan")


# User
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    role = Column(SQLEnum(UserRole), default=UserRole.MEMBER)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="users")


# Query History
class Query(Base):
    __tablename__ = "queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    question = Column(String)
    results = Column(JSON)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    organization = relationship("Organization", back_populates="queries")


# Incentive (Teşvik) - updated for future features
class Tesvik(Base):
    __tablename__ = "tesvikler"

    id = Column(Integer, primary_key=True, index=True)
    kurum = Column(String, index=True)
    baslik = Column(String, index=True)
    ozet = Column(Text)
    detay = Column(Text)
    hedef_kitle = Column(String)
    kaynak_url = Column(String, unique=True)
    guncelleme_tarihi = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # New fields for enhanced features
    kategori = Column(String, nullable=True)  # Ar-Ge, İnovasyon, İhracat, etc.
    baslama_tarihi = Column(DateTime, nullable=True)  # Program başlangıç tarihi
    bitis_tarihi = Column(DateTime, nullable=True)   # Deadline
    tesvil_tutari = Column(String, nullable=True)  # ₺100K - ₺500K range (metin)
    basin_orzu = Column(Float, nullable=True)  # % paylaşım
    uygunluk_kriterleri = Column(JSON, nullable=True)  # {calisanSayisi, ciroCinsi, endüstri}

    # Tutarı hesaplama: kullanıcının profil bilgisine göre tahmini destek tutarı
    tutari_min = Column(Float, nullable=True)  # TL cinsinden minimum
    tutari_max = Column(Float, nullable=True)  # TL cinsinden maksimum
    tutari_hesaplama_kriteri = Column(String, nullable=True)  # "dekar" | "calisan" | "ciro" | "saat" | "genel"
    tutari_hesaplama_formulu = Column(String, nullable=True)  # "Dekar başına ₺500-1000" gibi insan okunaklı açıklama

    # Başvuru süreci ve şartlar
    basvuru_sartlari = Column(JSON, nullable=True)  # ["Çiftçi olmalı", "Asgari 10 dekar", "İlk kuruluş 5 yıl içinde"]
    gerekli_belgeler = Column(JSON, nullable=True)  # ["Tapu", "Satış Belgesi", "Yıllık Muhasebe"]
    basvuru_yeri = Column(String, nullable=True)  # "İL Tarım Müdürlüğü" | "TKDK" | "Online"
    basvuru_suresi = Column(String, nullable=True)  # "30 gün" | "Sürekli" | "15 Eylül - 15 Ekim"
    destek_verilme_suresi = Column(String, nullable=True)  # "30-60 gün" | "2-3 ay"


# Financial Profile (isletme/ciftci finansal girdisi)
class FinancialProfile(Base):
    __tablename__ = "financial_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), unique=True, index=True)

    sektor = Column(String, index=True)  # tarim, imalat, perakende, hizmet, ihracat, arge...
    bolge = Column(String, nullable=True)  # il / bolge kodu
    calisan_sayisi = Column(Integer, nullable=True)
    yillik_ciro = Column(Float, nullable=True)
    hedefler = Column(JSON, nullable=True)  # ["yatirim", "ihracat", "arge", "istihdam", "makine", "sulama", "hayvan", "organik"]
    giderler = Column(JSON, nullable=True)  # {"stok": 100000, "reklam": 20000, "toplam": 550000, "personel": ...}
    ilk_yil_mi = Column(Boolean, nullable=True)  # arazi hazirligi/sera/ekipman gibi tek seferlik kurulus giderleri var mi

    # Tarim sektorune ozel ek alanlar (sektor != "tarim" ise bos kalir)
    arazi_buyuklugu_dekar = Column(Float, nullable=True)
    urun_turu = Column(String, nullable=True)  # "bugday", "nohut", "meyve", "sebze", "zeytin" ... (fiyat aramasi icin serbest metin)
    tarim_kategori = Column(String, nullable=True)  # "hayvancilik" | "sebze_meyve" | "tahil_baklagil" | "organik" | "sera" | "sulama_yatirimi" | "makinelestirme" | "genel" - yapilandirilmis secim, teshvik eslesmesi bunu kullanir

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization")


# Sector Benchmark (TUIK/TCMB tabanli makro-ekonomik sektor referanslari)
class SectorBenchmark(Base):
    __tablename__ = "sector_benchmarks"

    id = Column(Integer, primary_key=True, index=True)
    sektor = Column(String, unique=True, index=True)
    stok_maliyeti_oran_min = Column(Float)  # ciro icindeki min pay
    stok_maliyeti_oran_max = Column(Float)
    reklam_oran_min = Column(Float)
    reklam_oran_max = Column(Float)
    net_kar_orani = Column(Float, nullable=True)  # Net Kar / Net Satislar orani (TCMB Sektor Bilancolari)
    kaynak = Column(String, nullable=True)  # "TUIK sektor anketi 2025" gibi
    guncelleme_tarihi = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Macro Indicator (TUIK/TCMB genel gostergeler)
class MacroIndicator(Base):
    __tablename__ = "macro_indicators"

    id = Column(Integer, primary_key=True, index=True)
    anahtar = Column(String, unique=True, index=True)  # "yillik_enflasyon", "tcmb_politika_faizi"
    deger = Column(Float)
    birim = Column(String, nullable=True)  # "%"
    kaynak = Column(String, nullable=True)
    guncelleme_tarihi = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Tarim Urunleri Ihracat Fiyati (T.C. Ticaret Bakanligi Hal Kayit Sistemi
# "Ihracat Fiyat Bulteni" - gumruk/ihracat beyani icin resmi referans fiyat).
# Cilek'in aksine (bkz. app/models_cilek.py PazarFiyati) bu bulten cilek
# icermiyor ama ~40 baska urun (domates, elma, biber, kayisi vb.) icin
# gercek gunluk veri sagliyor - bkz. app/scrapers/hal_ihracat_fiyat.py.
class IhracatFiyati(Base):
    __tablename__ = "ihracat_fiyatlari"

    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date, nullable=False, index=True)
    urun_adi = Column(String, nullable=False, index=True)  # "DOMATES" gibi, HKS'nin buyuk harfli adi
    urun_cinsi = Column(String, nullable=True)  # "BİBER DOLMALIK" gibi alt tur
    urun_turu = Column(String, nullable=True)  # Geleneksel(Konvansiyonel) / İyi Tarım / Organik Tarım
    fiyat_kg = Column(Float, nullable=False)
    miktar_kg = Column(Float, nullable=True)


# Genel Hal Fiyati (T.C. Ticaret Bakanligi Hal Kayit Sistemi "Fiyat
# Detaylari" gunluk bulteni - https://www.hal.gov.tr/Sayfalar/
# FiyatDetaylari.aspx). Cilek'e ozel PazarFiyati/KaliteSinifi modelinden
# (bkz. app/models_cilek.py, cilek_engine.py paneline bagli) FARKLI olarak
# bu tablo, hedef urun listesine (bkz. app/scrapers/hal_urun_fiyat.py
# HEDEF_URUNLER) giren HERHANGI bir urun icin genel amacli kullanilir -
# suan MUZ, ileride baska urunler eklenebilir.
class HalFiyati(Base):
    __tablename__ = "hal_fiyatlari"

    id = Column(Integer, primary_key=True, index=True)
    tarih = Column(Date, nullable=False, index=True)
    urun_adi = Column(String, nullable=False, index=True)  # "MUZ" gibi
    urun_cinsi = Column(String, nullable=True)  # "MUZ YERLİ(ANAMUR)" gibi
    urun_turu = Column(String, nullable=True)  # Geleneksel(Konvansiyonel) / İyi Tarım / Organik Tarım
    fiyat_kg = Column(Float, nullable=False)
    hacim_kg = Column(Float, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seen_keys(db, kurum: str) -> tuple[set[str], set[str]]:
    """Bir kurum icin var olan (kaynak_url kumesi, normallestirilmis baslik
    kumesi) dondurur. Ayni program farkli URL/slug altinda tekrar
    listelendiginde baslik uzerinden de dedup yapabilmek icin kullanilir."""
    rows = db.query(Tesvik.kaynak_url, Tesvik.baslik).filter(Tesvik.kurum == kurum).all()
    urls = {u for (u, _) in rows if u}
    titles = {" ".join(b.lower().split()) for (_, b) in rows if b}
    return urls, titles


def normalize_title(baslik: str) -> str:
    return " ".join(baslik.lower().split())
