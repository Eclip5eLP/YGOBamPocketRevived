#!/usr/bin/env bash
set -euo pipefail

# Yu-Gi-Oh! BAM Pocket Revival Server Launch Script
# Target deployment path: ~/Documents/PythonBots/YGOBamPocketRevival

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "Starting Yu-Gi-Oh! BAM Pocket Revival Server..."
exec python3 server/server.py \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8087}" \
    --cdn-host "${CDN_HOST:-ygo.eclip5e.com}" \
    --input-dir "input/data/data/air.com.konami.ygo/com.konami.ygo/Local Store" \
    --cache-dir "work/package_cache" \
    --version-string "android=1.11.2~ios=1.11.2"
