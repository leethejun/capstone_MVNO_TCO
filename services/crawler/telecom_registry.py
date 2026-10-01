from typing import List, Dict, Any
from sqlalchemy.orm import Session
from models import Telecom
from database import SessionLocal

# 나무위키 "통신회사/MVNO 통신사 목록/대한민국" 기준 전체 알뜰폰 통신사 마스터 데이터
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
    {"name": "앤텔레콤", "website_url": "https://www.n-telecom.co.kr", "network": "3사망"},
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

def sync_telecom_master(db: Session = None) -> Dict[str, Any]:
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
            existing = db.query(Telecom).filter(
                (Telecom.name == name) |
                (Telecom.name.ilike(f"%{name[:3]}%"))
            ).first()

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
