import os
from pathlib import Path
import logging
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from sqlalchemy import Column, Integer, String, Text, DateTime, Date, create_engine, ForeignKey, Enum as SQLEnum, JSON, Boolean, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# app.sifreleme, settings'i FONKSIYON ICINDE ice aktarir; bu yuzden
# burada modul seviyesinde almak dongusel import yaratmaz.
from app.sifreleme import SifreliMetin
from pydantic_settings import BaseSettings

PROJE_KOKU = Path(__file__).resolve().parent.parent


def sqlite_url_mutlak(url: str) -> str:
    """Goreli sqlite yolunu CALISMA DIZININE gore degil PROJE KOKUNE gore cozer.

    Neden: 'sqlite:///./x.db' calisma dizinine baglidir; uygulama baska bir klasorden
    baslatilinca (2026-07-09'da ana dizinden) o klasorde bos bir veritabani olusuyordu.
    Bellek ici ('sqlite://'), mutlak yol ve sqlite disi (postgresql vb.) adresler aynen kalir.
    """
    onek = "sqlite:///"
    if not url.startswith(onek):
        return url
    yol = url[len(onek):]
    if not yol or yol.startswith(":memory:"):
        return url
    p = Path(yol)
    # Windows'ta '/abs' kokludur ama is_absolute() False doner; hepsini mutlak say: '/abs', 'C:/abs'
    if p.is_absolute() or yol.startswith(("/", "\\")) or (len(yol) > 1 and yol[1] == ":"):
        return url
    return onek + (PROJE_KOKU / p).resolve().as_posix()


class Settings(BaseSettings):
    # Varsayilan, gercek veritabanidir (.env.example ile ayni): data/tesvikler.db
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/tesvikler.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7  # denetim 2026-10-07: 30 gündü; iptal mekanizması olmadığı için kısaltıldı
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_PRO: str = os.getenv("STRIPE_PRICE_PRO", "")
    STRIPE_PRICE_BUSINESS: str = os.getenv("STRIPE_PRICE_BUSINESS", "")
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")
    APP_NAME: str = "Teşvik Asistanı SaaS"
    # CORS: virgülle ayrılmış izinli origin listesi. Boşsa APP_URL + yerel geliştirme
    # adresleri kullanılır. Denetim 2026-10-07: allow_origins=["*"] + allow_credentials=True idi.
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "")
    # Yalnızca yerel geliştirme: varsayılan SECRET_KEY ile açılışa izin verir.
    ALLOW_INSECURE_SECRET: bool = os.getenv("ALLOW_INSECURE_SECRET", "false").lower() == "true"
    # Hız sınırı sayaçları: boşsa süreç içi (tek işçi); doluysa Redis (çok işçi/instance).
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    # Zamanlanmış scraper işleri (çok işçili dağıtımda yalnızca kilidi alan işçi çalıştırır).
    SCHEDULER_ENABLED: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    # E-posta (app/email.py): boşsa e-posta gönderimi kapalı. Denetim 2026-10-07: email.py
    # settings.SMTP_* okuyordu ama alanlar tanımlı değildi (AttributeError).
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587") or 587)
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    # Doğrulama zorunlu kayıt (SMTP kurulunca açılır). Açıkken: kayıt yanıtı hesap var/yok fark etmeksizin
    # aynıdır (e-posta numaralandırma yok), kayıt belirteç vermez, doğrulanmamış hesap giriş yapamaz ve
    # etkinleştirme bağlantı + parola ister (hesabın önceden ele geçirilmesine karşı). Kapalıyken eski akış:
    # kayıt hemen oturum açar, var olan e-postaya 400 döner.
    KAYIT_EPOSTA_DOGRULAMA_ZORUNLU: bool = os.getenv("KAYIT_EPOSTA_DOGRULAMA_ZORUNLU", "false").lower() == "true"
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    # Harici hata izleme (app/hata_izleme.py). Boşsa kapalı. KVKK: AB bölgesi DSN'i tercih edin.
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_ORTAM: str = os.getenv("SENTRY_ORTAM", "production")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

    # İKAS Admin App entegrasyonu - client_id/secret İKAS Builders Dashboard'da
    # uygulama kaydi yapilip test magazasi atandiktan sonra elde edilir.
    # Bos ise IKAS_MOCK_MODE zorunlu olarak True kabul edilir (bkz. app/ikas_integration.py).
    IKAS_CLIENT_ID: str = os.getenv("IKAS_CLIENT_ID", "")
    IKAS_CLIENT_SECRET: str = os.getenv("IKAS_CLIENT_SECRET", "")
    IKAS_SCOPE: str = os.getenv("IKAS_SCOPE", "read_orders read_products")
    IKAS_MOCK_MODE: bool = os.getenv("IKAS_MOCK_MODE", "true").lower() == "true"
    # İKAS yönetim paneli uygulamayı iframe içinde açar; bu kökenler giriş/panel/ikas sayfalarını çerçeveleyebilir.
    # Boş bırakılırsa hiçbir sayfa çerçevelenemez (frame-ancestors 'none').
    IKAS_CERCEVE_KAYNAKLARI: str = os.getenv("IKAS_CERCEVE_KAYNAKLARI", "https://*.myikas.com")
    # İKAS'a kayıtlı uygulama adresi (Next.js kabuğu ikas-app/ ayrı alan adındaysa onun adresi). Callback ve
    # webhook adresleri bundan üretilir; boşsa APP_URL.
    IKAS_UYGULAMA_URL: str = os.getenv("IKAS_UYGULAMA_URL", "")

    class Config:
        # Proje kokune gore: baska bir calisma dizininden baslatilsa da .env bulunur.
        env_file = str(PROJE_KOKU / ".env")
        extra = "ignore"

