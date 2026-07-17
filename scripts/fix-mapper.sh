#!/usr/bin/env bash
# Force-sync models.py from git source and restart API (fixes stale dual-FK mapper)
set -euo pipefail

SRC="${SRC:-/opt/aibots-src}"
APP="${APP:-/opt/aibots}"

if [[ ! -f "$SRC/apps/api/app/models.py" ]]; then
  echo "Missing $SRC — run: git clone https://github.com/xceedconnections/aibots.git $SRC"
  exit 1
fi

echo "==> Pull latest"
git -C "$SRC" pull origin main

echo "==> Copy models.py + compose"
cp -f "$SRC/apps/api/app/models.py" "$APP/apps/api/app/models.py"
cp -f "$SRC/docker-compose.yml" "$APP/docker-compose.yml"
cp -f "$SRC/apps/api/app/"*.py "$APP/apps/api/app/" 2>/dev/null || true
cp -f "$SRC/apps/api/app/routers/"*.py "$APP/apps/api/app/routers/" 2>/dev/null || true
cp -f "$SRC/apps/api/app/services/"*.py "$APP/apps/api/app/services/" 2>/dev/null || true

echo "==> Verify next_question_id is NOT a ForeignKey in source file"
if grep -n 'next_question_id.*ForeignKey' "$APP/apps/api/app/models.py"; then
  echo "ERROR: models.py still has ForeignKey on next_question_id"
  exit 1
fi
echo "OK: no ForeignKey on next_question_id"

echo "==> Drop obsolete DB FK constraint (if any)"
docker exec -i aibots-postgres psql -U aibots -d aibots <<'SQL' || true
ALTER TABLE answers DROP CONSTRAINT IF EXISTS answers_next_question_id_fkey;
SQL

echo "==> Clear pycache + recreate API"
cd "$APP"
find apps/api -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
docker compose up -d --force-recreate api

echo "==> Wait + test login"
sleep 5
curl -s http://127.0.0.1:8000/health || true
echo
curl -s -X POST http://127.0.0.1:8000/auth/reset-admin || true
echo
curl -s -X POST http://127.0.0.1:8000/auth/login/json \
  -H 'Content-Type: application/json' \
  -d '{"email":"xceedconnections@gmail.com","password":"Openaccount@123"}'
echo
echo "==> Done. If token above, login works."
