#!/usr/bin/env python3
"""Load the SALES story into a freshly reset demo workspace, through the public API (no database shortcuts).

    tools/reset_demo.sh && python3 tools/seed_demo.py        # API on http://127.0.0.1:8000, or set NIYAM_API

What it sets up (all synthetic):
  1. A real circular: RBI Master Direction on Payment Aggregators (settlement and merchant terms), taken from the knowledge base.
     Niyam drafts rules from it; counsel approves the one that bites on sales documents and REJECTS the three that do not.
  2. The rules that fire on the demo documents are approved; the rest of the queue is left pending, as it would be in real life.
  3. The library is scanned (2 PDFs, 5 text documents). The BlueCart proposal gets one wording committed as version 2 through the PDF workbench.
  4. Fixes are drafted on the agreement and the proposal; one is approved by a named person, the others wait. (So "you can see when a fix is approved" is visible.)
  5. Two synthetic voice notes are checked.
Nothing here is real merchant data. Needs Ollama or Sarvam keys configured for the AI-drafted fix and for speech-to-text.
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("NIYAM_API", "http://127.0.0.1:8000").rstrip("/") + "/api/v1"
COUNSEL, SALES = "priya.sharma (counsel)", "asha.verma (sales)"


def call(method, path, body=None, actor=COUNSEL, timeout=300):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "X-Actor": actor})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "_body": e.read().decode()[:300]}


def step(msg):
    print(f"\n== {msg}", flush=True)


def main() -> int:
    if call("GET", "/overview").get("_http"):
        print("API not reachable or not ready at", API)
        return 1
    step("1. Circular: RBI Payment Aggregator directions")
    kb = call("GET", "/kb/documents?q=payment%20aggregators&regulator=RBI")
    doc = next((d for d in kb if "Payment Aggregators" in d["title"]), None) if isinstance(kb, list) else None
    if not doc:
        print("knowledge-base document not found; run the ingest first")
        return 1
    c = call("POST", "/circulars", {"kb_document_id": doc["id"], "kb_query": "settlement merchant timeline escrow fee charges",
                                    "title": "RBI Master Direction on Payment Aggregators (settlement and merchant terms)", "institution": "RBI",
                                    "product_area": "Payment Gateway settlement and merchant terms", "effective_date": "2025-09-15"})
    drafts = c.get("drafts", [])
    print("  drafted:", [d["title"] for d in drafts] or c)
    pending = {a["rule"]["id"]: a["id"] for a in call("GET", "/approvals?kind=rule&status=pending") if a.get("rule")}
    for d in drafts:
        aid = pending.get(d["rule_id"])
        if not aid:
            continue
        relevant = "settlement timeline" in d["title"].lower()
        call("POST", f"/approvals/{aid}/decision", {"decision": "approve" if relevant else "reject",
             "reason": "Bites on proposals and agreements: settlement timelines must be stated." if relevant else "About escrow or fund flows, not merchant-facing documents."})
        print(f"  {'approved' if relevant else 'rejected'}: {d['title']}")

    step("2. Approve the rules that fire on the demo documents")
    for a in call("GET", "/approvals?kind=rule&status=pending"):
        if a["rule"]["id"] in ("RBI-TAT-UPI-MERCHANT", "RBI-TAT-COMP-100", "SEBI-NO-ASSURED-RETURNS"):
            call("POST", f"/approvals/{a['id']}/decision", {"decision": "approve", "reason": "Quote verified against the source."})
            print("  approved:", a["rule"]["id"])

    step("3. Scan the library")
    s = call("POST", "/library/scan", {})
    print(f"  discovered {s.get('discovered')}, reviewed {s.get('reviewed')}, skipped {s.get('skipped')}")
    lib = call("GET", "/library")
    prop = next(d for d in lib if d["format"] == "pdf" and "Proposal" in d["title"])
    agr = next(d for d in lib if d["format"] == "pdf" and "Agreement" in d["title"])

    step("4. Proposal: commit approved wording as version 2 through the PDF workbench")
    det = call("GET", "/documents/" + prop["id"])
    edits = [{"finding_id": f["id"], "wording": f["suggested_fix"]["wording"]} for f in det["findings"] if f["suggested_fix"] and f["status"] != "current"]
    r = call("POST", f"/documents/{prop['id']}/apply", {"edits": edits, "commit": True}, actor=SALES)
    print("  committed:", r.get("committed"), "| open findings now:", (r.get("comparison") or {}).get("after", {}).get("open"), r.get("_body", ""))

    step("5. Fixes: one approved by a named person, the rest waiting")
    fs = [f for f in call("GET", "/documents/" + agr["id"])["findings"] if f["suggested_fix"] and f["status"] != "current"]
    for i, f in enumerate(fs[:4]):
        a = call("POST", f"/findings/{f['id']}/send-for-approval", actor="ravi.menon (sales)")
        if i == 0 and a.get("id"):
            call("POST", f"/approvals/{a['id']}/decision", {"decision": "approve", "reason": "Approved wording matches the fee schedule."})
            print("  approved a fix on the agreement")
    for f in call("GET", "/documents/" + prop["id"])["findings"]:
        if f["rule_id"] == "RBI-TAT-UPI-MERCHANT":
            a = call("POST", f"/findings/{f['id']}/send-for-approval", actor=SALES)
            print("  AI-drafted refund fix waiting for approval:", (a.get("proposed_wording") or a.get("_body", ""))[:110])

    step("6. Voice notes (synthetic)")
    for name in ("hinglish-settlement", "english-fees"):
        v = call("POST", f"/voice/samples/{name}/check", actor=SALES)
        print(" ", name, "->", v.get("document", {}).get("format") or v.get("_body"))

    o = call("GET", "/overview")
    print("\nDone.", {k: o[k] for k in ("documents_total", "open_findings", "fixes_awaiting_approval", "rules_pending_approval")}, "| next:", o["next_action"]["label"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
