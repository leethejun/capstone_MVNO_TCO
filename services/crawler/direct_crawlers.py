import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict, Any, Set, Tuple
from services.crawler.base import BaseCrawler


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

    def fetch_raw_plans(self) -> List[Dict[str, Any]]:
        """
        알뜰폰허브에 등록된 모든 사업자 목록을 파악하고,
        각 공식 홈페이지 및 브랜드 전용 페이지를 직접 순회하여 요금제를 수집합니다.
        """
        all_plans: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple[str, str]] = set()

        # Step 1: 알뜰폰허브에서 모든 입점 사업자 목록과 공식 홈페이지 URL 수집
        brands = self.discover_all_mvno_brands()
        print(f"[DirectTelecomCrawler] 알뜰폰허브에서 {len(brands)}개 사업자(브랜드) 발견 완료")

        # Step 2: 각 사업자의 공식 홈페이지 및 브랜드 전용 요금제 페이지를 직접 방문
        for i, brand in enumerate(brands, 1):
            name = brand["name"]
            home_url = brand["home_url"]
            brand_plan_url = brand["brand_plan_url"]
            network = brand.get("network", "")

            print(f"[DirectTelecomCrawler] [{i}/{len(brands)}] '{name}' 공식몰 직접 크롤링 시작 ({home_url})")

            # 2-A: 공식 홈페이지 직접 방문 크롤링
            official_plans = self._crawl_brand_official_site(name, home_url, network)
            added_official = 0
            for p in official_plans:
                key = (p["telecom_name"], p["title"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_plans.append(p)
                    added_official += 1

            # 2-B: 허브 내 브랜드 전용 요금제 페이지 크롤링
            if brand_plan_url:
                hub_brand_plans = self._crawl_brand_hub_page(name, brand_plan_url)
                added_hub = 0
                for p in hub_brand_plans:
                    key = (p["telecom_name"], p["title"])
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_plans.append(p)
                        added_hub += 1

            print(f"[DirectTelecomCrawler] '{name}' 수집 완료 (공식몰: {added_official}건, 브랜드특가: {added_hub if brand_plan_url else 0}건)")

            if self.delay_sec > 0:
                time.sleep(self.delay_sec)

        print(f"[DirectTelecomCrawler] ✅ 모든 개별 사업자 직접 크롤링 완료: 총 {len(all_plans)}건 요금제 수집")
        return all_plans

    def discover_all_mvno_brands(self) -> List[Dict[str, str]]:
        """알뜰폰허브 brand.do를 크롤링하여 전체 사업자 목록 및 공식 홈페이지 추출"""
        brands = []
        try:
            resp = requests.get(self.BRAND_LIST_URL, headers=self.HEADERS, timeout=self.timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

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
        if not home_url or not home_url.startswith("http"):
            return plans

        # 1. 특화 크롤러가 있는 주요 사업자
        clean_name = telecom_name.replace(" ", "")
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
                return plans

            soup = BeautifulSoup(resp.text, "html.parser")

            # 메인 페이지 및 요금제 링크 탐색
            plan_urls = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                txt = a.get_text(strip=True)
                if any(k in href.lower() for k in ["/plan", "/rate", "/charge", "plan_list", "charge_list"]) or any(k in txt for k in ["요금제", "요금제 안내"]):
                    full = urljoin(home_url, href)
                    if full.startswith(home_url):
                        plan_urls.add(full)

            # 방문할 URL 목록: 메인 + 최대 2개 요금제 페이지
            targets = [home_url] + list(plan_urls)[:2]

            for target_url in targets:
                try:
                    r = requests.get(target_url, headers=self.HEADERS, timeout=self.timeout)
                    if r.status_code != 200:
                        continue
                    p_soup = BeautifulSoup(r.text, "html.parser")
                    extracted = self._extract_plans_from_html(telecom_name, p_soup, target_url, default_network)
                    plans.extend(extracted)
                except Exception:
                    continue

        except Exception as e:
            print(f"[DirectTelecomCrawler] '{telecom_name}' 공식몰({home_url}) 크롤링 중 오류: {e}")

        return plans

    def _extract_plans_from_html(self, telecom_name: str, soup: BeautifulSoup, page_url: str, default_network: str) -> List[Dict[str, Any]]:
        """일반 웹페이지 HTML에서 요금제 패턴(카드, 박스, 리스트)을 직접 추출"""
        plans = []
        seen_titles = set()

        # 요금제 카드로 추정되는 컨테이너 셀렉터
        candidate_selectors = [
            ".plan-card, .plan_card, .plan-item, .plan_item, .plan_box, .plan-box",
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

        # 후보 태그가 없으면 데이터/가격이 포함된 블록 탐색
        if not elements:
            for div in soup.find_all(["div", "li"], class_=True):
                text = div.get_text(" ", strip=True)
                if ("GB" in text or "MB" in text) and "원" in text and len(text) < 300:
                    elements.append(div)

        for el in elements:
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
            if not ("원" in txt and ("GB" in txt or "MB" in txt or "통화" in txt)):
                continue

            # 요금제명 추출
            title_el = el.select_one(".tit, .title, strong, h3, h4, .name")
            if title_el:
                title = title_el.get_text(strip=True)
            else:
                m = re.search(r'([A-Za-z0-9가-힣+]{2,15}(?:\s+[A-Za-z0-9가-힣+]{1,10}){1,3})', txt)
                title = m.group(1) if m else f"{telecom_name} 알뜰요금제"

            title = re.sub(r'[^\w\s+()\[\]-]', '', title).strip()
            if not title or len(title) < 2 or title in seen_titles or title in ["비교", "신청하기", "상세보기", "더보기"]:
                continue
            seen_titles.add(title)

            # 가격 추출
            prices = re.findall(r'([\d,]+)\s*원', txt)
            numeric_prices = [int(p.replace(",", "")) for p in prices if 100 <= int(p.replace(",", "")) <= 200000]
            discount_price = min(numeric_prices) if numeric_prices else 0
            normal_price = max(numeric_prices) if numeric_prices else discount_price

            network_type = "5G" if "5G" in txt.upper() or "5G" in title.upper() else "LTE"

            month_match = re.search(r'(\d+)\s*개월', txt)
            if month_match:
                discount_months = int(month_match.group(1))
            else:
                # 할인 기간 파싱 실패 시 기본값 설정
                # 가격 동일시 lifetime deal (-1) 이 아닌 경우에만 기본값 12 적용
                if normal_price == discount_price:
                    discount_months = -1  # Lifetime discount (가격 변동 없음)
                else:
                    discount_months = 12

            raw_text = f"[공식몰] {title} | {txt} | 망: {default_network} [출처: {telecom_name} 공식홈페이지]"

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

                    prices = re.findall(r'([\d,]+)\s*원', clean_txt)
                    numeric_prices = [int(p.replace(",", "")) for p in prices if 100 <= int(p.replace(",", "")) <= 200000]
                    discount_price = min(numeric_prices) if numeric_prices else 0
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
                        plans.append({
                            "telecom_name": "유니컴즈",
                            "title": f"[공식몰] {title}",
                            "network_type": "LTE",
                            "discount_price": 0,
                            "normal_price": 0,
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
                discount_price = int(re.sub(r"[^\d]", "", now_price_tag.get_text())) if now_price_tag else 0

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
                if time_after_tag:
                    m = re.search(r"(\d+)\s*개월", time_after_tag.get_text())
                    if m:
                        discount_months = int(m.group(1))

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
