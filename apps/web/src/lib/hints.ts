/** Short explanations for chips, stats and table headers. Shown in Hint tooltips. */

export const HINT = {
  clock:
    "Starts when a circular is added. Stops when the pack has been scanned, a named person has signed a fix, and there are no open findings left.",
  clockDocuments: "How many proposals, agreements and brochures are in this pack.",
  clockAffected: "Files that still have a stale sentence a merchant could read.",
  clockClear:
    "Files with no open findings. Still check that a named person signed the last fix before you send.",

  statScanned: "Proposals, agreements, brochures and voice notes Niyam has read in this pack.",
  statOpen: "Sentences a merchant could still read. Do not send those files yet.",
  statSigned: "Fixes a named person has already approved. Those can go on the copy.",
  statWaitingFix: "Wording is drafted. Sales does not send until a named person signs.",
  statWaitingRule: "Draft checks. They are not used on decks until a named person approves them.",
  statQuote: "Share of findings that quote the sentence and cite the rule. Anything else is review, never a pass.",

  finding: {
    current: "Matches the rule and your approved terms. This sentence is clear to send.",
    outdated: "Says something an older rule allowed and the current one does not.",
    contradiction: "Says something your approved terms do not allow.",
    missing: "A required statement is not in the document.",
    review: "Niyam is unsure or has no evidence. A person must look. Never a pass.",
  } as const,

  doc: {
    new: "First time this file is in the pack. It has not been reviewed yet.",
    changed: "The file changed since the last scan. Open findings may be new.",
    unchanged: "Same bytes as last time. Findings are from the last review.",
    reviewed: "Niyam has scanned this version.",
  } as const,

  approval: {
    pending: "Waiting for a named person. Do not send yet.",
    approved: "A named person signed this. The wording can go on the copy.",
    rejected: "A named person said no. This wording is not used.",
    deferred: "Parked for later. It is not a yes.",
  } as const,

  rule: {
    draft: "Draft, pending approval. Not used in scans until a named person signs.",
    in_review: "In review. A named person has not approved it yet, so it is not used in scans.",
    active: "Approved. Niyam uses this rule when it scans decks.",
    superseded: "Replaced by a later version. The new version is what scans use.",
    retired: "No longer used in scans.",
    rejected: "A named person rejected this rule. It is not used in scans.",
  } as const,

  provenance: {
    official: "The regulator’s own publication.",
    official_html_extract: "Text taken from the regulator’s official web page.",
    mirror: "A mirror copy, not the regulator’s own publication. Treat the source with care.",
    user_downloaded: "Downloaded by a user. The official URL is unknown.",
  } as const,

  ocr: "Text was read by OCR. Quotes cannot be checked against the page image.",
  enforceLive: "This rule is in force from the date shown.",
  enforceLater: "This rule’s date has not arrived. It is not used in scans yet.",

  tierA: "Tier A: checked by code against a pattern or a product fact.",
  tierB: "Tier B: checked by a language model. A person still decides.",
  confidence: "How sure Niyam is. A named person still decides, even when this is high.",
  severity: {
    critical: "Highest severity. Fix before anything else goes out.",
    high: "A named person should look before this file is sent.",
    medium: "Worth fixing on this version. Not the first thing in the queue.",
    low: "Note it. It should not block a send on its own.",
  } as const,

  scanOn: "Niyam uses this rule when it scans documents.",
  scanOff: "Not live yet. This rule is not used in scans.",
  quoteVerified: "The quote was found as an exact substring of the stored source.",
  quoteUnverified: "The quote was not found in the source. Treat this as a draft.",
  recheckPass: "The suggested wording was tested against the rules that are active now.",
  recheckFail: "This wording has not been re-tested yet. Run a re-test on the copy.",
  needsHuman: "Niyam will not call this a pass. A person has to decide.",
  send: "Sends this wording to Approvals. A named person still has to sign.",
  sendReadOnly: "Open the latest version to send this for approval.",
  sendNoWording: "No suggested wording to send yet.",
  chainOk: "Each log entry is chained to the one before it. Intact means no entry was altered.",
  chainBad: "The audit chain is broken. An entry does not match the one before it.",
  sha: "SHA-256 of this version’s bytes. The original file is never changed.",
  stt: "Speech-to-text used to produce the transcript. Findings are checked against the English text.",
  synthetic: "Synthetic demo data. Not a real merchant file.",
  owner: "Sales owner of this file.",
  openFindings: "Stale sentences still in this version that a merchant could read.",
  fixStatus:
    "Whether a fix is drafted, waiting for a name, approved, rejected or deferred. Approved is what makes a deck safe to send.",
  reviewStatus: "Whether Niyam has seen this version, and whether the file changed since last time.",
  checkedBy: "Tier A is checked by code. Tier B is checked by a language model. A person still decides.",
  inScans: "Only active, in-force rules are used when Niyam scans decks.",
  ruleStatus: "Draft waits for a named person. Only active rules are used in scans. Superseded and retired are not.",
  productFact: "Your approved product terms. Documents are checked against these as well as circulars.",
  dryRun: "This rule is not approved yet. The list is a preview of what would break. Nothing has gone out.",
  retestPass: "Re-test passed: open findings went to zero on the copy.",
  retestFail: "Re-test did not pass: the copy still has open findings.",
  retestNone: "No re-test yet. Run one after a named person signs a fix.",
  whyFlagged: "Why this sentence failed the rule or the product fact.",
  source: "The circular quote or product fact this finding was checked against.",
  wording: "Suggested replacement. Approving records it; the original file does not change.",
  kindFix: "A wording change on a proposal or brochure. A named person must sign before it goes out.",
  kindRule: "A check drafted from a circular. It is not used in scans until a named person approves it.",
  step: {
    circular: "A circular is the regulator text that just landed. Adding it starts the clock.",
    rules: "Niyam drafts checks from the circular. They do nothing until a named person approves.",
    scan: "Scan reads every proposal and brochure in the pack against approved rules.",
    fixes: "Each stale sentence gets drafted wording. A named person must sign before it can go out.",
    retest: "Re-test checks the copy. The pack is clear when there are no open findings left.",
    evidence: "The proof pack is who signed, when, and the hashes of both files.",
  } as const,
} as const;

export function tierHint(tier: string): string {
  if (tier === "A") return HINT.tierA;
  if (tier === "B") return HINT.tierB;
  return HINT.checkedBy;
}

export function severityHint(value: string): string | undefined {
  return HINT.severity[value as keyof typeof HINT.severity];
}
