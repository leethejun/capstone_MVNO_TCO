"""전체 브랜드 감사가 완료된 허브 스냅샷만 원자적으로 반영한다."""
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re

from database import SessionLocal
from models import Plan, Telecom
from parser import PlanTextParser
from services.crawler.bank_eligibility import requires_financial_product
from services.crawler.pricing_validation import valid_pricing
from services.crawler.telecom_registry import canonical_telecom_name, is_excluded_telecom, sync_telecom_master, visible_crawler_report


def load_snapshot(root):
    manifest=json.loads((root/'brands.json').read_text())
    audit=json.loads((root/'results.json').read_text())
    expected={b['brand_plan_url'] for b in manifest if not is_excluded_telecom(b['name'],b.get('home_url',''))}
    if {r['url'] for r in audit}!=expected or len(audit)!=len(expected) or not all(r['complete'] for r in audit):
        raise ValueError('모든 허브 브랜드관의 전체 수집이 완료되어야 합니다.')
    grouped=defaultdict(list);seen={}
    for row in audit:
        records=json.loads((root/f'brand-{row["brand_id"]}-records.json').read_text())
        if len(records)!=row['total'] or len(records)!=row['collected']:
            raise ValueError('허브 브랜드별 선언 건수와 저장 원본 불일치')
        for record in records:
            if canonical_telecom_name(record['telecom_name'])!=row['name'] or not valid_pricing(record):
                raise ValueError('허브 원본의 통신사/가격 검증 실패')
            pid=str(record['_hub_product_id'])
            if pid in seen and seen[pid]!=record:
                raise ValueError('동일 허브 상품 ID의 가격/스펙 충돌')
            if pid not in seen:
                seen[pid]=record;grouped[row['name']].append(record)
        grouped.setdefault(row['name'],[])
    global_result=json.loads((root/'global-records.json').read_text())
    if not global_result['complete'] or global_result['errors']:
        raise ValueError('전역 허브 목록 전체 수집 미완료')
    global_ids={str(r['_hub_product_id']) for r in global_result['records']}
    live_path=root/'global-live-api.json'
    if live_path.exists():
        # 조사 중 상품이 추가될 수 있어 마지막 전체 API 응답으로 ID 집합을 갱신한다.
        live=json.loads(live_path.read_text())
        page=live.get('pageResult',{})
        ids={str(r['productId']) for r in page.get('content',[])}
        if (live.get('isRecommendation') or page.get('hasNext') or page.get('number')!=0
                or page.get('totalPages')!=1 or len(ids)!=page.get('totalElements')
                or len(page.get('content',[]))!=len(ids)):
            raise ValueError('전역 전체 API 응답의 상품 수/페이지 검증 실패')
        global_ids=ids
    if global_ids!=set(seen):
        raise ValueError(f'전역/브랜드 상품 ID 대조 실패: 전역에만 {sorted(global_ids-set(seen))}, 브랜드에만 {sorted(set(seen)-global_ids)}')
    return audit,dict(grouped)


