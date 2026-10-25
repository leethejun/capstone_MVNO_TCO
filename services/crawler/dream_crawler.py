"""드림라인 전체 목록: 모든 요금 유형 필터를 보내야 서버가 정상 반환한다."""
import json
import re
import requests
from bs4 import BeautifulSoup
from services.crawler.structured_official import record,amount


class DreamCrawler:
    BASE='https://dreammobile.kr'
    URL=BASE+'/common/component/service/AjaxPlans.aspx'

    def query(self,kind,body):
        response=requests.post(self.URL,data=json.dumps({'header':[{'type':kind}],'body':[body]}),timeout=20)
        response.raise_for_status();payload=response.json()
        if payload.get('RESULT')!='Y' or not isinstance(payload.get('DATA'),list):
            raise ValueError('드림라인 공식 요금제 API 조회 실패')
        return payload['DATA']

    @staticmethod
    def parse(item):
        if item['PAYDIV']!='후불' or item.get('NETDIV')=='D' or item.get('WEB_FG')!='1':return None
        if (not any(float(item.get(k) or 0)>0 for k in ('DATAAMOUNT','VOICEAMOUNT','LETTERAMOUNT'))
                and not any('기본제공' in item.get(k,'') for k in ('SEEVOICE','SEELETTER'))):
            return None  # Pure metered service with no allowance cannot be compared as fixed consumption.
        if amount(item['DISCOUNT'] or 0):raise ValueError('드림라인 할인 기간 추가 검증 필요')
        price=amount(item['TT_AMT'])
        data=re.sub(r'^(?:데이터)+','',item['SEEDATA'].strip())
        data=re.sub(r'(\d+(?:\.\d+)?)\s*GB\s*/\s*일',r'매일 \1GB',data,flags=re.I)
        return record('드림라인 모바일',item['GDNM'],price,price,0,data,item['SEEVOICE'],item['SEELETTER'],'KT',item['GDCD'])

    def fetch_raw_plans(self):
        response=requests.get(self.BASE+'/view/service/plans.aspx',timeout=20);response.raise_for_status()
        soup=BeautifulSoup(response.content,'html.parser')
        filters=[x['id'].removeprefix('flatFg_') for x in soup.select('.flatFg[id^="flatFg_"]')]
        if set(filters)!={'0','1'}:raise ValueError('드림라인 전체 요금 유형 필터 구조 변경')
        items=self.query('01',{'paydiv':'','flatFgArr':filters})
        if not items or len({i['GDCD'] for i in items})!=len(items):raise ValueError('드림라인 전체 상품 코드 검증 실패')
        self.source_count=len(items);self.skipped=[];self.excluded=[];result=[]
        for item in items:
            if item['PAYDIV']!='후불' or item.get('NETDIV')=='D':
                self.excluded.append(item['GDCD']);continue
            try:
                details=self.query('02',{'gdcd':item['GDCD']})
                if len(details)!=1 or details[0]['GDCD']!=item['GDCD']:raise ValueError('드림라인 상세 코드 불일치')
                detail=details[0]
                for field in ('GDNM','TT_AMT','SEEDATA','SEEVOICE','SEELETTER'):
                    if str(detail[field]).strip()!=str(item[field]).strip():raise ValueError('드림라인 목록·상세 제공 조건 불일치')
                if (row:=self.parse(item)):result.append(row)
                else:self.excluded.append(item['GDCD'])
            except (KeyError,TypeError,ValueError) as error:self.skipped.append(f"{item['GDCD']}: {error}")
        return result
