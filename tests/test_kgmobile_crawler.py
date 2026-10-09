import unittest
from copy import deepcopy
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Plan, Telecom, User, UserSubscription
from parser import PlanTextParser
from services.tco import calculate_tco
from services.crawler.kgmobile_crawler import KgMobileCrawler
from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.pipeline import run_comprehensive_crawler_pipeline
from deploy.refresh_kgmobile import refresh


def sample(**changes):
    row = {'planNo': 779, 'planName': '[평생할인] 데이터 마음대로 (5GB+/100분)',
           'useFlag': 'Y', 'network': '4G', 'basicAmount': 17200,
           'saleList': [{'ltSaleAmount': 14300, 'prSaleAmount': 0}],
           'basicMonthData': '5', 'basicMonthDataUnit': 'GB', 'basicDayData': -1,
           'basicDayDataUnit': 'GB', 'basicQos': '1Mbps', 'basicVoice': '100', 'basicSms': '100',
           'contents': '<p>할인기간 제한이 없는 평생 할인 요금제입니다.</p>'}
    row.update(changes)
    return row


class KgMobileTests(unittest.TestCase):
    def test_lifetime_amount_not_signup_campaign_end(self):
        plan = KgMobileCrawler.parse_plan(sample())
        self.assertEqual((plan['discount_price'], plan['normal_price'], plan['discount_months']), (2900, 17200, -1))
        for months in [6, 12, 24, 36, 48]:
            self.assertEqual(calculate_tco(months, -1, 2900, 17200)['tco'], months * 2900)
        parsed = PlanTextParser.parse(plan['raw_text'])
        self.assertEqual((parsed['base_data_gb'], parsed['qos_speed_mbps'], parsed['voice_minutes'], parsed['sms_count']), (5, 1, 100, 100))

    def test_coupon_duration_not_mobile_price_duration(self):
        plan = KgMobileCrawler.parse_plan(sample(planName='[일반] 5GB+', basicAmount=19300,
                     saleList=[{'ltSaleAmount': 0, 'prSaleAmount': 19290}],
                     contents='<p>쿠폰은 24개월간 지급합니다.</p><p>기본료 할인 프로모션은 가입월 포함 6개월간 적용됩니다.</p>'))
        self.assertEqual((plan['discount_price'], plan['normal_price'], plan['discount_months']), (10, 19300, 6))

    def test_lifetime_and_temporary_discount_combination(self):
        plan = KgMobileCrawler.parse_plan(sample(saleList=[{'ltSaleAmount': 5000, 'prSaleAmount': 2000}],
                      contents='<p>기본료 할인 프로모션은 12개월간 적용됩니다.</p>'))
        self.assertEqual((plan['discount_price'], plan['normal_price'], plan['discount_months']), (10200, 12200, 12))

    def test_missing_discount_or_unknown_duration_rejected(self):
        self.assertIsNone(KgMobileCrawler.parse_plan(sample(saleList=None)))
        self.assertIsNone(KgMobileCrawler.parse_plan(sample(saleList=[{'ltSaleAmount': 0, 'prSaleAmount': 1000}], contents='쿠폰 24개월 지급')))
        self.assertIsNone(KgMobileCrawler.parse_plan(sample(saleList=[{'ltSaleAmount': 20000, 'prSaleAmount': 0}])))

    def test_unlimited_call_sms_and_daily_specs(self):
        plan = KgMobileCrawler.parse_plan(sample(basicVoice='-1', basicSms='-1', basicMonthData='11', basicDayData=2, basicQos='3Mbps'))
        parsed = PlanTextParser.parse(plan['raw_text'])
        self.assertEqual((parsed['base_data_gb'], parsed['daily_data_gb'], parsed['qos_speed_mbps'], parsed['voice_minutes'], parsed['sms_count']), (11, 2, 3, -1, -1))

    def test_daily_only_data_and_no_sms_are_not_missing_specs(self):
        plan = KgMobileCrawler.parse_plan(sample(basicMonthData='-1', basicDayData=5, basicQos='5Mbps', basicSms='-'))
        parsed = PlanTextParser.parse(plan['raw_text'])
        self.assertEqual((parsed['base_data_gb'], parsed['daily_data_gb'], parsed['qos_speed_mbps'], parsed['sms_count']), (0, 5, 5, 0))

    def test_future_and_expired_plans_are_excluded(self):
        now = datetime(2026, 10, 9)
        self.assertFalse(KgMobileCrawler.available(sample(startDate='2026-11-01T00:00:00'), now))
        self.assertFalse(KgMobileCrawler.available(sample(endDate='2026-10-01T00:00:00'), now))
        self.assertFalse(KgMobileCrawler.available(sample(useFlag='N'), now))

    def test_kg_collected_even_without_hub_listing(self):
        crawler = DirectTelecomCrawler(delay_sec=0)
        with patch('services.crawler.direct_crawlers.MASTER_TELECOMS', [{'name': 'KG모바일', 'website_url': KgMobileCrawler.BASE_URL, 'network': 'LGU+'}]), \
             patch.object(crawler, 'discover_all_mvno_brands', return_value=[]), \
             patch('services.crawler.direct_crawlers.KgMobileCrawler.fetch_raw_plans', return_value=[KgMobileCrawler.parse_plan(sample())]):
            self.assertEqual(len(crawler.fetch_raw_plans()), 1)

    def test_failed_kg_keeps_subscription_history_but_excludes_recommendations(self):
        engine = create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        kg, other = Telecom(name='KG모바일'), Telecom(name='Other')
        db.add_all([kg, other]); db.flush()
        def stored(carrier):
            return Plan(telecom_id=carrier.telecom_id, title='Existing', base_data_gb=5, discount_price=2900,
                        normal_price=17200, discount_months=-1, raw_text='', is_active=True, scraped_at=datetime.now())
        old_kg = stored(kg); old_other = stored(other); db.add_all([old_kg, old_other]); db.commit()
        user = User(email='snapshot@example.com'); db.add(user); db.flush()
        db.add(UserSubscription(user_id=user.user_id, plan_id=old_kg.plan_id,
                               start_date=datetime(2026, 1, 1), target_months=12,
                               discount_end_date=datetime(2027, 1, 1))); db.commit()
        raw = KgMobileCrawler.parse_plan(sample()); raw['telecom_name'] = 'Other'
        with patch('services.crawler.pipeline.sync_telecom_master', return_value={'total_master': 2}), \
             patch('services.crawler.pipeline.MvnohubCrawler') as hub, \
             patch('services.crawler.pipeline.DirectTelecomCrawler') as direct:
            hub.return_value.fetch_raw_plans.return_value = [raw]
            hub.return_value.complete = True
            hub.return_value.errors = []
            direct.return_value.fetch_raw_plans.return_value = []
            direct.return_value.failed_telecom_names = {'KG모바일'}
            result = run_comprehensive_crawler_pipeline(db=db)
        self.assertTrue(result['success']); self.assertEqual(result['failed_telecoms'], ['KG모바일'])
        db.expire_all()
        self.assertFalse(db.get(Plan, old_kg.plan_id).is_active)
        self.assertEqual(db.query(Plan).filter(Plan.telecom_id == kg.telecom_id).count(), 1)
        db.close(); engine.dispose()

    def test_targeted_refresh_idempotent_and_preserves_old_subscription(self):
        engine = create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        raw = KgMobileCrawler.parse_plan(sample())
        with patch.object(KgMobileCrawler, 'fetch_raw_plans', return_value=[raw]):
            first = refresh(db); second = refresh(db)
        self.assertEqual((first['inserted'], second['inserted']), (1, 0))
        plan = db.query(Plan).one()
        user = User(email='member@example.com'); db.add(user); db.flush()
        subscription = UserSubscription(user_id=user.user_id, plan_id=plan.plan_id,
                                       start_date=datetime(2026, 1, 1), target_months=12, discount_end_date=datetime(2027, 1, 1))
        db.add(subscription); db.commit()
        changed = deepcopy(raw); changed['discount_price'] = 3100
        with patch.object(KgMobileCrawler, 'fetch_raw_plans', return_value=[changed]): refresh(db)
        self.assertEqual(subscription.plan_id, plan.plan_id); self.assertEqual(plan.discount_price, 2900)
        self.assertFalse(plan.is_active); self.assertEqual(db.query(Plan).count(), 2)
        db.close(); engine.dispose()


if __name__ == '__main__': unittest.main()