settings = Settings()
settings.DATABASE_URL = sqlite_url_mutlak(settings.DATABASE_URL)

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

    # KVKK: yapay zeka danismani kullanildiginda isletme profili (sektor,
    # bolge, calisan sayisi, ciro, hedefler, tarim kategorisi, urun turu,
    # arazi buyuklugu, NACE kodu) yanit uretilmesi icin Anthropic'e (ABD) gonderiliyor.
    # ozellikler (kadin/genc girisimci vb.) BILEREK gonderilmez.
    # Bu YURT DISINA AKTARIM'dir ve acik riza gerektirir.
    #
    # Riza KAYIT SIRASINDA ZORUNLU TUTULMUYOR: KVKK acik rizanin "ozgur
    # iradeyle" verilmesini arar, hizmete erisimin sartina baglanamaz.
    # Riza yoksa uygulama calismaya devam eder, yalnizca AI danisman yerine
    # liste formati kullanilir (bkz. app/main.py sor()).
    ai_yurtdisi_riza = Column(Boolean, default=False)
    ai_riza_tarihi = Column(DateTime, nullable=True)
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
    # E-posta doğrulama (Aşama E): NULL = doğrulanmadı. Giriş doğrulamaya BAĞLI DEĞİL (ürün kararı bekliyor).
    email_dogrulama_zamani = Column(DateTime, nullable=True)
    # JWT iptali: belirteç "sv" talebinde bu sürümü taşır; parola sıfırlanınca veya "tüm oturumları kapat"
    # denince artırılır ve önceki tüm belirteçler geçersizleşir (Denetim 2 / kod listesi, 2026-10-08).
    oturum_surumu = Column(Integer, nullable=False, default=0, server_default="0")

    organization = relationship("Organization", back_populates="users")


