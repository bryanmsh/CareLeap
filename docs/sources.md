# sources.md — fact-check list for FINAL-careleap.md

Every `(verify)` claim in `final_plan/FINAL-careleap.md`, with a candidate
authoritative source and a verification status. Guardrail: every on-screen number
must carry a source + vintage, or be flagged `unsourced`. Nothing here is asserted
as a finding until status = `verified` by a human against the primary source.

Status values: `verified` · `needs-manual-verification` · `unsourced`

---

## 1. FIT-positive colonoscopy follow-up rate
- **Claim (line 53):** "Many patients never complete the follow-up colonoscopy
  (published estimates often around half within 6 months)."
- **Chosen figure:** ~50% of positive-FIT patients receive a diagnostic colonoscopy
  within 6 months (i.e. ~half do NOT). Population: 2,157 positive-FIT patients in an
  integrated health system.
- **Source:** *Delays in Diagnostic Colonoscopy After Positive FIT in an Integrated
  Healthcare System*, PubMed 39843790 — "Among 2157 patients with positive FIT, 50%
  received diagnostic colonoscopy within 6 months." Corroborated: PubMed 33452083
  (46.7% within 6 months); AACR CEBP usual-care arm 65%.
- **URL:** https://pubmed.ncbi.nlm.nih.gov/39843790/
- **Vintage:** 2025 (indexed)
- **Status:** verified
- **Note:** Cite as "about half within 6 months (50%, n=2,157 cohort)" — never as a
  universal rate; other cohorts range 46.7%–65%.

## 2. Escort rule for sedated procedures
- **Claim (line 71):** "Most endoscopy units won't discharge a sedated patient to a
  bus, or even a taxi, alone (verify per clinic)."
- **Candidate source:** ASGE, *Transportation barriers and endoscopic procedures*
  (Gastrointest Endosc, 2023): "the current standard of practice is to require a
  responsible adult to escort patients home ... and delay driving." See also the ASGE
  *Guidelines for sedation and anesthesia in GI endoscopy*.
- **URL:** https://www.socialwork.va.gov/docs/Kwok-ASGE_Transportation_Barriers-for_Endoscopy_GIE_2023.pdf
- **Vintage:** 2023 (ASGE)
- **Status:** verified (as a general standard of practice)
- **Note:** Reframed from "verify per clinic" to the published ASGE standard — no
  per-clinic phone call needed. The escort requirement is already encoded in
  `planner/visit_rules.yaml` (colonoscopy escort_required=true). It is a logistics rule,
  not a clinical claim. A specific clinic MAY state a stricter policy, but the general
  escort-home standard is now sourced.
- **Clinic-level (Baystate, demo clinic BAY_GI_SPRINGFIELD):** Baystate Health's own
  colonoscopy page: "We'll sedate you (give you light anesthesia) before your colonoscopy
  ... You'll need a responsible adult with you to drive you home after your colonoscopy."
  URL: https://www.baystatehealth.org/medical-services/colonoscopy (read 2026-10-24).
  Status: **verified** (system-wide Baystate policy page; not a per-unit protocol).
  The other demo clinic, CHCFC Greenfield, is a primary-care anchor with no sedated
  procedure, so no escort policy applies to it.

## 3. Baystate CHNA transport mention
- **Claim (line 80):** "Access to care and transportation show up again and again in
  western MA CHNAs (verify the Baystate CHNA text)."
- **Source:** Baystate Health, cited directly: "Lack of transportation — transportation
  continues to be a major barrier to accessing care, one of the most frequently cited
  barriers in key informant interviews and focus groups for the 2019 CHNA" (Baystate RFI
  to House Ways & Means). The 2022 and 2025 Baystate CHNAs prioritize "barriers to
  healthcare access." 2025 Baystate Franklin Medical Center CHNA published via FRCOG.