def apply_snapshot(db,grouped):
    fields=('title','network_type','base_data_gb','daily_data_gb','qos_speed_mbps','voice_minutes','sms_count','discount_price','normal_price','discount_months')
    floats={'base_data_gb','daily_data_gb','qos_speed_mbps'}
    def signature(values):
        return tuple(float(values[k] or 0) if k in floats else values[k] for k in fields)
    results=[]
    for name,records in grouped.items():
        carrier=db.query(Telecom).filter(Telecom.name==name).one()
        old=db.query(Plan).filter(Plan.telecom_id==carrier.telecom_id).all()
        hub=[p for p in old if '[출처: 알뜰폰허브]' in (p.raw_text or '') or '브랜드전용관]' in (p.raw_text or '')]
        before=sum(p.is_active for p in hub)
        by_id={};legacy=defaultdict(list)
        for plan in hub:
            values={k:getattr(plan,k) for k in fields}
            match=re.search(r'\[허브 상품 ID: (\d+)\]',plan.raw_text or '')
            if match:by_id[(match[1],signature(values))]=plan
            else:
                values['title']=values['title'].removeprefix('[브랜드특가] ')
                legacy[signature(values)].append(plan)
        prepared=[];excluded=[]
        for record in records:
            if requires_financial_product(record):excluded.append(record['title']);continue
            if not valid_pricing(record) or is_excluded_telecom(record['telecom_name']):
                raise ValueError('반영 직전 허브 상품 검증 실패')
            parsed=PlanTextParser.parse(record['raw_text'])
            values={k:record[k] if k in record else parsed[k] for k in fields}
            prepared.append((record,values))
        for plan in hub:plan.is_active=False
        inserted=0;now=datetime.now()
        for record,values in prepared:
            sig=signature(values);pid=str(record['_hub_product_id'])
            plan=by_id.get((pid,sig))
            if plan is None and legacy[sig]:plan=legacy[sig].pop(0)
            if plan is None:
                plan=Plan(telecom_id=carrier.telecom_id,**values);db.add(plan);inserted+=1
            else:
                plan.title=values['title']
            plan.raw_text,plan.scraped_at,plan.is_active=record['raw_text'],now,True
        db.flush()
        after=db.query(Plan).filter(Plan.telecom_id==carrier.telecom_id,Plan.is_active==True).all()
        results.append(dict(name=name,before_hub=before,hub_total=len(records),hub_count=len(prepared),
                            financial_excluded=excluded,inserted=inserted,active_plan_count=len(after),
                            official_count=sum('[출처: 알뜰폰허브]' not in (p.raw_text or '') and '브랜드전용관]' not in (p.raw_text or '') for p in after)))
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit_dir',type=Path);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();audit,grouped=load_snapshot(args.audit_dir)
    result=dict(checked_brands=len(audit),carriers=len(grouped),hub_total=sum(len(r) for r in grouped.values()),applied=False)
    if args.apply:
        stamp=datetime.now().isoformat();root=args.audit_dir/('apply-'+datetime.now().strftime('%Y%m%d-%H%M%S'));root.mkdir()
        report_path=Path('runtime/crawler-report.json')
        if report_path.exists():(root/'crawler-report-before.json').write_bytes(report_path.read_bytes())
        with SessionLocal() as db:
            try:
                # 과거 별칭의 상품도 복원할 수 있도록 전체 상품을 백업한다.
                backup=[{c.name:getattr(p,c.name) for c in Plan.__table__.columns} for p in db.query(Plan).all()]
                (root/'plans-before.json').write_text(json.dumps(backup,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
                sync_telecom_master(db=db,commit=False)
                rows=apply_snapshot(db,grouped);db.commit()
                total_active=db.query(Plan).filter(Plan.is_active==True).count()
            except Exception:db.rollback();raise
        result.update(applied=True,rows=rows,total_active_plans=total_active)
        if report_path.exists():
            report=visible_crawler_report(json.loads(report_path.read_text()))
            # 같은 통신사의 망별 브랜드관은 한 행에 합친다.
            coverage={canonical_telecom_name(r['name']):r for r in report.get('coverage',[])}
            for row in rows:
                name=row['name'];target=coverage.setdefault(name,dict(name=name,home_url=''))
                branches=[r for r in audit if r['name']==name]
                target.update(name=name,hub_count=row['hub_count'],hub_total=row['hub_total'],hub_complete=True,
                              hub_pages=sum(r['pages'] for r in branches),hub_brands=branches,
                              official_count=row['official_count'],active_plan_count=row['active_plan_count'],
                              hub_excluded_financial_count=len(row['financial_excluded']),refreshed_at=stamp,refresh_scope='hub_only')
                if row['hub_count'] and not row['official_count']:
                    target.update(status='hub_fallback',official_error=target.get('official_error') or target.get('error'),
                                  error=f'공식몰 미수집 · 알뜰폰허브 전체 {row["hub_count"]}개 수집 완료')
            report.update(coverage=list(coverage.values()),total_active_plans=total_active)
            report.setdefault('partial_refreshes',[]).append(dict(scope='all_hub_brands',crawled_at=stamp,brands=len(audit),hub_total=result['hub_total']))
            tmp=report_path.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(report_path)
        result['backup_path']=str(root)
        (root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
