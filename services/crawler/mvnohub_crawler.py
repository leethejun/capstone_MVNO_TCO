import re
import time
import unicodedata
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Set
from services.crawler.base import BaseCrawler


class MvnohubCrawler(BaseCrawler):
    """
    알뜰폰허브(mvnohub.kr) 전 요금제 전수 크롤러

    사이트 구조:
    - 상단: .rank_set 영역 (허브 추천 요금제 ~100건, 모든 페이지에서 동일)
    - 하단: .list_plan_set 영역 (페이징 리스트, 페이지당 ~12건, 총 69+페이지)
    - 페이지네이션: products.do?page=N (0-indexed)
    
    이 크롤러는:
    1. 첫 페이지에서 추천 영역(.rank_set) 요금제를 한 번만 수집
    2. 모든 페이지에서 리스트 영역(.list_plan_set) 요금제를 수집
    3. data-product-id 기준으로 중복 제거
    """
    BASE_URL = "https://www.mvnohub.kr/product/products.do"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def __init__(self, timeout: int = 20, delay_sec: float = 0.5):
        self.timeout = timeout
        self.delay_sec = delay_sec

    def fetch_raw_plans(self, max_pages: int = 0) -> List[Dict[str, Any]]:
        """
        알뜰폰허브의 요금제 목록을 전수 수집합니다.
        :param max_pages: 수집할 최대 페이지 수 (0이면 전체 전수 수집)
        :return: 중복 제거된 요금제 딕셔너리 리스트
        """
        results: List[Dict[str, Any]] = []
        seen_product_ids: Set[str] = set()
        page = 0
        total_pages = 1  # 최소 1페이지
        rank_collected = False
        consecutive_empty = 0

        print(f"[MvnohubCrawler] 알뜰폰허브 전수 크롤링 시작 (max_pages={max_pages}, 0=전체)")

        while True:
            # 종료 조건
            if max_pages > 0 and page >= max_pages:
                print(f"[MvnohubCrawler] max_pages={max_pages} 도달, 순회 종료")
                break
            if page >= total_pages and page > 0:
                print(f"[MvnohubCrawler] 마지막 페이지({total_pages}) 도달, 순회 종료")
                break
            if consecutive_empty >= 3:
                print(f"[MvnohubCrawler] 연속 3페이지 빈 결과, 순회 종료")
                break

            url = f"{self.BASE_URL}?page={page}"
            try:
                resp = requests.get(url, headers=self.HEADERS, timeout=self.timeout)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                # 첫 페이지에서 총 페이지 수 파악
                if page == 0:
                    total_pages = self._discover_total_pages(soup)
                    print(f"[MvnohubCrawler] 총 {total_pages}개 페이지 발견")

                page_new_count = 0

                # 1. 추천 영역 (rank_set) - 첫 페이지에서만 한 번 수집
                if not rank_collected:
                    rank_section = soup.select_one(".rank_set")
                    if rank_section:
                        rank_cards = rank_section.select(".plan_card")
                        for card in rank_cards:
                            plan_data = self._parse_card(card)
                            if plan_data and plan_data.get("_product_id"):
                                pid = plan_data["_product_id"]
                                if pid not in seen_product_ids:
                                    seen_product_ids.add(pid)
                                    results.append(plan_data)
                                    page_new_count += 1
                        print(f"[MvnohubCrawler] 추천 영역에서 {len(rank_cards)}개 카드, {page_new_count}개 신규 수집")
                    rank_collected = True

                # 2. 리스트 영역 (list_plan_set) - 매 페이지 수집
                list_section = soup.select_one(".list_plan_set")
                list_new = 0
                if list_section:
                    list_cards = list_section.select(".plan_card")
                    for card in list_cards:
                        try:
                            plan_data = self._parse_card(card)
                            if plan_data and plan_data.get("_product_id"):
                                pid = plan_data["_product_id"]
                                if pid not in seen_product_ids:
                                    seen_product_ids.add(pid)
                                    results.append(plan_data)
                                    list_new += 1
                        except Exception as e:
                            print(f"[MvnohubCrawler] 카드 파싱 오류: {e}")
                            continue

                    if list_new == 0 and len(list_cards) == 0:
                        consecutive_empty += 1
                    else:
                        consecutive_empty = 0

                    print(f"[MvnohubCrawler] 페이지 {page+1}/{total_pages}: "
                          f"리스트 {len(list_cards)}개 카드, {list_new}개 신규 (누적 {len(results)}건)")
                else:
                    # list_plan_set이 없으면 fallback: 전체 plan_card 수집
                    all_cards = soup.select(".plan_card")
                    for card in all_cards:
                        try:
                            plan_data = self._parse_card(card)
                            if plan_data and plan_data.get("_product_id"):
                                pid = plan_data["_product_id"]
                                if pid not in seen_product_ids:
                                    seen_product_ids.add(pid)
                                    results.append(plan_data)
                                    list_new += 1
                        except Exception as e:
                            continue

                    if list_new == 0:
                        consecutive_empty += 1
                    else:
                        consecutive_empty = 0

                    print(f"[MvnohubCrawler] 페이지 {page+1}/{total_pages} (fallback): "
                          f"{len(all_cards)}개 카드, {list_new}개 신규 (누적 {len(results)}건)")

                page += 1

                if self.delay_sec > 0:
                    time.sleep(self.delay_sec)

            except requests.exceptions.RequestException as e:
                print(f"[MvnohubCrawler] 페이지 {page} 네트워크 오류: {e}")
                consecutive_empty += 1
                page += 1
                time.sleep(self.delay_sec * 2)
                continue
            except Exception as e:
                print(f"[MvnohubCrawler] 페이지 {page} 파싱 오류: {e}")
                page += 1
                continue

        # _product_id 필드 제거 (내부 용도)
        for plan in results:
            plan.pop("_product_id", None)

        print(f"[MvnohubCrawler] ✅ 전수 크롤링 완료: 총 {len(results)}건 (중복 제거), "
              f"{len(seen_product_ids)}개 고유 상품ID, {page}페이지 수집")
        return results

    def _discover_total_pages(self, soup) -> int:
        """페이지네이션에서 총 페이지 수 추출"""
        # 방법 1: pagination 버튼에서 최대 data-page 추출
        page_buttons = soup.select(".pagination button[data-page]")
        pages = []
        for btn in page_buttons:
            dp = btn.get("data-page", "")
            if dp.isdigit():
                pages.append(int(dp))

        if pages:
            max_page = max(pages)
            return max_page + 1  # 0-indexed이므로 +1

        # 방법 2: 숫자 버튼에서 마지막 번호 추출
        num_buttons = soup.select(".pagination button.num")
        max_num = 1
        for btn in num_buttons:
            text = btn.get_text(strip=True)
            if text.isdigit():
                max_num = max(max_num, int(text))
        return max_num

    def _clean_text(self, text: str) -> str:
        """전각 문자를 반각으로 정규화하고 중복 공백/개행 제거"""
        if not text:
            return ""
        norm = unicodedata.normalize("NFKC", text)
        return re.sub(r"\s+", " ", norm).strip()

    def _parse_card(self, card) -> Dict[str, Any]:
        """요금제 카드 HTML에서 정보 추출"""
        # 0. 상품 고유 ID
        product_id = card.get("data-product-id", "")
        if not product_id:
            return None

        # 1. 요금제명
        tit_tag = card.select_one("p.tit")
        if not tit_tag:
            return None
        title = self._clean_text(tit_tag.get("title") or tit_tag.get_text())

        # 2. 통신망 및 통신사
        posi_lis = card.select(".posi ul li")
        network_carrier = self._clean_text(posi_lis[0].get_text()) if len(posi_lis) > 0 else "기타"
        telecom_name = self._clean_text(posi_lis[1].get_text()) if len(posi_lis) > 1 else network_carrier

        # 3. 네트워크 타입 (5G or LTE)
        tips = card.select(".tips span")
        tips_text = " ".join(self._clean_text(t.get_text()) for t in tips)
        if "5G" in title.upper() or "5G" in network_carrier.upper() or "5G" in tips_text.upper():
            network_type = "5G"
        else:
            network_type = "LTE"

        # 4. 할인 요금 (현재 월 납부액)
        discount_price = 0
        now_price_tag = card.select_one(".price p.now span")
        if now_price_tag:
            price_digits = re.sub(r"[^\d]", "", now_price_tag.get_text())
            if price_digits:
                discount_price = int(price_digits)

        if now_price_tag is None or not price_digits:
            return None

        # 5. 정상 요금
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

        # 6. 할인 개월수
        discount_months = 12  # 기본값
        time_after_tag = card.select_one(".time_after")
        if time_after_tag:
            after_text = time_after_tag.get_text()
            month_match = re.search(r"(\d+)\s*개월", after_text)
            if month_match:
                discount_months = int(month_match.group(1))

        # 7. QoS 속도 (data-data-after 속성에서도 추출)
        data_after = card.get("data-data-after", "")

        # 8. 비정형 스펙 텍스트 조합
        spec_parts = [title]

        # WiFi/데이터 스펙
        wifi_li = card.select_one(".dtl li.wifi")
        if wifi_li:
            wifi_txt = self._clean_text(wifi_li.get_text())
            if wifi_txt:
                spec_parts.append(wifi_txt)

        # 통화 스펙
        call_li = card.select_one(".dtl li.call")
        if call_li:
            call_txt = self._clean_text(call_li.get_text())
            if call_txt:
                spec_parts.append(call_txt)

        # 문자 스펙
        mes_li = card.select_one(".dtl li.mes")
        if mes_li:
            mes_txt = self._clean_text(mes_li.get_text())
            if mes_txt:
                spec_parts.append(mes_txt)

        # 부가 혜택
        book_li = card.select_one(".dtl li.book")
        if book_li:
            book_txt = self._clean_text(book_li.get_text())
            if book_txt:
                spec_parts.append(book_txt)

        # data-data-after 속성의 QoS 정보 추가
        if data_after and data_after not in ("0", ""):
            spec_parts.append(f"소진후 {data_after}")

        # 네트워크 캐리어 정보 추가
        spec_parts.append(f"망: {network_carrier}")

        raw_text = " | ".join(spec_parts)

        return {
            "_product_id": product_id,
            "telecom_name": telecom_name,
            "title": title,
            "network_type": network_type,
            "discount_price": discount_price,
            "normal_price": normal_price,
            "discount_months": discount_months,
            "raw_text": f"{raw_text} [출처: 알뜰폰허브]"
        }
