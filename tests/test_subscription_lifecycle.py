import unittest
from datetime import date, datetime
from unittest.mock import patch
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from database import Base
from models import User, Telecom, Plan, UserSubscription, Notification, NoticeType, NotificationStatus, SubscriptionStatus
from schemas import SubscriptionCreate
from routers.subscriptions import create_subscription, delete_subscription, serialize_subscription
from services.lifecycle import target_end_date, recommendation_start_date, recommendation_available, notification_schedule
from services.scheduler.tasks import job_send_lifecycle_notifications
from deploy.migrate_notification_schedule import migrate_pending


class SubscriptionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        @event.listens_for(self.engine, 'connect')
        def foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = User(email='member@example.com', default_target_months=12)
        telecom = Telecom(name='test')
        self.db.add_all([self.user, telecom])
        self.db.flush()
        self.plan = Plan(telecom_id=telecom.telecom_id, title='test', base_data_gb=7,
                         discount_price=1000, normal_price=22000, discount_months=7,
                         scraped_at=datetime.now())
        self.db.add(self.plan)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def subscription(self, start=date(2026, 3, 31), months=12):
        sub = UserSubscription(user_id=self.user.user_id, plan_id=self.plan.plan_id,
                               start_date=start, target_months=months, discount_end_date=date(2026, 10, 31),
                               status=SubscriptionStatus.ACTIVE)
        self.db.add(sub)
        self.db.commit()
        return sub

    def test_calendar_month_boundary_and_maintenance_period(self):
        sub = self.subscription()
        self.assertEqual(target_end_date(sub), date(2027, 3, 31))
        self.assertEqual(recommendation_start_date(sub), date(2027, 2, 28))
        self.assertEqual(notification_schedule(sub), [(NoticeType.MONTH_BEFORE, date(2027, 2, 28)),
                         (NoticeType.D_7, date(2027, 3, 24)), (NoticeType.D_1, date(2027, 3, 30))])
        self.assertFalse(recommendation_available(sub, date(2027, 2, 27)))
        self.assertTrue(recommendation_available(sub, date(2027, 2, 28)))

    def test_registration_reserves_maintenance_not_discount_dates(self):
        result = create_subscription(SubscriptionCreate(user_id=self.user.user_id, plan_id=self.plan.plan_id,
                                     start_date=date(2026, 3, 31), target_months=12), self.db)
        self.assertEqual(result.discount_end_date, date(2026, 10, 31))
        self.assertEqual(result.target_end_date, date(2027, 3, 31))
        self.assertEqual({n.scheduled_date for n in result.notifications},
                         {date(2027, 2, 28), date(2027, 3, 24), date(2027, 3, 30)})

    def test_delete_removes_notifications_but_keeps_plan_and_user(self):
        sub = self.subscription()
        self.db.add(Notification(subscription_id=sub.subscription_id, notice_type=NoticeType.D_7,
                                 scheduled_date=date(2027, 3, 24)))
        self.db.commit()
        delete_subscription(sub.subscription_id, self.user.user_id, self.db)
        self.assertEqual(self.db.query(UserSubscription).count(), 0)
        self.assertEqual(self.db.query(Notification).count(), 0)
        self.assertEqual(self.db.query(Plan).count(), 1)
        self.assertEqual(self.db.query(User).count(), 1)

    def test_delete_wrong_user_rejected(self):
        sub = self.subscription()
        with self.assertRaises(HTTPException) as error:
            delete_subscription(sub.subscription_id, self.user.user_id + 1, self.db)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(self.db.query(UserSubscription).count(), 1)

    def test_response_hides_existing_recommendation_before_window(self):
        sub = self.subscription()
        self.db.add(Notification(subscription_id=sub.subscription_id, notice_type=NoticeType.D_7,
                                 scheduled_date=date(2027, 3, 24), recommended_plan_id=self.plan.plan_id))
        self.db.commit()
        with patch('routers.subscriptions.recommendation_available', return_value=False):
            result = serialize_subscription(sub)
        self.assertFalse(result.recommendation_available)
        self.assertIsNone(result.notifications[0].recommended_plan_id)
        self.assertIsNone(result.notifications[0].recommended_plan)
        with patch('routers.subscriptions.recommendation_available', return_value=True):
            result = serialize_subscription(sub)
        self.assertEqual(result.notifications[0].recommended_plan.plan_id, self.plan.plan_id)

    def test_batch_does_not_compute_or_send_before_window(self):
        sub = self.subscription()
        self.db.add(Notification(subscription_id=sub.subscription_id, notice_type=NoticeType.D_14,
                                 scheduled_date=date(2026, 10, 17), status=NotificationStatus.PENDING))
        self.db.commit()
        with patch('services.scheduler.tasks.date') as mock_date, \
             patch('services.scheduler.tasks.recommend_best_plan') as recommend, \
             patch('services.scheduler.tasks.NotificationDispatcher.dispatch') as dispatch:
            mock_date.today.return_value = date(2026, 10, 17)
            result = job_send_lifecycle_notifications(self.db)
        self.assertEqual(result['sent_count'], 0)
        recommend.assert_not_called()
        dispatch.assert_not_called()

    def test_batch_recommends_at_calendar_month_boundary(self):
        sub = self.subscription()
        notification = Notification(subscription_id=sub.subscription_id, notice_type=NoticeType.MONTH_BEFORE,
                                    scheduled_date=date(2027, 2, 28), status=NotificationStatus.PENDING)
        self.db.add(notification)
        self.db.commit()
        with patch('services.scheduler.tasks.date') as mock_date, \
             patch('services.scheduler.tasks.recommend_best_plan', return_value=self.plan) as recommend, \
             patch('services.scheduler.tasks.NotificationDispatcher.dispatch', return_value={}) as dispatch:
            mock_date.today.return_value = date(2027, 2, 28)
            result = job_send_lifecycle_notifications(self.db)
        self.assertEqual(result['sent_count'], 1)
        self.assertEqual(notification.status, NotificationStatus.SENT)
        recommend.assert_called_once_with(current_plan=self.plan, target_months=12, db=self.db)
        dispatch.assert_called_once()

    def test_existing_pending_migration_is_idempotent_preserves_sent(self):
        sub = self.subscription()
        for kind in (NoticeType.D_14, NoticeType.D_7, NoticeType.D_3):
            self.db.add(Notification(subscription_id=sub.subscription_id, notice_type=kind,
                                     scheduled_date=date(2026, 10, 17), status=NotificationStatus.PENDING))
        sent = Notification(subscription_id=sub.subscription_id, notice_type=NoticeType.D_14,
                            scheduled_date=date(2026, 10, 1), status=NotificationStatus.SENT)
        self.db.add(sent)
        self.db.commit()
        stats = migrate_pending(self.db, date(2026, 10, 9))
        self.db.commit()
        self.assertEqual(stats['updated'], 3)
        self.assertEqual(sent.notice_type, NoticeType.D_14)
        pending = self.db.query(Notification).filter(Notification.status==NotificationStatus.PENDING).all()
        self.assertEqual({n.notice_type for n in pending}, {NoticeType.MONTH_BEFORE, NoticeType.D_7, NoticeType.D_1})
        second = migrate_pending(self.db, date(2026, 10, 9))
        self.assertEqual(second['updated'], 0)
        self.assertEqual(second['created'], 0)


if __name__ == '__main__':
    unittest.main()
