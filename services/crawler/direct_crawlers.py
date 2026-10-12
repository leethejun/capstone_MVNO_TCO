import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any, Set, Tuple, Optional
from services.crawler.base import BaseCrawler
from services.crawler.eyes_crawler import EyesCrawler
from services.crawler.official_routes import OFFICIAL_PLAN_LIST_URLS
from services.crawler.mvnohub_crawler import MvnohubCrawler
from services.crawler.kgmobile_crawler import KgMobileCrawler
from services.crawler.telecom_registry import MASTER_TELECOMS, canonical_telecom_name, is_excluded_telecom


class DirectTelecomCrawler(BaseCrawler):
    """
    알뜰폰허브(mvnohub.kr/brand.do)에 등록된 모든 알뜰폰 사업자(25개사)를
    동적으로 파악한 뒤, 각 사업자의 공식 홈페이지 및 브랜드 전용 페이지를
    직접 일일이 방문하여 크롤링하는 개별 사업자 전용 크롤러
    """

    BRAND_LIST_URL = "https://www.mvnohub.kr/brand.do"
    BASE_URL = "https://www.mvnohub.kr"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(self, timeout: int = 10, delay_sec: float = 0.2):
        self.timeout = timeout
        self.delay_sec = delay_sec
        self.failed_telecom_names = set()
        self.coverage = []
        self._official_errors = {}
        self._detail_price_cache: Dict[str, Optional[int]] = {}

    def fetch_raw_plans(self) -> List[Dict[str, Any]]:
        """
        알뜰폰허브에 등록된 모든 사업자 목록을 파악하고,
        각 공식 홈페이지 및 브랜드 전용 페이지를 직접 순회하여 요금제를 수집합니다.
        """
        all_plans: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple[str, str]] = set()

        # Step 1: 알뜰폰허브에서 모든 입점 사업자 목록과 공식 홈페이지 URL 수집
        self.failed_telecom_names.clear()
        self._official_errors.clear()
        self.coverage = []
        brands = self.merge_brands(self.discover_all_mvno_brands())
        print(f"[DirectTelecomCrawler] 허브 + 마스터 수집 대상: {len(brands)}개")

        # Step 2: 각 사업자의 공식 홈페이지 및 브랜드 전용 요금제 페이지를 직접 방문
        for i, brand in enumerate(brands, 1):
            name = brand["name"]
            home_url = brand["home_url"]
            brand_plan_url = brand["brand_plan_url"]
            network = brand.get("network", "")

            print(f"[DirectTelecomCrawler] [{i}/{len(brands)}] '{name}' 공식몰 직접 크롤링 시작 ({home_url})")

            # 2-A: 공식 홈페이지 직접 방문 크롤링
            error = None
            try:
                official_plans = self._crawl_brand_official_site(name, home_url, network)
            except Exception as exc:
                official_plans = []
                error = str(exc)
            valid_plans = [plan for plan in official_plans
                           if isinstance(plan.get('discount_price'), int)
                           and isinstance(plan.get('normal_price'), int)
                           and 0 <= plan['discount_price'] <= plan['normal_price']
                           and plan['normal_price'] > 0
                           and isinstance(plan.get('discount_months'), int)
                           and plan['discount_months'] >= -1]
            if len(valid_plans) != len(official_plans):
                self.failed_telecom_names.add(name)
                error = f'가격/기간 검증 실패 {len(official_plans) - len(valid_plans)}건: 이전 상품은 추천에서 제외'
            official_plans = valid_plans
            if not official_plans:
                self.failed_telecom_names.add(name)
                error = error or self._official_errors.get(name) or '공식몰에서 검증 가능한 요금제 없음: 사이트/API/파서 확인 필요'
            added_hub = 0
            added_official = 0
            for p in official_plans:
                key = (p["telecom_name"], p["title"], p.get("network_type"), p.get("discount_price"), p.get("normal_price"), p.get("discount_months"), p.get("raw_text"))
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_plans.append(p)
                    added_official += 1

            # 2-B: 허브 내 브랜드 전용 요금제 페이지 크롤링
            if brand_plan_url:
                hub_brand_plans = self._crawl_brand_hub_page(name, brand_plan_url)
                added_hub = 0
                for p in hub_brand_plans:
                    key = (p["telecom_name"], p["title"], p.get("network_type"), p.get("discount_price"), p.get("normal_price"), p.get("discount_months"), p.get("raw_text"))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_plans.append(p)
                        added_hub += 1

            self.coverage.append({'name': name, 'home_url': home_url,
                                  'official_count': len(official_plans), 'hub_count': added_hub,
                                  'status': 'collected' if official_plans and name not in self.failed_telecom_names else 'needs_attention',
                                  'error': error or self._official_errors.get(name)})
            print(f"[DirectTelecomCrawler] '{name}' 수집 완료 (공식몰: {added_official}건, 브랜드특가: {added_hub if brand_plan_url else 0}건)")

            if self.delay_sec > 0:
                time.sleep(self.delay_sec)

        print(f"[DirectTelecomCrawler] ✅ 개별 사업자 수집 시도 완료: 총 {len(all_plans)}건 요금제 수집")
        return all_plans

    @staticmethod
    def merge_brands(hub_brands):
        """목록 누락과 허브 장애에 무관하게 모든 마스터를 방문한다."""
        def host(url):
            return urlparse(url or '').netloc.lower().removeprefix('www.')
        def name(value):
            return re.sub(r'\s+', '', canonical_telecom_name(value)).lower()
        result = [dict(brand) for brand in hub_brands]
        for carrier in MASTER_TELECOMS:
            match = next((brand for brand in result
                          if name(brand['name']) == name(carrier['name']) or
                          (host(brand.get('home_url')) and host(brand.get('home_url')) == host(carrier['website_url']))), None)
            if match:
                match['name'] = carrier['name']
                match['home_url'] = match.get('home_url') or carrier['website_url']
            else:
                result.append({'name': carrier['name'], 'home_url': carrier['website_url'],
                               'brand_plan_url': '', 'network': carrier['network']})
        return [brand for brand in result if not is_excluded_telecom(brand["name"], brand.get("home_url", ""))]

    def discover_all_mvno_brands(self) -> List[Dict[str, str]]:
        """알뜰폰허브 brand.do를 크롤링하여 전체 사업자 목록 및 공식 홈페이지 추출"""
        brands = []
        try:
            resp = requests.get(self.BRAND_LIST_URL, headers=self.HEADERS, timeout=self.timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            boxes = soup.select(".brand_box_list .box")
            for box in boxes:
                name_el = box.select_one(".logo_div p span, p span")
                name = name_el.get_text(strip=True) if name_el else ""
                if not name:
                    continue

                home_link = box.select_one(".btm a[href^='http']")
                home_url = home_link.get("href") if home_link else ""

                brand_plan_link = box.select_one("a[href*='/brand/plan/']")
                brand_plan_url = ""
                if brand_plan_link:
                    raw_href = brand_plan_link.get("href", "")
                    brand_plan_url = urljoin(self.BASE_URL, raw_href)

                network_el = box.select_one(".gb")
                network = network_el.get_text(strip=True) if network_el else ""

                brands.append({
                    "name": name,
                    "home_url": home_url,
                    "brand_plan_url": brand_plan_url,
                    "network": network
                })

        except Exception as e:
            print(f"[DirectTelecomCrawler] 사업자 목록 탐색 오류: {e}")

        return brands

    def _crawl_brand_official_site(self, telecom_name: str, home_url: str, default_network: str) -> List[Dict[str, Any]]:
        """각 알뜰폰 사업자 공식 홈페이지를 직접 방문하여 요금제 추출"""
        plans = []
        if is_excluded_telecom(telecom_name, home_url):
            return plans
        if not home_url or not home_url.startswith("http"):
            return plans

        # 1. 특화 크롤러가 있는 주요 사업자
        from services.crawler.structured_official import PinCrawler, AlbireoCrawler, MonaCrawler, GmeCrawler, EumCrawler, ErelCrawler, S1Crawler, KoretelCrawler, ShakeCrawler
        from services.crawler.flash_crawler import FlashCrawler
        from services.crawler.won_crawler import WonCrawler
        from services.crawler.kb_crawler import KbCrawler
        dedicated={'KB리브모바일':KbCrawler,'핀다이렉트':PinCrawler,'알비레오':AlbireoCrawler,'MONA':MonaCrawler,'GME모바일':GmeCrawler,'이음모바일':EumCrawler,'에르엘':ErelCrawler,'에스원 안심모바일':S1Crawler,'플래시모바일':FlashCrawler,'한국E텔레콤':KoretelCrawler,'우리WON모바일':WonCrawler,'쉐이크모바일':ShakeCrawler}
        if telecom_name in dedicated:
            crawler=dedicated[telecom_name]()
            records=crawler.fetch_raw_plans()
            if getattr(crawler,'skipped',[]):
                self.failed_telecom_names.add(telecom_name)
                self._official_errors[telecom_name]=f'공식 가격 기간 확인 불가 {len(crawler.skipped)}건 제외: '+', '.join(crawler.skipped)
            return records
        clean_name = telecom_name.replace(" ", "")
        if 'theonem.co.kr' in home_url:
            from services.crawler.theone_crawler import TheOneCrawler
            return TheOneCrawler().fetch_raw_plans()
        if 'sk7mobile.com' in home_url:
            from services.crawler.sk7_crawler import Sk7Crawler
            return Sk7Crawler(headers=self.HEADERS, timeout=self.timeout).fetch_raw_plans()
        if '아이즈' in clean_name or 'eyes.co.kr' in home_url:
            return EyesCrawler(headers=self.HEADERS, timeout=self.timeout, delay_sec=self.delay_sec).fetch_raw_plans()
        if 'KG모바일' in clean_name or 'kgmobile.co.kr' in home_url:
            try:
                crawler = KgMobileCrawler(timeout=self.timeout, delay_sec=self.delay_sec)
                plans = crawler.fetch_raw_plans()
                if crawler.skipped:
                    self.failed_telecom_names.add(telecom_name)
                    self._official_errors[telecom_name] = f'가격/스펙 검증 실패 {crawler.skipped}건: 이전 상품은 추천에서 제외'
                return plans
            except Exception as error:
                self.failed_telecom_names.add('KG모바일')
                print(f'[DirectTelecomCrawler] KG모바일 수집 실패: {error}')
                return []
        if "프리티" in clean_name:
            return self._crawl_freet_direct(telecom_name)
        elif "큰사람" in clean_name or "이야기" in clean_name:
            return self._crawl_eyagi_direct(telecom_name)
        elif "유니컴즈" in clean_name or "모빙" in clean_name:
            return self._crawl_mobing_direct(telecom_name, home_url)

        # 2. 일반 사업자 공식 홈페이지 직접 방문 및 요금제 추출
        try:
            resp = requests.get(home_url, headers=self.HEADERS, timeout=self.timeout)
            if resp.status_code != 200:
                self._official_errors[telecom_name] = f'HTTP {resp.status_code}'
                return plans

            soup = BeautifulSoup(resp.content, "html.parser")

            # 메인 페이지 및 요금제 링크 탐색
            plan_urls = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                txt = a.get_text(strip=True)
                if href.startswith(('javascript:', '#')):
                    paths = re.findall(r"['\"](/[^'\"]+)['\"]", href + a.get('onclick', ''))
                    if not paths:
                        continue
                    href = paths[0]
                if any(k in href.lower() for k in ["/plan", "/rate", "/charge", "plan_list", "charge_list"]) or any(k in txt for k in ["요금제", "요금제 안내"]):
                    full = urljoin(resp.url, href)
                    if urlparse(full).netloc == urlparse(resp.url).netloc:
                        plan_urls.add(full)

            # 요금제 목록 페이지 우선순위 정렬 (view/detail 단일 페이지보다 list/rate_plan 등 목록 페이지 우선)
            sorted_plan_urls = sorted(
                plan_urls,
                key=lambda u: (
                    0 if any(k in u.lower() for k in ["rate_plan.do", "plan_list", "/plan/list", "rate_plan", "/plan"]) and not any(v in u.lower() for v in ["view", "detail"]) else
                    1 if not any(v in u.lower() for v in ["view", "detail", "charge_account", "charge_credit", "charge_autopay"]) else
                    2
                )
            )
            # 방문할 URL 목록: 메인 + 주요 요금제 페이지 (최대 3개)
            verified = OFFICIAL_PLAN_LIST_URLS.get(canonical_telecom_name(telecom_name))
            targets = list(dict.fromkeys(([verified] if verified else []) + [resp.url] + sorted_plan_urls))

            for target_url in targets:
                try:
                    r = requests.get(target_url, headers=self.HEADERS, timeout=self.timeout)
                    if r.status_code != 200:
                        continue
                    p_soup = BeautifulSoup(r.content, "html.parser")
                    extracted = self._extract_plans_from_html(telecom_name, p_soup, target_url, default_network)
                    plans.extend(extracted)
                except Exception:
                    continue

        except Exception as e:
            self._official_errors[telecom_name] = str(e)
            print(f"[DirectTelecomCrawler] '{telecom_name}' 공식몰({home_url}) 크롤링 중 오류: {e}")

        return plans

    def _fetch_normal_price_from_detail(self, detail_url: str) -> Optional[int]:
        """카드에 정상가가 누락된 경우 상세 페이지에서 'N개월 이후 XX원' 또는 정상가 추출"""
        if detail_url in self._detail_price_cache:
            return self._detail_price_cache[detail_url]

        try:
            r = requests.get(detail_url, headers=self.HEADERS, timeout=3)
            if r.status_code == 200:
                # 1. '7개월 이후 56,650원', '이후 56,650원', '정상가 56,650원' 등 패턴 탐색
                detail_soup = BeautifulSoup(r.text, "html.parser")
                detail_text = detail_soup.get_text(" ", strip=True)
                matches = re.findall(r'(?:\*?\d+\s*개월\s*이후|정상가?|기본료)\s*([\d,]+)\s*원', detail_text)
                if matches:
                    val = int(matches[0].replace(",", ""))
                    self._detail_price_cache[detail_url] = val
                    return val

                # 2. .origin, del 등 정상가 태그 탐색
                soup = BeautifulSoup(r.text, "html.parser")
                origin_el = soup.select_one(".origin, del, s, strike, .before_price, .normal_price, .org_p")
                if origin_el:
                    digits = re.sub(r"[^\d]", "", origin_el.get_text())
                    if digits:
                        val = int(digits)
                        self._detail_price_cache[detail_url] = val
                        return val
        except Exception:
            pass

        self._detail_price_cache[detail_url] = None
        return None

    def _extract_plans_from_html(self, telecom_name: str, soup: BeautifulSoup, page_url: str, default_network: str) -> List[Dict[str, Any]]:
        """일반 웹페이지 HTML에서 요금제 패턴(카드, 박스, 리스트)을 직접 추출"""
        if soup.select('.prepay_tb, .cts_prcInfo') and any(host in page_url for host in ('valuecomm.co.kr', 'firstmobile.co.kr')):
            from services.crawler.gnuboard_plans import parse_gnuboard
            return parse_gnuboard(soup, telecom_name, page_url)
        if soup.select('a.card_rate_link, a.rate_link'):
            from services.crawler.menu_cards import parse_menu_cards
            records = parse_menu_cards(soup, telecom_name, page_url, default_network)
            expected = len({a.get("href") for a in soup.select("a.card_rate_link, a.rate_link")})
            if len(records) < expected:
                self.failed_telecom_names.add(telecom_name)
                self._official_errors[telecom_name] = f"공식 카드 {expected}건 중 가격/기간 검증 {len(records)}건: 미확인 상품 제외"
            return records
        plans = []
        seen_titles = set()

        # 요금제 카드로 추정되는 컨테이너 셀렉터 (.rate_card_item 등 추가)
        candidate_selectors = [
            ".rate_card_item, .plan-card, .plan_card, .plan-item, .plan_item, .plan_box, .plan-box, .card_list_item",
            ".rate-item, .rate_item, .card-plan, .product-item",
            "li[class*='plan'], div[class*='plan_list'] > ul > li",
            "table.plan_table tbody tr, table.rate_table tbody tr"
        ]

        elements = []
        for sel in candidate_selectors:
            found = soup.select(sel)
            if found:
                elements = found
                break

        # 임의 div/li 탐색은 메뉴·혜택·로밍 안내까지 상품으로 오인한다.
        # 알려진 상품 카드가 없으면 사이트별 전용 크롤러가 필요하다.
        for el in elements:
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
            if not ("원" in txt and ("GB" in txt or "MB" in txt or "통화" in txt)):
                continue

            # 요금제명 추출
            title_el = el.select_one(".tit, .title, strong, h3, h4, .name")
            if title_el:
                title = title_el.get_text(" ", strip=True)
            else:
                m = re.search(r'([A-Za-z0-9가-힣+]{2,15}(?:\s+[A-Za-z0-9가-힣+]{1,10}){1,3})', txt)
                title = m.group(1) if m else f"{telecom_name} 알뜰요금제"

            # 소수점(.), 퍼센트(%), 슬래시(/) 등 요금제 스펙 문자가 제거되지 않도록 보존
            title = re.sub(r'[^\w\s+()\[\]./%\-~,]', '', title).strip()
            title = re.sub(r'\s+', ' ', title)
            if not title or len(title) < 2 or title in seen_titles or title in ["비교", "신청하기", "상세보기", "더보기"]:
                continue
            seen_titles.add(title)

            # 1. 명시적 정상가/할인가 태그 탐색 (.origin, del 등)
            origin_el = el.select_one(".origin, del, s, strike, .before_price, .orig_price, .normal_price, .org_p")
            disc_el = el.select_one(".discount, .now, .sale, .sale_price, .current_price, .current_p")

            explicit_normal = None
            if origin_el:
                m_orig = re.search(r'([\d,]+)\s*원?', origin_el.get_text())
                if m_orig:
                    explicit_normal = int(m_orig.group(1).replace(",", ""))

            explicit_disc = None
            if disc_el:
                m_disc = re.search(r'([\d,]+)\s*원?', disc_el.get_text())
                if m_disc:
                    explicit_disc = int(m_disc.group(1).replace(",", ""))

            # 2. 가격 추출 (.price 클래스 영역 우선 탐색 후 fallback)
            price_el = el.select_one(".price, .fee, .pay, .money, .cost")
            price_text = price_el.get_text(" ", strip=True) if price_el else txt
            prices = re.findall(r'(?<![\d.,])(\d[\d,]*)(?![\d.,])\s*원', price_text)
            # 메뉴·쿠폰·실체감 가격을 월 납부액으로 해석하지 않는다.
            if price_el is None and disc_el is None:
                continue
            if explicit_disc is None and not prices:
                continue

            # 0원 및 10원 등 초저가 프로모션 요금제도 유효 가격으로 수집
            numeric_prices = [int(p.replace(",", "")) for p in prices if 0 <= int(p.replace(",", "")) <= 300000]
            discount_price = explicit_disc if explicit_disc is not None else (min(numeric_prices) if numeric_prices else 0)
            normal_price = explicit_normal if explicit_normal is not None else (max(numeric_prices) if numeric_prices else discount_price)

            network_type = "5G" if "5G" in txt.upper() or "5G" in title.upper() else "LTE"

            month_match = re.search(r'(\d+)\s*개월\s*(?:이후|차부터|할인|간)', txt)
            if month_match:
                discount_months = int(month_match.group(1))
            else:
                # 할인 기간 파싱 실패 시 기본값 설정
                if normal_price == discount_price:
                    discount_months = -1 if "평생" in txt else 0
                else:
                    if "평생" in txt:
                        discount_months = -1
                    else:
                        continue

            # 3. 할인 기간이 명시되어 있는데 정상가격이 누락된 경우, 상세 링크 방문하여 정상가 보완
            if discount_months > 0 and normal_price == discount_price:
                link_el = el if el.name == "a" and el.get("href") else (el.select_one("a[href]") or el.find_parent("a", href=True))
                if link_el and link_el.get("href"):
                    detail_url = urljoin(page_url, link_el["href"])
                    if any(k in detail_url.lower() for k in ["view", "detail", "prod", "plan"]):
                        fetched_normal = self._fetch_normal_price_from_detail(detail_url)
                        if fetched_normal and fetched_normal > discount_price:
                            normal_price = fetched_normal

            # 유한 할인인데 정상가를 확인하지 못한 상품을 싼 고정 요금으로 노출하지 않는다.
            if discount_months > 0 and normal_price == discount_price and explicit_normal is None:
                self.failed_telecom_names.add(telecom_name)
                self._official_errors[telecom_name] = '유한 할인 상품 정상가 확인 실패'
                continue

            raw_text = f"[공식몰] {title} | {txt} | 망: {default_network} [출처: {telecom_name} 공식홈페이지] [월요금 요소 검증]"

            plans.append({
                "telecom_name": telecom_name,
                "title": f"[공식몰] {title}",
                "network_type": network_type,
                "discount_price": discount_price,
                "normal_price": normal_price,
                "discount_months": discount_months,
                "raw_text": raw_text
            })

        return plans

    def _crawl_freet_direct(self, telecom_name: str) -> List[Dict[str, Any]]:
        """프리티(freeT) 공식몰 직접 크롤링 (전수 수집)"""
        plans = []
        try:
            page_no = 1
            while True:
                url = f"https://api.freet.co.kr/plan/v1/list?pageNo={page_no}&rowSize=50"
                resp = requests.get(url, headers={"User-Agent": self.HEADERS["User-Agent"], "Referer": "https://www.freet.co.kr/plan/ratePlan"}, timeout=10)
                if resp.status_code != 200:
                    break

                data = resp.json().get("data", {})
                rate_plans = data.get("ratePlans", [])
                total_count = data.get("totalCount", 0)

                if not rate_plans:
                    break

                for item in rate_plans:
                    title = (item.get("svcName") or item.get("ratePlanName") or "프리티 요금제").strip()
                    com_type = item.get("comType", "")
                    network_carrier = {"freeS": "SKT", "freeK": "KT", "freeL": "LGU+"}.get(com_type, "기타")
                    gen_cd = str(item.get("genCd", "LTE")).upper()
                    network_type = "5G" if "5G" in gen_cd or "5G" in title.upper() else "LTE"

                    discount_price = int(item.get("monthlyFee") or item.get("salePrice") or item.get("basicFee") or 0)
                    normal_price = int(item.get("basicFee") or discount_price)

                    # 가격 동일시 lifetime deal (-1) 감지
                    is_lifetime = (normal_price == discount_price)

                    period_disc_month_str = item.get("periodDiscMonth")
                    if period_disc_month_str:
                        discount_months = int(period_disc_month_str)
                    else:
                        if is_lifetime:
                            discount_months = -1  # Lifetime discount
                        else:
                            discount_months = 12

                    free_data = item.get("freeData") or ""
                    free_voice = item.get("freeVoice") or ""
                    free_sms = item.get("freeSms") or ""
                    qos_info = item.get("qos") or ""

                    raw_text = f"[공식몰] {title} | 데이터 {free_data} | QoS {qos_info} | 음성 {free_voice} | 문자 {free_sms} | 망: {network_carrier} [출처: 프리티 공식홈페이지]"

                    plans.append({
                        "telecom_name": "프리티",
                        "title": f"[공식몰] {title}",
                        "network_type": network_type,
                        "discount_price": discount_price,
                        "normal_price": normal_price,
                        "discount_months": discount_months,
                        "raw_text": raw_text
                    })

                if len(plans) >= total_count or len(rate_plans) == 0:
                    break
                page_no += 1
                time.sleep(0.1)

        except Exception as e:
            print(f"[DirectTelecomCrawler] 프리티 수집 오류: {e}")

        return plans

    def _crawl_eyagi_direct(self, telecom_name: str) -> List[Dict[str, Any]]:
        """이야기모바일(큰사람커넥트) 공식몰 웹 직접 크롤링"""
        plans = []
        seen_titles = set()
        badge_words = {"KT", "SKT", "LGU+", "LGT", "인기", "갓성비", "MD추천", "추천", "인터넷 결합", "안심무약정", "선불", "후불", "평생 할인", "평생할인", "비교", "신청하기"}

        tags = ["pick", "skt", "kt", "lgt", "20", "21", "22", "31"]
        try:
            for tag in tags:
                url = f"https://www.eyagi.co.kr/shop/plan/list.php?tag={tag}"
                resp = requests.get(url, headers=self.HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                for card in soup.select(".plan-card-body"):
                    txt = card.get_text(separator=" | ", strip=True)
                    clean_txt = re.sub(r"\s+", " ", txt).strip()
                    if re.search(r"종량제|쓴\s*만큼\s*과금|원\s*/\s*(?:MB|GB|분|건)", clean_txt, re.IGNORECASE):
                        continue

                    tokens = [t.strip() for t in clean_txt.split("|") if t.strip()]
                    title = ""
                    for token in tokens:
                        if token in badge_words or len(token) < 2 or any(u in token for u in ["원", "GB", "Mbps", "분", "건", "혜택", "할인"]):
                            continue
                        title = token
                        break

                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)

                    network_carrier = "LGU+"
                    if "SKT" in clean_txt:
                        network_carrier = "SKT"
                    elif "KT" in clean_txt:
                        network_carrier = "KT"

                    network_type = "5G" if "5G" in clean_txt.upper() or "5G" in title.upper() else "LTE"

                    prices = re.findall(r'(?<![\d.,])(\d[\d,]*)(?![\d.,])\s*원', clean_txt)
                    numeric_prices = [int(p.replace(",", "")) for p in prices if 0 <= int(p.replace(",", "")) <= 300000]
                    if not numeric_prices:
                        continue
                    discount_price = min(numeric_prices)
                    normal_price = max(numeric_prices) if numeric_prices else discount_price

                    month_match = re.search(r'(\d+)\s*개월\s*이후', clean_txt)
                    discount_months = int(month_match.group(1)) if month_match else 12
                    # 파싱 실패 시 가격 동일 체크 (lifetime deal 감지)
                    if not month_match and normal_price == discount_price:
                        discount_months = -1  # Lifetime discount

                    raw_text = f"[공식몰] {title} | 망: {network_carrier} | {clean_txt} [출처: 이야기모바일 공식홈페이지]"

                    plans.append({
                        "telecom_name": "이야기모바일",
                        "title": f"[공식몰] {title}",
                        "network_type": network_type,
                        "discount_price": discount_price,
                        "normal_price": normal_price,
                        "discount_months": discount_months,
                        "raw_text": raw_text
                    })
                time.sleep(0.1)

        except Exception as e:
            print(f"[DirectTelecomCrawler] 이야기모바일 수집 오류: {e}")

        return plans

    def _crawl_mobing_direct(self, telecom_name: str, home_url: str) -> List[Dict[str, Any]]:
        """유니컴즈(모빙) 공식몰 직접 크롤링"""
        plans = []
        try:
            url = "https://www.mobing.co.kr/plan/list"
            resp = requests.get(url, headers=self.HEADERS, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select(".plan-box, .plan_box, .plan-item, li[class*='plan']")
                for card in cards:
                    txt = re.sub(r"\s+", " ", card.get_text(" ", strip=True)).strip()
                    title_el = card.select_one(".tit, strong, h3, .name")
                    if title_el:
                        title = title_el.get_text(strip=True)
                        # 가격 전용 요소가 없는 카드는 수집하지 않는다.
                        price_el = card.select_one(".price, .fee, .pay, .money, .cost")
                        if price_el is None:
                            continue
                        prices = re.findall(r'(?<![\d.,])(\d[\d,]*)(?![\d.,])\s*원', price_el.get_text(" ", strip=True))
                        if not prices:
                            continue
                        amounts = [int(value.replace(",", "")) for value in prices]
                        plans.append({
                            "telecom_name": "유니컴즈",
                            "title": f"[공식몰] {title}",
                            "network_type": "5G" if "5G" in title.upper() else "LTE",
                            "discount_price": min(amounts),
                            "normal_price": max(amounts),
                            "discount_months": 12,
                            "raw_text": f"[공식몰] {title} | {txt} [출처: 모빙 공식홈페이지]"
                        })
        except Exception as e:
            print(f"[DirectTelecomCrawler] 모빙 수집 오류: {e}")

        return plans

    def _crawl_brand_hub_page(self, telecom_name: str, brand_plan_url: str) -> List[Dict[str, Any]]:
        """알뜰폰허브 내 브랜드 전용 요금제 페이지(/brand/plan/{id}.do) 크롤링"""
        plans = []
        try:
            resp = requests.get(brand_plan_url, headers=self.HEADERS, timeout=self.timeout)
            if resp.status_code != 200:
                self._official_errors[telecom_name] = f'HTTP {resp.status_code}'
                return plans

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".plan_card")

            for card in cards:
                tit_tag = card.select_one("p.tit")
                if not tit_tag:
                    continue
                title = re.sub(r"\s+", " ", tit_tag.get("title") or tit_tag.get_text()).strip()

                posi_lis = card.select(".posi ul li")
                network_carrier = posi_lis[0].get_text(strip=True) if len(posi_lis) > 0 else "기타"
                brand_name = posi_lis[1].get_text(strip=True) if len(posi_lis) > 1 else telecom_name

                network_type = "5G" if "5G" in title.upper() else "LTE"

                now_price_tag = card.select_one(".price p.now span")
                price_digits = re.sub(r"[^\d]", "", now_price_tag.get_text()) if now_price_tag else ""
                if not price_digits:
                    continue
                discount_price = int(price_digits)

                normal_price = discount_price
                after_price_tag = card.select_one(".time_after span")
                ex_price_tag = card.select_one(".price p.ex span")
                if after_price_tag:
                    digits = re.sub(r"[^\d]", "", after_price_tag.get_text())
                    if digits:
                        normal_price = int(digits)
                elif ex_price_tag:
                    digits = re.sub(r"[^\d]", "", ex_price_tag.get_text())
                    if digits:
                        normal_price = int(digits)

                discount_months = 12
                # 할인 기간 파싱 전: 가격 동일시 lifetime deal (-1) 감지
                if normal_price == discount_price:
                    discount_months = -1  # Lifetime discount
                else:
                    discount_months = 12
                time_after_tag = card.select_one(".time_after")
                if time_after_tag:
                    m = re.search(r"(\d+)\s*개월", time_after_tag.get_text())
                    if m:
                        discount_months = int(m.group(1))

                lifetime = MvnohubCrawler.lifetime_prices(card, discount_price)
                if lifetime:
                    normal_price, discount_months = lifetime
                data_after = card.get("data-data-after", "")
                spec_parts = [title]
                for cls in ["wifi", "call", "mes", "book"]:
                    li = card.select_one(f".dtl li.{cls}")
                    if li:
                        t = re.sub(r"\s+", " ", li.get_text()).strip()
                        if t:
                            spec_parts.append(t)
                if data_after and data_after not in ("0", ""):
                    spec_parts.append(f"소진후 {data_after}")
                spec_parts.append(f"망: {network_carrier}")

                raw_text = " | ".join(spec_parts) + f" [출처: {brand_name} 브랜드전용관]"

                plans.append({
                    "telecom_name": brand_name,
                    "title": f"[브랜드특가] {title}",
                    "network_type": network_type,
                    "discount_price": discount_price,
                    "normal_price": normal_price,
                    "discount_months": discount_months,
                    "raw_text": raw_text
                })

        except Exception as e:
            print(f"[DirectTelecomCrawler] '{telecom_name}' 브랜드 요금제 페이지 크롤링 오류: {e}")

        return plans
