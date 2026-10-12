#!/usr/bin/env bash
# 이 앱의 사이트 설정에 있는 Basic 인증만 제거한다.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'sudo bash deploy/remove-basic-auth.sh 로 실행하세요.' >&2; exit 1; }
CONF=/etc/nginx/conf.d/alddle-tco.conf
[[ -f "$CONF" ]] || { echo '앱 nginx 설정이 없습니다.' >&2; exit 1; }
# Google 인증이 운영에 반영된 경우에만 사이트를 공개한다.
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:8000/api/users/me) == 401 ]] || {
    echo 'Google 인증 API를 먼저 운영에 반영하세요.' >&2; exit 1;
}
BACKUP="${CONF}.before-public-$(date -u +%Y%m%dT%H%M%SZ).bak"
cp -p "$CONF" "$BACKUP"
restore() { cp -p "$BACKUP" "$CONF"; nginx -t && systemctl reload nginx; }
trap restore ERR
python3 - "$CONF" <<'PY'
import sys,re
from pathlib import Path
p=Path(sys.argv[1]);s=p.read_text()
if 'server_name alddletco.bulldog-walker.com;' not in s:
    raise SystemExit('대상 도메인 불일치')
s=re.sub(r'^\s*auth_basic_user_file[^;]*;\s*$', '', s, flags=re.M)
s=re.sub(r'^(\s*)auth_basic\s+[^;]*;', r'\1auth_basic off;', s, flags=re.M)
s=s.replace('사이트 Basic 인증과 공존한다.', '백엔드 인증에 사용한다.')
p.write_text(s)
PY
nginx -t
systemctl reload nginx
trap - ERR
printf '사이트 접속 비밀번호 제거 완료. 백업: %s\n' "$BACKUP"
