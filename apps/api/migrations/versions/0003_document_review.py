"""document review: library, versions, reviews, findings, approvals, scans, circular sources, notifications, retests

Revision ID: 0003
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

DDL = [
    """
    CREATE TABLE sales_documents (
      id           uuid PRIMARY KEY,
      tenant_id    text NOT NULL DEFAULT 'default',
      source_path  text NOT NULL,
      title        text NOT NULL,
      doc_type     text NOT NULL CHECK (doc_type IN ('proposal','agreement','order_form','brochure','pitch_deck','onboarding')),
      product      text NOT NULL,
      owner        text NOT NULL,
      merchant     text,
      channel      text,
      created_at   timestamptz NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, source_path)
    )""",
    """
    CREATE TABLE document_versions (
      id           uuid PRIMARY KEY,
      tenant_id    text NOT NULL DEFAULT 'default',
      document_id  uuid NOT NULL REFERENCES sales_documents(id) ON DELETE CASCADE,
      version      int  NOT NULL,
      sha256       char(64) NOT NULL,
      content      text NOT NULL,
      trigger      text NOT NULL CHECK (trigger IN ('scan','upload','retest')),
      source_mtime timestamptz,
      created_at   timestamptz NOT NULL DEFAULT now(),
      UNIQUE (document_id, version)
    )""",
    # one row per (version, rule fingerprint): the same content is not reviewed again against the same active rules + facts
    """
    CREATE TABLE doc_reviews (
      id            uuid PRIMARY KEY,
      tenant_id     text NOT NULL DEFAULT 'default',
      version_id    uuid NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
      fingerprint   char(64) NOT NULL,
      reviewed_at   timestamptz NOT NULL DEFAULT now(),
      trigger       text NOT NULL,
      engine_version text NOT NULL,
      rules         jsonb NOT NULL,
      duration_ms   int NOT NULL DEFAULT 0,
      UNIQUE (version_id, fingerprint)
    )""",
    """
    CREATE TABLE findings (
      id            uuid PRIMARY KEY,
      tenant_id     text NOT NULL DEFAULT 'default',
      review_id     uuid NOT NULL REFERENCES doc_reviews(id) ON DELETE CASCADE,
      version_id    uuid NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
      clause_idx    int,
      locator       text NOT NULL,
      quote         text,
      span_start    int,
      span_end      int,
      status        text NOT NULL CHECK (status IN ('current','outdated','missing','contradiction','review')),
      severity      text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
      confidence    real NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
      reason        text NOT NULL,
      rule_id       text,
      rule_version  int,
      rule_status   text,
      fact_id       text,
      source        jsonb NOT NULL,
      tier          text NOT NULL DEFAULT 'A',
      suggested_fix jsonb,
      needs_human   boolean NOT NULL DEFAULT false,
      created_at    timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT finding_has_source CHECK (rule_id IS NOT NULL OR fact_id IS NOT NULL),
      CONSTRAINT finding_span_pair CHECK ((span_start IS NULL) = (span_end IS NULL)),
      -- the core invariant: missing evidence is never 'current'
      CONSTRAINT current_has_quote CHECK (status <> 'current' OR quote IS NOT NULL)
    )""",
    "CREATE INDEX findings_version_idx ON findings (version_id, clause_idx)",
    """
    CREATE TABLE approvals (
      id            uuid PRIMARY KEY,
      tenant_id     text NOT NULL DEFAULT 'default',
      kind          text NOT NULL CHECK (kind IN ('rule','fix')),
      status        text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','deferred')),
      severity      text NOT NULL CHECK (severity IN ('low','medium','high','critical')),
      confidence    real,
      title         text NOT NULL,
      payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
      finding_id    uuid REFERENCES findings(id) ON DELETE SET NULL,
      document_id   uuid REFERENCES sales_documents(id) ON DELETE SET NULL,
      rule_id       text,
      rule_version  int,
      created_at    timestamptz NOT NULL DEFAULT now(),
      decided_at    timestamptz,
      decided_by    text,
      reason        text,
      CONSTRAINT decided_has_actor CHECK (status IN ('pending') OR (decided_by IS NOT NULL AND decided_at IS NOT NULL))
    )""",
    "CREATE UNIQUE INDEX approvals_rule_open_idx ON approvals (tenant_id, rule_id, rule_version) WHERE kind='rule' AND status IN ('pending','deferred')",
    "CREATE UNIQUE INDEX approvals_fix_open_idx ON approvals (finding_id) WHERE kind='fix' AND status IN ('pending','deferred')",
    """
    CREATE TABLE scans (
      id          uuid PRIMARY KEY,
      tenant_id   text NOT NULL DEFAULT 'default',
      trigger     text NOT NULL,
      started_at  timestamptz NOT NULL DEFAULT now(),
      finished_at timestamptz,
      discovered  int NOT NULL DEFAULT 0,
      reviewed    int NOT NULL DEFAULT 0,
      skipped     int NOT NULL DEFAULT 0,
      detail      jsonb NOT NULL DEFAULT '[]'::jsonb,
      actor       text NOT NULL DEFAULT 'api'
    )""",
    """
    CREATE TABLE circular_sources (
      id             uuid PRIMARY KEY,
      tenant_id      text NOT NULL DEFAULT 'default',
      title          text NOT NULL,
      institution    text NOT NULL,
      product_area   text,
      url            text,
      kb_document_id uuid,
      sha256         char(64) NOT NULL,
      text           text NOT NULL,
      effective_date date,
      retrieved_at   timestamptz NOT NULL DEFAULT now(),
      actor          text NOT NULL DEFAULT 'api'
    )""",
    """
    CREATE TABLE notifications (
      id          uuid PRIMARY KEY,
      tenant_id   text NOT NULL DEFAULT 'default',
      document_id uuid NOT NULL REFERENCES sales_documents(id) ON DELETE CASCADE,
      ts          timestamptz NOT NULL DEFAULT now(),
      recipient   text NOT NULL,
      channel     text NOT NULL DEFAULT 'in_app',
      subject     text NOT NULL,
      payload     jsonb NOT NULL DEFAULT '{}'::jsonb
    )""",
    """
    CREATE TABLE retests (
      id            uuid PRIMARY KEY,
      tenant_id     text NOT NULL DEFAULT 'default',
      document_id   uuid NOT NULL REFERENCES sales_documents(id) ON DELETE CASCADE,
      from_version  uuid NOT NULL REFERENCES document_versions(id),
      to_version    uuid NOT NULL REFERENCES document_versions(id),
      ts            timestamptz NOT NULL DEFAULT now(),
      passed        boolean NOT NULL,
      before        jsonb NOT NULL,
      after         jsonb NOT NULL,
      actor         text NOT NULL
    )""",
    """
    CREATE TABLE impact_tasks (
      id          uuid PRIMARY KEY,
      tenant_id   text NOT NULL DEFAULT 'default',
      document_id uuid NOT NULL REFERENCES sales_documents(id) ON DELETE CASCADE,
      rule_id     text NOT NULL,
      rule_version int NOT NULL,
      owner       text NOT NULL,
      title       text NOT NULL,
      state       text NOT NULL DEFAULT 'open' CHECK (state IN ('open','done')),
      created_at  timestamptz NOT NULL DEFAULT now(),
      UNIQUE (document_id, rule_id, rule_version)
    )""",
]


def upgrade() -> None:
    for s in DDL:
        op.execute(s)


def downgrade() -> None:
    for t in ["impact_tasks", "retests", "notifications", "circular_sources", "scans", "approvals", "findings", "doc_reviews",
              "document_versions", "sales_documents"]:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
