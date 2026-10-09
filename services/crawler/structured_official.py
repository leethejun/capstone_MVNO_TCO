"""공식 공개 상품 데이터의 할인액/청구액과 전체 페이지를 구분한다."""
import json
import re
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup


def flight_objects(soup):
    decoder = json.JSONDecoder()
    chunks = []
    for script in soup.select('script:not([src])'):
        source = script.get_text()
        for match in re.finditer(r'self\.__next_f\.push\(', source):
            try:
                value, _ = decoder.raw_decode(source[match.end():])
                if len(value) > 1 and value[0] == 1 and isinstance(value[1], str):
                    chunks.append(value[1])
            except (ValueError, TypeError):
                continue
    # Flight의 T(문자열) 레코드 바로 뒤에 JSON 레코드가 이어질 수도 있다.
    source = ''.join(chunks)
    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)
    for match in re.finditer(r'[0-9a-f]+:(?=[\[{])', source):
        try:
            value, _ = decoder.raw_decode(source[match.end():])
            yield from walk(value)
        except ValueError:
            continue


def amount(value):
    return int(str(value).replace(',', ''))


def record(name, title, current, normal, months, data, voice, sms, network, code, net='LTE'):
    if not (0 <= current <= normal <= 300000 and normal > 0 and months >= -1):
        raise ValueError(f'{name} 가격/기간 검증 실패: {title}')
    if re.match(r'^(?:매일|하루|일일|일)\s*\d', data):
        data='0GB + '+data
    return dict(telecom_name=name, title=f'[공식몰] {title}', network_type=net,
                discount_price=current, normal_price=normal, discount_months=months,
                raw_text=f'{title} | 데이터 {data} | 통화 {str(voice).replace("기본제공", "무제한")} | 문자 {str(sms).replace("기본제공", "무제한")} | 망: {network} [출처: {name} 공식홈페이지] [상품 코드: {code}]')


class PinCrawler:
    URL = 'https://www.pindirectshop.com/deal-list'

    @staticmethod
    def parse(item):
        if item['hiddenYN'] != 'N' or item['plan']['onSaleYn'] != 'Y':
            return None
        if item.get('contractSupportYN') == 'Y':
            return None  # 약정 조건은 현재 무약정 환승 비교 대상에서 제외
        today = datetime.now(timezone.utc)
        if not datetime.fromisoformat(item['salesStartAt'].replace('Z', '+00:00')) <= today <= datetime.fromisoformat(item['salesEndAt'].replace('Z', '+00:00')):
            return None
        base=amount(item['price']); permanent=amount(item['lifetimeDiscountPrice']); temporary=amount(item['discountPrice'])
        normal=base-permanent; current=normal-temporary
        if not temporary:
            normal=base
        months=amount(item['discountPeriod']) if temporary else (-1 if permanent else 0)
        if temporary and months <= 0:
            raise ValueError('핀다이렉트 기간 없는 일시 할인')
        p=item['plan'];data=f"{p['basicData']/1000:g}GB"
        if p.get('dailyData'):data+=f" + 매일 {p['dailyData']/1000:g}GB"
        if p.get('qos'):data+=f" + {p['qos']/1000:g}Mbps"
        voice='무제한' if p['voice']==-1 else f"{p['voice']}분"
        sms='무제한' if p['message']==-1 else f"{p['message']}건"
        return record('핀다이렉트',item['name'],current,normal,months,data,voice,sms,p['provider'],item['uuid'],p['network'])

    def fetch_raw_plans(self):
        response=requests.get(self.URL,timeout=20);response.raise_for_status()
        models=list(flight_objects(BeautifulSoup(response.content,'html.parser')))
        lists=[x['initialDeals'] for x in models if 'initialDeals' in x]
        if not lists or len(lists[0]['list']) != lists[0]['total']:
            raise ValueError('핀다이렉트 전체 목록 개수 검증 실패')
        return [p for x in lists[0]['list'] if (p:=self.parse(x))]


