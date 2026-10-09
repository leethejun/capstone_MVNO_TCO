import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, Text,
    Numeric, Date, DateTime, ForeignKey, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from database import Base

# --- Enum 정의 ---
class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class NoticeType(str, enum.Enum):
    MONTH_BEFORE = "MONTH_BEFORE"
    D_1 = "D-1"
    # 과거 발송 이력을 읽기 위해 기존 종류도 보존한다.
    D_14 = "D-14"
    D_7 = "D-7"
    D_3 = "D-3"

class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


# --- ORM 모델 클래스 ---
class Telecom(Base):
    __tablename__ = "telecoms"

    telecom_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    logo_url = Column(String(255), nullable=True)
    website_url = Column(String(255), nullable=True)

    plans = relationship("Plan", back_populates="telecom", cascade="all, delete-orphan")


class Plan(Base):
    __tablename__ = "plans"

    plan_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    telecom_id = Column(Integer, ForeignKey("telecoms.telecom_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(100), nullable=False)
    network_type = Column(String(10), default="LTE")
    base_data_gb = Column(Numeric(5, 1), nullable=False)
    daily_data_gb = Column(Numeric(3, 1), default=0.0)
    qos_speed_mbps = Column(Numeric(4, 1), default=0.0)
    voice_minutes = Column(Integer, default=0)
    sms_count = Column(Integer, default=0)
    discount_price = Column(Integer, nullable=False)
    normal_price = Column(Integer, nullable=False)
    discount_months = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    scraped_at = Column(DateTime, nullable=False)

    telecom = relationship("Telecom", back_populates="plans")
    subscriptions = relationship("UserSubscription", back_populates="plan")


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False)
    firebase_uid = Column(String(128), unique=True, nullable=True)
    fcm_token = Column(String(255), nullable=True)  # 이전 스키마 호환용, 실제 발송에는 사용하지 않음
    default_target_months = Column(Integer, default=12)
    created_at = Column(DateTime, default=datetime.now)

    subscriptions = relationship("UserSubscription", back_populates="user", cascade="all, delete-orphan")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    subscription_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.plan_id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    target_months = Column(Integer, nullable=False)
    discount_end_date = Column(Date, nullable=False)
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    notifications = relationship("Notification", back_populates="subscription", cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.subscription_id", ondelete="CASCADE"), nullable=False)
    notice_type = Column(SQLEnum(NoticeType), nullable=False)
    recommended_plan_id = Column(Integer, ForeignKey("plans.plan_id", ondelete="SET NULL"), nullable=True)
    scheduled_date = Column(Date, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    push_status = Column(String(20), default="NOT_SENT", nullable=False)
    push_attempts = Column(Integer, default=0, nullable=False)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)

    subscription = relationship("UserSubscription", back_populates="notifications")
    recommended_plan = relationship("Plan")


class PushDevice(Base):
    __tablename__ = "push_devices"
    device_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    installation_id = Column(String(64), nullable=False, unique=True)
    token = Column(String(2048), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, nullable=False)


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    __table_args__ = (UniqueConstraint("notification_id", "device_id"),)
    delivery_id = Column(Integer, primary_key=True, autoincrement=True)
    notification_id = Column(Integer, ForeignKey("notifications.notification_id", ondelete="CASCADE"), nullable=False)
    device_id = Column(Integer, ForeignKey("push_devices.device_id", ondelete="CASCADE"), nullable=False)
    delivered_at = Column(DateTime, nullable=True)
