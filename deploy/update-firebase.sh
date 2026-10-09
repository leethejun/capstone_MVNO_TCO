#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $EUID -eq 0 ]] || { echo 'sudo bash deploy/update-firebase.sh 로 실행하세요.' >&2; exit 1; }
cd "$PROJECT_DIR"
[[ -f frontend/dist/firebase-messaging-sw.js && -f secrets/service-account.json ]] || {
    echo 'Firebase 키와 프론트엔드 빌드를 먼저 준비하세요.' >&2; exit 1;
}
CONF=/etc/nginx/conf.d/alddle-tco.conf
[[ -f "$CONF" && -L /srv/alddle-tco/current ]] || { echo '기존 도메인 배포가 필요합니다.' >&2; exit 1; }
BACKUP_DIR="/srv/alddle-tco/backups/firebase-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 700 "$BACKUP_DIR"
cp "$CONF" "$BACKUP_DIR/nginx.conf"
install -m 644 deploy/nginx/alddle-tco-https.conf "$CONF"
if ! nginx -t; then
    cp "$BACKUP_DIR/nginx.conf" "$CONF"
    echo 'nginx 검증 실패: 기존 설정을 복원했습니다.' >&2
    exit 1
fi
restore_on_error() {
    cp "$BACKUP_DIR/nginx.conf" "$CONF"
    echo "업데이트 실패. nginx 파일을 복원했습니다. 백업: $BACKUP_DIR" >&2
}
trap restore_on_error ERR
# 비밀번호를 인자나 출력에 노출하지 않고 실행 중인 DB에서 백업한다.
docker exec alddle_mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"' > "$BACKUP_DIR/database.sql"
chmod 600 "$BACKUP_DIR/database.sql"
docker compose run --rm --no-deps backend python -B -m deploy.migrate_firebase
docker compose up -d --no-deps backend
healthy=false
for attempt in {1..20}; do
    if curl --fail --silent http://127.0.0.1:8000/health/db >/dev/null; then healthy=true; break; fi
    sleep 1
done
[[ "$healthy" == true ]] || { echo '백엔드 상태 확인 실패' >&2; exit 1; }
bash deploy/update-frontend.sh
nginx -t
systemctl reload nginx
trap - ERR
printf 'Google 로그인 / FCM 배포 완료. 백업: %s\n' "$BACKUP_DIR"
