import unittest
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models import FavoritePlan, Plan, Telecom, User
from routers.favorites import add_favorite, delete_favorite, list_favorites
from schemas import FavoriteCreate, FavoriteKey
from services.explain import explain_alternative, explain_ranking
from services.favorites import resolve_favorites
from services.tco import rank_plans_by_tco


def make_plan(pid, title, discount, normal, months, telecom_id=1, qos=0, data=10, active=True):
    return Plan(plan_id=pid, telecom_id=telecom_id, title=title, network_type="LTE",
                base_data_gb=data, daily_data_gb=0, qos_speed_mbps=qos, voice_minutes=-1, sms_count=-1,
                discount_price=discount, normal_price=normal, discount_months=months,
                raw_text="", is_active=active, scraped_at=datetime(2026, 10, 1))


def codes(item):
    return [reason.code for reason in item.reasons]


class RankingReasonTests(unittest.TestCase):
    def rank(self, plans, months=12, **filters):
        return explain_ranking(rank_plans_by_tco(plans, target_months=months), filters)

    def test_top_plan_explains_cost_structure_and_gap(self):
        ranked = self.rank([make_plan(1, "평생", 9900, 22000, -1),
                            make_plan(2, "7개월 할인", 3300, 18700, 7),
                            make_plan(3, "비싼", 30000, 30000, 12)])
        top = ranked[0]
        # 3,300*7 + 18,700*5 = 116,600 < 9,900*12 = 118,800
        self.assertEqual(top.title, "7개월 할인")
        self.assertEqual(codes(top)[0], "lowest_tco")
        self.assertIn("price_increase", codes(top))
        self.assertIn("lifetime_discount", codes(ranked[1]))
        self.assertEqual(codes(ranked[1])[0], "rank_position")
        gap = next(r for r in top.reasons if r.code == "cheaper_than_next").params["gap"]
        self.assertEqual(gap, ranked[1].tco - top.tco)

    def test_price_increase_and_formula_values(self):
        ranked = self.rank([make_plan(2, "7개월 할인", 3300, 18700, 7)])
        reasons = {r.code: r.params for r in ranked[0].reasons}
        self.assertEqual(reasons["price_increase"], {"after_months": 7, "from_price": 3300,
                                                     "to_price": 18700, "normal_months": 5})
        formula = reasons["tco_formula"]
        self.assertEqual(formula["discount_price"] * formula["discount_months"]
                         + formula["normal_price"] * formula["normal_months"], formula["tco"])
        self.assertNotIn("below_average", reasons)  # 비교 대상이 없으면 평균 근거를 만들지 않는다.

    def test_tie_break_criterion_matches_sort(self):
        ranked = self.rank([make_plan(1, "QoS 없음", 10000, 10000, 12, qos=0),
                            make_plan(2, "QoS 3M", 10000, 10000, 12, qos=3)])
        self.assertEqual(ranked[0].title, "QoS 3M")
        tie = next(r for r in ranked[0].reasons if r.code == "tie_break")
        self.assertEqual(tie.params["criterion"], "unlimited")

    def test_below_average_and_only_selected_filters(self):
        ranked = self.rank([make_plan(1, "A", 10000, 10000, 12), make_plan(2, "B", 20000, 20000, 12),
                            make_plan(3, "C", 30000, 30000, 12)],
                           min_qos_speed_mbps=0, unlimited_voice=True, network_type=None)
        below = next(r for r in ranked[0].reasons if r.code == "below_average")
        self.assertEqual(below.params, {"saving": 120000, "percent": 50, "count": 3})
        filters = next(r for r in ranked[0].reasons if r.code == "filters_matched")
        self.assertEqual(filters.params, {"unlimited_voice": True})
        self.assertEqual(ranked[2].reasons[0].params["gap_to_top"], 240000)

    def test_limit_only_builds_returned_reasons(self):
        ranked = explain_ranking(rank_plans_by_tco([make_plan(1, "A", 1, 1, 12), make_plan(2, "B", 2, 2, 12)], 12),
                                 limit=1)
        self.assertTrue(ranked[0].reasons)
        self.assertEqual(ranked[1].reasons, [])


class AlternativeReasonTests(unittest.TestCase):
    def test_similar_plan_saving_uses_post_period_price(self):
        current = make_plan(1, "현재", 3300, 18700, 7, qos=1, data=7)
        recommended = make_plan(2, "추천", 5000, 15000, 12, qos=3, data=11)
        reasons = {r.code: r.params for r in explain_alternative(current, recommended, 12)}
        self.assertIn("similar_lowest_tco", reasons)
        self.assertEqual(reasons["keeps_qos"], {"current_speed": 1.0, "recommended_speed": 3.0})
        self.assertEqual(reasons["saving_vs_current"]["current_cost"], 18700 * 12)
        self.assertEqual(reasons["saving_vs_current"]["saving"], 18700 * 12 - 5000 * 12)

    def test_fallback_when_similarity_not_met(self):
        current = make_plan(1, "현재", 3300, 18700, 7, qos=5, data=100)
        recommended = make_plan(2, "추천", 5000, None, -1, qos=0, data=1)
        reasons = [r.code for r in explain_alternative(current, recommended, 12)]
        self.assertEqual(reasons[0], "fallback_lowest_tco")
        self.assertNotIn("keeps_data", reasons)


class FavoriteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(Telecom(telecom_id=1, name="프리티"))
        self.user = User(user_id=1, email="a@example.com", default_target_months=12)
        self.db.add_all([self.user, make_plan(10, "든든 7GB", 3300, 18700, 7),
                         make_plan(11, "정상가 미확인", 3300, None, 7)])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def key(self, title, plan_id=None):
        return FavoriteKey(telecom_name="프리티", title=title, network_type="LTE", plan_id=plan_id)

    def test_resolve_statuses(self):
        items = resolve_favorites(self.db, [self.key("든든 7GB", 10), self.key("정상가 미확인", 11),
                                            self.key("없는 요금제", 99)], 12)
        self.assertEqual([i.status for i in items], ["available", "not_computable", "unavailable"])
        self.assertEqual(items[0].plan.tco, 3300 * 7 + 18700 * 5)

    def test_recrawled_plan_is_matched_by_name(self):
        # 월간 재수집: 기존 상품 삭제 후 같은 이름 상품이 새 plan_id로 등록된다.
        self.db.query(Plan).filter(Plan.plan_id == 10).delete()
        self.db.add(make_plan(20, "든든 7GB", 2200, 18700, 7))
        self.db.commit()
        item = resolve_favorites(self.db, [self.key("든든 7GB", 10)], 12)[0]
        self.assertEqual((item.status, item.plan_id), ("replaced", 20))

    def test_add_is_idempotent_and_delete_is_owner_only(self):
        first = add_favorite(FavoriteCreate(plan_id=10), 12, self.db, self.user)
        second = add_favorite(FavoriteCreate(plan_id=10), 12, self.db, self.user)
        self.assertEqual(first.favorite_id, second.favorite_id)
        self.assertEqual(self.db.query(FavoritePlan).count(), 1)
        self.assertEqual([i.title for i in list_favorites(12, self.db, self.user)], ["든든 7GB"])
        stranger = User(user_id=2, email="b@example.com")
        with self.assertRaises(HTTPException):
            delete_favorite(first.favorite_id, self.db, stranger)
        delete_favorite(first.favorite_id, self.db, self.user)
        self.assertEqual(self.db.query(FavoritePlan).count(), 0)


if __name__ == "__main__":
    unittest.main()
