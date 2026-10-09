"""검증된 아이즈 공식몰 상품만 교체한다. 허브·브랜드관 판매 조건은 유지한다."""
from datetime import datetime
from database import SessionLocal
from models import Plan, Telecom, UserSubscription, Notification
from parser import PlanTextParser
from services.crawler.eyes_crawler import EyesCrawler
from services.crawler.direct_crawlers import DirectTelecomCrawler


def refresh(records=None):
    records = records if records is not None else EyesCrawler(headers=DirectTelecomCrawler.HEADERS).fetch_raw_plans()
    if not records:
        raise ValueError('공식몰 결과가 비어 있어 교체하지 않습니다.')
    db = SessionLocal()
    try:
        carrier = db.query(Telecom).filter(Telecom.name=='아이즈모바일').one()
        plans = []
        for record in records:
            assert record['normal_price'] > 0 and 0 <= record['discount_price'] <= record['normal_price']
            parsed = PlanTextParser.parse(record['raw_text'])
            parsed = {field:parsed[field] for field in ['base_data_gb','daily_data_gb','qos_speed_mbps','voice_minutes','sms_count']}
            plans.append(Plan(telecom_id=carrier.telecom_id, title=record['title'], network_type=record['network_type'],
                              discount_price=record['discount_price'],normal_price=record['normal_price'],
                              discount_months=record['discount_months'],raw_text=record['raw_text'],
                              scraped_at=datetime.now(),is_active=True,**parsed))
        old_ids = [row[0] for row in db.query(Plan.plan_id).filter(Plan.telecom_id==carrier.telecom_id,Plan.title.startswith('[공식몰]')).all()]
        subscribed = {row[0] for row in db.query(UserSubscription.plan_id).filter(UserSubscription.plan_id.in_(old_ids)).all()}
        removable = set(old_ids) - subscribed
        db.query(Notification).filter(Notification.recommended_plan_id.in_(removable)).update({Notification.recommended_plan_id:None},synchronize_session=False)
        deleted = db.query(Plan).filter(Plan.plan_id.in_(removable)).delete(synchronize_session=False)
        db.query(Plan).filter(Plan.plan_id.in_(subscribed)).update({Plan.is_active:False},synchronize_session=False)
        db.add_all(plans); db.commit()
        print({'deleted_official':deleted,'inserted_official':len(plans),'preserved_history':len(subscribed)})
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


if __name__ == '__main__':
    refresh()
