"""Corpus ingestion: files on disk -> documents + units in Postgres. Idempotent and auditable.

    python -m niyam.kb.ingest [--force] [--only SUBSTR]

- corpus_kind=regulation: everything under NIYAM_REGULATIONS_DIR (PDF/HTML/MD), manifests supply metadata.
- corpus_kind=surface: only PAYTM_*.md under NIYAM_SURFACES_DIR. These are statements to TEST, never sources of obligation,
  and the default KB search excludes them.
- OCR sidecars (`_ocr/*.ocr.txt`) back a PDF that has no text layer; those documents are flagged text_basis=ocr.
- Duplicates (same sha256) are skipped; a changed file at the same path replaces the old version.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
import time
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import text

from niyam.config import get_settings
from niyam.db import audit
from niyam.db.session import tx
from niyam.kb.extract import Extracted, extract
from niyam.kb.units import NS, build_units

log = logging.getLogger("niyam.ingest")

SKIP_NAMES = {"README.md", "MANIFEST.csv", "BLOCKED-DOWNLOAD-MANUALLY.md", "PAYTM-TERMS-BOOK.md", "NIYAM-TEST-SURFACES.md"}
STATUSES = {"in_force", "superseded", "repealed", "draft", "recommendation", "unknown"}
OFFICIAL_HOSTS = ("rbi.org.in", "rbidocs.rbi.org.in", "sebi.gov.in", "irdai.gov.in", "meity.gov.in", "indiacode", "pfrda.org.in",
                  "npci.org.in", "fiuindia.gov.in", "fatf-gafi.org", "trai.gov.in", "doca.gov.in", "ccpa", "asci", "cert-in")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifests(root: Path) -> dict[str, dict]:
    """file name -> manifest row, from every MANIFEST.csv found anywhere under root."""
    out: dict[str, dict] = {}
    for m in root.rglob("MANIFEST.csv"):
        try:
            with m.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    f = (row.get("file") or "").strip()
                    if f:
                        out[f] = {**row, "_manifest_dir": str(m.parent)}
        except Exception as e:  # noqa: BLE001
            log.warning("cannot read manifest %s: %s", m, e)
    return out


CANON = [  # (prefix, canonical) - first match wins; keeps the regulator facet usable
    ("rbi", "RBI"), ("reserve bank", "RBI"), ("sebi", "SEBI"), ("irdai", "IRDAI"), ("npci", "NPCI"), ("pfrda", "PFRDA"),
    ("meity", "MeitY"), ("trai", "TRAI"), ("ccpa", "CCPA"), ("dept of consumer affairs", "CCPA"), ("ministry of law", "CCPA"),
    ("department of consumer", "CCPA"), ("fiu", "FIU-IND"), ("mof", "MoF"), ("asci", "ASCI"), ("fatf", "FATF"),
    ("cert-in", "CERT-In"), ("bc civil", "BCCRT"), ("paytm", "Paytm"), ("mca", "MCA"),
]


def canonical_regulator(name: str) -> str:
    n = (name or "").strip().lower()
    for prefix, canon in CANON:
        if n.startswith(prefix):
            return canon
    return (name or "unknown").strip()[:60]


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    m = re.match(r"\s*(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    return None


def guess_provenance(path: Path, row: dict, ex: Extracted, kind: str, ocr: bool) -> str:
    if kind == "surface":
        return "surface_site"
    src = (row.get("source_url") or ex.meta.get("source_url") or "").lower()
    note = (row.get("verified") or "") + " " + (row.get("source_url") or "")
    if "_user-dropped" in path.parts or "user-downloaded" in note.lower() or ocr and "user" in note.lower():
        return "user_downloaded"
    if "mirror" in note.lower() or "third-party" in note.lower() or "avantiscdn" in src:
        return "mirror"
    if "official" in (ex.meta.get("header_comment", "")).lower() and "html" in ex.meta.get("header_comment", "").lower():
        return "official_html_extract"
    if path.suffix.lower() in (".html", ".md") and "rbi.org.in" in src:
        return "official_html_extract"
    if any(h in src for h in OFFICIAL_HOSTS):
        return "official"
    return "unknown"


def derive_meta(path: Path, root: Path, row: dict, ex: Extracted, kind: str, ocr: bool) -> dict:
    status = (row.get("status") or "").strip().lower()
    if "repealed" in path.name.lower():
        status = "repealed"
    if status not in STATUSES:
        status = "unknown"
    title = (row.get("title") or ex.meta.get("title") or path.stem.replace("_", " ")).strip()
    regulator = (row.get("regulator") or ex.meta.get("entity") or "").strip()
    if not regulator:
        regulator = path.name.split("_")[0].upper() if "_" in path.name else "unknown"
    regulator = canonical_regulator(regulator)
    if kind == "surface":
        regulator = "Paytm"
    return dict(
        title=title[:500],
        regulator=regulator[:60],
        doc_type=(row.get("doc_type") or ("tnc" if kind == "surface" else "unknown")).strip()[:40],
        reference_no=(row.get("reference_no") or "").strip()[:200] or None,
        issue_date=parse_date(row.get("issue_date")),
        status=status,
        provenance=guess_provenance(path, row, ex, kind, ocr),
        source_url=(row.get("source_url") or ex.meta.get("source_url") or None),
        manifest_note=(row.get("verified") or None),
    )


def discover(settings) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    reg = settings.regulations_path
    if reg.exists():
        for p in sorted(reg.rglob("*")):
            if not p.is_file() or p.name in SKIP_NAMES or p.name.startswith("."):
                continue
            if "_ocr" in p.parts:
                continue                                   # sidecars are attached to their PDF
            if p.suffix.lower() in (".pdf", ".html", ".htm", ".md"):
                files.append((p, "regulation"))
    sur = settings.surfaces_path
    if sur.exists():
        for p in sorted(sur.glob("PAYTM_*.md")):
            if p.name not in SKIP_NAMES:
                files.append((p, "surface"))
    return files


def find_sidecar(p: Path) -> Path | None:
    for cand in (p.parent / "_ocr" / f"{p.stem}.ocr.txt",):
        if cand.exists():
            return cand
    return None


def ingest(force: bool = False, only: str | None = None) -> dict:
    s = get_settings()
    stats = dict(files=0, docs_new=0, docs_replaced=0, skipped_same=0, skipped_duplicate=0, ocr_sidecar=0, empty=0, failed=0, units=0)
    manifests = load_manifests(s.data_root)
    run_id = uuid.uuid4()
    t0 = time.time()
    with tx() as conn:
        conn.execute(text("INSERT INTO ingest_runs (id, tenant_id) VALUES (:i, :t)"), {"i": run_id, "t": s.tenant_id})
    for path, kind in discover(s):
        if only and only not in str(path):
            continue
        stats["files"] += 1
        rel = str(path.relative_to(s.data_root))
        digest = sha256_file(path)
        doc_id = uuid.uuid5(NS, f"doc:{digest}")
        with tx() as conn:
            same = conn.execute(text("SELECT file_path, unit_count FROM documents WHERE tenant_id=:t AND sha256=:h"),
                                {"t": s.tenant_id, "h": digest}).first()
            if same and not force and same.unit_count > 0:
                stats["skipped_same" if same.file_path == rel else "skipped_duplicate"] += 1
                continue
            old = conn.execute(text("SELECT id FROM documents WHERE tenant_id=:t AND file_path=:p AND sha256<>:h"),
                               {"t": s.tenant_id, "h": digest, "p": rel}).scalars().all()
        ex = extract(path)
        ocr = False
        if path.suffix.lower() == ".pdf" and ex.status == "empty":
            side = find_sidecar(path)
            if side:
                ex2 = extract(side)
                if ex2.status == "ok":
                    ex, ocr = ex2, True
                    ex.note = f"text from OCR sidecar {side.name} (machine-read; PDF is authoritative)"
                    stats["ocr_sidecar"] += 1
        status = "failed" if ex.status == "failed" else ("empty" if ex.status == "empty" else ("ocr_sidecar" if ocr else "ok"))
        row = manifests.get(path.name, {})
        meta = derive_meta(path, s.data_root, row, ex, kind, ocr)
        units = build_units(ex.blocks, digest) if status in ("ok", "ocr_sidecar") else []
        if status == "empty":
            stats["empty"] += 1
        if status == "failed":
            stats["failed"] += 1
        with tx() as conn:
            if same:   # re-processing (forced, or the previous attempt produced no units)
                conn.execute(text("DELETE FROM documents WHERE id=:i"), {"i": doc_id})
            for oid in old:
                conn.execute(text("DELETE FROM documents WHERE id=:i"), {"i": oid})
                stats["docs_replaced"] += 1
            conn.execute(
                text(
                    "INSERT INTO documents (id, tenant_id, corpus_kind, sha256, file_path, title, regulator, doc_type, reference_no, issue_date, "
                    "status, provenance, text_basis, source_url, pages, unit_count, extraction_status, extraction_note, manifest_note) "
                    "VALUES (:id,:t,:k,:h,:fp,:title,:reg,:dt,:ref,:idate,:st,:prov,:tb,:url,:pages,:uc,:es,:en,:mn)"
                ),
                dict(id=doc_id, t=s.tenant_id, k=kind, h=digest, fp=rel, title=meta["title"], reg=meta["regulator"], dt=meta["doc_type"],
                     ref=meta["reference_no"], idate=meta["issue_date"], st=meta["status"], prov=meta["provenance"],
                     tb="ocr" if ocr else "native", url=meta["source_url"], pages=ex.pages, uc=len(units), es=status,
                     en=(ex.note or None), mn=meta["manifest_note"]),
            )
            if units:
                conn.execute(
                    text(
                        "INSERT INTO units (id, tenant_id, document_id, ordinal, page, kind, locator, heading_path, text, text_sha256, char_count) "
                        "VALUES (:id,:t,:d,:o,:p,:k,:l,:hp,:tx,:sh,:cc)"
                    ),
                    [dict(id=u.id, t=s.tenant_id, d=doc_id, o=u.ordinal, p=u.page, k=u.kind, l=u.locator, hp=u.heading_path,
                          tx=u.text, sh=u.text_sha256, cc=len(u.text)) for u in units],
                )
            stats["docs_new"] += 1
            stats["units"] += len(units)
        log.info("%-9s %-5d units  %s", status, len(units), rel)
    stats["seconds"] = round(time.time() - t0, 1)
    with tx() as conn:
        conn.execute(text("UPDATE ingest_runs SET finished_at=now(), stats=CAST(:s AS jsonb) WHERE id=:i"), {"s": json.dumps(stats), "i": run_id})
        audit.append(conn, actor="ingest-cli", action="kb.ingest", object_type="ingest_run", object_id=str(run_id), payload=stats)
    return stats


def refresh_metadata() -> dict:
    """Re-derive title/regulator/type/reference/date/status from the manifests for documents already ingested.
    Does not re-extract text and does not touch provenance. Use after editing a MANIFEST.csv."""
    s = get_settings()
    manifests = load_manifests(s.data_root)
    n = 0
    with tx() as conn:
        for r in conn.execute(text("SELECT id, file_path, corpus_kind, title FROM documents WHERE tenant_id=:t"), {"t": s.tenant_id}).all():
            row = manifests.get(Path(r.file_path).name)
            if not row:
                continue
            m = derive_meta(Path(r.file_path), s.data_root, row, Extracted(), r.corpus_kind, False)
            conn.execute(text("UPDATE documents SET title=:title, regulator=:reg, doc_type=:dt, reference_no=:ref, issue_date=:idate, status=:st WHERE id=:i"),
                         dict(i=r.id, title=m["title"], reg=m["regulator"], dt=m["doc_type"], ref=m["reference_no"], idate=m["issue_date"], st=m["status"]))
            n += 1
        # documents without a manifest row still get a canonical regulator
        for r in conn.execute(text("SELECT id, regulator FROM documents WHERE tenant_id=:t"), {"t": s.tenant_id}).all():
            c = canonical_regulator(r.regulator)
            if c != r.regulator:
                conn.execute(text("UPDATE documents SET regulator=:c WHERE id=:i"), {"c": c, "i": r.id})
        audit.append(conn, actor="ingest-cli", action="kb.refresh_metadata", object_type="documents", object_id="*", payload={"updated": n})
    return {"updated": n}


def main() -> int:
    logging.basicConfig(level=get_settings().log_level, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--refresh-metadata", action="store_true", help="re-read manifests into existing documents; no re-extraction")
    a = ap.parse_args()
    print(json.dumps(refresh_metadata() if a.refresh_metadata else ingest(a.force, a.only), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
