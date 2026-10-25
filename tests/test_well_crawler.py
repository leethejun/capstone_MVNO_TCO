import unittest
from unittest.mock import patch, Mock
from services.crawler.well_crawler import WellCrawler
from parser import PlanTextParser


def page(code, category, price='22,000', after='24개월 이후 49,500원'):
    return f'''<a class="rate_link" href="rateplan_view.do;jsessionid=SESSION?type={category}&no={code}">
    <p class="title">WELL 71GB+</p><ul class="desc"><li>11GB + 일 2GB + 3Mbps</li><li>통화 기본제공</li><li>문자 기본제공</li></ul>
    <div class="price"><p class="origin">49,500원</p><p>월 {price} 원</p><p class="ref">{after}</p></div></a>'''


class WellTests(unittest.TestCase):
    def response(self, html, category):
        r = Mock(content=html.encode(), url=f'{WellCrawler.URL}?type={category}')
        r.raise_for_status.return_value = None
        return r

    def test_all_postpaid_categories_and_duplicate_codes(self):
        visited = []
        def get(url, params=None, **kwargs):
            category = params['type']; visited.append(category)
            # A featured product can also appear in a network category.
            code = '1' if category in ('T008', 'T009') else category
            return self.response(page(code, category), category)
        with patch('services.crawler.well_crawler.requests.Session') as session:
            session.return_value.get.side_effect = get
            rows = WellCrawler().fetch_raw_plans()
        self.assertEqual(tuple(visited), WellCrawler.CATEGORIES)
        self.assertNotIn('T002', visited)  # prepaid excluded
        self.assertEqual(len(rows), 4)
        self.assertNotIn('jsessionid', str(rows))
        self.assertEqual((rows[0]['discount_price'],rows[0]['normal_price'],rows[0]['discount_months']), (22000,49500,24))
        spec = PlanTextParser.parse(rows[0]['raw_text'])
        self.assertEqual((spec['base_data_gb'],spec['daily_data_gb'],spec['qos_speed_mbps']), (11,2,3))

    def test_missing_category_and_price_fail_closed(self):
        for html in ['<html>점검 중</html>', page('1','T008',price='미정')]:
            with self.subTest(html=html), patch('services.crawler.well_crawler.requests.Session') as session:
                session.return_value.get.return_value = self.response(html,'T008')
                with self.assertRaises(ValueError): WellCrawler().fetch_raw_plans()

    def test_restricted_shared_and_senior_plans_are_not_recommended(self):
        html = page('1','T008').replace('WELL 71GB+', '시니어 요금제')
        with patch('services.crawler.well_crawler.requests.Session') as session:
            session.return_value.get.return_value = self.response(html,'T008')
            crawler = WellCrawler()
            self.assertEqual(crawler.fetch_raw_plans(), [])
            self.assertEqual(len(crawler.excluded), 1)

    def test_pagination_cannot_silently_truncate_catalog(self):
        with patch('services.crawler.well_crawler.requests.Session') as session:
            session.return_value.get.return_value = self.response(page('1','T008')+'<div class="paging"><a>2</a></div>','T008')
            with self.assertRaisesRegex(ValueError,'페이지'): WellCrawler().fetch_raw_plans()
