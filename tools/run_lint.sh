#!/usr/bin/env bash
# Incremental ruff gate (P158.10): lint changed Python files, not a no-op.
set -euo pipefail
cd "$(dirname "$0")/.."
base="${SVQ_LINT_BASE:-}"
files=()
if [[ -n "$base" ]] && git rev-parse --verify --quiet "$base" >/dev/null; then
  while IFS= read -r f; do
    [[ -n "$f" && -f "$f" ]] && files+=("$f")
  done < <(git diff --name-only "$base" -- '*.py')
else
  while IFS= read -r f; do
    [[ -n "$f" && -f "$f" ]] && files+=("$f")
  done < <(git diff --name-only HEAD -- '*.py')
fi
if [[ ${#files[@]} -eq 0 ]]; then
  echo "ruff: no changed Python files"
  exit 0
fi
ruff check "${files[@]}"
