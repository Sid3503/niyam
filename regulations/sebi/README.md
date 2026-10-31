# SEBI regulatory corpus for NIYAM

Retrieved 2026-10-31 from sebi.gov.in. 36 files (35 PDFs, 1 HTML), all checked as real PDFs (or HTML) with a readable first page. Hashes, page counts and source URLs are in `MANIFEST.csv`. Clause citations below are given only where the text was read in the stored file. Anything else is marked as inference.

Access note: sebi.gov.in served public circular pages and PDFs to plain `curl -L` with a descriptive User-Agent at low volume (sequential, at least 1.5 s apart). No bypass was needed or used. No Firecrawl credits were spent. Discovery used WebSearch, then SEBI's own listing pages for master circulars and regulations.

## Resolved question: which SEBI text prohibits assured or guaranteed returns?

Several texts do, depending on the entity type. These are the ones read in the stored files:

| Text | What it says (as read) | Applies to | Status |
| --- | --- | --- | --- |
| SEBI (Intermediaries) Regulations 2008, **Reg 16O(b)** and **16O(c)** (Chapter IIID Common Advertisement Code) | An advertisement shall not contain anything that "directly or indirectly, promises or gives assurance of any guaranteed or risk free or indicative returns to prospective or existing clients". 16O(c) bars any promise of fixed returns, with a carve-out for Online Bond Platform Providers. | Stock brokers, DPs, OBPPs, IAs, RAs, MFs/AMCs, PMs (the "regulated entity" list in Reg 16G(3)) | Chapter IIID is footnoted "Inserted by (Second Amendment) Regulations, 2026 w.e.f. 08.04.2027". As printed, it is **not yet in force** at 31 Oct 2026. |
| **Master Circular for Investment Advisers (6 Feb 2026), para 10.1(c)(x)** | The advertisement shall not contain "Any promise or guarantee of assured or risk free return to the investors", nor imply assured, minimum or target returns or percentage accuracy. | IAs | In force. |
| Same master circular, **Annexure A para 2(b)** (mandatory agreement clause) | The IA shall not, in the course of performing its services, "hold out any investment advice implying any assured returns or minimum returns or target return or percentage accuracy". This covers service interactions with existing clients, not only advertising. | IAs | In force. |
| Master Circular for Research Analysts (6 Feb 2026) | The same text is present in its advertisement section ("Any promise or guarantee of assured or risk free return"). I did not read the para number. | RAs | In force. |
| Mutual-fund texts | The MF Regulations 2026 Fifth Schedule (Advertisement Code) has the standard warning and anti-misleading limbs. I found no express "no guaranteed return" word in it. The 2000 MF ad guidelines treat as misleading any promise of return "not backed by adequate reserve funds or sponsors' or third party guarantees". | MFs/AMCs | The Fifth Schedule is omitted w.e.f. 08.04.2027, per footnote 4 of the file. The 2000 guidelines are legacy. |

I did not find a standalone sub-regulation of the IA or RA Regulations themselves that says "no assured returns". The prohibition sits in the Intermediaries Regulations (advertising) and the IA master circular (advertising and agreement terms). The IA FAQ Q48 restates the "hold out" language. Do not cite an IA Regulation number for it.

## 1. File inventory and NIYAM relevance

Stage abbreviations: **Author** (rule-card authoring), **Attack** (synthetic customer tests), **Judge**, **Fix**, **Gate**, **Evidence**. Surfaces: chat agent, voice, scripts and macros, ads and social, disclosures.

### AI/ML obligations (highest NIYAM value)

