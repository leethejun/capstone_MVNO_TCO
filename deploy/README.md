# alddletco.bulldog-walker.com 배포

기존 블로그, 댓글 서비스, Open WebUI의 nginx 설정과 컨테이너를 유지하고
`/etc/nginx/conf.d/alddle-tco.conf` 파일만 추가합니다.

## 준비된 구성

- 프론트엔드: `/srv/alddle-tco/current`의 React 빌드 파일
- API: nginx의 `/api/` → `http://127.0.0.1:8000/api/`
- 사이트 전체(HTML, 정적 파일, API): HTTPS + Basic 인증
- 앱 백엔드만 `127.0.0.1:8000`에 바인딩. 외부에서 비밀번호를 우회해 API에 접근하지 못합니다.
- 개발 환경은 로컬 Vite `/api` proxy를 사용합니다. 개발 서버도 `127.0.0.1:5173`에 바인딩해 사이트 비밀번호를 우회하는 외부 경로를 만들지 않습니다.
- TLS 인증서: 별도 서브도메인 인증서를 webroot 방식으로 발급합니다.
  Certbot nginx 플러그인을 쓰지 않아 기존 도메인 설정을 자동 편집하지 않습니다.
- nginx는 `nginx -t` 성공 후 reload합니다. stop/restart하지 않습니다.

## 1. DNS 등록

현재 DNS 관리 업체에서 다음 레코드를 추가합니다. 기존 레코드는 변경하지 않습니다.

| 유형 | 이름 | 값 |
| --- | --- | --- |
| A | alddletco | 222.96.171.168 |

이 주소는 배포 준비 시 기존 `bulldog-walker.com`이 가리키던 IPv4입니다.
공인 IP가 바뀌었다면 기존 블로그와 동일한 최신 IP를 사용하세요.
기존 라우터의 80/443 포트 연결을 그대로 사용하며 새 외부 포트는 필요 없습니다.

```bash
getent ahostsv4 alddletco.bulldog-walker.com
```

## 2. 데스크톱 터미널에서 설치

sudo 암호는 Codex 채팅에 보내지 말고 터미널에 직접 입력합니다.

```bash
cd /home/bulldogw/문서/capstone_MVNO_TCO
npm run build --prefix frontend
sudo bash deploy/install-host.sh
```

사이트 접속 계정/비밀번호는 설치 중 직접 지정합니다.
Certbot이 요구하면 인증서 계정 이메일과 약관에 응답합니다.
설치 중에는 새 도메인의 ACME 경로만 열고 앱은 404로 유지합니다.
인증서 발급이 끝나면 HTTPS/비밀번호 설정을 활성화합니다.
설정 검사나 발급 실패 시 이번에 추가한 nginx 파일을 제거하고 기존 설정으로 reload합니다.
배포 파일은 보존하며, 이번에 생성한 인증 파일과 current 링크는 해제해 재시도가 가능하게 합니다.
첫 배포 전용 스크립트이므로 기존 앱 배포가 있으면 덮어쓰지 않고 중단합니다.

## 3. 확인

- `https://alddletco.bulldog-walker.com`에서 비밀번호 입력 후 랭킹 확인
- 비밀번호 없이 HTML/API 요청 시 401인지 확인
- 블로그, `chat.bulldog-walker.com`, `comments.bulldog-walker.com`도 확인

```bash
curl -I https://alddletco.bulldog-walker.com
curl -I https://alddletco.bulldog-walker.com/api/plans/rank
sudo nginx -t
sudo certbot renew --dry-run --cert-name alddletco.bulldog-walker.com
systemctl status alddle-tco-certbot.timer
```

기존 `certbot-renew.timer`는 점검 시 비활성 상태였습니다.
설치 스크립트는 이 도메인만 대상으로 하는 `alddle-tco-certbot.timer`를 새로 추가하고 활성화합니다.
하루 두 번 갱신 필요 여부를 확인하며 기존 timer 상태는 변경하지 않습니다.
해당 인증서 갱신 후에만 `alddle-tco-reload-nginx` deploy hook이 nginx 검사/reload를 실행합니다.
기존 hook을 덮어쓰지 않습니다.

## 코드 수정 후 배포

```bash
cd /home/bulldogw/문서/capstone_MVNO_TCO
npm run build --prefix frontend
sudo bash deploy/update-frontend.sh
# 백엔드 변경 시 이 서비스만 갱신
# docker compose up -d --no-deps --build backend
```

프론트엔드 업데이트는 새 release 폴더를 만들고 current 링크만 교체합니다.
기존 release는 보존하며, nginx 재시작이 필요 없습니다.

## 적용 범위와 남은 단계

준비 시 프론트엔드 빌드, 임시 nginx의 HTTPS/Basic 인증/API 전달 테스트를 통과했습니다.
백엔드 이미지의 누락된 requests 의존성도 재빌드로 복구했습니다.
실제 호스트 nginx 파일 설치 및 공인 TLS 발급은 sudo 권한/DNS 설정 후 실행해야 합니다.
사이트 전체 비밀번호는 앱 내부 사용자별 로그인 기능과 별개입니다.

참고: [nginx reload 동작](https://nginx.org/en/docs/beginners_guide.html#control), [proxy_pass 경로 처리](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass).
