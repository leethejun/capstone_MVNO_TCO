"""공식 요금제 검색 화면의 전체 응답을 수집한다 (HTML 예시 카드는 목록이 아니다)."""
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import requests
from services.crawler.structured_official import record, amount


class EyagiCrawler:
    URL = 'https://www.eyagi.co.kr/shop/plan/json_proc.php'
    FIELDS = ('comm_code','agent_code','comm_name','mno_gubun','pay_type','base_fee',
              'selling_price','restoration_fee','terms','terms_str','free_data_str',
              'add_data','qos','call_str','sms_str','evnt_start_date','evnt_end_date','is_5g_yn')

    @staticmethod
    def parse(item):
        title=item['comm_name']
        if item['pay_type']!='2' or re.search(r'시니어|청소년|주니어|키즈|복지|태블릿|워치|쉐어링|선불|팡',title):
            return None
        now=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d%H%M%S')
        if item['evnt_start_date'] and now<item['evnt_start_date']: return None
        if item['evnt_end_date'] and now>item['evnt_end_date']: return None
        current=amount(item['selling_price'])
        if not any(item[k] for k in ('base_fee','restoration_fee','terms','terms_str')):
            normal=current;months=0
        elif item['terms_str']=='life' and item['terms']=='99':
            normal=amount(item['base_fee']);months=-1 if current<normal else 0
        else:
            months=amount(item['terms']);normal=amount(item['restoration_fee'])
            if months<=0:raise ValueError('할인 기간 확인 필요')
        data=item['free_data_str']
        if not re.fullmatch(r'\d+(?:\.\d+)?[GM]B',data):raise ValueError('정액 데이터 제공량 확인 필요')
        extra=item['add_data']
        if re.fullmatch(r'매일\s*\d+(?:\.\d+)?GB',extra): data+=' + '+extra
        elif extra not in ('','데이터 차단'):raise ValueError('일일 데이터 제공량 확인 필요')
        qos=item['qos']
        if qos:
            if not re.fullmatch(r'\d+(?:\.\d+)?K?',qos):raise ValueError('QoS 단위 확인 필요')
            data+=' + '+(qos[:-1]+'Kbps' if qos.endswith('K') else qos+'Mbps')
        for key,unit in [('call_str','분'),('sms_str','건')]:
            if item[key]!='기본제공' and not re.fullmatch(r'\d+'+unit,item[key]):
                raise ValueError('통화/문자 정액 제공량 확인 필요')
        return record('이야기모바일',title,current,normal,months,data,item['call_str'],item['sms_str'],
                      {'lgt':'LGU+','kt':'KT','skt':'SKT'}.get(item['mno_gubun'],item['mno_gubun']),
                      item['comm_code']+':'+item['agent_code'],item['is_5g_yn'])

    def fetch_raw_plans(self):
        response=requests.post(self.URL,data={'page_seq':'2','keyword':'','search_mindata':'0GB',
            'search_maxdata':'무제한','search_pchip':'','search_callgride':'','search_networkgride':'',
            'search_carrierSelect':'all','search_planSort':'reco','mode':'comm_list_view'},timeout=40)
        response.raise_for_status();payload=response.json();data=payload['data'];count=int(payload['num'])
        if count<=0 or any(not isinstance(data.get(k),list) or len(data[k])!=count for k in self.FIELDS):
            raise ValueError('이야기모바일 전체 검색 응답 개수 불일치')
        self.source_count=count;self.skipped=[];result=[];seen=set()
        for i in range(count):
            item={k:data[k][i] for k in self.FIELDS};key=(item['comm_code'],item['agent_code'])
            if key in seen: raise ValueError('이야기모바일 상품 코드 중복')
            seen.add(key)
            try:
                if (row:=self.parse(item)):result.append(row)
            except (ValueError,TypeError,KeyError) as error:self.skipped.append(f"{item['comm_name']}: {error}")
        return result
