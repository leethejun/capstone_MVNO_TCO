import re
from urllib.parse import urlparse
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models import Telecom, Plan
from database import SessionLocal

# 수동 관리하는 통신사 마스터. 나무위키 실시간 수집 또는 전체 사업자 보장을 의미하지 않는다.
MASTER_TELECOMS: List[Dict[str, str]] = [
    # 1. 이동통신사 자회사
    {"name": "SK 7mobile", "website_url": "https://www.sk7mobile.com", "network": "SKT"},
    {"name": "KT M모바일", "website_url": "https://www.ktmmobile.com", "network": "KT"},
    {"name": "KT스카이라이프", "website_url": "https://shop.skylife.co.kr", "network": "KT"},
    {"name": "U+유모바일", "website_url": "https://www.uplusumobile.com", "network": "LGU+"},
    {"name": "헬로모바일", "website_url": "https://direct.lghellovision.net", "network": "3사망"},

    # 2. 금융기관 및 대형 플랫폼
    {"name": "KB리브모바일", "website_url": "https://www.liivm.com", "network": "3사망"},
    {"name": "우리WON모바일", "website_url": "https://www.wooriwonmobile.com", "network": "LGU+"},
    {"name": "토스모바일", "website_url": "https://tossmobile.co.kr", "network": "3사망"},
    {"name": "핀다이렉트", "website_url": "https://www.pindirectshop.com", "network": "3사망"},

    # 3. 3사 복수망 지원 중대형 MVNO
    {"name": "프리티", "website_url": "https://www.freet.co.kr", "network": "3사망"},
    {"name": "이야기모바일", "website_url": "https://www.eyagi.co.kr", "network": "3사망"},
    {"name": "모빙", "website_url": "https://www.mobing.co.kr", "network": "3사망"},
    {"name": "아이즈모바일", "website_url": "https://eyes.co.kr", "network": "3사망"},
    {"name": "티플러스", "website_url": "https://www.tplusmobile.com", "network": "3사망"},
    {"name": "스마텔", "website_url": "https://smartel.kr", "network": "3사망"},
    {"name": "A모바일(에넥스텔레콤)", "website_url": "https://www.amobile.co.kr", "network": "3사망"},
    {"name": "에르엘", "website_url": "https://www.erel.co.kr", "network": "3사망"},
    {"name": "이지모바일", "website_url": "https://www.egmobile.co.kr", "network": "3사망"},
    {"name": "스노우맨", "website_url": "https://www.snowman.co.kr", "network": "3사망"},
    {"name": "고고모바일(고고팩토리)", "website_url": "https://www.gogomobile.co.kr", "network": "3사망"},
    {"name": "인스모바일", "website_url": "https://www.insmobile.co.kr", "network": "3사망"},
    {"name": "위너스텔(WELL)", "website_url": "https://www.idowell.co.kr", "network": "3사망"},
    {"name": "아시아모바일", "website_url": "https://asiamobile.kr", "network": "3사망"},
    {"name": "니즈모바일", "website_url": "https://nizmobile.com", "network": "3사망"},
    {"name": "친구모바일", "website_url": "https://chingumobile.com", "network": "3사망"},
    {"name": "에스원 안심모바일", "website_url": "http://www.s1mobile.co.kr", "network": "3사망"},
    {"name": "밸류컴", "website_url": "https://valuecomm.co.kr", "network": "3사망"},
    {"name": "도시락모바일", "website_url": "https://www.dosirakmobile.com", "network": "3사망"},
    {"name": "아정당모바일", "website_url": "https://www.ajd.co.kr/phone/mvno", "network": "3사망"},
    {"name": "플래시모바일", "website_url": "https://www.flashmobile.kr", "network": "3사망"},
    {"name": "코인샷 모바일", "website_url": "https://mobile.coinshot.org", "network": "3사망"},

    # 4. 단일망 및 특화 MVNO
    {"name": "조이텔", "website_url": "https://joytel.co.kr", "network": "SKT"},
    {"name": "알비레오", "website_url": "https://www.albireomobile.com", "network": "SKT"},
    {"name": "쉐이크모바일", "website_url": "https://shakemobile.co.kr", "network": "KT"},
    {"name": "아이디스파워텔", "website_url": "https://idispowertel.com", "network": "KT"},
    {"name": "드림라인 모바일", "website_url": "https://dreammobile.kr", "network": "KT"},
    {"name": "퍼스트 모바일", "website_url": "https://www.firstmobile.co.kr", "network": "KT"},
    {"name": "더원모바일", "website_url": "https://www.theonem.co.kr", "network": "KT"},
    {"name": "한국E텔레콤", "website_url": "https://www.koretel.co.kr", "network": "KT"},
    {"name": "마블링", "website_url": "https://marvelring.com", "network": "LGU+"},
    {"name": "슈가모바일", "website_url": "https://www.sugarmobile.co.kr", "network": "LGU+"},
    {"name": "찬스모바일", "website_url": "https://chancemobile.co.kr", "network": "LGU+"},
    {"name": "MONA", "website_url": "https://mobilemona.co.kr", "network": "LGU+"},
    {"name": "GME모바일", "website_url": "https://www.gmemobile.com", "network": "LGU+"},
    {"name": "한패스모바일", "website_url": "https://www.hanpassmobile.co.kr", "network": "LGU+"},
    {"name": "시월모바일", "website_url": "https://www.siwolmobile.com", "network": "LGU+"},
    {"name": "KCTV모바일", "website_url": "https://kctvm.com", "network": "LGU+"},
    {"name": "KG모바일", "website_url": "https://www.kgmobile.co.kr", "network": "LGU+"},
    {"name": "온국민폰", "website_url": "https://온국민폰.kr", "network": "LGU+"},
    {"name": "토리모바일", "website_url": "https://ntontel.com", "network": "LGU+"},
    {"name": "이음모바일", "website_url": "https://eummobile.co.kr", "network": "LGU+"},
    {"name": "서경모바일", "website_url": "https://www.scsmobile.co.kr", "network": "LGU+"},
    {"name": "여유모바일", "website_url": "https://www.yytelecom.co.kr", "network": "LGU+"},
    {"name": "원텔레콤", "website_url": "https://onetelecom.co.kr", "network": "LGU+"},
]

