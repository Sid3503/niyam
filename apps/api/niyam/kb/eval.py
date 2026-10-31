"""Retrieval evaluation against a hand-written gold set (tests/gold/kb_queries.jsonl).

    python -m niyam.kb.eval [--k 10] [-v]

A query is a HIT at rank r when a returned unit's document path contains `expect_file` (case-insensitive; `a|b` = either; empty = any) AND the
unit text contains `expect_text` (case-insensitive). Reports recall@1/3/5/10 and MRR, lists misses. This is the evidence for
deciding whether dense embeddings are worth adding: if lexical recall@10 is already high, they are not.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from niyam.db.session import tx
from niyam.kb.search import search

GOLD = Path(__file__).resolve().parents[2] / "tests" / "gold" / "kb_queries.jsonl"


def run(k: int = 10, verbose: bool = False) -> dict:
    cases = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    ranks: list[int | None] = []
    misses = []
    with tx() as conn:
        for c in cases:
            res = search(conn, c["query"], limit=k)
            rank = None
            for i, h in enumerate(res["hits"], 1):
                if any(f.lower() in h["file"].lower() for f in (c["expect_file"].split("|") if c["expect_file"] else [""])) and c["expect_text"].lower() in h["text"].lower():
                    rank = i
                    break
            ranks.append(rank)
            if rank is None:
                top = res["hits"][0] if res["hits"] else None
                misses.append({"id": c["id"], "query": c["query"], "top": (top["file"].split("/")[-1] + " :: " + top["text"][:90]) if top else None})
            if verbose:
                print(f"{'HIT@'+str(rank) if rank else 'MISS':7s} {c['id']}")
    n = len(cases)
    out = {"queries": n}
    for kk in (1, 3, 5, 10):
        out[f"recall@{kk}"] = round(sum(1 for r in ranks if r and r <= kk) / n, 3)
    out["mrr"] = round(sum(1 / r for r in ranks if r) / n, 3)
    out["misses"] = misses
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    print(json.dumps(run(a.k, a.v), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
