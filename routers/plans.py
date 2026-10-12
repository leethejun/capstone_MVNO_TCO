from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Plan, Telecom
from schemas import PlanResponse, PlanRankItem, TelecomResponse
from services.tco import rank_plans_by_tco

router = APIRouter(prefix="/api/plans", tags=["Plans & TCO Ranking"])

@router.get("/rank", response_model=List[PlanRankItem], summary="목표 기간별 TCO 최저가 랭킹 조회")
def get_tco_ranked_plans(
    target_months: int = Query(12, ge=1, le=48, description="목표 유지 기간(개월, 기본값 12)"),
    telecom_id: Optional[int] = Query(None, description="통신사 ID 필터"),
    min_data_gb: Optional[float] = Query(None, ge=0, description="최소 기본 제공 데이터(GB)"),
    min_daily_data_gb: Optional[float] = Query(None, ge=0, description="최소 일일 제공 데이터(GB)"),
    min_qos_speed_mbps: Optional[float] = Query(None, ge=0, description="최소 QoS 속도제어(Mbps) - 예: 1.0(유튜브SD), 3.0(유튜브FHD)"),
    is_unlimited_data: Optional[bool] = Query(None, description="실질 무제한 요금제 여부 (True: QoS 속도제어 또는 일일데이터 제공만)"),
    unlimited_voice: Optional[bool] = Query(None, description="음성 무제한 여부 (True: 무제한만)"),
    unlimited_sms: Optional[bool] = Query(None, description="문자 무제한 여부 (True: 무제한만)"),
    network_type: Optional[str] = Query(None, description="망 종류 (LTE 또는 5G)"),
    limit: int = Query(50, ge=1, le=100, description="조회 건수 제한"),
    db: Session = Depends(get_db)
):
    query = db.query(Plan).options(joinedload(Plan.telecom)).filter(Plan.is_active == True)

    if telecom_id:
        query = query.filter(Plan.telecom_id == telecom_id)
    if min_data_gb is not None:
        query = query.filter(Plan.base_data_gb >= min_data_gb)
    if min_daily_data_gb is not None:
        query = query.filter(Plan.daily_data_gb >= min_daily_data_gb)
    if min_qos_speed_mbps is not None:
        query = query.filter(Plan.qos_speed_mbps >= min_qos_speed_mbps)
    if is_unlimited_data is True:
        query = query.filter((Plan.qos_speed_mbps >= 0.4) | (Plan.daily_data_gb > 0))
    elif is_unlimited_data is False:
        query = query.filter(Plan.qos_speed_mbps == 0, (Plan.daily_data_gb == 0) | (Plan.daily_data_gb == None))
    if unlimited_voice is True:
        query = query.filter(Plan.voice_minutes == -1)
    if unlimited_sms is True:
        query = query.filter(Plan.sms_count == -1)
    if network_type:
        query = query.filter(Plan.network_type.ilike(f"%{network_type}%"))

    plans = query.all()
    ranked = rank_plans_by_tco(plans, target_months=target_months)
    return ranked[:limit]

@router.get("/telecoms", response_model=List[TelecomResponse], summary="등록된 통신사 목록 조회")
def get_telecoms(db: Session = Depends(get_db)):
    return db.query(Telecom).all()

@router.get("/{plan_id}", response_model=PlanResponse, summary="요금제 단건 상세 조회")
def get_plan_detail(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(Plan).options(joinedload(Plan.telecom)).filter(Plan.plan_id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="해당 요금제를 찾을 수 없습니다.")
    return plan
