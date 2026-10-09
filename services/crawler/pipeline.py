from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Telecom, Plan, UserSubscription, Notification
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
    4. 이전 DB 요금제 삭제 (단종 요금제 완전 정리) 및 최신 요금제 신규 적재
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
        "deleted_old_plans": 0,
        "inserted": 0,
        "skipped_invalid_prices": 0,
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

        # Step 4: 이전 DB 요금제 일괄 정리 (크롤링 시마다 이전 요금제 삭제)
        # 사용자 구독(UserSubscription)에 연결된 요금제는 개통 이력 보존을 위해 is_active=False 처리하고,
        # 구독되지 않은 기존 요금제는 전부 DB에서 삭제하여 단종 요금제를 완전히 제거합니다.
        subscribed_plan_ids = {
            row[0] for row in db.query(UserSubscription.plan_id).all()
        }

        # 이전 추천 알림의 recommended_plan_id 참조 해제
        db.query(Notification).filter(Notification.recommended_plan_id.isnot(None)).update(
            {"recommended_plan_id": None}, synchronize_session=False
        )

        if subscribed_plan_ids:
            # 구독 중인 기존 요금제는 과거 가입 이력 보존을 위해 비활성화
            db.query(Plan).filter(Plan.plan_id.in_(subscribed_plan_ids)).update(
                {"is_active": False}, synchronize_session=False
            )
            # 구독되지 않은 기존 요금제는 전량 삭제
            deleted_count = db.query(Plan).filter(~Plan.plan_id.in_(subscribed_plan_ids)).delete(synchronize_session=False)
        else:
            # 구독된 요금제가 없으면 기존 요금제 테이블 전량 삭제
            deleted_count = db.query(Plan).delete(synchronize_session=False)

        stats["deleted_old_plans"] = deleted_count
        db.flush()

        # Step 5: 비정형 텍스트 파싱 및 수집된 신규 요금제 적재
        seen_keys = set()
        plans_to_insert = []

        for rdata in all_raw_plans:
            discount = rdata.get("discount_price")
            normal = rdata.get("normal_price")
            months = rdata.get("discount_months")
            if (not isinstance(discount, int) or not isinstance(normal, int)
                    or discount < 0 or normal <= 0 or normal < discount
                    or not isinstance(months, int) or months < -1):
                stats["skipped_invalid_prices"] += 1
                continue
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

            title = rdata.get("title", "").strip()
            normal_price = rdata.get("normal_price", 0)

            # 동일 크롤링 수집 내 중복 방지
            dedup_key = (telecom.telecom_id, title, normal_price)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            # Regex 비정형 텍스트 정형화
            parsed = PlanTextParser.parse(rdata.get("raw_text", ""))

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
                normal_price=normal_price,
                discount_months=rdata.get("discount_months", 12),
                raw_text=rdata.get("raw_text", ""),
                is_active=True,
                scraped_at=now
            )
            plans_to_insert.append(new_plan)

        if plans_to_insert:
            db.add_all(plans_to_insert)
            stats["inserted"] = len(plans_to_insert)

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
