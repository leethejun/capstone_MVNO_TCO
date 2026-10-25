"""스마텔 후불 전체 화면의 공개 Flight 데이터. 결합 혜택을 기본 제공량에 합산하지 않는다."""
import requests
from bs4 import BeautifulSoup
from services.crawler.structured_official import flight_objects, record


class SmartelCrawler:
    URL = 'https://www.smartel.kr/phoneplan'

    @staticmethod
    def parse(item):
        title = item['name']
        if (item.get('prepaidPostpaid') != 'postpaid' or item.get('disabled') or item.get('deletedAt')
                or item.get('serviceBundled') or any(word in title for word in ('시니어','청소년','주니어','키즈','복지','태블릿','워치','데이터쉐어링'))):
            return None
        settings = item.get('registrationSettings')
        if settings and not settings.get('enabled'):
            return None
        if item.get('originalPrice2'):
            raise ValueError('추가 가격 단계 확인 필요')
        normal = int(item['originalPrice']); current = int(item['promotionPrice'])
        duration = int(item['promotionDuration'])
        months = -1 if duration == 999 else duration
        if current != normal and months == 0:
            raise ValueError('할인 기간 누락')
        daily = item.get('dataEveryday')
        data = f"{item.get('dataDefault') or 0}GB"
        if daily: data += f' + 매일 {daily}GB'
        speed = item.get('dataAdditionalSpeedLimit')
        if speed: data += f' + {speed}Mbps'
        voice = '무제한' if str(item['voiceDefault']) == '999' else f"{item['voiceDefault']}분"
        sms = item['text'].replace('기본제공','무제한').replace('미제공','0건')
        return record('스마텔', title, current, normal, months, data, voice, sms,
                      item['mno'], item['planCode'], item['networkType'])

    def fetch_raw_plans(self):
        response = requests.get(self.URL, timeout=25); response.raise_for_status()
        payloads = [obj['phoneplans'] for obj in flight_objects(BeautifulSoup(response.content,'html.parser')) if 'phoneplans' in obj]
        if len(payloads) != 1 or not payloads[0]: raise ValueError('스마텔 전체 후불 목록 확인 실패')
        items = payloads[0]
        if len({item['planCode'] for item in items}) != len(items): raise ValueError('스마텔 상품 코드 중복')
        self.skipped = []; self.excluded = []; result = []
        for item in items:
            try:
                parsed = self.parse(item)
                if parsed: result.append(parsed)
                else: self.excluded.append(item['name'])
            except (ValueError, TypeError, KeyError) as error:
                self.skipped.append(f"{item.get('name')}: {error}")
        return result
