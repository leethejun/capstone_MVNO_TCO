"""KG모바일의 공개 상품 API 수집. SPA HTML 대신 실제 화면과 같은 데이터 사용."""
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List
import requests
from bs4 import BeautifulSoup
from services.crawler.base import BaseCrawler


class KgMobileCrawler(BaseCrawler):
    BASE_URL = 'https://www.kgmobile.co.kr'
    HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': BASE_URL + '/plan'}

    def __init__(self, timeout=15, delay_sec=0.1):
        self.timeout = timeout
        self.delay_sec = delay_sec
        self.skipped = 0

    @staticmethod
    def available(item, now=None):
        if item.get('useFlag') != 'Y':
            return False
        now = now or datetime.now(ZoneInfo('Asia/Seoul')).replace(tzinfo=None)
        for key, before in [('startDate', True), ('endDate', False)]:
            if item.get(key):
                try:
                    boundary = datetime.fromisoformat(item[key]).replace(tzinfo=None)
                except (ValueError, TypeError):
                    return False
                if (before and boundary > now) or (not before and boundary < now):
                    return False
        return True

    def _get_list(self, endpoint, params):
        """긍정적인 page/limit로 실제 totalPage까지 수집한다. 실패 시 부분 결과를 반환하지 않는다."""
        items = []
        for page in range(1, 101):
            response = requests.get(self.BASE_URL + endpoint,
                                    params={**params, 'page': page, 'limit': 100},
                                    headers=self.HEADERS, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            entity = payload.get('entity') or {}
            batch = entity.get('list')
            if payload.get('code') != 1 or not isinstance(batch, list):
                raise ValueError('KG모바일 상품 API 응답 형식 변경')
            items.extend(batch)
            info = entity.get('pageInfo') or {}
            total = int(info.get('totalPage') or 1)
            if page >= total:
                return items
            if not batch:
                raise ValueError('KG모바일 상품 API 페이지 누락')
            time.sleep(self.delay_sec)
        raise ValueError('KG모바일 상품 API 페이지 상한 초과')

    def fetch_raw_plans(self) -> List[Dict[str, Any]]:
        # 모든 상품 API에는 비공개 그룹/제휴 전용 상품도 존재한다.
        # 사이트에 게시된 그룹을 먼저 읽고 각 그룹의 실제 상품만 수집한다.
        groups = self._get_list('/api/product/plan/group', {'isUser': 'true'})
        groups = [group for group in groups if self.available(group) and group.get('planCount', 0) > 0]
        if not groups:
            raise ValueError('KG모바일 공개 상품 그룹이 비어 있습니다.')
        plans, seen = [], set()
        self.skipped = 0
        for group in groups:
            rows = self._get_list('/api/product/plan', {
                'isUser': 'true', 'useFlag': 'Y', 'planGroupNo': group['planGroupNo'],
                'orderType': 'DISPLAY_ORDER'
            })
            for row in rows:
                if row.get('planNo') in seen or not self.available(row):
                    continue
                plan = self.parse_plan(row, group)
                if plan is None:
                    self.skipped += 1
                    continue
                seen.add(row['planNo'])
                plans.append(plan)
            if self.delay_sec:
                time.sleep(self.delay_sec)
        if not plans:
            raise ValueError('KG모바일의 검증 가능한 공개 요금제가 없습니다.')
        print(f'[KgMobileCrawler] {len(plans)}건 수집, 가격/스펙 검증 제외 {self.skipped}건')
        return plans

    @staticmethod
    def parse_plan(row, group=None):
        group = group or {}
        try:
            title = str(row['planName']).strip()
            basic = int(row['basicAmount'])
            sales = row['saleList']
            # isUser 파라미터 없는 API 응답은 saleList=null: 정상가를 할인가로 오인하지 않는다.
            if not title or not isinstance(sales, list) or basic <= 0:
                return None
            lifetime = sum(int(sale['ltSaleAmount']) for sale in sales)
            promotion = sum(int(sale['prSaleAmount']) for sale in sales)
            if any(int(sale[key]) < 0 for sale in sales for key in ('ltSaleAmount', 'prSaleAmount')):
                return None
            discount = basic - lifetime - promotion
            if discount < 0:
                return None
            content = BeautifulSoup(row.get('contents') or '', 'html.parser').get_text(' ', strip=True)
            if promotion:
                # 쿠폰/카드/사은품의 개월 수가 아닌 기본료 할인 문장만 우선한다.
                match = re.search(r'기본료\s*할인\s*프로모션(?:은|이)[^.\n]{0,100}?(\d+)\s*개월', content)
                if match is None:
                    match = re.search(r'(\d+)\s*개월\s*(?:할인|간)|_(\d+)\s*개월', title + ' ' + str(group.get('groupName', '')))
                if match is None:
                    return None
                months = int(next(value for value in match.groups() if value is not None))
                if not 1 <= months <= 120:
                    return None
                # 평생 할인 + 기간 할인 조합은 기간 할인 종료 후 평생 할인 가격으로 돌아간다.
                normal = basic - lifetime
            else:
                months = -1 if lifetime > 0 else 0
                normal = basic
            unit = str(row['basicMonthDataUnit']).upper()
            if unit not in ('GB', 'MB'):
                return None
            data = float(row['basicMonthData'])
            day = max(0, float(row.get('basicDayData', 0)))
            day_unit = str(row.get('basicDayDataUnit', 'GB')).upper()
            # -1은 월 정량 없는 일일 제공형(예: 매일 5GB+5Mbps)이다.
            if data == -1 and day > 0:
                data = 0
            if data < 0 or day_unit not in ('GB', 'MB'):
                return None
            qos = str(row.get('basicQos') or '').strip()
            # '-'는 미제공, '-1'은 무제한: 서로 다른 표기다.
            voice = 0 if str(row['basicVoice']).strip() == '-' else int(row['basicVoice'])
            sms = 0 if str(row['basicSms']).strip() == '-' else int(row['basicSms'])
            if voice < -1 or sms < -1 or row.get('network') not in ('4G', '5G'):
                return None
            specs = f'데이터 {data:g}{unit}' + (f'+매일{day:g}{day_unit}' if day else '') + (f'+{qos}' if re.search(r'\d', qos) else '')
            raw = (f'[공식몰] {title} | {specs} | 통화 ' + ('무제한' if voice == -1 else f'{voice}분')
                   + ' | 문자 ' + ('무제한' if sms == -1 else f'{sms}건')
                   + f' | [월요금 요소 검증] 기본료 {basic}원, 평생할인 {lifetime}원, 기간할인 {promotion}원'
                   + f' | [KG API planNo={int(row["planNo"])}] [출처: {KgMobileCrawler.BASE_URL}/plan/{int(row["planNo"])}]')
            return {'telecom_name': 'KG모바일', 'title': title, 'network_type': '5G' if row['network'] == '5G' else 'LTE',
                    'discount_price': discount, 'normal_price': normal, 'discount_months': months, 'raw_text': raw}
        except (KeyError, ValueError, TypeError, OverflowError):
            return None
