/** Simple word-level redline: LCS over word and whitespace tokens. */
export type RedlineOp = { type: "eq" | "del" | "ins"; text: string };

function tokens(s: string): string[] {
  return s.match(/\s+|[^\s]+/g) ?? [];
}

function merge(ops: RedlineOp[]): RedlineOp[] {
  const out: RedlineOp[] = [];
  for (const o of ops) {
    const last = out[out.length - 1];
    if (last && last.type === o.type) last.text += o.text;
    else out.push({ ...o });
  }
  return out;
}

export function wordDiff(before: string, after: string): RedlineOp[] {
  const a = tokens(before);
  const b = tokens(after);
  if (a.length * b.length > 400_000) {
    return merge([...(before ? [{ type: "del" as const, text: before }] : []), ...(after ? [{ type: "ins" as const, text: after }] : [])]);
  }
  const n = a.length;
  const m = b.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const ops: RedlineOp[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { ops.push({ type: "eq", text: a[i] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { ops.push({ type: "del", text: a[i] }); i++; }
    else { ops.push({ type: "ins", text: b[j] }); j++; }
  }
  while (i < n) ops.push({ type: "del", text: a[i++] });
  while (j < m) ops.push({ type: "ins", text: b[j++] });
  return merge(ops);
}