| File | What it is | NIYAM relevance | Key clauses worth turning into rule cards (read in file) |
| --- | --- | --- | --- |
| `SEBI_2026-10-10_intermediaries-regulations-2008-consolidated.pdf` | Consolidated Intermediaries Regulations. Contains Reg 16A (association), Reg 16C (AI), Reg 16G-16Q (Common Advertisement Code). | Binding legal basis. Feeds a new card `SEBI-AI-ACCOUNTABILITY`. Also feeds `RBI-MIS-SELL-GUARANTEE` as a SEBI twin, `SEBI-ADS-NO-GUARANTEE`. Author, Judge, Evidence. | **Reg 16C(1)**: a regulated person using AI/ML tools, in-house or from a third-party vendor, "irrespective of the scale and scenario of adoption", is "solely responsible" for (a) privacy, security and integrity of investor data, (b) the output of the tools, (c) compliance with law. Inserted w.e.f. 10.02.2025. **Reg 16A**: no direct or indirect association with a person who gives securities advice unregistered, or claims returns or performance without permission. Association includes money, client referral, and interaction of IT systems (Explanation 2). **Reg 16O(b)**: no guaranteed, risk-free or indicative returns. **Reg 16O(h)**: no content implying past performance may recur. **Reg 16O(k)**: no vague adjectives such as "high returns". **Reg 16J(1)(d)**: "essential communication" with existing clients is not an advertisement (inference: a servicing chatbot may fall outside the ad code, but Reg 16O(b) still says "prospective or existing clients"). **Reg 16M**: no dark patterns, referring to the CCPA 2023 guidelines. |
| `SEBI_2025-06-20_consultation-paper-responsible-ai-ml.pdf` | June 2025 consultation paper (17 pp). | Defines the likely final AI/ML guidelines. It is a **draft** and no final text exists on sebi.gov.in as of 31 Oct 2026. Feeds new cards `SEBI-AI-DISCLOSURE` and `SEBI-AI-GRIEVANCE`. Author, Gate, Evidence. | Para 5.1 model governance, including **5.1(k)** retain logs "with full verbosity" so events can be reconstructed chronologically, **5.1(l)** control to switch to manual, **5.1(h)** independent audit with findings sent to SEBI. **5.2(a)** to **5.2(d)**: disclose AI/ML use that directly affects clients; disclose features, risks, limitations and accuracy; use language customers can understand; AI grievances follow SEBI's existing framework. **5.3(d)**: keep documentation and input/output data for at least 5 years. **5.3(c)**: shadow testing. **5.4** fairness and bias. **5.5(c)**: report technical glitches and data breaches to SEBI. The paper also lists chatbots among current broker and MF AI uses. |
| `SEBI_2024-12-18_board-memo-ai-tools-responsibility.pdf` | Board memo behind the Reg 16C amendment. | Context: it shows why Reg 16C exists. Inference: usable as the rationale in an evidence pack. | Memo refers to the 13 Nov 2024 consultation paper. I did not locate that consultation paper itself. |
| `SEBI_2019-01-04_ai-ml-reporting-circular-brokers-dps.pdf` | Jan 2019 AI/ML reporting circular (brokers and DPs). | Historical. Reporting only, not conduct. **Para 2** is notable: advertised financial benefit from AI/ML "should not constitute misrepresentation". | **Para 6**: quarterly AI/ML reporting form within 15 days of quarter end, from the quarter ending March 2019. Scope para 3 covers robo-advisers and compliance tech. |
| `SEBI_2026-03-20_master-circular-mutual-funds.pdf` (748 pp) | MF master circular. | Shows the 2019 AI/ML reporting was folded into master circulars (**para 5.12**, **Annexure 5**). Chapter 14 holds MF advertisement rules. Also feeds MF disclaimer checks. | **Para 5.12** and Annexure 5: AI/ML reporting for MFs. **Chapter 14**: IDCW, performance and CAGR advertising rules. The Fifth Schedule advertisement code is referenced in the master circular. |
| `SEBI_2025-06-17_master-circular-stock-brokers.pdf` (399 pp) | Broker master circular. | Item 63 in its contents list is the AI/ML reporting circular, so the 2019 obligation continues for brokers. Algo and technology chapter. | Contents entry "63. Reporting for AI and ML applications and systems offered and used by market intermediaries". |

### Advertising, guaranteed-return and mis-selling rules

