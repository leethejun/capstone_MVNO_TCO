"""SK7 상단 상품서비스→요금제의 공개 전체 검색 API."""
import requests


class Sk7Crawler:
    URL = 'https://www.sk7mobile.com/prod/data/callingPlanList.do?refCode=USIM'

    def __init__(self, headers=None, timeout=15):
        self.headers = headers or {}
        self.timeout = timeout

    @staticmethod
    def parse(item):
        title = item.get('prodNm')
        if not title or item.get('prodTp') != '20':
            return None
        normal = int(str(item['basicAmt']).replace(',', ''))
        discount = int(str(item['basicAmt2']).replace(',', ''))
        period = item.get('promoDcMth')
        if normal == discount:
            months = 0
        elif period == '9999':
            months = -1
        elif period and str(period).isdigit() and 0 < int(period) < 120:
            months = int(period)
        else:
            raise ValueError(f'SK7 할인 종료 조건 누락: {title}')
        if not 0 <= discount <= normal or normal <= 0:
            raise ValueError(f'SK7 가격 검증 실패: {title}')
        data = str(item.get('basicFreeData', '')) + str(item.get('basicFreeDataUnit', ''))
        qos = item.get('ordering', '')
        voice = str(item.get('basicFreeVoice', '')).replace('기본제공', '무제한') + item.get('basicFreeVoiceUnit', '')
        sms = str(item.get('basicFreeSms', '')).replace('기본제공', '무제한') + item.get('basicFreeSmsUnit', '')
        return dict(telecom_name='SK 7mobile',title=f'[공식몰] {title}',network_type='5G' if item.get('prodInfoText') == '5G' else 'LTE',
                    discount_price=discount,normal_price=normal,discount_months=months,
                    raw_text=f'{title} | 데이터 {data} + {qos} | 통화 {voice} | 문자 {sms} | 망: SKT [출처: SK 7mobile 공식홈페이지] [상품 코드: {item["prodCd"]}]')

    def fetch_raw_plans(self):
        session = requests.Session(); session.headers.update(self.headers)
        response = session.get(self.URL,timeout=self.timeout); response.raise_for_status()
        response = session.post('https://www.sk7mobile.com/prod/data/searchPlanList.do',json={'refCode':'USIM','prodSearchListYn':'Y','searchOrderby':''},timeout=self.timeout)
        response.raise_for_status()
        items = response.json()['resultList']
        if not items:
            raise ValueError('SK7 전체 목록이 비어 있음')
        return [plan for item in items if (plan := self.parse(item))]
