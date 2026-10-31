/** Types mirror docs/REVAMP-CONTRACT.md (v0.2). Optional fields are those the contract leaves loose. */

export type RuleStatus = "draft" | "in_review" | "active" | "superseded" | "retired" | "rejected";
export type Provenance = "official" | "official_html_extract" | "mirror" | "user_downloaded";
export type TextBasis = "native" | "ocr";
export type Enforceability = "live" | "not_yet_enforceable";

export type FindingStatus = "current" | "outdated" | "missing" | "contradiction" | "review";
export type Severity = "low" | "medium" | "high" | "critical";
export type ApprovalStatus = "pending" | "approved" | "rejected" | "deferred";
export type ApprovalKind = "rule" | "fix";
export type DocStatus = "new" | "changed" | "unchanged" | "reviewed";
export type Decision = "approve" | "reject" | "defer";

export interface RuleSummary {
  id: string;
  version: number;
  title: string;
  status: RuleStatus;
  severity: string;
  tier: string;
  check_type: string;
  effective_from: string | null;
  effective_to?: string | null;
  enforceability: Enforceability;
  regulator: string;
  source: { document: string; file?: string; provenance: Provenance; text_basis?: TextBasis };
  open_issues_count: number;
  aliases: string[];
  approval_id?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  scan_active?: boolean;
}

export interface RuleDetail {
  id: string;
  version: number;
  title: string;
  status: RuleStatus;
  obligation: string;
  severity: string;
  owner?: string;
  confidence_threshold?: number;
  evidence_required?: string;
  effective_from: string | null;
  effective_to?: string | null;
  supersedes?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  aliases?: string[];
  notes?: string[];
  open_issues?: string[];
  versions?: { version: number; status: string; effective_from: string | null }[];
  source: {
    regulator?: string;
    document: string;
    reference?: string;
    issue_date?: string;
    document_status?: string;
    file?: string;
    sha256?: string;
    text_basis?: TextBasis;
    provenance: Provenance;
    locator?: string;
    quotes?: string[];
    url?: string;
  };
  check: { type: string; tier: string; config?: Record<string, unknown> };
  scope?: Record<string, string[]>;
  enforceability?: Enforceability;
  validation: { ok: boolean; errors: string[]; warnings: string[]; quotes_verified: boolean };
}

export interface ProductFact {
  id: string;
  category: string;
  title: string;
  statement: string;
  value: unknown;
  unit: string | null;
  owner: string;
  source_label: string;
}

export interface ByStatus {
  current: number;
  outdated: number;
  missing: number;
  contradiction: number;
  review: number;
}

export interface Overview {
  documents_scanned: number;
  open_findings: number;
  fixes_awaiting_approval: number;
  rules_pending_approval: number;
  citation_coverage: number;
  rules: { active: number; draft: number };
  next_action: { label: string; route: string; kind: string };
  /** v0.3. Optional so an older backend still renders (see lib/overview.ts). */
  documents_total?: number;
  steps?: PackStep[];
  pack?: PackClock;
}

export type PackStepKey = "circular" | "rules" | "scan" | "fixes" | "retest" | "evidence";
export interface PackStep { key: PackStepKey; label: string; state: "done" | "current" | "todo"; detail: string; route: string }
export interface PackClock {
  circular_title: string | null;
  started_at: string | null;
  approved_at: string | null;
  elapsed_seconds: number | null;
  documents_total: number;
  documents_affected: number;
  documents_clear: number;
}

export interface Document {
  id: string;
  title: string;
  doc_type: string;
  product: string;
  owner: string;
  merchant: string | null;
  channel: string | null;
  version: number;
  last_modified: string;
  status: DocStatus;
  demo_data: boolean;
  open_findings: number;
  by_status: ByStatus;
  last_reviewed_at: string | null;
  source_path: string;
  /** v0.3 */
  format?: DocFormat;
  pages?: number | null;
  duration_seconds?: number | null;
}

export interface Clause {
  idx: number;
  locator: string;
  text: string;
  start: number;
  end: number;
}

export interface RuleSource {
  document: string;
  reference?: string;
  locator?: string;
  quote?: string;
  regulator?: string;
  provenance?: Provenance;
}
export interface FactSource {
  fact_id: string;
  title: string;
  statement: string;
  label: string;
}

export interface Finding {
  id: string;
  version_id: string;
  clause_idx: number | null;
  locator: string;
  quote: string | null;
  span: [number, number] | null;
  status: FindingStatus;
  severity: Severity;
  confidence: number;
  reason: string;
  rule_id: string | null;
  rule_version: number | null;
  rule_status: string | null;
  fact_id: string | null;
  source: RuleSource | FactSource;
  tier: string;
  suggested_fix: { wording: string; rationale: string; validated: boolean } | null;
  approval: { id: string; status: ApprovalStatus } | null;
  decision: null | "approved" | "rejected" | "deferred";
  needs_human: boolean;
  /** v0.3: 1-based page, bbox in PDF points (origin top-left), audio seconds. */
  page?: number | null;
  bbox?: [number, number, number, number] | null;
  audio_time?: [number, number] | null;
}

export interface VersionInfo {
  id: string;
  version: number;
  sha256: string;
  created_at: string;
  trigger: string;
  open_findings: number;
}

