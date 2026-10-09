"""공식 상단 요금제 메뉴의 공통 카드/상세 가격표 파서."""
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup


def amount(text):
    m = re.fullmatch(r'\s*([\d,]+)\s*(?:원)?\s*', text)
    return int(m[1].replace(',', '')) if m else None


def detail_base(soup):
    for table in soup.select('table'):
        heads = [h.get_text(' ', strip=True) for h in table.select('thead th')]
        index = next((i for i, h in enumerate(heads) if '기본료' in h), None)
        cells = table.select('tbody tr:first-child td')
        if index is not None and len(cells) > index:
            return amount(cells[index].get_text(strip=True))
    return None


def parse_menu_cards(soup, name, url, network, fetch_detail=None):
    result = []
    seen = set()
    for card in soup.select('a.card_rate_link, a.rate_link'):
        href = urljoin(url, card.get('href', ''))
        if href in seen:
            continue
        seen.add(href)
        title_el = card.select_one('.title')
        price_el = card.select_one('.price')
        if not title_el or not price_el:
            continue
        title_copy = BeautifulSoup(str(title_el), 'html.parser')
        for badge in title_copy.select('.badge_wrap, .text_light_color'):
            badge.decompose()
        title = title_copy.get_text(' ', strip=True)
        price_copy = BeautifulSoup(str(price_el), 'html.parser')
        ref = price_copy.select_one('.ref')
        ref_text = ref.get_text(' ', strip=True) if ref else ''
        for excluded in price_copy.select('.origin, .ref'):
            excluded.decompose()
        current = re.search(r'([\d,]+)\s*원', price_copy.get_text(' ', strip=True))
        if not title or not current:
            continue
        discount = int(current[1].replace(',', ''))
        after = re.search(r'(\d+)\s*개월\s*(이후|차부터|부터)\s*([\d,]+)\s*원', ref_text)
        origin = price_el.select_one('.origin')
        normal = amount(origin.get_text(strip=True)) if origin else None
        text = card.get_text(' ', strip=True)
        if after:
            months = int(after[1]) - (1 if after[2] == '차부터' else 0)
            normal = int(after[3].replace(',', ''))
        else:
            lifetime = '평생' in text
            # 쿠폰 지급 기간은 월요금 할인 기간이 아니다.
            finite = re.search(r'(\d+)\s*개월\s*할인', text)
            months = -1 if lifetime else int(finite[1]) if finite else 0
            if normal is None and months == 0:
                normal = discount  # 할인 표시가 없는 공식 기본요금
            if normal is None:
                try:
                    if fetch_detail:
                        detail = fetch_detail(href)
                    else:
                        response = requests.get(href, timeout=10)
                        response.raise_for_status()
                        detail = BeautifulSoup(response.content, 'html.parser')
                    normal = detail_base(detail)
                except requests.RequestException:
                    continue
            if normal is None:
                continue
            if months == 0 and normal != discount:
                # 할인은 있으나 종료 조건을 확인하지 못했으므로 추측하지 않는다.
                continue
        if months < -1 or normal < discount or normal <= 0:
            continue
        specs = card.select('.desc li')
        data = specs[0].get_text(' ', strip=True) if specs else ''
        voice = specs[1].get_text(' ', strip=True) if len(specs) > 1 else ''
        sms = specs[2].get_text(' ', strip=True) if len(specs) > 2 else ''
        voice = re.sub(r'^통화\s*', '', voice).replace('기본제공', '무제한')
        sms = re.sub(r'^문자\s*', '', sms).replace('기본제공', '무제한')
        badge = card.select_one('.badge_LGT, .badge_SKT, .badge_KT')
        carrier = badge.get_text(strip=True) if badge else network
        result.append(dict(telecom_name=name,title=f'[공식몰] {title}',
            network_type='5G' if re.search(r'\b5G\b',text) else 'LTE',
            discount_price=discount,normal_price=normal,discount_months=months,
            raw_text=f'{title} | 데이터 {data} | 통화 {voice} | 문자 {sms} | 망: {carrier} | {text} [출처: {name} 공식홈페이지] [상품 URL: {href}]'))
    return result
