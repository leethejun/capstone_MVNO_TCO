import ssl
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from parser import PlanTextParser
from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.pricing_validation import UNKNOWN_NORMAL_MARKER
from services.crawler.tplus_crawler import TplusCrawler
from services.tco import calculate_tco


def card(code='A', title='티플 11GB+', amount_label='7개월간 월', normal='48,400',
         current='12,900', detail='7개월간 월 12,900원, 7개월 후 월 48,400원', data='11GB + 일 2GB 최대 3Mbps'):
    original = f'<p class="throthDesc">월 {normal}원</p>' if normal is not None else ''
    return f'''<div class="cardArea"><input class="plan-seq" value="{code}">
      <div class="badgeArea"><i class="badge kt">KT</i></div><h4 class="title">{title}</h4>
      <div class="descArea"><p>{data}</p><p><span class="ico call">기본제공</span>
      <span class="ico message">100건</span></p></div><div class="amountArea">{original}
      <p>{amount_label} <span class="textPoint">{current}</span> 원</p></div>
      <div class="feelPrice">혜택 체감가 0원</div><p class="rateDetail">{detail}</p></div>'''


def parse(**kwargs):
    return TplusCrawler.parse_card(BeautifulSoup(card(**kwargs), 'html.parser').select_one('.cardArea'))


def page(html, total, count, key='next'):
    return TplusCrawler.SEPARATOR.join(['TRUE', html, str(total), str(count), 'F', key])


class TplusTests(unittest.TestCase):
    def test_actual_bill_not_benefit_effective_price_and_restoration_tco(self):
        p = parse(normal='52,800')  # 취소선보다 명시적인 할인 종료 후 청구액 우선
        self.assertEqual((p['discount_price'], p['normal_price'], p['discount_months']), (12900, 48400, 7))
        self.assertEqual(calculate_tco(12, 7, 12900, 48400)['tco'], 332300)
        specs = PlanTextParser.parse(p['raw_text'])
        self.assertEqual((specs['base_data_gb'], specs['daily_data_gb'], specs['qos_speed_mbps']), (11, 2, 3))
        self.assertEqual((specs['voice_minutes'], specs['sms_count']), (-1, 100))

    def test_daily_only_data_does_not_use_title_data(self):
        specs = PlanTextParser.parse(parse(title='티플 매일5G+', data='일 5GB 최대 5Mbps')['raw_text'])
        self.assertEqual((specs['base_data_gb'], specs['daily_data_gb'], specs['qos_speed_mbps']), (0, 5, 5))

    def test_lifetime_with_unpublished_normal_price(self):
        p = parse(amount_label='평생 월', normal=None, current='8,990', detail='평생 월 8,990원')
        self.assertIsNone(p['normal_price'])
        self.assertEqual(p['discount_months'], -1)
        self.assertIn(UNKNOWN_NORMAL_MARKER, p['raw_text'])
        self.assertEqual(calculate_tco(48, -1, 8990, None)['tco'], 431520)

    def test_after_period_lifetime_is_not_initial_lifetime(self):
        p = parse(amount_label='4개월간 월', current='8,800', normal='22,000', detail='4개월 후 평생 월 22,000원')
        self.assertEqual((p['discount_months'], p['normal_price']), (4, 22000))

    def test_missing_or_conflicting_restoration_is_rejected(self):
        for detail in ['혜택 체감가 0원', '6개월간 월 12,900원, 7개월 후 월 48,400원',
                       '7개월간 월 1원, 7개월 후 월 48,400원']:
            with self.subTest(detail=detail), self.assertRaises(ValueError):
                parse(detail=detail)

    def test_complete_cursor_pagination_and_restricted_product_exclusion(self):
        c = TplusCrawler(delay_sec=0)
        with patch.object(c, '_request_page', side_effect=[page(card(), 3, 1, 'cursor1'),
                page(card(code='B') + card(code='C', title='티플 외국인 전용'), 3, 2, '')]) as fetch:
            self.assertEqual(len(c.fetch_raw_plans()), 2)
        self.assertEqual((c.total, c.pages, len(c.excluded), c.skipped), (3, 2, 1, []))
        self.assertEqual(fetch.call_args_list[1].args, ('N', 'cursor1'))

    def test_incomplete_duplicate_or_changed_total_fails(self):
        sequences = [
            [page(card(), 2, 1), page('', 2, 0)],
            [page(card(), 2, 1), page(card(), 2, 1)],
            [page(card(), 2, 1), page(card(code='B'), 3, 1)],
            [page(card(), 2, 2)],
        ]
        for responses in sequences:
            c = TplusCrawler(delay_sec=0)
            with self.subTest(responses=responses), patch.object(c, '_request_page', side_effect=responses), self.assertRaises(ValueError):
                c.fetch_raw_plans()

    def test_tls_keeps_certificate_hostname_and_security_level(self):
        default = ssl.create_default_context()
        context = TplusCrawler.ssl_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(context.security_level, default.security_level)
        self.assertEqual(context.minimum_version, default.minimum_version)
        ciphers = {c['name'] for c in context.get_ciphers() if c['protocol'] != 'TLSv1.3'}
        self.assertEqual(ciphers, {'AES128-GCM-SHA256', 'AES256-GCM-SHA384'})

    def test_official_dispatch_uses_dedicated_crawler(self):
        with patch.object(TplusCrawler, 'fetch_raw_plans', return_value=[parse()]):
            result = DirectTelecomCrawler()._crawl_brand_official_site('티플러스', 'https://www.tplusmobile.com', '3사망')
        self.assertEqual(len(result), 1)


if __name__ == '__main__':
    unittest.main()
