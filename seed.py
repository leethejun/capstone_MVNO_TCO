from datetime import datetime
from database import SessionLocal
from models import Telecom, Plan
from parser import PlanTextParser

def seed_data():
    db = SessionLocal()
    try:
        # 기존 데이터 확인
        existing_telecoms = db.query(Telecom).count()
        if existing_telecoms > 0:
            print("데이터가 이미 존재합니다. 시딩을 건너뜁니다.")
            return

        print("=== 1. 알뜰폰 통신사 시드 데이터 생성 ===")
        telecom_freet = Telecom(name="프리티", website_url="https://www.freet.co.kr", logo_url="https://example.com/freet.png")
        telecom_eyagi = Telecom(name="이야기모바일", website_url="https://www.eyagi.co.kr", logo_url="https://example.com/eyagi.png")
        telecom_mobing = Telecom(name="모빙", website_url="https://www.mobing.co.kr", logo_url="https://example.com/mobing.png")
        telecom_erel = Telecom(name="에르엘", website_url="https://www.erel.co.kr", logo_url="https://example.com/erel.png")
        telecom_eyes = Telecom(name="아이즈모바일", website_url="https://www.eyes.co.kr", logo_url="https://example.com/eyes.png")

        db.add_all([telecom_freet, telecom_eyagi, telecom_mobing, telecom_erel, telecom_eyes])
        db.flush()

        print("=== 2. 비정형 텍스트 기반 요금제 시드 데이터 생성 및 정형화 ===")
        raw_plan_data = [
            # 1. 프리티 요금제
            {
                "telecom": telecom_freet,
                "title": "프리티 든든 7GB+",
                "network_type": "LTE",
                "raw_text": "7GB+1Mbps 음성무제한 문자무제한",
                "discount_price": 3300,
                "normal_price": 18700,
                "discount_months": 7,
            },
            {
                "telecom": telecom_freet,
                "title": "프리티 0원 세이브",
                "network_type": "LTE",
                "raw_text": "1GB 음성100분 문자100건",
                "discount_price": 0,
                "normal_price": 8800,
                "discount_months": 6,
            },
            {
                "telecom": telecom_freet,
                "title": "프리티 안심 15GB+",
                "network_type": "LTE",
                "raw_text": "15GB+3Mbps 음성100분 문자100건",
                "discount_price": 12100,
                "normal_price": 3300,
                "discount_months": 7,
            },
            # 2. 이야기모바일 요금제
            {
                "telecom": telecom_eyagi,
                "title": "이야기 스탠다드 11GB+",
                "network_type": "LTE",
                "raw_text": "11GB+일2GB+3Mbps 음성무제한 문자무제한",
                "discount_price": 19800,
                "normal_price": 39600,
                "discount_months": 7,
            },
            {
                "telecom": telecom_eyagi,
                "title": "이야기 라이트 5GB",
                "network_type": "LTE",
                "raw_text": "5GB 음성200분 문자100건",
                "discount_price": 4400,
                "normal_price": 15400,
                "discount_months": 12,
            },
            {
                "telecom": telecom_eyagi,
                "title": "이야기 매일5GB 헤비",
                "network_type": "LTE",
                "raw_text": "일5GB+5Mbps 음성무제한 문자무제한",
                "discount_price": 27500,
                "normal_price": 45100,
                "discount_months": 6,
            },
            # 3. 모빙 요금제
            {
                "telecom": telecom_mobing,
                "title": "모빙 매일2GB+",
                "network_type": "LTE",
                "raw_text": "11GB+일2GB+3Mbps 음성무제한 문자무제한",
                "discount_price": 17900,
                "normal_price": 38500,
                "discount_months": 6,
            },
            {
                "telecom": telecom_mobing,
                "title": "모빙 실속 10GB+",
                "network_type": "LTE",
                "raw_text": "10GB+1Mbps 음성200분 문자100건",
                "discount_price": 7700,
                "normal_price": 22000,
                "discount_months": 7,
            },
            {
                "telecom": telecom_mobing,
                "title": "모빙 초저가 3GB",
                "network_type": "LTE",
                "raw_text": "3GB 음성100분 문자50건",
                "discount_price": 1100,
                "normal_price": 9900,
                "discount_months": 6,
            },
            # 4. 에르엘 요금제
            {
                "telecom": telecom_erel,
                "title": "에르엘 갓성비 15GB+",
                "network_type": "LTE",
                "raw_text": "15GB+3Mbps 음성300분 문자300건",
                "discount_price": 10900,
                "normal_price": 31900,
                "discount_months": 7,
            },
            {
                "telecom": telecom_erel,
                "title": "에르엘 5G 스피드 10GB",
                "network_type": "5G",
                "raw_text": "10GB+1Mbps 음성무제한 문자무제한",
                "discount_price": 14500,
                "normal_price": 29700,
                "discount_months": 12,
            },
            # 5. 아이즈모바일 요금제
            {
                "telecom": telecom_eyes,
                "title": "아이즈 슈퍼세이브 7GB+",
                "network_type": "LTE",
                "raw_text": "7GB+일1GB+1Mbps 음성무제한 문자무제한",
                "discount_price": 8800,
                "normal_price": 26400,
                "discount_months": 8,
            },
        ]

        now = datetime.now()
        for pdata in raw_plan_data:
            # PlanTextParser로 비정형 텍스트 파싱
            parsed = PlanTextParser.parse(pdata["raw_text"])

            plan = Plan(
                telecom_id=pdata["telecom"].telecom_id,
                title=pdata["title"],
                network_type=pdata["network_type"],
                base_data_gb=parsed["base_data_gb"],
                daily_data_gb=parsed["daily_data_gb"],
                qos_speed_mbps=parsed["qos_speed_mbps"],
                voice_minutes=parsed["voice_minutes"],
                sms_count=parsed["sms_count"],
                discount_price=pdata["discount_price"],
                normal_price=pdata["normal_price"],
                discount_months=pdata["discount_months"],
                raw_text=pdata["raw_text"],
                is_active=True,
                scraped_at=now
            )
            db.add(plan)

        db.commit()
        print("✅ 시드 데이터 적재 완료! (통신사 5곳, 요금제 12개)")

    except Exception as e:
        db.rollback()
        print(f"❌ 시드 데이터 삽입 실패: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
