from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Plan, Telecom
from services.crawler.pipeline import run_comprehensive_crawler_pipeline
from services.crawler.telecom_registry import sync_telecom_master

router = APIRouter(prefix="/api/crawler", tags=["Web Crawler & Pipeline"])

@router.post("/run", summary="알뜰폰 전수 웹 크롤러 및 정형화 파이프라인 실행")
def trigger_comprehensive_crawler(
    max_pages: int = Query(0, ge=0, le=100, description="수집할 알뜰폰허브 페이지 수 (0이면 전체 69페이지 전수 수집)"),
    include_direct: bool = Query(True, description="개별 통신사 공식몰 및 브랜드관 직접 크롤링 포함 여부"),
    db: Session = Depends(get_db)
):
    """
    1. 대한민국 55+개 알뜰폰 통신사 마스터 DB 동기화
    2. 알뜰폰허브(mvnohub.kr) 페이징 전수 요금제 수집 (69페이지 전체)
    3. 알뜰폰허브에 등록된 모든 알뜰폰 사업자(25개사) 공식 홈페이지 및 브랜드관 직접 크롤링
    4. Regex 비정형 파싱을 통한 DB Upsert 자동화
    """
    result = run_comprehensive_crawler_pipeline(
        max_pages=max_pages,
        include_direct=include_direct,
        db=db
    )
    return result

@router.post("/sync-telecoms", summary="대한민국 40+개 알뜰폰 통신사 마스터 DB 동기화")
def sync_telecoms_endpoint(db: Session = Depends(get_db)):
    """나무위키 기반 대한민국 40+개 알뜰폰 통신사(공식 홈페이지, 브랜드명) 즉시 동기화"""
    return sync_telecom_master(db=db)

@router.get("/status", summary="크롤링 적재 상태 및 최근 스크랩 정보 조회")
def get_crawler_status(db: Session = Depends(get_db)):
    total_plans = db.query(Plan).count()
    active_plans = db.query(Plan).filter(Plan.is_active == True).count()
    total_telecoms = db.query(Telecom).count()
    latest_scraped = db.query(func.max(Plan.scraped_at)).scalar()

    return {
        "total_plans": total_plans,
        "active_plans": active_plans,
        "total_telecoms": total_telecoms,
        "latest_scraped_at": latest_scraped.isoformat() if latest_scraped else None
    }