| File | What it is | NIYAM relevance | Key clauses |
| --- | --- | --- | --- |
| `SEBI_2026-02-06_master-circular-investment-advisers.pdf` | Current IA master circular (99 pp). | Core for SEBI conduct tests. Card ids `SEBI-IA-NO-ASSURED-RETURNS` (ads) and `SEBI-IA-AI-DISCLOSURE`. Attack and Judge on advisory bots. | **Para 10.1** advertisement code. 10.1(b)(iii) mandatory standard warning "Investment in securities market are subject to market risks. Read all the related documents carefully before investing" with no added or deleted words, minimum 10-point font. 10.1(b)(viii) disclaimer that registration does not guarantee performance. **10.1(c)(x)** guaranteed or risk-free return ban. 10.1(c)(vi) no statements exploiting lack of experience. **Item (xii)** (p. 20): IA using AI is solely responsible for client data, data used for advice and advice from AI output (cites Reg 15(14)), and must disclose the extent of AI use (cites Reg 18(9)) at the time of the agreement and when otherwise required. **Annexure A** para 2(b) "hold out" ban. Agreement clause 2 and 3 in the sample: "The IA does not guarantee returns... assured/guaranteed/fixed returns schemes... are prohibited by law". Page 52 prescribes a past-performance disclaimer ("Past performance is no guarantee of future results..."). Page 82 lists the investor tip "Inform SEBI about IAs offering assured or guaranteed returns". |
| `SEBI_2026-02-06_master-circular-research-analysts.pdf` | Current RA master circular (107 pp). | Same as above for research bots. Card ids `SEBI-RA-NO-ASSURED-RETURNS`, `SEBI-RA-AI-DISCLOSURE`. | **Para 1.7**: AI tools in RA services. Cites Reg 24(7) (sole responsibility) and Reg 19(vii) (disclose the extent of AI use). Advertisement code with the same guarantee ban, around p. 35. |
| `SEBI_2025-11-25_investment-advisers-regulations-2013-consolidated.pdf` | IA Regulations, amended to 25 Nov 2025. | Statutory text. | **Reg 15(14)**: AI sole responsibility. **Reg 18(9)**: disclose extent of AI use. Reg 15(9): abide by the Third Schedule Code of Conduct. Reg 15(15): comply with the Investor Charter. |
| `SEBI_2026-10-10_research-analysts-regulations-2014-consolidated.pdf` | RA Regulations, amended to 10 Oct 2026. | Statutory text. | **Reg 24(7)**: AI sole responsibility. **Reg 19(vii)**: disclose the extent of AI use. |
| `SEBI_2013-01-21_investment-advisers-regulations-2013-original-gazette.pdf` | Original 2013 gazette. | Historical only. Do not cite for current law. | Superseded by the consolidated text. |
| `SEBI_2023-04-05_advertisement-code-ia-ra.pdf` | April 2023 standalone IA/RA ad code circular. | Origin of IA master circular para 10 (footnote 27 of that master circular cites it). Superseded by the master circulars. | See the master circulars. |
| `SEBI_2025-01-08_guidelines-for-investment-advisers.pdf`, `SEBI_2025-01-08_guidelines-for-research-analysts.pdf` | Jan 2025 consolidated guidelines (12 and 21 pp). | Superseded in practice by the Feb 2026 master circulars (inference from the master circulars' footnotes). Useful for dating AI-disclosure requirements. | Not read in detail. |
| `SEBI_2025-06-02_investor-charter-investment-advisers.pdf` | IA investor charter. | Reg 15(15) makes the charter binding. Charter language on rights and grievances could seed disclosure checks. | Not read in detail. |
| `SEBI_2025-08_faq-registered-investment-advisers.pdf` | IA FAQ. | **Q48** restates the "hold out assured returns" language. Guidance only. | Q48. |
| `SEBI_2022-09-02_returns-claimed-by-unregulated-algo-platforms.pdf` | Returns claimed by unregulated algo platforms. | Context for return claims in marketing of AI or algo products. | Not read in detail. |
| `SEBI_2026-10-10_mutual-funds-regulations-2026-consolidated.pdf` | MF Regulations 2026 (88 pp). | Source of the MF standard warning for ad checks. Card `SEBI-MF-STD-WARNING`. | **Reg 28** (now pointing to Chapter IIID of the Intermediaries Regulations). **Fifth Schedule** (text shown in footnote 4): standard warning "Mutual Fund investments are subject to market risks, read all scheme related documents carefully." with no added or deleted words. Vernacular ads must carry it in the vernacular. Clauses (b) no testimonials or rankings, (e) no celebrities. Omitted w.e.f. 08.04.2027. |
| `SEBI_2000-06-05_mf-advertisement-guidelines.html` | Legacy 2000 MF ad guidelines. | Legacy only. | Treats forecasts of NAV growth or promised returns without backing as misleading. |
| `SEBI_2026-09-24_pr59-board-decisions-common-advertisement-code.pdf`, `SEBI_2026-09_board-memo-common-advertisement-code.pdf` | Board press release and memo on the Common Advertisement Code. | Explains the forthcoming single ad code. Para 4.2 of the press release: prior approval dropped except for celebrity ads, post-issuance reporting within 3 working days (the memo's own timeline may differ). | Illustrative non-advertisement list (see Reg 16J). |

### Association with unregistered entities and finfluencers

| File | What it is | NIYAM relevance | Key clauses |
| --- | --- | --- | --- |
| `SEBI_2025-01-29_association-with-unregistered-persons-clarifications.pdf` | Circular on Reg 16A (updated 8 May 2026). | Card `SEBI-NO-UNREGISTERED-ASSOC`. Attack: an agent that refers a customer to an unregistered advice channel. Judge, Evidence. | "Association" means money or money's worth, client referral, or interaction of IT systems. A person engaged solely in investor education is not "another person" if they do not give advice or claim returns. A "specified digital platform" carve-out exists. |
| `SEBI_2024-07_board-memo-association-with-unregistered-persons.pdf` | July 2024 board memo (finfluencer proposal). | Background only. | The memo reports that registered-entity finfluencers are already covered by ad codes. |
| `SEBI_2026-02-26_eodi-registered-name-on-social-media.pdf` | Feb 2026 circular. | Social media surface: disclosure of registered name and number by regulated entities and their agents. Card `SEBI-SMP-REGISTRATION-DISCLOSURE`. | Read title and addressees only. Details to be extracted by the card author. |

### Cyber resilience

| File | What it is | NIYAM relevance | Key clauses |
| --- | --- | --- | --- |
| `SEBI_2024-08-20_cscrf-circular.pdf` (205 pp) | CSCRF base circular. | Evidence-pack security controls. A NIYAM signed evidence pack should align with logging and audit expectations (inference). | Applicability table at p. 103 requires REs (except small and self-certification REs) to "prepare SOPs for open source application security and concerns from emerging technologies like Generative AI security". This is the only generative-AI hook I found in the CSCRF. |
| `SEBI_2024-12-31_cscrf-clarifications.pdf`, `SEBI_2025-03-28_cscrf-extension-of-timelines.pdf`, `SEBI_2025-08-28_cscrf-technical-clarifications.pdf` | Updates and timeline extensions. | Check timelines before citing an effective date. | Not read in detail. |
| `SEBI_2025-06_cscrf-faq.pdf` | CSCRF FAQ. | Guidance. | Its own preface says it is not a binding interpretation. |
| `SEBI_2026-08-24_cyber-incident-portal-fire-format.pdf` | Incident reporting aligned to FSB FIRE format. | Incident report format for AI-incident evidence packs (inference). | Read the English subject line only. |

### Grievance redressal and ODR

| File | What it is | NIYAM relevance | Key clauses |
| --- | --- | --- | --- |
| `SEBI_2023-09-20_scores-2-0-circular.pdf` | SCORES 2.0 circular. | Card `SEBI-GRIEVANCE-TAT`. Attack: customer asks where to complain. Judge: the agent must route to SCORES and ODR correctly and must not misstate timelines. | **Para 1.2** and **1.3**: entities resolve complaints and upload the ATR within **21 calendar days**. Complaints are auto-forwarded. **Para 2.2**: first review by the Designated Body, then SEBI. |
| `SEBI_2024-10_scores-2-0-faq.pdf` | SCORES 2.0 FAQs. | Customer-facing wording reference. | Not read in detail. |
| `SEBI_2023-07-31_online-dispute-resolution-circular.pdf`, `SEBI_2023-12-20_odr-amendment.pdf` | ODR circular and amendment. | Escalation path after SCORES. | The IA master circular sample agreement mentions SCORES and the Smart ODR portal (smartodr.in). |

### Algo trading

| File | What it is | NIYAM relevance | Key clauses |
| --- | --- | --- | --- |
| `SEBI_2025-02-04_algo-trading-retail-safer-participation.pdf`, `SEBI_2025-09-30_algo-trading-timeline-extension.pdf` | Retail algo trading framework and timeline extension. | Applies to API-based algo trading via brokers. Gate evidence for AI-driven order logic. | Brokers act as principals and algo providers as agents. The extension circular sets milestones. |

## 2. Not found, failed or blocked

- **Final SEBI AI/ML guidelines**: none published on sebi.gov.in as of 31 Oct 2026. The SEBI circulars listing page (checked) shows nothing on AI/ML in Oct 2026. News coverage says the SEBI Chair has repeatedly said guidelines will be issued shortly. Treat the June 2025 paper as a draft. WebSearch also returned a third-party page citing a "May 2026" SEBI AI circular, which I could not corroborate on sebi.gov.in, so I did not use it.
- **13 Nov 2024 consultation paper on assigning AI responsibility**: not downloaded. The Dec 2024 board memo is stored instead.
- **SEBI circular on AI chatbots or customer-interaction AI**: none found. Chatbots appear only as a use case in the consultation paper.
- **Older IA/RA master circulars (June 2025, May 2024)** and original Jan 2019 circulars for MIIs and MFs: not downloaded. Superseded or folded into the stored master circulars.
- **Blocked — download manually**: nothing was blocked. Every attempted SEBI URL returned HTTP 200.
- Not covered: AMFI advertisement code (AMFI is not a SEBI document), exchange circulars on broker advertisements.

## 3. Superseded or uncertain status

- Master circulars of 6 Feb 2026 supersede the June 2025 IA/RA master circulars, and the 2023 ad code and Jan 2025 guidelines are folded in (inference from the master circular footnotes).
- **Common Advertisement Code (Intermediaries Regs Chapter IIID)** and the omission of the MF Fifth Schedule are both footnoted with an effective date of 08.04.2027. I read the date as printed and did not resolve whether it is intended. Until then, the IA/RA master circular ad codes and the MF Fifth Schedule remain the operative texts.
- Reg 16A (association) is in force from 29.08.2024. Reg 16C (AI) is in force from 10.02.2025. Both dates come from the footnotes in the stored file.
- ODR: SEBI pages cite different numbers for the ODR framework (2023/131 for the circular, 2023/145 for a master circular in other sources). I stored the circular I could read (2023/131) and did not locate 2023/145.
- The consolidated IA Regulations file is amended only to 25 Nov 2025. Later amendments may exist.

## 4. Corrections or notes for existing NIYAM claims

- `RBI-MIS-SELL-GUARANTEE` is labelled RBI-only. SEBI texts independently prohibit "guaranteed" or "assured" return wording. Propose a SEBI twin (`SEBI-ADS-NO-GUARANTEE`) so the phrase list (`must_not_claim`) is traceable to a SEBI clause for securities-market clients.
- NIYAM's phrase list should add "risk free", "indicative returns", "target return", "minimum return" and "percentage accuracy" for SEBI surfaces. These phrases appear in the texts read.
- No contradiction found with the NIYAM docs on SEBI items. The docs make no SEBI-specific factual claims.
- Do not describe SEBI's AI/ML guidelines as final. The binding AI provisions today are Reg 16C of the Intermediaries Regulations, Reg 15(14) and 18(9) of the IA Regulations, and Reg 24(7) and 19(vii) of the RA Regulations.
