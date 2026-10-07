from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


SIFRE_EN_AZ, SIFRE_EN_COK_BAYT = 8, 72  # bcrypt 72 bayttan sonrasını yok sayar/hata verir


def sifre_kontrol(sifre: str) -> str:
    """Parola politikası (denetim 2026-10-07): 8+ karakter, en çok 72 bayt (bcrypt sınırı; aşınca
    passlib ValueError → 500), en az bir harf ve bir rakam, baştan/sondan boşluk yok."""
    if sifre != sifre.strip():
        raise ValueError("Parola başında/sonunda boşluk olamaz")
    if len(sifre) < SIFRE_EN_AZ:
        raise ValueError(f"Parola en az {SIFRE_EN_AZ} karakter olmalı")
    if len(sifre.encode("utf-8")) > SIFRE_EN_COK_BAYT:
        raise ValueError(f"Parola en çok {SIFRE_EN_COK_BAYT} bayt olabilir")
    if not any(c.isalpha() for c in sifre) or not any(c.isdigit() for c in sifre):
        raise ValueError("Parola en az bir harf ve bir rakam içermeli")
    return sifre


# Auth Schemas
class UserSignup(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=SIFRE_EN_AZ)
    full_name: str = Field(..., min_length=1, max_length=200)
    company_name: str = Field(..., min_length=1, max_length=200)

    _sifre = field_validator("password")(sifre_kontrol)
    # KVKK acik rizasi - ZORUNLU DEGIL. Verilmezse hesap yine acilir, AI
    # danisman yerine liste formati kullanilir (bkz. app/main.py sor()).
    ai_yurtdisi_riza: bool = Field(
        False,
        description="Yapay zeka danismani icin isletme profilinin "
                    "Anthropic'e (ABD) aktarilmasina acik riza")


class AiRizaGuncelle(BaseModel):
    riza: bool = Field(..., description="true: riza ver, false: rizayi geri al")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[dict] = None


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str = Field(..., min_length=SIFRE_EN_AZ)

    _sifre = field_validator("password")(sifre_kontrol)


class UserResponse(UserBase):
    id: UUID
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Organization Schemas
class OrganizationBase(BaseModel):
    name: str
    email: EmailStr


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: UUID
    plan: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrganizationWithUsers(OrganizationResponse):
    users: List[UserResponse] = []


# Query Schemas
class QueryResponse(BaseModel):
    id: UUID
    question: str
    results: List[dict]
    tokens_used: int
    created_at: datetime

    class Config:
        from_attributes = True


# Incentive (Tesvik) Schemas
class TesvikBase(BaseModel):
    kurum: str
    baslik: str
    ozet: str
    detay: str
    hedef_kitle: Optional[str] = None
    kaynak_url: Optional[str] = None
    kategori: Optional[str] = None
    baslama_tarihi: Optional[datetime] = None
    bitis_tarihi: Optional[datetime] = None
    tesvil_tutari: Optional[str] = None
    basin_orzu: Optional[float] = None


class TesvikResponse(TesvikBase):
    id: int
    guncelleme_tarihi: datetime

    class Config:
        from_attributes = True


