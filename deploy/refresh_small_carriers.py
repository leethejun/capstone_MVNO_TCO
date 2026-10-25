"""전체 공식 목록 검증을 마친 수집기만 실행. 기본 dry-run, --apply로 통신사별 교체."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from services.crawler.expanded_catalogs import AMobileCrawler,TossCrawler,SkylifeCrawler
from services.crawler.eyagi_crawler import EyagiCrawler
from services.crawler.large_carriers import UplusCrawler,HelloCrawler
from services.crawler.dream_crawler import DreamCrawler
from services.crawler.won_crawler import WonCrawler
from services.crawler.gnuboard_plans import GnuboardCatalogCrawler
from services.crawler.ktm_crawler import KtmCrawler
from services.crawler.smartel_crawler import SmartelCrawler
from services.crawler.menu_catalog import MenuCatalogCrawler

ROOT=Path('runtime/small-carrier-audit-2026-10-25')
COLLECTORS={'드림라인 모바일':DreamCrawler,'우리WON모바일':WonCrawler,'밸류컴':lambda:GnuboardCatalogCrawler('밸류컴'),'U+유모바일':UplusCrawler,'헬로모바일':HelloCrawler,'A모바일(에넥스텔레콤)':AMobileCrawler,'토스모바일':TossCrawler,
            'KT스카이라이프':SkylifeCrawler,'이야기모바일':EyagiCrawler,'KT M모바일':KtmCrawler,'스마텔':SmartelCrawler}
for name in ('한패스모바일','아정당모바일','인스모바일','마블링','슈가모바일','KCTV모바일','온국민폰','토리모바일'):
    COLLECTORS[name]=lambda name=name:MenuCatalogCrawler(name)


def collect(entry):
    name,factory=entry
    try:
        crawler=factory();records=crawler.fetch_raw_plans();skipped=getattr(crawler,'skipped',[])
        if skipped:raise ValueError(f'미검증 상품 {len(skipped)}건: {skipped}')
        if not records:raise ValueError('전체 검증 상품 없음')
        ROOT.mkdir(parents=True,exist_ok=True)
        (ROOT/f'{name}-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
        return name,records,None
    except Exception as error:return name,[],str(error)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    results=[]
    # Collection is read-only. Replacement remains sequential and transactional per carrier.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for name,records,error in pool.map(collect,COLLECTORS.items()):
            row={'name':name,'verified_official':len(records),'error':error,'applied':False}
            if args.apply and not error:
                from deploy.refresh_investigated import replace
                row['inserted_official']=replace(name,records);row['applied']=True
            results.append(row);print(row,flush=True)
            (ROOT/'verified-refresh.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    if any(row['error'] for row in results):raise SystemExit(1)


if __name__=='__main__':main()
