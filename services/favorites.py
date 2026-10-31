"""즐겨찾기 요금제를 현재 판매 중인 상품과 TCO로 연결한다."""
from typing import Dict, List, Sequence
from sqlalchemy.orm import Session, joinedload
from models import Plan, Telecom
from schemas import FavoriteItem, FavoriteKey
from services.tco import rank_plans_by_tco


def favorite_key(plan: Plan) -> Dict[str, str]:
    return {
        "telecom_name": plan.telecom.name if plan.telecom else "알뜰폰",
        "title": plan.title,
        "network_type": plan.network_type or "LTE",
    }


def _identity(telecom_name, title, network_type):
    return (telecom_name.strip(), title.strip(), (network_type or "LTE").strip().upper())


def resolve_favorites(db: Session, keys: Sequence, target_months: int) -> List[FavoriteItem]:
    """
    저장한 plan_id가 판매 중이면 그대로 사용하고, 재수집으로 사라졌으면
    같은 통신사·요금제명·망의 활성 상품 중 TCO가 가장 낮은 상품으로 대체한다.
    keys: FavoriteKey 또는 FavoritePlan ORM 객체 (favorite_id 속성은 선택)
    """
    if not keys:
        return []
    plan_ids = {k.plan_id for k in keys if k.plan_id}
    saved = {}
    if plan_ids:
        rows = db.query(Plan).options(joinedload(Plan.telecom)).filter(Plan.plan_id.in_(plan_ids)).all()
        saved = {p.plan_id: p for p in rows}

    titles = {k.title.strip() for k in keys}
    active_by_identity: Dict[tuple, List[Plan]] = {}
    for plan in (db.query(Plan).join(Telecom).options(joinedload(Plan.telecom))
                 .filter(Plan.is_active == True, Plan.title.in_(titles)).all()):
        active_by_identity.setdefault(_identity(*favorite_key(plan).values()), []).append(plan)

    results = []
    for key in keys:
        base = FavoriteKey(telecom_name=key.telecom_name, title=key.title,
                           network_type=key.network_type or "LTE", plan_id=key.plan_id).model_dump()
        base["favorite_id"] = getattr(key, "favorite_id", None)
        original = saved.get(key.plan_id)
        if original is not None and original.is_active:
            candidates, status = [original], "available"
        else:
            candidates = active_by_identity.get(_identity(key.telecom_name, key.title, key.network_type), [])
            status = "replaced"
        if not candidates:
            results.append(FavoriteItem(**base, status="unavailable"))
            continue
        ranked = rank_plans_by_tco(candidates, target_months=target_months)
        if not ranked:
            results.append(FavoriteItem(**base, status="not_computable"))
            continue
        base["plan_id"] = ranked[0].plan_id
        results.append(FavoriteItem(**base, status=status, plan=ranked[0]))
    return results
