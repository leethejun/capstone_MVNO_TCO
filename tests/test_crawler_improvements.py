import unittest
from unittest.mock import Mock, patch

from services.crawler.chancemobile_crawler import ChanceMobileCrawler
from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.egmobile_crawler import EgmobileCrawler
from services.tco import calculate_tco


def chance(**changes):
    row = dict(GDNM='알찬 실속 데이터7G', GDCD='C1', TT_AMT='17,600',
               DISCOUNT='10', ORGCHARGE='12,100', LIMPERIOD='6개월',
               DATAAMOUNT='7GB', VOICEAMOUNT='250분', LETTERAMOUNT='100건',
               MNO_CD='LGU+', NETDIV='LTE')
    row.update(changes)
    return row


def eg(code='E1', name='EG 일반 7GB', **changes):
    row = dict(name=name, FEECD=code, seq=code, price1='20000', price2='10000',
               DUTYMONTH='7', telecom='KT', data='7GB', voice='100분', sms='100건')
    row.update(changes)
    return row


class ChancePricingTests(unittest.TestCase):
    def test_restoration_price_drives_tco_after_promotion(self):
        plan = ChanceMobileCrawler()._parse(chance())
        self.assertEqual(plan['normal_price'], 12100)
        self.assertEqual(calculate_tco(12, plan['discount_months'],
                                      plan['discount_price'], plan['normal_price'])['tco'], 72660)
        self.assertEqual(calculate_tco(6, 6, plan['discount_price'], plan['normal_price'])['tco'], 60)

    def test_invalid_restoration_price_is_not_replaced_by_list_price(self):
        for price in (None, '', '미공개', '0', '9', '300001'):
            with self.subTest(price=price), self.assertRaises(ValueError):
                ChanceMobileCrawler()._parse(chance(ORGCHARGE=price))

    def test_no_discount_and_lifetime_keep_their_price_rules(self):
        crawler = ChanceMobileCrawler()
        regular = crawler._parse(chance(DISCOUNT='0', ORGCHARGE='0', LIMPERIOD=''))
        self.assertEqual((regular['discount_price'], regular['normal_price'], regular['discount_months']),
                         (17600, 17600, 0))
        lifetime = crawler._parse(chance(GDNM='[평생할인] 7GB', DISCOUNT='5500', LIMPERIOD=''))
        self.assertEqual((lifetime['discount_price'], lifetime['discount_months']), (5500, -1))


class EgEligibilityTests(unittest.TestCase):
    def test_restricted_and_device_plans_are_excluded_before_price_parsing(self):
        for name in ('복지할인 LTE', 'EGK LTE 시니어A(EGM시니어)',
                     'EG 스마트디바이스10G', 'EG 스마트디바이스20G',
                     '데이터 쉐어링', '데이터쉐어링', '청소년 7GB', '태블릿 10GB', '워치'):
            with self.subTest(name=name):
                self.assertIsNone(EgmobileCrawler.parse(dict(name=name)))

    def test_regular_and_lifetime_phone_plans_remain_available(self):
        self.assertIsNotNone(EgmobileCrawler.parse(eg()))
        plan = EgmobileCrawler.parse(eg(name='EG 데이터 300MB', DUTYMONTH='0'))
        self.assertEqual(plan['discount_months'], -1)

    def run_catalog(self, rows):
        crawler = DirectTelecomCrawler(delay_sec=0)
        response = Mock()
        response.json.return_value = {'total': len(rows), 'list': rows}
        brands = [dict(name='이지모바일', home_url=EgmobileCrawler.BASE, brand_plan_url='')]
        with patch('services.crawler.egmobile_crawler.requests.Session') as session, \
                patch.object(crawler, 'discover_all_mvno_brands', return_value=brands), \
                patch.object(crawler, 'merge_brands', return_value=brands):
            session.return_value.post.return_value = response
            result = crawler.fetch_raw_plans()
        return crawler, result

    def test_intentional_exclusions_do_not_mark_carrier_failed(self):
        crawler, result = self.run_catalog([eg(), eg('E2', '데이터 쉐어링'),
                                           eg('E3', '복지할인 LTE'), eg('E4', 'EG 스마트디바이스10G')])
        self.assertEqual(len(result), 1)
        self.assertEqual(crawler.failed_telecom_names, set())
        self.assertEqual(crawler.coverage[0]['status'], 'collected')
        self.assertIsNone(crawler.coverage[0]['error'])

    def test_real_price_validation_failure_still_marks_carrier_failed(self):
        crawler, result = self.run_catalog([eg(), eg('E2', price2='미공개')])
        self.assertEqual(len(result), 1)
        self.assertEqual(crawler.failed_telecom_names, {'이지모바일'})
        self.assertEqual(crawler.coverage[0]['status'], 'needs_attention')

    def test_exclusions_count_toward_complete_pagination_and_are_reset(self):
        crawler = EgmobileCrawler()
        response = Mock()
        response.json.side_effect = [
            {'total': 2, 'list': [eg('E2', '데이터 쉐어링')]},
            {'total': 2, 'list': [eg()]},
            {'total': 1, 'list': [eg()]},
        ]
        with patch('services.crawler.egmobile_crawler.requests.Session') as session:
            session.return_value.post.return_value = response
            self.assertEqual(len(crawler.fetch_raw_plans()), 1)
            self.assertEqual(len(crawler.excluded), 1)
            self.assertEqual(crawler.skipped, [])
            self.assertEqual(len(crawler.fetch_raw_plans()), 1)
            self.assertEqual(crawler.excluded, [])


if __name__ == '__main__':
    unittest.main()
