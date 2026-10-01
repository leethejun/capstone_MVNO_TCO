# 알뜰폰 TCO 최적화 프로젝트 구현 및 검증 결과

## 1. 개요 및 진행 현황
- **과제 1 & 2 완료**: All-in-Docker 컨테이너 환경, MySQL 8.0, SQLAlchemy ORM 모델, 비정형 데이터 정규표현식 파서(`PlanTextParser`)
- **과제 4 완료**: TCO 최적화 계산 엔진, 최저가 랭킹 API, 사용자 개통 및 환승 알림 스케줄 자동 생성 시스템
- **과제 3 완료 & 고도화**: 나무위키 55개 알뜰폰 통신사 마스터 DB 구축, 알뜰폰허브 전수 페이징 크롤러(340+건), 공식몰 다이렉트 크롤러
- **QoS 무제한 실시간 수집 및 비교 체계화 (완료)**: 크롤링 단계에서 실제 명시된 정확한 QoS 속도(1Mbps, 3Mbps, 5Mbps, 400Kbps) 추출, 무제한 등급(`qos_tier`) 산출, 조건별(1Mbps/3Mbps 무제한 필터) TCO 최저가 랭킹 구현

---

## 2. QoS 정밀 수집 및 비교 개선 상세

### ① 크롤링 & 파싱 단계 원천 데이터 정밀 복원
- **원인 규명**: 알뜰폰허브 웹 소스에 `10GB+1Mbps`, `11GB+3Mbps`, `125GB+5Mbps`처럼 정확한 QoS 수치가 명시되어 있었으나, 전각 문자(`＋`), 다중 개행, 음성 조건 미흡으로 누락되었던 문제를 근본 해결.
- **`PlanTextParser` (`parser.py`)**:
  - 유니코드 `NFKC` 정규화로 전각 기호 통일
  - `Mbps`, `Kbps`, `+3M`, `속도제어 3` 등 복합 QoS 패턴을 실수형(`qos_speed_mbps`)으로 정밀 추출
  - `(?<![가-힣])` Negative Lookbehind를 적용하여 `모바일 10GB` 등에서 `일` 오매칭 방지
- **`MvnohubCrawler` (`services/crawler/mvnohub_crawler.py`)**:
  - 카드 내 제목(`p.tit`)과 스펙 태그(`.dtl li.wifi`)를 온전히 병합 정규화하여 파서로 전달

### ② 무제한 체감 등급(Tier) 및 동률 시 조건 우대
- **`qos_tier` 체계**:
  - `5.0Mbps+`: "초고속 무제한 (5Mbps+)"
  - `3.0Mbps`: "FHD 고속 무제한 (3Mbps, 유튜브 1080p/릴스 원활)"
  - `1.0Mbps`: "실속 무제한 (1Mbps, 유튜브 480p SD 원활)"
  - `0.4Mbps`: "안심 무제한 (400Kbps, 카카오톡 텍스트용)"
  - `0.0Mbps`: "소진 시 차단/과금형"
- **TCO 랭킹 정렬 가중치**:
  - 동일한 TCO(비용)인 경우 **무제한 여부 $\rightarrow$ QoS 속도 높은 순 $\rightarrow$ 기본 데이터 많은 순**으로 자동 정렬하여 사용자에게 더 좋은 조건의 요금제를 우선 추천.

### ③ REST API 조건별 검색 지원 (`GET /api/plans/rank`)
- `is_unlimited_data=true`: 추가 과금 없는 실질 무제한 요금제만 모아보기
- `min_qos_speed_mbps=1.0`: 유튜브 SD 스트리밍 가능한 실속 무제한 이상만 모아보기
- `min_qos_speed_mbps=3.0`: 유튜브 FHD 고화질 재생 가능한 고속 무제한 이상만 모아보기

---

## 3. 실시간 검증 결과

### ① DB 내 실제 QoS 속도 수집 확인
```sql
SELECT plan_id, title, base_data_gb, qos_speed_mbps, discount_price FROM plans WHERE qos_speed_mbps > 0 LIMIT 5;
```
| plan_id | 요금제명 | 기본데이터 | QoS속도 | 할인가 |
| :--- | :--- | :--- | :--- | :--- |
| 14 | [LGU+](5G) 95GB+3Mbps | 95.0GB | **3.0Mbps** | 6,500원 |
| 15 | [L]100GB+5Mbps | 100.0GB | **5.0Mbps** | 6,800원 |
| 16 | 필요한 만큼만 골라 쓰는 초저가 | 4.5GB | **1.0Mbps** | 10원 |
| 18 | #찬스모바일 놓치면 후회 | 125.0GB | **5.0Mbps** | 10,500원 |
| 19 | [12개월간 990원 특가] 4.5기가 | 4.5GB | **1.0Mbps** | 990원 |

### ② "유튜브 FHD 재생 가능한 실질 무제한 (QoS 3Mbps 이상)" TCO 최저가 랭킹 검색
```bash
curl -s "http://localhost:8000/api/plans/rank?target_months=7&min_qos_speed_mbps=3.0&limit=3"
```
**결과:**
```
1. [티플러스] 티플 외국인 7GB＋3Mbps | 기본:7.0GB | QoS:3.0Mbps | 등급:FHD 고속 무제한 (3Mbps) | TCO:27,300원 (월평균:3,900원)
2. [A모바일] LGU+ 지금 진짜 최저가 | 기본:11.0GB | QoS:3.0Mbps | 등급:FHD 고속 무제한 (3Mbps) | TCO:34,293원 (월평균:4,899원)
```
> 사용자가 원하는 조건(유튜브 1080p 시청 가능한 3Mbps 무제한) 중 **가장 저렴한 3,900원대 요금제**가 정확히 1위로 찾아졌습니다.
