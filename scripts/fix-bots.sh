#!/usr/bin/env bash
# Force-sync API code + seed ACA Qualifier bot
set -euo pipefail

SRC="${SRC:-/opt/aibots-src}"
APP="${APP:-/opt/aibots}"

cd "$SRC"
git fetch origin main
git reset --hard origin/main

echo "==> Sync API app code"
mkdir -p "$APP/apps/api/app/routers" "$APP/apps/api/app/services"
cp -f "$SRC/apps/api/app/"*.py "$APP/apps/api/app/"
cp -f "$SRC/apps/api/app/routers/"*.py "$APP/apps/api/app/routers/"
cp -f "$SRC/apps/api/app/services/"*.py "$APP/apps/api/app/services/"
cp -f "$SRC/docker-compose.yml" "$APP/docker-compose.yml"

echo "==> Verify no Question.answers relationship"
if grep -n 'Question.answers\|answers = relationship' "$APP/apps/api/app/models.py"; then
  echo "ERROR: models still declare Answer relationship"
  exit 1
fi
echo "OK: no Answer ORM relationship"

echo "==> Drop obsolete FK"
docker exec -i aibots-postgres psql -U aibots -d aibots <<'SQL' || true
ALTER TABLE answers DROP CONSTRAINT IF EXISTS answers_next_question_id_fkey;
SQL

cd "$APP"
find apps/api -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
docker compose up -d --force-recreate api
sleep 6

echo "==> Health"
curl -s http://127.0.0.1:8000/health; echo

echo "==> Reset admin"
curl -s -X POST http://127.0.0.1:8000/auth/reset-admin; echo

TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/login/json \
  -H 'Content-Type: application/json' \
  -d '{"email":"xceedconnections@gmail.com","password":"Openaccount@123"}' \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

echo "Token length: ${#TOKEN}"

echo "==> Seed sample bot"
curl -s -X POST http://127.0.0.1:8000/bots/seed-sample \
  -H "Authorization: Bearer $TOKEN"; echo

echo "==> List bots"
curl -s http://127.0.0.1:8000/bots \
  -H "Authorization: Bearer $TOKEN"; echo

echo "Done. Refresh portal Bots page."