class AlbireoCrawler:
    URL='https://www.albireomobile.com/api/web/v1/plans'

    @staticmethod
    def parse(item):
        if item['type']!='POSTPAID' or item['discountSteps'].get('selectiveAgreementMonths'):
            return None
        current=amount(item['monthlyFee']);period=item.get('periodDiscountMonths')
        normal=amount(item['feeAfterPeriodDiscount']) if period else amount(item['baseFee'])
        months=int(period) if period else (-1 if current<normal else 0)
        qos=item.get('throttleSpeedKbps');data=item['dataDisplay']+(f' + {qos/1000:g}Mbps' if qos else '')
        return record('알비레오',item['name'],current,normal,months,data,item['voiceDisplay'],item['smsDisplay'],item['mnoCode'],item['code'],item['networkType'])

    def fetch_raw_plans(self):
        items=[];page=0
        while True:
            response=requests.get(self.URL,params={'page':page,'size':100},timeout=20);response.raise_for_status();payload=response.json()
            if payload.get('success') is not True:raise ValueError('알비레오 목록 조회 실패')
            data=payload['data'];items.extend(data['content'])
            if data['last']:
                if len(items)!=data['totalElements']:raise ValueError('알비레오 전체 페이지 개수 불일치')
                break
            if not data['content'] or page>=100:raise ValueError('알비레오 페이지 순회 실패')
            page+=1
        return [p for x in items if (p:=self.parse(x))]


class MonaCrawler:
    URL='https://mobilemona.co.kr/common/component/plan/AjaxRate_plan.aspx'

    @staticmethod
    def parse(item):
        if any(x in item['GDNM']+' '+item['GDDESC'] for x in ['복지','시니어','키즈','카드','멀티넘버','태블릿','워치']):return None
        normal=amount(item['TT_AMT']);period=item['EVENT_PERIOD'];current=amount(item['DISCOUNT']) if period else normal
        months=(-1 if int(period)>=120 else int(period)) if period else 0
        return record('MONA',item['GDNM'],current,normal,months,item['SEEDATA'],item['SEEVOICE'],item['SEELETTER'],item['MNO_CD'],item['GDCD'],item['NETDIV'])

    def fetch_raw_plans(self):
        r=requests.post(self.URL,data=json.dumps({'header':[{'type':'01'}],'body':[{'e_agcd':'','keywordSeq':''}]}),timeout=20);r.raise_for_status();data=r.json()
        if data.get('RESULT')!='Y' or not data['DATA']:raise ValueError('MONA 전체 목록 조회 실패')
        return [p for x in data['DATA'] if (p:=self.parse(x))]


class GmeCrawler:
    URL='https://www.gmemobile.com/common/component/plan/AjaxPhone_plan.aspx'

    def query(self,kind,body):
        r=requests.post(self.URL,data=json.dumps({'header':[{'type':kind}],'body':[body]}),timeout=20);r.raise_for_status();data=r.json()
        if data.get('RESULT')!='Y':raise ValueError('GME 목록 조회 실패')
        return data['DATA']

    @staticmethod
    def parse(item):
        desc=item['GDDESC']
        if any(x in item['GDNM']+' '+desc for x in ['선불','테블릿','태블릿','워치','시니어','복지','카드']):return None
        normal=amount(item['TT_AMT']);discount=amount(item['DISCOUNT'])
        current=discount if discount or item.get('DISCNT_FREE')=='Y' else normal
        if current==normal:months=0
        elif '평생' in desc:months=-1
        else:
            match=re.search(r'(\d+)개월\s*할인',desc)
            if not match:raise ValueError(f'GME 할인 기간 누락: {item["GDNM"]}')
            months=int(match[1])
        data=item['DATAAMOUNT']+item['ADD_DATA']+(f" + {item['QOSAMT']}" if item['QOSFG']=='1' else '')
        return record('GME모바일',item['GDNM'],current,normal,months,data,item['VOICEAMOUNT'],item['LETTERAMOUNT'],item['MNO_CD'],item['GDCD'],'5G' if '5G' in item['GDNM'] else 'LTE')

    def fetch_raw_plans(self):
        cats=self.query('01',{});items={}
        if not cats:raise ValueError('GME 카테고리 목록 없음')
        for cat in cats:
            if cat['KEYWORD']=='선불':continue
            for item in self.query('02',{'seq':cat['SEQ'],'order_type':'AMT','order_align':'ASC'}):items[item['GDCD']]=item
        return [p for x in items.values() if (p:=self.parse(x))]


