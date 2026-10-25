"""활성 상품 50개 미만 통신사의 공식 메뉴·기존 수집기를 순서대로 재검증한다. DB 변경 없음."""
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from sqlalchemy import func
from database import SessionLocal
from models import Telecom, Plan
from services.crawler.telecom_registry import MASTER_TELECOMS
from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.official_routes import OFFICIAL_PLAN_LIST_URLS


def main():
    root = Path('runtime/small-carrier-audit-2026-10-25'); root.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        counts = dict(db.query(Telecom.name, func.count(Plan.plan_id)).outerjoin(
            Plan, (Plan.telecom_id == Telecom.telecom_id) & (Plan.is_active == True)).group_by(Telecom.telecom_id).all())
    finally: db.close()
    targets = [dict(row, active_before=counts.get(row['name'], 0)) for row in MASTER_TELECOMS if counts.get(row['name'], 0) < 50]
    rows = []
    for index, entry in enumerate(targets, 1):
        name = entry['name']; row = dict(entry, checked_at=datetime.now().isoformat(), menu_links=[])
        print(f'[{index}/{len(targets)}] {name}', flush=True)
        folder = root / str(index); folder.mkdir(exist_ok=True)
        try:
            response = requests.get(entry['website_url'], timeout=12)
            row.update(home_status=response.status_code, resolved_home=response.url)
            (folder/'home.html').write_bytes(response.content)
            soup = BeautifulSoup(response.content, 'html.parser')
            for a in soup.select('a'):
                text = a.get_text(' ', strip=True); href = a.get('href') or a.get('onclick') or ''
                if any(word in text for word in ('요금제', '전체요금', '후불')) or any(word in href.lower() for word in ('rate', '/plan', 'charge')):
                    link = {'text':text[:100], 'href':href}
                    if link not in row['menu_links']: row['menu_links'].append(link)
            row['known_list'] = OFFICIAL_PLAN_LIST_URLS.get(name)
        except Exception as error: row['home_error'] = str(error)
        crawler = DirectTelecomCrawler(timeout=10, delay_sec=0)
        try:
            records = crawler._crawl_brand_official_site(name, entry['website_url'], entry['network'])
            row.update(official_count=len(records), error=crawler._official_errors.get(name), incomplete=name in crawler.failed_telecom_names)
            (folder/'records.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as error: row.update(official_count=0,error=str(error),incomplete=True)
        rows.append(row)
        (root/'report.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k:row.get(k) for k in ('name','active_before','home_status','official_count','error')},ensure_ascii=False),flush=True)
    print('완료',len(rows),flush=True)


if __name__ == '__main__': main()
