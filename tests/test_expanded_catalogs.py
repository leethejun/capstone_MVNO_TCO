import unittest
from unittest.mock import patch, Mock
from bs4 import BeautifulSoup
from services.crawler.expanded_catalogs import AMobileCrawler, SkylifeCrawler, TossCrawler
from services.crawler.eyagi_crawler import EyagiCrawler
from services.crawler.menu_cards import detail_base
from services.crawler.menu_catalog import stable_url
from parser import PlanTextParser


class ExpandedCatalogTests(unittest.TestCase):
    def test_amobile_temporary_discount_restores_permanently_discounted_price(self):
        item={'요금제명':'데이터','기본료':'30000','할인요금':'9','추가할인개월수':'7',
              '평생할인여부':'N','알뜰할인':'20000','무료데이타':'11GB + 매일 2GB + 3Mbps',
              '무료음성':'기본제공','무료문자':'100','통신사':'KT','요금제구성ID':'A','망구분':'LTE'}
        p=AMobileCrawler.parse(item)
        self.assertEqual((p['discount_price'],p['normal_price'],p['discount_months']),(9,10000,7))
        parsed=PlanTextParser.parse(p['raw_text'])
        self.assertEqual((parsed['base_data_gb'],parsed['daily_data_gb'],parsed['qos_speed_mbps']),(11,2,3))

    def test_editor_table_permanent_discount_is_only_subtracted_after_temporary_promotion(self):
        soup=BeautifulSoup('<table><tr><td>기본료</td><td>평생 할인</td></tr><tr><td>33,000원</td><td>11,000원</td></tr></table>','html.parser')
        self.assertEqual(detail_base(soup),33000)
        self.assertEqual(detail_base(soup,True),22000)

    def test_session_id_does_not_create_new_product(self):
        self.assertEqual(stable_url('https://a/rate_plan.do;jsessionid=ABC?type=T1'), 'https://a/rate_plan.do?type=T1')

    def test_sky_billing_month_is_not_promotion_duration_and_daily_data_is_separate(self):
        p=SkylifeCrawler.parse({'name':'매일5GB','type':'MOBILE_PLAN','code':'A',
            'price':{'baseFee':50000,'default':[{'period':{'unit':'월','value':1},'fee':30000}]},
            'properties':{'data':{'description':'매일 5GB','limit':5,'unit':'GB','qosLimit':5,'qosUnit':'Mbps'},
                          'voice':{'unit':'기본제공'},'message':{'unit':'기본제공'},'network':{'type':'LTE'}}})
        self.assertEqual(p['discount_months'],-1)
        parsed=PlanTextParser.parse(p['raw_text'])
        self.assertEqual((parsed['base_data_gb'],parsed['daily_data_gb']),(0,5))

    def eyagi(self,**changes):
        item=dict(comm_code='A',agent_code='SHOP',comm_name='기본요금제',mno_gubun='lgt',pay_type='2',
                  base_fee='56,100',selling_price='16,500',restoration_fee='39,600',terms='7',terms_str='t12',
                  free_data_str='11GB',add_data='매일 2GB',qos='400K',call_str='기본제공',sms_str='100건',
                  evnt_start_date='20200101000000',evnt_end_date='99991231235959',is_5g_yn='LTE')
        item.update(changes);return item

    def test_eyagi_uses_exact_months_not_tab_label_and_restoration_fee(self):
        p=EyagiCrawler.parse(self.eyagi())
        self.assertEqual((p['normal_price'],p['discount_months']),(39600,7))
        parsed=PlanTextParser.parse(p['raw_text'])
        self.assertEqual((parsed['daily_data_gb'],parsed['qos_speed_mbps']),(2,.4))

    def test_eyagi_prepaid_is_not_general_postpaid(self):
        self.assertIsNone(EyagiCrawler.parse(self.eyagi(pay_type='1')))

    def test_eyagi_no_discount_fields_is_normal_price(self):
        p=EyagiCrawler.parse(self.eyagi(base_fee='',restoration_fee='',terms='',terms_str='',evnt_start_date=None,evnt_end_date=None))
        self.assertEqual((p['normal_price'],p['discount_months']),(16500,0))

    def test_eyagi_incomplete_columns_fail_before_replacement(self):
        response=Mock();response.json.return_value={'num':3,'data':{}}
        with patch('services.crawler.eyagi_crawler.requests.post',return_value=response):
            with self.assertRaises(ValueError): EyagiCrawler().fetch_raw_plans()

    def test_toss_signup_window_does_not_become_discount_duration(self):
        item={'displayName':'요금제','costType':'정액','monthlyFee':30000,'promotionDiscountAmount':0,
              'discountPolicyList':[{'applyStartTs':'2020-01-01T00:00:00','applyEndTs':'2099-12-31T23:59:59','startMonthIndex':0,'numberOfMonths':7,'amount':20000}],
              'dataUsage':{'basicAmount':11,'dailyAmount':2,'speedLimit':3,'speedLimitUnit':'Mbps'},
              'callUsage':{'type':'UNLIMITED'},'messageUsage':{'type':'UNLIMITED'},'mnoCarrier':'KT','id':'A','network':'LTE'}
        p=TossCrawler.parse(item)
        self.assertEqual((p['discount_price'],p['normal_price'],p['discount_months']),(10000,30000,7))
        item['discountPolicyList'].append(item['discountPolicyList'][0])
        with self.assertRaises(ValueError):TossCrawler.parse(item)