class EumCrawler:
    URL='https://eummobile.co.kr/api/soc/lists'

    @staticmethod
    def parse(item,name='이음모바일'):
        if item.get('isHasAgreement') or any(x in item['name'] for x in ['로밍','번호변경','부가서비스','복지','시니어','워치','태블릿']):return None
        if not item.get('data') and not item.get('isDataQos') and not item.get('voc') and not item.get('isVocInfinity'):return None
        current=amount(item['salePrice']);base=amount(item['basePrice']);unit=item.get('discountUnit');period=item.get('discountPeriod')
        if unit=='always':months=-1 if current<base else 0;normal=base
        elif period and unit=='month':months=int(period);normal=amount(item['originalPrice'])
        elif current==base:months=0;normal=base
        else:raise ValueError(f'{name} 할인 기간 불명: {item["name"]}')
        data=item.get('dataDesc') or f"{float(item['data'])/(1024 if name=='에르엘' else 1000):g}GB"
        if item.get('dataUnit')=='day':data='매일 '+data
        if item.get('additionalData'):data+=f" + {'매일 ' if item.get('additionalDataUnit')=='day' else ''}{float(item['additionalData'])/1000:g}GB"
        if item.get('isDataQos'):data+=f" + {float(item['dataQos']):g}Mbps"
        voice='무제한' if item.get('isVocInfinity') else item.get('vocDesc') or f"{item['voc']}분"
        sms='무제한' if item.get('isSmsInfinity') else item.get('smsDesc') or f"{item['sms']}건"
        return record(name,item['name'],current,normal,months,data,voice,sms,item['mnoGubun'],item['code'],item.get('planType') or ('5G' if '5G' in item['name'] else 'LTE'))

    def fetch_raw_plans(self):
        r=requests.get(self.URL,params={'isUse':1,'isFront':1,'cnusecd':'R'},timeout=20);r.raise_for_status();items=r.json()['data']
        if not isinstance(items,list) or not items:raise ValueError('이음 전체 상품 조회 실패')
        return [p for x in items if (p:=self.parse(x))]


class ErelCrawler:
    URL='https://www.erel.co.kr/nf-mvno-user/graphql'
    FIELDS='code name socDesc mnoGubun basePrice salePrice originalPrice discountPeriod discountUnit priceDesc srvtp data dataUnit dataDesc additionalData additionalDataUnit isDataQos dataQos voc vocDesc isVocInfinity sms smsDesc isSmsInfinity isUse isFront isUseNew isUseTransfer isHasAgreement planType socType isMonthly ord cnusecd'

    def fetch_raw_plans(self):
        query='query getCmSocs($where:CmSocWhereInput){getCmSocs(where:$where){'+self.FIELDS+'}}'
        where={'workerId':{'not':None},'cnusecd':{'equals':'R'},'isUse':{'equals':True},'isFront':{'equals':True},'ord':{'not':None}}
        r=requests.post(self.URL,json={'query':query,'variables':{'where':where}},timeout=25);r.raise_for_status();payload=r.json()
        if payload.get('errors'):raise ValueError('에르엘 공개 상품 조회 실패')
        items=payload['data']['getCmSocs']
        if not items:raise ValueError('에르엘 공개 상품 목록 없음')
        plans=[]
        self.skipped=[]
        for x in items:
            try:
                if (p:=EumCrawler.parse(x,'에르엘')):plans.append(p)
            except ValueError:
                self.skipped.append(x['name'])
        return plans


class S1Crawler:
    # 가입 화면이 통신망별 전체 선택 항목을 한 번에 불러오는 공개 API.
    # 안내 목록의 TCount(비판매 항목 포함)와 별개로 실제 가입 가능 목록을 검증한다.
    URL='http://www.s1mobile.co.kr/mall/usim/getPolicyRate.do'

    @staticmethod
    def parse(item):
        if item.get('catCode')!='P0301' or any(x in item['chargePlanNm'] for x in ['데이터쉐어링','시니어','청소년','복지','키즈','태블릿','디바이스']):return None
        vat=lambda value:int(float(value)*1.1)
        base=vat(item['bassChrge']);current=base-vat(item['chrgeDscnt'])-vat(item['promoSalePrice'])
        desc=item.get('addDispMsg') or '';match=re.search(r'(\d+)개월\s*후\s*([\d,]+)원',desc)
        if match:months=int(match[1]);normal=amount(match[2])
        elif current==base:months=0;normal=base
        elif item.get('noticeMsgYn')=='N' and desc in ('N','-',''):
            months=-1;normal=base
        else:raise ValueError(f'안심모바일 할인기간 미확인: {item["chargePlanNm"]}')
        data=item['dataServing']+' '+(item.get('dataServeAddInfo') or '')
        return record('에스원 안심모바일',item['chargePlanNm'],current,normal,months,data,item['dmstcTalkServing'],item['smsServing'],item['mno'],item['chargePlanSn'],'5G' if '5G' in item['chargePlanNm'] else 'LTE')

    def fetch_raw_plans(self):
        plans=[]
        for network in ['LGUP','KT','SKT']:
            r=requests.post(self.URL,data={'mno':network,'moblPhonSn':'0','moblSaleSp':'P7103'},timeout=20);r.raise_for_status();payload=r.json()
            if len(payload)!=1 or not isinstance(payload[0].get('list'),list) or not payload[0]['list']:
                raise ValueError('안심모바일 가입 가능 전체 목록 조회 실패')
            items=payload[0]['list']
            if len({x['chargePlanSn'] for x in items})!=len(items):raise ValueError('안심모바일 상품 코드 중복')
            for item in items:
                if item['mno']!=network:raise ValueError('안심모바일 통신망 불일치')
                if (p:=self.parse(item)):plans.append(p)
        return plans


