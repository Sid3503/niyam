"""initial schema: documents, units (FTS+trigram), rule cards, check runs, verdicts, audit log

Revision ID: 0001
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = [
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    # reserved for the optional dense-retrieval add-on (measured before adoption); optional so plain Postgres images still work
    """DO $$ BEGIN
         IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
           CREATE EXTENSION IF NOT EXISTS vector;
         END IF;
       END $$""",
    """
    CREATE TABLE documents (
      id              uuid PRIMARY KEY,
      tenant_id       text NOT NULL DEFAULT 'default',
      corpus_kind     text NOT NULL CHECK (corpus_kind IN ('regulation','surface')),
      sha256          char(64) NOT NULL,
      file_path       text NOT NULL,
      title           text NOT NULL,
      regulator       text NOT NULL,
      doc_type        text NOT NULL,
      reference_no    text,
      issue_date      date,
      status          text NOT NULL DEFAULT 'unknown'
                      CHECK (status IN ('in_force','superseded','repealed','draft','recommendation','unknown')),
      provenance      text NOT NULL
                      CHECK (provenance IN ('official','official_html_extract','mirror','user_downloaded','surface_site','unknown')),
      text_basis      text NOT NULL DEFAULT 'native' CHECK (text_basis IN ('native','ocr')),
      source_url      text,
      pages           int,
      unit_count      int NOT NULL DEFAULT 0,
      extraction_status text NOT NULL CHECK (extraction_status IN ('ok','empty','ocr_sidecar','failed')),
      extraction_note text,
      manifest_note   text,
      created_at      timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, sha256)
    )""",
    "CREATE INDEX documents_kind_reg_idx ON documents (tenant_id, corpus_kind, regulator)",
    """
    CREATE TABLE units (
      id            uuid PRIMARY KEY,
      tenant_id     text NOT NULL DEFAULT 'default',
      document_id   uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      ordinal       int  NOT NULL,
      page          int,
      kind          text NOT NULL CHECK (kind IN ('heading','paragraph','table_row','list_item')),
      locator       text,
      heading_path  text,
      text          text NOT NULL,
      text_sha256   char(64) NOT NULL,
      char_count    int  NOT NULL,
      tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
      UNIQUE (document_id, ordinal)
    )""",
    "CREATE INDEX units_tsv_idx  ON units USING GIN (tsv)",
    "CREATE INDEX units_trgm_idx ON units USING GIN (text gin_trgm_ops)",
    "CREATE INDEX units_doc_idx  ON units (document_id, ordinal)",
    """
    CREATE TABLE ingest_runs (
      id          uuid PRIMARY KEY,
      tenant_id   text NOT NULL DEFAULT 'default',
      started_at  timestamptz NOT NULL DEFAULT now(),
      finished_at timestamptz,
      stats       jsonb NOT NULL DEFAULT '{}'::jsonb
    )""",
    """
    CREATE TABLE rule_cards (
      tenant_id      text NOT NULL DEFAULT 'default',
      id             text NOT NULL,
      version        int  NOT NULL CHECK (version >= 1),
      status         text NOT NULL CHECK (status IN ('draft','in_review','active','superseded','retired','rejected')),
      title          text NOT NULL,
      severity       text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
      tier           text NOT NULL CHECK (tier IN ('A','B','A+B')),
      check_type     text NOT NULL,
      effective_from date NOT NULL,
      regulator      text NOT NULL,
      card           jsonb NOT NULL,
      card_sha256    char(64) NOT NULL,
      validation     jsonb NOT NULL,
      loaded_at      timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (tenant_id, id, version),
      -- only a named human may make a card active
      CONSTRAINT active_needs_approver CHECK (status <> 'active' OR (card->>'approved_by') IS NOT NULL)
    )""",
    """
    CREATE FUNCTION rule_cards_active_immutable() RETURNS trigger AS $$
    BEGIN
      IF OLD.status = 'active' AND NEW.card_sha256 <> OLD.card_sha256 THEN
        RAISE EXCEPTION 'rule card %.v% is active and immutable: create a new version', OLD.id, OLD.version;
      END IF;
      RETURN NEW;
    END $$ LANGUAGE plpgsql""",
    "CREATE TRIGGER rule_cards_active_guard BEFORE UPDATE ON rule_cards FOR EACH ROW EXECUTE FUNCTION rule_cards_active_immutable()",
    """
    CREATE TABLE check_runs (
      id             uuid PRIMARY KEY,
      tenant_id      text NOT NULL DEFAULT 'default',
      created_at     timestamptz NOT NULL DEFAULT now(),
      as_of          date NOT NULL,
      text_sha256    char(64) NOT NULL,
      text           text,
      facts          jsonb NOT NULL DEFAULT '{}'::jsonb,
      rule_filter    jsonb,
      summary        jsonb NOT NULL,
      engine_version text NOT NULL,
      cards_snapshot jsonb NOT NULL,
      duration_ms    int NOT NULL,
      actor          text NOT NULL DEFAULT 'api'
    )""",
    "CREATE INDEX check_runs_created_idx ON check_runs (tenant_id, created_at DESC)",
    """
    CREATE TABLE verdicts (
      id             uuid PRIMARY KEY,
      tenant_id      text NOT NULL DEFAULT 'default',
      run_id         uuid NOT NULL REFERENCES check_runs(id) ON DELETE CASCADE,
      rule_id        text NOT NULL,
      rule_version   int  NOT NULL,
      rule_status    text NOT NULL,
      verdict        text NOT NULL CHECK (verdict IN ('pass','fail','review','not_applicable','not_yet_enforceable')),
      tier           text NOT NULL,
      confidence     real NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
      quote          text,
      span_start     int,
      span_end       int,
      reason         text NOT NULL,
      checks         jsonb NOT NULL DEFAULT '[]'::jsonb,
      source         jsonb NOT NULL DEFAULT '{}'::jsonb,
      human_decision jsonb,
      created_at     timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT span_pair CHECK ((span_start IS NULL) = (span_end IS NULL))
    )""",
    "CREATE INDEX verdicts_run_idx ON verdicts (run_id)",
    """
    CREATE TABLE audit_events (
      seq         bigserial PRIMARY KEY,
      tenant_id   text NOT NULL DEFAULT 'default',
      ts          timestamptz NOT NULL DEFAULT now(),
      actor       text NOT NULL,
      action      text NOT NULL,
      object_type text NOT NULL,
      object_id   text NOT NULL,
      payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
      prev_hash   char(64) NOT NULL,
      hash        char(64) NOT NULL
    )""",
    """
    CREATE FUNCTION audit_events_append_only() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'audit_events is append-only'; END $$ LANGUAGE plpgsql""",
    "CREATE TRIGGER audit_no_update_delete BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION audit_events_append_only()",
    "CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION audit_events_append_only()",
]


def upgrade() -> None:
    for stmt in DDL:
        op.execute(stmt)


def downgrade() -> None:
    for t in ["audit_events", "verdicts", "check_runs", "rule_cards", "ingest_runs", "units", "documents"]:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS audit_events_append_only()")
    op.execute("DROP FUNCTION IF EXISTS rule_cards_active_immutable()")
