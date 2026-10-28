#!/usr/bin/env bash
set -euo pipefail

# Yugioh BAM Pocket Revived: start the game server from the project root.
# PUBLIC_HOST must be the host name the APK was built for (tools/build_release.py --host).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

: "${PUBLIC_HOST:?set PUBLIC_HOST, e.g. PUBLIC_HOST=ygo.example.com}"

exec python3 server/server.py \
    --host "${BIND:-0.0.0.0}" \
    --port "${PORT:-8087}" \
    --cdn-host "${PUBLIC_HOST}" \
    --input-dir "${LOCAL_STORE:-input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store}" \
    --cache-dir "work/package_cache"
