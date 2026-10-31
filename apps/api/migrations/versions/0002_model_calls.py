"""model_calls: one row per LLM call (observability + cost + replay), never stores the API key

Revision ID: 0002
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE model_calls (
      id               uuid PRIMARY KEY,
      tenant_id        text NOT NULL DEFAULT 'default',
      run_id           uuid REFERENCES check_runs(id) ON DELETE SET NULL,
      stage            text NOT NULL,                 -- tier_b_judge | suggest_fix
      rule_id          text,
      provider         text NOT NULL,
      model            text NOT NULL,
      prompt_version   text NOT NULL,
      prompt_sha256    char(64) NOT NULL,
      request_id       text,
      tokens_in        int,
      tokens_out       int,
      reasoning_tokens int,
      latency_ms       int,
      cache_hit        boolean NOT NULL DEFAULT false,
      error_code       text,
      created_at       timestamptz NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE INDEX model_calls_run_idx ON model_calls (run_id)")
    op.execute("CREATE INDEX model_calls_stage_idx ON model_calls (tenant_id, stage, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS model_calls")
