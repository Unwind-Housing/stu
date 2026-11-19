# Functional spec

What the product must do, in plain terms. docs/DESIGN.md records how each requirement is built.

## 1. Purpose
Give a small community land trust one place to track its homes, the households that apply for and live in them, and its ongoing stewardship obligations, at low cost and with little effort to run.

## 2. Users
| User | Uses it to |
|---|---|
| CLT staff (stewardship, homeownership) | Manage properties, households, occupancies, verifications, insurance, requests, sales, documents |
| Intake reviewer (Applications and Sales app) | Set up projects, review screeners and pre-screens, run selection, verify income, assets and debts, certify households, match them to homes |
| Finance (CFO, bookkeeper) | ERRR ledger, fees, monthly reconciliation to QuickBooks |
| Board or read-only | View portfolio and status |
| Applicants and homeowners | Never log in. They interact only through online forms and email. |

## 3. Scope
The product is **two apps in one environment**:
- **CLT Stewardship** (the core solution): properties, households, occupancies and everything after purchase. Every client installs it.
- **CLT Applications and Sales** (an optional second solution, built on the core): screeners, projects, selection, full applications and certification. A CLT that selects buyers some other way skips it and hands winners over through the same handoff (H-1).

In: properties and their funders' covenants; projects and eligibility rules; households and members; occupancies; intake (screener and full application data); pre-screen, selection and certification; matching households to homes; annual verification; insurance; homeowner requests; resale price calculation; sales (initial and resale); funder reporting; documents; ERRR; fees.

Out, on purpose:
- Subsidy accounting: draws, disbursements and allocation tracking. Funders appear only as each home's covenant (who funded it, contract, target AMI, term).
- Funder-specific rule sets (decided 2026-11-10). Eligibility is the organization's rules plus each project's overrides; any funder requirements go in the project's notes. This keeps simple deployments simple.
- Waitlists as a general feature. A project's ranked selection list is project-specific and ends when the project closes.
- A public applicant portal (the forms platform handles that)
- Accounting (QuickBooks remains the general ledger)
- Multi-tenant hosting (each CLT gets its own installation)

## 4. Requirements by area

### Portfolio
- P-1. Record each property: address (with state and county chosen from staff lists, and only the chosen state's counties offered), parcel number, type, tenure, bedrooms, bathrooms, size, year built, AMI target, status.
- P-2. Homes offered together are grouped by project (J-1). There is no separate development or neighborhood table.
- P-3. Show each property's current occupancy, full occupancy history, sales, requests, fees, ERRR ledger and documents in one place. Insurance policies belong to the occupancy (the owner's policy), not the property.
- P-4. Track replacement cost, with an "as of" date.

### People and occupancy
- O-1. Record households, their members, and each member's role and relationship.
- O-2. Link a household to a property through an occupancy with start and end dates, role (owner or tenant) and status. A property has at most one current occupancy.
- O-3. Keep the full history as homes change hands.

### Intake
- I-1. Receive screener and full application entries from any online forms platform (Cognito Forms, Jotform, FormAssembly) without changing the app.
- I-2. Create or update the household, members, application, income sources, debts and assets automatically. Re-submitting a form updates the records instead of duplicating them.
- I-3. Match form answers to the CLT's own dropdown values. Staff maintain the matching, and unmatched answers are kept as text.
- I-4. Reviewers mark each income, debt and asset as accepted, adjusted (with a verified amount) or excluded (with a reason). Totals and income as a percentage of AMI calculate automatically on the certification (see C-2).
- I-5. Track each application's stage from screener through selection, certification and matching to purchase.
- I-6. Show submissions that couldn't be processed, with the reason.
- I-7. The full application collects optional demographics (Hispanic or Latino; race, check all that apply; special needs, check all that apply) and current housing costs (housing situation, monthly rent or mortgage, utilities included, monthly utilities, and owner costs if applicable). Demographic answers are optional, never affect eligibility, and are restricted by column security.

