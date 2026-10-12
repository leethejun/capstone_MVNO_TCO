# 통신사 수집 조사 — 2026-10-09

등록된 마스터 55곳 중 상품 미수집 28곳과 동일 할인가·정상가 상품이 있는 16곳, 총 44곳의 공식 홈페이지 메뉴를 순서대로 조사했다. 주소 발견은 상품 수집 완료를 의미하지 않는다. 후속 조사에서 남은 24곳도 모두 확인했다. 이 중 15곳의 검증된 공식 상품 502개를 추천 DB에 반영했고, 전체 활성 상품은 2,675개다. 가입 중단·여행용·가입 제한·선불 상품 및 외부 조회 실패는 아래에서 구분한다. 등록 마스터는 수동 목록이므로 대한민국 모든 사업자를 보장하는 숫자는 아니다.

은행계 통신사에서 금융상품·급여이체·예적금·카드실적 등을 조건으로 하는 상품은 수집 파이프라인에서 제외한다. 조건을 확인하지 못한 은행 상품을 임의의 체감가로 추가하지 않았다. KB리브 31개는 금융 결합 없는 공식 월 기본료 기준으로 반영하고, 선택형 카드 할인·캐시백·포인트는 차감하지 않았다. 우리WON은 조건 없는 첫 2개월 할인 상품 1개를 반영했다. 금융 조건 설명과 모든 상품에 붙는 일반 유의사항·선택형 카드 배너를 구분했다.

## 반영 내용

- SK7 공개 전체 검색 117건, 더원 공개 전체 카테고리 141건, 위너스텔 15건, 밸류컴 후불 상세 표 26건 신규 반영.
- 공식몰 카드/상세 표 파서를 통해 조이텔 60건, 도시락 58건, 한패스 18건, KCTV 17건, 시월 64건, 온국민 16건 반영. 허브 상품과 공식몰 상품의 조건은 별도로 유지한다.
- `8개월 차부터`는 할인 7개월로 해석한다. 쿠폰 제공 개월 수를 할인 기간으로 사용하지 않는다. 평생 할인 정상가는 상세 기본료를 확인하며 확인 실패 상품은 제외한다.
- HTTP 한글 인코딩을 HTML 원본 기준으로 읽고 실제 메뉴에서 확인한 목록 경로를 저장했다.
- 구독 중인 이전 요금제는 삭제하지 않고 비활성 이력으로 보존한다.

## 통신사별 상태

