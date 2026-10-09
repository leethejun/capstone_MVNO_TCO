"""기존 대기 알림을 유지기간 기준으로 전환. 발송 이력은 보존한다.

미리보기: python -m deploy.migrate_notification_schedule
적용: python -m deploy.migrate_notification_schedule --apply
"""
import argparse
import json
from datetime import date, datetime
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import joinedload
from database import SessionLocal, engine
from models import UserSubscription, Notification, NoticeType, NotificationStatus, SubscriptionStatus
from services.lifecycle import notification_schedule, recommendation_available


def migrate_pending(db, today=None, flush=True):
    today = today or date.today()
    stats = {"updated": 0, "created": 0, "duplicates_removed": 0, "early_recommendations_cleared": 0}
    subscriptions = db.query(UserSubscription).options(joinedload(UserSubscription.notifications)).all()
    aliases = {NoticeType.D_14: NoticeType.MONTH_BEFORE, NoticeType.D_3: NoticeType.D_1}
    for sub in subscriptions:
        if sub.status != SubscriptionStatus.ACTIVE:
            continue
        dates = dict(notification_schedule(sub))
        seen = {n.notice_type for n in sub.notifications if n.status != NotificationStatus.PENDING}
        # 이미 새 종류가 있으면 이전 종류의 중복 대기 알림을 만들지 않는다.
        pending = sorted((n for n in sub.notifications if n.status == NotificationStatus.PENDING),
                         key=lambda n: n.notice_type in aliases)
        for notification in pending:
            kind = aliases.get(notification.notice_type, notification.notice_type)
            if kind not in dates:
                continue
            if kind in seen:
                db.delete(notification)
                stats["duplicates_removed"] += 1
                continue
            seen.add(kind)
            if notification.notice_type != kind or notification.scheduled_date != dates[kind]:
                notification.notice_type = kind
                notification.scheduled_date = dates[kind]
                notification.recommended_plan_id = None
                stats["updated"] += 1
        for kind, scheduled in dates.items():
            # 과거에 이미 놓친 시점을 새 알림으로 재발송하지 않는다.
            if kind not in seen and scheduled >= today:
                db.add(Notification(subscription_id=sub.subscription_id, notice_type=kind,
                                    scheduled_date=scheduled, status=NotificationStatus.PENDING))
                stats["created"] += 1
        if not recommendation_available(sub, today):
            for notification in sub.notifications:
                if notification.recommended_plan_id is not None:
                    notification.recommended_plan_id = None
                    stats["early_recommendations_cleared"] += 1
    if flush:
        db.flush()
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.apply:
            rows = db.execute(text('SELECT * FROM notifications')).mappings().all()
            backup = Path('/tmp') / f'alddle-notifications-{datetime.now():%Y%m%dT%H%M%S}.json'
            backup.write_text(json.dumps([dict(row) for row in rows], default=str, ensure_ascii=False, indent=2))
            backup.chmod(0o600)
            # 별도 연결에서 DDL을 실행하기 전에 SELECT 트랜잭션의 metadata lock을 해제한다.
            db.rollback()
            print(f'알림 백업: {backup}')
            # MySQL create_all은 기존 Enum 컬럼을 확장하지 않으므로 명시적으로 적용한다.
            if engine.dialect.name == 'mysql':
                with engine.begin() as connection:
                    connection.execute(text("SET SESSION lock_wait_timeout = 10"))
                    connection.execute(text("ALTER TABLE notifications MODIFY COLUMN notice_type "
                                            "ENUM('D_14','D_7','D_3','MONTH_BEFORE','D_1') NOT NULL"))
        stats = migrate_pending(db, flush=args.apply)
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps({"applied": args.apply, **stats}, ensure_ascii=False))


if __name__ == '__main__':
    main()
