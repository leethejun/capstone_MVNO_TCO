import calendar
from datetime import date, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import User, Plan, UserSubscription, Notification, SubscriptionStatus, NoticeType, NotificationStatus
from schemas import SubscriptionCreate, SubscriptionResponse

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions & Notifications"])

def calculate_discount_end_date(start_date: date, months: int) -> date:
    """start_date 기준으로 정확히 months 개월 후의 날짜 계산"""
    month = start_date.month - 1 + months
    year = start_date.year + month // 12
    month = month % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

@router.post("", response_model=SubscriptionResponse, summary="사용자 요금제 개통 등록 및 만료 알림 스케줄 자동 생성")
def create_subscription(sub_in: SubscriptionCreate, db: Session = Depends(get_db)):
    # 1. 사용자 및 요금제 존재 여부 확인
    user = db.query(User).filter(User.user_id == sub_in.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    plan = db.query(Plan).options(joinedload(Plan.telecom)).filter(Plan.plan_id == sub_in.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="요금제를 찾을 수 없습니다.")

    target_months = sub_in.target_months or user.default_target_months or plan.discount_months

    # 2. 프로모션 할인 만료일 계산 (개통일 + 할인개월수)
    discount_end_date = calculate_discount_end_date(sub_in.start_date, plan.discount_months)

    subscription = UserSubscription(
        user_id=user.user_id,
        plan_id=plan.plan_id,
        start_date=sub_in.start_date,
        target_months=target_months,
        discount_end_date=discount_end_date,
        status=SubscriptionStatus.ACTIVE
    )
    db.add(subscription)
    db.flush()  # subscription_id 확보

    # 3. 만료일 기준 D-14, D-7, D-3 환승 알림 스케줄 자동 생성
    notification_configs = [
        (NoticeType.D_14, 14),
        (NoticeType.D_7, 7),
        (NoticeType.D_3, 3)
    ]

    for notice_type, days_before in notification_configs:
        sched_date = discount_end_date - timedelta(days=days_before)
        notification = Notification(
            subscription_id=subscription.subscription_id,
            notice_type=notice_type,
            scheduled_date=sched_date,
            status=NotificationStatus.PENDING
        )
        db.add(notification)

    db.commit()
    db.refresh(subscription)

    # relations eager loading
    subscription.plan = plan
    return subscription

@router.get("/user/{user_id}", response_model=List[SubscriptionResponse], summary="특정 사용자의 개통 요금제 목록 및 알림 상태 조회")
def get_user_subscriptions(user_id: int, db: Session = Depends(get_db)):
    subs = db.query(UserSubscription)\
        .options(
            joinedload(UserSubscription.plan).joinedload(Plan.telecom),
            joinedload(UserSubscription.notifications)
        )\
        .filter(UserSubscription.user_id == user_id)\
        .order_by(UserSubscription.created_at.desc())\
        .all()
    return subs

@router.get("/{subscription_id}", response_model=SubscriptionResponse, summary="개통 상세 정보 및 알림 조회")
def get_subscription_detail(subscription_id: int, db: Session = Depends(get_db)):
    sub = db.query(UserSubscription)\
        .options(
            joinedload(UserSubscription.plan).joinedload(Plan.telecom),
            joinedload(UserSubscription.notifications)
        )\
        .filter(UserSubscription.subscription_id == subscription_id)\
        .first()

    if not sub:
        raise HTTPException(status_code=404, detail="개통 정보를 찾을 수 없습니다.")
    return sub
