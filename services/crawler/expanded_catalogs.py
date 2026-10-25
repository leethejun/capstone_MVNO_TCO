"""공식 화면이 사용하는 전체 상품 데이터. 조건부 혜택·쿠폰을 월 청구액에서 차감하지 않는다."""
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import requests
from bs4 import BeautifulSoup
from services.crawler.structured_official import flight_objects, record, amount

RESTRICTED = re.compile(r'시니어|청소년|주니어|키즈|복지|태블릿|워치|쉐어링|선불|새\s*휴대폰')


class AMobileCrawler:
    URL = 'https://amobile.co.kr/planasync'

    @staticmethod
    def parse(item):
        title = item['요금제명']
        if RESTRICTED.search(title): return None
        base = amount(item['기본료']); current = amount(item['할인요금'])
        period = amount(item['추가할인개월수'])
        if item['평생할인여부'] == 'Y': normal = base; months = -1
        elif period > 0: normal = base - amount(item['알뜰할인']); months = period
        else: raise ValueError('A모바일 할인 종료 조건 확인 필요')
        def allowance(text, unit):
            return '무제한' if text in ('기본','기본제공','무제한') else text if re.search(r'[분건]',text) else text+unit
        return record('A모바일(에넥스텔레콤)',title,current,normal,months,item['무료데이타'],
                      allowance(item['무료음성'],'분'),allowance(item['무료문자'],'건'),item['통신사'],item['요금제구성ID'],
                      '5G' if item['망구분']=='5G' else 'LTE')

    def fetch_raw_plans(self):
        r=requests.post(self.URL,json={'section':'plansearch','keyword':'N','telecom':'all','sort':'star','status':'N'},timeout=25)
        r.raise_for_status(); items=r.json().get('planList')
        if not items or len({x['요금제구성ID'] for x in items}) != len(items): raise ValueError('A모바일 전체 목록/상품 코드 검증 실패')
        self.skipped=[]; result=[]
        for item in items:
            try:
                if (row:=self.parse(item)): result.append(row)
            except (ValueError,KeyError,TypeError) as error: self.skipped.append(f"{item.get('요금제명')}: {error}")
        return result


class TossCrawler:
    URL='https://api-public.toss.im/api/v3/mvno-growth/products/homepage'

    @staticmethod
    def parse(item):
        title=item['displayName']
        if item.get('isWelfare') or RESTRICTED.search(title) or item.get('costType')!='정액': return None
        base=int(item['monthlyFee']); policies=item.get('discountPolicyList') or []
        now=datetime.now(ZoneInfo('Asia/Seoul'))
        policies=[p for p in policies if datetime.fromisoformat(p['applyStartTs']).replace(tzinfo=ZoneInfo('Asia/Seoul'))<=now<=datetime.fromisoformat(p['applyEndTs']).replace(tzinfo=ZoneInfo('Asia/Seoul'))]
        if len(policies)>1 or item.get('promotionDiscountAmount'):
            raise ValueError('복수 할인 단계 검증 필요')
        normal=base; current=base; months=0
        if policies:
            policy=policies[0]
            if policy['startMonthIndex']!=0: raise ValueError('할인 시작 개월 검증 필요')
            current=base-int(policy['amount']); months=-1 if policy['numberOfMonths'] is None else int(policy['numberOfMonths'])
        d=item['dataUsage']; data=f"{d.get('basicAmount') or 0}GB"
        if d.get('dailyAmount'): data+=f" + 매일 {d['dailyAmount']}GB"
        if d.get('speedLimit'): data+=f" + {d['speedLimit']}{d['speedLimitUnit']}"
        def allowance(value,unit): return '무제한' if value['type']=='UNLIMITED' else f"{value.get('amount') or 0}{unit}"
        return record('토스모바일',title,current,normal,months,data,allowance(item['callUsage'],'분'),allowance(item['messageUsage'],'건'),item['mnoCarrier'],item['id'],item['network'])

    def fetch_raw_plans(self):
        r=requests.get(self.URL,timeout=25);r.raise_for_status();payload=r.json()
        items=payload.get('success')
        if payload.get('resultType')!='SUCCESS' or not isinstance(items,list) or not items or len({i['id'] for i in items})!=len(items): raise ValueError('토스 전체 목록 검증 실패')
        self.skipped=[]; result=[]
        for item in items:
            try:
                if (row:=self.parse(item)):result.append(row)
            except (ValueError,KeyError,TypeError) as error:self.skipped.append(f"{item.get('displayName')}: {error}")
        return result


class SkylifeCrawler:
    URL='https://www.skylife.co.kr/product/mobile/all'

    @staticmethod
    def parse(item):
        title=item['name']
        if RESTRICTED.search(title):return None
        if item.get('type')!='MOBILE_PLAN':return None
        price=item['price']; rates=price.get('default') or []
        if len(rates)!=1 or rates[0]['period']!={'unit':'월','value':1}:raise ValueError('스카이라이프 월 기본료 구조 변경')
        # The official mobile contract notice states no commitment / lifetime pricing.
        # period=1 is the billing frequency, not a one-month promotion.
        normal=int(price['baseFee']);current=int(rates[0]['fee']);months=-1 if current<normal else 0
        props=item['properties'];data=props['data'];desc=data.get('description') or ''
        daily=re.search(r'매일\s*(\d+(?:\.\d+)?)\s*GB',desc,re.I)
        if daily: spec=f'0GB + 매일 {daily[1]}GB'
        else: spec=f"{data.get('limit') or 0}{data.get('unit') or 'MB'}"
        if data.get('qosLimit'):spec+=f" + {data['qosLimit']}{data['qosUnit']}"
        def allowance(v,unit): return '무제한' if v['unit']=='기본제공' else f"{v.get('limit') or 0}{unit}"
        return record('KT스카이라이프',title,current,normal,months,spec,allowance(props['voice'],'분'),allowance(props['message'],'건'),'KT',item['code'],props['network']['type'])

    def fetch_raw_plans(self):
        r=requests.get(self.URL,timeout=25);r.raise_for_status()
        lists=[x['mobilePlans'] for x in flight_objects(BeautifulSoup(r.content,'html.parser')) if 'mobilePlans' in x]
        if len(lists)!=1 or not lists[0]:raise ValueError('스카이라이프 전체 목록 검증 실패')
        unique={}
        for item in lists[0]:
            old=unique.get(item['code'])
            if old and any(old[k]!=item[k] for k in ('name','price','properties')):
                raise ValueError('스카이라이프 동일 코드의 가격/제공량 충돌')
            unique[item['code']]=item
        self.skipped=[];result=[]
        for item in unique.values():
            try:
                if (row:=self.parse(item)):result.append(row)
            except (ValueError,KeyError,TypeError) as error:self.skipped.append(f"{item.get('name')}: {error}")
        return result
