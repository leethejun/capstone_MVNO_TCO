import unittest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Telecom, Plan
from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.telecom_registry import MASTER_TELECOMS, canonical_telecom_name, is_excluded_telecom
from services.crawler.pipeline import run_comprehensive_crawler_pipeline


class CoverageTests(unittest.TestCase):
    def test_explicitly_excluded_carrier_cannot_return_from_hub(self):
        for name in ['앤텔레콤', '엔텔레콤', '(주)앤알커뮤니케이션', 'Ntelecom']:
            self.assertTrue(is_excluded_telecom(name))
        self.assertFalse(is_excluded_telecom('한국E텔레콤'))
        self.assertTrue(is_excluded_telecom('다른 표기', 'https://info.n-telecom.co.kr/plans'))
        self.assertNotIn('앤텔레콤', {x['name'] for x in MASTER_TELECOMS})
        hub=[{'name':'앤텔레콤','home_url':'https://www.n-telecom.co.kr','brand_plan_url':'/brand/1'}]
        self.assertFalse(any(is_excluded_telecom(x['name']) for x in DirectTelecomCrawler.merge_brands(hub)))
        crawler=DirectTelecomCrawler()
        with patch('services.crawler.direct_crawlers.requests.get') as get:
            self.assertEqual(crawler._crawl_brand_official_site('앤텔레콤', 'https://www.n-telecom.co.kr', 'KT'), [])
        get.assert_not_called()

    def test_explicit_corporate_aliases_do_not_merge_similar_unknown_names(self):
        self.assertEqual(canonical_telecom_name('에스케이텔링크'), 'SK 7mobile')
        self.assertEqual(canonical_telecom_name('KB국민은행'), 'KB리브모바일')
        self.assertEqual(canonical_telecom_name('이야기새통신사'), '이야기새통신사')

    def test_hub_outage_keeps_all_master_targets(self):
        brands = DirectTelecomCrawler.merge_brands([])
        self.assertEqual({b['name'] for b in brands}, {b['name'] for b in MASTER_TELECOMS})

    def test_host_alias_and_hub_only_brand_are_kept(self):
        master = [{'name': 'Master', 'website_url': 'https://www.example.org', 'network': 'KT'}]
        hub = [{'name': 'Alias', 'home_url': 'https://example.org/', 'brand_plan_url': '/brand/1'},
               {'name': 'New', 'home_url': 'https://new.org', 'brand_plan_url': '/brand/2'}]
        with patch('services.crawler.direct_crawlers.MASTER_TELECOMS', master):
            brands = DirectTelecomCrawler.merge_brands(hub)
        self.assertEqual(len(brands), 2)
        self.assertEqual(brands[0]['name'], 'Master')
        self.assertEqual(brands[0]['brand_plan_url'], '/brand/1')

    def test_failed_official_is_reported_even_with_hub_fallback(self):
        crawler = DirectTelecomCrawler(delay_sec=0)
        with patch('services.crawler.direct_crawlers.MASTER_TELECOMS', []), \
             patch.object(crawler, 'discover_all_mvno_brands', return_value=[{'name':'A', 'home_url':'https://example.org', 'brand_plan_url':'/brand/1'}]), \
             patch.object(crawler, '_crawl_brand_official_site', side_effect=ValueError('API changed')), \
             patch.object(crawler, '_crawl_brand_hub_page', return_value=[]):
            crawler.fetch_raw_plans()
        self.assertEqual(crawler.failed_telecom_names, {'A'})
        self.assertEqual(crawler.coverage[0]['error'], 'API changed')

    def test_full_refresh_removes_missing_carrier_without_accumulating_plans(self):
        engine = create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        carrier = Telecom(name='Missing'); db.add(carrier); db.flush()
        old = Plan(telecom_id=carrier.telecom_id, title='Existing', base_data_gb=1, discount_price=1000,
                   normal_price=1000, discount_months=-1, raw_text='', is_active=True, scraped_at=datetime.now())
        db.add(old); db.commit(); old_id = old.plan_id
        record = {'telecom_name':'Collected', 'title':'New', 'network_type':'LTE', 'discount_price':2000,
                  'normal_price':3000, 'discount_months':6, 'raw_text':'데이터 5GB 통화 100분 문자 100건'}
        with patch('services.crawler.pipeline.sync_telecom_master', return_value={'total_master':2}), \
             patch('services.crawler.pipeline.MvnohubCrawler') as hub, \
             patch.dict('os.environ', {'CRAWLER_REPORT_PATH':'/tmp/test-crawler-coverage.json'}):
            hub.return_value.fetch_raw_plans.return_value = [record]
            hub.return_value.complete = True
            hub.return_value.errors = []
            first = run_comprehensive_crawler_pipeline(db=db, include_direct=False, max_pages=0)
            second = run_comprehensive_crawler_pipeline(db=db, include_direct=False, max_pages=0)
        self.assertTrue(first['success']); self.assertTrue(second['success'])
        self.assertEqual(db.query(Plan).filter(Plan.telecom_id == carrier.telecom_id).count(), 0)
        self.assertEqual((first['inserted'], second['inserted'], db.query(Plan).count()), (1,1,1))
        db.close(); engine.dispose()
