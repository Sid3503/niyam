"""document formats: PDF + voice. Blob keys, page geometry, media metadata, workbench trigger, finding geometry

Revision ID: 0004
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sales_documents DROP CONSTRAINT sales_documents_doc_type_check")
    op.execute("""ALTER TABLE sales_documents ADD CONSTRAINT sales_documents_doc_type_check
                  CHECK (doc_type IN ('proposal','agreement','order_form','brochure','pitch_deck','onboarding','voice_note'))""")
    op.execute("ALTER TABLE sales_documents ADD COLUMN format text NOT NULL DEFAULT 'markdown' CHECK (format IN ('markdown','pdf','voice'))")
    op.execute("ALTER TABLE document_versions DROP CONSTRAINT document_versions_trigger_check")
    op.execute("ALTER TABLE document_versions ADD CONSTRAINT document_versions_trigger_check CHECK (trigger IN ('scan','upload','retest','workbench'))")
    op.execute("ALTER TABLE document_versions ADD COLUMN content_type text NOT NULL DEFAULT 'text/markdown'")
    op.execute("ALTER TABLE document_versions ADD COLUMN blob_key text")
    op.execute("ALTER TABLE document_versions ADD COLUMN blob_sha256 char(64)")           # sha256 of the stored FILE bytes (PDF/audio); `sha256` stays the content hash for text
    op.execute("ALTER TABLE document_versions ADD COLUMN page_map jsonb")                  # [{start,end,page,bbox}] one entry per extracted block
    op.execute("ALTER TABLE document_versions ADD COLUMN media jsonb")                     # voice: transcripts, sentences, stt; pdf: page_sizes
    op.execute("ALTER TABLE findings ADD COLUMN page int")
    op.execute("ALTER TABLE findings ADD COLUMN bbox jsonb")
    op.execute("ALTER TABLE findings ADD COLUMN audio_start real")
    op.execute("ALTER TABLE findings ADD COLUMN audio_end real")


def downgrade() -> None:
    for c in ("page", "bbox", "audio_start", "audio_end"):
        op.execute(f"ALTER TABLE findings DROP COLUMN {c}")
    for c in ("content_type", "blob_key", "blob_sha256", "page_map", "media"):
        op.execute(f"ALTER TABLE document_versions DROP COLUMN {c}")
    op.execute("ALTER TABLE sales_documents DROP COLUMN format")
