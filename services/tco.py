import re
from typing import Dict, Any, List
from models import Plan
from schemas import PlanRankItem, TelecomResponse

def calculate_tco(
    target_months: int,
    discount_months: int,
    discount_price: int,
    normal_price: int
) -> Dict[str, int]:
    """
    사용자의 목표 유지 기간에 따른 TCO(총소유비용) 및 월 환산 평균 비용 산출
    - target_months <= discount_months: 할인 요금 * 목표유지개월
    - target_months > discount_months: (할인 요금 * 할인개월) + (정상 요금 * 초과개월)
    """
    if target_months <= 0:
        target_months = 1

    if discount_months == -1 or target_months <= discount_months:
        discount_period = target_months
        normal_period = 0
        tco = discount_price * target_months
    else:
        discount_period = discount_months
        normal_period = target_months - discount_months
        tco = (discount_price * discount_months) + (normal_price * normal_period)

    monthly_avg = round(tco / target_months)

    return {
        "tco": tco,
        "monthly_avg_price": monthly_avg,
        "discount_period_months": discount_period,
        "normal_period_months": normal_period,
    }

def determine_qos_tier(qos_mbps: float, daily_gb: float) -> str:
    """QoS 속도 및 일일 데이터 기반 실체감 무제한 등급 분류"""
    if qos_mbps >= 5.0:
        return "초고속 무제한 (5Mbps+)"
    elif qos_mbps >= 3.0:
        return "FHD 고속 무제한 (3Mbps)"
    elif qos_mbps >= 1.0:
        return "실속 무제한 (1Mbps, 유튜브 480p)"
    elif qos_mbps >= 0.4:
        return "안심 무제한 (400Kbps, 메신저용)"
    elif daily_gb > 0.0:
        return f"일일제공 무제한 (매일 {daily_gb}GB)"
    else:
        return "소진 시 차단/과금형"

def rank_plans_by_tco(plans: List[Plan], target_months: int) -> List[PlanRankItem]:
    """
    Plan ORM 객체 리스트에 대해 TCO를 산출하고 TCO 최저가(오름차순)로 정렬하여 반환.
    동일 TCO 시: 무제한 요금제 우선 -> QoS 속도 빠른 순 -> 기본 데이터 많은 순으로 더 좋은 조건 우대.
    """
    ranked_items: List[PlanRankItem] = []

    for plan in plans:
        # 과거 크롤러가 누락된 가격을 0원으로 저장한 레코드는 추천하지 않는다.
        # 정상가가 확인된 0원 프로모션은 유효하다.
        if (plan.discount_price is None or plan.normal_price is None
                or plan.discount_price < 0 or plan.normal_price <= 0
                or plan.normal_price < plan.discount_price
                or plan.discount_months is None or plan.discount_months < -1):
            continue
        raw = plan.raw_text or ""
        # 종량제·충전형 요금은 사용량 없이 월 고정 TCO를 계산할 수 없다.
        if re.search(r"종량제|쓴\s*만큼\s*과금|원\s*/\s*(?:MB|GB|분|건)", raw, re.IGNORECASE):
            continue
        # 과거 범용 공식몰 수집은 혜택 문구를 요금제로 저장했다.
        # 명시적 데이터 필드/전용 크롤러/새 가격 검증 근거가 없으면 재수집 전까지 제외한다.
        if (raw.startswith("[공식몰]") and "[월요금 요소 검증]" not in raw
                and not re.search(r"\|\s*데이터\s+\d", raw)
                and "[출처: 이야기모바일 공식홈페이지]" not in raw):
            continue
        tco_info = calculate_tco(
            target_months=target_months,
            discount_months=plan.discount_months,
            discount_price=plan.discount_price,
            normal_price=plan.normal_price
        )

        telecom_resp = None
        if plan.telecom:
            telecom_resp = TelecomResponse.model_validate(plan.telecom)

        qos = float(plan.qos_speed_mbps or 0.0)
        daily = float(plan.daily_data_gb or 0.0)
        is_unlimited = (qos > 0.0) or (daily > 0.0)
        tier = determine_qos_tier(qos, daily)

        rank_item = PlanRankItem(
            plan_id=plan.plan_id,
            telecom_id=plan.telecom_id,
            title=plan.title,
            network_type=plan.network_type,
            base_data_gb=float(plan.base_data_gb),
            daily_data_gb=daily,
            qos_speed_mbps=qos,
            voice_minutes=plan.voice_minutes,
            sms_count=plan.sms_count,
            discount_price=plan.discount_price,
            normal_price=plan.normal_price,
            discount_months=plan.discount_months,
            raw_text=plan.raw_text,
            is_active=plan.is_active,
            scraped_at=plan.scraped_at,
            telecom=telecom_resp,
            target_months=target_months,
            tco=tco_info["tco"],
            monthly_avg_price=tco_info["monthly_avg_price"],
            discount_period_months=tco_info["discount_period_months"],
            normal_period_months=tco_info["normal_period_months"],
            is_unlimited_data=is_unlimited,
            qos_tier=tier
        )
        ranked_items.append(rank_item)

    # TCO 오름차순 정렬 (동일 TCO 시: 무제한 여부 -> QoS 속도 높은 순 -> 기본 데이터 많은 순)
    ranked_items.sort(
        key=lambda x: (
            x.tco,
            -int(x.is_unlimited_data),
            -x.qos_speed_mbps,
            -x.daily_data_gb,
            -x.base_data_gb
        )
    )
    return ranked_items
