"""더원모바일 공식 전체 카테고리 조회."""
import re
import json
from datetime import datetime
import requests


class TheOneCrawler:
    URL = 'https://www.theonem.co.kr/view/plan/phone_plan.aspx'

    @staticmethod
    def parse(item):
        if item['GDCD'] in ('100156','100157'):
            return None  # 공식 화면에서도 판매 차단
        today=datetime.now().strftime('%Y%m%d')
        if not item['APPDT'] <= today <= item['ENDDT']:
            return None
        price=lambda value:int(str(value).replace(',',''))
        discount=price(item['AMT_MONTHLY'] or item['TT_AMT'])
        period=item['PERIOD']
        if period=='평생':
            months=-1;normal=price(item['TT_AMT'])
        elif re.fullmatch(r'\d+개월 차부터',period):
            months=int(re.search(r'\d+',period)[0])-1
            normal=price(item['AMT_DISCOUNT'])
        elif not period and discount==price(item['TT_AMT']):
            months=0;normal=discount
        else:
            raise ValueError(f'더원 할인 기간 검증 실패: {item["GDNM"]}')
        if not 0 <= discount <= normal or normal<=0:
            raise ValueError('더원 가격 검증 실패')
        network='KT' if 'KT' in item.get('EVNTTAGNM1','') else 'LGU+' if 'U+' in item.get('EVNTTAGNM1','') else 'SKT'
        title=item['GDNM'];data=item['SEEDATA'];voice=item['SEEVOICE'].replace('기본제공','무제한');sms=item['SEELETTER'].replace('기본제공','무제한')
        return dict(telecom_name='더원모바일',title=f'[공식몰] {title}',network_type='5G' if '5G' in title else 'LTE',
            discount_price=discount,normal_price=normal,discount_months=months,
            raw_text=f'{title} | 데이터 {data} | 통화 {voice} | 문자 {sms} | 망: {network} [출처: 더원모바일 공식홈페이지] [상품 코드: {item["GDCD"]}]')

    def fetch_raw_plans(self):
        session=requests.Session();response=session.get(self.URL,timeout=15);response.raise_for_status()
        response=session.post('https://www.theonem.co.kr/common/component/plan/AjaxPhone_plan.aspx',data=json.dumps({'header':[{'type':'06'}],'body':[{'order_type':'AMT','order_align':'ASC','seq':'','opentype':'','simtype':''}]}),timeout=15)
        response.raise_for_status();payload=response.json()
        if payload.get('RESULT')!='Y' or not payload.get('DATA'):
            raise ValueError('더원 전체 상품 조회 실패')
        return [plan for item in payload['DATA'] if (plan:=self.parse(item))]
