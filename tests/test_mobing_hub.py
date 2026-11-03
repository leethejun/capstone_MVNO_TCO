import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bs4 import BeautifulSoup

from parser import PlanTextParser
from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.mobing_hub_crawler import MobingHubCrawler
from services.crawler.pipeline import run_comprehensive_crawler_pipeline
from models import Base, Telecom, Plan
from deploy.refresh_mobing_hub import replace_hub_snapshot


def product(pid=1, **changes):
    value = dict(productId=pid, partnerName='유니컴즈', productName='모빙 11GB+',
                 monthlyPaymentFee=1000, baseMonthlyFee=30000, planDiscountAmount=10000,
                 contractDiscountPeriod=7, contractDiscountAmount=19000,
                 networkProtocol='LTE', dataAfter='3Mbps')
    value.update(changes)
    return value


def parsed_card(pid=1):
    return dict(_product_id=str(pid),telecom_name='유니컴즈',title='모빙 11GB+',network_type='LTE',
                discount_price=1000,normal_price=20000,discount_months=7,
                raw_text='모빙 11GB+ | 데이터 11GB+3Mbps | 통화 무제한 | 문자 무제한 [출처: 알뜰폰허브]')


class MobingHubTests(unittest.TestCase):
    def test_scoped_refresh_preserves_history_and_other_carriers_and_is_idempotent(self):
        engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
        db=sessionmaker(bind=engine)()
        carrier=Telecom(name='모빙');other=Telecom(name='다른통신사');db.add_all([carrier,other]);db.flush()
        def old(tid,title,raw):
            return Plan(telecom_id=tid,title=title,network_type='LTE',base_data_gb=1,discount_price=1000,
                        normal_price=2000,discount_months=6,raw_text=raw,is_active=True,scraped_at=datetime.now())
        history=old(carrier.telecom_id,'과거 상품','[출처: 알뜰폰허브]')
        official=old(carrier.telecom_id,'공식몰 상품','[출처: 모빙 공식홈페이지]')
        unrelated=old(other.telecom_id,'다른 상품','[출처: 알뜰폰허브]')
        db.add_all([history,official,unrelated]);db.commit()
        record=dict(telecom_name='모빙',title='새 상품',network_type='LTE',discount_price=1000,
                    normal_price=20000,discount_months=7,raw_text='데이터 11GB + 일 2GB + 3Mbps | 통화 무제한 | 문자 무제한 [출처: 알뜰폰허브]')
        first=replace_hub_snapshot(db,[record]);db.commit()
        second=replace_hub_snapshot(db,[record]);db.commit();db.refresh(history)
        self.assertEqual((first['inserted'],second['inserted']),(1,0))
        self.assertFalse(history.is_active)
        self.assertTrue(official.is_active and unrelated.is_active)
        self.assertEqual(db.query(Plan).count(),4)
        db.close();engine.dispose()

    def test_failed_full_hub_fallback_aborts_before_database_replacement(self):
        db=Mock()
        with patch('services.crawler.pipeline.MvnohubCrawler') as hub, \
             patch.dict('os.environ',{'CRAWLER_REPORT_PATH':'/tmp/test-mobing-hub-failure.json'}):
            hub.return_value.fetch_raw_plans.return_value=[]
            hub.return_value.complete=True;hub.return_value.errors=[]
            direct=Mock();direct.fetch_raw_plans.return_value=[];direct.failed_telecom_names={'모빙'}
            direct.coverage=[dict(name='모빙',hub_complete=False,official_count=0)]
            result=run_comprehensive_crawler_pipeline(db=db,direct_crawler=direct)
        self.assertFalse(result['success'])
        self.assertIn('모빙',result['error'])
        db.query.assert_not_called();db.rollback.assert_called_once()

    def test_restoration_price_keeps_permanent_discount(self):
        with patch('services.crawler.mobing_hub_crawler.MvnohubCrawler._parse_card',return_value=parsed_card()):
            result=MobingHubCrawler.parse(product(),object())
        self.assertEqual((result['telecom_name'],result['normal_price'],result['discount_months']),('모빙',20000,7))
        self.assertIn('[허브 상품 ID: 1]',result['raw_text'])

    def test_unverified_price_or_wrong_carrier_fails(self):
        with patch('services.crawler.mobing_hub_crawler.MvnohubCrawler._parse_card',return_value=parsed_card()):
            with self.assertRaises(ValueError):
                MobingHubCrawler.parse(product(contractDiscountAmount=1),object())
            with self.assertRaises(ValueError):
                MobingHubCrawler.parse(product(partnerName='다른통신사'),object())

    def test_detail_recovers_daily_data_and_ignores_other_seller_labels(self):
        fields={'기본 데이터':'11GB','데이터 소진 후 속도':'3Mbps','데이터 소진 후 용량':'일 2GB',
                '기본 통화':'무제한','기본 문자':'무제한','통신사':'유니컴즈','통신 규격':'LTE','통신망':'LGU+'}
        html='<div class="gray_box">'+''.join(f'<dl><dt>{k}</dt><dd>{v}</dd></dl>' for k,v in fields.items())+'</div><dl><dt>통신사</dt><dd>LGU+</dd></dl>'
        plan=parsed_card(); MobingHubCrawler.apply_detail(plan,product(),BeautifulSoup(html,'html.parser'))
        specs=PlanTextParser.parse(plan['raw_text'])
        self.assertEqual((specs['base_data_gb'],specs['daily_data_gb'],specs['qos_speed_mbps']),(11,2,3))

    def test_all_pages_and_details_checked_against_declared_total(self):
        c=MobingHubCrawler(delay_sec=0); c.SIZE=2
        events=[]
        def get(session,url,params):
            if url.endswith('/filter'):
                events.append('list')
                n=params['page']; ids=[1,2] if n==0 else [3]
                return Mock(json=lambda:dict(content=[product(pid=i) for i in ids],number=n,
                    totalElements=3,totalPages=2,hasNext=n==0))
            if url==c.URL:
                ids=[1,2] if params['page']==0 else [3]
                return Mock(content=('<div class="list_plan_set">'+''.join(f'<div class="plan_card" data-product-id="{i}"></div>' for i in ids)+'</div>').encode())
            events.append('detail')
            return Mock(content=b'<html></html>')
        with patch.object(c,'_get',side_effect=get),patch.object(c,'parse',side_effect=lambda item,card:dict(id=item['productId'])),patch.object(c,'apply_detail') as detail:
            result=c.fetch_raw_plans()
        self.assertEqual((len(result),c.total,c.pages,c.complete,detail.call_count),(3,3,2,True,3))
        self.assertLess(max(i for i,v in enumerate(events) if v=='list'),events.index('detail'))

    def test_api_page_truncation_fails_without_complete_flag(self):
        c=MobingHubCrawler(delay_sec=0)
        value=dict(content=[product()],number=0,totalElements=13,totalPages=2,hasNext=True)
        with patch.object(c,'_get',return_value=Mock(json=lambda:value)),self.assertRaises(ValueError):
            c.fetch_raw_plans()
        self.assertFalse(c.complete)

    def test_official_failure_still_returns_complete_hub_fallback(self):
        c=DirectTelecomCrawler(delay_sec=0)
        row=dict(telecom_name='모빙',title='모빙 11GB+',network_type='LTE',discount_price=1000,
                 normal_price=20000,discount_months=7,raw_text='데이터 11GB [출처: 알뜰폰허브]')
        with patch.object(c,'merge_brands',return_value=[dict(name='모빙',home_url='https://www.mobing.co.kr',brand_plan_url='',network='')]), \
             patch.object(c,'discover_all_mvno_brands',return_value=[]), \
             patch.object(c,'_crawl_brand_official_site',return_value=[]), \
             patch('services.crawler.mobing_hub_crawler.MobingHubCrawler') as hub:
            hub.return_value.fetch_raw_plans.return_value=[row]
            hub.return_value.total=1;hub.return_value.pages=1;hub.return_value.complete=True
            result=c.fetch_raw_plans()
        self.assertEqual(result,[row])
        self.assertEqual(c.coverage[0]['status'],'hub_fallback')
        self.assertTrue(c.coverage[0]['hub_complete'])
        self.assertEqual(c.coverage[0]['official_count'],0)
        self.assertNotIn('모빙',c.failed_telecom_names)


if __name__=='__main__':
    unittest.main()
