# APScheduler 기반 정기 크롤링 및 환승 알림 엔진 구현 계획 (과제 5)

백엔드 서버 내에서 자동으로 작동하는 백그라운드 스케줄러를 구축하여:
1. **매일 새벽 2시**: 알뜰폰 요금제 전수 자동 크롤링 및 최신화
2. **매일 자정**: 프로모션 만료 임박(D-14, D-7, D-3) 구독자를 자동 조회하고, 현재 요금제와 유사한 최적의 **TCO 최저가 대체 요금제를 자동 추천**하여 알림(FCM, Discord Webhook, 콘솔 로깅)을 발송하는 생애주기 환승 시스템을 완성합니다.

---

## 1. 아키텍처 및 배치 워크플로우

```
[APScheduler 백그라운드 매니저]
  │
  ├─▶ [새벽 02:00 작업]: run_comprehensive_crawler_pipeline()
  │     └─ 55개 통신사 동기화 & 알뜰폰허브/공식몰 대량 요금제 갱신
  │
  └─▶ [자정 00:00 작업]: job_send_lifecycle_notifications()
        │
        ├─ 1. notifications 테이블 조회 (scheduled_date <= 오늘, status == 'PENDING')
        │
        ├─ 2. 최적 대체 요금제 자동 추천 엔진
        │     └─ 현재 요금제 스펙(데이터/QoS) 충족 & TCO 최저가 1위 요금제 매핑
        │
        ├─ 3. 알림 페이로드 구성 및 멀티 채널 발송
        │     ├─ FCM 푸시 알림 (토큰 보유 시)
        │     ├─ Discord Webhook 알림 (실시간 모니터링 채널)
        │     └─ 시스템 감사 로그 기록
        │
        └─ 4. notifications 상태 업데이트 (status = 'SENT', sent_at = now)
```

---

## Proposed Changes

### 의존성 및 라이브러리

#### [MODIFY] [requirements.txt](file:///home/bulldogw/문서/capstone_MVNO_TCO/requirements.txt)
- `apscheduler`, `firebase-admin` 추가

---

### 스케줄러 및 알림 엔진 모듈

#### [NEW] [services/notifier.py](file:///home/bulldogw/문서/capstone_MVNO_TCO/services/notifier.py)
- 멀티 채널 알림 발송 서비스:
  - `send_fcm_notification()`: Firebase Cloud Messaging 발송
  - `send_discord_notification()`: Discord Webhook 메시지 전송 (임베드 카드 형태)
  - 알림 페이로드 템플릿 (D-14: 사전 탐색, D-7: 환승 준비, D-3: 즉시 개통 권고)

#### [NEW] [services/recommender.py](file:///home/bulldogw/문서/capstone_MVNO_TCO/services/recommender.py)
- 환승 알림 대상자의 현재 요금제(기본 데이터, QoS 속도)를 기준으로 가장 유리한 TCO 최저가 대체 요금제 1종을 선별하는 추천 알고리즘

#### [NEW] [services/scheduler/tasks.py](file:///home/bulldogw/문서/capstone_MVNO_TCO/services/scheduler/tasks.py)
- 새벽 2시 크롤링 정기 작업
- 자정 환승 알림 배치 발송 정기 작업

#### [NEW] [services/scheduler/manager.py](file:///home/bulldogw/문서/capstone_MVNO_TCO/services/scheduler/manager.py)
- `AsyncIOScheduler` 초기화 및 FastAPI 라이프사이클 연동

---

### REST API 엔드포인트 및 관리 라우터

#### [NEW] [routers/notifications.py](file:///home/bulldogw/문서/capstone_MVNO_TCO/routers/notifications.py)
- `POST /api/notifications/trigger-batch`: 자정 환승 알림 배치 즉시 수동 실행 (검증 및 테스트용)
- `GET /api/notifications/pending`: 발송 대기 중인 알림 목록 조회
- `GET /api/scheduler/jobs`: 등록된 스케줄러 작업 목록 및 다음 실행 일시 조회

#### [MODIFY] [main.py](file:///home/bulldogw/문서/capstone_MVNO_TCO/main.py)
- 스케줄러 시작/종료 라이프사이클 이벤트 등록
- `notifications` 라우터 포함

---

## Verification Plan

### Automated Tests & Container Execution
1. 패키지 설치 및 컨테이너 재시작:
   ```bash
   docker compose exec backend pip install apscheduler firebase-admin
   docker compose restart backend
   ```
2. 오늘 날짜로 만료 알림이 도래한 테스트 구독/알림 생성
3. 알림 배치 즉시 실행 API 호출:
   ```bash
   curl -s -X POST http://localhost:8000/api/notifications/trigger-batch
   ```
4. DB 검증:
   - `notifications.status`가 `SENT`로 변경되었는지 확인
   - `recommended_plan_id`에 최적의 TCO 요금제가 매핑되었는지 확인
5. 스케줄러 상태 조회:
   ```bash
   curl -s http://localhost:8000/api/scheduler/jobs
   ```
