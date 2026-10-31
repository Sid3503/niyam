#!/usr/bin/env bash
# Reset the document-review demo to its starting state: all rule cards back to draft, circular-derived drafts removed,
# no documents/findings/approvals/scans. The audit log is append-only by design and is NOT cleared.
# Usage: tools/reset_demo.sh   (runs psql inside the niyam-db-1 container; no host psql needed)
set -euo pipefail
cd "$(dirname "$0")/.."
docker exec -i "${NIYAM_DB_CONTAINER:-niyam-db-1}" psql -U niyam -d niyam -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
ALTER TABLE rule_cards DISABLE TRIGGER rule_cards_active_guard;
DELETE FROM approvals; DELETE FROM impact_tasks; DELETE FROM notifications; DELETE FROM retests;
DELETE FROM sales_documents;           -- cascades versions, reviews, findings
DELETE FROM scans; DELETE FROM circular_sources;
DELETE FROM rule_cards WHERE (card->'source'->>'file') IS NULL;
UPDATE rule_cards SET status='draft', card = jsonb_set(jsonb_set(jsonb_set(card,'{status}','"draft"'),'{approved_by}','null'),'{approved_at}','null');
ALTER TABLE rule_cards ENABLE TRIGGER rule_cards_active_guard;
COMMIT;
SQL
echo "demo reset. Restart the API (or call GET /api/v1/approvals) to recreate the draft-rule approval items."
