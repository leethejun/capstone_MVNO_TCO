import copy
import unittest
from unittest.mock import Mock, patch

from parser import PlanTextParser
from services.crawler.asia_crawler import AsiaCrawler
from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.telecom_registry import MASTER_TELECOMS, is_excluded_telecom, visible_crawler_report
from services.tco import calculate_tco


def item(**changes):
    value = dict(PAYDIV='L', GDNM='아시아 5G 통화기본 180GB+', TT_AMT='58300',
                 REAL_AMT='25300', DISCOUNT=[dict(AMT='30000', PERIOD='7', USEYN='Y')],
                 MNO_CD='LGU+', GDCD='A', SEEDATA='180GB+10Mbps',
                 DATAAMOUNT='976GB', SEEVOICE='기본제공(부가통화300분)', SEELETTER='기본제공')
    value.update(changes)
    return value


class AsiaTests(unittest.TestCase):
    def test_vat_discount_and_display_data_not_internal_data(self):
        plan = AsiaCrawler.parse(item())
        self.assertEqual((plan['discount_price'], plan['normal_price'], plan['discount_months']), (25300,58300,7))
        specs = PlanTextParser.parse(plan['raw_text'])
        self.assertEqual((specs['base_data_gb'], specs['qos_speed_mbps'], specs['voice_minutes']), (180,10,-1))
        self.assertEqual(calculate_tco(12,7,25300,58300)['tco'],468600)

    def test_permanent_discount_remains_after_temporary_discount(self):
        plan = AsiaCrawler.parse(item(REAL_AMT='24200', DISCOUNT=[
            dict(AMT='30000', PERIOD='7', USEYN='Y'), dict(AMT='1000', PERIOD='999', USEYN='Y')]))
        self.assertEqual((plan['discount_price'],plan['normal_price']), (24200,57200))

    def test_unrepresentable_multiple_periods_and_bill_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            AsiaCrawler.parse(item(REAL_AMT='1'))
        with self.assertRaises(ValueError):
            AsiaCrawler.parse(item(DISCOUNT=[dict(AMT='100',PERIOD='4',USEYN='Y'),dict(AMT='100',PERIOD='7',USEYN='Y')]))

    def test_restricted_and_prepaid_not_collected(self):
        self.assertIsNone(AsiaCrawler.parse(item(GDNM='A9 시니어')))
        self.assertIsNone(AsiaCrawler.parse(item(PAYDIV='P')))

    def test_duplicate_categories_are_merged_and_network_lists_checked(self):
        one = item(); duplicate = dict(one, SORT='2')
        responses = [dict(RESULT='Y', DATA=[one,duplicate]),dict(RESULT='Y',DATA=[]),dict(RESULT='Y',DATA=[one])]
        session = Mock()
        session.post.side_effect = [Mock(json=Mock(return_value=r)) for r in responses]
        manager = Mock(); manager.__enter__ = Mock(return_value=session); manager.__exit__ = Mock(return_value=False)
        with patch('services.crawler.asia_crawler.requests.Session',return_value=manager):
            crawler=AsiaCrawler(); self.assertEqual(len(crawler.fetch_raw_plans()),1)
        self.assertEqual((crawler.total,crawler.skipped),(1,[]))


class ExclusionTests(unittest.TestCase):
    def test_seven_removed_carriers_cannot_reappear_from_hub(self):
        excluded = ['스노우맨','니즈모바일','친구모바일','아이디스파워텔','서경모바일','여유모바일','원텔레콤']
        self.assertTrue(all(is_excluded_telecom(name) for name in excluded))
        self.assertFalse(set(excluded) & {x['name'] for x in MASTER_TELECOMS})
        self.assertTrue(is_excluded_telecom('별칭', 'https://www.chingumobile.com/plans'))
        rows = DirectTelecomCrawler.merge_brands([dict(name=name,home_url='https://example.org',brand_plan_url='') for name in excluded])
        self.assertFalse(set(excluded) & {row['name'] for row in rows})

    def test_old_admin_report_is_filtered_without_mutating_history(self):
        report=dict(coverage=[dict(name='친구모바일'),dict(name='모빙')],failed_telecoms=['원텔레콤','모빙'],needs_attention=['친구모바일'])
        before=copy.deepcopy(report); result=visible_crawler_report(report)
        self.assertEqual(result['coverage'],[dict(name='모빙')])
        self.assertEqual(result['failed_telecoms'],['모빙'])
        self.assertEqual(result['needs_attention'],[])
        self.assertEqual(report,before)

    def test_mobing_current_route_reports_transport_error(self):
        crawler=DirectTelecomCrawler()
        with patch('services.crawler.direct_crawlers.requests.get',side_effect=ConnectionError('remote closed')) as get:
            self.assertEqual(crawler._crawl_mobing_direct('모빙','https://www.mobing.co.kr/main'),[])
        self.assertEqual(get.call_args.args[0],'https://www.mobing.co.kr/product/plan')
        self.assertIn('remote closed',crawler._official_errors['모빙'])


if __name__ == '__main__':
    unittest.main()