class HesapBelirteci(Base):
    """Parola sıfırlama / e-posta doğrulama tek kullanımlık belirteçleri. Ham belirteç yalnızca e-postayla
    gider; veritabanında SHA-256 özeti tutulur (veritabanı sızsa da bağlantı üretilemez)."""
    __tablename__ = "hesap_belirtecleri"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    amac = Column(String(30), nullable=False)  # "sifre_sifirlama" | "eposta_dogrulama"
    belirtec_ozeti = Column(String(64), unique=True, index=True, nullable=False)
    olusturma = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    bitis = Column(DateTime, nullable=False)
    kullanildi = Column(DateTime, nullable=True)


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
    # onupdate SART: default yalnizca INSERT'te uygulanir. Onupdate olmadan
    # var olan bir kaydin tazelenmesi tarihi guncellemiyordu ve veri
    # tazeligi gostergesi basarili tazelemeden sonra bile "bayat" gosteriyordu.
    guncelleme_tarihi = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                               onupdate=lambda: datetime.now(timezone.utc), index=True)

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
    # Denetlenmiş kontrol listesi (2026-10-10, scripts/fix_veri_2026_10_10_kontrol_listesi_tur19.py):
    # [{tur: sart|belge|adim|kural|bilgi, metin, alinti, kaynak_url, kaynak_tarihi, dogrulandi}]. Boşsa liste
    # basvuru_sartlari/gerekli_belgeler/basvuru_yeri alanlarından eski yolla üretilir (app/basvuru_listesi.py).
    kontrol_listesi = Column(JSON, nullable=True)
    # proje | kredi | faiz_destegi | kefalet | bildirim_prim | uretim_odeme | belge_etuys | gider_on_onay | hisse_fon |
    # gotuyu_hibe | diger (docs/olcum/2026-10-09-uygunluk/KRITER_SEMASI.md); taslak bölümünü belirler.
    basvuru_bicimi = Column(String(20), nullable=True)

    # Programin hala basvuruya acik olup olmadigi - KGF/TUBITAK kayitlarinin
    # cogu "gecmis-programlar" (artik kapali) sayfalarindan cekilmisti ve
    # bu ayrim hic yapilmamisti; kullaniciya kapanmis bir programi "hala
    # basvurabilirsiniz" gibi sunmamak icin eklendi.
    nace_kayitlari = relationship("TesvikNace", cascade="all, delete-orphan", lazy="select")
    # Dönemsel başvuru çağrıları (app/cagrilar.py); kapanışa göre sıralı.
    cagrilar = relationship("TesvikCagrisi", cascade="all, delete-orphan", lazy="select",
                            order_by="TesvikCagrisi.kapanis")
    # NACE kapsam kararı (LLM): satırı olmayan YATAY/BELIRSIZ kararları da kalıcı olsun
    # ve her koşuda tekrar API'ye gidilmesin diye. "YATAY" + güven >= eşik -> atlanır.
    nace_kapsam_turu = Column(String(20), nullable=True)     # YATAY | SEKTOR_KISITLI | BELIRSIZ
    nace_kapsam_guven = Column(Float, nullable=True)
    nace_kapsam_kaynak = Column(String(30), nullable=True)   # "llm_extraction" | "elle"
    nace_kapsam_tarihi = Column(DateTime, nullable=True)
    aktif_mi = Column(Boolean, nullable=True)  # None = henuz kontrol edilmedi, True/False = teyit edildi
    durum_notu = Column(String, nullable=True)  # "2023'te kapanmis, KGF 'gecmis programlar' sayfasinda listeleniyor" gibi


# Kurum iletisim rehberi - dogrulanmis resmi telefon/adres bilgileri.
# Tesvik.kurum alaniyla ayni degeri tasir (orn. "KOSGEB"); tek tek tesvik
# kaydina degil, kuruma bagli oldugu icin ayri bir tablo (bir kurumun
# 79 tesvik kaydi olabilir, telefon numarasi hepsinde aynidir).
#
# ONEMLI: Buradaki her satir gercek resmi kaynaktan (kurumun kendi
# iletisim sayfasi) WebFetch ile TEK TEK dogrulanarak eklenmistir -
# hicbir telefon numarasi/adres LLM egitim verisinden veya tahminden
# uydurulmamistir. dogrulama_tarihi ve kaynak_url alanlari, bu bilginin
# ne zaman ve nereden teyit edildigini izlenebilir kilar - kurumlar
# numara degistirebilir, bu yuzden "dogrulama_tarihi" eski ise tekrar
# teyit edilmelidir.
class KurumIletisim(Base):
    __tablename__ = "kurum_iletisim"

    id = Column(Integer, primary_key=True, index=True)
    kurum = Column(String, unique=True, index=True, nullable=False)  # "KOSGEB", "TUBITAK", "KGF", "Tarım Bakanlığı"
    kurum_tam_ad = Column(String, nullable=True)

    cagri_merkezi_no = Column(String, nullable=True)  # "444 1 567" gibi ulusal cagri merkezi
    genel_merkez_no = Column(String, nullable=True)   # "0 312 595 28 00" gibi santral
    calisma_saatleri = Column(String, nullable=True)

    adres = Column(String, nullable=True)
    web_sitesi = Column(String, nullable=True)
    eposta = Column(String, nullable=True)

    kaynak_url = Column(String, nullable=False)  # dogrulamanin yapildigi resmi sayfa
    dogrulama_tarihi = Column(Date, nullable=False)  # bu bilginin ne zaman teyit edildigi


