import ssl
import unittest
from unittest.mock import patch,Mock
from bs4 import BeautifulSoup
from services.crawler.pricing_validation import valid_pricing,UNKNOWN_NORMAL_MARKER
from services.crawler.menu_cards import parse_menu_cards
from services.crawler.structured_official import ErelCrawler
from services.tco import calculate_tco
from parser import PlanTextParser


class PartialPricingTests(unittest.TestCase):
    def test_missing_normal_is_not_silently_accepted(self):
        item={'discount_price':1000,'normal_price':None,'discount_months':-1,'raw_text':''}
        self.assertFalse(valid_pricing(item))
        item['raw_text']=UNKNOWN_NORMAL_MARKER
        self.assertTrue(valid_pricing(item))
        item['discount_months']=0
        self.assertFalse(valid_pricing(item))

    def test_lifetime_tco_never_needs_unpublished_original_price(self):
        self.assertEqual(calculate_tco(48,-1,14850,None)['tco'],14850*48)

    def test_finite_price_is_only_usable_inside_verified_period(self):
        self.assertEqual(calculate_tco(24,24,39600,None)['tco'],39600*24)
        with self.assertRaises(ValueError):calculate_tco(36,24,39600,None)

    def test_explicit_lifetime_card_with_no_original_does_not_disappear(self):
        soup=BeautifulSoup('<a class="card_rate_link" href="/rateplan_view.do?no=946"><p class="title">[평생] 한패스 7GB+</p><ul class="desc"><li>7GB+1Mbps</li><li>통화 무제한</li><li>문자 무제한</li></ul><div class="price">월 14,850원</div></a>','html.parser')
        rows=parse_menu_cards(soup,'한패스모바일','https://www.hanpassmobile.co.kr/rate_plan.do','LGU+',lambda _:BeautifulSoup('<p>월 14,850원</p>','html.parser'))
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]['normal_price'],rows[0]['discount_months']),(None,-1))
        self.assertTrue(valid_pricing(rows[0]))

    def erel(self,**kwargs):
        row=dict(name='음성300분11GB+일2GB',code='A',basePrice=38500,salePrice=19000,
                 originalPrice=None,discountPeriod=None,discountUnit=None,tags=',34,',
                 data=11264,dataUnit=None,dataDesc='소진 후 일 2GB/이후 최대 3Mbps',additionalData=None,
                 isDataQos=True,dataQos=3,voc=300,vocDesc='LGU+망 1회선 무제한',isVocInfinity=False,
                 sms=100,smsDesc='',isSmsInfinity=False,mnoGubun='LGT',planType='LTE')
        row.update(kwargs);return row

    def test_erel_uses_actual_lifetime_tag_not_missing_period_guess(self):
        row=ErelCrawler.parse(self.erel(),{'34'})
        p=PlanTextParser.parse(row['raw_text'])
        self.assertEqual(row['discount_months'],-1)
        self.assertEqual((p['base_data_gb'],p['daily_data_gb'],p['voice_minutes']),(11,2,300))
        with self.assertRaises(ValueError):ErelCrawler.parse(self.erel(tags=''),{'34'})

    def test_erel_daily_only_plan_is_not_monthly_five_gb(self):
        row=ErelCrawler.parse(self.erel(name='음성기본매일5GB+',data=5120,dataDesc='(매일) / 이후 최대 5Mbps',dataQos=5),{'34'})
        parsed=PlanTextParser.parse(row['raw_text'])
        self.assertEqual((parsed['base_data_gb'],parsed['daily_data_gb']),(0,5))

    def test_won_chain_supplement_keeps_tls_validation(self):
        from services.crawler.won_crawler import WonCrawler
        response=Mock();response.read.return_value=b'{"resultCode":"00000000","data":{}}'
        manager=Mock();manager.__enter__=Mock(return_value=response);manager.__exit__=Mock(return_value=False)
        with patch('services.crawler.won_crawler.urllib.request.urlopen',return_value=manager) as mocked:
            WonCrawler().query('LMPM000012',{})
        context=mocked.call_args.kwargs['context']
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertFalse(context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN)


