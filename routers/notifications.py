from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Notification, NotificationStatus, UserSubscription, Plan, User
from schemas import NotificationResponse
from services.auth import get_current_user, require_admin
from services.scheduler.tasks import job_send_lifecycle_notifications
from services.scheduler.manager import get_scheduler_jobs

router = APIRouter(prefix="/api/notifications", tags=["Notifications & Scheduler"])

@router.post("/trigger-batch", summary="자정 환승 알림 배치 즉시 수동 실행 (테스트 및 검증용)")
def trigger_notification_batch(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """
    매일 자정에 동작하는 환승 알림 배치 작업을 즉시 실행합니다.
    - 유지기간 종료 한 달 전·일주일 전·하루 전 도래 대상자 조회
    - TCO 최저가 대체 요금제 자동 추천
    - 알림 발송 및 PENDING -> SENT 상태 갱신
    """
    result = job_send_lifecycle_notifications(db=db)
    return result

@router.get("/pending", response_model=List[NotificationResponse], summary="발송 대기 중(PENDING)인 알림 목록 조회")
def get_pending_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Notification).join(UserSubscription).filter(Notification.status == NotificationStatus.PENDING, UserSubscription.user_id == user.user_id).all()

@router.get("/scheduler/jobs", summary="백그라운드 스케줄러 정기 작업 목록 조회")
def list_scheduled_jobs(admin=Depends(require_admin)):
    """새벽 2시 크롤링 및 자정 환승 알림 스케줄러 상태 및 다음 실행 일시 조회"""
    return get_scheduler_jobs()