class WholeCatalogTests(unittest.TestCase):
    def test_gnuboard_follows_network_buttons_and_pagination(self):
        from urllib.parse import parse_qs,urlsplit
        from services.crawler.gnuboard_plans import GnuboardCatalogCrawler
        def get(url,**kwargs):
            q=parse_qs(urlsplit(url).query)
            if q.get('page')==['2']:code='3';links=''
            elif q.get('sca2')==['KT']:code='2';links="<a href='?bo_table=pricList&sca=후불&sca2=KT&page=2'>2</a>"
            else:code='1';links="<button onclick=\"location.href='?bo_table=pricList&sca=후불&sca2=KT'\">KT</button>"
            response=Mock();response.content=(f'<div data-code="{code}"></div>'+links).encode();return response
        def parse(soup,name,url):
            code=soup.select_one('[data-code]')['data-code']
            return [dict(title=code,discount_price=100,normal_price=100,discount_months=0,
                         raw_text=f'[상품 URL: https://www.valuecomm.co.kr/bbs/board.php?bo_table=pricList&wr_id={code}&sca=후불]')]
        with patch('services.crawler.gnuboard_plans.requests.get',side_effect=get),patch('services.crawler.gnuboard_plans.parse_gnuboard',side_effect=parse):
            crawler=GnuboardCatalogCrawler('밸류컴');rows=crawler.fetch_raw_plans()
        self.assertEqual({r['title'] for r in rows},{'1','2','3'})
        self.assertEqual(crawler.skipped,[])

    def test_ktm_does_not_add_conditional_bonus_to_monthly_data(self):
        from services.crawler.ktm_crawler import KtmCrawler
        item={'rateAdsvcNm':'요금제','useYn':'Y','mmBasAmtVatDesc':'55000','promotionAmtVatDesc':'30000',
              'usePrd':'0','dateType':'1','bnfitData':'11GB + 매일 2GB + 3Mbps','promotionBnfitData':'24개월 150GB',
              'bnfitVoice':'기본제공','bnfitSms':'기본제공','rateAdsvcCd':'A'}
        row=KtmCrawler.parse(item);p=PlanTextParser.parse(row['raw_text'])
        self.assertEqual((p['base_data_gb'],p['daily_data_gb']),(11,2))
        item['usePrd']='12'
        with self.assertRaises(ValueError):KtmCrawler.parse(item)


class LargeCarrierTests(unittest.TestCase):
    def hello(self,**changes):
        item=dict(dedicatedPriceGubun='N',salesName='요금제',directPromotionDirectmallPrice='7500',defaultPrice='24000',
                  directPromotionInfotext='P',directPromotionAfterMonthChk='7',directPromotionAfterPrice='11550',
                  dedicatedMonthlyOfferGubun='G',dedicatedMonthlyOfferValue='11',dedicatedDailyOfferGubun='G',
                  dedicatedDailyOfferValue='2',dedicatedDataDepletionRate='3',dedicatedCallsGubun='L',dedicatedCallsValue='',
                  dedicatedSmsGubun='B',dedicatedSmsValue='100',telecom='LGU',paymentcode='A',usimType='LTE')
        item.update(changes);return item

    def test_hello_after_promotion_price_is_not_undiscounted_list_price(self):
        from services.crawler.large_carriers import HelloCrawler
        p=HelloCrawler.parse(self.hello())
        self.assertEqual((p['discount_price'],p['normal_price'],p['discount_months']),(7500,11550,7))
        parsed=PlanTextParser.parse(p['raw_text'])
        self.assertEqual((parsed['base_data_gb'],parsed['daily_data_gb'],parsed['qos_speed_mbps']),(11,2,3))
        self.assertIsNone(HelloCrawler.parse(self.hello(dedicatedPriceGubun='J')))

    def test_hello_does_not_only_take_first_visible_six(self):
        from services.crawler.large_carriers import HelloCrawler
        items=[self.hello(paymentcode=str(i)) for i in range(15)]
        import json
        with patch('services.crawler.large_carriers.read_public',return_value=json.dumps({'list':items}).encode()):
            self.assertEqual(len(HelloCrawler().fetch_raw_plans()),15)

    def test_uplus_temporary_extra_data_does_not_become_permanent_allowance(self):
        from services.crawler.large_carriers import UplusCrawler
        soup=BeautifulSoup('<div class="box" data-discntaddvat="17500" data-bscchrgaddvat="41400" data-ppngen="4"><a seq="A"><strong class="pln-tit">요금제</strong><span class="pln-spc">(7+10)GB+1Mbps</span><p class="pln-txt">통화 기본제공, 문자 기본제공</p></a></div>','html.parser')
        p=UplusCrawler.parse(soup.div)
        self.assertEqual(PlanTextParser.parse(p['raw_text'])['base_data_gb'],7)
        self.assertEqual((p['normal_price'],p['discount_months']),(41400,-1))
