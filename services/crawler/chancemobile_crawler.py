"""찬스모바일 공식몰 AJAX 요금제 조회. 가격/기간 검증 불가능한 상품은 제외."""
import re
import requests


class ChanceMobileCrawler:
    PAGE = 'https://chancemobile.co.kr/view/plan/phone_plan.aspx'
    API = 'https://chancemobile.co.kr/common/component/plan/AjaxPhone_plan.aspx'

    def __init__(self):
        self.skipped = []

    @staticmethod
    def _money(value):
        try:
            return int(str(value).replace(',', '').strip())
        except (ValueError, TypeError):
            return None

    def _parse(self, item):
        name = str(item.get('GDNM') or '').strip()
        code = str(item.get('GDCD') or '').strip()
        if not name or not code:
            raise ValueError('상품명/상품코드 누락')
        normal = self._money(item.get('TT_AMT'))
        current = self._money(item.get('DISCOUNT'))
        reference = self._money(item.get('ORGCHARGE'))
        period = str(item.get('LIMPERIOD') or '').strip()
        is_lifetime = '평생할인' in name or '평생 할인' in name
        match = re.fullmatch(r'(\d+)\s*개월', period)
        if match:
            months = int(match.group(1))
            # 공식 화면의 "N개월 후" 금액은 정가 TT_AMT가 아닌 ORGCHARGE다.
            # 종료 후 가격이 없으면 정가로 대체하지 않고 검증에서 제외한다.
            normal = reference
        elif is_lifetime and not period:
            months = -1
        elif not period and current == 0 and reference == 0 and normal is not None and normal > 0:
            # 공식몰에서 할인 없는 일반 요금제로 확인된 상품.
            # DISCOUNT=0은 무료가 아니라 프로모션 미적용을 뜻한다.
            current = normal
            months = 0
        elif not period and current is not None and normal is not None and current == normal:
            months = 0
        elif not period and current is not None and current > 0 and normal is not None and current < normal:
            # 할인기간이 표시되지 않는 비-평생 상품은 가격 오인 가능성이 있어 제외.
            raise ValueError('할인기간 미공개')
        else:
            raise ValueError(f'할인기간 해석 불가: {period!r}')
        if current is None or normal is None or not (0 < normal <= 300000 and 0 <= current <= normal):
            raise ValueError('할인가/정상가 범위 오류')
        if current == 0 and months <= 0:
            raise ValueError('기간 없는 0원 요금')
        if months == 0 and current != normal:
            raise ValueError('할인기간 없이 정상가/판매가 불일치')
        data = str(item.get('DATAAMOUNT') or '').strip()
        extra = str(item.get('ADD_DATA') or '').strip()
        qos = str(item.get('QOSAMT') or '').strip()
        if extra and extra not in ('0', '0GB'):
            data += f' + {extra}'
        if qos and qos not in ('0', '0Mbps'):
            data += f' {qos}'
        voice = str(item.get('VOICEAMOUNT') or '').strip()
        sms = str(item.get('LETTERAMOUNT') or '').strip()
        network = str(item.get('MNO_CD') or '').strip()
        net_type = str(item.get('NETDIV') or 'LTE').strip().upper()
        if not data or not voice or not sms:
            raise ValueError('데이터/통화/문자 스펙 누락')
        return {
            'telecom_name': '찬스모바일',
            'title': '[공식몰] ' + name,
            'network_type': net_type if net_type in ('LTE', '5G') else 'LTE',
            'discount_price': current,
            'normal_price': normal,
            'discount_months': months,
            'raw_text': (f'{name} | 데이터 {data} | 통화 {voice} | 문자 {sms} | 망: {network} '
                         f'[출처: 찬스모바일 공식홈페이지] [상품 코드: {code}] '
                         f'[공식 API ORGCHARGE: {reference}] [할인기간: {period or "할인 없음"}]'),
        }

    def fetch_raw_plans(self):
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': self.PAGE})
        response = session.get(self.PAGE, timeout=25)
        response.raise_for_status()
        payload = {'header': [{'type': '02'}], 'body': [{'seq': '', 'order_type': '', 'order_align': ''}]}
        response = session.post(self.API, json=payload, headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get('RESULT') != 'Y' or not isinstance(result.get('DATA'), list):
            raise ValueError('찬스모바일 공식 API 응답 오류')
        items = result['DATA']
        if not items:
            raise ValueError('찬스모바일 공식 API 조회 0건')
        plans, seen = [], set()
        for item in items:
            try:
                plan = self._parse(item)
                code = str(item['GDCD'])
                if code not in seen:
                    seen.add(code)
                    plans.append(plan)
            except (ValueError, KeyError, TypeError) as exc:
                self.skipped.append(f"{item.get('GDCD', '?')} {item.get('GDNM', '?')}: {exc}")
        print(f'[ChanceMobileCrawler] 공식 API {len(items)}건, 유효 {len(plans)}건, 제외 {len(self.skipped)}건')
        return plans
