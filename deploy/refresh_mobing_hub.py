"""모빙 허브 전체 목록 검증 후 --apply 시 해당 통신사의 허브 상품만 갱신한다."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from database import SessionLocal
from models import Plan, Telecom
from parser import PlanTextParser
from services.crawler.mobing_hub_crawler import MobingHubCrawler
from services.crawler.pricing_validation import valid_pricing


def replace_hub_snapshot(db, records):
    if not records or any(r.get('telecom_name') != '모빙' or not valid_pricing(r)
                          or '[출처: 알뜰폰허브]' not in r.get('raw_text', '') for r in records):
        raise ValueError('검증된 모빙 허브 전체 상품이 필요합니다.')
    carrier = db.query(Telecom).filter(Telecom.name == '모빙').one()
    old = db.query(Plan).filter(Plan.telecom_id == carrier.telecom_id).all()
    fields = ('title','network_type','base_data_gb','daily_data_gb','qos_speed_mbps',
              'voice_minutes','sms_count','discount_price','normal_price','discount_months')
    numeric = {'base_data_gb','daily_data_gb','qos_speed_mbps'}
    def key(values):
        return tuple(float(values[f] or 0) if f in numeric else values[f] for f in fields)
    hub = [p for p in old if '[출처: 알뜰폰허브]' in (p.raw_text or '') or '브랜드전용관]' in (p.raw_text or '')]
    by_key = {key({f:getattr(p,f) for f in fields}):p for p in hub}
    prepared = []
    for r in records:
        parsed = PlanTextParser.parse(r['raw_text'])
        values = {f:r[f] if f in r else parsed[f] for f in fields}
        prepared.append((r,values))
    if len({key(values) for _,values in prepared}) != len(records):
        raise ValueError('모빙 허브 상품의 가격/스펙 중복을 확인해야 합니다.')
    for plan in hub:
        plan.is_active = False
    now = datetime.now(); inserted = 0
    for record,values in prepared:
        plan = by_key.get(key(values))
        if plan is None:
            plan = Plan(telecom_id=carrier.telecom_id, **values)
            db.add(plan); inserted += 1
        plan.raw_text, plan.scraped_at, plan.is_active = record['raw_text'], now, True
    db.flush()
    return dict(inserted=inserted, hub_count=len(records), active_plan_count=db.query(Plan).filter(
        Plan.telecom_id==carrier.telecom_id,Plan.is_active==True).count())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    crawler=MobingHubCrawler(); records=crawler.fetch_raw_plans()
    if not crawler.complete or len(records)!=crawler.total:
        raise ValueError('모빙 허브 전체 수집 미완료: 기존 데이터 보존')
    stamp=datetime.now().isoformat()
    audit=Path('runtime')/('mobing-hub-refresh-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    audit.mkdir(parents=True,exist_ok=False)
    (audit/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    result=dict(name='모빙',crawled_at=stamp,hub_total=crawler.total,hub_pages=crawler.pages,
                hub_complete=crawler.complete,hub_count=len(records),applied=False)
    if args.apply:
        report_path=Path('runtime/crawler-report.json')
        if report_path.exists():
            (audit/'crawler-report-before.json').write_bytes(report_path.read_bytes())
        with SessionLocal() as db:
            try:
                carrier=db.query(Telecom).filter(Telecom.name=='모빙').one()
                old=db.query(Plan).filter(Plan.telecom_id==carrier.telecom_id).all()
                backup=[{c.name:getattr(p,c.name) for c in Plan.__table__.columns} for p in old]
                (audit/'plans-before.json').write_text(json.dumps(backup,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
                result.update(replace_hub_snapshot(db,records)); db.commit()
                result['applied']=True
                total_active=db.query(Plan).filter(Plan.is_active==True).count()
            except Exception:
                db.rollback();raise
        if report_path.exists():
            report=json.loads(report_path.read_text(encoding='utf-8'))
            for row in report.get('coverage',[]):
                if row['name']=='모빙':
                    if row.get('status')!='hub_fallback':
                        row['official_error']=row.get('error')
                    row.update(hub_count=len(records),hub_total=crawler.total,hub_pages=crawler.pages,
                               hub_complete=True,status='hub_fallback',refreshed_at=stamp,
                               active_plan_count=result['active_plan_count'],refresh_scope='hub_only',
                               error=f'공식몰 미복구 · 알뜰폰허브 전체 {len(records)}개 수집 완료')
            report['failed_telecoms']=[name for name in report.get('failed_telecoms',[]) if name!='모빙']
            report['total_active_plans']=total_active
            report.setdefault('partial_refreshes',[]).append(dict(name='모빙',crawled_at=stamp,hub_count=len(records),source='hub'))
            tmp=report_path.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(report_path)
    (audit/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result,audit_path=str(audit)),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
