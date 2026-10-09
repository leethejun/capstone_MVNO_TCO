import unittest
from unittest.mock import patch, Mock
from bs4 import BeautifulSoup
from services.crawler.eyes_crawler import EyesCrawler
from services.crawler.mvnohub_crawler import MvnohubCrawler


def card(period='평생', original='52,800원', extra=''):
    return BeautifulSoup(f'''<a class="plan_card" href="/payplan/plan_info/630/C01"><div class="mid"><div>
    <p class="body_medium">[L]무한100GB+</p><p class="plan_tit">100GB + 5Mbps</p>
    <div class="plan_info"><p>기본제공 +영상/부가통화 300분</p><p>기본제공</p></div></div>
    <div class="price">{f'<p class="org_p">{original}</p>' if original else ''}<p class="period">{period}</p><p class="current_p">월 29,500원</p></div></div>{extra}</a>''','html.parser').a


class EyesTests(unittest.TestCase):
    def test_lifetime_keeps_original_price_independently(self):
        plan = EyesCrawler.parse_card(card())
        self.assertEqual((plan['discount_price'],plan['normal_price'],plan['discount_months']), (29500,52800,-1))
        self.assertEqual(plan['title'], '[공식몰] [L]무한100GB+')

    def test_coupon_months_do_not_change_lifetime_period(self):
        plan = EyesCrawler.parse_card(card(extra='<p>쿠폰 24개월 혜택 100,000원</p>'))
        self.assertEqual((plan['normal_price'],plan['discount_months']), (52800,-1))

    def test_unknown_original_is_not_filled_with_lifetime_price(self):
        self.assertIsNone(EyesCrawler.parse_card(card(original=None)))
        self.assertEqual(EyesCrawler.parse_card(card(original=None,period=''))['discount_months'],0)

    def test_page_failure_does_not_return_partial_catalog(self):
        first = Mock(text=f'<div class="plancard_list">{card()}</div><div class="list_footer"><button onclick="page=2">2</button></div>')
        first.raise_for_status.return_value = None
        with patch('services.crawler.eyes_crawler.requests.get', side_effect=[first,RuntimeError('page failed')]):
            with self.assertRaisesRegex(RuntimeError,'page failed'):
                EyesCrawler(delay_sec=0).fetch_raw_plans()

    def test_hub_base_fee_and_permanent_reduction_are_independent(self):
        node = BeautifulSoup('<div data-fee="52800" data-plan-discount-amount="23300"></div>','html.parser').div
        self.assertEqual(MvnohubCrawler.lifetime_prices(node,29500),(52800,-1))
        node['data-discount-period-in-month'] = '7'
        self.assertIsNone(MvnohubCrawler.lifetime_prices(node,29500))
