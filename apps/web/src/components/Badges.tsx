import { Hint } from "@/components/Hint";
import { HINT, severityHint } from "@/lib/hints";
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
  const el = <span className={cn("chip chip-dot", TONE_CLASS[tone])}>{children}</span>;
  return title ? <Hint text={title}>{el}</Hint> : el;
}

/** Green only for `current`. Missing evidence is amber, never green. */
export function FindingChip({ status }: { status: FindingStatus }) {
  return <Chip tone={FINDING_TONE[status]} title={HINT.finding[status]}>{FINDING_LABEL[status]}</Chip>;
}
export function DocStatusChip({ status }: { status: DocStatus }) {
  return <Chip tone={DOC_TONE[status]} title={HINT.doc[status]}>{status}</Chip>;
}
export function ApprovalChip({ status }: { status: ApprovalStatus }) {
  return <Chip tone={APPROVAL_TONE[status]} title={HINT.approval[status]}>{status}</Chip>;
}

/** `draft` reads amber ("waiting on a human"); only `active` is green. Never implies approval. */
export function StatusBadge({ status }: { status: RuleStatus }) {
  const tone = status === "active" ? "chip-ok" : status === "draft" || status === "in_review" ? "chip-warn" : "";
  return (
    <Hint text={HINT.rule[status]}>
      <span className={cn("chip chip-dot", tone)}>{STATUS_LABEL[status]}</span>
    </Hint>
  );
}

export function ProvenanceBadge({ provenance }: { provenance: Provenance }) {
  return (
    <Hint text={HINT.provenance[provenance]}>
      <span className={cn("chip chip-plain", provenance === "mirror" || provenance === "user_downloaded" ? "chip-warn" : "")}>
        {PROVENANCE_LABEL[provenance]}
      </span>
    </Hint>
  );
}

export function OcrBadge({ basis }: { basis?: TextBasis }) {
  if (basis !== "ocr") return null;
  return <Hint text={HINT.ocr}><span className="chip">OCR</span></Hint>;
}

export function EnforceChip({ enforceability, effective }: { enforceability: Enforceability; effective: string | null }) {
  if (enforceability === "not_yet_enforceable") {
    return <Hint text={HINT.enforceLater}><span className="chip chip-plain">not yet enforceable · effective {fmtDate(effective)}</span></Hint>;
  }
  return <Hint text={HINT.enforceLive}><span className="chip chip-plain">live · effective {fmtDate(effective)}</span></Hint>;
}

export function Tag({ children, className, title }: { children: React.ReactNode; className?: string; title?: string }) {
  const el = <span className={cn("chip chip-plain", className)}>{children}</span>;
  return title ? <Hint text={title}>{el}</Hint> : el;
}

export function Severity({ value }: { value: string }) {
  const el = <span className={cn("chip", value === "critical" && "text-[var(--foreground)]")}>{humanize(value)}</span>;
  return <Hint text={severityHint(value)}>{el}</Hint>;
}