# Il bazli Tarim ve Orman Il Mudurlugu iletisim rehberi (81 il).
#
# ONEMLI - IKI FARKLI GUVEN SEVIYESI VAR:
#   url_dogrulandi=True  -> bu ilin /Iletisim sayfasi gercekten WebFetch ile
#                            acilip telefon/adres TEK TEK teyit edildi.
#   url_dogrulandi=False -> sadece URL SEKLI (https://{il}.tarimorman.gov.tr/Iletisim)
#                            dogrulanan 13 ilden gozlemlenen TUTARLI bir
#                            desene gore uretildi; bu ilin sayfasi henuz
#                            acilip icerigi teyit edilmedi. Bu satirlarda
#                            telefon/adres BILEREK BOS birakilmistir -
#                            "muhtemelen dogru" bir numara yazmak yerine
#                            kullaniciyi dogrudan resmi linke yonlendiriyoruz.
# Plaka kodu (il_kodu) TC il plaka kodlarindan alinmistir, ayrica dogrulama
# gerektirmez (kamuya acik, degismeyen standart bir liste).
class IlTarimMudurlugu(Base):
    __tablename__ = "il_tarim_mudurlugu"

    id = Column(Integer, primary_key=True, index=True)
    il_kodu = Column(Integer, unique=True, index=True, nullable=False)  # 1-81 plaka kodu
    il_adi = Column(String, unique=True, index=True, nullable=False)

    telefon = Column(String, nullable=True)  # url_dogrulandi=False ise NULL
    adres = Column(String, nullable=True)
    eposta = Column(String, nullable=True)  # "{il}@tarimorman.gov.tr" - deseni tum dogrulanan illerde tutarli

    kaynak_url = Column(String, nullable=False)
    url_dogrulandi = Column(Boolean, nullable=False, default=False)
    dogrulama_tarihi = Column(Date, nullable=True)  # url_dogrulandi=True ise dolu


# Il bazli KOSGEB Mudurlugu iletisim rehberi (81 il, TAMAMI dogrulandi).
#
# IlTarimMudurlugu'ndan farkli olarak buradaki TUM 81 il, KOSGEB'in kendi
# "mudurluktekil?ID={plaka}" endpoint'i tek tek WebFetch ile cekilerek
# 2026-07-12 tarihinde dogrulandi - deseni tahmin edip URL uretmedik,
# gercekten her ilin sayfasi acildi. Bazi buyuk illerin (Ankara, Istanbul,
# Izmir) birden fazla musdurlugu var; ek_mudurlukler alani varsa diger
# musdurluk(ler)i JSON liste olarak tutar, ana kayit ilk/en genel musdurluk.
class IlKosgebMudurlugu(Base):
    __tablename__ = "il_kosgeb_mudurlugu"

    id = Column(Integer, primary_key=True, index=True)
    il_kodu = Column(Integer, unique=True, index=True, nullable=False)  # 1-81 plaka kodu
    il_adi = Column(String, unique=True, index=True, nullable=False)

    mudurluk_adi = Column(String, nullable=False)
    telefon = Column(String, nullable=False)
    adres = Column(String, nullable=False)
    eposta = Column(String, nullable=True)

    ek_mudurlukler = Column(JSON, nullable=True)  # [{"ad":..., "telefon":..., "adres":...}, ...]

    kaynak_url = Column(String, nullable=False)
    dogrulama_tarihi = Column(Date, nullable=False)


