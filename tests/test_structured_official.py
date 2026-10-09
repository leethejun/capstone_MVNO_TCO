import json
import unittest
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
from parser import PlanTextParser
from services.crawler.structured_official import (PinCrawler, AlbireoCrawler, MonaCrawler,
    GmeCrawler, EumCrawler, S1Crawler, ShakeCrawler, flight_objects, record)
from services.crawler.kb_crawler import KbCrawler


class StructuredOfficialTests(unittest.TestCase):
    def pin(self, **changes):
        item=dict(hiddenYN='N',contractSupportYN='N',salesStartAt='2020-01-01T00:00:00Z',salesEndAt='2099-01-01T00:00:00Z',
            price=61600,lifetimeDiscountPrice=17600,discountPrice=9100,discountPeriod=7,name='100GB+',uuid='sample',
            plan=dict(onSaleYn='Y',basicData=100000,dailyData=0,qos=5000,voice=-1,message=-1,provider='LGU+',network='LTE'))
        item.update(changes);return PinCrawler.parse(item)

    def test_discount_amount_is_not_monthly_price(self):
        p=self.pin()
        self.assertEqual((p['discount_price'],p['normal_price'],p['discount_months']),(34900,44000,7))
        self.assertEqual(PlanTextParser.parse(p['raw_text'])['qos_speed_mbps'],5)

    def test_lifetime_original_price_is_preserved(self):
        p=self.pin(discountPrice=0,lifetimeDiscountPrice=35200)
        self.assertEqual((p['discount_price'],p['normal_price'],p['discount_months']),(26400,61600,-1))

    def test_contract_and_expired_offers_are_not_recommended(self):
        self.assertIsNone(self.pin(contractSupportYN='Y'))
        self.assertIsNone(self.pin(salesEndAt='2021-01-01T00:00:00Z'))

    def test_temporary_discount_requires_period(self):
        with self.assertRaises(ValueError):self.pin(discountPeriod=0)

    def test_partial_albireo_page_fails_before_returning_snapshot(self):
        response=Mock();response.json.return_value={'success':True,'data':{'content':[{}],'last':True,'totalElements':2}}
        with patch('services.crawler.structured_official.requests.get',return_value=response):
            with self.assertRaises(ValueError):AlbireoCrawler().fetch_raw_plans()

    def test_albireo_post_promotion_bill_is_not_original_sticker(self):
        p=AlbireoCrawler.parse(dict(type='POSTPAID',discountSteps={},monthlyFee=6600,periodDiscountMonths=7,
            feeAfterPeriodDiscount=12000,baseFee=16500,throttleSpeedKbps=400,dataDisplay='6GB',voiceDisplay='100분',
            smsDisplay='100건',name='sample',mnoCode='SKT',code='s',networkType='LTE'))
        self.assertEqual((p['normal_price'],p['discount_price']),(12000,6600))

    def test_mona_free_promotion_and_official_lifetime_sentinel(self):
        item=dict(GDNM='sample',GDDESC='',TT_AMT='33,000',EVENT_PERIOD='7',DISCOUNT='0',SEEDATA='7GB',SEEVOICE='기본제공',SEELETTER='기본제공',MNO_CD='LGU+',GDCD='s',NETDIV='LTE')
        self.assertEqual(MonaCrawler.parse(item)['discount_price'],0)
        item.update(EVENT_PERIOD='120',DISCOUNT='12,000')
        self.assertEqual(MonaCrawler.parse(item)['discount_months'],-1)

    def test_gme_discount_field_is_the_bill(self):
        item=dict(GDNM='sample',GDDESC='평생 할인',TT_AMT='14,300',DISCOUNT='7,700',DATAAMOUNT='3GB',ADD_DATA='',QOSFG='1',QOSAMT='1Mbps',VOICEAMOUNT='100분',LETTERAMOUNT='100건',MNO_CD='KT',GDCD='s')
        self.assertEqual(GmeCrawler.parse(item)['discount_price'],7700)

    def test_daily_only_spec_does_not_read_monthly_marketing_title(self):
        p=record('sample','최대170GB',10000,10000,0,'하루 5GB + 5Mbps','무제한','무제한','KT','s')
        parsed=PlanTextParser.parse(p['raw_text'])
        self.assertEqual((parsed['base_data_gb'],parsed['daily_data_gb'],parsed['qos_speed_mbps']),(0,5,5))

    def test_erel_binary_data_units_and_unknown_discount(self):
        item=dict(name='6GB',data=6144,isDataQos=True,dataQos=1,voc=0,sms=0,isVocInfinity=True,isSmsInfinity=True,
            salePrice=6600,basePrice=22000,originalPrice=13200,discountUnit='month',discountPeriod=7,mnoGubun='KT',code='s')
        p=EumCrawler.parse(item,'에르엘')
        self.assertEqual(PlanTextParser.parse(p['raw_text'])['base_data_gb'],6)
        self.assertEqual(p['normal_price'],13200)
        item['discountUnit']=None
        with self.assertRaises(ValueError):EumCrawler.parse(item,'에르엘')

    def test_shake_permanent_discount_after_temporary_period(self):
        p=ShakeCrawler.parse(dict(ltediv='DISCNT7',amt=50600,tt_AMT=8900,promo_MM=7,life_TIME_DISCOUNT=5000,
            seedata='매일5GB + 5Mbps (최대170GB)',gdnm='일5GB',voiceamountv='무제한',letteramountv='무제한',gdcd='s',netdiv='LTE'))
        self.assertEqual((p['discount_price'],p['normal_price'],p['discount_months']),(8900,45100,7))
        parsed=PlanTextParser.parse(p['raw_text'])
        self.assertEqual((parsed['base_data_gb'],parsed['daily_data_gb']),(0,5))

    def test_s1_device_is_excluded_and_end_fee_is_used(self):
        self.assertIsNone(S1Crawler.parse(dict(catCode='P0301',chargePlanNm='안심 디바이스 10K')))
        p=S1Crawler.parse(dict(catCode='P0301',chargePlanNm='안심100GB',bassChrge=56000,chrgeDscnt=16000,promoSalePrice=30000,
            addDispMsg='7개월 후 44,000원',dataServing='100GB',dataServeAddInfo='5Mbps',dmstcTalkServing='기본제공',smsServing='기본제공',mno='KT',chargePlanSn='s'))
        self.assertEqual((p['discount_price'],p['normal_price'],p['discount_months']),(11000,44000,7))

    def test_flight_json_immediately_after_string_record(self):
        payload='a:T3,foo1b:{"initialDeals":{"list":[{"name":"sample"}],"total":1}}\n'
        soup=BeautifulSoup('<script>self.__next_f.push('+json.dumps([1,payload])+')</script>','html.parser')
        self.assertTrue(any('initialDeals' in x for x in flight_objects(soup)))

    def test_kb_optional_card_banner_does_not_exclude_general_product(self):
        html='<div class="biz_info_wrap"><div class="badge_wrap">요금제 혜택</div>기간 제한 없는 기본 요금</div><div class="biz_info_wrap"><div class="badge_wrap">카드 청구할인혜택</div>카드 실적 70만원</div>'
        self.assertEqual(KbCrawler.product_conditions({'srvDtlDesc':html}),'요금제 혜택 기간 제한 없는 기본 요금')
        self.assertIn('급여이체',KbCrawler.product_conditions({'srvDtlDesc':'<div class="biz_info_wrap">급여이체 조건</div>'}))
