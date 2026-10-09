#!/usr/bin/env bash
set -euo pipefail
if [[ "${RENEWED_LINEAGE:-}" == /etc/letsencrypt/live/alddletco.bulldog-walker.com ]]; then
    nginx -t
    systemctl reload nginx
fi