|통신사|조사 전 활성/동일가|조사 후 활성/동일가|확인한 목록 또는 상태|
|---|---:|---:|---|
|SK 7mobile|0/0|117/1|[공식 목록](https://www.sk7mobile.com/prod/data/callingPlanList.do?refCode=USIM)|
|KB리브모바일|0/0|31/31|[공식 목록](https://m.liivm.com/rateplan/plans/products)|
|우리WON모바일|0/0|1/0|[공식 목록](https://www.wooriwonmobile.com/rate-plan/list)|
|핀다이렉트|0/0|69/0|[공식 목록](https://www.pindirectshop.com/deal-list)|
|에르엘|0/0|17/0|[공식 목록](https://www.erel.co.kr/usim/entry-soc) — 17개 반영, 할인 기간 필드 없는 9개 제외|
|스노우맨|0/0|0/0|HTML에 직접 요금제 목록 없음; 동적 화면/현행 경로 추가 확인 필요 — **수집 미완료**|
|위너스텔(WELL)|0/0|15/6|[공식 목록](https://www.idowell.co.kr/rate_plan.do)|
|니즈모바일|0/0|0/0|HTML에 직접 요금제 목록 없음; 동적 화면/현행 경로 추가 확인 필요 — **수집 미완료**|
|친구모바일|0/0|0/0|[공식 목록](https://chingumobile.com/ko/plans) — **수집 미완료**|
|에스원 안심모바일|0/0|30/0|[공식 목록](http://www.s1mobile.co.kr/home/plan/rateList.do?rateDv=U)|
|밸류컴|0/0|17/3|[공식 목록](https://www.valuecomm.co.kr/bbs/board.php?bo_table=pricList&sca=후불)|
|앤텔레콤|0/0|35/35|[공식 목록](https://info.n-telecom.co.kr/ntelecom-asp/products/all.asp)|
|아정당모바일|0/0|17/0|[공식 목록](https://www.ajdmobile.co.kr/rate_plan.do)|
|플래시모바일|0/0|15/15|[KT 공식 목록](https://olleh.flashmobile.kr/html_k/pay_main.html) 및 [LGU+ 공식 목록](https://uplus.flashmobile.kr/html/pay_main.html) — 무약정 기본료 기준|
|코인샷 모바일|0/0|0/0|[공식 목록](https://mobile.coinshot.org/ko/mobilePlan) — **수집 미완료**|
|알비레오|0/0|33/2|[공식 목록](https://www.albireomobile.com/plan)|
|쉐이크모바일|0/0|87/0|[공식 전체 목록](https://shakemobile.co.kr/M2Mobile/Set3G)|
|아이디스파워텔|0/0|0/0|[공식 목록](https://idispowertel.com/html/dh/powertalk3_3) — **수집 미완료**|
|드림라인 모바일|0/0|0/0|[공식 목록](https://dreammobile.kr/view/service/plans.aspx) — **수집 미완료**|
|퍼스트 모바일|0/0|13/13|[공식 목록](https://www.firstmobile.co.kr/bbs/board.php?bo_table=pricList&sca=후불&sca2=KT)|
|더원모바일|0/0|141/1|[공식 목록](https://www.theonem.co.kr/view/plan/phone_plan.aspx)|
|한국E텔레콤|0/0|4/4|[공식 목록](https://www.koretel.co.kr/view/plan/phone_plan.aspx)|
|MONA|0/0|126/0|[공식 목록](https://mobilemona.co.kr/view/plan/rate_plan.aspx)|
|GME모바일|0/0|14/0|[공식 목록](https://www.gmemobile.com/view/plan/phone_plan.aspx)|
|이음모바일|0/0|10/7|[공식 목록](https://eummobile.co.kr/rate)|
|서경모바일|0/0|0/0|HTML에 직접 요금제 목록 없음; 동적 화면/현행 경로 추가 확인 필요 — **수집 미완료**|
|여유모바일|0/0|0/0|HTML에 직접 요금제 목록 없음; 동적 화면/현행 경로 추가 확인 필요 — **수집 미완료**|
|원텔레콤|0/0|0/0|HTTPSConnectionPool(host='onetelecom.co.kr', port=443): Max retries exceeded with url: / (Caused by SSLError(SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch, certificate is not valid for 'onetelecom.co.kr'. (_ssl.c:1016)"))) — **수집 미완료**|
|아이즈모바일|384/111|384/111|[공식 목록](https://eyes.co.kr/payplan/all_plan/)|
|조이텔|131/93|131/58|[공식 목록](https://joytel.co.kr/rate_plan.do)|
|도시락모바일|59/59|58/58|[공식 목록](https://www.dosirakmobile.com/rate_plan.do)|
|프리티|314/29|316/30|HTML에 직접 요금제 목록 없음; 동적 화면/현행 경로 추가 확인 필요|
|KT스카이라이프|20/20|20/20|[공식 목록](https://www.skylife.co.kr/product/mobile/all)|
|한패스모바일|25/20|18/15|[공식 목록](https://www.hanpassmobile.co.kr/rate_plan.do)|
|KCTV모바일|17/17|17/17|[공식 목록](https://kctvm.com/rate_plan.do)|
|시월모바일|54/12|64/0|[공식 목록](https://www.siwolmobile.com/rate_plan.do)|
|고고모바일(고고팩토리)|87/10|87/10|[공식 목록](https://www.gogomobile.co.kr/onlineplan)|
|티플러스|133/9|133/9|HTTPSConnectionPool(host='www.tplusmobile.com', port=443): Max retries exceeded with url: / (Caused by SSLError(SSLError(1, '[SSL: WRONG_SIGNATURE_TYPE] wrong signature type (_ssl.c:1016)')))|
|KT M모바일|8/8|8/8|[공식 목록](https://www.ktmmobile.com/rate/rateList.do)|
|U+유모바일|8/8|8/8|HTML에 직접 요금제 목록 없음; 동적 화면/현행 경로 추가 확인 필요|
|헬로모바일|16/8|16/8|HTML에 직접 요금제 목록 없음; 동적 화면/현행 경로 추가 확인 필요|
|이야기모바일|14/2|14/2|[공식 목록](https://www.eyagi.co.kr/shop/plan/list.php?tag=pick)|
|찬스모바일|79/2|79/2|[공식 목록](https://chancemobile.co.kr/view/plan/phone_plan.aspx)|
|온국민폰|1/1|16/5|[공식 목록](https://xn--3e0b39yfuhjlo.kr/rate_plan.do)|

## 남은 24곳 후속 조사 결과와 제외 사유

정상가와 할인가가 같다는 이유만으로 오류 처리하지 않았다. 앤텔레콤·플래시·퍼스트·한국E·KB의 동일가는 확인된 무할인/무약정 기본료다. 핀다이렉트의 할인액 필드를 청구액과 구분하고, 일시 할인 종료 후 남는 평생 할인을 반영했다. 한국E는 필수 부가서비스를 포함한 실제 월 납부액을 사용한다. MONA의 120개월 이상 값은 공식 화면의 평생 할인 표기 규칙을 따른다.

|추천 DB에 미포함한 통신사|확인 결과와 원본|
|---|---|
|스노우맨|[전체 후불 목록](https://www.snowman.co.kr/portal/chageAdtnsvc/ppdChage/list)은 남아 있으나 온라인 가입 버튼은 숨겨져 있고 가입 경로는 과거 점검 안내를 표시한다. [사업 양도 공지](https://www.snowman.co.kr/portal/cctr/ntf/13226)는 2026-08-03~10-31 고고모바일 순차 이관, 10-31 서비스 종료 예정(연장 가능)을 안내한다. 현재 이미 서비스가 종료됐다고 판단하지 않았으며 신규 가입 가능한 상품으로 검증되지 않았다.|
|서경모바일|[현재 홈페이지](https://www.scsmobile.co.kr/)에 서비스 종료·해지/번호이동 안내가 표시된다. 종료일 연장 가능 문구도 있으며 새 요금제/가입 메뉴가 없다. 기존 가입자 안내를 신규 상품으로 적재하지 않는다.|
|여유모바일|[도시락 공식 약관 별표 2026-09-30](https://www.dosirakmobile.com/event_view.do?no=59)에 2025-12-01 신규 가입·번호이동 불가와 도시락 인수가 명시돼 있다. 기존 계약 요금은 유지되지만 신규 환승 추천 대상이 아니다. 도시락의 신규 상품은 별도 수집돼 있다.|
|니즈모바일|[국내 음성 eSIM 상세](https://nizmobile.com/Shop/SktEsimDetail)는 3/5/7/10/15/30일 여행용, 외국 여권 인증, 발신 별도 충전 상품이다. 국내 월별 번호이동 요금과 섞지 않는다.|
|친구모바일|[전체 후불 목록](https://chingumobile.com/ko/plans/select/postpaid) 45개 카드와 모든 상세를 원본 수집했다. [상품 선택 화면](https://chingumobile.com/ko/plans)은 후불 대상을 외국인등록증 소지자로 안내하며 [상세 예시](https://chingumobile.com/ko/plans/detail/784)에 최소 183일 사용·단말 제한이 있다. 현재 앱은 국적·기기·최소 유지일 조건을 검증하지 못하므로 일반 추천 DB에 섞지 않고 `runtime/restricted-carrier-inventory.json`에 보존한다.|
|코인샷 모바일|공식 전체 API의 9개 상품을 개수 검증 후 원본 수집했다. 모두 선불(PRE), 7개 정액·2개 종량제다. 선불 충전 주기를 월별 후불 유지기간과 동일하게 가정하지 않고 위 별도 원본 파일에 보존한다.|
|아이디스파워텔|[공식 요금 표](https://idispowertel.com/html/dh/powertalk3_3)는 파워톡/PTT 무전 상품이다. 스마트 요금에도 무전·전용 서비스가 묶여 있어 일반 스마트폰 유심 요금으로 취급하지 않았다.|
|드림라인 모바일|상단 메뉴의 [전체 요금제](https://dreammobile.kr/view/service/plans.aspx)와 공개 `AjaxPlans.aspx`를 확인했다. 실제 조회는 `RESULT=N`, 빈 목록을 반환한다. HTML의 반복 DREAM4 샘플 카드만으로 상품을 만들지 않았다. 외부 API 정상화 또는 현행 상품 자료가 필요하다.|
|원텔레콤|HTTPS 인증서 호스트 불일치, 공개 HTTP 홈페이지 내부 프레임은 403 Forbidden이다. 현행 전체 목록·가격을 확인할 수 없다. 인증서 검증을 끄지 않았다.|

은행계 제외는 상품 조건별로 처리한다. KB는 전체 121개/43개 그룹을 조사하고 금융 결합·별도 기기·가입 대상 제한 등을 제외했다. 우리WON은 전체 45개를 조사했으며 상세 조건 설명 누락/불일치 상품은 추정하지 않았다. 에르엘의 9개도 할인 종료 후 가격/기간을 확인하지 못해 제외했다. 따라서 **모든 사이트 조사 완료와 모든 상품 가격 검증 완료는 다르다**.

전용 수집기를 일일 전체 크롤링 경로에 연결했다. 목록 페이지 수/전체 개수/상품 코드·통신망 검증 실패 시 해당 결과를 완전한 목록으로 교체하지 않는다. 이번 수동 반영은 통신사별 공식몰 상품만 원자적으로 교체했으며 허브 상품과 구독 이력은 보존했다. 신규 파서 회귀 검증을 포함한 82개 테스트를 통과했다.

별도 제한 상품 원본/DB 건수 조사 재실행: `docker exec alddle_backend python -m deploy.collect_restricted_inventory`. 이 명령은 추천 DB를 변경하지 않는다.

## 사용자 제외 요청 반영

앤텔레콤은 사용자 요청으로 수집/추천 대상에서 제외했다. 공식·허브 재등록을 차단하고 DB의 요금제 35개 및 통신사 행을 삭제했다. 연결된 구독/알림은 없었다. 위 조사 건수는 제외 요청 이전 시점의 기록이다.
