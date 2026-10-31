from niyam.kb.extract import Block, extract_html, extract_md
from niyam.kb.units import MAX_CHARS, build_units


def test_numbered_paragraphs_get_locators_and_sublabels():
    blocks = [Block("paragraph", "Cooling-off period"), Block("paragraph", "10. Cooling-off period"),
              Block("paragraph", "(i) The borrower shall be given an explicit option to exit."), Block("paragraph", "(ii) RE may retain a fee.")]
    u = build_units(blocks, "a" * 64)
    locs = [x.locator for x in u]
    assert "para 10" in locs and "para 10(i)" in locs and "para 10(ii)" in locs


def test_units_have_stable_ids_and_hashes():
    b = [Block("paragraph", "The Payee PSP shall ensure that no surcharge is levied.")]
    u1, u2 = build_units(b, "d" * 64), build_units(b, "d" * 64)
    assert u1[0].id == u2[0].id and len(u1[0].text_sha256) == 64
    assert build_units(b, "e" * 64)[0].id != u1[0].id          # different document => different id


def test_long_paragraph_splits_only_at_sentence_boundaries_and_loses_nothing():
    sent = "The entity shall disclose the fee before acceptance. "
    text = (sent * 80).strip()
    units = build_units([Block("paragraph", text)], "f" * 64)
    assert len(units) > 1 and all(len(x.text) <= MAX_CHARS * 1.5 for x in units)
    assert " ".join(x.text for x in units).split() == text.split()    # nothing dropped or reordered


def test_bare_page_numbers_dropped():
    assert build_units([Block("paragraph", "12"), Block("paragraph", "-3-")], "1" * 64) == []


def test_table_rows_are_their_own_units():
    u = build_units([Block("table_row", "Description: Account debited | Timeline: T + 5 days", page=4)], "2" * 64)
    assert u[0].kind == "table_row" and "T + 5" in u[0].text


def test_html_rowspan_and_group_label_survive(tmp_path):
    html = """<html><body><form><table>
      <tr><th>Sl</th><th>Incident</th><th>Timeline</th></tr>
      <tr><td>4</td><td colspan="2">Unified Payments Interface (UPI)</td></tr>
      <tr><td>a</td><td>Beneficiary not credited</td><td>T + 1 day</td></tr>
      <tr><td>b</td><td>Payment to merchant</td><td>T + 5 days</td></tr>
    </table></form></body></html>"""
    p = tmp_path / "t.html"; p.write_text(html)
    ex = extract_html(p)                           # the <form> wrapper must NOT delete the content (RBI pages are ASP.NET forms)
    rows = [b.text for b in ex.blocks if b.kind == "table_row"]
    merchant = next(r for r in rows if "Payment to merchant" in r)
    assert "Unified Payments Interface" in merchant and "T + 5" in merchant
    assert "T + 1" not in merchant                 # rows must not bleed into each other


def test_markdown_front_matter_and_tables(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("---\ntitle: Terms\nentity: Paytm\nsource_url: https://example.test/t\n---\n# Heading\n\nA paragraph about fees.\n\n| Fee | Amount |\n|---|---|\n| Add money | 4% |\n")
    ex = extract_md(p)
    assert ex.meta["entity"] == "Paytm" and ex.meta["source_url"].startswith("https")
    assert any(b.kind == "table_row" and "4%" in b.text for b in ex.blocks)
