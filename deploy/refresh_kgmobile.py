"""KG모바일만 검증 후 갱신한다. 다른 통신사와 기존 개통 이력은 보존."""
from datetime import datetime
from database import SessionLocal
from models import Telecom, Plan
from parser import PlanTextParser
from services.crawler.kgmobile_crawler import KgMobileCrawler


def refresh(db=None, crawler=None):
    records = (crawler or KgMobileCrawler()).fetch_raw_plans()
    if not records:
        raise ValueError('KG모바일 수집 실패: 기존 데이터 보존')
    owns_db = db is None
    db = db or SessionLocal()
    fields = ['title', 'network_type', 'base_data_gb', 'daily_data_gb', 'qos_speed_mbps',
              'voice_minutes', 'sms_count', 'discount_price', 'normal_price', 'discount_months']
    try:
        carrier = db.query(Telecom).filter(Telecom.name == 'KG모바일').first()
        if carrier is None:
            carrier = Telecom(name='KG모바일', website_url=KgMobileCrawler.BASE_URL)
            db.add(carrier); db.flush()
        existing = db.query(Plan).filter(Plan.telecom_id == carrier.telecom_id).all()
        numeric_specs = {'base_data_gb', 'daily_data_gb', 'qos_speed_mbps'}
        def identity(values):
            return tuple(float(values[field]) if field in numeric_specs else values[field] for field in fields)
        by_key = {identity({field: getattr(plan, field) for field in fields}): plan for plan in existing}
        # 가격이 바뀐 상품을 직접 덮어쓰지 않아 가입 당시 상품 정보가 보존된다.
        for plan in existing:
            plan.is_active = False
        now = datetime.now()
        inserted = 0
        for record in records:
            parsed = PlanTextParser.parse(record['raw_text'])
            values = {field: record[field] if field in record else parsed[field] for field in fields}
            key = identity(values)
            plan = by_key.get(key)
            if plan is None:
                plan = Plan(telecom_id=carrier.telecom_id, **values)
                db.add(plan); by_key[key] = plan; inserted += 1
            plan.raw_text, plan.scraped_at, plan.is_active = record['raw_text'], now, True
        db.commit()
        result = {'carrier': carrier.name, 'active': len(records), 'inserted': inserted,
                  'lifetime': sum(record['discount_months'] == -1 for record in records)}
        print(result)
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_db:
            db.close()


if __name__ == '__main__':
    refresh()
