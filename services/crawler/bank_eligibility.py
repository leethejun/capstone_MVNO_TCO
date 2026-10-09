"""금융 거래 조건이 붙은 은행계 통신사 상품은 추천 수집 대상에서 제외."""
import re
from services.crawler.telecom_registry import canonical_telecom_name

BANK_CARRIERS={'KB리브모바일','우리WON모바일','토스모바일'}
FINANCIAL_CONDITIONS=re.compile(r'금융\s*(?:상품|할인|거래|실적|혜택)|급여\s*이체|예[·ㆍ/\s]?적금|예금\s*(?:가입|보유)|적금\s*(?:가입|보유)|주택\s*청약|카드\s*(?:실적|이용금액)|은행\s*거래\s*실적')


def requires_financial_product(record):
    if canonical_telecom_name(record.get('telecom_name','')) not in BANK_CARRIERS:
        return False
    if record.get('requires_financial_product') is True:
        return True
    return bool(FINANCIAL_CONDITIONS.search(record.get('title','')+' '+record.get('raw_text','')))
