import re
import unicodedata
from typing import Dict, Any, Optional

class PlanTextParser:
    """
    비정형 알뜰폰 요금제 텍스트를 수치형 데이터로 변환하는 정규표현식 파서
    전각 문자(＋ 등), 불규칙 공백, 다양한 QoS 표기를 표준 수치로 변환합니다.
    """

    @staticmethod
    def parse(raw_text: str) -> Dict[str, Any]:
        """
        비정형 텍스트를 파싱하여 DB 컬럼에 매핑할 딕셔너리를 반환합니다.

        반환값 구조:
        - base_data_gb: float (월 기본 데이터, GB)
        - daily_data_gb: float (일일 추가 데이터, GB)
        - qos_speed_mbps: float (소진 후 속도 제어, Mbps - 예: 1.0, 3.0, 5.0, 0.4)
        - is_data_unlimited: bool (QoS 속도제어 또는 일일제공이 있어 추가과금 없는 실질 무제한 여부)
        - voice_minutes: int (기본 통화 분, -1은 무제한)
        - sms_count: int (기본 문자 건수, -1은 무제한)
        """
        if not raw_text:
            raw_text = ""

        # 1. 전각 문자(＋, ㎆, ㎇ 등)를 반각 표준 문자로 정규화 (NFKC)
        normalized = unicodedata.normalize("NFKC", raw_text)

        qos = PlanTextParser._extract_qos_speed(normalized)
        daily = PlanTextParser._extract_daily_data(normalized)
        base = PlanTextParser._extract_base_data(normalized)

        # 실질 무제한 여부: QoS 속도제어가 0.4Mbps 이상이거나 일일 데이터가 제공되는 경우
        is_unlimited = (qos > 0.0) or (daily > 0.0)

        # 공백 제거 버전 (음성/문자 추출용)
        compact_text = re.sub(r"\s+", "", normalized)

        return {
            "base_data_gb": base,
            "daily_data_gb": daily,
            "qos_speed_mbps": qos,
            "is_data_unlimited": is_unlimited,
            "voice_minutes": PlanTextParser._extract_voice(compact_text),
            "sms_count": PlanTextParser._extract_sms(compact_text),
            "raw_text": raw_text
        }

    @staticmethod
    def _extract_qos_speed(text: str) -> float:
        """
        QoS 속도제어 수치 추출 (예: '3Mbps', '1Mbps', '5Mbps', '400Kbps', '+3Mbps', '소진시1Mbps')
        """
        # 1. Mbps 추출 (예: 3Mbps, 1.5Mbps, 3 Mbps)
        mbps_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:Mbps|mbps|MBPS|메가)', text)
        if mbps_match:
            return round(float(mbps_match.group(1)), 1)

        # 2. Kbps 추출 -> Mbps 환산 (예: 400Kbps -> 0.4Mbps, 200Kbps -> 0.2Mbps)
        kbps_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:Kbps|kbps|KBPS|킬로)', text)
        if kbps_match:
            return round(float(kbps_match.group(1)) / 1000.0, 1)

        # 3. '+숫자M' 형태 (예: 11GB+3M)
        plus_m_match = re.search(r'\+\s*(\d+(?:\.\d+)?)\s*M(?:bps)?', text, re.IGNORECASE)
        if plus_m_match:
            return round(float(plus_m_match.group(1)), 1)

        # 4. '속도제어', 'QoS' 키워드 뒤 숫자 매칭
        qos_keyword_match = re.search(r'(?:qos|속도제어|소진시|안심)\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if qos_keyword_match:
            val = float(qos_keyword_match.group(1))
            if val >= 100:  # 400 등은 Kbps 단위
                return round(val / 1000.0, 1)
            return round(val, 1)

        return 0.0

    @staticmethod
    def _extract_daily_data(text: str) -> float:
        """
        일일 추가 데이터 추출 (예: '일2GB', '매일1GB', '일500MB', '하루2GB')
        '모바일 10GB' 등에서 끝글자 '일'에 오매칭되지 않도록 Negative Lookbehind 적용
        """
        pattern = r'(?<![가-힣])(?:일|매일|하루|일일)\s*(\d+(?:\.\d+)?)\s*(GB|MB|기가|메가)'
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            return 0.0

        unit = match.group(2).upper()
        value = float(match.group(1))

        if unit in ['MB', '메가']:
            return round(value / 1000.0, 1)
        return round(value, 1)

    @staticmethod
    def _extract_base_data(text: str) -> float:
        """월 기본 제공 데이터 추출 (일일 데이터 및 QoS 속도제어 제외)"""
        # 일일 데이터(일2GB 등)나 속도제한(3Mbps 등)을 임시 마스킹
        cleaned = re.sub(r'(?<![가-힣])(?:일|매일|하루|일일)\s*\d+(?:\.\d+)?\s*(?:GB|MB|기가|메가)', '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'\d+(?:\.\d+)?\s*(?:Mbps|Kbps|mbps|kbps)', '', cleaned, flags=re.IGNORECASE)

        # 1. GB 단위 추출
        gb_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:GB|기가)', cleaned, re.IGNORECASE)
        if gb_match:
            return round(float(gb_match.group(1)), 1)

        # 2. MB 단위 추출 -> GB 환산
        mb_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:MB|메가)', cleaned, re.IGNORECASE)
        if mb_match:
            return round(float(mb_match.group(1)) / 1000.0, 1)

        return 0.0

    @staticmethod
    def _extract_voice(text: str) -> int:
        """통화량 추출 (무제한/기본제공 = -1, 지정 분수 = 숫자)"""
        if re.search(r'(?:음성|통화|집/이동전화)(?:무제한|기본제공|무제한/|기본)', text):
            return -1

        voice_match = re.search(r'(?:음성|통화)?(\d+)분', text)
        if voice_match:
            return int(voice_match.group(1))

        return 0

    @staticmethod
    def _extract_sms(text: str) -> int:
        """문자량 추출 (무제한/기본제공 = -1, 지정 건수 = 숫자)"""
        if re.search(r'(?:문자|SMS)(?:무제한|기본제공|기본)', text):
            return -1

        sms_match = re.search(r'(?:문자|SMS)?(\d+)건', text)
        if sms_match:
            return int(sms_match.group(1))

        return 0
