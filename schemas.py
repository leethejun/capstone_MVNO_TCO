from datetime import date, datetime
from typing import Any, Dict, Literal, Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from models import SubscriptionStatus, NoticeType, NotificationStatus

# --- Telecom Schemas ---
class TelecomBase(BaseModel):
    name: str
    logo_url: Optional[str] = None
    website_url: Optional[str] = None

class TelecomResponse(TelecomBase):
    model_config = ConfigDict(from_attributes=True)
    telecom_id: int

# --- Plan Schemas ---
class PlanBase(BaseModel):
    title: str
    network_type: str = "LTE"
    base_data_gb: float
    daily_data_gb: float = 0.0
    qos_speed_mbps: float = 0.0
    voice_minutes: int = 0
    sms_count: int = 0
    discount_price: int
    normal_price: Optional[int]
    discount_months: int
    raw_text: Optional[str] = None
    is_active: bool = True

class PlanResponse(PlanBase):
    model_config = ConfigDict(from_attributes=True)
    plan_id: int
    telecom_id: int
    scraped_at: datetime
    telecom: Optional[TelecomResponse] = None

# 추천 근거: 프론트엔드가 code별 문구로 번역하고 params 값을 채운다.
class RecommendationReason(BaseModel):
    code: str
    params: Dict[str, Any] = {}

class PlanRankItem(PlanResponse):
    target_months: int
    tco: int
    monthly_avg_price: int
    discount_period_months: int
    normal_period_months: int
    is_unlimited_data: bool = False
    qos_tier: str = "소진 시 차단/과금형"
    reasons: List[RecommendationReason] = []

# --- Favorite Schemas ---
class FavoriteKey(BaseModel):
    telecom_name: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=100)
    network_type: str = Field("LTE", max_length=10)
    plan_id: Optional[int] = None

class FavoriteCreate(BaseModel):
    plan_id: int

class FavoriteResolveRequest(BaseModel):
    items: List[FavoriteKey] = Field(default_factory=list, max_length=100)
    target_months: int = Field(12, ge=1, le=48)

class FavoriteItem(FavoriteKey):
    favorite_id: Optional[int] = None
    # available: 저장한 상품 그대로 / replaced: 재수집된 같은 이름 상품 / unavailable: 판매 확인 불가
    # not_computable: 상품은 있으나 선택 기간 TCO 계산 불가(정상가 미확인 등)
    status: Literal["available", "replaced", "unavailable", "not_computable"]
    plan: Optional[PlanRankItem] = None

# --- User Schemas ---
class UserCreate(BaseModel):
    email: str
    fcm_token: Optional[str] = None
    default_target_months: int = 12

class UserResponse(BaseModel):
    is_admin: bool = False
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    email: str
    default_target_months: int
    created_at: datetime

# --- Notification Schemas ---
class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    notification_id: int
    subscription_id: int
    notice_type: NoticeType
    recommended_plan_id: Optional[int] = None
    recommended_plan: Optional[PlanResponse] = None
    recommendation_reasons: List[RecommendationReason] = []
    scheduled_date: date
    sent_at: Optional[datetime] = None
    push_status: str = "NOT_SENT"
    status: NotificationStatus

# --- Subscription Schemas ---
class SubscriptionCreate(BaseModel):
    user_id: int
    plan_id: int
    start_date: date
    target_months: Optional[int] = None  # None일 경우 유저의 default_target_months 또는 요금제의 discount_months 적용

class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subscription_id: int
    user_id: int
    plan_id: int
    start_date: date
    target_months: int
    discount_end_date: date
    target_end_date: Optional[date] = None
    recommendation_start_date: Optional[date] = None
    recommendation_available: bool = False
    status: SubscriptionStatus
    created_at: datetime
    plan: Optional[PlanResponse] = None
    notifications: List[NotificationResponse] = []


class PushDeviceInput(BaseModel):
    language: Literal["ko", "en"] = "ko"
    installation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    token: str = Field(min_length=20, max_length=2048)


class PushDeviceDelete(BaseModel):
    installation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class UserPreferences(BaseModel):
    default_target_months: int = Field(ge=6, le=48)
