"""티플러스 공식 전체 목록과 실제 납부액을 수집한다."""
import re
import ssl
import time
import unicodedata
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

from services.crawler.pricing_validation import UNKNOWN_NORMAL_MARKER, valid_pricing


class TplusCrawler:
    # www 호스트는 현재 HTTP 400을 반환한다. 공식 사이트의 apex를 사용한다.
    BASE = 'https://tplusmobile.com'
    LIST_PATH = '/BackBone/rate/rate_list'
    SEPARATOR = 'ㅹㆄ'

    def __init__(self, timeout=30, delay_sec=0.2):
        self.timeout = timeout
        self.delay_sec = delay_sec
        self.skipped = []
        self.excluded = []
        self.total = 0
        self.pages = 0

    @staticmethod
    def ssl_context():
        context = ssl.create_default_context()
        # 서버의 ECDHE 핸드셰이크 서명은 OpenSSL 3 기본 정책과 호환되지 않는다.
        # 이 사이트에만 RSA/AES-GCM을 사용한다. CA/호스트/유효기간 검증과
        # 기본 보안 수준은 유지하며 SECLEVEL 하향이나 verify=False는 사용하지 않는다.
        context.set_ciphers('AES128-GCM-SHA256:AES256-GCM-SHA384')
        return context

    def _request_page(self, tp, key):
        fields = dict(tp=tp, key=key, keyword='', seloptiontp='', selcompanytp='',
                      recommendtp='', selplanstp='all_plans', selsorttp='',
                      filter_data_s=0, filter_data_e=30001,
                      filter_voice_s=0, filter_voice_e=501,
                      filter_price_s=0, filter_price_e=50001,
                      sel_companies='', sel_sms='', sel_network='', sel_qos='',
                      sel_term='', sel_benefit_seqs='')
        request = urllib.request.Request(
            self.BASE + self.LIST_PATH,
            data=urllib.parse.urlencode(fields).encode(),
            headers={'User-Agent': 'Mozilla/5.0',
                     'Referer': self.BASE + '/main/rate/join',
                     'Content-Type': 'application/x-www-form-urlencoded',
                     'X-Requested-With': 'XMLHttpRequest'})
        with urllib.request.urlopen(request, context=self.ssl_context(), timeout=self.timeout) as response:
            return response.read().decode('utf-8')

    @staticmethod
    def parse_card(card):
        def text(node):
            if node is None:
                raise ValueError('티플러스 공식 상품 필드 누락')
            return unicodedata.normalize('NFKC', node.get_text(' ', strip=True))

        title = text(card.select_one('.title'))
        code = card.select_one('input.plan-seq')
        if code is None or not code.get('value'):
            raise ValueError('티플러스 상품 코드 누락')
        amount = card.select_one('.amountArea')
        if amount is None:
            raise ValueError('티플러스 월 납부액 누락')
        current_text = text(amount.select_one('.textPoint'))
        if not re.fullmatch(r'[\d,]+', current_text):
            raise ValueError('티플러스 월 납부액 형식 변경')
        current = int(current_text.replace(',', ''))
        amount_text = text(amount)
        # 상품권/제휴 혜택을 뺀 feelPrice는 요금이 아니므로 읽지 않는다.
        price_details = [text(p) for p in card.select('.rateDetail')]
        restoration = next((m for t in price_details if (m := re.search(
            r'(\d+)개월간\s*월\s*([\d,]+)원\s*,\s*(\d+)개월\s*후\s*월\s*([\d,]+)원', t))), None)
        if restoration:
            months = int(restoration[1])
            if months <= 0 or months != int(restoration[3]) or current != int(restoration[2].replace(',', '')):
                raise ValueError('티플러스 할인 기간/청구액 불일치')
            normal = int(restoration[4].replace(',', ''))
        elif '평생' in amount_text:
            months = -1
            original_node = amount.select_one('.throthDesc')
            original = re.search(r'([\d,]+)원', text(original_node)) if original_node else None
            normal = int(original[1].replace(',', '')) if original else None
        elif re.search(r'\d+개월', amount_text):
            period = re.search(r'(\d+)개월간\s*월', amount_text)
            after = next((m for t in price_details if (m := re.fullmatch(
                r'(\d+)개월\s*후\s*(?:평생\s*)?월\s*([\d,]+)원', t))), None)
            if period is None or after is None or int(period[1]) != int(after[1]):
                raise ValueError('티플러스 할인 종료 후 요금 미확인')
            months, normal = int(period[1]), int(after[2].replace(',', ''))
        else:
            original_node = amount.select_one('.throthDesc')
            original = re.search(r'([\d,]+)원', text(original_node)) if original_node else None
            if original and int(original[1].replace(',', '')) != current:
                raise ValueError('티플러스 할인 기간 미확인')
            months = 0
            normal = current
        data = text(card.select_one('.descArea > p'))
        if not re.search(r'\d\s*(?:GB|MB)|무제한', data, re.I):
            raise ValueError('티플러스 데이터 제공량 미확인')
        if re.match(r'^(?:일|매일|하루|일일)\s*\d', data):
            data = '0GB + ' + data
        voice = text(card.select_one('.ico.call')).replace('기본제공', '무제한')
        sms = text(card.select_one('.ico.message')).replace('기본제공', '무제한')
        network_badge = card.select_one('.badge.kt, .badge.skt, .badge.lgu, .badge.lguplus, .badge.lg')
        if network_badge is None:
            network_badge = card.select_one('.badgeArea .badge')
        network = text(network_badge)
        all_text = text(card)
        plan = dict(telecom_name='티플러스', title='[공식몰] ' + title,
                    network_type='5G' if '5G' in text(card.select_one('.badgeArea')) or title.startswith('5G') else 'LTE',
                    discount_price=current, normal_price=normal, discount_months=months,
                    raw_text=f'{title} | 데이터 {data} | 통화 {voice} | 문자 {sms} | 망: {network} '
                             f'[출처: 티플러스 공식홈페이지] [상품 코드: {code["value"]}] '
                             f'[상품 URL: {TplusCrawler.BASE}/main/rate/plan_details?seq={code["value"]}] | {all_text}')
        if normal is None:
            plan['raw_text'] += ' ' + UNKNOWN_NORMAL_MARKER
        if not valid_pricing(plan):
            raise ValueError('티플러스 가격/기간 검증 실패')
        return plan

    def fetch_raw_plans(self):
        self.skipped = []; self.excluded = []; self.pages = 0; self.total = 0
        seen = set(); cursors = set(); result = []; key = ''
        for page in range(100):
            parts = self._request_page('F' if page == 0 else 'N', key).strip().split(self.SEPARATOR)
            if len(parts) < 6 or parts[0] != 'TRUE':
                raise ValueError('티플러스 공식 목록 응답 형식 오류')
            total, count = int(parts[2]), int(parts[3])
            if page == 0:
                self.total = total
            elif total != self.total:
                raise ValueError('티플러스 수집 도중 전체 상품 수 변경')
            cards = BeautifulSoup(parts[1], 'html.parser').select('.cardArea')
            if len(cards) != count:
                raise ValueError('티플러스 페이지 상품 수 불일치')
            self.pages += 1
            for card in cards:
                code = card.select_one('input.plan-seq')
                code = code.get('value') if code else None
                if not code or code in seen:
                    raise ValueError('티플러스 상품 코드 누락 또는 페이지 중복')
                seen.add(code)
                title = card.select_one('.title')
                title = title.get_text(' ', strip=True) if title else ''
                badges = card.select_one('.badgeArea')
                eligibility = title + ' ' + (badges.get_text(' ', strip=True) if badges else '')
                if re.search(r'복지|시니어|청소년|주니어|어린이|키즈|외국인|선불|태블릿|워치|데이터\s*전용', eligibility):
                    self.excluded.append(title)
                    continue
                try:
                    result.append(self.parse_card(card))
                except ValueError as exc:
                    self.skipped.append(f'{title} ({exc})')
            if len(seen) == self.total:
                if not seen:
                    raise ValueError('티플러스 공식 전체 목록이 비어 있음')
                return result
            if len(seen) > self.total or not count or not parts[5] or parts[5] in cursors:
                raise ValueError('티플러스 전체 목록 페이지 누락/커서 반복')
            key = parts[5]; cursors.add(key)
            if self.delay_sec:
                time.sleep(self.delay_sec)
        raise ValueError('티플러스 전체 목록 페이지 한도 초과')
