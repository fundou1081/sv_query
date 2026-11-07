#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${DSH_HOME:-$HOME/.dsh}/profiles/node_modules/@svq/query-tool"
mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -R "$HERE/svq-query-tool" "$DEST"
echo "installed $DEST"
