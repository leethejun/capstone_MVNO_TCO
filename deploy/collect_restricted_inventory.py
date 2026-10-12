"""추천 가입 조건을 검증하지 못하는 공식 상품의 원본과 전체 DB 건수를 별도 조사한다. DB는 변경하지 않는다."""
from pathlib import Path
import requests,json,re
from bs4 import BeautifulSoup
from database import SessionLocal
from models import Plan,Telecom
from sqlalchemy import func
from services.crawler.telecom_registry import MASTER_TELECOMS


def main():
    inventory={}
    url='https://chingumobile.com/ko/plans/select/postpaid'
    s=BeautifulSoup(requests.get(url,timeout=20).content,'html.parser');cards=s.select('article')
    if not cards:raise ValueError('친구 전체 목록 없음')
    products=[]
    for a in cards:
     link=a.select_one('a[href*=detail]');d=BeautifulSoup(requests.get('https://chingumobile.com'+link['href'],timeout=20).content,'html.parser')
     products.append({'title':a.select_one('h3').get_text(' ',strip=True),'url':'https://chingumobile.com'+link['href'],'card':a.get_text(' ',strip=True),'detail':d.get_text(' ',strip=True)})
    inventory['친구모바일']={'url':url,'products':products,'reason':'공식 상품 선택 화면의 가입 대상은 외국인등록증 소지자. 상품별 최소 183일 이용·단말·연령 조건이 있어 일반 무약정 추천에 미포함.'}
    url='https://mobile.coinshot.org/api/mvno-plan?page=0&size=100&recommend=false'
    r=requests.get(url,timeout=20);r.raise_for_status();d=r.json()
    if len(d['list'])!=d['totalElement'] or d['maxPage']!=1:raise ValueError('코인샷 전체 목록 개수 불일치')
    inventory['코인샷 모바일']={'url':url,'products':d['list'],'reason':'공개 9개 모두 선불(PRE): 7개 정액·2개 종량. 선불 충전 주기를 월 후불 유지기간과 동일하다고 가정하지 않음.'}
    (Path(__file__).resolve().parents[1]/'runtime').mkdir(exist_ok=True)
    (Path(__file__).resolve().parents[1]/'runtime'/'restricted-carrier-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2))
    print('별도 원본 수집', {k:len(v['products']) for k,v in inventory.items()},flush=True)
    db=SessionLocal();rows=[]
    for entry in MASTER_TELECOMS:
     t=db.query(Telecom).filter(Telecom.name==entry['name']).one()
     p=db.query(Plan).filter(Plan.telecom_id==t.telecom_id,Plan.is_active==True)
     rows.append({'name':entry['name'],'active':p.count(),'official':p.filter(Plan.title.startswith('[공식몰]')).count(),'same_price':p.filter(Plan.normal_price==Plan.discount_price).count()})
    print('전체 활성',sum(x['active'] for x in rows),'미반영',[x['name'] for x in rows if not x['active']],flush=True)
    (Path(__file__).resolve().parents[1]/'runtime'/'carrier-counts.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));db.close()


if __name__=="__main__":
    main()
