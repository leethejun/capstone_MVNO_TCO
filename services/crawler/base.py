from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseCrawler(ABC):
    """
    알뜰폰 요금제 크롤러 기본 인터페이스[cite: 1]
    """

    @abstractmethod
    def fetch_raw_plans(self) -> List[Dict[str, Any]]:
        """
        웹사이트에서 요금제 원시(raw) 데이터를 스크래핑하여 반환합니다.
        
        반환 형태 (각 dict):
        {
            "telecom_name": str,       # 통신사명 (예: "고고팩토리", "프리티")
            "title": str,              # 요금제명 (예: "KT망 5G 요금제 초저가 모음")
            "network_type": str,       # 망 종류 ("LTE", "5G" 등)
            "discount_price": int,     # 프로모션 할인 요금
            "normal_price": int,       # 프로모션 종료 후 정상 요금
            "discount_months": int,    # 할인 제공 개월 수
            "raw_text": str            # 스펙 및 비정형 텍스트 (예: "15GB+3Mbps 음성200분 문자100건")
        }
        """
        pass