# Ikas magaza baglantisi (OAuth2 Authorization Code Flow ile alinan token).
#
# Endpoint/alan adlari @ikas/admin-api-client SDK'sinin (npm, versiyon
# 2.1.0) kendi unit test dosyalarindan ve kaynak kodundan dogrulanmistir
# (2026-07-12) - resmi ikas.dev/builders.ikas.com dokumantasyonu bazi
# detaylari (ozellikle authorize taban URL'i) acikca vermiyordu, bu yuzden
# SDK'nin derlenmis JS kaynagi (oauth/index.js) tek tek okunarak teyit
# edildi:
#   - OAuth taban URL: https://{storeName}.myikas.com/api/admin/oauth
#   - Authorize:        {taban}/authorize?client_id=...&redirect_uri=...&scope=...&state=...
#   - Token exchange:   POST {taban}/token (x-www-form-urlencoded,
#                        grant_type=authorization_code|refresh_token|client_credentials)
#   - GraphQL Admin API: https://api.myikas.com/api/v2/admin/graphql
#                        (Authorization: Bearer {access_token})
#
# GERCEK client_id/client_secret ISE HENUZ YOK - bunlar ancak İKAS
# Builders Dashboard'da uygulama kaydi yapilip bir test magazasi
# atandiktan sonra elde edilebilir (bkz. proje notlari). Bu tablo ve
# ilgili OAuth akisi o noktaya kadar TEST/MOCK modunda calisir.
class IkasBaglanti(Base):
    __tablename__ = "ikas_baglanti"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), unique=True, index=True)

    store_name = Column(String, nullable=False)  # "{storeName}.myikas.com" - alt alan adi
    # SIFRELI sutunlar: bu iki anahtar kullanicinin magaza verisine erisim
    # saglar ve veritabaninda ACIK METIN duruyordu (KVKK metni yazilirken
    # tespit edildi, 2026-09-27). SifreliMetin diskte sifreli tutar,
    # uygulama kodu duz metin gorur - boylece bir cagri yerinde sifrelemeyi
    # unutmak mumkun degil. Mevcut sifresiz kayitlar icin:
    # scripts/sifrele_mevcut_tokenlar.py
    access_token = Column(SifreliMetin, nullable=True)
    refresh_token = Column(SifreliMetin, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    scope = Column(String, nullable=True)  # "read_orders read_products" gibi bosluk ayrilmis

    oauth_state = Column(String, nullable=True)  # CSRF korumasi icin - authorize->callback arasi gecici
    baglanti_durumu = Column(String, default="beklemede")  # "beklemede" | "bagli" | "hata" | "koptu"

    son_senkron_zamani = Column(DateTime, nullable=True)
    son_senkron_hata = Column(String, nullable=True)

    # İKAS App Store kurulumu (2026-10-08): me.id = authorizedAppId (imzalı açılış ve webhook bunu taşır),
    # getMerchant.id = merchantId. Kurulumla gelen (org_id'siz) satır callback'te kuruluşa bağlanır.
    authorized_app_id = Column(String(64), nullable=True, index=True)
    merchant_id = Column(String(64), nullable=True, index=True)
    son_ozet = Column(JSON, nullable=True)  # EslemeSonucu.gostergeler(): ciro, döviz, yurt dışı teslimat
    # Webhook olayı kısa aralıkla gelirse tam senkron ertelenir; panel açılınca tamamlanır (bkz. ikas_panel).
    senkron_bekliyor = Column(Boolean, nullable=False, default=False, server_default="0")
    webhook_kaydi = Column(String(300), nullable=True)  # "kayitli" ya da saveWebhook hata metni

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization")


# Financial Profile (isletme/ciftci finansal girdisi)
class TesvikNace(Base):
    """Bir teşvikin kapsadığı NACE önekleri (çoktan çoğa; bkz. app/nace_hiyerarsi.py).

    nace_prefix standart biçimdedir: kısım harfi ("C") veya noktalı rakam
    ("10", "10.71"). Önek sorguları indeksli sütun üzerinden yapılır."""
    __tablename__ = "tesvik_nace_association"
    __table_args__ = (UniqueConstraint("tesvik_id", "nace_prefix", name="uq_tesvik_nace"),)

    id = Column(Integer, primary_key=True)
    tesvik_id = Column(Integer, ForeignKey("tesvikler.id", ondelete="CASCADE"), nullable=False, index=True)
    nace_prefix = Column(String(10), nullable=False, index=True)
    kaynak = Column(String(60), nullable=False, default="elle")  # "elle" | "otomatik:..." | "llm_extraction"
    # True: program bu kolu AÇIKÇA dışlıyor ("imalat, ancak tütün (12) hariç").
    # Dışlama satırı kapsamı genişletmez; eşleşmede işletmeyi eler.
    haric_mi = Column(Boolean, nullable=False, default=False, server_default="0")


class TesvikCagrisi(Base):
    """Bir programın dönemsel başvuru çağrısı (2026-10-08). Program (Tesvik) sürekli bir destek türüdür; KOSGEB,
    TÜBİTAK ve kalkınma ajanslarında başvuru ise "2026/2. dönem" gibi tarihli çağrılarla açılır. Tarih hatırlatıcısı ve
    "son başvuru" gösterimi bu tablodan üretilir (app/cagrilar.py). Her satır resmi duyurudan doğrulanır: kaynak_url ve
    dogrulama_tarihi zorunlu; tahmini tarih yazılmaz (bilinmeyen kapanış NULL kalır)."""
    __tablename__ = "tesvik_cagrilari"
    __table_args__ = (UniqueConstraint("tesvik_id", "ad", name="uq_tesvik_cagri_ad"),)

    id = Column(Integer, primary_key=True)
    tesvik_id = Column(Integer, ForeignKey("tesvikler.id", ondelete="CASCADE"), nullable=False, index=True)
    ad = Column(String(200), nullable=False)          # "2026/2. Başvuru Dönemi", "2026 Yılı Mali Destek Programı"
    acilis = Column(Date, nullable=True)
    kapanis = Column(Date, nullable=True, index=True)  # son başvuru günü (dahil)
    on_kayit_son = Column(Date, nullable=True)         # ön kayıt / kuruluş başvurusu son günü (varsa yeni başvuranın son günü)
    kaynak_url = Column(String, nullable=False)
    dogrulama_tarihi = Column(Date, nullable=False)
    notlar = Column(Text, nullable=True)              # "Kapanış saati 18:00", "ön başvuru zorunlu" gibi duyurudaki ayrıntı


class BasvuruTakibi(Base):
    """Kullanıcının bir teşvik için başvuru kontrol listesindeki işaretleri (app/basvuru_listesi.py).

    Maddeler kaydın şart/belge/başvuru yeri alanlarından üretilir; burada yalnızca işaretlenen madde anahtarları
    tutulur. Kayıt metni değişirse eski anahtarlar okuma sırasında düşer (yanlış madde işaretli görünmez)."""
    __tablename__ = "basvuru_takipleri"
    __table_args__ = (UniqueConstraint("org_id", "tesvik_id", name="uq_basvuru_takibi_org_tesvik"),)

    id = Column(Integer, primary_key=True)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    tesvik_id = Column(Integer, ForeignKey("tesvikler.id"), nullable=False, index=True)
    isaretli = Column(JSON, nullable=False, default=list)
    olusturma = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    guncelleme = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    # Yapay zekâ ile üretilen başvuru ön taslağı (app/basvuru_taslagi.py); tekrar ücret ödenmesin diye saklanır.
    taslak = Column(Text, nullable=True)
    taslak_tarihi = Column(DateTime, nullable=True)
    taslak_model = Column(String(60), nullable=True)
    # Taslak sihirbazı cevapları (proje, gerekçe, faaliyetler, bütçe, oran, çıktılar; app/sablon_taslak.py)
    taslak_cevaplar = Column(JSON, nullable=True)
    # Şartlara verilen cevaplar {madde anahtarı: "evet" | "hayir" | "bilmiyorum"}; belge/adım işaretlerinden ayrı.
    uygunluk_cevaplari = Column(JSON, nullable=True)


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
    nace_kodu = Column(String(10), nullable=True, index=True)  # standart biçim: "C" | "10" | "10.71" (bkz. app/nace_hiyerarsi.py)
    # Girişim modu / HUKS (bkz. app/girisim.py)
    sirket_turu = Column(String(20), nullable=True)   # yok | sahis | limited | anonim | kooperatif
    kurulus_tarihi = Column(Date, nullable=True)
    trl = Column(Integer, nullable=True)              # Teknoloji hazırlık seviyesi 1-9
    # Uygunluk alanları (2026-10-10, isteğe bağlı; boşsa eleme yapılmaz — app/matching.uygunluk_engeli):
    kurucu_yasi = Column(Integer, nullable=True)      # işletme sahibi / en az %50 hissedarın yaşı
    baska_sirkette_ortak = Column(Boolean, nullable=True)  # başka bir şirkette ortaklık (BiGG/1812 yasağı)
    sertifikalar = Column(JSON, nullable=True)        # ["organik_sertifika", "iyi_tarim_sertifikasi"] ya da ["hicbiri"]
    ozellikler = Column(JSON, nullable=True)  # hedef kitle etiketleri: ["kadin_girisimci", "savunma_sanayii", ...] (bkz. app/match_adapter.py)
    hazirlik = Column(JSON, nullable=True)  # {"durumlar": {"birlik_uyeligi": true, ...}, "eihracat": {...}} (bkz. app/hazirlik.py)
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
    # bkz. Tesvik.guncelleme_tarihi - onupdate olmadan tazeleme tarihi yazilmiyordu.
    guncelleme_tarihi = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                               onupdate=lambda: datetime.now(timezone.utc))


