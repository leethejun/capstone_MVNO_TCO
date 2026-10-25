"""유모바일·헬로 공식 전체 목록. 기본 requests UA에 오류를 반환해 표준 urllib를 사용한다."""
import json
import re
import urllib.request
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from services.crawler.structured_official import record,amount


def read_public(url,data=None):
    request=urllib.request.Request(url,data=urlencode(data).encode() if data is not None else None)
    with urllib.request.urlopen(request,timeout=25) as response:
        return response.read()


class HelloCrawler:
    URL='https://direct.lghellovision.net/fund/ajaxRateList.do'
    QOS={'0':'','1':'400Kbps','2':'1Mbps','3':'3Mbps','4':'5Mbps','5':'10Mbps'}

    @classmethod
    def parse(cls,item):
        if item['dedicatedPriceGubun'] in ('T','J','S'):return None
        title=item['salesName']
        if re.search(r'키즈|청소년|시니어|복지|패드|워치|태블릿|선불',title):return None
        current=amount(item['directPromotionDirectmallPrice']);base=amount(item['defaultPrice'])
        if item['directPromotionInfotext']=='A':normal=base;months=-1 if current<base else 0
        else:
            months=amount(item['directPromotionAfterMonthChk']);normal=amount(item['directPromotionAfterPrice'])
            if months<=0:raise ValueError('헬로 할인 기간 확인 필요')
        def data_value(prefix):
            value=item[prefix+'Value'] or '0';unit=item[prefix+'Gubun']
            if unit not in ('M','G'):raise ValueError('헬로 데이터 단위 확인 필요')
            return value+('MB' if unit=='M' else 'GB')
        data=data_value('dedicatedMonthlyOffer')
        if item['dedicatedDailyOfferValue']:data+=' + 매일 '+data_value('dedicatedDailyOffer')
        qos=cls.QOS[item['dedicatedDataDepletionRate']]
        if qos:data+=' + '+qos
        def allowance(prefix,unit):
            return '무제한' if item[prefix+'Gubun']=='L' else str(amount(item[prefix+'Value'] or '0'))+unit
        return record('헬로모바일',title,current,normal,months,data,allowance('dedicatedCalls','분'),
                      allowance('dedicatedSms','건'),item['telecom'],item['paymentcode'],item['usimType'])

    def fetch_raw_plans(self):
        payload=json.loads(read_public(self.URL,{'reqRateType':'U','reqTelecom':'','reqOrder':'S1',
            'mktList':'','reqDataSum':'','reqUsimType':'','reqDepleRateList':'','reqCalls':'',
            'reqPriceGubunList':'','reqMin':'0','reqMax':'1000000','reqText':''}))
        items=payload['list']
        # Official JS gets the entire list then slices for "more"; never slice here.
        if not items or len({i['paymentcode'] for i in items})!=len(items):raise ValueError('헬로 전체 목록 검증 실패')
        self.source_count=len(items);self.skipped=[];result=[]
        for item in items:
            try:
                if (row:=self.parse(item)):result.append(row)
            except (ValueError,KeyError,TypeError) as error:self.skipped.append(f"{item.get('salesName')}: {error}")
        return result


class UplusCrawler:
    URL='https://www.uplusumobile.com/product/pric/usim/pricList'

    @staticmethod
    def parse(card):
        title=card.select_one('.pln-tit').get_text(' ',strip=True)
        badges=' '.join(i.get('alt','') for i in card.select('img'))
        if re.search(r'시니어|틴에이저|키즈|청소년|주니어|복지|워치|태블릿|만18세|만65세',title+' '+badges):return None
        current=amount(card['data-discntaddvat']);normal=amount(card['data-bscchrgaddvat'])
        months=-1 if current<normal else 0
        spec=card.select_one('.pln-spc').get_text(' ',strip=True)
        # Finite additional 10GB campaigns are not permanent base allowance.
        spec=re.sub(r'\((\d+(?:\.\d+)?)\+\d+(?:\.\d+)?\)GB',r'\1GB',spec)
        if spec=='미제공':spec='0GB'
        voice_sms=card.select_one('.pln-txt').get_text(' ',strip=True)
        m=re.fullmatch(r'통화\s*(.*?),\s*문자\s*(.*)',voice_sms)
        if not m:raise ValueError('유모바일 통화/문자 제공량 구조 변경')
        def allowance(v,unit):return '0'+unit if v=='미제공' else v
        link=card.select_one('a[seq]')
        if not link:raise ValueError('유모바일 상품 코드 누락')
        return record('U+유모바일',title,current,normal,months,spec,allowance(m[1],'분'),allowance(m[2],'건'),
                      'LGU+',link['seq'],'5G' if card['data-ppngen']=='5' else 'LTE')

    def fetch_raw_plans(self):
        soup=BeautifulSoup(read_public(self.URL),'html.parser')
        cards=soup.select('#bx-list > .box');total=soup.select_one('#filteredListCnt')
        if not total or int(total.get_text(strip=True))!=len(cards) or not cards:
            raise ValueError('유모바일 전체 목록 개수 불일치')
        if '평생 할인은 기본' not in soup.get_text(' ',strip=True):
            raise ValueError('유모바일 기본 할인 정책 변경: 개별 기간 검증 필요')
        self.source_count=len(cards);self.skipped=[];result=[];codes=set()
        for card in cards:
            code=card.select_one('a[seq]')['seq']
            if code in codes:raise ValueError('유모바일 상품 코드 중복')
            codes.add(code)
            try:
                if (row:=self.parse(card)):result.append(row)
            except (ValueError,KeyError,TypeError) as error:self.skipped.append(f'{code}: {error}')
        return result
