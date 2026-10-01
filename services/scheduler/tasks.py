from datetime import date, datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session, joinedload

from database import SessionLocal
from models import Notification, UserSubscription, Plan, User, NotificationStatus
from services.crawler.pipeline import run_comprehensive_crawler_pipeline
from services.recommender import recommend_best_plan
from services.notifier import NotificationDispatcher

def job_crawl_mvno_plans() -> Dict[str, Any]:
    """
    [매일 새벽 02:00 정기 작업]
    대한민국 알뜰폰 통신사 및 요금제 전수 자동 크롤링 및 DB 최신화
    """
    print(f"\n[Scheduler] 새벽 02:00 정기 크롤링 작업 시작: {datetime.now()}")
    db = SessionLocal()
    try:
        # 전수 정기 수집 (69페이지 + 25개 사업자 공식몰 전체)
        stats = run_comprehensive_crawler_pipeline(max_pages=0, include_direct=True, db=db)
        print(f"[Scheduler] 정기 크롤링 완료: {stats}")
        return stats
    except Exception as e:
        print(f"[Scheduler] 정기 크롤링 중 오류: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def job_send_lifecycle_notifications(db: Session = None) -> Dict[str, Any]:
    """
    [매일 자정 00:00 정기 배치 작업]
    만료일 기준 D-14, D-7, D-3 도래 대상자를 조회하고,
    TCO 최저가 대체 요금제를 추천하여 알림 발송 및 상태 업데이트
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    today = date.today()
    print(f"\n[Scheduler] 자정 환승 알림 배치 작업 시작 (기준일: {today})")

    stats = {
        "processed_date": today.isoformat(),
        "total_targets": 0,
        "sent_count": 0,
        "failed_count": 0,
        "results": []
    }

    try:
        # 오늘 이하 날짜로 예약된 PENDING 알림 조회
        pending_notifications: List[Notification] = db.query(Notification)\
            .options(
                joinedload(Notification.subscription)
                    .joinedload(UserSubscription.user),
                joinedload(Notification.subscription)
                    .joinedload(UserSubscription.plan)
                    .joinedload(Plan.telecom)
            )\
            .filter(
                Notification.scheduled_date <= today,
                Notification.status == NotificationStatus.PENDING
            )\
            .all()

        stats["total_targets"] = len(pending_notifications)
        print(f"[Scheduler] 발송 대상 알림: {len(pending_notifications)}건 발견")

        now = datetime.now()

        for notif in pending_notifications:
            sub = notif.subscription
            user = sub.user
            current_plan = sub.plan

            # 1. 최적의 TCO 대체 요금제 자동 추천
            recommended_plan = recommend_best_plan(
                current_plan=current_plan,
                target_months=sub.target_months,
                db=db
            )
            if recommended_plan:
                notif.recommended_plan_id = recommended_plan.plan_id

            # 2. 멀티채널 알림 발송
            dispatch_res = NotificationDispatcher.dispatch(
                notification=notif,
                subscription=sub,
                user=user,
                current_plan=current_plan,
                recommended_plan=recommended_plan
            )

            # 3. 알림 발송 상태 업데이트
            notif.status = NotificationStatus.SENT
            notif.sent_at = now
            stats["sent_count"] += 1
            stats["results"].append(dispatch_res)

        db.commit()
        print(f"[Scheduler] 자정 환승 알림 배치 완료: {stats['sent_count']}건 발송 성공")

    except Exception as e:
        db.rollback()
        stats["failed_count"] += 1
        stats["error"] = str(e)
        print(f"[Scheduler] 환승 알림 배치 실행 오류: {e}")
    finally:
        if should_close_db:
            db.close()

    return stats
