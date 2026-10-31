# Demo library (synthetic)

These PDFs are the BlueCart / Sunrise **sales pack**. A scan (`POST /library/scan`) picks up every `library/*.pdf` that has a sidecar `*.pdf.meta.json`. All of them have a real text layer (not scans). Names, fees and merchants are invented.

| File | What it is | Typical stale line |
| --- | --- | --- |
| `proposal-bluecart-payment-gateway.pdf` | Proposal Asha would send | UPI refunds in **7 working days**; “assured returns” |
| `agreement-bluecart-payment-gateway.pdf` | Merchant agreement | Settlement **T+3**; UPI MDR 0.3% |
| `pitch-deck-bluecart-payment-gateway.pdf` | Pitch deck | Instant refunds; 2.4% MDR |
| `brochure-payment-gateway-onboarding.pdf` | Brochure | Instant settlement; zero charges |
| `order-form-sunrise-payment-gateway.pdf` | Control order form | Mostly current (T+2, no UPI MDR) |
| `onboarding-checklist-payment-gateway.pdf` | Internal checklist | Mostly current |
| `whatsapp-follow-up-script-merchant-onboarding.pdf` | Follow-up script | “no hidden charges” |

Markdown originals live in `_source/`. Voice clips live in `_voice/`. Rebuild the PDFs from markdown with:

```bash
apps/api/.venv/bin/python tools/make_demo_pdfs.py
```

Files to **upload yourself** in the console (not scanned automatically) are in `/samples`.
