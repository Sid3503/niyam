import { useEffect } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, X } from "lucide-react";
import { NiyamMark } from "@/components/AppShell";
import { useTour } from "@/components/Tour";
import { FOOTER_TEXT } from "@/lib/format";

export const HERO_LINE = "Proposals and brochures stop shipping claims that are out of date, and you can see when a fix is approved.";

export const LANDING_TITLE = "Niyam: proposals and brochures without out-of-date claims";
export const LANDING_DESCRIPTION = "Niyam finds the out-of-date claims in your proposals, agreements and brochures after an RBI or NPCI circular, drafts corrected wording, and shows you when a named person approves the fix. Decision support, not legal advice.";

const PROBLEM = [
  "A rule changed, and nobody told the people who send proposals.",
  "The old brochure and deck are still going out.",
  "A promise in a proposal, like a settlement time, a fee or “guaranteed approval”, contradicts what the company can deliver.",
  "And nobody can tell whether the fixed version is the approved one.",
];

const OUTCOMES: [string, string][] = [
  ["See what is out of date", "Which of your proposals, agreements, brochures and order forms say something out of date, with the exact sentence and the rule behind it."],
  ["Get corrected wording ready", "Suggested wording is drafted for each stale clause, so you are not waiting for someone to redline it."],
  ["Watch the fix get approved", "See a fix move from drafted to approved, by a named person, so you know which version is the approved one."],
  ["Keep the proof", "What changed, who approved it and when, in one evidence file you can hand over."],
];

const LOOP: [string, string, string][] = [
  ["A rule changes", "A new RBI or NPCI circular is added to Niyam.", "You or the approver"],
  ["Rule approved", "Niyam drafts a checkable rule. A named person approves it before it is used.", "Niyam drafts, the approver decides"],
  ["Documents checked", "Your proposals, agreements and brochures are scanned clause by clause.", "Niyam"],
  ["Fix drafted", "Corrected wording appears next to the stale sentence. The original stays as it was.", "Niyam"],
  ["Fix approved", "You can see when a named person approves, rejects or defers it.", "The approver"],
  ["Send the approved version", "The fix goes on a copy and is re-tested. The evidence file exports.", "You, with Niyam"],
];


const GUARDS: [string, string][] = [
  ["A named person signs off", "Rules and fixes wait for a human. The AI never approves, publishes or activates anything."],
  ["The original file never changes", "Fixes go on a copy saved as a new version. The old text is really removed from the copy."],
  ["Unsure means review, never pass", "With no evidence either way, a finding says review. Only a verified clean clause says current."],
  ["Every finding points to its evidence", "The sentence is quoted from your document, next to the cited rule."],
  ["The AI drafts. A person decides.", "A language model helps find and draft. Every outcome that matters is a human decision."],
  ["A tamper-evident log", "Each action is chained to the one before, so an edited history shows. The evidence pack has a SHA-256 of both file versions."],
];

const IS: [string, string][] = [
  ["Shows which of your documents say something out of date, with the quote and the rule. You skip the hunt.", "Not legal advice. It is decision support."],
  ["Drafts corrected wording for the clause that failed, as a redline on a copy. You are not waiting on a first draft.", "Not a contract generator. It never writes an agreement from a prompt."],
  ["Shows when a named person approves a fix. You know which version is the approved one.", "Not a replacement for the people who approve, and the AI never approves anything."],
  ["Leaves the original untouched and keeps the proof. You can show what changed and who approved.", "Not a circular tracker with a task list."],
];

const FAQ: [string, string][] = [
  ["Will it slow my deals down?", "It should not. The check runs on the documents you already have, and suggested wording is ready when a finding appears. A fix still waits for a named approver, because that is what makes it safe to send."],
  ["Who decides what is out of date?", "A rule does, and a named person approves that rule before it is used. Every finding shows the rule and the quote. Niyam is decision support, not legal advice."],
  ["Does the AI approve anything?", "No. A named person approves every rule and every fix. The AI drafts and flags; it never approves, publishes or activates."],
  ["Does it change my original file?", "No. Fixes are applied to a copy and saved as a new version. The original keeps its bytes, and the evidence pack records a SHA-256 of both."],
  ["What does it check against?", "Cited RBI, NPCI and SEBI-type rules turned into executable checks, plus your own approved product terms. The demo rule set is small and the demo product facts are synthetic. FREE-AI is a recommendation, not a binding rule."],
  ["What if it is unsure?", "It says review, never pass. Missing evidence is never shown as clean."],
  ["Where does our data go?", "In this demo, only synthetic documents are used. Document text is sent to a hosted language model for drafting and judging. A production deployment would need a data decision made with you first."],
];

