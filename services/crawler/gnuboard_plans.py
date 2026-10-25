"""밸류컴·퍼스트의 후불 목록에서 공식 상세 표를 검증한다."""
import re
from urllib.parse import urljoin, unquote
import requests
from bs4 import BeautifulSoup
from services.crawler.pricing_validation import UNKNOWN_NORMAL_MARKER


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
            if not 0<=price<=300000:continue
            # The official post-promotion text may contain an amount typo.
            # Preserve known current price and duration, never guess the correction.
            if period and normal>300000:normal=None
            if normal is not None and (normal<price or normal<=0):continue
            qos=values.get('QoS','');data=values['데이터'];voice=values['음성'].replace('기본제공','무제한');sms=values['문자'].replace('기본제공','무제한')
            plans.append(dict(telecom_name=name,title=f'[공식몰] {title}',network_type='5G' if '5G' in text else 'LTE',discount_price=price,normal_price=normal,discount_months=months,raw_text=f'{title} | 데이터 {data} + {qos} | 통화 {voice} | 문자 {sms} | {text} [출처: {name} 공식홈페이지] [상품 URL: {href}]'+(' '+UNKNOWN_NORMAL_MARKER if normal is None else '')))
            break
    return plans


class GnuboardCatalogCrawler:
    """공식 후불 메뉴의 통신망 탭·페이지 링크를 빠짐없이 순회한다."""
    HOMES={'밸류컴':'https://www.valuecomm.co.kr','퍼스트 모바일':'https://www.firstmobile.co.kr'}

    def __init__(self,name):self.name=name

    def fetch_raw_plans(self):
        from urllib.parse import urlsplit,parse_qs,parse_qsl,urlencode,urlunsplit
        def canonical(url):
            p=urlsplit(url)
            return urlunsplit((p.scheme,p.netloc,p.path,urlencode(sorted(parse_qsl(p.query))),''))
        base=self.HOMES[self.name]
        pending=[canonical(base+'/bbs/board.php?bo_table=pricList&sca=후불')]
        seen=set();products={};self.skipped=[];self.pages=[]
        while pending:
            url=pending.pop(0)
            if url in seen:continue
            if len(seen)>100:raise ValueError('공식 요금제 페이지 순회 한도 초과')
            seen.add(url);response=requests.get(url,timeout=20);response.raise_for_status()
            soup=BeautifulSoup(response.content,'html.parser');self.pages.append(url)
            for node in soup.select('a[href], [onclick]'):
                candidates=[node.get('href','')]+re.findall(r"['\"]([^'\"]+)['\"]",node.get('onclick',''))
                for candidate in candidates:
                    target=canonical(urljoin(url,candidate));parts=urlsplit(target);query=parse_qs(parts.query)
                    if parts.netloc!=urlsplit(base).netloc or query.get('bo_table')!=['pricList'] or 'wr_id' in query:continue
                    if query.get('sca') not in (None,['후불']):continue
                    if target not in seen and target not in pending:pending.append(target)
            if parse_qs(urlsplit(url).query).get('sca')!=['후불']:continue
            rows=parse_gnuboard(soup,self.name,url)
            expected=set()
            for node in soup.select('[onclick]'):
                for candidate in re.findall(r"['\"]([^'\"]*wr_id=[^'\"]+)['\"]",node.get('onclick','')):
                    q=parse_qs(urlsplit(candidate).query)
                    if q.get('sca')==['후불']:expected.add(q['wr_id'][0])
            found=set()
            for row in rows:
                match=re.search(r'\[상품 URL: (.*?)\]',row['raw_text'])
                code=parse_qs(urlsplit(match[1]).query)['wr_id'][0];found.add(code)
                old=products.get(code)
                if old and any(old[k]!=row[k] for k in ('title','discount_price','normal_price','discount_months')):
                    raise ValueError('동일 상품의 가격 정보 충돌')
                products[code]=row
            self.skipped.extend(sorted(expected-found))
        if not products:raise ValueError('공식 후불 전체 목록 검증 실패')
        return list(products.values())
