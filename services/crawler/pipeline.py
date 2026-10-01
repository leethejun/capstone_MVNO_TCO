from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Telecom, Plan
from parser import PlanTextParser
from services.crawler.telecom_registry import sync_telecom_master
from services.crawler.mvnohub_crawler import MvnohubCrawler
from services.crawler.direct_crawlers import DirectTelecomCrawler

def run_comprehensive_crawler_pipeline(
    max_pages: int = 0,
    include_direct: bool = True,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    통합 크롤러 파이프라인:
    1. 대한민국 55+개 알뜰폰 통신사 마스터 동기화
    2. 알뜰폰허브 페이징(products.do) 전수 요금제 수집 (69페이지 전체, 800+건)
    3. 알뜰폰허브에 등록된 모든 알뜰폰 사업자(25개사) 공식 홈페이지 및 브랜드관 직접 크롤링
    4. 비정형 Regex 파싱 및 MySQL DB Upsert
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    stats = {
        "telecoms_synced": 0,
        "hub_crawled": 0,
        "direct_crawled": 0,
        "total_crawled": 0,
        "inserted": 0,
        "updated": 0,
        "total_active_plans": 0,
        "success": False,
        "error": None,
        "crawled_at": datetime.now().isoformat()
    }

    try:
        # Step 1: 통신사 마스터 40+개사 동기화
        telecom_stats = sync_telecom_master(db=db)
        stats["telecoms_synced"] = telecom_stats["total_master"]

        # Step 2: 알뜰폰허브 페이징 크롤링
        hub_crawler = MvnohubCrawler()
        hub_plans = hub_crawler.fetch_raw_plans(max_pages=max_pages)
        stats["hub_crawled"] = len(hub_plans)

        all_raw_plans = list(hub_plans)

        # Step 3: 개별 통신사 공식몰 크롤링
        if include_direct:
            direct_crawler = DirectTelecomCrawler()
            direct_plans = direct_crawler.fetch_raw_plans()
            stats["direct_crawled"] = len(direct_plans)
            all_raw_plans.extend(direct_plans)

        stats["total_crawled"] = len(all_raw_plans)

        now = datetime.now()

        # Step 4: 정규표현식 파싱 및 DB Upsert
        for rdata in all_raw_plans:
            tname = rdata.get("telecom_name", "알뜰폰 통신사").strip()

            # 통신사 조회 (완전 일치 or 부분 일치)
            telecom = db.query(Telecom).filter(
                (Telecom.name == tname) |
                (Telecom.name.ilike(f"%{tname[:3]}%"))
            ).first()

            if not telecom:
                telecom = Telecom(name=tname)
                db.add(telecom)
                db.flush()

            # Regex 비정형 텍스트 정형화
            parsed = PlanTextParser.parse(rdata.get("raw_text", ""))

            # 방법 2: 같은 제목 + 가격이 같으면 중복으로 간주 (중복 제거 기준 강화)
            title = rdata.get("title", "").strip()
            normal_price = rdata.get("normal_price", 0)
            
            existing_plan = db.query(Plan).filter(
                Plan.title == title,
                ((Plan.normal_price.is_(None)) | (Plan.normal_price == normal_price))
            ).first()

            if existing_plan:
                existing_plan.network_type = rdata.get("network_type", "LTE")
                existing_plan.base_data_gb = parsed["base_data_gb"]
                existing_plan.daily_data_gb = parsed["daily_data_gb"]
                existing_plan.qos_speed_mbps = parsed["qos_speed_mbps"]
                existing_plan.voice_minutes = parsed["voice_minutes"]
                existing_plan.sms_count = parsed["sms_count"]
                existing_plan.discount_price = rdata.get("discount_price", 0)
                existing_plan.normal_price = rdata.get("normal_price", 0)
                existing_plan.discount_months = rdata.get("discount_months", 12)
                existing_plan.raw_text = rdata.get("raw_text", "")
                existing_plan.is_active = True
                existing_plan.scraped_at = now
                stats["updated"] += 1
            else:
                new_plan = Plan(
                    telecom_id=telecom.telecom_id,
                    title=title,
                    network_type=rdata.get("network_type", "LTE"),
                    base_data_gb=parsed["base_data_gb"],
                    daily_data_gb=parsed["daily_data_gb"],
                    qos_speed_mbps=parsed["qos_speed_mbps"],
                    voice_minutes=parsed["voice_minutes"],
                    sms_count=parsed["sms_count"],
                    discount_price=rdata.get("discount_price", 0),
                    normal_price=rdata.get("normal_price", 0),
                    discount_months=rdata.get("discount_months", 12),
                    raw_text=rdata.get("raw_text", ""),
                    is_active=True,
                    scraped_at=now
                )
                db.add(new_plan)
                stats["inserted"] += 1

        db.commit()
        stats["success"] = True
        stats["total_active_plans"] = db.query(Plan).filter(Plan.is_active == True).count()

    except Exception as e:
        db.rollback()
        stats["success"] = False
        stats["error"] = str(e)
        print(f"[ComprehensivePipeline] 실행 중 오류: {e}")
    finally:
        if should_close_db:
            db.close()

    return stats

# 이전 하위 호환용 래퍼
def run_crawler_pipeline(crawler=None, db=None) -> Dict[str, Any]:
    return run_comprehensive_crawler_pipeline(max_pages=3, include_direct=True, db=db)