function WalkthroughCta() {
  const tour = useTour();
  return (
    <button type="button" className="btn btn-lg" onClick={tour.start}>
      Start the 2-minute walkthrough
    </button>
  );
}

function Cta({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-wrap items-center gap-3 ${className}`}>
      <Link to="/overview" className="btn btn-primary btn-lg">Open the demo workspace <ArrowRight size={16} aria-hidden="true" /></Link>
      <a href="#how" className="btn btn-lg">See how it works</a>
    </div>
  );
}

/** A faithful, small mock of a finding card: stale clause becoming approved wording. Not a screenshot. */
function ClauseCard() {
  return (
    <figure className="sheet land-card" aria-label="Example: a stale clause and its approved wording">
      <figcaption className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-2.5">
        <span className="label">Synthetic demo document</span>
        <span className="chip chip-bad chip-dot">outdated</span>
      </figcaption>
      <div className="px-4 py-4">
        <p className="label">Proposal, section 3.1</p>
        <p className="mt-2 text-[15px] leading-relaxed">“Failed UPI payments are <span className="rl-del">refunded to the customer within 7 working days</span>.”</p>
        <div className="land-arrow" aria-hidden="true"><span /></div>
        <p className="label">Corrected wording, ready to send</p>
        <p className="mt-2 text-[15px] leading-relaxed">“Failed UPI payments are <ins className="rl-ins">reversed within T+5 working days</ins>.”</p>
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-[var(--border)] px-4 py-2.5 text-[12px] text-[var(--muted-foreground)]">
        <span><b className="font-semibold text-[var(--foreground)]">Fix approved</b> by Asha K., 31 Oct 2026, 10:42 (synthetic)</span>
        <span className="chip chip-ok chip-dot">approved</span>
      </div>
    </figure>
  );
}

export default function Landing() {
  useEffect(() => {
    document.title = LANDING_TITLE;
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute("content", LANDING_DESCRIPTION);
  }, []);
  return (
    <div className="land">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded-md focus:bg-[var(--card)] focus:px-3 focus:py-2 focus:text-[12px]">Skip to content</a>
      <header className="land-wrap flex items-center justify-between py-5 sm:py-7">
        <Link to="/" className="flex items-center gap-2.5" aria-label="Niyam home">
          <NiyamMark className="size-8 text-[var(--taupe)]" />
          <span className="text-[16px] font-semibold tracking-[-0.01em]">Niyam</span>
        </Link>
        <nav aria-label="Page" className="flex items-center gap-5">
          <a href="#walkthrough" className="hidden text-[13px] text-[var(--muted-foreground)] hover:text-[var(--foreground)] sm:inline">Dry run</a>
          <a href="#how" className="hidden text-[13px] text-[var(--muted-foreground)] hover:text-[var(--foreground)] sm:inline">How it works</a>
          <a href="#faq" className="hidden text-[13px] text-[var(--muted-foreground)] hover:text-[var(--foreground)] sm:inline">Questions</a>
          <Link to="/overview" className="btn btn-sm">Open the demo workspace</Link>
        </nav>
      </header>

      <main id="main" tabIndex={-1} className="outline-none">
        <section className="land-wrap land-hero grid items-center gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:gap-14" aria-labelledby="hero-h">
          <div>
            <span className="eyebrow rise">For sales ops and merchant onboarding</span>
            <h1 id="hero-h" className="land-h1 rise mt-5 max-w-[20ch]" style={{ animationDelay: "60ms" }}>
              Proposals and brochures stop shipping <em>claims that are out of date.</em>
            </h1>
            <p className="rise mt-5 text-[clamp(20px,2.4vw,28px)] font-light leading-snug tracking-[-0.02em]" style={{ animationDelay: "140ms" }}>...and you can see when a fix is approved.</p>
            <p className="sr-only">{HERO_LINE}</p>
            <div className="rise mt-8 flex flex-wrap items-center gap-3">
              <Cta />
              <WalkthroughCta />
            </div>
            <p className="rise mt-4 text-[12.5px] text-[var(--muted-foreground)]" style={{ animationDelay: "320ms" }}>Synthetic Bluecart and Sunrise demo documents. No sign-up.</p>
          </div>
          <div className="rise" style={{ animationDelay: "240ms" }}><ClauseCard /></div>
        </section>

        <section className="land-section" aria-labelledby="problem-h">
          <div className="land-wrap grid gap-8 lg:grid-cols-[0.8fr_1.2fr]">
            <h2 id="problem-h" className="land-h2 max-w-[18ch]">What goes wrong when a rule changes</h2>
            <ol className="land-problem">
              {PROBLEM.map((p) => <li key={p}>{p}</li>)}
            </ol>
          </div>
        </section>

        <section className="land-section land-tint" aria-labelledby="gets-h">
          <div className="land-wrap">
            <h2 id="gets-h" className="land-h2 max-w-[24ch]">What you get</h2>
            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              {OUTCOMES.map(([t, d]) => (
                <div key={t} className="sheet p-5">
                  <h3 className="text-[16px] font-semibold tracking-[-0.01em]">{t}</h3>
                  <p className="mt-2 text-[14px] leading-relaxed text-[var(--muted-foreground)]">{d}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="walkthrough" className="land-section land-tint" aria-labelledby="walk-h">
          <div className="land-wrap">
            <h2 id="walk-h" className="land-h2 max-w-[22ch]">A two-minute dry run, on one sentence</h2>
            <p className="land-p mt-3">Follow BlueCart’s payment-gateway proposal. This is the file a sales-ops teammate would send. Everything below is synthetic.</p>
            <ol className="mt-8 grid gap-3 lg:grid-cols-4">
              {[
                ["Monday morning", "A circular lands. Failed UPI payments must auto-reverse within T+5 days."],
                ["The deck still out", "BlueCart’s proposal still says refunds in 7 working days. That sentence is already in merchants’ inboxes."],
                ["Niyam marks it", "The line is outdated. Suggested wording is ready: reversed within T+5 working days. Original file untouched."],
                ["A name on the fix", "Counsel approves. Sales sends version 2. You can see who signed, and when."],
              ].map(([t, d], i) => (
                <li key={t} className="sheet p-4">
                  <p className="label">{i + 1}. {t}</p>
                  <p className="mt-3 text-[15px] leading-relaxed">{d}</p>
                </li>
              ))}
            </ol>
            <div className="sheet mt-4 p-5">
              <h3 className="text-[16px] font-semibold">How you run this demo</h3>
              <ol className="mt-3 grid gap-2 text-[14px] leading-relaxed text-[var(--muted-foreground)]">
                <li>1. Open the demo workspace. Paste the API key from the submission notes (one field). It stays in this browser.</li>
                <li>2. Click <b className="font-semibold text-[var(--foreground)]">2-min walkthrough</b> in the top bar, or read <Link to="/guide" className="font-medium text-[var(--taupe-strong)] hover:underline">How to use</Link>.</li>
                <li>3. Open Documents → BlueCart payment-gateway proposal. Find “7 working days”.</li>
                <li>4. Open Approvals. One fix already has a name on it. The rest wait for you.</li>
              </ol>
            </div>
          </div>
        </section>

        <section id="how" className="land-section" aria-labelledby="how-h">
          <div className="land-wrap">
            <h2 id="how-h" className="land-h2 max-w-[22ch]">How it works, in six steps</h2>
            <p className="land-p mt-3">One step waits for a named person: the approval. Everything else is Niyam doing the legwork.</p>
            <ol className="loop mt-8" aria-label="Six-step loop">
              {LOOP.map(([t, d, who], i) => (
                <li key={t}><span className="n" aria-hidden="true">{i + 1}</span><b>{t}</b><p>{d}</p><span className="who">{who}</span></li>
              ))}
            </ol>
          </div>
        </section>

        <section className="land-section land-tint" aria-labelledby="clause-h">
          <div className="land-wrap">
            <h2 id="clause-h" className="land-h2 max-w-[24ch]">One out-of-date sentence, followed to an approved fix</h2>
            <p className="land-p mt-3">A worked example on a synthetic demo document. The rule quote is verbatim from the RBI circular on TAT for failed transactions (DPSS.CO.PD No.629/02.01.014/2019-20), as stored in Niyam's rule card RBI-TAT-UPI-MERCHANT.</p>
            <div className="mt-8 grid gap-3 lg:grid-cols-4">
              <figure className="sheet p-4">
                <figcaption className="label">1. Stale clause <span className="chip chip-plain ml-1">synthetic demo document</span></figcaption>
                <blockquote className="mt-3 text-[15px] leading-relaxed">“Failed UPI payments are <span className="rl-del">refunded to the customer within 7 working days</span>.”</blockquote>
                <p className="mt-3 text-[12px] text-[var(--muted-foreground)]">Payment-gateway proposal, section 3.1</p>
              </figure>
              <figure className="sheet p-4">
                <figcaption className="label">2. Finding <span className="chip chip-bad ml-1">outdated</span></figcaption>
                <blockquote className="mt-3 border-l-2 border-[var(--taupe)] pl-3 text-[13.5px] leading-relaxed">“Account debited but transaction confirmation not received at merchant location (payment to merchant). Auto-reversal within T + 5 days.”<footer className="mt-1.5 text-[11.5px] text-[var(--muted-foreground)]">RBI, Harmonisation of TAT and customer compensation for failed transactions (rule card RBI-TAT-UPI-MERCHANT). The app shows rule id, version and confidence.</footer></blockquote>
              </figure>
              <figure className="sheet p-4">
                <figcaption className="label">3. Suggested wording</figcaption>
                <p className="mt-3 text-[15px] leading-relaxed">“Failed UPI payments are <ins className="rl-ins">reversed within T+5 working days</ins>.”</p>
                <p className="mt-3 text-[12px] text-[var(--muted-foreground)]">Drafted as a redline. The original file is never changed.</p>
              </figure>
              <figure className="sheet p-4">
                <figcaption className="label">4. Approval <span className="chip chip-ok ml-1">approved</span></figcaption>
                <p className="mt-3 text-[15px] font-medium">Asha K., approver</p>
                <p className="mt-1 text-[12px] text-[var(--muted-foreground)]">Name and time are recorded on the approval and in the evidence file. Synthetic name.</p>
              </figure>
            </div>
          </div>
        </section>

        <section className="land-section land-dark" aria-labelledby="control-h">
          <div className="land-wrap">
            <h2 id="control-h" className="land-h2 max-w-[24ch]">Why you can rely on a fix before you send it</h2>
            <ul className="mt-8 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
              {GUARDS.map(([t, d]) => (
                <li key={t}>
                  <h3 className="flex items-start gap-2 text-[15px] font-semibold"><Check size={16} className="mt-0.5 shrink-0" aria-hidden="true" />{t}</h3>
                  <p className="mt-1.5 pl-6 text-[13.5px] leading-relaxed">{d}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="land-section" aria-labelledby="voice-h">
          <div className="land-wrap grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
            <h2 id="voice-h" className="land-h2 max-w-[18ch]">It also listens to promises made out loud.</h2>
            <p className="land-p">Promises made out loud count too. Niyam can check a recorded sales-call note against the same rules it uses for documents, and show the spoken claim next to the rule it breaks. The demo audio is synthetic. It checks recorded notes you add, not live calls.</p>
          </div>
        </section>

        <section className="land-section land-tint" aria-labelledby="is-h">
          <div className="land-wrap">
            <h2 id="is-h" className="land-h2">What Niyam is, and is not</h2>
            <div className="sheet mt-8 overflow-x-auto">
              <table className="tbl">
                <caption className="sr-only">What Niyam is and is not</caption>
                <thead><tr><th scope="col" className="w-1/2">Niyam is</th><th scope="col">Niyam is not</th></tr></thead>
                <tbody>
                  {IS.map(([a, b]) => (
                    <tr key={a}>
                      <td className="!py-4 text-[14px]"><Check size={14} className="mr-2 inline text-[var(--taupe-strong)]" aria-hidden="true" />{a}</td>
                      <td className="!py-4 text-[14px] text-[var(--muted-foreground)]"><X size={14} className="mr-2 inline" aria-hidden="true" />{b}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section id="faq" className="land-section" aria-labelledby="faq-h">
          <div className="land-wrap grid gap-8 lg:grid-cols-[0.8fr_1.2fr]">
            <h2 id="faq-h" className="land-h2 max-w-[16ch]">Questions before you rely on it</h2>
            <div className="land-faq">
              {FAQ.map(([q, a]) => (
                <details key={q}>
                  <summary>{q}</summary>
                  <p>{a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="land-section land-cta" aria-labelledby="final-h">
          <div className="land-wrap flex flex-col items-start gap-6">
            <h2 id="final-h" className="land-h2 max-w-[24ch]">See a fix go from drafted to approved.</h2>
            <p className="land-p">Open the demo workspace and follow one clause from the stale sentence to the approved fix. Synthetic Bluecart and Sunrise documents. No sign-up.</p>
            <Cta />
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--border)] py-6">
        <p className="land-wrap text-[12px] text-[var(--muted-foreground)]">{FOOTER_TEXT}</p>
      </footer>
    </div>
  );
}
