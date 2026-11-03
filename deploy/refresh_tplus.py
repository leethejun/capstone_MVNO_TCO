"""티플러스 공식몰 전체 수집을 검증하고 --apply 시 해당 공식몰 상품만 갱신한다."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from database import SessionLocal
from deploy.refresh_investigated import replace
from models import Plan, Telecom
from services.crawler.tplus_crawler import TplusCrawler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    crawler = TplusCrawler()
    records = crawler.fetch_raw_plans()
    if not records or crawler.skipped:
        raise ValueError(f'티플러스 전체 상품 검증 미완료: {crawler.skipped}')
    stamp = datetime.now().isoformat()
    root = Path('runtime') / ('tplus-refresh-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    root.mkdir(parents=True, exist_ok=False)
    (root / 'records.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    result = dict(name='티플러스', crawled_at=stamp, total=crawler.total, pages=crawler.pages,
                  official_count=len(records), excluded=crawler.excluded, skipped=crawler.skipped,
                  applied=False)
    if args.apply:
        with SessionLocal() as db:
            carrier = db.query(Telecom).filter(Telecom.name == '티플러스').one()
            old = db.query(Plan).filter(Plan.telecom_id == carrier.telecom_id).all()
            backup = [{column.name: getattr(p, column.name) for column in Plan.__table__.columns} for p in old]
        (root / 'plans-before.json').write_text(json.dumps(backup, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        report_path = Path('runtime/crawler-report.json')
        if report_path.exists():
            (root / 'crawler-report-before.json').write_bytes(report_path.read_bytes())
        result['inserted'] = replace('티플러스', records)
        result['applied'] = True
        with SessionLocal() as db:
            result['active_plan_count'] = db.query(Plan).filter(Plan.telecom_id == carrier.telecom_id, Plan.is_active == True).count()
            total_active = db.query(Plan).filter(Plan.is_active == True).count()
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding='utf-8'))
            # 전체 실행 시각과 타 통신사의 결과는 보존하고 부분 갱신 시각을 별도로 기록한다.
            for row in report.get('coverage', []):
                if row.get('name') == '티플러스':
                    row.update(official_count=len(records), status='collected', error=None,
                               active_plan_count=result['active_plan_count'], refreshed_at=stamp,
                               refresh_scope='official_only', official_total=crawler.total,
                               official_excluded=len(crawler.excluded))
            for field in ('failed_telecoms', 'needs_attention'):
                if field in report:
                    report[field] = [name for name in report[field] if name != '티플러스']
            report['total_active_plans'] = total_active
            report.setdefault('partial_refreshes', []).append(dict(name='티플러스', crawled_at=stamp, official_count=len(records)))
            tmp = report_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            tmp.replace(report_path)
    (root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(result, audit_path=str(root)), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
