from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr
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
    normal_price: int
    discount_months: int
    raw_text: Optional[str] = None
    is_active: bool = True

class PlanResponse(PlanBase):
    model_config = ConfigDict(from_attributes=True)
    plan_id: int
    telecom_id: int
    scraped_at: datetime
    telecom: Optional[TelecomResponse] = None

class PlanRankItem(PlanResponse):
    target_months: int
    tco: int
    monthly_avg_price: int
    discount_period_months: int
    normal_period_months: int
    is_unlimited_data: bool = False
    qos_tier: str = "소진 시 차단/과금형"

# --- User Schemas ---
class UserCreate(BaseModel):
    email: str
    fcm_token: Optional[str] = None
    default_target_months: int = 12

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    email: str
    fcm_token: Optional[str] = None
    default_target_months: int
    created_at: datetime

# --- Notification Schemas ---
class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    notification_id: int
    subscription_id: int
    notice_type: NoticeType
    recommended_plan_id: Optional[int] = None
    scheduled_date: date
    sent_at: Optional[datetime] = None
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
    status: SubscriptionStatus
    created_at: datetime
    plan: Optional[PlanResponse] = None
    notifications: List[NotificationResponse] = []
