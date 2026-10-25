"""공식 요금제 메뉴의 모든 카테고리를 방문하고 상품 코드로 중복 제거."""
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs
import requests
from bs4 import BeautifulSoup
from services.crawler.menu_cards import parse_menu_cards

URLS = {
    '아정당모바일': 'https://www.ajdmobile.co.kr/rate_plan.do',
    '인스모바일': 'https://www.insmobile.co.kr/rate_plan.do',
    '마블링': 'https://marvelring.com/rate_plan.do',
    '슈가모바일': 'https://www.sugarmobile.co.kr/rate_plan.do',
    '한패스모바일': 'https://www.hanpassmobile.co.kr/rate_plan.do',
    'KCTV모바일': 'https://kctvm.com/rate_plan.do',
    '온국민폰': 'https://xn--3e0b39yfuhjlo.kr/rate_plan.do',
    '토리모바일': 'https://ntontel.com/rate_plan.do',
}


def stable_url(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, re.sub(r';jsessionid=[^/?;]+','',parts.path,flags=re.I),parts.query,''))


class MenuCatalogCrawler:
    def __init__(self, name): self.name = name

    def fetch_raw_plans(self):
        session = requests.Session()
        session.headers.update({'User-Agent':'Mozilla/5.0','Accept-Language':'ko-KR,ko;q=0.9'})
        pending = [URLS[self.name]]; visited = set(); products = set(); details = {}; result = []
        self.skipped = []; self.excluded = []
        while pending:
            url = pending.pop(0)
            if url in visited: continue
            if len(visited) >= 100: raise ValueError('공식 카테고리 순회 한도 초과')
            visited.add(url)
            r = session.get(url,timeout=15); r.raise_for_status()
            soup = BeautifulSoup(r.content,'html.parser')
            cards = soup.select('a.card_rate_link, a.rate_link')
            for a in soup.select('a[href]'):
                link = stable_url(urljoin(r.url,a['href'])); parts = urlsplit(link)
                if (parts.hostname == urlsplit(r.url).hostname and parts.path == '/rate_plan.do'
                        and not any(word in a.get_text() for word in ('선불','복지','청소년','시니어','공유'))
                        and link not in visited and link not in pending):
                    pending.append(link)
            if not cards:
                if re.search(r'(?:해당하는|등록된|검색된).*요금제.*없', soup.get_text(' ',strip=True)):
                    continue
                raise ValueError(f'{self.name} 공식 카테고리 상품 없음: {url}')
            for card in cards:
                href = stable_url(urljoin(r.url,card.get('href','')))
                code = parse_qs(urlsplit(href).query).get('no',[None])[0]
                if not code: raise ValueError('공식 상품 코드 누락')
                if code in products: continue
                products.add(code)
                title = card.select_one('.title')
                if any(word in (title.get_text() if title else '') + card.get_text(' ',strip=True)[:60] for word in ('선불','복지','시니어','청소년','주니어','태블릿','워치','공유')):
                    self.excluded.append(code); continue
                card['href'] = href
                def detail(target):
                    if target not in details:
                        response = session.get(target,timeout=15); response.raise_for_status()
                        details[target] = BeautifulSoup(response.content,'html.parser')
                    return details[target]
                parsed = parse_menu_cards(BeautifulSoup(str(card),'html.parser'),self.name,r.url,'',fetch_detail=detail)
                if not parsed: self.skipped.append(code)
                result.extend(parsed)
        return result
