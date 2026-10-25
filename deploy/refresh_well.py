"""위너스텔 전체 후불 상품 검증. --apply일 때만 해당 공식몰 상품을 교체한다."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from services.crawler.well_crawler import WellCrawler
from deploy.refresh_investigated import replace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    crawler = WellCrawler()
    records = crawler.fetch_raw_plans()
    result = {'name': '위너스텔(WELL)', 'crawled_at': datetime.now().isoformat(),
              'official_count': len(records), 'excluded': crawler.excluded, 'applied': args.apply}
    if args.apply:
        result['inserted'] = replace('위너스텔(WELL)', records)
    root = Path('runtime'); root.mkdir(exist_ok=True)
    (root/'well-refresh.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
