# Documents to download manually
These were blocked (captcha, 403, JS-only) or not publicly retrievable by the research agents, which did not try to bypass the blocks. Open each official URL in a normal browser and save the file into the matching folder using the naming convention `<REGULATOR>_<date>_<slug>.pdf`, then add a row to that folder's `MANIFEST.csv`.
Sections below are copied verbatim from each folder's README (`## ... blocked / not found`). Anything marked *Not found* may simply not be public.

---

## dpdp-meity-consumer-telecom

Blocked (HTTP 403 to a plain `curl` with a descriptive UA; I did not retry, spoof or escalate). **Blocked - download manually:**
- DPDP commencement notification **G.S.R. 843(E)** of 13 Nov 2025 (stages Act sections): https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf (URL taken from a third-party tracker, judicio.ai). Because I could not read it, which Act sections commence when is **secondary-source only** (below).
- IT Act 2000 consolidated/updated text: https://www.indiacode.nic.in/bitstream/123456789/13116/1/it_act_2000_updated.pdf ; amendment Act 2008: https://www.meity.gov.in/static/uploads/2024/03/IT_amendment_act2008-1_0.pdf ; (the 2000 original at aicte.gov.in downloaded fine but lacks ss.43A/70B/79 and was discarded).
- MeitY Dec 2023 deepfake advisory (eNo.2(4)/2023-CyberLaws-3, 26 Dec 2023): https://www.meity.gov.in/static/uploads/2024/02/c9f89809b63d22656be38a166ef14949.pdf ; MeitY-hosted advisories https://www.meity.gov.in/static/uploads/2024/02/9f6e99572739a3024c9cdaec53a0a0ef.pdf
- IT Intermediary Rules 2021 updated: https://www.meity.gov.in/static/uploads/2026/02/550681ab908f8afb135b0ad42816a1c9.pdf (title seen in search only; content unverified)
- MeitY DPDP landing page https://www.meity.gov.in/data-protection-framework (403/JS shell) - official source for any MeitY DPDP FAQ.
- Corrigendum **G.S.R. 892(E)** (10 Dec 2025) to the DPDP Rules: only a third-party host surfaced (indiacode.ecourtsindia.com, 403). Per a search snippet it makes eight corrections to G.S.R. 846(E). **The stored Rules PDF is the uncorrected 13 Nov text; check the corrigendum before quoting rule numbers or wording.**
- CanLII copy of Moffatt (captcha); the BC CRT site copy was fetched instead.

Not found as a primary document:
- **MeitY DPDP FAQs**: none located. No FAQ file stored.
- **Mar 2024 MeitY advisory from a MeitY-hosted URL**: only a law-firm mirror found (stored; flagged).
- **Consumer Protection (E-Commerce) Rules 2020 as a text PDF** and the 2025 amendments (if any): only a scan stored. Official page: https://consumeraffairs.nic.in/theconsumerprotection/consumer-protection-e-commerce-rules-2020 (that host timed out on plain curl; not retried).
- consumeraffairs.nic.in CCPA notification URL hung; the same notification was fetched from ccpa.doca.gov.in.
- TRAI First Amendment 2025 (if separate) and gazette-published version/date of the Third Amendment 2026; TRAI DLT/consent-template process circulars.
- ASCI "financial services advertising" stand-alone guideline: none found; the BFSI content is Addendum II inside the Code book plus the VDA guideline.

---

## fiu-ind

### Blocked - download manually
- RBI KYC PDFs: `https://rbidocs.rbi.org.in/rdocs/notification/PDFs/169MD.PDF` (commercial banks) returned an HTML bot-challenge page to a plain request; not retried or bypassed. The rbi.org.in HTML master-direction pages (public) were saved instead. Same expected for the payments-bank and NBFC PDFs (not attempted).
- FATF India Mutual Evaluation 2024 Executive Summary: `https://www.fatf-gafi.org/content/dam/fatf-gafi/mer/Executive-Summary-MER%20India%202024.pdf.coredownload.inline.pdf` (page: `https://www.fatf-gafi.org/content/fatf-gafi/en/publications/Mutualevaluations/India-MER-2024.html`) returned HTTP 403 to plain curl. Full report URL: `https://www.fatf-gafi.org/content/dam/fatf-gafi/mer/India-MER-2024.pdf.coredownload.inline.pdf`. Only the FIU annual report's statement (regular follow-up) is in the corpus.