# 허브 법인명과 공식 브랜드명을 명시적으로 연결한다. 유사 문자열 추측은 하지 않는다.
TELECOM_ALIASES = {
    'KB국민은행': 'KB리브모바일', 'LG헬로모바일': '헬로모바일',
    '에스케이텔링크': 'SK 7mobile', 'KCT (티플러스)': '티플러스',
    '케이티엠모바일': 'KT M모바일', '유니컴즈': '모빙',
    '케이티스카이라이프': 'KT스카이라이프', '큰사람커넥트': '이야기모바일',
    '고고팩토리': '고고모바일(고고팩토리)', '마블프로듀스': '마블링',
    '스테이지파이브': '핀다이렉트', '프리티 (SKT, KT망)': '프리티',
    '프리티 (LGU+망)': '프리티',
}


def canonical_telecom_name(name):
    return TELECOM_ALIASES.get(name.strip(), name.strip())


def sync_telecom_master(db: Session = None, commit: bool = True) -> Dict[str, Any]:
    """
    나무위키 40+개 알뜰폰 통신사 마스터 데이터를 DB telecoms 테이블과 동기화(Upsert)합니다.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    stats = {"total_master": len(MASTER_TELECOMS), "inserted": 0, "updated": 0}

    try:
        for tdata in MASTER_TELECOMS:
            name = tdata["name"]
            url = tdata["website_url"]
            logo = f"https://logo.clearbit.com/{url.replace('https://', '').replace('http://', '').split('/')[0]}"

            # 기존 이름이나 유사 이름 검색 (예: 프리티, A모바일 등)
            existing = db.query(Telecom).filter(Telecom.name == name).first()

            if existing:
                if not existing.website_url:
                    existing.website_url = url
                if not existing.logo_url:
                    existing.logo_url = logo
                stats["updated"] += 1
            else:
                new_t = Telecom(name=name, website_url=url, logo_url=logo)
                db.add(new_t)
                stats["inserted"] += 1

        db.flush()
        for alias, canonical in TELECOM_ALIASES.items():
            source = db.query(Telecom).filter(Telecom.name == alias).first()
            target = db.query(Telecom).filter(Telecom.name == canonical).first()
            if source and target and source.telecom_id != target.telecom_id:
                # 상품 ID를 유지하므로 구독과 알림 참조를 보존한다.
                db.query(Plan).filter(Plan.telecom_id == source.telecom_id).update(
                    {Plan.telecom_id: target.telecom_id}, synchronize_session=False)
        if commit:
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[TelecomRegistry] 동기화 에러: {e}")
        raise e
    finally:
        if should_close_db:
            db.close()

    return stats

if __name__ == "__main__":
    result = sync_telecom_master()
    print("통신사 마스터 동기화 완료:", result)


def is_excluded_telecom(name, website_url=''):
    """사용자가 명시적으로 제외한 사업자는 허브/공식몰 어느 경로로도 재등록하지 않는다."""
    normalized=re.sub(r'\s+', '', (name or '').replace('(주)', '').replace('㈜', '')).lower()
    host=urlparse(website_url or '').hostname or ''
    return normalized in {'앤텔레콤','엔텔레콤','ntelecom','앤알커뮤니케이션','주식회사앤알커뮤니케이션'} or host=='n-telecom.co.kr' or host.endswith('.n-telecom.co.kr')