class DreamCollectorTests(unittest.TestCase):
    def test_dream_uses_both_visible_rate_filters_and_all_details(self):
        from services.crawler.dream_crawler import DreamCrawler
        html='<span class="flatFg active" id="flatFg_0"></span><span class="flatFg active" id="flatFg_1"></span>'
        row=dict(GDCD='A',GDNM='드림',PAYDIV='후불',NETDIV='',WEB_FG='1',TT_AMT='17,600',DISCOUNT='0',
                 DATAAMOUNT='7168',VOICEAMOUNT='0',LETTERAMOUNT='0',SEEDATA='데이터7GB+최대1Mbps',
                 SEEVOICE='기본제공(영상/부가 300분)',SEELETTER='기본제공')
        c=DreamCrawler();response=Mock();response.content=html.encode()
        with patch('services.crawler.dream_crawler.requests.get',return_value=response),patch.object(c,'query',side_effect=[[row],[row]]) as query:
            records=c.fetch_raw_plans()
        self.assertEqual(query.call_args_list[0].args,('01',{'paydiv':'','flatFgArr':['0','1']}))
        self.assertEqual(len(records),1)
        self.assertEqual(PlanTextParser.parse(records[0]['raw_text'])['base_data_gb'],7)

    def test_dream_daily_extra_is_not_monthly_data(self):
        from services.crawler.dream_crawler import DreamCrawler
        row=dict(GDCD='A',GDNM='DREAM 42',PAYDIV='후불',NETDIV='',WEB_FG='1',TT_AMT='42,900',DISCOUNT='0',
                 DATAAMOUNT='10240',VOICEAMOUNT='0',LETTERAMOUNT='0',SEEDATA='데이터10GB+2GB/일+최대3Mbps',
                 SEEVOICE='기본제공',SEELETTER='기본제공')
        parsed=PlanTextParser.parse(DreamCrawler.parse(row)['raw_text'])
        self.assertEqual((parsed['base_data_gb'],parsed['daily_data_gb'],parsed['qos_speed_mbps']),(10,2,3))

    def test_won_financial_terms_in_benefit_block_are_excluded(self):
        from services.crawler.won_crawler import WonCrawler
        c=WonCrawler();item=dict(prodNm='우리WON 셀럽',soId='01',prodCd='C',maxDisDesc='')
        with patch.object(c,'query',side_effect=[{'dsRes':[item],'dsHdr':{'totalCnt':1}},
                {'dsRes':[{'srvDesc':'','subscribeDesc':'','bigo5Desc':'우리은행 신규 금융거래에 따라 할인'}]}]):
            self.assertEqual(c.fetch_raw_plans(),[])
        self.assertEqual(c.skipped,[])
        self.assertEqual(len(c.excluded),1)


class PartialPriceRankingTests(unittest.TestCase):
    def test_unknown_normal_price_is_only_ranked_inside_known_price_horizon(self):
        from datetime import datetime
        from models import Plan
        from services.tco import rank_plans_by_tco
        def plan(pid,months):
            return Plan(plan_id=pid,telecom_id=1,title='검증 상품',network_type='LTE',base_data_gb=7,
                        daily_data_gb=0,qos_speed_mbps=1,voice_minutes=-1,sms_count=-1,
                        discount_price=10000,normal_price=None,discount_months=months,
                        raw_text=UNKNOWN_NORMAL_MARKER,is_active=True,scraped_at=datetime.now())
        plans=[plan(1,-1),plan(2,24)]
        self.assertEqual({p.plan_id for p in rank_plans_by_tco(plans,12)},{1,2})
        self.assertEqual({p.plan_id for p in rank_plans_by_tco(plans,36)},{1})
        self.assertIsNone(rank_plans_by_tco(plans,12)[0].model_dump()['normal_price'])
