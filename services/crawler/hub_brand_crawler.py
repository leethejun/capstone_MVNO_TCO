"""알뜰폰허브 브랜드관의 전체 페이지와 상세 스펙을 검증한다."""
import time
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import requests
from bs4 import BeautifulSoup
from parser import PlanTextParser

from services.crawler.mvnohub_crawler import MvnohubCrawler
from services.crawler.pricing_validation import valid_pricing
from services.crawler.telecom_registry import canonical_telecom_name

# 2026-11-03 brand.do의 공개 링크. 브랜드 목록 일시 장애에도 각 공개 목록을 방문한다.
HUB_BRAND_IDS = {
    'A모바일(에넥스텔레콤)': (7,), 'KB리브모바일': (3,), '티플러스': (18,),
    '헬로모바일': (19,), 'U+유모바일': (4,), '고고모바일(고고팩토리)': (2,),
    '마블링': (20,), '슈가모바일': (1000,), '스마텔': (5,), '핀다이렉트': (5021,),
    '아시아모바일': (21,), '아이즈모바일': (6,), 'SK 7mobile': (8,),
    '위너스텔(WELL)': (10,), '모빙': (11,), '이지모바일': (15,),
    '인스모바일': (1040,), '조이텔': (5061,), '찬스모바일': (12,),
    'KT스카이라이프': (13,), 'KT M모바일': (14,), '이야기모바일': (16,),
    '토스모바일': (5041,), '프리티': (9, 17),
}


class HubCatalogChanged(ValueError):
    """목록 조회 중 상품 추가/정렬 변경이 감지된 경우."""


