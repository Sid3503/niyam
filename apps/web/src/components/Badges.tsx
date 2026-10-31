import { cn } from "@/lib/utils";
import { APPROVAL_TONE, DOC_TONE, FINDING_LABEL, FINDING_TONE, fmtDate, humanize, STATUS_LABEL, type Tone } from "@/lib/format";
import type { ApprovalStatus, DocStatus, Enforceability, FindingStatus, Provenance, RuleStatus, TextBasis } from "@/lib/types";

const PROVENANCE_LABEL: Record<Provenance, string> = {
  official: "official",
  official_html_extract: "official · html extract",
  mirror: "mirror",
  user_downloaded: "user downloaded",
};

const TONE_CLASS: Record<Tone, string> = { ok: "chip-ok", warn: "chip-warn", bad: "chip-bad", neutral: "" };

export function Chip({ tone = "neutral", children, title }: { tone?: Tone; children: React.ReactNode; title?: string }) {
  return <span className={cn("chip chip-dot", TONE_CLASS[tone])} title={title}>{children}</span>;
}

/** Green only for `current`. Missing evidence is amber, never green. */
export function FindingChip({ status }: { status: FindingStatus }) {
  return <Chip tone={FINDING_TONE[status]}>{FINDING_LABEL[status]}</Chip>;
}
export function DocStatusChip({ status }: { status: DocStatus }) {
  return <Chip tone={DOC_TONE[status]}>{status}</Chip>;
}
export function ApprovalChip({ status }: { status: ApprovalStatus }) {
  return <Chip tone={APPROVAL_TONE[status]}>{status}</Chip>;
}

/** `draft` reads amber ("waiting on a human"); only `active` is green. Never implies approval. */
export function StatusBadge({ status }: { status: RuleStatus }) {
  const tone = status === "active" ? "chip-ok" : status === "draft" || status === "in_review" ? "chip-warn" : "";
  return <span className={cn("chip chip-dot", tone)} title={status === "draft" ? "Draft: pending approval, not approved by a human" : undefined}>{STATUS_LABEL[status]}</span>;
}

export function ProvenanceBadge({ provenance }: { provenance: Provenance }) {
  const title: Record<Provenance, string> = {
    official: "Official regulator document",
    official_html_extract: "Text extracted from the regulator's official web page",
    mirror: "Mirror copy; not the regulator's own publication",
    user_downloaded: "Downloaded by a user; official URL unknown",
  };
  return (
    <span className={cn("chip chip-plain", provenance === "mirror" || provenance === "user_downloaded" ? "chip-warn" : "")} title={title[provenance]}>
      {PROVENANCE_LABEL[provenance]}
    </span>
  );
}

export function OcrBadge({ basis }: { basis?: TextBasis }) {
  if (basis !== "ocr") return null;
  return <span className="chip" title="Text was read by OCR; quotes cannot be checked against the page image">OCR</span>;
}

export function EnforceChip({ enforceability, effective }: { enforceability: Enforceability; effective: string | null }) {
  if (enforceability === "not_yet_enforceable") {
    return <span className="chip chip-plain">not yet enforceable · effective {fmtDate(effective)}</span>;
  }
  return <span className="chip chip-plain">live · effective {fmtDate(effective)}</span>;
}

export function Tag({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("chip chip-plain", className)}>{children}</span>;
}

export function Severity({ value }: { value: string }) {
  return <span className={cn("chip", value === "critical" && "text-[var(--foreground)]")}>{humanize(value)}</span>;
}
