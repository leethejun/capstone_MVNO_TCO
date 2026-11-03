"""모빙 공개 브랜드관의 전체 수집 호환 인터페이스."""
from services.crawler.hub_brand_crawler import HubBrandCrawler
from services.crawler.mvnohub_crawler import MvnohubCrawler


class MobingHubCrawler(HubBrandCrawler):
    URL = 'https://www.mvnohub.kr/brand/plan/11.do'

    def __init__(self, timeout=25, delay_sec=0.15):
        super().__init__('모빙', self.URL, timeout, delay_sec)

    @staticmethod
    def parse(item, card):
        return HubBrandCrawler._parse(item, card, '모빙')

    @staticmethod
    def apply_detail(plan, item, soup):
        return HubBrandCrawler._apply_detail(plan, item, soup, '모빙')
