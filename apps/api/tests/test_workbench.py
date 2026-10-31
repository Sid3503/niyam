"""PDF workbench invariants (no database, no network). The PDF is generated here."""
import os
from pathlib import Path

import pymupdf
import pytest

os.environ.setdefault("NIYAM_DATA_ROOT", str(Path(__file__).resolve().parents[3]))

from niyam.review import pdfio, voice

BODY = ("<h1>Proposal</h1><p>1.1 Accept cards and UPI on your site.</p>"
        "<p>3.1 If a UPI merchant payment fails but the customer is debited, the amount is refunded within 7 working days.</p>"
        "<p>4.1 Earn assured returns of 12% a year with no risk.</p><p>5.1 Share your PAN.</p>")
OLD = "the amount is refunded within 7 working days."


def _pdf() -> bytes:
    st = pymupdf.Story(f"<body style='font-family:sans-serif;font-size:10.5pt'>{BODY}</body>")
    path = "/tmp/niyam-test-wb.pdf"
    w = pymupdf.DocumentWriter(path)
    box = pymupdf.paper_rect("a4")
    more = 1
    while more:
        dev = w.begin_page(box)
        more, _ = st.place(box + (54, 60, -54, -60))
        st.draw(dev)
        w.end_page()
    w.close()
    return Path(path).read_bytes()


def _edit(ex, data, needle, wording, fid="f1"):
    start = ex.content.index(needle)
    end = start + len(needle)
    page, bbox = pdfio.locate(data, ex.page_map, start, end, needle)
    return pdfio.Edit(fid, wording, needle, page, bbox, (start, end))


def test_extract_gives_clauses_with_geometry():
    d = _pdf()
    ex = pdfio.extract(d)
    assert "3.1 If a UPI merchant payment fails" in ex.content and ex.pages == 1
    assert all(m["bbox"][2] > m["bbox"][0] for m in ex.page_map)
    loc = pdfio.locate(d, ex.page_map, ex.content.index(OLD), ex.content.index(OLD) + len(OLD), OLD)
    assert loc and loc[0] == 1 and loc[1][3] > loc[1][1]


def test_apply_really_removes_old_text_and_replaces_the_whole_sentence():
    d = _pdf()
    ex = pdfio.extract(d)
    new_bytes, strat = pdfio.apply_edits(d, ex, [_edit(ex, d, OLD, "If a UPI merchant payment fails and the customer is debited, the refund reaches the customer within T+5 working days.")])
    new = pdfio.extract(new_bytes)
    assert strat[0]["method"] == "redact_rewrite"
    assert not pdfio.stale(OLD, new.content)                       # the stale quote cannot be extracted: removed, not covered
    assert "T+5 working days" in new.content
    assert new.content.count("If a UPI merchant payment fails") == 1   # no leftover head of the old sentence
    assert "assured returns of 12%" in new.content                     # untouched clauses survive
    assert pymupdf.open(stream=new_bytes, filetype="pdf").metadata.get("author", "") == ""


def test_whiteout_would_be_detected_as_stale():
    d = _pdf()
    doc = pymupdf.open(stream=d, filetype="pdf")
    page = doc[0]
    r = page.search_for("refunded within 7 working days")[0]
    page.draw_rect(r, color=(1, 1, 1), fill=(1, 1, 1))              # what a lazy "fix" does: paint over the words
    covered = pdfio.extract(doc.tobytes())
    assert pdfio.stale("refunded within 7 working days", covered.content)   # extraction still finds it, so the commit gate rejects it


def test_missing_disclosure_is_appended_as_new_text():
    d = _pdf()
    ex = pdfio.extract(d)
    out, strat = pdfio.apply_edits(d, ex, [pdfio.Edit("m1", "Contact the grievance redressal officer named in the Merchant Agreement.", None, None, None, None)])
    assert strat[0]["method"] == "append_text" and "grievance redressal officer" in pdfio.extract(out).content


def test_longer_wording_reflows_the_page_and_loses_nothing():
    d = _pdf()
    ex = pdfio.extract(d)
    longer = "If a UPI merchant payment fails and the customer is debited, the amount is auto-reversed to the customer within T+5 working days; compensation of Rs 100 per day applies after that. " * 3
    out, strat = pdfio.apply_edits(d, ex, [_edit(ex, d, OLD, longer.strip())])
    new = pdfio.extract(out)
    assert strat[0]["method"] == "redact_rewrite" and not pdfio.stale(OLD, new.content)
    for keep in ("Accept cards and UPI", "assured returns of 12%", "5.1 Share your PAN"):    # content below the edit was pushed down, not dropped
        assert keep in new.content
    first = pymupdf.open(stream=out, filetype="pdf")[0].get_text("blocks")
    ys = [b[1] for b in first if "5.1 Share" in b[4]]
    old_y = [b[1] for b in pymupdf.open(stream=d, filetype="pdf")[0].get_text("blocks") if "5.1 Share" in b[4]]
    assert ys and ys[0] > old_y[0]


def test_wording_that_cannot_fit_on_the_page_is_refused_not_hidden():
    d = _pdf()
    ex = pdfio.extract(d)
    with pytest.raises(pdfio.WordingDoesNotFit):
        pdfio.apply_edits(d, ex, [_edit(ex, d, OLD, "word " * 6000)])


def test_two_edits_in_one_clause_are_applied_once():
    d = _pdf()
    ex = pdfio.extract(d)
    with pytest.raises(pdfio.WordingDoesNotFit):                       # two edits fighting over one sentence are refused, never half-applied
        pdfio.apply_edits(d, ex, [_edit(ex, d, OLD, "A.", "a"), _edit(ex, d, "refunded within 7", "B.", "b")])


def test_voice_sentence_times_cover_the_transcript():
    en = "Sir, your settlement is guaranteed in two hours. There is no KYC hassle."
    s, note = voice.sentences_with_times(en, [{"text": en, "start": 0.0, "end": 7.0}], 7.0)
    assert [x["text"] for x in s] == ["Sir, your settlement is guaranteed in two hours.", "There is no KYC hassle."]
    assert s[0]["start"] == 0.0 and s[-1]["end"] == 7.0 and "Approximate" in note
    assert all(en[x["start_char"]:x["end_char"]] == x["text"] for x in s)
