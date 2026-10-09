from bs4 import BeautifulSoup
from services.crawler.menu_cards import parse_menu_cards
from services.crawler.sk7_crawler import Sk7Crawler


def card(ref='',badge=''):
    return BeautifulSoup(f'<a class="card_rate_link" href="rateplan_view.do?no=1"><p class="title">테스트</p><p class="badge">{badge}</p><ul class="desc"><li>15GB + 3Mbps</li><li>통화 기본제공</li><li>문자 100건</li></ul><div class="price">월 10원<p class="ref">{ref}</p></div></a>','html.parser')


def detail(url):
    return BeautifulSoup('<table><thead><tr><th>요금제</th><th>기본료(원)</th></tr></thead><tbody><tr><td>테스트</td><td>29,700</td></tr></tbody></table>','html.parser')


def test_eighth_month_means_seven_discounted_months():
    p=parse_menu_cards(card('*8개월 차부터 29,700원','쿠폰 24개월 제공'),'조이','https://joytel.co.kr/rate_plan.do','SKT')[0]
    assert (p['discount_price'],p['normal_price'],p['discount_months'])==(10,29700,7)


def test_lifetime_original_from_detail_table():
    p=parse_menu_cards(card('*평생할인'),'조이','https://joytel.co.kr/rate_plan.do','SKT',detail)[0]
    assert (p['normal_price'],p['discount_months'])==(29700,-1)


def test_unknown_discount_duration_is_not_guessed():
    soup=card('','쿠폰 24개월 제공')
    soup.select_one('.price').insert(0,BeautifulSoup('<p class=origin>29,700원</p>','html.parser'))
    assert parse_menu_cards(soup,'조이','https://joytel.co.kr/rate_plan.do','SKT',detail)==[]


def test_sk7_duration_is_not_gift_duration():
    item=dict(prodNm='LTE 유심',prodCd='A',prodTp='20',basicAmt='48,400',basicAmt2='16,900',promoDcMth='9999',gcGiftNm='상품권 10개월',basicFreeData='7',basicFreeDataUnit='GB')
    p=Sk7Crawler.parse(item)
    assert (p['normal_price'],p['discount_months'])==(48400,-1)
    item['promoDcMth']='12'
    assert Sk7Crawler.parse(item)['discount_months']==12


def load_tests(loader, tests, pattern):
    import unittest
    return unittest.TestSuite(unittest.FunctionTestCase(value) for name,value in globals().items() if name.startswith('test_') and callable(value))


def test_theone_uses_price_after_promotion_not_list_price():
    from services.crawler.theone_crawler import TheOneCrawler
    p=TheOneCrawler.parse(dict(GDCD='1',GDNM='요금제',APPDT='20200101',ENDDT='99991231',AMT_MONTHLY='2,750',AMT_DISCOUNT='22,000',TT_AMT='35,200',PERIOD='8개월 차부터',SEEDATA='7GB+1Mbps',SEEVOICE='기본제공',SEELETTER='기본제공',EVNTTAGNM1='KT망'))
    assert (p['discount_price'],p['normal_price'],p['discount_months'])==(2750,22000,7)
