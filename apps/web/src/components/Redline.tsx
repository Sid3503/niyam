import { wordDiff } from "@/lib/redline";

/** Original clause and proposed wording side by side, with a word-level redline on both sides. */
export function Redline({ before, after }: { before: string; after: string }) {
  const ops = wordDiff(before, after);
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="redline">
      <div>
        <div className="label mb-1">Original clause</div>
        <p className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-[12.5px] leading-relaxed">
          {ops.filter((o) => o.type !== "ins").map((o, i) => (o.type === "del" ? <del key={i} className="rl-del">{o.text}</del> : <span key={i}>{o.text}</span>))}
        </p>
      </div>
      <div>
        <div className="label mb-1">Proposed wording</div>
        <p className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-[12.5px] leading-relaxed">
          {ops.filter((o) => o.type !== "del").map((o, i) => (o.type === "ins" ? <ins key={i} className="rl-ins">{o.text}</ins> : <span key={i}>{o.text}</span>))}
        </p>
      </div>
    </div>
  );
}
