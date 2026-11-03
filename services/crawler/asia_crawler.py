"""아시아모바일 공식 후불 목록의 다단계 할인과 표시 스펙을 해석한다."""
import json
import re

import requests

from services.crawler.structured_official import record


class AsiaCrawler:
    BASE = 'https://asiamobile.kr'
    PAGE = '/view/price/pricePlan.aspx'
    API = '/common/component/price/AjaxPricePlan.aspx'

    def __init__(self):
        self.skipped = []
        self.excluded = []
        self.total = 0

    @staticmethod
    def parse(item):
        if item['PAYDIV'] != 'L':
            return None
        title = item['GDNM']
        if re.search(r'복지|시니어|청소년|키즈|외국인|태블릿|워치', title):
            return None
        base = int(str(item['TT_AMT']).replace(',', ''))
        discounts = [d for d in item['DISCOUNT'] if d['USEYN'] == 'Y']
        steps = []
        for d in discounts:
            amt, period = int(d['AMT']), int(d['PERIOD'])
            if amt < 0 or period <= 0:
                raise ValueError('아시아모바일 할인 금액/기간 오류')
            steps.append((amt * 11 // 10, period))
        periods = {period for _, period in steps if period != 999}
        if len(periods) > 1:
            raise ValueError('아시아모바일 3단계 이상 요금은 현재 TCO 모델로 표현 불가')
        current = base - sum(amt for amt, _ in steps)
        if steps and not periods:
            months, normal = -1, base
        elif periods:
            months = periods.pop()
            normal = base - sum(amt for amt, period in steps if period == 999)
        else:
            months, normal = 0, base
        if int(str(item['REAL_AMT']).replace(',', '')) != current:
            raise ValueError('아시아모바일 표시 납부액과 할인 계산 불일치')
        # DATAAMOUNT에는 화면과 다른 내부 값이 있어 실제 표시값 SEEDATA 우선.
        data = item['SEEDATA']
        if not re.search(r'\d\s*(?:GB|MB)|무제한', data, re.I):
            raise ValueError('아시아모바일 데이터 제공량 누락')
        return record('아시아모바일', title, current, normal, months, data,
                      item['SEEVOICE'], item['SEELETTER'], item['MNO_CD'],
                      item['GDCD'], '5G' if '5G' in title else 'LTE')

    def fetch_raw_plans(self):
        self.skipped = []; self.excluded = []
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'Mozilla/5.0',
                                    'Referer': self.BASE + self.PAGE,
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
            session.get(self.BASE + self.PAGE, timeout=20).raise_for_status()

            def query(network):
                payload = {'header': [{'type': '01'}], 'body': [dict(
                    seq='', mnoCd=network, order_type='DEFAULT', order_align='ASC', payDiv='L')]}
                response = session.post(self.BASE + self.API, data=json.dumps(payload), timeout=25)
                response.raise_for_status()
                value = response.json()
                if value.get('RESULT') != 'Y' or not isinstance(value.get('DATA'), list):
                    raise ValueError('아시아모바일 공식 후불 목록 조회 실패')
                return value['DATA']

            rows = query('')
            def unique(items):
                result = {}
                fields = ('GDNM','TT_AMT','REAL_AMT','DISCOUNT','SEEDATA','SEEVOICE','SEELETTER','PAYDIV')
                for row in items:
                    key = (row['MNO_CD'], row['GDCD'])
                    if key in result and any(row[f] != result[key][f] for f in fields):
                        raise ValueError('아시아모바일 동일 상품의 가격/스펙 충돌')
                    result[key] = row
                return result
            all_products, network_products = unique(rows), unique(query('K') + query('L'))
            if not rows or all_products.keys() != network_products.keys():
                raise ValueError('아시아모바일 전체 목록과 통신망별 목록 불일치')
            for key in all_products:
                if self.parse(all_products[key]) != self.parse(network_products[key]):
                    raise ValueError('아시아모바일 통신망별 가격/스펙 불일치')
            rows = list(all_products.values())
        self.total = len(rows)
        result = []
        for row in rows:
            try:
                plan = self.parse(row)
                if plan:
                    result.append(plan)
                else:
                    self.excluded.append(row['GDNM'])
            except (KeyError, TypeError, ValueError) as exc:
                self.skipped.append(f'{row.get("GDNM", "상품명 미확인")} ({exc})')
        return result
