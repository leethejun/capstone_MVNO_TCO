import unittest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Plan, Telecom, User, UserSubscription, Notification, NoticeType
from services.crawler.pipeline import run_comprehensive_crawler_pipeline


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        carrier = Telecom(name='Carrier'); self.db.add(carrier); self.db.flush()
        self.db.add(Plan(telecom_id=carrier.telecom_id, title='Old', network_type='LTE', base_data_gb=5,
                         discount_price=1000, normal_price=1000, discount_months=-1,
                         raw_text='', is_active=True, scraped_at=datetime.now()))
        self.db.commit()
        self.raw = {'telecom_name':'Carrier','title':'New','network_type':'LTE',
                    'discount_price':2000,'normal_price':3000,'discount_months':7,
                    'raw_text':'데이터 5GB 통화 100분 문자 100건 [출처: 공식몰]'}

    def tearDown(self):
        self.db.close(); self.engine.dispose()

    def run_snapshot(self, records=None, complete=True, max_pages=0):
        with patch('services.crawler.pipeline.sync_telecom_master', return_value={'total_master':1}), \
             patch('services.crawler.pipeline.MvnohubCrawler') as hub, \
             patch.dict('os.environ', {'CRAWLER_REPORT_PATH':'/tmp/snapshot-tests.json'}):
            hub.return_value.fetch_raw_plans.return_value = records if records is not None else [self.raw]
            hub.return_value.complete = complete
            hub.return_value.errors = []
            return run_comprehensive_crawler_pipeline(db=self.db, include_direct=False, max_pages=max_pages)

    def assert_old_unchanged(self):
        self.db.expire_all()
        plan = self.db.query(Plan).one()
        self.assertEqual((plan.title,plan.normal_price,plan.is_active), ('Old',1000,True))

    def test_incomplete_or_page_limited_run_cannot_replace_catalog(self):
        self.assertFalse(self.run_snapshot(complete=False)['success']); self.assert_old_unchanged()
        self.assertFalse(self.run_snapshot(max_pages=1)['success']); self.assert_old_unchanged()

    def test_empty_or_entirely_invalid_run_cannot_clear_catalog(self):
        self.assertFalse(self.run_snapshot(records=[])['success']); self.assert_old_unchanged()
        invalid = {**self.raw,'normal_price':0}
        self.assertFalse(self.run_snapshot(records=[invalid])['success']); self.assert_old_unchanged()

    def test_database_failure_rolls_back_deletion_and_insert(self):
        with patch.object(self.db, 'commit', side_effect=RuntimeError('write failed')):
            result = self.run_snapshot()
        self.assertFalse(result['success']); self.assert_old_unchanged()

    def test_distinct_sale_channels_are_not_collapsed(self):
        brand = {**self.raw, 'raw_text':self.raw['raw_text'].replace('공식몰','브랜드관')}
        result = self.run_snapshot(records=[self.raw,brand])
        self.assertTrue(result['success'])
        self.assertEqual(self.db.query(Plan).filter(Plan.is_active==True).count(),2)

    def test_subscription_and_notification_survive_catalog_replacement(self):
        old = self.db.query(Plan).one()
        user = User(email='history@example.com'); self.db.add(user); self.db.flush()
        subscription = UserSubscription(user_id=user.user_id, plan_id=old.plan_id,
                                        start_date=datetime(2026,1,1), target_months=12,
                                        discount_end_date=datetime(2027,1,1))
        self.db.add(subscription)
        recommendation = Plan(telecom_id=old.telecom_id, title='Old recommendation', network_type='LTE',
                              base_data_gb=5, discount_price=500, normal_price=1000, discount_months=7,
                              raw_text='', is_active=True, scraped_at=datetime.now())
        self.db.add(recommendation); self.db.flush()
        notification = Notification(subscription_id=subscription.subscription_id, notice_type=NoticeType.D_7,
                                    recommended_plan_id=recommendation.plan_id, scheduled_date=datetime(2026,12,25))
        self.db.add(notification); self.db.commit()
        old_id = old.plan_id
        self.assertTrue(self.run_snapshot()['success'])
        self.db.expire_all()
        self.assertEqual(self.db.query(UserSubscription).one().plan_id, old_id)
        self.assertFalse(self.db.get(Plan, old_id).is_active)
        self.assertEqual(self.db.get(Plan, old_id).normal_price, 1000)
        self.assertIsNone(self.db.query(Notification).one().recommended_plan_id)
        self.assertEqual(self.db.query(Plan).filter(Plan.is_active==True).count(),1)
