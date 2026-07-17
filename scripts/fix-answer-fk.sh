#!/usr/bin/env bash
# Drop obsolete answers.next_question_id FK if it exists (dual-FK mapper bug)
set -euo pipefail

echo "==> Dropping answers_next_question_id_fkey if present"
docker exec -i aibots-postgres psql -U aibots -d aibots <<'SQL'
ALTER TABLE answers DROP CONSTRAINT IF EXISTS answers_next_question_id_fkey;
ALTER TABLE answers DROP CONSTRAINT IF EXISTS fk_answers_next_question_id;
SQL

echo "==> Done. Restart API:"
echo "    docker compose restart api"
