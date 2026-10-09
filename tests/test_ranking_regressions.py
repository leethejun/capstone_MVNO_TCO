import unittest
from datetime import datetime
from bs4 import BeautifulSoup
from models import Plan
from parser import PlanTextParser
from services.tco import calculate_tco, rank_plans_by_tco
from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.mvnohub_crawler import MvnohubCrawler


class RankingRegressions(unittest.TestCase):
    def test_data_volume_is_not_qos_speed(self):
        for raw in ("안심무약정2+300MB | 300MB", "데이터 1GB+500MB",
                    "안심300MB", "QoS 300MB", "데이터 2GB+300메가"):
            with self.subTest(raw=raw):
                self.assertEqual(PlanTextParser.parse(raw)["qos_speed_mbps"], 0)

    def test_qos_speed_units_and_shorthand(self):
        for raw, expected in (("11GB+3M", 3), ("11GB+3Mbps", 3),
                              ("300MB | 소진후 400Kbps", 0.4),
                              ("데이터 1GB+300MB+5Mbps", 5),
                              ("QoS 400", 0.4), ("소진시 1", 1)):
            with self.subTest(raw=raw):
                self.assertEqual(PlanTextParser.parse(raw)["qos_speed_mbps"], expected)

    def test_lifetime_discount(self):
        for months in (6, 12, 24, 36, 48):
            result = calculate_tco(months, -1, 9900, 22000)
            self.assertEqual(result["tco"], months * 9900)
            self.assertEqual(result["normal_period_months"], 0)
            self.assertEqual(result["discount_period_months"], months)

    def test_promotion_expiry(self):
        self.assertEqual(calculate_tco(6, 7, 0, 22000)["tco"], 0)
        self.assertEqual(calculate_tco(12, 7, 0, 22000)["tco"], 110000)

    def test_invalid_prices_excluded_but_free_promotion_kept(self):
        def plan(pid, normal):
            return Plan(plan_id=pid, telecom_id=1, title="test", network_type="LTE",
                        base_data_gb=7, daily_data_gb=0, qos_speed_mbps=1,
                        voice_minutes=-1, sms_count=-1, discount_price=0,
                        normal_price=normal, discount_months=7, raw_text="",
                        is_active=True, scraped_at=datetime.now())
        ranked = rank_plans_by_tco([plan(1, 0), plan(2, 22000)], 6)
        self.assertEqual([item.plan_id for item in ranked], [2])

    def test_legacy_benefit_with_nonzero_normal_price_excluded(self):
        plan = Plan(discount_price=0, normal_price=47300, discount_months=24,
                    raw_text="[공식몰] 혼자 결합 해도 추가데이터 | 24개월 20GB 제공 제휴카드 할인")
        self.assertEqual(rank_plans_by_tco([plan], 12), [])

    def test_metered_plan_cannot_have_fixed_monthly_tco(self):
        plan = Plan(discount_price=5, normal_price=100, discount_months=12,
                    raw_text="[공식몰] Prepay30 | 종량제 | 쓴 만큼 과금 | 22.52원/MB [출처: 이야기모바일 공식홈페이지]")
        self.assertEqual(rank_plans_by_tco([plan], 12), [])

    def test_specs_preferred_to_title(self):
        parsed = PlanTextParser.parse("100GB+5Mbps 이벤트 | 데이터 7GB+1Mbps | 통화 무제한 | 문자 무제한")
        self.assertEqual(parsed["base_data_gb"], 7)
        self.assertEqual(parsed["qos_speed_mbps"], 1)
        self.assertEqual(parsed["sms_count"], -1)

    def test_generic_crawler_rejects_navigation_and_rewards(self):
        soup = BeautifulSoup('<div class="plan-card"><h3>최근 검색어</h3>100GB 0원폰</div>'
                             '<div class="plan-card"><h3>실체감 0원</h3>7GB 상품권 0원</div>', "html.parser")
        plans = DirectTelecomCrawler()._extract_plans_from_html("test", soup, "https://example.com", "KT")
        self.assertEqual(plans, [])

    def test_generic_crawler_keeps_explicit_free_promotion(self):
        soup = BeautifulSoup('<div class="plan-card"><h3>LTE 7GB</h3>'
                             '<div class="price"><span class="now">0원</span>'
                             '<del>22,000원</del></div>7개월 이후 문자 무제한</div>', "html.parser")
        plans = DirectTelecomCrawler()._extract_plans_from_html("test", soup, "https://example.com", "KT")
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["discount_price"], 0)
        self.assertEqual(plans[0]["normal_price"], 22000)

    def test_hub_missing_price_is_not_free(self):
        card = BeautifulSoup('<div data-product-id="1"><p class="tit">7GB</p></div>', "html.parser").div
        self.assertIsNone(MvnohubCrawler()._parse_card(card))


if __name__ == "__main__":
    unittest.main()
