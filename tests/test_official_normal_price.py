import unittest
from unittest.mock import patch, Mock
from bs4 import BeautifulSoup
from services.crawler.direct_crawlers import DirectTelecomCrawler

CARD = '<a class="plan_card" href="/payplan/plan_info/10641/C01"><h3>100GB + 5Mbps</h3><p>첫 7개월간</p><p class="price">월 6,800원</p></a>'
DETAIL = '<div class="price"><p class="org_p">61,600원</p><p class="period">첫 7개월간</p><p class="current_p">월 6,800원</p></div>'

class OfficialPriceTests(unittest.TestCase):
    def test_card_itself_is_detail_anchor_and_normal_price_is_read(self):
        crawler = DirectTelecomCrawler(delay_sec=0)
        with patch('services.crawler.direct_crawlers.requests.get', return_value=Mock(status_code=200, text=DETAIL)) as get:
            rows = crawler._extract_plans_from_html('아이즈모바일', BeautifulSoup(CARD, 'html.parser'), 'https://eyes.co.kr/', 'LGU+')
        self.assertEqual(get.call_args.args[0], 'https://eyes.co.kr/payplan/plan_info/10641/C01')
        self.assertEqual((rows[0]['discount_price'], rows[0]['normal_price'], rows[0]['discount_months']), (6800,61600,7))

    def test_missing_normal_price_does_not_become_discount_price(self):
        crawler = DirectTelecomCrawler(delay_sec=0)
        with patch.object(crawler, '_fetch_normal_price_from_detail', return_value=None):
            rows = crawler._extract_plans_from_html('아이즈모바일', BeautifulSoup(CARD, 'html.parser'), 'https://eyes.co.kr/', 'LGU+')
        self.assertEqual(rows, [])
        self.assertIn('아이즈모바일', crawler.failed_telecom_names)

    def test_normal_price_label_split_by_tags(self):
        crawler = DirectTelecomCrawler(delay_sec=0)
        with patch('services.crawler.direct_crawlers.requests.get', return_value=Mock(status_code=200,text='<p>정상가 <b>61,600</b> 원</p>')):
            self.assertEqual(crawler._fetch_normal_price_from_detail('https://example.com/plan'), 61600)
