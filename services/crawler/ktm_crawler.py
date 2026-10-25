"""KT M모바일 공개 전체 카테고리와 상품 API. 별도 결합/기간 추가 데이터 제외."""
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
from services.crawler.structured_official import record, amount


class KtmCrawler:
    BASE='https://www.ktmmobile.com'
    RESTRICTED=('결합','단말','키즈','시니어','청소년','주니어','워치','태블릿','2nd','복지','쉐어링')

    @classmethod
    def parse(cls,item):
        title=item['rateAdsvcNm']
        if item.get('useYn')!='Y' or any(word in title for word in cls.RESTRICTED):return None
        normal=amount(item['mmBasAmtVatDesc']);promo=item.get('promotionAmtVatDesc')
        current=amount(promo) if promo else normal
        # Official direct-store common conditions define the ongoing promotion;
        # usePrd=0/dateType=1 denotes no duration, not a guessed 12-month term.
        if current<normal and (item.get('usePrd')!='0' or item.get('dateType')!='1'):
            raise ValueError('KT M모바일 할인 기간 구조 변경')
        months=-1 if current<normal else 0
        return record('KT M모바일',title,current,normal,months,item['bnfitData'],item['bnfitVoice'],item['bnfitSms'],
                      'KT',item['rateAdsvcCd'],'5G' if '5G' in title else 'LTE')

    def fetch_raw_plans(self):
        session=requests.Session()
        r=session.get(self.BASE+'/m/direct/storeInfo.do',timeout=20);r.raise_for_status()
        terms=BeautifulSoup(r.content,'html.parser').get_text(' ',strip=True)
        if '평생할인' not in terms or '다이렉트몰' not in terms:raise ValueError('KT M모바일 다이렉트 할인 정책 확인 실패')
        r=session.post(self.BASE+'/rate/getCtgXmlAllListAjax.do',data={'rateAdsvcDivCd':'RATE'},timeout=20);r.raise_for_status();categories=r.json()
        roots={c['rateAdsvcCtgCd'] for c in categories if c.get('depthKey')==1 and c.get('rateAdsvcCtgNm') in ('유심/eSIM 요금제','제휴 요금제')}
        if len(roots)!=2:raise ValueError('KT M모바일 전체 카테고리 구조 변경')
        allowed=set(roots)
        for depth in (2,3):
            for c in categories:
                if c.get('depthKey')==depth and c.get('upRateAdsvcCtgCd') in allowed and not any(w in c['rateAdsvcCtgNm'] for w in self.RESTRICTED):allowed.add(c['rateAdsvcCtgCd'])
        items={};self.skipped=[];self.category_counts={}
        now=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
        for c in categories:
            if c['rateAdsvcCtgCd'] not in allowed or not c.get('relCnt') or c.get('useYn')!='Y':continue
            if not c['pstngStartDate']<=now<=c['pstngEndDate']:continue
            r=session.post(self.BASE+'/rate/rateContentAjax.do',data={'rateAdsvcCtgCd':c['rateAdsvcCtgCd']},timeout=20);r.raise_for_status();rows=r.json()
            # relCnt is the registered association count, whereas this public
            # endpoint filters unpublished products. The actual UI consumes this
            # whole array without pagination; never use relCnt as a page limit.
            if not isinstance(rows,list):raise ValueError('KT M모바일 목록 응답 형식 변경')
            self.category_counts[c['rateAdsvcCtgCd']]=len(rows)
            for item in rows:
                previous=items.get(item['rateAdsvcCd'])
                if previous and any(previous[k]!=item[k] for k in ('mmBasAmtVatDesc','promotionAmtVatDesc','bnfitData','bnfitVoice','bnfitSms')):raise ValueError('KT M모바일 중복 상품 가격/제공량 충돌')
                items[item['rateAdsvcCd']]=item
        if not items:raise ValueError('KT M모바일 전체 상품 없음')
        result=[]
        for item in items.values():
            try:
                if (row:=self.parse(item)):result.append(row)
            except (ValueError,KeyError,TypeError) as error:self.skipped.append(f"{item.get('rateAdsvcNm')}: {error}")
        return result