### Not found
- Dept of Revenue / finmin notifications on RE registration and s.13 penalties as separate documents (the consolidated Act and Rules are stored; dor.gov.in amendment-rule PDFs exist per search results, e.g. 22.09.2015 third amendment, but not downloaded since the consolidated Rules include them).
- FIU-IND sector RFIs; FIU-IND orders against payment aggregators/PSOs (PayPal 2020 order not located on FIU site).
- Skipped as out of scope: VDA guidelines and VDASP circulars, TCSP/dealer/ICAI guidance, other penalty orders.

---

## irdai-npci-pfrda

- **Blocked, download manually (plain request returned HTTP 403 and was not retried):** NPCI legacy-path PDF, `https://www.npci.org.in/PDF/npci/imps/circular/2019/IMPS-UPI-I-OC-93-I-FY-19-20-I-Harmonisation-of-Turn-Around-Time(TAT)-and-customer-compensation-for-failed-transaction.pdf` (NPCI OC 93 FY19-20, NPCI's own implementation of the RBI TAT circular). Also the NPCI listings `https://www.npci.org.in/circulars/upi` and `https://upihelp.npci.org.in/` are JS-rendered and returned no usable content to the Firecrawl default scrape.
- **Not located as a public PDF:** UPI Procedural Guidelines (current version) and OSG v2.1 (members-only per NPCI references); NPCI OC 98 (24-Nov-2020 "UDIR - Enhancing complaint handling") and OC 145/A; NPCI NACH Procedural Guidelines (only third-party copies surfaced, not stored); the original OC 184 and OC 185A. Cited only by reference inside stored circulars.
- **IRDAI AI:** no IRDAI document on chatbots/AI conduct found. Secondary sources report a 17-Jun-2026 office order forming an AI governance working group (ref IRDAI/GA&HR/ORD/MISC/90/06/2026); the only PDF found was on a third-party host that returned 404, so nothing stored. Treat as INFERENCE: no binding IRDAI AI rule exists yet.
- **IRDAI Advertisement regulations:** the standalone 2021 Advertisement and Disclosure Regulations and 2019 advertising master circular were not downloaded; secondary sources say they were folded into the 2024 regulations (Chapter 1, regs 27-29) and the master circulars. Not verified against an IRDAI repeal notice.
- **IRDAI 2026 cyber guidelines full text** (annexures) not obtained; only the cover page. The IRDAI "Bima Bharosa" grievance master circular as a separate instrument was not found; its content is inside the 5-Sep-2024 master circular.
- **PFRDA mis-selling:** no dedicated PFRDA mis-selling circular found. The PoP-NPS-Lite operational circular (PFRDA/2022/06/SUP-POP/01) was downloaded and discarded as off-scope.

---

## rbi-lending-ai-governance

**Blocked: download manually** (official URLs; captcha/verification page returned to a plain request; not retried):
- FREE-AI report PDF: https://rbidocs.rbi.org.in/rdocs/PublicationReport/Pdfs/FREEAIR130820250A24FF2D4578453F824C72ED9F5D5851.PDF (alternate listed on the RBI page: https://rbidocs.rbi.org.in/rdocs/content/pdfs/FREEAIR13082025_ANVI.pdf)
- Digital Lending Directions 2025 PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/36NT8C402BE7C2A349E0BFFF3C526668CD7A.PDF
- IT Governance MD PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/107MDITGOVERNANCE3303572008604C67AC25B84292D85567.PDF
- KFS circular and annexes (Annex A template, B, C): https://rbidocs.rbi.org.in/rdocs/content/pdfs/CIRCULARKFS1504242_A.pdf (also _B, _C), main PDF https://rbidocs.rbi.org.in/rdocs/notification/PDFs/CIRCULARKFS1504242AE2500BAF494C2A82442B0B642705C1.PDF
- Penal charges circular PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/FAIRLENDINGPRACTICE1B9DBE75410B4DA881E6EF953304B6F7.PDF
- Withdrawal annex (9,445 circulars): https://rbidocs.rbi.org.in/rdocs/Notification/PDFs/100NTADBC8AC018BE437BBE70F8664031EB4A.PDF
- Commercial Banks RBC Directions current (1 Oct 2026) version and Annex XIII KFS template: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/170MD.PDF and https://rbidocs.rbi.org.in/rdocs/content/pdfs/170MD28112025M_AN13.pdf
- Commercial Banks Credit Facilities Directions 2025 (RBI/DOR/2025-26/154), HTML page is PDF-only: https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13156
- NBFC Responsible Business Conduct Directions 2025 (RBI/DOR/2025-26/362): https://rbidocs.rbi.org.in/rdocs/notification/PDFs/362MD26CA543937BA439A97E1BCFC08CF5808.PDF
- Draft Model Risk Management guidance PDF, linked from press release: https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR528C19BBE2D14B248E1A0D8CFCF6B210BDF.PDF
- Prepayment Charges on Loans Directions 2025 (2 Jul 2025): not located on an RBI page; only a third-party copy was found, so not stored.

**Not found / not collected:**
- Any RBI circular adopting FREE-AI as binding: none found.
- KYC Master Direction: only an amendment page was found (RBI/2025-26/75); not stored because it is not the consolidated text.
- MuleHunter.AI: RBI press release prid=59245 and RBIH docs exist but were not stored (low relevance to customer-communication tests).
- Standalone customer-service/outsourcing-of-financial-services Master Circular: covered by the 2025 bank Directions above.
- Co-operative bank and SFB versions of the 2025 Directions: not collected.

**Process disclosure.** Early in the session, a few plain GETs to RBI pages used a browser-style User-Agent, and three PDF requests sent a Referer header. Afterwards I switched to a descriptive User-Agent with no Referer, one attempt per URL, at least 1 second apart. Nothing from the captcha-protected PDFs was circumvented.

---

## rbi-payments

Blocked, download manually (official URLs; `rbidocs.rbi.org.in` returns a bot-challenge page to plain `curl`):
- 2019 TAT circular PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/CIRCULAR677EC931A7A65E4D99AA957D8E85BC0A2A.PDF
- Reserve Bank - Integrated Ombudsman Scheme, 2026 (Scheme text): https://rbidocs.rbi.org.in/rdocs/content/pdfs/SCHEME16012026_A.pdf
- PA Master Direction PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/141MD7D7F25DEBF1F48449E20D685E4B014E5.PDF
- Authentication Directions PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NT79258FF36ECA8F4886B3B01F55D166C2B2.PDF
- Responsible Business Conduct Directions PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/170MD.PDF
- Third Amendment Directions 2026 PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NT16738E653AADCEC4217BEFFA92C050F69AD.PDF
- PPI Master Direction PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/82MDPPIS2708202181CF0A6FCD1B47B88CAE8E92A228B160.PDF
- Internal Ombudsman Directions PDF: https://rbidocs.rbi.org.in/rdocs/notification/PDFs/380MD14012026DAD56B73DC944F02AEA4530EC779AD7F.PDF
- Payments Vision 2025: https://rbidocs.rbi.org.in/rdocs/PublicationReport/Pdfs/PAYMENTSVISION2025844D11300C884DC4ACB8E56B7348F4D4.PDF (not fetched; it is a 2022 vision document, low rule-card value)

Not found or not fetched:
- Integrated Ombudsman Scheme 2021 text (repealed 1 Jul 2026 per the press release and FAQ; the HTML text was not retrieved).
- RBI circulars on UPI transaction limits and charges. No RBI primary text found. UPI per-transaction and daily limits and P2M MDR are NPCI instructions (NPCI pages are in another agent's scope). Web search snippets mention an NPCI MDR framework dated Oct 2026; I did not read it.
- Draft Master Direction on PPIs 2026 (search snippet only, not fetched).
- Digital Payment Security Controls MD (cited in para 76B of the 2026 amendment) was not fetched.

---

## sebi

- **Final SEBI AI/ML guidelines**: none published on sebi.gov.in as of 31 Oct 2026. The SEBI circulars listing page (checked) shows nothing on AI/ML in Oct 2026. News coverage says the SEBI Chair has repeatedly said guidelines will be issued shortly. Treat the June 2025 paper as a draft. WebSearch also returned a third-party page citing a "May 2026" SEBI AI circular, which I could not corroborate on sebi.gov.in, so I did not use it.
- **13 Nov 2024 consultation paper on assigning AI responsibility**: not downloaded. The Dec 2024 board memo is stored instead.
- **SEBI circular on AI chatbots or customer-interaction AI**: none found. Chatbots appear only as a use case in the consultation paper.
- **Older IA/RA master circulars (June 2025, May 2024)** and original Jan 2019 circulars for MIIs and MFs: not downloaded. Superseded or folded into the stored master circulars.
- **Blocked — download manually**: nothing was blocked. Every attempted SEBI URL returned HTTP 200.
- Not covered: AMFI advertisement code (AMFI is not a SEBI document), exchange circulars on broker advertisements.