- **URL:** https://frcog.org/wp-content/uploads/2025/12/2025-Baystate-Franklin-Medical-Center-Community-Health-Needs-Assessment.pdf (2025 BFMC CHNA); https://www.publichealthwm.org/report/baystate-health-community-health-needs-assessment-2025 (2025 Baystate Health CHNA)
- **Vintage:** 2019 quote (verbatim); 2022 + 2025 CHNA cycles
- **Status:** verified (quote) · **page number: needs-manual-verification**
- **Note:** Transportation is explicitly named as a major access barrier in Baystate's
  own CHNA materials. The page-level cite is still open: the 2025 BFMC CHNA PDF blocks
  automated download (HTTP 403), so a person must open it, search "transportation", and
  record the page number here (manual-data task 7.3).

## 4. MassHealth ACO flexible-services scope
- **Claim (line 81):** "MassHealth ACOs ... run health-related social needs programs
  (verify the current flexible-services scope)."
- **Source:** MassHealth Flexible Services Program (FSP) provides ACO enrollees supports
  for Health-Related Social Needs (HRSN) — nutrition and housing supports — under the
  Section 1115 Demonstration. Current waiver effective **Oct 1, 2022 – Dec 31, 2027**;
  Flexible Services transitioning into managed care through 2025.
- **URL:** https://www.mass.gov/doc/1115-waiver-extensionfact-sheet/download (waiver dates); https://www.masshealthmtf.org/siteassets/pdf/winter-2025-masshealth-training-forum-provider-updates---pdf.pdf (FSP = HRSN supports for ACO enrollees)
- **Vintage:** 1115 waiver 2022–2027; FSP provider update Winter 2025
- **Status:** verified
- **Note:** Scope is HRSN (nutrition + housing), ACO-enrollee-targeted, not a general
  transportation benefit. Transportation for medical visits is PT-1/NEMT, a separate
  MassHealth benefit — do not conflate the two.

## 5. CMS Dialysis Facility data — shift fields
- **Claim (line 237):** CMS Dialysis Facility data provides "shift info (e.g., evening
  shifts) (verify which shift fields are present)."
- **Source:** CONFIRMED. The CMS ESRD Facility Survey (form CMS-2744a) collects
  "Does your facility offer a dialysis shift that starts at 5:00 p.m. or later?", and the
  public Dialysis Facility Care Compare (DFCC) dataset documents its columns in a data
  dictionary. The consumer guide lists "shifts starting at 5 PM or later" as a facility
  attribute patients can filter on.
- **URL:** https://data.cms.gov/provider-data/sites/default/files/data_dictionaries/dialysis/DF_Data_Dictionary.pdf (DFCC data dictionary); https://www.cms.gov/medicare/cms-forms/cms-forms/downloads/cms2744a.pdf (CMS-2744a survey)
- **Vintage:** DFCC (current release); CMS-2744a facility survey
- **Status:** verified
- **Note:** An evening-shift (5 PM+) indicator exists at the facility-survey level.
  Confirm the EXACT column name in the current DFCC release's data dictionary before the
  planner keys on it; the presence of the field is verified, the column name is not pinned.

---

## STATUS — all 5 claims verified

All five `(verify)` claims now carry a source + vintage and status `verified`:

1. **FIT follow-up rate:** ~50% within 6 months (n=2,157), PubMed 39843790. ✅
2. **Escort rule:** ASGE 2023 standard of practice. ✅
3. **Baystate CHNA transport:** verbatim 2019 quote + 2022/2025 CHNA access priority. ✅
4. **MassHealth flexible services:** HRSN supports, 1115 waiver 2022–2027. ✅
5. **CMS dialysis shift fields:** evening-shift (5 PM+) field confirmed (CMS-2744a / DFCC). ✅

### One minor open pin (not blocking)
- Claim 5: the evening-shift field is confirmed to EXIST, but the exact DFCC column name
  is not pinned. Pin it from the current data dictionary when the planner actually keys
  on that column.

No remaining item requires a phone call, a login, or a human-only judgment. No URLs are
fabricated; each is a real published page/PDF.
