"""KB 공개 전체 목록. 금융 결합 상품을 제외하고 조건 없는 기본료만 비교한다."""
import re
import requests
from bs4 import BeautifulSoup
from services.crawler.structured_official import amount, record
from services.crawler.bank_eligibility import FINANCIAL_CONDITIONS


class KbCrawler:
    BASE='https://m.liivm.com'

    @staticmethod
    def product_conditions(detail):
        soup=BeautifulSoup(detail.get('srvDtlDesc') or '', 'html.parser')
        for block in soup.select('.biz_info_wrap'):
            badge=block.select_one('.badge_wrap')
            if badge and '카드 청구할인혜택' in badge.get_text(' ',strip=True):
                block.decompose()  # 모든 상품에 붙는 선택형 카드 광고
        return soup.get_text(' ',strip=True)

    def query(self,code,data):
        path='/appIf/v1/rateplan/' if code.startswith('LIIVM') else '/appIf/v1/ratePlan/'
        r=self.session.post(self.BASE+path+code,data=data,headers=self.headers,timeout=20)
        r.raise_for_status();return r.json()

    def fetch_raw_plans(self):
        self.session=requests.Session();r=self.session.get(self.BASE+'/rateplan/plans/products',timeout=20);r.raise_for_status()
        soup=BeautifulSoup(r.content,'html.parser');header=soup.select_one('meta[name="_csrf_header"]');token=soup.select_one('meta[name="_csrf"]')
        if not header or not token:raise ValueError('KB 공개 목록 조회 세션 누락')
        self.headers={header['content']:token['content']}
        # 실제 전체 목록 화면은 필터 없는 단일 응답으로 모든 망을 받는다.
        items=self.query('LMPM000012',{})['searchProdList']['planList']
        if not items or len({(x['soId'],x['prodCd']) for x in items})!=len(items):raise ValueError('KB 전체 목록 비어있거나 상품 중복')
        groups={};plans=[];self.excluded=[];self.skipped=[]
        for item in items:
            if 'G010' in item['planGrp'] or item['prodGrpCd'] in ['U11','K05','K06']:
                self.excluded.append(item['prodNm']+' (별도 기기·공유 회선)');continue
            key=(item['soId'],item['prodGrpCd'])
            args={'soId':item['soId'],'prodGrpCd':item['prodGrpCd'],'prodCd':item['prodCd']}
            if key not in groups:groups[key]=self.query('LMPM000010',args)['prodGrpInfo']
            group=groups[key]
            if not group:self.skipped.append(item['prodNm']+' (공식 그룹 상세 없음)');continue
            condition=self.product_conditions(group)
            if FINANCIAL_CONDITIONS.search(condition) or re.search(r'입출금\s*(?:계좌|통장)|피싱보험|현역|공무원|교직원',condition):
                self.excluded.append(item['prodNm']+' (금융 결합·가입대상 조건)');continue
            details=self.query('LIIVM_LMPM000002',{**args,'svcTp':'99','grpTp':'','smsAmt':'','voiceAmt':'','dataAmt':'','mstrGb':'1'})['searchProdList']
            if len(details)!=1 or details[0]['prodCd']!=item['prodCd']:
                self.skipped.append(item['prodNm']+' (공식 상품 상세 불일치)');continue
            d=details[0]
            if d['priceUnit']!='M' or d.get('adultJrCd') not in ('NA',''):
                self.excluded.append(item['prodNm']+' (월별 일반 요금제 아님)');continue
            price=amount(d['prodPrice']);data=d['dataDesc']+' '+(d.get('qosDesc') or '')
            plan=record('KB리브모바일',d['prodNm'],price,price,0,data,d['voiceUnit'],d['smsUnit'],{'01':'LGU+','02':'KT','03':'SKT'}[d['soId']],d['prodCd'],'5G' if '5G' in d['prodNm'] else 'LTE')
            plan['raw_text']+=' | 공식 월 기본료: 조건부 할인·제휴카드·캐시백·포인트·기간 한정 추가 데이터 미적용'
            plans.append(plan)
        return plans
