import calendar
from datetime import date, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import User, Plan, UserSubscription, Notification, SubscriptionStatus, NoticeType, NotificationStatus
from schemas import SubscriptionCreate, SubscriptionResponse
from services.auth import get_current_user
from services.lifecycle import notification_schedule, target_end_date, recommendation_start_date, recommendation_available

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions & Notifications"])

def calculate_discount_end_date(start_date: date, months: int) -> date:
    """start_date 기준으로 정확히 months 개월 후의 날짜 계산"""
    month = start_date.month - 1 + months
    year = start_date.year + month // 12
    month = month % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

@router.post("", response_model=SubscriptionResponse, summary="사용자 요금제 개통 등록 및 만료 알림 스케줄 자동 생성")
def create_subscription(sub_in: SubscriptionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if sub_in.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="본인 계정에만 등록할 수 있습니다.")
    user = current_user

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

    # 선택한 유지기간 종료 한 달 전·일주일 전·하루 전 알림을 예약한다.
    for notice_type, sched_date in notification_schedule(subscription):
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
    return serialize_subscription(subscription)

@router.get("/user/{user_id}", response_model=List[SubscriptionResponse], summary="특정 사용자의 개통 요금제 목록 및 알림 상태 조회")
def get_user_subscriptions(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="본인 요금제만 조회할 수 있습니다.")
    subs = db.query(UserSubscription)\
        .options(
            joinedload(UserSubscription.plan).joinedload(Plan.telecom),
            joinedload(UserSubscription.notifications)
        )\
        .filter(UserSubscription.user_id == user_id)\
        .order_by(UserSubscription.created_at.desc())\
        .all()
    return [serialize_subscription(sub) for sub in subs]

@router.get("/{subscription_id}", response_model=SubscriptionResponse, summary="개통 상세 정보 및 알림 조회")
def get_subscription_detail(subscription_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(UserSubscription)\
        .options(
            joinedload(UserSubscription.plan).joinedload(Plan.telecom),
            joinedload(UserSubscription.notifications)
        )\
        .filter(UserSubscription.subscription_id == subscription_id, UserSubscription.user_id == current_user.user_id)\
        .first()

    if not sub:
        raise HTTPException(status_code=404, detail="개통 정보를 찾을 수 없습니다.")
    return serialize_subscription(sub)


def serialize_subscription(sub):
    result = SubscriptionResponse.model_validate(sub)
    result.target_end_date = target_end_date(sub)
    result.recommendation_start_date = recommendation_start_date(sub)
    result.recommendation_available = recommendation_available(sub)
    if not result.recommendation_available:
        for notification in result.notifications:
            notification.recommended_plan_id = None
            notification.recommended_plan = None
    return result


@router.delete("/{subscription_id}", status_code=204, summary="내 요금제 및 관련 알림 삭제")
def delete_subscription(subscription_id: int, user_id: int = Query(..., ge=1), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="본인 요금제만 삭제할 수 있습니다.")
    sub = db.query(UserSubscription).filter(
        UserSubscription.subscription_id == subscription_id,
        UserSubscription.user_id == user_id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="등록된 요금제를 찾을 수 없습니다.")
    db.delete(sub)  # ORM cascade로 예약·발송 알림도 함께 삭제한다.
    db.commit()
    return Response(status_code=204)
