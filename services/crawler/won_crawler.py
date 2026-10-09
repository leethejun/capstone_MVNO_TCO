"""우리WON 공개 전체 목록. 금융 조건 상품과 체감가를 일반 납부액에 혼합하지 않는다."""
import html
import re
import time
import requests
from bs4 import BeautifulSoup
from services.crawler.structured_official import amount, record


class WonCrawler:
    BASE='https://www.wooriwonmobile.com/appIf/v1/internal/eai/'

    def query(self,code,data):
        body={'messageId':int(time.time()*1000),'systemId':'S00001','apiKey':'1234567890',
              'serviceId':code,'timestamp':time.strftime('%Y-%m-%d %H:%M:%S'),'data':data}
        response=requests.post(self.BASE+code,json=body,timeout=20);response.raise_for_status();payload=response.json()
        if payload.get('resultCode')!='00000000':raise ValueError('우리WON 공개 상품 조회 실패')
        return payload['data']

    def fetch_raw_plans(self):
        page=1;items=[]
        while True:
            data=self.query('LMPM000012',{'soId':'01','pageNo':page,'countPerPage':100,'prodCtgr':'','dataQosList':[],
                'chrgAmtFrom':'0','chrgAmtTo':'','dataAmtFrom':'0','dataAmtTo':'','sortTyp':'','svcTp':'','grpTp':''})
            rows=data['dsRes'];items.extend(rows);total=int(data['dsHdr'][0]['totalCnt']) if isinstance(data['dsHdr'],list) else int(data['dsHdr']['totalCnt'])
            if len(items)>=total:
                if len(items)!=total:raise ValueError('우리WON 전체 페이지 수 불일치')
                break
            if not rows or page>=100:raise ValueError('우리WON 목록 페이지 누락')
            page+=1
        plans=[];self.skipped=[];self.excluded=[]
        for item in items:
            details=self.query('LMPM000008',{'soId':item['soId'],'prodCd':item['prodCd']})['dsRes']
            descriptions={BeautifulSoup(html.unescape(d.get('srvDesc') or d.get('subscribeDesc') or ''),'html.parser').get_text(' ',strip=True) for d in details}
            if len(descriptions)!=1 or not next(iter(descriptions),''):
                self.skipped.append(item['prodNm']+' (공식 상세 조건 누락 또는 불일치)')
                continue
            description=descriptions.pop()
            # 일반 공통 안내의 '금융할인 등'은 상품의 실제 가입 조건으로 사용하지 않는다.
            # 조건 없는 첫 2개월 + 이후 추가 휴대폰 회선 조건인 상품은 금융 결합 상품이 아니다.
            if ('추가회선' in item.get('maxDisDesc','') and '2개월' in description
                    and re.search(r'적용조건\s*상관\s*없',description)
                    and not re.search(r'금융할인|은행\s*거래|급여\s*이체|예적금|카드\s*실적',description)):
                normal=amount(item['prodPrice']);current=amount(item['maxDisAdjAmt'])
                plan=record('우리WON모바일',item['prodNm'],current,normal,2,item['dataDesc'],item['voiceUnit'],item['smsUnit'],'LGU+',item['prodCd'])
                plan['raw_text']+=' | 가입월 포함 2개월 조건 없이 할인, 이후 추가 회선 할인 미적용'
                plans.append(plan)
            else:
                self.excluded.append(item['prodNm']+' (금융·가입대상·추가혜택 조건 상품 제외)')
        return plans
