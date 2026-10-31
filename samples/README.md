# Dummy PDFs to upload in the console

Synthetic, selectable-text PDFs. They are **not** in `library/`, so a scan does not pick them up. Download a file, then upload it in the running app.

| File | Where to upload it | What you should see |
| --- | --- | --- |
| `circular-rbi-upi-tat-synthetic.pdf` | **Rules → Add a circular** | Niyam drafts a T+5 reversal check. A named person still has to approve it. |
| `proposal-stale-upi-refunds-synthetic.pdf` | **Documents → Add a document** | Flags “7 working days” and “assured returns of 12%”. |
| `brochure-zero-fees-synthetic.pdf` | **Documents → Add a document** | Flags instant settlement, zero fees, and 7-day refunds. |

Each PDF is labelled “synthetic demo” on the page. Not a real RBI circular and not a real merchant file.

Rebuild:

```bash
apps/api/.venv/bin/python tools/make_demo_pdfs.py
```