# API Request/Response
class AskQuestion(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class SearchResult(BaseModel):
    id: int
    kurum: str
    baslik: str
    ozet: str
    hedef_kitle: Optional[str]
    baslama_tarihi: Optional[datetime]
    bitis_tarihi: Optional[datetime]
    relevance_score: Optional[float] = None


class AskResponse(BaseModel):
    query_id: UUID
    question: str
    results: List[SearchResult]
    tokens_used: int
    message: Optional[str] = None


# Billing Schemas
class PlanUpgrade(BaseModel):
    plan: str = Field(..., pattern="^(free|pro|business|enterprise)$")
    stripe_token: Optional[str] = None


class SubscriptionResponse(BaseModel):
    plan: str
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Financial Profile Schemas
class FinancialProfileCreate(BaseModel):
    sektor: str = Field(..., min_length=2, max_length=100, description="tarim, imalat, perakende, e-ticaret, hizmet, ihracat, arge, genel")
    bolge: Optional[str] = Field(None, max_length=100)
    calisan_sayisi: Optional[int] = Field(None, ge=0, le=1_000_000)
    yillik_ciro: Optional[float] = Field(None, ge=0, le=1e12)
    hedefler: Optional[List[str]] = Field(None, max_length=20)
    giderler: Optional[dict] = Field(None, description="{'stok': 100000, 'reklam': 20000} veya tek kalem biliniyorsa {'toplam': 550000}")
    arazi_buyuklugu_dekar: Optional[float] = Field(None, ge=0, le=1e7, description="Sadece tarim sektoru icin")
    urun_turu: Optional[str] = Field(None, max_length=100, description="Sadece tarim sektoru icin, serbest metin (fiyat aramasi icin), orn. bugday, domates, cilek")
    tarim_kategori: Optional[str] = Field(None, max_length=40, description="Yapilandirilmis secim: hayvancilik | sebze_meyve | tahil_baklagil | organik | sera | sulama | makinelestirme | genel")
    ilk_yil_mi: Optional[bool] = Field(None, description="Arazi hazirligi/sera/ekipman gibi tek seferlik kurulus gideri var mi")
    nace_kodu: Optional[str] = Field(None, max_length=20,
        description="Faaliyet kodu: C, C.10, C.10.71, 10.71 ... (NACE; harf isteğe bağlı)")
    ozellikler: Optional[List[str]] = Field(None, max_length=20,
        description="Hedef kitle etiketleri (kadin_girisimci, genc_girisimci, savunma_sanayii, ...)")
    sirket_turu: Optional[str] = Field(None, max_length=20,
        description="yok (henüz kurulmadı) | sahis | limited | anonim | kooperatif")
    kurulus_tarihi: Optional[date] = None
    trl: Optional[int] = Field(None, ge=1, le=9, description="Teknoloji hazırlık seviyesi 1-9")

    @field_validator("sirket_turu")
    @classmethod
    def _sirket_turu_gecerli(cls, v):
        if v is None or not str(v).strip():
            return None
        from app.girisim import SIRKET_TURLERI
        v = str(v).strip().lower()
        if v not in SIRKET_TURLERI:
            raise ValueError("sirket_turu şunlardan biri olmalı: " + ", ".join(SIRKET_TURLERI))
        return v

    @field_validator("kurulus_tarihi")
    @classmethod
    def _kurulus_gecerli(cls, v):
        if v is not None and v > date.today():
            raise ValueError("Kuruluş tarihi gelecekte olamaz")
        return v

    @field_validator("nace_kodu")
    @classmethod
    def _nace_gecerli(cls, v):
        if v is None or not str(v).strip():
            return None
        from app.nace_hiyerarsi import normalize_nace
        n = normalize_nace(v)
        if n is None:
            raise ValueError("Geçersiz NACE kodu (örn. C, C.10, 10.71, 55.10.01)")
        return n

    @field_validator("ozellikler")
    @classmethod
    def _ozellikler_gecerli(cls, v):
        if v is None:
            return v
        from app.match_adapter import OZELLIK_ETIKETLERI
        gecersiz = [x for x in v if x not in OZELLIK_ETIKETLERI]
        if gecersiz:
            raise ValueError(f"Bilinmeyen özellik: {', '.join(gecersiz)}")
        return sorted(set(v))

    @field_validator("giderler")
    @classmethod
    def _giderler_gecerli(cls, v):
        if v is None:
            return v
        if len(v) > 30:
            raise ValueError("En fazla 30 gider kalemi girilebilir")
        for ad, tutar in v.items():
            if isinstance(tutar, bool) or not isinstance(tutar, (int, float)):
                raise ValueError(f"'{ad}' gider kalemi sayı olmalı")
            if not (0 <= tutar <= 1e12):
                raise ValueError(f"'{ad}' gider kalemi 0 ile 1e12 arasında olmalı")
        return v


class FinancialProfileResponse(BaseModel):
    id: UUID
    sektor: str
    bolge: Optional[str]
    calisan_sayisi: Optional[int]
    yillik_ciro: Optional[float]
    hedefler: Optional[List[str]]
    giderler: Optional[dict]
    arazi_buyuklugu_dekar: Optional[float]
    urun_turu: Optional[str]
    tarim_kategori: Optional[str]
    ilk_yil_mi: Optional[bool]
    nace_kodu: Optional[str] = None
    ozellikler: Optional[List[str]] = None
    sirket_turu: Optional[str] = None
    kurulus_tarihi: Optional[date] = None
    trl: Optional[int] = None
    updated_at: datetime

    class Config:
        from_attributes = True


# Matching Schemas
class TesvikEslesmeItem(BaseModel):
    id: int
    kurum: str
    baslik: str
    ozet: str
    tesvil_tutari: Optional[str] = None
    kaynak_url: Optional[str] = None
    skor: float
    gerekce: List[str]
    eksik_kriterler: List[str]

    # Tutarı hesaplama ve başvuru süreci (çiftçi/KOBİ perspektifi)
    tutari_min: Optional[float] = None
    tutari_max: Optional[float] = None
    tutari_hesaplama_formulu: Optional[str] = None
    tutari_tahmini_profil: Optional[float] = None  # Kullanıcının profiline göre tahmin
    basvuru_sartlari: Optional[List[str]] = None
    gerekli_belgeler: Optional[List[str]] = None
    basvuru_yeri: Optional[str] = None

    # Programin hala basvuruya acik olup olmadigi. None = hic kontrol
    # edilmedi (kullaniciya "teyit edin" uyarisi gosterilmeli), True =
    # acik oldugu dogrulandi. False olanlar eslesmeye hic girmez.
    aktif_mi: Optional[bool] = None
    durum_notu: Optional[str] = None
    basvuru_suresi: Optional[str] = None
    destek_verilme_suresi: Optional[str] = None
    kategori: Optional[str] = None
    alt_kategori: Optional[str] = None


class TesvikEslesmeResponse(BaseModel):
    eslesen_tesvikler: List[TesvikEslesmeItem]
    tahmini_toplam_destek_min: float
    tahmini_toplam_destek_max: float


# Budget Recommendation Schemas
class ButceOnerisiResponse(BaseModel):
    sektor: str
    yillik_ciro: float
    stok_maliyeti_min: float
    stok_maliyeti_max: float
    reklam_butcesi_min: float
    reklam_butcesi_max: float
    # Onumuzdeki 12 ay icin TUFE-duzeltilmis projeksiyon (TUFE verisi yoksa None)
    gelecek_yil_stok_min: Optional[float] = None
    gelecek_yil_stok_max: Optional[float] = None
    gelecek_yil_reklam_min: Optional[float] = None
    gelecek_yil_reklam_max: Optional[float] = None
    mevcut_stok_gideri: Optional[float]
    mevcut_reklam_gideri: Optional[float]
    mevcut_toplam_gider: Optional[float]
    ilk_yil_kurulum_gideri: Optional[float]
    yillik_tufe: Optional[float]
    sektor_net_kar_orani: Optional[float]
    tarim_girdi_enflasyonu: Optional[dict]
    en_yuksek_artan_girdi: Optional[dict]
    guncel_urun_fiyati: Optional[dict]
    guncel_ihracat_fiyati: Optional[dict]
    tarim_dis_ticaret: Optional[dict]
    urun_veri_yok_mesaji: Optional[str]
    bolgesel_tavsiye: Optional[dict]
    gider_sapma_yuzdesi: Optional[float]
    notlar: List[str]
    analist_onerileri: List[str]


class EticaretGiderGirdisi(BaseModel):
    pazara_giris_raporu: Optional[float] = None
    dijital_pazaryeri_tanitim: Optional[float] = None
    e_ihracat_tanitim: Optional[float] = None
    siparis_karsilama_hizmeti: Optional[float] = None
    yurt_disi_depo_kirasi: Optional[float] = None
    pazaryeri_entegrasyon: Optional[float] = None
    pazaryeri_komisyon: Optional[float] = None
    hedef_ulke_mi: bool = False
    ihracatci_birligi_uyesi_mi: Optional[bool] = None


class EticaretGiderKalemiResponse(BaseModel):
    kalem: str
    etiket: str
    yillik_gider_tl: float
    tahmini_geri_odeme_tl: float


class EticaretDestekResponse(BaseModel):
    hedef_ulke_mi: bool
    uygulanan_oran: float
    kalemler: List[EticaretGiderKalemiResponse]
    toplam_yillik_gider_tl: float
    toplam_tahmini_geri_odeme_tl: float
    notlar: List[str]


# Analytics Schemas
class UsageStats(BaseModel):
    queries_this_month: int
    queries_limit: Optional[int]
    api_calls_this_month: int
    users_active: int
    storage_used_mb: float


class AnalyticsResponse(BaseModel):
    org_id: UUID
    usage_stats: UsageStats
    created_at: datetime
