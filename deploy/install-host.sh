#!/usr/bin/env bash
# 첫 배포 전용. 기존 nginx.conf 및 다른 사이트 설정을 수정하지 않는다.
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN=alddletco.bulldog-walker.com
SITE_DIR=/srv/alddle-tco
SITE_CONF=/etc/nginx/conf.d/alddle-tco.conf
AUTH_FILE=/etc/nginx/alddle-tco.htpasswd

if [[ $EUID -ne 0 ]]; then
    echo 'sudo bash deploy/install-host.sh 로 실행하세요.' >&2
    exit 1
fi
for command in nginx certbot openssl curl getent systemctl; do
    command -v "$command" >/dev/null || { echo "필요한 명령이 없습니다: $command" >&2; exit 1; }
done
[[ -f "$PROJECT_DIR/frontend/dist/index.html" ]] || { echo '먼저 npm run build --prefix frontend 를 실행하세요.' >&2; exit 1; }
[[ ! -e "$SITE_CONF" && ! -e "$AUTH_FILE" && ! -e "$SITE_DIR/current" ]] || { echo '이 프로젝트 설정이 이미 있습니다. 기존 파일을 자동으로 덮어쓰지 않습니다.' >&2; exit 1; }
getent group http >/dev/null || { echo "nginx 실행 그룹 http가 없습니다." >&2; exit 1; }
getent ahostsv4 "$DOMAIN" >/dev/null || { echo "DNS A 레코드를 먼저 등록하세요: $DOMAIN" >&2; exit 1; }
nginx -t
curl --fail --silent http://127.0.0.1:8000/health/db >/dev/null

read -r -p '사이트 접속 계정 이름 [alddle]: ' LOGIN_USER
LOGIN_USER=${LOGIN_USER:-alddle}
[[ "$LOGIN_USER" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo '계정 이름은 영문/숫자/_/-만 사용하세요.' >&2; exit 1; }
read -r -s -p '사이트 접속 비밀번호: ' LOGIN_PASSWORD
printf '\n'
read -r -s -p '비밀번호 확인: ' PASSWORD_CONFIRM
printf '\n'
[[ -n "$LOGIN_PASSWORD" && "$LOGIN_PASSWORD" == "$PASSWORD_CONFIRM" ]] || { echo '비밀번호가 비어 있거나 일치하지 않습니다.' >&2; exit 1; }
PASSWORD_HASH=$(printf '%s' "$LOGIN_PASSWORD" | openssl passwd -6 -stdin)
unset LOGIN_PASSWORD PASSWORD_CONFIRM

install -d -m 755 "$SITE_DIR" "$SITE_DIR/acme" "$SITE_DIR/releases"
RELEASE_DIR="$SITE_DIR/releases/$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 755 "$RELEASE_DIR"
cp -R "$PROJECT_DIR/frontend/dist/." "$RELEASE_DIR/"
chmod -R a+rX "$RELEASE_DIR"
ln -s "$RELEASE_DIR" "$SITE_DIR/current"
printf '%s:%s\n' "$LOGIN_USER" "$PASSWORD_HASH" > "$AUTH_FILE"
unset PASSWORD_HASH
chown root:http "$AUTH_FILE"
chmod 640 "$AUTH_FILE"

# 실패하면 이번에 추가한 설정만 제거하고 기존 nginx 구성을 다시 로드한다.
# 웹 빌드는 보존하고, 이번에 만든 비밀번호/배포 링크만 해제한다.
rollback() {
    status=$?
    if [[ $status -ne 0 ]]; then
        unlink "$SITE_CONF" 2>/dev/null || true
        unlink "$AUTH_FILE" 2>/dev/null || true
        unlink "$SITE_DIR/current" 2>/dev/null || true
        if nginx -t; then systemctl reload nginx || true; fi
        echo '배포 실패: 새 사이트 설정만 해제했습니다. 기존 사이트 설정은 보존했습니다.' >&2
    fi
}
trap rollback EXIT
install -m 644 "$PROJECT_DIR/deploy/nginx/alddle-tco-http.conf" "$SITE_CONF"
nginx -t
systemctl reload nginx

# nginx 플러그인을 사용하지 않아 기존 사이트/인증서 설정을 편집하지 않는다.
# 최초 발급 시 Certbot의 이메일/약관 안내에 직접 응답한다.
certbot certonly --webroot --webroot-path "$SITE_DIR/acme" \
    --cert-name "$DOMAIN" -d "$DOMAIN"
install -m 644 "$PROJECT_DIR/deploy/nginx/alddle-tco-https.conf" "$SITE_CONF"
nginx -t
systemctl reload nginx
# 갱신 완료 후 새 인증서를 무중단으로 읽는다. 다른 갱신 hook은 유지한다.
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
install -m 755 "$PROJECT_DIR/deploy/reload-nginx.sh" \
    /etc/letsencrypt/renewal-hooks/deploy/alddle-tco-reload-nginx
# 기존 Certbot timer 상태를 바꾸지 않고 이 도메인만 갱신한다.
install -m 644 "$PROJECT_DIR/deploy/systemd/alddle-tco-certbot.service" /etc/systemd/system/alddle-tco-certbot.service
install -m 644 "$PROJECT_DIR/deploy/systemd/alddle-tco-certbot.timer" /etc/systemd/system/alddle-tco-certbot.timer
systemctl daemon-reload
systemctl enable --now alddle-tco-certbot.timer
trap - EXIT
printf '배포 완료: https://%s (계정: %s)\n' "$DOMAIN" "$LOGIN_USER"
