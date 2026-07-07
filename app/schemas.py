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
