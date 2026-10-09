"""아이즈 공식 전체 목록의 가격과 할인 기간을 독립적으로 읽는다."""
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from services.crawler.base import BaseCrawler


class EyesCrawler(BaseCrawler):
    URL = 'https://eyes.co.kr/payplan/all_plan/'

    def __init__(self, headers=None, timeout=15, delay_sec=0.1):
        self.headers = headers or {'User-Agent':'Mozilla/5.0'}
        self.timeout, self.delay_sec = timeout, delay_sec

    @staticmethod
    def parse_card(card):
        title = card.select_one('.mid > div > p.body_medium')
        current = card.select_one('.price .current_p')
        original = card.select_one('.price .org_p')
        period = card.select_one('.price .period')
        data = card.select_one('.plan_tit')
        info = card.select('.plan_info > p')
        if not all([title, current, data]) or len(info) < 2:
            return None
        def amount(node):
            match = re.search(r'(\d[\d,]*)\s*원', node.get_text(' ', strip=True))
            return int(match.group(1).replace(',', '')) if match else None
        label = period.get_text(' ', strip=True) if period else ''
        discount = amount(current)
        # 할인 표시가 없는 일반 요금제만 현재 요금을 기본료로 읽는다.
        normal = amount(original) if original else (discount if not label and not card.select_one('.badge.period') else None)
        if discount is None or normal is None or not 0 <= discount <= normal or normal <= 0:
            return None
        if '평생' in label:
            months = -1
        elif match := re.search(r'(\d+)\s*개월', label):
            months = int(match.group(1))
        elif discount == normal:
            months = 0
        else:
            return None
        voice = info[0].get_text(' ',strip=True)
        sms = info[1].get_text(' ',strip=True)
        voice = '무제한' if '기본제공' in voice else voice
        sms = '무제한' if '기본제공' in sms else sms
        name = title.get_text(' ',strip=True)
        raw = (f'[공식몰] {name} | 데이터 {data.get_text(" ",strip=True)} | 통화 {voice} | 문자 {sms}'
               f' | [월요금 요소 검증] 정상가 {normal}원, 할인가 {discount}원, 할인기간 {label}'
               f' [출처: 아이즈모바일 공식홈페이지] [상품 URL: {urljoin(EyesCrawler.URL,card.get("href", ""))}]')
        return dict(telecom_name='아이즈모바일',title=f'[공식몰] {name}',network_type='5G' if '5G' in name.upper() else 'LTE',
                    discount_price=discount,normal_price=normal,discount_months=months,raw_text=raw)

    def fetch_raw_plans(self):
        plans, seen = [], set()
        page, last = 1, 1
        while page <= last:
            if page > 100:
                raise ValueError('아이즈 목록 페이지 상한 초과')
            response = requests.get(self.URL, params={'page':page},headers=self.headers,timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text,'html.parser')
            cards = soup.select('.plancard_list .plan_card')
            if not cards:
                raise ValueError(f'아이즈 목록 {page}페이지 비어 있음')
            footer = soup.select_one('.list_footer')
            if footer:
                pages = re.findall(r'page=(\d+)',str(footer))
                last = max([last]+[int(value) for value in pages])
            for card in cards:
                key = card.get('href')
                if key in seen:
                    continue
                plan = self.parse_card(card)
                if plan is None:
                    raise ValueError(f'아이즈 상품 가격/기간 확인 실패: {key}')
                seen.add(key); plans.append(plan)
            page += 1
            if self.delay_sec:
                time.sleep(self.delay_sec)
        print(f'[EyesCrawler] {len(plans)}개 상품, {last}페이지 수집')
        return plans
