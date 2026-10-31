"""
추천 결과 설명: 랭킹·환승 추천이 왜 그 요금제를 골랐는지 근거를 만든다.
문구는 프론트엔드에서 code별로 번역하고, 여기서는 code와 계산 값만 반환한다.
"""
from typing import Any, Dict, List, Optional
from models import Plan
from schemas import PlanRankItem, RecommendationReason

# rank_plans_by_tco의 동점 정렬 순서와 같아야 한다.
TIE_BREAKERS = (
    ("unlimited", lambda x: int(x.is_unlimited_data)),
    ("qos", lambda x: x.qos_speed_mbps),
    ("daily_data", lambda x: x.daily_data_gb),
    ("base_data", lambda x: x.base_data_gb),
)


def _reason(code: str, **params: Any) -> RecommendationReason:
    return RecommendationReason(code=code, params=params)


def _tie_break_criterion(winner: PlanRankItem, loser: PlanRankItem) -> Optional[str]:
    for name, value in TIE_BREAKERS:
        if value(winner) != value(loser):
            return name
    return None


def explain_ranking(ranked: List[PlanRankItem], filters: Optional[Dict[str, Any]] = None,
                    limit: Optional[int] = None) -> List[PlanRankItem]:
    """
    TCO 정렬이 끝난 전체 후보 목록에 근거를 채운다.
    평균·순위 비교는 전체 후보 기준이며, 근거 생성은 응답할 앞쪽 limit건만 한다.
    """
    count = len(ranked)
    if not count:
        return ranked
    average = sum(item.tco for item in ranked) / count
    active_filters = {k: v for k, v in (filters or {}).items() if v not in (None, False, 0, "")}
    top = ranked[0]

    for index, item in enumerate(ranked[:limit]):
        reasons: List[RecommendationReason] = []
        if index == 0:
            reasons.append(_reason("lowest_tco", count=count, months=item.target_months))
        else:
            reasons.append(_reason("rank_position", rank=index + 1, count=count, gap_to_top=item.tco - top.tco))

        # 기간 중 요금 변화
        if item.discount_months == -1:
            reasons.append(_reason("lifetime_discount", price=item.discount_price))
        elif item.normal_period_months == 0:
            reasons.append(_reason("discount_covers_period", months=item.target_months, price=item.discount_price))
        else:
            reasons.append(_reason("price_increase", after_months=item.discount_period_months,
                                   from_price=item.discount_price, to_price=item.normal_price,
                                   normal_months=item.normal_period_months))

        if count > 1 and item.tco < average:
            saving = round(average - item.tco)
            percent = round(saving * 100 / average) if average else 0
            reasons.append(_reason("below_average", saving=saving, percent=percent, count=count))

        if index + 1 < count:
            nxt = ranked[index + 1]
            gap = nxt.tco - item.tco
            if gap > 0:
                reasons.append(_reason("cheaper_than_next", gap=gap))
            else:
                criterion = _tie_break_criterion(item, nxt)
                if criterion:
                    reasons.append(_reason("tie_break", criterion=criterion))

        if item.is_unlimited_data:
            reasons.append(_reason("qos_tier", tier=item.qos_tier, speed=item.qos_speed_mbps,
                                   daily=item.daily_data_gb))
        if active_filters:
            reasons.append(_reason("filters_matched", **active_filters))

        reasons.append(_reason("tco_formula", target_months=item.target_months,
                               discount_price=item.discount_price, discount_months=item.discount_period_months,
                               normal_price=item.normal_price, normal_months=item.normal_period_months,
                               tco=item.tco))
        item.reasons = reasons
    return ranked


def cost_from(plan: Plan, months: int, elapsed_months: int = 0) -> Optional[int]:
    """elapsed_months 이후 months 동안의 요금 합계. 할인 종료 후 정상가를 모르면 None."""
    if plan is None or plan.discount_price is None or plan.discount_months is None:
        return None
    total = 0
    for month in range(elapsed_months, elapsed_months + months):
        if plan.discount_months == -1 or month < plan.discount_months:
            total += plan.discount_price
        elif plan.normal_price is None:
            return None
        else:
            total += plan.normal_price
    return total


def meets_similarity(current: Plan, candidate: Plan) -> bool:
    """recommender.recommend_best_plan의 1차 후보 조건과 동일하다."""
    if float(candidate.base_data_gb) < float(current.base_data_gb) * 0.8:
        return False
    current_qos = float(current.qos_speed_mbps or 0.0)
    candidate_qos = float(candidate.qos_speed_mbps or 0.0)
    if current_qos >= 1.0:
        return candidate_qos >= current_qos
    if current_qos >= 0.4:
        return candidate_qos >= 0.4
    return True


def explain_alternative(current: Plan, recommended: Plan, target_months: int) -> List[RecommendationReason]:
    """환승 알림 추천 요금제의 근거. 현재 요금제는 유지기간이 끝난 시점부터 계속 쓴다고 가정한다."""
    if current is None or recommended is None:
        return []
    reasons: List[RecommendationReason] = []
    if meets_similarity(current, recommended):
        reasons.append(_reason("similar_lowest_tco", months=target_months))
        reasons.append(_reason("keeps_data", current_gb=float(current.base_data_gb),
                               recommended_gb=float(recommended.base_data_gb)))
        if float(current.qos_speed_mbps or 0) > 0:
            reasons.append(_reason("keeps_qos", current_speed=float(current.qos_speed_mbps),
                                   recommended_speed=float(recommended.qos_speed_mbps or 0)))
    else:
        reasons.append(_reason("fallback_lowest_tco", months=target_months))

    stay = cost_from(current, target_months, elapsed_months=target_months)
    switch = cost_from(recommended, target_months)
    if stay is not None and switch is not None:
        reasons.append(_reason("saving_vs_current", months=target_months, current_cost=stay,
                               recommended_cost=switch, saving=stay - switch))
    return reasons
