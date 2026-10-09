#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_DIR=/srv/alddle-tco
[[ $EUID -eq 0 ]] || { echo 'sudo bash deploy/update-frontend.sh 로 실행하세요.' >&2; exit 1; }
[[ -L "$SITE_DIR/current" ]] || { echo '먼저 최초 배포를 완료하세요.' >&2; exit 1; }
[[ -f "$PROJECT_DIR/frontend/dist/index.html" ]] || { echo '먼저 프론트엔드를 빌드하세요.' >&2; exit 1; }
RELEASE_DIR="$SITE_DIR/releases/$(date -u +%Y%m%dT%H%M%SZ)"
[[ ! -e "$RELEASE_DIR" ]] || { echo '같은 시각의 release가 있습니다. 잠시 후 다시 실행하세요.' >&2; exit 1; }
PREVIOUS_RELEASE=$(readlink "$SITE_DIR/current")
install -d -m 755 "$RELEASE_DIR"
cp -R "$PROJECT_DIR/frontend/dist/." "$RELEASE_DIR/"
chmod -R a+rX "$RELEASE_DIR"
NEXT_LINK="$SITE_DIR/.current-$$"
ln -s "$RELEASE_DIR" "$NEXT_LINK"
mv -Tf "$NEXT_LINK" "$SITE_DIR/current"
printf '배포 완료: %s\n이전 release: %s\n' "$RELEASE_DIR" "$PREVIOUS_RELEASE"