export interface DocumentDetail {
  document: Document;
  version: { id: string; version: number; sha256: string; content: string; created_at: string; trigger: string };
  clauses: Clause[];
  findings: Finding[];
  versions: VersionInfo[];
  rule_fingerprint: string;
  workbench?: WorkbenchInfo | null;
  voice?: VoiceInfo | null;
}

export interface ScanResult {
  scan_id: string;
  trigger: string;
  started_at: string;
  discovered: number;
  reviewed: number;
  skipped: number;
  documents: { document_id: string; title: string; outcome: string; findings: number }[];
}

export interface UploadBody {
  title: string;
  doc_type: string;
  product: string;
  owner: string;
  content: string;
}

export interface RetestSide {
  open: number;
  by_status: Partial<ByStatus>;
}
export interface RetestResult {
  document: DocumentDetail;
  comparison: { before: RetestSide; after: RetestSide; resolved: string[]; remaining: string[]; new: string[] };
  passed: boolean;
}

export interface Approval {
  id: string;
  kind: ApprovalKind;
  status: ApprovalStatus;
  severity: Severity;
  confidence: number | null;
  title: string;
  created_at: string;
  decided_at: string | null;
  decided_by: string | null;
  reason: string | null;
  document: { id: string; title: string } | null;
  clause: { locator: string; text: string } | null;
  finding_id: string | null;
  current_wording: string | null;
  proposed_wording: string | null;
  rule: { id: string; version: number; title: string; obligation: string; tier: string; effective_from: string | null; status: string } | null;
  source: { document: string; reference?: string; locator?: string; quote?: string; provenance?: string; quote_verified: boolean };
}

export interface CircularBody {
  url?: string;
  text?: string;
  title?: string;
  institution: string;
  product_area: string;
  effective_date?: string;
}
export interface CircularResult {
  source: { id: string; title: string; institution: string; url: string | null; sha256: string; retrieved_at: string; chars: number };
  drafts: { approval_id: string; rule_id: string; title: string; source_quote: string; quote_verified: boolean; obligation: string; severity: string; tier: string; product: string; claim_type: string }[];
  notes: string[];
}

export interface ImpactListItem {
  rule_id: string;
  version: number;
  title: string;
  status: RuleStatus;
  effective_from: string | null;
  previous_version: number | null;
  affected_count: number | null;
}

export interface Impact {
  rule: { id: string; version: number; title: string; status: RuleStatus; effective_from: string | null; obligation: string; source: { document: string; reference?: string; quote?: string } };
  previous: { version: number; status: string; effective_from: string | null; obligation: string; changes: string[] } | null;
  dry_run: boolean;
  affected: {
    document_id: string;
    title: string;
    owner: string;
    version: number;
    clause_locator: string;
    quote: string;
    status: FindingStatus;
    reason: string;
    matched_on: string[];
    change_note: string;
    proposed_wording: string | null;
    task: { owner: string; title: string; state: "open" | "done" };
  }[];
  scanned_documents: number;
}

export interface EvidenceListItem {
  document_id: string;
  title: string;
  versions: number;
  findings: number;
  approvals: number;
  last_event_at: string | null;
  retest: "passed" | "failed" | "none";
}

export interface EvidenceRecord {
  document: Document;
  original: { version: number; sha256: string; content_preview: string };
  events: { seq: number; ts: string; actor: string; action: string; summary: string; payload: unknown }[];
  findings: Finding[];
  approvals: Approval[];
  retests: { ts: string; passed: boolean; before: RetestSide; after: RetestSide }[];
  notifications: { ts: string; to: string; channel: string; subject: string }[];
  chain_ok: boolean;
  /** v0.3 */
  format?: DocFormat;
  hashes?: { original: { version: number; sha256: string }; current: { version: number; sha256: string } };
}

export function isFactSource(s: Finding["source"]): s is FactSource {
  return "fact_id" in s;
}

/* ── v0.3: PDF workbench, voice note, compare (docs/REVAMP-CONTRACT.md addendum) ── */
export type DocFormat = "markdown" | "pdf" | "voice";
export type ApplyMethod = "redact_rewrite" | "rasterize_page" | "append_text";

export interface WorkbenchInfo {
  pdf_url: string;
  pages: number;
  page_sizes: [number, number][];
}
export interface VoiceSentence {
  idx: number;
  start: number;
  end: number;
  text: string;
  start_char: number;
  end_char: number;
}
export interface VoiceInfo {
  audio_url: string;
  duration_seconds: number;
  language: string;
  transcript_original: string;
  transcript_en: string;
  sentences: VoiceSentence[];
  stt: { provider: string; model: string };
  timing_note: string;
}
export interface VoiceSample {
  name: string;
  title: string;
  language: string;
  duration_seconds: number;
  audio_url: string;
  expected: string;
}
export interface ApplyEdit {
  finding_id: string;
  wording: string;
}
export interface ApplyResult {
  committed: boolean;
  strategy: { finding_id: string; method: ApplyMethod }[];
  stale_text_remains: { finding_id: string; quote: string }[];
  sha256_before: string;
  sha256_after: string;
  comparison: RetestResult["comparison"];
  preview_url: string | null;
  document: DocumentDetail | null;
}
export interface CompareResult {
  from: { version_id: string; version: number; sha256: string };
  to: { version_id: string; version: number; sha256: string };
  pages: { page: number; from_url: string; to_url: string; changed: boolean }[];
}
