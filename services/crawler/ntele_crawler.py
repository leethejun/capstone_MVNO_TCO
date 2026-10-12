"""앤텔레콤 공식 K/L망 후불 목록. 선불/복지 목록은 혼합하지 않는다."""
import requests
from bs4 import BeautifulSoup
from services.crawler.structured_official import amount, record


class NteleCrawler:
    BASE='https://info.n-telecom.co.kr/ntelecom-asp/products/'

    def fetch_raw_plans(self):
        plans=[]
        for network,file in [('KT','KTdefer_lte.asp'),('LGU+','LGdefer_lte.asp')]:
            response=requests.get(self.BASE+file,timeout=20);response.raise_for_status();soup=BeautifulSoup(response.content,'html.parser');cards=soup.select('.plan-summary')
            if not cards:raise ValueError('앤텔레콤 후불 목록 없음')
            for card in cards:
                title=card.select_one('.plan-name').get_text(' ',strip=True)
                if any(x in title for x in ['복지','약정','청소년','시니어']):continue
                specs={}
                for label in card.select('.label-group'):
                    text=label.get_text(' ',strip=True);key=text.split()[0]
                    specs[key]=text[len(key):].strip().replace('기본제공','무제한')
                for key in ['음성','문자','데이터']:
                    if key not in specs:raise ValueError('앤텔레콤 제공량 누락')
                    if specs[key]=='-':specs[key]='0GB' if key=='데이터' else '0분' if key=='음성' else '0건'
                price=amount(card.select_one('.main-price span').get_text())
                plans.append(record('앤텔레콤',title,price,price,0,specs['데이터'],specs['음성'],specs['문자'],network,title,'5G' if '5G' in title else 'LTE'))
        return plans
