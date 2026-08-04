#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

fail() {
  echo "release preflight failed: $1" >&2
  exit 1
}

test -f landing/dist/index.html || fail "landing/dist/index.html is missing; run the Landing build"
test -f frontend/src/lib/queryClient.ts || fail "frontend QueryClient module is missing"
test -f backend/.env || fail "backend/.env is missing; copy and complete backend/.env.example"

head_count="$(cd backend && alembic heads | grep -c '(head)$')"
test "$head_count" -eq 1 || fail "Alembic must have exactly one head (found $head_count)"

command -v docker >/dev/null 2>&1 || fail "Docker CLI is unavailable"
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is unavailable"
docker compose --env-file .env -f docker-compose.yml config -q
docker compose --env-file .env -f docker-compose.prod.yml config -q

echo "release preflight passed"
