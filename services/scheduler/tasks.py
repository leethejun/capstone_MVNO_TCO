from datetime import date, datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session, joinedload

from database import SessionLocal
from models import Notification, UserSubscription, Plan, User, NotificationStatus, SubscriptionStatus
from services.crawler.pipeline import run_comprehensive_crawler_pipeline
from services.recommender import recommend_best_plan
from services.notifier import NotificationDispatcher
from services.lifecycle import recommendation_available

def job_crawl_mvno_plans() -> Dict[str, Any]:
    """
    [매일 새벽 02:00 정기 작업]
    대한민국 알뜰폰 통신사 및 요금제 전수 자동 크롤링 및 DB 최신화
    """
    print(f"\n[Scheduler] 새벽 02:00 정기 크롤링 작업 시작: {datetime.now()}")
    db = SessionLocal()
    try:
        # 허브 전체 페이지와 허브·마스터 사업자 공식몰 수집 후 추천 목록 교체
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
    유지기간 종료 한 달 전, 일주일 전, 하루 전 도래 대상자를 조회하고,
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
            if not recommendation_available(sub, today):
                continue
            user = sub.user
            current_plan = sub.plan

            # 1. 최적의 TCO 대체 요금제 자동 추천
            recommended_plan = recommend_best_plan(
                current_plan=current_plan,
                target_months=sub.target_months,
                db=db
            )
            notif.recommended_plan_id = recommended_plan.plan_id if recommended_plan else None

            # 2. 멀티채널 알림 발송
            dispatch_res = NotificationDispatcher.dispatch(
                notification=notif,
                subscription=sub,
                user=user,
                current_plan=current_plan,
                recommended_plan=recommended_plan,
                db=db
            )

            push_result = dispatch_res.get('push', {})
            notif.push_attempts = (notif.push_attempts or 0) + 1
            if push_result.get('failed', 0):
                notif.push_status = 'FAILED'
                # 성공한 기기는 발송 이력으로 제외하고 실패 기기만 다음 배치에서 재시도한다.
                if notif.push_attempts >= 3:
                    notif.status = NotificationStatus.FAILED
                stats['failed_count'] += 1
            else:
                notif.push_status = 'SENT' if push_result.get('sent', 0) else 'NO_DEVICE'
                notif.status = NotificationStatus.SENT
                notif.sent_at = now
                stats['sent_count'] += 1
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
