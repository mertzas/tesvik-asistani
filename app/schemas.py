from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# Auth Schemas
class UserSignup(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    company_name: str


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
    password: str = Field(..., min_length=8)


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
    sektor: str = Field(..., min_length=2, description="tarim, imalat, perakende, e-ticaret, hizmet, ihracat, arge, genel")
    bolge: Optional[str] = None
    calisan_sayisi: Optional[int] = Field(None, ge=0)
    yillik_ciro: Optional[float] = Field(None, ge=0)
    hedefler: Optional[List[str]] = None
    giderler: Optional[dict] = Field(None, description="{'stok': 100000, 'reklam': 20000} veya tek kalem biliniyorsa {'toplam': 550000}")
    arazi_buyuklugu_dekar: Optional[float] = Field(None, ge=0, description="Sadece tarim sektoru icin")
    urun_turu: Optional[str] = Field(None, description="Sadece tarim sektoru icin, serbest metin (fiyat aramasi icin), orn. bugday, domates, cilek")
    tarim_kategori: Optional[str] = Field(None, description="Yapilandirilmis secim: hayvancilik | sebze_meyve | tahil_baklagil | organik | sera | sulama | makinelestirme | genel")
    ilk_yil_mi: Optional[bool] = Field(None, description="Arazi hazirligi/sera/ekipman gibi tek seferlik kurulus gideri var mi")


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