### Projects and eligibility
- J-1. A project is a selling (or rent-up) campaign for one or more homes: for example, a new development phase, or the resale of a single home. It holds its homes, application window, selection method, eligibility overrides and pre-screen settings.
- J-2. Organization eligibility: one record of the CLT's own rules, used by every project: max income (% of AMI), optional minimum (% of AMI), first-time buyer required, lives or works locally (with the local area, for example a named county for at least 1 year), asset limit, housing ratio max, total debt ratio max, homebuyer education required, and how long a certification stays valid. Staff change it without a developer.
- J-3. Each project can override any of those rules (for example a lower max % of AMI). A blank project rule uses the organization's. Funder requirements go in the project's notes.
- J-4. Each home records its funders' covenants (funder from a staff list, contract number, target AMI, covenant start, years and end), for stewardship and reporting.
- J-5. A resale project sets its rules from the covenants on the home, so the next buyer is tested against the rules that apply to that house.
- J-6. AMI comes from HUD's income limits, kept as one record per county per year: the 50% (very low income) limit for household sizes 1 to 8, plus median family income for reference only (HUD's "family" isn't our household). 100% AMI = 2 x the 50% limit for the household size. Over 8 people, HUD's rule: the 4-person limit x (1.32 + 0.08 per person over 8). Source is HUD or Other; only HUD records define AMI. Entered by staff once a year (later option: fetch from HUD's Income Limits API).
- J-9. Each screener's stated income is shown as a % of AMI (whole number), worked out on intake from its county, household size and the newest HUD limits, and recalculated when new limits are loaded.
- J-10. Each screener shows its organization eligibility, worked out live from the stated answers against the organization's rules: Eligible, Not eligible (with the rules not met), or Needs review (with the missing answers), plus an Is eligible yes or no for lists. It covers % of AMI, first-time buyer, local tie and assets; housing ratios need a home's monthly cost and are checked at pre-screen.
- J-11. Screener answers are the applicant's own statement: staff can't edit them in the app. Corrections are made in the forms platform and flow through. Every change to an application is kept in its audit history (who, when, old and new value).
- J-8. A resale project chooses how to find its buyer: run its own application and selection, or reuse a recent project's ranked list that's still in effect, when the home size and funding rules match. Reusing a list keeps its ranks and statuses.
- J-7. Each project sets its own selection priorities: household size priority tiers for each bedroom size (for example, for a 2-bedroom home, 4 people first, then 3, 2 and 1), and any preference tiers.

### Eligibility and selection
- E-1. The screener is generic, not tied to a project. Staff add each application to a project (one project per application). A household interested in another project submits the screener again. Each application records the source form it came from (forms platform and form), so staff can filter by it when adding applications to a project. A form made for one project can add its new applications to that project automatically. Staff can add applications to a project from a filtered list, ticking some or adding everyone shown.
- E-2. When the application period closes, each application gets a Unique ID for that project (ID-0001, ID-0002 and so on, in submission order).
- E-3. Blind lottery: names are visible on screeners and applications, but nobody can influence who is selected because of who they are. Eligibility follows written rules (E-4), the order is set by submission time (E-2), the pools are locked before the draw (E-7), luck comes from the Board Observer's dice (E-9), and the ranking is a formula with no manual changes (E-14). The pool lists and results the Board Observer initials and signs show Unique IDs, tiers and lottery numbers only, no names. See BL-1 to BL-5.
- E-4. Pre-screen: the system checks each screener's self-reported answers against the project's eligibility rules (the organization's where the project leaves one blank) and the project's screening buffers, records each test with its value and limit, and marks the application Eligible for selection, Not eligible or Needs review, giving the reason. Screened-out applicants get a written notice with the reason and how to ask for a review.
- E-5. The pre-screen checks both ends of income: stated income no more than the project's buffer above the limit (default 10% over, so 110% of the limit), and at least enough to afford the project's homes at the eligibility housing ratio. It also applies the project's housing ratio and debt ratio buffers, credit and bankruptcy tests.
- E-6. Pools: one list per bedroom size, holding every household that passes screening for that size. A household can be on several lists under the same Unique ID. Each household gets the priority tier set by the project for its household size on each list (J-7).
- E-7. Pools are locked before the draw: the Board Observer reviews and initials the pool lists, and no household can be added or removed afterward.
- E-8. Selection method per project: **lottery** or **first come first served**, without changing the rest of the process. Both rank each list by priority tier first (household size for the bedroom size, then any preference tiers, J-7); only the tiebreaker differs: lottery number for a lottery, submission time for first come first served. First come first served runs as a **rolling list** by default (households are ranked as they apply, with no draw); a project can instead run it as a **campaign** with an application window and closing date.
- E-9. The lottery runs in the app and can be verified by anyone. At the draw, on the recording, the Board Observer rolls a 10-sided die ten times; the 10-digit roll sets the seed. Each household gets one lottery number from a published formula applied in Unique ID order (after a fixed warm-up, so no household is disadvantaged by its place in the order), and the same roll always gives the same numbers. The app records the roll and seed, the run time, who ran it and who observed, every entrant, each lottery number and each rank. Each list is ranked by priority tier, then lottery number. Once the result is certified it can't be changed.
- E-10. The Board Observer and the Lottery Administrator sign a lottery certification, which is kept with the lottery record in the project's documents.
- E-11. Staff invite the top households on each list to the full application (default 10 per list, and at least twice the number of homes of that size), each with a response deadline (default 15 days). A household that misses its deadline, stops responding or is found ineligible is replaced by the next on the list, and each replacement is recorded with the date and reason.
- E-12. Purchase offers go to approved (certified) households in rank order. No lower-ranked household is offered a home while a higher-ranked one on the same list is still within its deadline. A household that accepts a home is removed from every other list.
- E-13. The ranked lists stay in effect until every home in the project has closed, or for 12 months after the draw, whichever comes first.
- E-15. Weighted lottery (optional, per project): the project lists **lottery factors**, each worth a number of extra chances (for example "works in the county: +1"). Every household starts with 1 chance and adds the extra chances for each factor it meets. More chances means better odds, never a guaranteed place: a household with 2 chances has a 2 in 3 chance of ranking ahead of a household with 1. Weights only work inside a priority tier; tiers still come first. Factors and each household's chances are fixed when the pools lock, shown on the pool lists, and verified at certification. If a claimed factor isn't verified, the household's position is recalculated from its same lottery number with the verified chances, and the change is logged. Every factor needs a stated basis and a fair housing review before use.
- E-14. No re-ordering by hand (decided 2026-11-09). After the ranking, a household's position changes only through recorded statuses (ineligible at certification, declined, unresponsive, accepted a home on another list, withdrew), each with a reason and date. The original rank always stays visible.

### Blind lottery safeguards (decided 2026-11-09)
- BL-1. Pre-screen overrides (for example Needs review to Eligible) record who, when and why, and are only possible before the pools lock.
- BL-2. Locking the pools makes the selection entries read-only in the data, not just on the form, for everyone except a system administrator. Every change to an entry is kept in the audit log.
- BL-3. At the lock, the app computes a **check number** for each pool list from every Unique ID, tier and number of chances, with a published formula. It is printed on the list the Board Observer initials, and the verifier workbook recomputes it. Any later change to the list changes the number.
- BL-4. Screener answers used for screening and pools freeze when Unique IDs are assigned. Later edits change nothing; the form submission is flagged for staff to review. A rolling first come first served list ranks by first submission time.
- BL-5. Notices to applicants who are screened out or not selected are sent by the system, and every notice is logged.

### Handoff to Stewardship
- H-1. When a selected, certified household signs a purchase and sale agreement, a single action creates (or updates) the Household and its members in CLT Stewardship, copies the certified figures (household size, annual income, AMI %, certification date and expiry), creates the Occupancy for the matched home in Pending status, and creates the Sale (Under contract). From then on the household is managed in CLT Stewardship.
- H-2. At closing the occupancy becomes Current and the household becomes Homeowner (R-3).
- H-3. The handoff is documented as a contract (which fields, which statuses), so a CLT using another selection tool can bring winners in by import instead.
- H-4. The household's documents are copied from the forms platform to its Household Documents folder at the handoff. Documents of applicants who never reach the handoff stay in the forms platform and are purged on schedule.

### Certification
- C-1. A household has at most one active certification. Statuses: Reviewing, Waiting for more information, Certified, Not certified, Expired. It can move back and forth between Reviewing and Waiting for more information as needed.
- C-2. Staff review the full application's income, debt and asset lines (accept, adjust with a verified amount, or exclude with a reason), then fill in four figures: certified household size, certified annual income, certified assets, certified monthly debt.
- C-3. At Certify, the system tests the household against the project's eligibility rules (the organization's where the project leaves one blank) and records each test as a check (test, value, limit, pass or fail). Certify succeeds only if every check passes.
- C-4. One person, one Certify action. On Certify, the four figures and the line items lock, and an expiry date is set from the eligibility rules' validity period. Changing anything afterward means re-certifying.
- C-5. If a household isn't certified, staff record a reason and email the household themselves.
- C-6. Housing and debt ratios are calculated at certification (estimated, from the pre-approval) and again at closing (final, from the actual loans).
- C-7. Certifications expire automatically on their expiry date.
- C-8. Each certification has a required-documents checklist that staff build (per household or per member), each item with a status (Missing, Received, Accepted, Rejected, Expired, Waived). At Certify, open items are listed as a warning; staff can still certify, and the open items are recorded on the certification.

### Matching and purchase
- M-1. A certified household is matched to a specific home in the project, following the offer order in E-12. This creates a sale in Pre-purchase status.
- M-2. Sale statuses: Pre-purchase, Under contract, Closed, Cancelled. At closing the household becomes the homeowner (see R-3).
- M-3. The sale records the purchase financing the funder report needs: purchase price including closing costs, rehab cost, buyer cash, sweat equity, other assistance, each loan (type, lender, amount, rate, term, amortization, deferred or not, monthly payment), and monthly taxes, insurance, mortgage insurance, association dues, land lease fee and utilities.

### Funder reporting
- FR-1. Produce each funder's report from the same data. First: the WA HTF Homebuyer Information Form, one per homebuyer, from Household, Certification and Sale.
- FR-2. Rental reporting (WBARS) is planned for HTF rental projects, using the same demographics.

### Stewardship
- S-1. Create annual verifications ahead of each occupancy anniversary, send the homeowner a form link, and match the reply to the right verification automatically.
- S-2. Track insurance policies and flag homes that are underinsured against replacement cost, or whose policy is renewing soon.
- S-3. Track homeowner requests (capital improvements, ERRR repair draws, refinance, renting, leave, intent to sell, transfers) through to a decision. Approved capital improvements add to the home's resale credits.
- S-4. Provide work queues: new screeners, pre-screens needing review, selection rounds in draft, certifications in review or waiting for information, certifications expiring soon, matched homes, verifications to do, renewals, underinsured policies, open requests, sales in progress.

### Resale and sales
- R-1. Calculate each occupancy's formula price and maximum resale price using its own formula terms: fixed annual rate (compounding) or appraisal share, with optional floor, cap and rounding, plus improvement credits.
- R-2. Within a resale project, the sale on a home with a current owner is a resale and captures the seller's price figures. A home with no owner makes it an initial sale. Matching (M-1) creates the sale; staff no longer pick the buyer by hand.
- R-3. At closing, end the seller's occupancy and create the buyer's occupancy with the right formula terms. Sale documents are filed in the property or household library (see D-1), so nothing needs to be carried over.

### Documents
- D-1. Documents are stored in SharePoint, in three libraries, each file with a document type and date (SharePoint columns; staff maintain the types).
  - **Property documents** stay with the house: deed, survey, appraisals, inspections, warranties, repair invoices, recorded ground leases.
  - **Household documents** go with the people, in a restricted library: eligibility documents, certifications, closing disclosure and loan documents, annual verification uploads, correspondence.
  - **Project documents** belong to a project: the lottery record (locked pool lists, conflict of interest confirmations, recording, signed certification, notices), funder contracts.
  - Occupancy and sale documents are filed under the property or household by the house-or-people rule.
- D-2. When a household is certified, its uploaded documents are copied from the forms platform into its household documents automatically.
- D-3. Uploads from households that are never certified stay in the forms platform and are purged on a schedule.

### ERRR and fees
- F-1. Keep each property's ERRR balance as a ledger that stays with the house through every sale.
- F-2. Post each home's monthly ERRR contribution from its fee schedule. ERRR amounts vary by home and change over time.
- F-3. Record repair draws against approved requests, plus returned payments and adjustments.
- F-4. Reconcile the sum of property balances to the QuickBooks ERRR total each month, allowing for interest that isn't allocated to homes.
- F-5. Load opening balances and fee schedules when migrating from another system.

### Settings
- A-1. Staff can add, rename, reorder and deactivate values in the editable lists (states, counties, property types, income types and so on) without a developer.
- A-2. Properties, households, occupancies, applications, sales and homeowner requests each get a short record number when created (P-00001, H-00001, O-00001, A-00001, S-00001, R-00001) that staff can quote.
- A-3. Names fill themselves in: a property is named by its address, a household by its primary applicant's last name (adding the first name if another household has that name), and an occupancy as "household last name - address".

## 5. Non-functional requirements
- N-1. Cost: runs on the nonprofit Power Apps per app donation for up to 10 users.
- N-2. Maintainability: low-code, maintainable by a small team. Custom code in the running app is limited to a few small form scripts for obvious conveniences (such as filling in names).
- N-3. Updates: one managed solution; each CLT receives updates without losing its data, its lists or its settings.
- N-4. Usability: simple. Short navigation, one form per record with related lists, and queues that show what needs doing.
- N-5. Privacy: no SSNs or bank account numbers in Dataverse; applicant documents stay in the forms platform until the household is certified, and only certified households' documents are copied out, into the restricted household library; income, assets, dates of birth and demographics are restricted by column security; each CLT's data stays in its own Microsoft tenant.
- N-6. Portability: nothing specific to one CLT is built into the solution. Form IDs, emails, schedules and list values are settings or data.

## 6. Open questions
- Should "Domestic partner" be its own relationship value?
- Do any client CLTs own and lease rental units directly?
- Can the ERRR interest pool cover a draw larger than a home's balance? (Policy decision.)
- Which preference tiers does a CLT use besides household size, if any? (Proposed default: none.)
- Invites per list. (Proposed default: top 10, and at least twice the number of homes of that size.)
- A household that declines an offered home. (Proposed default, from one CLT's draft procedure: moves to the bottom of that list once; a second decline removes it from the lottery.)
- Offer order when a household is on more than one list. (Proposed default: largest homes first.)
- Decided (2026-11-09, revised): names are visible to intake staff; the lottery is kept blind by rules, lock, check number, dice and formula (E-3, BL-1 to BL-5). No identity table or identity admin role.
- Pre-screen buffer above the income limit, and whether the minimum-affordability check applies. (Proposed defaults: 110%; yes.)
- Can a valid certification be reused for another project by re-running that project's checks? (Proposed default: yes, while it's unexpired.)
- How long does an HTF homeownership certification stay valid, and is homebuyer education required? (Verify with Commerce or the contract.)
- Decided (2026-11-09): first come first served is rolling by default, with a campaign (closing date) option. Weighted lotteries are allowed per project (E-15); The default is no lottery factors. Certification uses gross annual income for now; HUD Part 5 asset income is a later per-program option. Missing required documents warn at Certify but don't block it (C-8). Each resale project chooses its own list or reuse of a recent one (J-8).
- Which lottery factors would a CLT use, if any, and have they had a fair housing review?
- Decided: all documents live in SharePoint, in the Property, Household and Project libraries, and the Document table is retired (see D-1).
