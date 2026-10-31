export const TOUR_STORAGE_KEY = "niyam.tour.seen";

export type TourStep = {
  id: string;
  path: string;
  title: string;
  body: string;
  example: string;
};

/** Six stops. Plain English, one BlueCart sentence carried all the way through. */
export const TOUR_STEPS: TourStep[] = [
  {
    id: "welcome",
    path: "/overview",
    title: "You send the proposal. Niyam keeps it current.",
    body: "A circular changes a rule. Last quarter’s deck still goes out. Niyam finds the stale sentence, drafts the new wording, and waits for a named person to approve. The original file is never changed.",
    example: "BlueCart’s payment-gateway proposal still says failed UPI payments are refunded in 7 working days. The rule is T+5.",
  },
  {
    id: "overview",
    path: "/overview",
    title: "Overview is the pack at a glance",
    body: "These numbers are this workspace: how many documents were scanned, how many claims are still out of date, and how many fixes wait for a name.",
    example: "Open findings = sentences still wrong. Fixes waiting = wording is drafted, nobody has signed yet.",
  },
  {
    id: "documents",
    path: "/library",
    title: "Documents is the list you would send",
    body: "Open the BlueCart payment-gateway proposal. Findings sit on the exact sentence, not a summary of the file.",
    example: "Find “7 working days”. That line is marked outdated.",
  },
  {
    id: "rules",
    path: "/rules",
    title: "Rules are the checks, not a chatbot",
    body: "Each rule quotes the circular in its own words. A rule is not used until a named person approves it.",
    example: "RBI-TAT-UPI-MERCHANT: auto-reversal within T+5 days.",
  },
  {
    id: "approvals",
    path: "/approvals",
    title: "Nothing ships without a name",
    body: "Fixes wait here. One is already approved so you can see what “approved by” looks like. The rest are waiting — you can decide them with the name you set in Settings.",
    example: "Counsel signed a settlement-timeline fix. A refund-wording fix is still waiting.",
  },
  {
    id: "evidence",
    path: "/evidence",
    title: "Evidence is the proof you can hand over",
    body: "Who changed what, who approved, and the hashes of both files. Sales needed to know the deck is clear to send. Audit asks for this pack.",
    example: "Send version 2, the approved copy. The original stays as it was.",
  },
];

export function tourSeen(): boolean {
  try {
    return localStorage.getItem(TOUR_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function markTourSeen(): void {
  try {
    localStorage.setItem(TOUR_STORAGE_KEY, "1");
  } catch {
    /* ignore */
  }
}
