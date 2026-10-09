"""상품 미수집/동일 가격 통신사를 홈페이지 메뉴부터 순서대로 조사한다."""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from sqlalchemy import func, case
from database import SessionLocal
from models import Telecom, Plan
from services.crawler.telecom_registry import MASTER_TELECOMS
from services.crawler.direct_crawlers import DirectTelecomCrawler


def inspect(name, url, directory):
    result = {'name':name,'url':url,'menus':[],'pages':[],'error':None}
    session = requests.Session(); session.headers.update(DirectTelecomCrawler.HEADERS)
    try:
        response = session.get(url,timeout=12); response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.content,'html.parser')
        (directory/'home.html').write_text(response.text)
        result['home_url'] = response.url
        nav = soup.select('header a, nav a, .gnb a, #gnb a, .header a, #header a') or soup.select('a')
        seen = set()
        for a in nav:
            label = a.get_text(' ',strip=True)
            href = a.get('href','')
            if not re.search('요금|유심|알뜰|전체',label):
                continue
            if not href or href.startswith(('javascript:','#')):
                quoted = re.findall(r"['\"](/[^'\"]+)['\"]",a.get('onclick','')+href)
                if not quoted:
                    continue
                href = quoted[0]
            target = urljoin(response.url,href)
            if urlparse(target).scheme not in ('http','https') or target in seen:
                continue
            seen.add(target)
            score = (0 if '전체' in label and '요금' in label else 1 if '요금' in label and any(x in target.lower() for x in ('list','all','plan','rate','charge')) else 2)
            result['menus'].append({'label':label,'url':target,'score':score})
        result['menus'].sort(key=lambda item:item['score'])
        for index, menu in enumerate(result['menus'][:5]):
            entry = dict(menu)
            try:
                page = session.get(menu['url'],timeout=12); page.raise_for_status()
                page.encoding = page.apparent_encoding
                doc = BeautifulSoup(page.content,'html.parser')
                (directory/f'list-{index}.html').write_text(page.text)
                entry.update(final_url=page.url,title=doc.title.get_text(strip=True) if doc.title else '',
                             text=doc.get_text(' ',strip=True)[-15000:],size=len(page.text))
                all_links = [{'label':a.get_text(' ',strip=True),'url':urljoin(page.url,a['href'])}
                             for a in doc.select('a[href]') if '전체' in a.get_text() and '요금' in a.get_text()]
                entry['all_plan_links'] = all_links
            except Exception as error:
                entry['error'] = str(error)
            result['pages'].append(entry)
    except Exception as error:
        result['error'] = str(error)
    return result


def investigate():
    db = SessionLocal()
    try:
        names = {row['name'] for row in MASTER_TELECOMS}
        rows = db.query(Telecom.name,Telecom.website_url,func.count(Plan.plan_id),func.sum(case((Plan.discount_price==Plan.normal_price,1),else_=0))).outerjoin(Plan,(Plan.telecom_id==Telecom.telecom_id)&(Plan.is_active==True)).group_by(Telecom.telecom_id).all()
        targets = [{'name':name,'url':url,'active':count,'equal':int(equal or 0)} for name,url,count,equal in rows if name in names and (count==0 or equal)]
    finally:
        db.close()
    targets.sort(key=lambda row:(row['active']!=0,-row['equal']))
    root=Path('/tmp/carrier-inspection'); root.mkdir(exist_ok=True)
    reports=[]
    for index,target in enumerate(targets,1):
        directory=root/f'{index:02d}'; directory.mkdir(exist_ok=True)
        print(f"[{index}/{len(targets)}] {target['name']} 메뉴 조사",flush=True)
        result=inspect(target['name'],target['url'],directory); result.update(active=target['active'],equal=target['equal'],directory=str(directory))
        (directory/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        reports.append(result)
        (root/'report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))
        print('  '+(result['error'] or ' / '.join(f"{m['label']}: {m['url']}" for m in result['menus'][:3]) or 'HTML 메뉴 없음'),flush=True)
    return reports


if __name__ == '__main__':
    investigate()
