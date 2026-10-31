import { Link } from "react-router-dom";
import { HereStrip, PageHeader } from "@/components/Page";
import { useTour } from "@/components/Tour";

const STEPS: [string, string, string][] = [
  ["1. Unlock", "Paste the demo API key in Settings. It stays in this browser. Then put your name so approvals show who signed.", "/settings"],
  ["2. Read Overview", "This is the pack: how many decks were scanned, how many sentences are still out of date, how many fixes wait for a name.", "/overview"],
  ["3. Open Documents", "Open the BlueCart payment-gateway proposal. That is the file sales would send. Find the line that says 7 working days — it is marked outdated.", "/library"],
  ["4. Check the rule", "The finding points at a cited circular (T+5, not T+7). Rules do nothing until a named person approves them.", "/rules"],
  ["5. Sign the fix", "Approvals is the queue. One fix is already approved so you can see a name on it. The rest wait for you.", "/approvals"],
  ["6. Hand over evidence", "Who changed what, who approved, hashes of both files. Send version 2. The original never moved.", "/evidence"],
];

export default function GuidePage() {
  const tour = useTour();
  return (
    <>
      <PageHeader
        eyebrow="How to use Niyam"
        title="A two-minute dry run"
        lede="Follow one sentence from a stale proposal to an approved copy. Simple English. Synthetic BlueCart documents."
      />
      <HereStrip here="You are reading the written walkthrough." next="Next: start the guided tour, or open Documents." />

      <section className="sheet p-5 sm:p-6">
        <h2 className="text-[16px] font-semibold tracking-[-0.01em]">The story in one breath</h2>
        <p className="mt-2 max-w-[64ch] text-[14px] leading-relaxed text-[var(--muted-foreground)]">
          BlueCart’s proposal still promises UPI refunds in <span className="rl-del">7 working days</span>.
          The circular says auto-reversal within <ins className="rl-ins">T+5 days</ins>.
          Niyam marks that sentence, drafts the new wording, and waits for a named person.
          Sales then sends the approved copy. The original file is never changed.
        </p>
        <button type="button" className="btn btn-primary mt-4" onClick={tour.start}>
          Start the guided walkthrough
        </button>
      </section>

      <ol className="mt-5 grid gap-3">
        {STEPS.map(([t, d, href]) => (
          <li key={t} className="sheet p-4 sm:p-5">
            <h3 className="text-[15px] font-semibold">{t}</h3>
            <p className="mt-1.5 max-w-[64ch] text-[13.5px] leading-relaxed text-[var(--muted-foreground)]">{d}</p>
            <Link to={href} className="mt-3 inline-flex text-[13px] font-medium text-[var(--taupe-strong)] hover:underline">
              Open this step
            </Link>
          </li>
        ))}
      </ol>
    </>
  );
}