# Macro Indicator (TUIK/TCMB genel gostergeler)
class MacroIndicator(Base):
    __tablename__ = "macro_indicators"

    id = Column(Integer, primary_key=True, index=True)
    anahtar = Column(String, unique=True, index=True)  # "yillik_enflasyon", "tcmb_politika_faizi"
    deger = Column(Float)
    birim = Column(String, nullable=True)  # "%"
    kaynak = Column(String, nullable=True)
    # bkz. Tesvik.guncelleme_tarihi - onupdate olmadan tazeleme tarihi yazilmiyordu.
    guncelleme_tarihi = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                               onupdate=lambda: datetime.now(timezone.utc))


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


_gunluk = logging.getLogger(__name__)


def alembic_durumu(motor=None) -> tuple[str | None, str | None]:
    """(veritabanındaki göç sürümü, kod deposundaki head). Sürüm tablosu yoksa ilki None."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect, text
    motor = motor or engine
    with motor.connect() as baglanti:
        mevcut = (baglanti.execute(text("SELECT version_num FROM alembic_version")).scalar()
                  if inspect(baglanti).has_table("alembic_version") else None)
    cfg = Config(str(PROJE_KOKU / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJE_KOKU / "migrations"))
    return mevcut, ScriptDirectory.from_config(cfg).get_current_head()


def init_db(motor=None) -> str:
    """Göç geçmişi olmayan (boş/yerel) veritabanında tabloları oluşturur. Alembic'in yönettiği veritabanında
    create_all ÇALIŞTIRILMAZ (2026-10-08): yeni tabloyu göçten önce açıp "alembic upgrade"i bozuyor, var olan tabloya
    yeni sütunu ise ekleyemediği için eksik göçü gizliyordu. Sürüm geride ise yüksek seviyeli uyarı yazılır.
    Dönüş: "olusturuldu" | "guncel" | "goc_gerekli"."""
    motor = motor or engine
    mevcut, head = alembic_durumu(motor)
    if mevcut is None:
        Base.metadata.create_all(bind=motor)
        return "olusturuldu"
    if mevcut != head:
        _gunluk.critical(
            "Veritabanı göçü geride (mevcut %s, kod %s): 'python -m alembic upgrade head' çalıştırın (önce yedek alın).",
            mevcut, head)
        return "goc_gerekli"
    return "guncel"


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
