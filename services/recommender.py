from typing import Optional
from sqlalchemy.orm import Session, joinedload
from models import Plan
from services.tco import rank_plans_by_tco

def recommend_best_plan(
    current_plan: Plan,
    target_months: int = 7,
    db: Session = None
) -> Optional[Plan]:
    """
    환승 알림 대상자의 현재 요금제 스펙(데이터량, QoS 속도 등)을 분석하여,
    더 유리하거나 동급 이상의 요금제 중 TCO 최저가 요금제 1종을 선별하여 추천합니다.
    """
    if db is None or current_plan is None:
        return None

    # 1. 1차 추천 조건: 데이터량 동급 이상(80% 이상) 및 QoS 속도 동급 이상
    query = db.query(Plan).options(joinedload(Plan.telecom)).filter(
        Plan.is_active == True,
        Plan.plan_id != current_plan.plan_id
    )

    req_data = float(current_plan.base_data_gb) * 0.8
    query = query.filter(Plan.base_data_gb >= req_data)

    current_qos = float(current_plan.qos_speed_mbps or 0.0)
    if current_qos >= 1.0:
        query = query.filter(Plan.qos_speed_mbps >= current_qos)
    elif current_qos >= 0.4:
        query = query.filter(Plan.qos_speed_mbps >= 0.4)

    candidates = query.all()

    # 2. 1차 조건 후보가 없으면 전체 활성 요금제 중 TCO 최저가 요금제 탐색 (폴백)
    if not candidates:
        fallback_query = db.query(Plan).options(joinedload(Plan.telecom)).filter(
            Plan.is_active == True,
            Plan.plan_id != current_plan.plan_id
        )
        candidates = fallback_query.all()

    if not candidates:
        return None

    # TCO 랭킹 산출
    ranked = rank_plans_by_tco(candidates, target_months=target_months)
    if not ranked:
        return None

    best_item = ranked[0]
    return db.query(Plan).filter(Plan.plan_id == best_item.plan_id).first()
