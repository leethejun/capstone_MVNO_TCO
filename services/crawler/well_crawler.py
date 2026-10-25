"""위너스텔 상단 메뉴의 후불 카테고리를 모두 수집한다."""
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs
import requests
from bs4 import BeautifulSoup
from services.crawler.menu_cards import parse_menu_cards


class WellCrawler:
    URL = 'https://www.idowell.co.kr/rate_plan.do'
    CATEGORIES = ('T008', 'T009', 'T006', 'T004', 'T011')

    @staticmethod
    def canonical_url(href):
        parts = urlsplit(urljoin(WellCrawler.URL, href))
        return urlunsplit((parts.scheme, parts.netloc, re.sub(r';jsessionid=[^/?;]+', '', parts.path, flags=re.I), parts.query, ''))

    def fetch_raw_plans(self):
        session = requests.Session()
        session.headers['User-Agent'] = 'Mozilla/5.0'
        seen = set()
        records = []
        self.excluded = []
        for category in self.CATEGORIES:
            response = session.get(self.URL, params={'type': category}, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            cards = soup.select('a.rate_link, a.card_rate_link')
            if not cards:
                raise ValueError(f'위너스텔 후불 카테고리 {category} 상품 없음')
            # If pagination is introduced, do not silently accept just its first page.
            if soup.select('.pagination a, .paging a'):
                raise ValueError('위너스텔 페이지 분할 구조 변경: 전체 수집 확인 필요')
            for card in cards:
                url = self.canonical_url(card.get('href', ''))
                code = parse_qs(urlsplit(url).query).get('no', [None])[0]
                if not code or urlsplit(url).hostname != 'www.idowell.co.kr':
                    raise ValueError('위너스텔 상품 코드/공식 주소 확인 실패')
                if code in seen:
                    continue
                seen.add(code)
                title = card.select_one('.title')
                if title and any(word in title.get_text() for word in ('시니어', '공유')):
                    self.excluded.append({'code': code, 'reason': '연령 제한 또는 추가 공유 회선'})
                    continue
                card['href'] = url
                def detail(href):
                    result = session.get(href, timeout=15)
                    result.raise_for_status()
                    return BeautifulSoup(result.content, 'html.parser')
                parsed = parse_menu_cards(BeautifulSoup(str(card), 'html.parser'), '위너스텔(WELL)', response.url, '', fetch_detail=detail)
                if len(parsed) != 1:
                    raise ValueError(f'위너스텔 상품 {code} 가격/기간 검증 실패')
                records.extend(parsed)
        return records
