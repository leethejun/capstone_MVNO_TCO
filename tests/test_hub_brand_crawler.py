import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Telecom, Plan
from bs4 import BeautifulSoup
from parser import PlanTextParser
from deploy.refresh_hub_snapshot import apply_snapshot, load_snapshot
from services.crawler.hub_brand_crawler import HubBrandCrawler, HubCatalogChanged, merge_hub_records
from services.crawler.direct_crawlers import DirectTelecomCrawler


class HubBrandTests(unittest.TestCase):
    def test_catalog_change_retries_whole_snapshot_and_never_returns_partial_result(self):
        c=HubBrandCrawler('이지모바일','https://www.mvnohub.kr/brand/plan/15.do')
        with patch.object(c,'_fetch_once',side_effect=[HubCatalogChanged('목록 변경'),['완료된 전체 목록']]) as fetch, \
             patch('services.crawler.hub_brand_crawler.time.sleep'):
            self.assertEqual(c.fetch_raw_plans(),['완료된 전체 목록'])
        self.assertEqual(fetch.call_count,2)

    def test_apply_gate_rejects_partial_manifest_and_missing_global_product(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);url='https://www.mvnohub.kr/brand/plan/9.do'
            def write(name,value):(root/name).write_text(json.dumps(value))
            write('brands.json',[dict(name='프리티',brand_plan_url=url)])
            write('results.json',[])
            with self.assertRaises(ValueError):load_snapshot(root)
            write('results.json',[dict(name='프리티',url=url,brand_id='9',complete=True,total=1,collected=1)])
            write('brand-9-records.json',[dict(telecom_name='프리티',_hub_product_id='1',title='상품',discount_price=1000,normal_price=2000,discount_months=6)])
            write('global-records.json',dict(complete=True,errors=[],records=[dict(_hub_product_id='2')]))
            with self.assertRaisesRegex(ValueError,'상품 ID 대조 실패'):load_snapshot(root)

    def test_monthly_allowance_wins_over_daily_minutes_in_product_name(self):
        specs=PlanTextParser.parse('쏙쏙 매일30분5GB 문자100건혜택 | 데이터 5GB | 통화 900분 | 문자 300건')
        self.assertEqual((specs['voice_minutes'],specs['sms_count']),(900,300))

    def test_hidden_unlimited_detail_speed_requires_matching_explicit_list_speed(self):
        c=HubBrandCrawler('이지모바일','https://www.mvnohub.kr/brand/plan/15.do')
        fields={'기본 데이터':'무제한','데이터 소진 후 용량':'일 5GB','기본 통화':'무제한',
                '기본 문자':'무제한','통신사':'이지모바일','통신 규격':'LTE','통신망':'LGU+'}
        soup=BeautifulSoup('<div class="gray_box">'+''.join(f'<dl><dt>{k}</dt><dd>{v}</dd></dl>' for k,v in fields.items())+'</div>','html.parser')
        plan=dict(title='매일5GB',raw_text='데이터 5GB + 5Mbps [출처: 알뜰폰허브]')
        c.apply_detail(plan,dict(networkProtocol='LTE',dataAfter='5Mbps'),soup)
        specs=PlanTextParser.parse(plan['raw_text'])
        self.assertEqual((specs['daily_data_gb'],specs['qos_speed_mbps']),(5,5))
        with self.assertRaises(ValueError):
            c.apply_detail(dict(title='상품',raw_text='데이터 5GB [출처: 알뜰폰허브]'),dict(networkProtocol='LTE',dataAfter='5Mbps'),soup)

    def test_snapshot_preserves_distinct_sale_ids_and_existing_history(self):
        engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine)
        db=sessionmaker(bind=engine)()
        carrier=Telecom(name='프리티');db.add(carrier);db.flush()
        old=Plan(telecom_id=carrier.telecom_id,title='과거',network_type='LTE',base_data_gb=1,
                 discount_price=1000,normal_price=2000,discount_months=6,is_active=True,
                 raw_text='[출처: 프리티 브랜드전용관]',scraped_at=datetime.now())
        db.add(old);db.commit()
        def record(pid):
            return dict(telecom_name='프리티',_hub_product_id=pid,title='같은 스펙',network_type='LTE',
                        discount_price=1000,normal_price=2000,discount_months=6,
                        raw_text=f'데이터 5GB | 통화 100분 | 문자 100건 [출처: 알뜰폰허브] [허브 상품 ID: {pid}]')
        rows={'프리티':[record('1'),record('2')]}
        first=apply_snapshot(db,rows);db.commit();second=apply_snapshot(db,rows);db.commit();db.refresh(old)
        self.assertEqual((first[0]['inserted'],second[0]['inserted']),(2,0))
        self.assertEqual(db.query(Plan).filter(Plan.is_active==True).count(),2)
        self.assertFalse(old.is_active)
        self.assertEqual(db.query(Plan).count(),3)
        db.close();engine.dispose()

    def test_zero_products_requires_agreement_between_api_and_html(self):
        c=HubBrandCrawler('KB리브모바일','https://www.mvnohub.kr/brand/plan/3.do',delay_sec=0)
        value=dict(totalElements=0,totalPages=0,number=0,hasNext=False,content=[])
        with patch.object(c,'_get',side_effect=[Mock(json=lambda:value),Mock(content=b'<div class="list_plan_set"></div>')]):
            self.assertEqual(c.fetch_raw_plans(),[])
        self.assertTrue(c.complete)
        with patch.object(c,'_get',side_effect=[Mock(json=lambda:value),Mock(content=b'<div class="list_plan_set"><div class="plan_card"></div></div>')]),self.assertRaises(ValueError):
            c.fetch_raw_plans()
        self.assertFalse(c.complete)

    def test_freet_both_network_branches_are_preserved_in_one_carrier(self):
        rows=[dict(name='프리티 (LGU+망)',home_url='https://www.freet.co.kr',brand_plan_url='https://www.mvnohub.kr/brand/plan/9.do'),
              dict(name='프리티 (SKT, KT망)',home_url='https://www.freet.co.kr',brand_plan_url='https://www.mvnohub.kr/brand/plan/17.do')]
        merged=DirectTelecomCrawler.merge_brands(rows)
        freet=[row for row in merged if row['name']=='프리티']
        self.assertEqual(len(freet),1)
        self.assertEqual(set(freet[0]['brand_plan_urls']),{row['brand_plan_url'] for row in rows})

    def test_brand_discovery_outage_still_has_known_brand_urls(self):
        rows={row['name']:row for row in DirectTelecomCrawler.merge_brands([])}
        self.assertEqual(rows['아시아모바일']['brand_plan_urls'],['https://www.mvnohub.kr/brand/plan/21.do'])
        self.assertEqual(len(rows['프리티']['brand_plan_urls']),2)

    def test_detailed_id_wins_and_global_only_id_is_not_dropped(self):
        old=dict(_hub_product_id='1',title='같은 상품',raw_text='데이터 11GB')
        detail=dict(old,raw_text='데이터 11GB + 일 2GB')
        extra=dict(_hub_product_id='2',title='전역 전용 상품')
        official=dict(title='공식몰 상품')
        self.assertEqual(merge_hub_records([old,extra],[detail,official]),[extra,detail,official])
        stale=dict(_hub_product_id='3',title='판매 종료 상품',telecom_name='유니컴즈')
        self.assertEqual(merge_hub_records([stale,extra],[detail],complete_carriers=['모빙']),[extra,detail])

    def test_new_shared_branch_collector_not_first_page_parser(self):
        c=DirectTelecomCrawler()
        with patch('services.crawler.hub_brand_crawler.HubBrandCrawler') as cls:
            cls.return_value.fetch_raw_plans.return_value=[dict(title='second page item')]
            cls.return_value.total=13;cls.return_value.pages=2;cls.return_value.complete=True
            result=c._crawl_brand_hub_page('티플러스','https://www.mvnohub.kr/brand/plan/18.do')
        self.assertEqual(len(result),1)
        self.assertEqual(c._official_metadata['티플러스']['hub_total'],13)
        self.assertTrue(c._official_metadata['티플러스']['hub_complete'])


if __name__=='__main__':unittest.main()
