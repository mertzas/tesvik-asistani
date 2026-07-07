import os
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine, ForeignKey, Enum as SQLEnum, JSON, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./tesvik.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    APP_NAME: str = "Teşvik Asistanı SaaS"

    class Config:
        env_file = ".env"

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
    tesvil_tutari = Column(String, nullable=True)  # ₺100K - ₺500K range
    basin_orzu = Column(Float, nullable=True)  # % paylaşım
    uygunluk_kriterleri = Column(JSON, nullable=True)  # {calisanSayisi, ciroCinsi, endüstri}


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
