"""검증 후 아시아모바일 공식몰만 갱신하고 관리자 허브 집계를 DB와 일치시킨다."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from database import SessionLocal
from deploy.refresh_investigated import replace
from models import Plan, Telecom
from services.crawler.asia_crawler import AsiaCrawler
from services.crawler.telecom_registry import canonical_telecom_name, visible_crawler_report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    crawler=AsiaCrawler(); records=crawler.fetch_raw_plans()
    if not records or crawler.skipped:
        raise ValueError(f'아시아모바일 전체 검증 실패: {crawler.skipped}')
    stamp=datetime.now().isoformat()
    audit=Path('runtime')/('asia-refresh-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    audit.mkdir(parents=True,exist_ok=False)
    (audit/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    result=dict(name='아시아모바일',crawled_at=stamp,official_total=crawler.total,
                official_count=len(records),excluded=crawler.excluded,applied=False)
    if args.apply:
        with SessionLocal() as db:
            carrier=db.query(Telecom).filter(Telecom.name=='아시아모바일').one()
            old=db.query(Plan).filter(Plan.telecom_id==carrier.telecom_id).all()
            backup=[{c.name:getattr(p,c.name) for c in Plan.__table__.columns} for p in old]
        (audit/'plans-before.json').write_text(json.dumps(backup,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        report_path=Path('runtime/crawler-report.json')
        if report_path.exists():
            (audit/'crawler-report-before.json').write_bytes(report_path.read_bytes())
        result['inserted']=replace('아시아모바일',records)
        result['applied']=True
        if report_path.exists():
            report=visible_crawler_report(json.loads(report_path.read_text(encoding='utf-8')))
            with SessionLocal() as db:
                carriers={t.telecom_id:canonical_telecom_name(t.name) for t in db.query(Telecom).all()}
                active=db.query(Plan).filter(Plan.is_active==True).all()
                for row in report.get('coverage',[]):
                    plans=[p for p in active if carriers.get(p.telecom_id)==canonical_telecom_name(row['name'])]
                    row['active_plan_count']=len(plans)
                    row['hub_count']=sum('[출처: 알뜰폰허브]' in (p.raw_text or '') or '브랜드전용관]' in (p.raw_text or '') for p in plans)
                    if row['name']=='아시아모바일':
                        row.update(official_count=len(records),official_total=crawler.total,
                                   official_excluded=len(crawler.excluded),status='collected',error=None,
                                   refreshed_at=stamp,refresh_scope='official_only',
                                   exclusion_summary=f'복지·시니어 {len(crawler.excluded)}개 제외')
                        result['active_plan_count']=len(plans)
                report['total_active_plans']=len(active)
            for field in ('failed_telecoms','needs_attention'):
                if field in report:
                    report[field]=[x for x in report[field] if x!='아시아모바일']
            report.setdefault('partial_refreshes',[]).append(dict(name='아시아모바일',crawled_at=stamp,official_count=len(records)))
            tmp=report_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(report_path)
    (audit/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result,audit_path=str(audit)),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
