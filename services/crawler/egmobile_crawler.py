"""EG Mobile public plan-list AJAX crawler (no database writes)."""
import re
import requests
from services.crawler.structured_official import record


class EgmobileCrawler:
    BASE = 'https://www.egmobile.co.kr'
    # Official detail pages verified as lifetime discounts (2026-10-30).
    LIFETIME_NAMES = (
        'EG 데이터 300MB',
        'EG 5G평생 2.5GB',
        'EGK LTE 시니어A',
        'EG 스마트디바이스10G',
        'EG 스마트디바이스20G',
    )

    def __init__(self):
        self.skipped = []

    @staticmethod
    def parse(item):
        name = str(item['name']).strip()
        normal = int(str(item['price1']).replace(',', ''))
        current = int(str(item['price2']).replace(',', ''))
        months = int(item['DUTYMONTH'])
        if not name or not item.get('FEECD') or not item.get('seq'):
            raise ValueError('상품명 또는 상품 식별자 누락')
        if '데이터 쉐어링' in name or '데이터쉐어링' in name:
            raise ValueError('독립 요금제가 아닌 데이터 쉐어링 서비스')
        if months < 0:
            raise ValueError('할인 기간 값 비정상')
        if current < normal and months == 0:
            if (name in EgmobileCrawler.LIFETIME_NAMES
                    or name.startswith('EGK LTE 시니어A(')):
                months = -1  # Existing TCO convention: lifetime discount.
            else:
                raise ValueError('할인 요금이 있으나 할인 기간 미확인')
        if current == normal:
            months = 0
        network = str(item.get('telecom') or '').strip()
        if network not in ('KT', 'SKT', 'LG', 'LGU+', 'U+'):
            raise ValueError('통신망 구분 미확인')
        data = str(item.get('data') or '').strip()
        if not data:
            raise ValueError('데이터 제공량 누락')
        qos = str(item.get('qos') or '').strip()
        if qos and qos not in data:
            data += ' + ' + qos
        extra = str(item.get('dataplus') or '').strip()
        if extra:
            data += ' | 추가 데이터: ' + extra
        # 5G is not implied by large data quotas; require explicit product indication.
        network_type = '5G' if re.search(r'(?<!\w)5G(?!\w)', name, re.I) else 'LTE'
        result = record('이지모바일', name, current, normal, months, data,
                        item.get('voice') or '', item.get('sms') or '', network,
                        item['FEECD'], network_type)
        result['raw_text'] += f" [상세: {EgmobileCrawler.BASE}/charge/view/{item['seq']}]"
        return result

    def fetch_raw_plans(self):
        self.skipped = []
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Referer': self.BASE + '/charge/list',
            'X-Requested-With': 'XMLHttpRequest',
        })
        landing = session.get(self.BASE + '/charge/list', timeout=20)
        landing.raise_for_status()
        results = []
        seen = set()
        expected_total = None
        for page in range(1, 21):
            response = session.post(self.BASE + '/app/ajax.app.php', data={
                'act': 'search_bill', 'te': '', 'ft': '0', 'ck': 'L',
                'page': str(page), 'start': '',
            }, timeout=20)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get('list'), list):
                raise ValueError('이지모바일 목록 API 응답 형식 변경')
            if expected_total is None:
                expected_total = int(payload['total'])
                if expected_total < 1:
                    raise ValueError('이지모바일 목록 API에서 상품이 반환되지 않음')
            rows = payload['list']
            if not rows:
                break
            fresh = 0
            for item in rows:
                code = str(item.get('FEECD') or item.get('seq') or '')
                if not code:
                    self.skipped.append('상품 식별자 누락')
                    continue
                if code in seen:
                    continue
                seen.add(code)
                fresh += 1
                try:
                    results.append(self.parse(item))
                except (ValueError, KeyError, TypeError) as exc:
                    self.skipped.append(f"{item.get('name', code)}: {exc}")
            if len(seen) >= expected_total:
                break
            if fresh == 0:
                raise ValueError('이지모바일 API 페이지 이동 중 중복 응답')
        if len(seen) != expected_total:
            raise ValueError(f'이지모바일 목록 일부만 수집: {len(seen)}/{expected_total}')
        if not results:
            raise ValueError('이지모바일 가격/기간 검증을 통과한 요금제 없음')
        return results
