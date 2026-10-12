"""밸류컴·퍼스트의 후불 목록에서 공식 상세 표를 검증한다."""
import re
from urllib.parse import urljoin, unquote
import requests
from bs4 import BeautifulSoup


def parse_gnuboard(soup,name,url):
    plans=[]
    for card in (soup.select('.prepay_tb') or soup.select('.cts_prcInfo')):
        text=card.get_text(' ',strip=True)
        if card.select_one('.circle_box') and '후불' not in text:
            continue
        source=card.get('onclick','')+' '.join(a.get('onclick','') for a in card.select('[onclick]'))
        targets=re.findall(r"['\"]([^'\"]*bo_table=pricList[^'\"]+)['\"]",source)
        if not targets:continue
        href=urljoin(url,targets[0])
        if 'wr_id=' not in href or '후불' not in unquote(href):continue
        response=requests.get(href,timeout=12)
        doc=BeautifulSoup(response.content,'html.parser')
        # 퍼스트는 완전한 공식 요금 표를 반환한 뒤 PHP 오류로 500을 보낸다.
        # 다른 오류 페이지 또는 표가 없는 500은 계속 실패로 처리한다.
        if response.status_code == 500 and 'firstmobile.co.kr' in href and doc.select_one('table.web_tb'):
            pass
        else:
            response.raise_for_status()
        for table in doc.select('table.web_tb'):
            headers=[x.get_text(strip=True) for x in table.select('thead th')]
            if not all(x in headers for x in ['요금제명','기본료','음성','문자','데이터']):continue
            cells=table.select('tbody tr:first-child th, tbody tr:first-child td')
            if len(cells)!=len(headers):continue
            values=dict(zip(headers,[x.get_text(' ',strip=True) for x in cells]));title=values['요금제명']
            current=card.select_one('.month_plan strong')
            price=int(re.sub(r'[^\d]','',current.get_text())) if current else None
            base_match=re.search(r'([\d,]+)\s*원',values['기본료'])
            if price is None or not base_match:continue
            base=int(base_match[1].replace(',',''))
            period=re.search(r'(\d+)\s*개월\s*할인\s*후[^\d]*([\d,]+)\s*원',text)
            if period:
                months=int(period[1]);normal=int(period[2].replace(',',''))
            elif '평생' in text:
                months=-1;normal=base
            elif base==price:
                months=0;normal=base
            else:continue
            if not 0<=price<=normal<=300000 or normal==0:continue
            qos=values.get('QoS','');data=values['데이터'];voice=values['음성'].replace('기본제공','무제한');sms=values['문자'].replace('기본제공','무제한')
            plans.append(dict(telecom_name=name,title=f'[공식몰] {title}',network_type='5G' if '5G' in text else 'LTE',discount_price=price,normal_price=normal,discount_months=months,raw_text=f'{title} | 데이터 {data} + {qos} | 통화 {voice} | 문자 {sms} | {text} [출처: {name} 공식홈페이지] [상품 URL: {href}]'))
            break
    return plans
