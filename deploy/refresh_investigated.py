"""조사 중 검증된 공식몰 결과만 통신사별 원자적으로 교체한다."""
import json
from pathlib import Path
from bs4 import BeautifulSoup
from services.crawler.direct_crawlers import DirectTelecomCrawler
from deploy.refresh_eyes import refresh
from database import SessionLocal
from models import Telecom,Plan,UserSubscription,Notification
from parser import PlanTextParser
from datetime import datetime
from services.crawler.bank_eligibility import requires_financial_product
from services.crawler.telecom_registry import is_excluded_telecom


def replace(name,records):
    if is_excluded_telecom(name):
        raise ValueError("사용자 요청으로 제외된 통신사")
    if not records:
        raise ValueError('검증된 수집 결과 없음')
    db=SessionLocal()
    try:
        carrier=db.query(Telecom).filter(Telecom.name==name).one()
        new=[];seen=set()
        for r in records:
            if requires_financial_product(r):continue
            key=(r['title'],r['discount_price'],r['normal_price'],r['discount_months'],r['raw_text'])
            if key in seen: continue
            seen.add(key)
            assert r['normal_price']>0 and 0<=r['discount_price']<=r['normal_price'] and r['discount_months']>=-1
            p=PlanTextParser.parse(r['raw_text']);p={f:p[f] for f in ['base_data_gb','daily_data_gb','qos_speed_mbps','voice_minutes','sms_count']}
            new.append(Plan(telecom_id=carrier.telecom_id,title=r['title'],network_type=r['network_type'],discount_price=r['discount_price'],normal_price=r['normal_price'],discount_months=r['discount_months'],raw_text=r['raw_text'],scraped_at=datetime.now(),is_active=True,**p))
        if not new:raise ValueError('금융 조건 제외 후 검증된 일반 상품 없음')
        old=[x[0] for x in db.query(Plan.plan_id).filter(Plan.telecom_id==carrier.telecom_id,Plan.title.startswith('[공식몰]')).all()]
        history={x[0] for x in db.query(UserSubscription.plan_id).filter(UserSubscription.plan_id.in_(old)).all()};remove=set(old)-history
        db.query(Notification).filter(Notification.recommended_plan_id.in_(remove)).update({Notification.recommended_plan_id:None},synchronize_session=False)
        db.query(Plan).filter(Plan.plan_id.in_(remove)).delete(synchronize_session=False)
        db.query(Plan).filter(Plan.plan_id.in_(history)).update({Plan.is_active:False},synchronize_session=False)
        db.add_all(new);db.commit();return len(new)
    except Exception:
        db.rollback();raise
    finally:db.close()


if __name__=='__main__':
    rows=json.loads(Path('/tmp/carrier-inspection/report.json').read_text());results=[]
    for row in rows:
        name=row['name'];print(name,flush=True);crawler=DirectTelecomCrawler()
        try:
            records=crawler._crawl_brand_official_site(name,row.get('home_url') or row['url'],'')
            count=replace(name,records)
            result={'name':name,'inserted_official':count,'error':crawler._official_errors.get(name)}
        except Exception as e:result={'name':name,'inserted_official':0,'error':str(e)}
        print(result,flush=True);results.append(result)
        Path('/tmp/carrier-refresh.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
