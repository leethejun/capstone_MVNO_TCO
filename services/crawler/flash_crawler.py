"""플래시 공식 USIM 기본료. 약정/제휴카드 조건부 광고가는 사용하지 않는다."""
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from services.crawler.structured_official import amount,record


class FlashCrawler:
    URLS=[('KT','https://olleh.flashmobile.kr/html_k/pay_main.html'),('LGU+','https://uplus.flashmobile.kr/html/pay_main.html')]

    def fetch_raw_plans(self):
        plans=[];seen=set()
        for network,url in self.URLS:
            r=requests.get(url,timeout=25);r.raise_for_status();s=BeautifulSoup(r.content,'html.parser')
            cards=s.select('dl.charge_list')
            if not cards:raise ValueError('플래시 공식 요금제 목록 없음')
            for card in cards:
                if not any('USIM' in x for x in card.get('class',[])):continue
                heading=BeautifulSoup(str(card.select_one('.charge_name')),'html.parser')
                for badge in heading.select('span'):badge.decompose()
                title=heading.get_text(' ',strip=True)
                if any(x in title for x in ['청소년','복지','시니어','태블릿','워치']):continue
                a=card.select_one('a.btn_ch_detail[href]')
                if not a:raise ValueError('플래시 상세 링크 누락')
                href=urljoin(url,a['href'])
                if href in seen:continue
                seen.add(href);detail=requests.get(href,timeout=20);detail.raise_for_status();doc=BeautifulSoup(detail.content,'html.parser');base=None
                for table in doc.select('table.tb'):
                    if '기본료' not in table.get_text():continue
                    for tr in table.select('tr'):
                        cells=tr.find_all('td',recursive=False)
                        if len(cells)<2 or re.sub(r'\s+','',cells[0].get_text())!=re.sub(r'\s+','',title):continue
                        m=re.search(r'([\d,]+)\s*원',cells[1].get_text(' ',strip=True))
                        if m:base=amount(m[1]);break
                    if base:break
                if base is None:raise ValueError(f'플래시 공식 무약정 기본료 확인 실패: {title}')
                specs=card.select('.charge_info .service_name')
                if len(specs)!=3:raise ValueError('플래시 제공량 누락')
                voice,sms,data=[x.get_text(' ',strip=True).replace('기본제공','무제한') for x in specs]
                plan=record('플래시모바일',title,base,base,0,data,voice,sms,network,href,'5G' if '5G' in title else 'LTE')
                plan['raw_text']+=' | 공식 상세 기본료 기준: 약정·제휴카드 할인 미적용'
                plans.append(plan)
        return plans
