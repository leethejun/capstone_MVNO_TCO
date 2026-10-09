from datetime import datetime
import json
import re
import os
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Telecom, Plan, UserSubscription, Notification
from parser import PlanTextParser
from services.crawler.telecom_registry import sync_telecom_master, canonical_telecom_name, is_excluded_telecom
from services.crawler.mvnohub_crawler import MvnohubCrawler
from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.bank_eligibility import requires_financial_product

def run_comprehensive_crawler_pipeline(
    max_pages: int = 0,
    include_direct: bool = True,
    db: Optional[Session] = None,
    direct_crawler: Optional[DirectTelecomCrawler] = None
) -> Dict[str, Any]:
    """
    통합 크롤러 파이프라인:
    1. 대한민국 55+개 알뜰폰 통신사 마스터 동기화
    2. 알뜰폰허브 페이징(products.do) 전수 요금제 수집 (69페이지 전체, 800+건)
    3. 허브와 마스터 목록을 합친 모든 알뜰폰 사업자 공식 홈페이지 및 브랜드관 직접 크롤링
    4. 검증 후 추천 목록 원자적 교체, 구독 당시 상품은 비활성 이력으로 보존
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
        "excluded_financial_products": 0,
        "excluded_telecom_plans": 0,
        "total_active_plans": 0,
        "failed_telecoms": [],
        "preserved_subscription_plans": 0,
        "coverage": [],
        "updated": 0,
        "success": False,
        "error": None,
        "crawled_at": datetime.now().isoformat()
    }

    try:
        # Step 2: 알뜰폰허브 페이징 크롤링
        hub_crawler = MvnohubCrawler()
        hub_plans = hub_crawler.fetch_raw_plans(max_pages=max_pages)
        stats["hub_crawled"] = len(hub_plans)
        stats["hub_complete"] = getattr(hub_crawler, "complete", False)
        stats["hub_errors"] = getattr(hub_crawler, "errors", [])

        all_raw_plans = list(hub_plans)

        failed_telecom_names = set()
        # Step 3: 개별 통신사 공식몰 크롤링
        if include_direct:
            direct_crawler = direct_crawler or DirectTelecomCrawler()
            direct_plans = direct_crawler.fetch_raw_plans()
            failed_telecom_names = direct_crawler.failed_telecom_names
            stats["coverage"] = direct_crawler.coverage if isinstance(direct_crawler.coverage, list) else []
            stats["direct_crawled"] = len(direct_plans)
            all_raw_plans.extend(direct_plans)

        stats["total_crawled"] = len(all_raw_plans)

        # 일부 페이지만 수집한 결과로 전체 추천 목록을 교체하지 않는다.
        if max_pages != 0 or not stats['hub_complete']:
            raise ValueError('허브 전체 수집이 완료되지 않아 추천 목록을 교체하지 않습니다.')
        if not all_raw_plans:
            raise ValueError('수집 결과가 비어 있어 기존 요금제를 보존합니다.')
        now = datetime.now()
        telecom_stats = sync_telecom_master(db=db, commit=False)
        stats["telecoms_synced"] = telecom_stats["total_master"]
        fields = ['telecom_id', 'title', 'network_type', 'base_data_gb', 'daily_data_gb',
                  'qos_speed_mbps', 'voice_minutes', 'sms_count', 'discount_price',
                  'normal_price', 'discount_months']
        numeric = {'base_data_gb', 'daily_data_gb', 'qos_speed_mbps'}
        def identity(values):
            return tuple(float(values[field] or 0) if field in numeric else values[field] for field in fields)
        seen_keys = set()
        plans_to_insert = []

        for rdata in all_raw_plans:
            if is_excluded_telecom(rdata.get("telecom_name", "")):
                stats["excluded_telecom_plans"] += 1
                continue
            if requires_financial_product(rdata):
                stats["excluded_financial_products"] += 1
                continue
            discount = rdata.get("discount_price")
            normal = rdata.get("normal_price")
            months = rdata.get("discount_months")
            if (not isinstance(discount, int) or not isinstance(normal, int)
                    or discount < 0 or normal <= 0 or normal < discount
                    or not isinstance(months, int) or months < -1):
                stats["skipped_invalid_prices"] += 1
                for row in stats['coverage']:
                    if row['name'] == rdata.get('telecom_name'):
                        row['status'] = 'needs_attention'
                        row['error'] = '일부 상품 가격/기간 검증 실패: 이전 상품은 추천에서 제외'
                        failed_telecom_names.add(row['name'])
                continue
            tname = canonical_telecom_name(rdata.get("telecom_name", "알뜰폰 통신사"))

            # 이름 앞 세 글자로 다른 통신사를 잘못 합치지 않는다.
            telecom = db.query(Telecom).filter(Telecom.name == tname).first()
            if not telecom:
                telecom = Telecom(name=tname)
                db.add(telecom)
                db.flush()

            title = rdata.get("title", "").strip()
            normal_price = rdata.get("normal_price", 0)

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
            # 판매 채널별 조건을 별개 상품으로 유지한다.
            source = re.search(r'\[출처:([^]]+)\]', new_plan.raw_text or '')
            key = identity({field: getattr(new_plan, field) for field in fields}) + (source.group(1) if source else '',)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            plans_to_insert.append(new_plan)

        if not seen_keys:
            raise ValueError('검증을 통과한 상품이 없어 기존 데이터를 보존합니다.')
        # 외부 수집과 검증을 마친 뒤 같은 트랜잭션에서 이전 목록을 교체한다.
        subscribed_ids = {row[0] for row in db.query(UserSubscription.plan_id).all()}
        removable = db.query(Plan.plan_id)
        if subscribed_ids:
            removable = removable.filter(~Plan.plan_id.in_(subscribed_ids))
        removable_ids = [row[0] for row in removable.all()]
        if removable_ids:
            db.query(Notification).filter(Notification.recommended_plan_id.in_(removable_ids)).update(
                {Notification.recommended_plan_id: None}, synchronize_session='fetch')
            stats['deleted_old_plans'] = db.query(Plan).filter(Plan.plan_id.in_(removable_ids)).delete(synchronize_session='fetch')
        if subscribed_ids:
            stats['preserved_subscription_plans'] = db.query(Plan).filter(Plan.plan_id.in_(subscribed_ids)).update(
                {Plan.is_active: False}, synchronize_session='fetch')
        db.add_all(plans_to_insert)
        stats['inserted'] = len(plans_to_insert)
        stats['failed_telecoms'] = sorted(canonical_telecom_name(name) for name in failed_telecom_names)
        db.flush()
        for row in stats['coverage']:
            carrier_ids = [value[0] for value in db.query(Telecom.telecom_id).filter(Telecom.name == row['name']).all()]
            row['active_plan_count'] = db.query(Plan).filter(Plan.telecom_id.in_(carrier_ids), Plan.is_active == True).count()
        stats['needs_attention'] = [row['name'] for row in stats['coverage'] if row['status'] != 'collected']
        stats["success"] = True
        stats["total_active_plans"] = db.query(Plan).filter(Plan.is_active == True).count()
        db.commit()

    except Exception as e:
        db.rollback()
        stats["success"] = False
        stats["error"] = str(e)
        print(f"[ComprehensivePipeline] 실행 중 오류: {e}")
    finally:
        if should_close_db:
            db.close()

    # 관리자와 운영자가 마지막 실행의 누락/장애를 확인할 수 있게 원자적으로 저장한다.
    report = Path(os.environ.get('CRAWLER_REPORT_PATH', 'runtime/crawler-report.json'))
    try:
        report.parent.mkdir(parents=True, exist_ok=True)
        temporary = report.with_suffix('.tmp')
        temporary.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(report)
    except OSError as error:
        print(f'[ComprehensivePipeline] 수집 보고서 저장 실패: {error}')
    return stats

# 이전 하위 호환용 래퍼
def run_crawler_pipeline(crawler=None, db=None) -> Dict[str, Any]:
    return run_comprehensive_crawler_pipeline(max_pages=0, include_direct=True, db=db)