class KoretelCrawler:
    BASE='https://www.koretel.co.kr/common/component/plan/'

    def query(self,endpoint,kind,body):
        response=requests.post(self.BASE+endpoint+'.aspx',data=json.dumps({'header':[{'type':kind}],'body':[body]}),timeout=20);response.raise_for_status();payload=response.json()
        if payload.get('RESULT')!='Y':raise ValueError('한국E 공식 상품 조회 실패')
        return payload['DATA']

    def fetch_raw_plans(self):
        categories=self.query('AjaxPhone_plan','01',{});items={}
        if not categories:raise ValueError('한국E 카테고리 없음')
        for category in categories:
            for item in self.query('AjaxPhone_plan','02',{'seq':category['SEQ'],'order_type':'AMT','order_align':'ASC'}):items[item['SEQ']]=item
        plans=[]
        for item in items.values():
            details=self.query('AjaxPhone_plan_detail','01',{'gdcd':item['GDCD'],'agcd':'','tseq':item['SEQ']})
            if len(details)!=1:raise ValueError('한국E 상품 상세 누락')
            d=details[0]
            if d['TERMSYN']=='Y':continue
            if d['DISCOUNTYN']=='Y':raise ValueError('한국E 할인 조건 추가 확인 필요')
            price=amount(d['TT_AMT'])
            data=d['SEEDATA'];qos=re.search(r'(\d+(?:\.\d+)?)\s*Mbps',d['DATA_CONTENT'])
            if qos:data+=' + '+qos[1]+'Mbps'
            daily=re.search(r'(?:하루|일)\s*(\d+)\s*GB',d['DATA_CONTENT'])
            if daily:data+=' + 매일 '+daily[1]+'GB'
            title=d['GDNM']+' + '+d['RSVCNM']
            plan=record('한국E텔레콤',title,price,price,0,data,d['SEEVOICE'],d['SEELETTER'],d['MNO_CD'],item['SEQ'])
            plan['raw_text']+=' | 필수 부가서비스를 포함한 공식 상세 월 납부액'
            plans.append(plan)
        return plans


class ShakeCrawler:
    BASE='https://shakemobile.co.kr/M2Mobile/'

    @staticmethod
    def parse(item):
        if item['ltediv']=='DATA_SHARING' or item.get('inetCombYn')=='Y' or item.get('soloCombCd'):
            return None
        base=amount(item['amt']);current=amount(item['tt_AMT']);period=amount(item['promo_MM'])
        if period:
            months=period;normal=base-int(float(item['life_TIME_DISCOUNT'])*1.1)
        else:
            months=-1 if current<base else 0;normal=base
        data=BeautifulSoup(item['seedata'],'html.parser').get_text(' ',strip=True)
        data=re.sub(r'\(최대\s*[\d.]+\s*GB\)','',data)
        if data.startswith(('매일','일 ','일5','하루')):data='0GB + '+data
        return record('쉐이크모바일',item['gdnm'],current,normal,months,data,item['voiceamountv'],item['letteramountv'],'KT',item['gdcd'],item['netdiv'])

    def fetch_raw_plans(self):
        session=requests.Session();r=session.get(self.BASE+'Set3G',timeout=20);r.raise_for_status()
        response=session.post(self.BASE+'getTG01NETDIV',timeout=20);response.raise_for_status();categories=response.json()
        if not categories:raise ValueError('쉐이크 전체 카테고리 없음')
        items={}
        for category in categories:
            response=session.post(self.BASE+'getTG01ByLtediv',json={'sLteDiv':category['ltediv'],'promoPrtnChk':[],'sort':'1'},timeout=20);response.raise_for_status();rows=response.json()
            if not isinstance(rows,list):raise ValueError('쉐이크 카테고리 조회 실패')
            for x in rows:items[x['gdcd']]=x
        if not items:raise ValueError('쉐이크 전체 상품 없음')
        return [p for x in items.values() if (p:=self.parse(x))]
