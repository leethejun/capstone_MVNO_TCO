"""허브의 모든 공개 브랜드관을 전체 페이지/상세 기준으로 감사한다. DB는 변경하지 않는다."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

import requests

from services.crawler.direct_crawlers import DirectTelecomCrawler
from services.crawler.hub_brand_crawler import HubBrandCrawler
from services.crawler.telecom_registry import canonical_telecom_name, is_excluded_telecom


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--refresh-brand', action='append', default=[], help='재개 시 이 브랜드 ID의 공개 응답은 새로 조회')
    args=parser.parse_args()
    root=args.resume or Path('runtime')/('hub-brand-audit-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    root.mkdir(parents=True,exist_ok=True)
    cache=root/'responses';cache.mkdir(exist_ok=True)
    manifest=root/'brands.json'
    if args.resume:
        brands=json.loads(manifest.read_text())
    else:
        brands=DirectTelecomCrawler().discover_all_mvno_brands()
        if not brands:raise ValueError('허브 브랜드 목록 탐색 실패')
        manifest.write_text(json.dumps(brands,ensure_ascii=False,indent=2),encoding='utf-8')
    results=[]
    for brand in brands:
        name=canonical_telecom_name(brand['name']);url=brand['brand_plan_url']
        if is_excluded_telecom(name,brand.get('home_url','')):continue
        brand_id=url.rsplit('/',1)[1].removesuffix('.do')
        crawler=HubBrandCrawler(name,url,delay_sec=.15)
        refresh = brand_id in args.refresh_brand
        get=crawler._get
        def capture(session,url,params):
            key=hashlib.sha256((url+json.dumps(params,sort_keys=True)).encode()).hexdigest()
            path=cache/key
            if args.resume and path.exists() and not refresh:
                response=requests.Response();response.status_code=200
                response._content=path.read_bytes();response.encoding='utf-8'
                return response
            response=get(session,url,params);path.write_bytes(response.content);return response
        crawler._get=capture
        print(f'CHECK {name} {url}',flush=True)
        row=dict(name=name,url=url,brand_id=brand_id)
        try:
            records=crawler.fetch_raw_plans()
            row.update(total=crawler.total,pages=crawler.pages,collected=len(records),complete=crawler.complete)
            (root/f'brand-{brand_id}-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as exc:
            row.update(total=crawler.total,pages=crawler.pages,complete=False,error=str(exc))
        results.append(row)
        (root/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(row,ensure_ascii=False),flush=True)
    print(json.dumps(dict(audit_path=str(root),brands=len(results),complete=sum(r['complete'] for r in results),
                          total=sum(r.get('total',0) for r in results)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
