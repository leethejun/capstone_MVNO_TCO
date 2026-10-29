"""코인샷 모바일 공식 API: 선불 9종 수집. 종량제는 기본료만 확인 가능."""
import requests
from services.crawler.structured_official import record


class CoinshotCrawler:
    URL = "https://mobile.coinshot.org/api/mvno-plan"

    def __init__(self):
        self.skipped = []

    def fetch_raw_plans(self):
        response = requests.get(
            self.URL,
            params={"page": 1, "size": 100, "recommend": "false"},
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("list"), list):
            raise ValueError("코인샷 공식 API 응답 형식 변경")
        if int(payload.get("maxPage", 1)) > 1:
            raise ValueError("코인샷 요금제 페이지가 2페이지 이상: 누락 방지를 위해 수집 중단")
        plans = []
        for item in payload["list"]:
            name = str(item.get("name") or "").strip()
            if not name or item.get("openable") is not True or item.get("prePostDiv") != "PRE":
                continue
            try:
                price = int(item["base"])
                if price <= 0:
                    raise ValueError("기본요금 누락")
                details = item.get("details") or {}
                data = str(details.get("dataText") or "").strip()
                voice = str(details.get("voiceText") or "").strip()
                sms = str(details.get("smsText") or "").strip()
                if not data or not voice or not sms:
                    raise ValueError("제공량 상세 누락")
                mno = str(item.get("mno") or "").upper()
                network = {"LG": "LG U+", "KT": "KT", "SK": "SKT"}.get(mno)
                if not network:
                    raise ValueError("통신망 확인 불가")
                usage = item.get("type") == "USAGE"
                # 종량제는 API base가 확정 월 청구액이 아니라 기본료다.
                # 화면에서 반드시 구분되도록 제목과 원문에 명시한다.
                if usage:
                    display_name = f"{name} (종량제·기본료 {price:,}원부터, 사용량 별도)"
                    data = f"종량제 {data}"
                    voice = f"종량제 {voice}"
                    sms = f"종량제 {sms}"
                else:
                    display_name = name
                plan = record("코인샷 모바일", display_name, price, price, 0,
                              data, voice, sms, network, str(item.get("code") or ""))
                plan["raw_text"] += (" [선불 종량제: 표시 금액은 기본료이며 실제 청구액 및 TCO는 사용량에 따라 증가함]"
                                     if usage else " [선불 정액제]")
                plan["raw_text"] += " [할인 없음] [충전 주기/가입 조건 별도 확인 필요]"
                plans.append(plan)
            except (KeyError, ValueError, TypeError) as exc:
                self.skipped.append(f"{name}({exc})")
        return plans