class HubBrandCrawler:
    SIZE = 12

    def __init__(self, name, url, timeout=25, delay_sec=0.15):
        if not re.fullmatch(r"https://www\.mvnohub\.kr/brand/plan/\d+\.do", url):
            raise ValueError("허브 브랜드관 주소 형식 오류")
        self.name = canonical_telecom_name(name)
        self.URL = url
        self.timeout = timeout
        self.delay_sec = delay_sec
        self.complete = False
        self.total = 0
        self.pages = 0
        self._request_lock = Lock()
        self._next_request_at = 0

    def _get(self, session, url, params):
        for attempt in range(3):
            try:
                with self._request_lock:
                    pause = self._next_request_at - time.monotonic()
                    if pause > 0:
                        time.sleep(pause)
                    self._next_request_at = time.monotonic() + self.delay_sec
                response = session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(0.5 * (2 ** attempt))

    def parse(self, item, card):
        return self._parse(item, card, self.name)

    @staticmethod
    def _parse(item, card, name):
        if canonical_telecom_name(item['partnerName']) != name:
            raise ValueError('브랜드 허브 목록에 다른 사업자 상품 포함')
        plan = MvnohubCrawler()._parse_card(card)
        if not plan or canonical_telecom_name(plan['telecom_name']) != name:
            raise ValueError('브랜드 허브 상품 카드 파싱 실패')
        if str(item['productId']) != plan.pop('_product_id'):
            raise ValueError('브랜드 허브 API와 카드 상품 ID 불일치')
        title = MvnohubCrawler()._clean_text(item['productName'])
        if title != plan['title'] or item['monthlyPaymentFee'] != plan['discount_price']:
            raise ValueError('브랜드 허브 API와 카드 상품명/월요금 불일치')
        current, base, permanent = item['monthlyPaymentFee'], item['baseMonthlyFee'], item['planDiscountAmount'] or 0
        period, temporary = item['contractDiscountPeriod'] or 0, item['contractDiscountAmount'] or 0
        if any(type(v) is not int for v in (current,base,permanent,period,temporary)):
            raise ValueError('브랜드 허브 가격/할인 기간 형식 오류')
        if min(permanent, period, temporary) < 0:
            raise ValueError('브랜드 허브 음수 할인 정보')
        after = base - permanent
        if period > 0 and temporary > 0:
            if current + temporary != after or plan['normal_price'] != after or plan['discount_months'] != period:
                raise ValueError('브랜드 허브 할인 종료 후 요금/기간 불일치')
            months, normal = period, after
        elif temporary == 0 and current == after:
            months, normal = (-1, base) if permanent else (0, current)
        else:
            raise ValueError('브랜드 허브 할인 구조 미확인')
        plan.update(telecom_name=name, normal_price=normal, discount_months=months,
                    network_type=item['networkProtocol'])
        if '[허브 상품 ID:' not in plan['raw_text']:
            plan['raw_text'] += f' [허브 상품 ID: {item["productId"]}]'
        plan['raw_text'] += f' [상품 URL: https://www.mvnohub.kr/product/products/{item["productId"]}.do]'
        if not valid_pricing(plan):
            raise ValueError('브랜드 허브 가격 검증 실패')
        plan['_hub_product_id'] = str(item['productId'])
        return plan

    def fetch_raw_plans(self):
        for attempt in range(3):
            try:
                return self._fetch_once()
            except HubCatalogChanged:
                if attempt == 2:
                    raise
                time.sleep(.5 * (attempt + 1))

    def _fetch_once(self):
        self.complete = False; self.pages = 0; self.total = 0
        result = []; seen = set(); pending = []; total_pages = None
        with requests.Session() as session, ThreadPoolExecutor(max_workers=2) as details:
            session.headers.update(MvnohubCrawler.HEADERS)
            session.headers['Referer'] = self.URL
            for page in range(100):
                value = self._get(session, self.URL + '/filter', dict(
                    page=page, size=self.SIZE, sortBy='order', sortDirection='DESC')).json()
                if page == 0:
                    self.total, total_pages = value['totalElements'], value['totalPages']
                    if (type(self.total) is not int or self.total < 0 or type(total_pages) is not int
                            or total_pages != (self.total + self.SIZE - 1) // self.SIZE or total_pages > 100):
                        raise ValueError('브랜드 허브 전체 상품 수/페이지 수 검증 실패')
                    if self.total == 0:
                        if value['content'] or value['hasNext']:
                            raise ValueError('허브 빈 목록 메타데이터 불일치')
                        response = self._get(session, self.URL, {'page': 0})
                        if BeautifulSoup(response.content, 'html.parser').select('.list_plan_set .plan_card'):
                            raise ValueError('허브 API 빈 목록과 HTML 상품 목록 불일치')
                        self.complete = True
                        return []
                if (value['number'] != page or value['totalElements'] != self.total
                        or value['totalPages'] != total_pages or value['hasNext'] != (page + 1 < total_pages)):
                    raise HubCatalogChanged('브랜드 허브 페이지 누락 또는 수집 도중 목록 변경')
                items = value['content']
                expected = min(self.SIZE, self.total - page * self.SIZE)
                if len(items) != expected:
                    raise ValueError('브랜드 허브 API 페이지 상품 수 불일치')
                response = self._get(session, self.URL, {'page': page})
                soup = BeautifulSoup(response.content, 'html.parser')
                nodes = soup.select('.list_plan_set .plan_card')
                cards = {card.get('data-product-id'): card for card in nodes}
                ids = {str(item['productId']) for item in items}
                if (len(ids) != expected or len(cards) != len(nodes) or set(cards) != ids or seen & ids):
                    raise HubCatalogChanged('브랜드 허브 API/화면 상품 목록 불일치 또는 페이지 중복')
                for item in items:
                    pending.append((item, self.parse(item, cards[str(item['productId'])])))
                seen.update(ids); self.pages += 1
                if page + 1 == total_pages:
                    if len(seen) != self.total:
                        raise ValueError('브랜드 허브 전체 상품 수 불일치')
                    break
                if self.delay_sec:
                    time.sleep(self.delay_sec)
            else:
                raise ValueError('브랜드 허브 전체 목록 순회 미완료')
            def validate_item(entry):
                item, plan = entry
                # 목록 확정 후 상세를 읽어 상세 조회 중 새 상품이 페이지 경계를 밀지 않게 한다.
                with requests.Session() as detail_session:
                    detail_session.headers.update(session.headers)
                    detail = self._get(detail_session, f'https://www.mvnohub.kr/product/products/{item["productId"]}.do', {})
                try:
                    self.apply_detail(plan, item, BeautifulSoup(detail.content, 'html.parser'))
                except ValueError as exc:
                    raise ValueError(f'브랜드 허브 상품 {item["productId"]} {item["productName"]}: {exc}') from exc
                return plan
            result.extend(details.map(validate_item, pending))
            self.complete = True
            return result

    def apply_detail(self, plan, item, soup):
        return self._apply_detail(plan, item, soup, self.name)

    @staticmethod
    def _apply_detail(plan, item, soup, name):
        # 목록/API에는 일일 데이터가 생략되므로 모든 상품의 상세 스펙을 읽는다.
        fields = {}
        required = ('기본 데이터','데이터 소진 후 속도','데이터 소진 후 용량','기본 통화','기본 문자','통신사','통신 규격','통신망')
        label = soup.find('dt', string=lambda text: text and text.strip() == '기본 데이터')
        section = label.find_parent('div', class_='gray_box') if label else None
        if section is None:
            raise ValueError('브랜드 허브 상세 스펙 영역 누락')
        for dl in section.select('dl'):
            dt, dd = dl.find('dt', recursive=False), dl.find('dd', recursive=False)
            if dt is not None and dd is not None:
                label, value = dt.get_text(' ', strip=True), dd.get_text(' ', strip=True)
                if label not in required:
                    continue
                if label in fields and fields[label] != value:
                    raise ValueError('브랜드 허브 상세 스펙 필드 충돌')
                fields[label] = value
        mandatory = ('기본 데이터','기본 통화','기본 문자','통신사','통신 규격','통신망')
        if any(field not in fields for field in mandatory) or canonical_telecom_name(fields['통신사']) != name:
            raise ValueError('브랜드 허브 상세 스펙 누락 또는 다른 사업자 상품')
        if fields['통신 규격'] != item['networkProtocol']:
            raise ValueError('브랜드 허브 목록과 상세 통신 규격 불일치')
        data = fields['기본 데이터']
        if not re.search(r'\d\s*(?:GB|MB)|무제한', data, re.I):
            raise ValueError('브랜드 허브 상세 데이터 제공량 미확인')
        after = fields.get('데이터 소진 후 용량', '')
        if re.search(r'\d\s*(?:GB|MB)', after, re.I):
            data += ' + ' + after
        qos = fields.get('데이터 소진 후 속도', '')
        if not qos and PlanTextParser._extract_qos_speed(item.get('dataAfter') or '') > 0:
            # 일부 무제한 상품은 상세 표에서 속도 행을 숨긴다. 목록 카드의 명시 속도와
            # API 속도가 일치할 때만 그 값을 보완하며 상품명에서 속도를 추정하지 않는다.
            speed = PlanTextParser._extract_qos_speed(item['dataAfter'])
            explicit = ' | '.join(part for part in plan['raw_text'].split('|')
                                  if re.match(r'^\s*(?:데이터|소진후)\s',part))
            if PlanTextParser._extract_qos_speed(explicit) != speed:
                raise ValueError('브랜드 허브 상세 소진 후 속도 누락 및 목록/API 불일치')
            qos = item['dataAfter']
        if re.search(r'\d\s*(?:Mbps|Kbps)', qos, re.I):
            data += ' + ' + qos
        source = plan['raw_text'].split('[출처:', 1)[1]
        plan['raw_text'] = (f'{plan["title"]} | 데이터 {data} | 통화 {fields["기본 통화"]} '
                            f'| 문자 {fields["기본 문자"]} | 망: {fields["통신망"]} '
                            f'| 혜택 {item.get("benefits") or ""} [출처:{source}')


def merge_hub_records(global_records, detailed_records, complete_carriers=()):
    """브랜드 상세를 우선하며 전역 전용 상품은 남기고 상품 ID 중복을 제거한다."""
    detailed_ids = {str(row['_hub_product_id']) for row in detailed_records if row.get('_hub_product_id')}
    complete = set(complete_carriers)
    return [row for row in global_records
            if str(row.get('_hub_product_id')) not in detailed_ids
            and canonical_telecom_name(row.get('telecom_name','')) not in complete] + list(detailed_records)
