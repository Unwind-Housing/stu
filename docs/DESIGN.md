# CLT Stewardship: design record

The decisions behind the data model, and the reasons for them. Update this file when a decision changes.

## Scope

**In scope:**
- Properties, households and household members
- Occupancies, which link a household to a property over time
- Annual verification
- Insurance tracking
- Homeowner requests
- Resale price calculation
- Sales
- Documents
- ERRR tracking
- Intake: screener and full application data, including household members, income, debts and assets
- Projects, organization eligibility and HUD AMI limits; funders appear as covenants on each home
- Pre-screen, selection (lottery, first come first served, ranked preferences), certification and matching
- Funder reporting, starting with the WA HTF Homebuyer Information Form

**Out of scope** (removed on purpose): subsidy accounting (draws, disbursements, allocation tracking); general waitlists (a project's ranked selection list is project-specific and ends when the project closes); the public-facing application portal (the forms platform handles that).

## Tables (v0.5)

Rows marked **v0.5** are designed but not built yet (SharePoint document management is built). See "Eligibility, selection and certification" below and docs/plans/v0.5-plan.md.

| Table | Purpose |
|---|---|
| Property | A home or lot. Has Current occupancy (kept up to date by flows), State, County, Property type and Tenure type, all from lists. The County dropdown only offers counties in the chosen State. Parcel number (schema name `apn`). SharePoint document management is on: one folder per property. |
| Household | Applicant, homeowner or past owner. Primary email is an alternate key. SharePoint document management is on: one restricted folder per household. **v0.5:** the certification fields move to Certification and are replaced by a Current certification lookup; adds optional demographics (column security). |
| Household member | A person in a household. Form item ID is an alternate key. Age and Is adult are formulas. |
| Application | One household applying to one project: screener and full application answers. Screener and full application entry IDs are alternate keys. **v0.5:** adds a Project lookup, pre-screen result, a new stage list and current housing costs; the verified rollups and Income as % of AMI move to Certification. |
| Income source, Debt, Asset | Repeating sections from the full application, each with a Review status and a Verified amount. Form item ID is an alternate key. **v0.5:** adds a Certification lookup (the rollups sum through it) and an exclusion reason. |
| Occupancy | Household at a property, with dates. **Resale formula terms live here only.** |
| Annual verification | Yearly occupancy check. **Verification code** (alternate key) is sent in the form link so replies match. |
| Insurance policy | Belongs to the occupancy only (the owner's policy). Coverage A, extended dwelling %, replacement cost (copied from the occupancy's property), coverage check. |
| Homeowner request | Capital improvement, ERRR repair draw, refinance, rental and so on. Approved credit and approved draw. |
| Sale | Workflow: 1. Property, 2. Buyer and contract, 3. Closing. Price snapshot from the seller's occupancy. **v0.5:** created by matching, in Pre-purchase status; adds purchase financing and final ratios; Loan rows are its children. |
| Document | **Retired in v0.5** (see Document storage). Files live in SharePoint under the property, household or project. |
| Fee | Monthly fee per property with effective dates (ground lease fee, ERRR, other). Drives ERRR posting. |
| ERRR transaction | Per-property ERRR ledger. |
| ERRR reconciliation | Monthly tie-out to QuickBooks. |
| List item | Staff-editable dropdown values: State (seeded with the 50 states and DC), County (all 3,143 US counties, loaded by tools/load_counties.py from the Census 2020 list), Property type, Tenure type, Relationship, Income type, Debt type, Asset type, Housing status. A County value has a State. |
| Form submission | Any form entry from any forms platform, in a standard JSON format, before processing. |
| **v0.5:** HUD AMI Limits | One county's income limits for one year, for example "Jefferson 2026": the 50% limit for household sizes 1 to 8, median family income (reference only), Source HUD or Other. |
| **v0.5:** Organization eligibility | The CLT's own eligibility rules (one record): max and min % of AMI, first-time buyer, asset limit, housing and debt ratio maximums, homebuyer education, certification validity. |
| **v0.5:** Project | A selling or rent-up campaign for one or more homes: new construction phase, single-home resale or rental lease-up. Holds screening buffers, invitation settings and its own Project Documents folder. |
| **v0.5:** Project priority | The project's household size priority tiers per bedroom size, and any preference tiers. |
| **v0.5:** Project home | A home offered in a project, with pool, target AMI, estimated price and monthly cost, and status. |
| **v0.5:** Property funding | A funder's covenant on a home: funder (staff list), contract number, target AMI, covenant start, years and end. |
| **v0.5:** Selection round | One lottery or draw for a project: pools locked (with check numbers), Board Observer, dice roll and seed, draw, certification. |
| **v0.5:** Selection entry | One line of a ranked list: one household on one bedroom-size list, with tier, lottery number, rank, status and deadlines. |
| **v0.5:** Certification | Staff's verified figures for a household, the affordability inputs, the calculated ratios and the result. |
| **v0.5:** Eligibility check | One test at pre-screen or Certify: value, limit, pass or fail. |
| **v0.5:** Loan | One loan on a sale: type, lender, amount, rate, term, amortization, deferred, monthly payment. |

## Lists and fixed choices

**Where to add a value:** a list value (state, county, property type and so on) is added by staff in the app under **Settings → Lists**. A fixed choice (any status or stage, sale type, request type and similar) is added in `schema.py` and a build run, because flows and formulas depend on it.

- **Lists** (List item table) vary by CLT or by form wording, so staff edit them in the app.
  - Each value has **Form answers** (one per line). The intake flows match a form answer to a value by checking this field, so when a form's wording changes, staff update the list, not the flow.
  - Answers that match no value go to the "(other)" text column on the record.
- **Fixed choices** are values that flows or formulas depend on: statuses, stages, resale formula, sale type, ERRR transaction type, pay frequency, request type, fee type and similar. They change only through `schema.py` and a new release. Values are prefix 76827 plus an index, and they stay stable across tenants.

## Record names and numbers (v0.5)

**Record numbers:** an autonumber column, Record number, on the main records: Property P-00001, Household H-00001, Occupancy O-00001, Application A-00001, Sale S-00001, Homeowner request R-00001. Dataverse assigns it on create. When the column is first added, the build numbers existing rows oldest first and starts the sequence after them. Shown first on each form (read-only) and in the main views.

**Start here pages** (webresources/overview.html and guides.html, HTML web resources):
- **Overview** is the first navigation item, so the app opens on it. Its tiles count records by running the app's own saved views by name ("Open requests", "Verifications to do" and so on), so a count always matches the list behind it, and a tile whose view doesn't exist is hidden. Counts run as the signed-in user.
- **How-to guides**: step-by-step instructions for the main jobs. Steps that flows will automate later say so.
- Both read the client's name and colors from the environment variables and show the logo uploaded by apply_branding.py.
- **Form tips** (webresources/tips.js): on Property and Household, a hint on new records and a reminder until the record has a SharePoint document location.

**Names** (webresources/names.js, a small form script):
- Property: street address, plus ", Unit X" when there's a unit. Updates as the address is typed, and on save.
- Household: the primary applicant's last name, set when that member is saved (or when the household is opened with no name). If another household already has that name: "Rivera, Maria", then "Rivera, Maria 2" and so on.
- Occupancy: household last name (the household name up to any comma), " - ", then the property's name.
- The Name field sits below the fields it's built from and is read-only. It isn't required on these three tables, so a household can be saved before it has members.
- Records created by flows (intake, sale closing) must set names with the same rules, because form scripts only run on forms.

## Client settings and branding (v0.5)

- **Environment variables** hold per-client settings. `schema.py` `ENVIRONMENT_VARIABLES` defines them; `build_schema.py` creates the definitions in the solution with blank defaults. Each environment holds its own values, which never go in the solution.
- **Client file** `clients/<client>/client.json`: the client's settings, environment URLs and SharePoint site. Start from `clients/example/client.json`; a CLT's own file is kept out of the public repo.
- **`tools/apply_branding.py`** writes the client file's settings into the environment variables, builds a modern theme (`clt_brandtheme`: header colors, a base palette from the accent color for buttons and links, and the logo, downloaded from the logo URL into `clt_brandlogo`), and sets the app's "Custom theme definition" setting to it. The theme only shows in the new look, and its attribute names must be lower camelCase (`background`, not `Background`); capitalized names are silently ignored. If a change seems stuck in the browser cache, bump the theme name. All without the solution header, so one client's branding never ships to another.
- Settings so far: CLT name, header color, header text color, accent color (hover and selected), logo URL.
- Model-driven apps can't change fonts, and the modern header shows the app name, not a logo. The logo URL is for the home page.
- Example: header #344734 (dark green), text #FFFFFF, accent #526B50 (sage), from its website palette.

## Removed in v0.5

- **Development table:** projects (v0.5) group the homes offered together; there's no separate development or neighborhood record. If a neighborhood label is ever needed for reporting, a plain text column on Property is enough.
- **Insurance policy's Property link:** a policy belongs to the owner's occupancy; the property is reached through it.
- **Document table:** replaced by SharePoint libraries.
- **State as free text** on Property and Household: now a lookup to the State list.

## Resale formulas (on Occupancy)

**Fixed annual rate:**
- Base price × (1 + rate)^(days ÷ 365), with an optional "whole years only" setting.
- Some CLTs use 1.5% compounding, rounded to $100.
- Test case: base price $185,000, base date 2015-06-01, end date 2026-11-03 gives **$219,300**.

**Appraisal share:**
- Base price + (latest appraisal − appraisal at purchase) × (base price ÷ appraisal at purchase) × owner share %.
- Example: 200,000 / 300,000 / 25% / 400,000 gives $216,666.67.

**Options:** floor at purchase price, price cap, round to nearest $X.

**Maximum resale price** = formula price + improvement credits. Improvement credits are the approved credits from Capital improvement requests, summed by a flow.

The formula columns are built by `build_schema.py` from `schema.py` (since 2026-11-10). Formula price reads Raw formula price (one formula column reading another, the "chaining test"); if Dataverse refuses that, the build reports it and the two get merged into one formula. The price is valued at the occupancy's end date, or today while it's current.

## ERRR (external repair and replacement reserve)

- The fund **stays with the house.** The balance belongs to the Property only, not to the occupancy or the sale.
- **Balance** = ERRR increases (rollup) − ERRR decreases (rollup), with the rollups filtered by transaction type. Rollups can't sum formula columns, which is why there are two.
- **Transaction types and signs:**
  - Increase: Opening balance, Contribution, Adjustment increase
  - Decrease: Returned contribution, Repair draw, Adjustment decrease
- **Contributions:** a CLT may collect one monthly ACH draw per owner covering all fees, including ERRR. The ERRR amount can differ by home and can change, so it's stored on the Fee table with effective dates.
  - Flow S-7 posts each property's ERRR contribution monthly on the ACH draw day (environment variable), as an upsert keyed on Posting key = property + YYYY-MM + ERRR.
  - A failed ACH draw is recorded as a manual Returned contribution.
- **Interest** accrues but **is not allocated** to homes. The reconciliation checks: QBO ERRR balance − unallocated interest to date − sum of property balances = 0.
  - Suggest a QBO sub-account for ERRR interest.
- **Cutover:** one Opening balance transaction per property from the previous system, plus Fee rows from its fee records.

## Document storage: SharePoint (v0.5)

**Decision:** files live in SharePoint through Dataverse's built-in document management, not in Dataverse file columns and not through a custom folder flow. One site per client, three libraries. Property and Household are built; Project comes with the Project table in the v0.5 schema build.

| Library | Table | Rule: | Examples | Access |
|---|---|---|---|---|
| **Property Documents** (`clt_property`) | Property | Stays with the house | Deed, survey, appraisals, inspections, warranties, repair invoices, recorded ground leases (each owner's lease stays in the property's history) | Staff; board read-only |
| **Household Documents** (`clt_household`) | Household | Goes with the people | Eligibility documents, certifications, closing disclosure and loan documents, annual verification uploads, correspondence | Staff and intake reviewers only |
| **Project Documents** (`clt_project`, v0.5) | Project | Belongs to a project | Lottery record (locked pool lists, conflict of interest confirmations, recording, signed certification, notices), funder contracts | Staff |

- Staff use **Related → Documents** on a property or household to upload, open, and jump to the folder in SharePoint. Occupancy and Sale have no documents of their own; their documents are filed under the property or household by the rule above.
- Each client picks a site in its own tenant (for example `https://yourorg.sharepoint.com/sites/Stewardship`). The build's `--sharepoint-site` creates the site record and a document location per library. Each library's web address is the table's logical name, which is where Dataverse looks for that table's folders; its title comes from `schema.py`.
- The build tries to create the libraries in SharePoint, but the sample sign-in app it uses isn't allowed to call SharePoint (401), so for now the libraries are created by hand, once per client. Our own app registration (Deployment step) should remove that step.
- **Permissions** are set per library in SharePoint, separately from Dataverse security roles. Household Documents breaks inheritance and is limited to staff.
- **Applicant documents** stay in the forms platform until the household is certified. The Certify flow (C-flow-1, through D-flow-1) copies its uploads into its Household Documents folder, creating the folder and its document location if nobody has opened the household's Documents tab yet. Uploads from households that are never certified are purged on a schedule.
- **Document type and date** become SharePoint library columns (staff maintain the type choices in SharePoint), with SharePoint views to group by type across folders.
- **The Document table is retired** in v0.5, with its File column, form, views and navigation.
- **Why:**
  - No extra flow and no premium license for the basic setup.
  - SharePoint storage is cheaper and larger than Dataverse file capacity.
  - Staff can use the files in SharePoint, Teams or OneDrive sync outside the app.
  - Library-level permissions match the sensitivity split.
- **Tradeoffs we accepted:**
  - A record's folder is created when someone first opens its Documents tab, not when the record is created.
  - Folder names include the record ID (`123 Main St_8F2A...`).
  - Document types are maintained in SharePoint, not in the app's Lists.

## Sale workflow

From v0.5 a sale starts when a certified household is matched to a home in a project (flow M-flow-1), instead of staff picking the property by hand.

1. Matching creates the Sale in **Pre-purchase** status for the household and the project home.
2. A flow sets Sale type: **Resale** if Property.Current occupancy is set, otherwise **Initial sale**. For a resale it also sets the seller's occupancy and snapshots the formula price, credits and maximum price.
3. Staff record the contract (**Under contract**), the purchase financing and the Loan rows.
4. At closing (**Closed**), flow S-5:
   - Ends the seller's occupancy.
   - Creates the buyer's occupancy, copying the formula terms on a resale, with base price = purchase price and base date = closing date.
   - Updates Current occupancy, the statuses, the project home (Sold) and the application (Purchased).
   - The final housing and debt ratios are calculated from the actual loans (C-6).

## Two apps, one environment (decided 2026-11-09)

| | CLT Stewardship | CLT Intake & Selection |
|---|---|---|
| Solution | `CLTStewardship` (core, every client) | `CLTIntake` (optional, depends on the core) |
| Who | Staff, finance, board | Intake reviewers, certifiers |
| Holds | Properties, households, occupancies, verifications, insurance, requests, sales, ERRR, fees, property funding (covenants) | Projects and their homes, priorities and eligibility overrides, organization eligibility, HUD AMI limits, screeners, applications, income, debt and asset lines, selection rounds and entries, certifications, eligibility checks, applicant identities |
| People appear as | Names | Names on screeners and applications; Unique IDs on the lottery documents the Board Observer signs |

**Why one environment:** no sync to build or break; the handoff is a flow inside the same database. Licensing: a Power Apps per-app pass covers one app, so staff who use both apps need two passes (check the current rule before go-live).

**Why a separate solution:** a CLT that runs selection elsewhere installs only the core and brings winners in through the handoff contract.

**Handoff (H-1), at "Purchase and sale agreement signed":** flow creates or updates Household and members (matching by email, then name), copies the certified household size, income, AMI % and certification dates onto the Household, creates the Occupancy (Pending) for the matched property, creates the Sale (Under contract), and copies the certified documents into the Household Documents folder. The intake records keep a lookup to the new Household. This changes the v0.5 plan: Household keeps its certification fields (filled at handoff) instead of a Current certification lookup, and documents move at handoff instead of at Certify.

## Eligibility, selection and certification (designed for v0.5)

Designed 2026-11-08. Not built yet: the build plan is docs/plans/v0.5-plan.md. Requirements: FUNCTIONAL-SPEC sections "Projects and funding", "Eligibility and selection", "Certification", "Matching and purchase" and "Funder reporting".

### Pipeline

Apply (screener for a project) > Application period closes, Unique IDs assigned > Pre-screen > Pools by bedroom size, priority tiers > Pools locked (check numbers) > Draw (lottery or first come first served) > Result certified > Invite to full application > Certification > Offer and match to a home (Sale: Pre-purchase) > Under contract > Closed (occupancy current, household Homeowner).

### Income limits (simplified 2026-11-10)

**HUD AMI Limits:** one record per county per year. Name (for example "Jefferson 2026"), county, year, source (HUD or Other), source details, effective date, median family income (reference only: HUD's "family" isn't our household), the 50% (very low income) limit for household sizes 1 to 8, notes.

Calculation:
- 100% AMI = 2 x the 50% limit for the household size. Any other X% = 100% AMI x X.
- Over 8 people, HUD's rule: the 4-person 50% limit x (1.32 + 0.08 per person over 8). Not stored.
- Only records with Source = HUD define AMI; the newest year for the county is used.
- **Stated income (% of AMI)** on each application is a formula column (whole number): stated income x 50 / **50% limit for household size**, itself a formula reading the limit for adults plus children from the application's **AMI limits used** record, HUD's rule over 8 (`schema.py` LIMIT50_FOR_SIZE and AMI_PCT; two columns because Dataverse caps a formula at 1,000 characters). It recalculates whenever the income, household size or limits change. The screener intake flow sets AMI limits used to the county's newest HUD record (a formula can't search for it); `tools/recalc_ami.py` re-points every screener after a new year's limits are loaded. Staff can change the link by hand.
- Certified households keep "Certified income (% of AMI)" on the Household, filled at handoff.
- Staff enter the limits once a year (or send Claude HUD's summary for each county). Later option: HUD USER's Income Limits API.

### Eligibility rules (simplified 2026-11-10)

Two layers, to keep simple deployments simple:
- **Organization eligibility** (one record, Settings): max income (% of AMI), min income (% of AMI, blank means none), first-time buyer (Required or Not required), lives or works locally (Required or Not required) and the local area, asset limit (blank means none), housing ratio max %, total debt ratio max %, homebuyer education (Required or Not required), certification valid for (days), notes. One CLT's settings, as an example (2026-11-10): 120% AMI max, housing (front-end) ratio 35%, total debt (back-end) ratio 44%, first-time buyer required, lives or works in Jefferson or Clallam County for at least 1 year. New environments start with 80% AMI, housing 38%, debt 45%, first-time buyer required, for the CLT to change.
- **Project** has the same fields. A blank project field uses the organization's rule. Funder requirements go in the project's notes.

**Organization eligibility on each application** (2026-11-11, formula columns): the flow links **Eligibility rules used** to the organization's record, and four formulas read through it: Eligibility: rules not met (over or under the AMI range, not a first-time buyer, no local tie, assets over the limit), Eligibility: missing answers, **Organization eligibility** (Eligible / Not eligible: ... / Needs review: ...) and **Is eligible** (yes or no). Choices and money on the rules are read through helper formulas on the rules record (First-time buyer is required, Local tie is required, Asset limit in whole dollars), because a formula can't compare a choice or calculate with money on a linked table. Housing ratios aren't checked here: they need a home's monthly cost (Project home: estimated monthly housing cost), so they belong to the pre-screen. The household's applications, with these figures, show on the Household form.

**Screener answers are read-only** on the Application form, and the Application table has auditing on (with environment auditing): Related > Audit history shows every change, including the flow bringing in an applicant's edit.

Removed on 2026-11-10: Funding program, Project funding, Document requirement and the per-household-size Income limit rows. Funders stay only as covenants on each home (Property funding).

### Projects and homes

**Project:** name, type (New construction sale, Resale, Rental lease-up), status (Planning, Accepting applications, Selection, Certifying, Matching, Closed), application opens and closes, selection method (Lottery, First come first served, Ranked preferences), notes, and these settings:
- Eligibility overrides (see Eligibility rules): blank uses the organization's.
- Screening buffers: income buffer % above the limit (default 110), debt ratio buffer (percentage points above the debt ratio max), minimum credit range, bankruptcy look-back (years), apply minimum-affordability check (default yes). Recorded before screening starts, as a lottery procedure usually requires.
- Invitations: invites per list (default 10), minimum invites per home (default 2x), response deadline in days (default 15).
- Waitlist: months the ranked lists stay in effect after the draw (default 12).
- SharePoint document management is on: **Project Documents** library, one folder per project, for the lottery record and funder contracts.

**Project priority** (projects set their own priorities): project, bedroom size, household size, tier, preference (optional text, for preference tiers such as local residency), notes. One row per bedroom size and household size that's eligible; household sizes with no row aren't eligible for that bedroom size. For example, from one CLT's homebuyer manual: 1 BR: 2 persons tier 1, 1 person tier 2; 2 BR: 4, 3, 2, 1 persons in tiers 1 to 4; 3 BR: 6, 5, 4, 3 persons in tiers 1 to 4. A "Copy priorities from another project" button saves retyping.

**Project home:** project, property, pool name (optional), target AMI %, estimated price, estimated monthly housing cost (used for the minimum-affordability pre-screen), status (Available, Matched, Sold).

**Property funding:** property, funder (staff list: Settings > Lists > Funder), contract number, target AMI %, covenant start, covenant years, covenant end, notes (the funder's requirements and reporting).

### Blind lottery (revised 2026-11-09)

Names are visible on screeners and applications. "Blind" means nobody can affect who wins because of who they are, enforced by the process rather than by hiding names (which leak anyway):
- **Rules decide eligibility.** The pre-screen tests every screener against the project's written rules. Overrides record who, when and why, and close when the pools lock.
- **The clock decides the order.** Unique IDs (ID-0001...) are assigned automatically in submission order when the window closes (or on arrival for a rolling first come first served list). Nobody types or edits them.
- **Screener answers freeze** when Unique IDs are assigned; later edits are flagged on the form submission for staff. Rolling first come first served uses the first submission time.
- **Locked means locked.** At Pools locked, a flow assigns the round's entries to a **Locked selections** team that only the Lottery Administrator role can write to, and only through the Draw and status actions; others get read access. (Form rules alone would only lock the form.) Auditing is on for Selection round and Selection entry.
- **Check number.** At the lock the flow computes, per list, `MOD(SUM(row x (UniqueIDnumber x 100 + tier x 10 + chances)), 999983)` over the list sorted by Unique ID, with row = 1, 2, 3... It's printed on the pool list the Board Observer initials and recomputed by the verifier workbook. It is a transparent checksum, not cryptography: its job is to make any later change visible. (Power Automate has no hash function.)
- **Dice decide luck** (ten d10 rolls, see the draw), and the **formula decides rank**: tier, then lottery number or weighted key. No manual rank edits (E-14).
- **The Board Observer sees Unique IDs only.** Pool lists, results and the certification show Unique ID, bedroom size, tier, chances, lottery number and rank, no names.
- **Notices** to screened-out and unselected applicants are sent by a flow and logged (Notice log: application, template, sent on, sent to, channel).


### Selection

**Methods.** Every method ranks each list by **priority tier first** (from the project's priorities: household size for the bedroom size, then preference tiers), then by a tiebreaker:
- **Lottery:** lottery number from the seeded draw below.
- **First come first served:** submission time (earliest first). No seed. **Rolling** by default (entries are created and ranked as screeners pass the pre-screen, with no lock or draw); or a **campaign** with an application window (pools locked at the closing date, then ranked).
- **Weighted lottery:** a lottery where some households get extra chances (below).

**Weighted lottery (E-15).** The project lists **lottery factors** (Project lottery factor: project, name, extra chances, how it's decided: a screener answer or staff verified, basis, fair housing review date, notes). Each entry records which factors it met (Entry factor rows) and its total **chances** w = 1 + extra chances.
- The draw is unchanged: every household gets its lottery number u from the seed, in Unique ID order.
- Ranking key = u^(1/w), largest first, within each tier. With w = 1 the key is just u, so an unweighted lottery ranks exactly as before.
- Why this formula: u^(1/w) behaves exactly like putting w tickets in the hat and keeping the household's best ticket (statistically, the best of w draws has that distribution). It works for whole or fractional chances, and anyone can check it in Excel: =U^(1/W). Chance of ranking ahead of another household = w / (w + w_other).
- Factors are fixed when the pools lock. At certification, a factor that isn't verified sets w back down, and the key is recalculated from the same u. No re-draw; the change is recorded on the entry (status reason) and in the audit log, and the original rank stays visible.
- The verifier workbook gets a Chances column and the key formula.
New methods later only need a new tiebreaker; pools, priorities, invites, offers and the handoff stay the same.

**No manual re-ordering (E-14).** After the ranking, positions change only through entry statuses (Ineligible, Declined, Unresponsive, Removed, Withdrawn), each with a reason and date. The original rank always stays visible. A certified draw is never re-run.

**Selection round** (one lottery or draw for a project): project, method, status (Open, Pools locked, Drawn, Certified, Closed), pools locked on, Board Observer (name, as text, because trustees may not be app users), dice roll, seed, check numbers, drawn on, drawn by, result certified on, lists end on (draw date + the project's waitlist months), notes. From Pools locked onward the round and its entries are read-only (Locked selections team, see Blind lottery).

**Selection entry** (one line of a ranked list: one household on one bedroom-size list): selection round, application, Unique ID, bedroom size, household size, priority tier, lottery number (lottery) or submitted on (first come first served), chances, ranking key, rank, status, status reason, invited on, response due, status date, notes.
- Statuses, from the procedure's ranked list: Waitlist, Invited, Application received, Approved, Offered, Accepted, Declined, Unresponsive, Ineligible, Removed (accepted a home on another list).
- A household on several lists has one entry per list, all with the same lottery number.

**The draw (transparent formula):**
1. Pools locked: the flow builds the entries from screened applications and the project's priorities; the Board Observer reviews and initials the pool lists (exported by Unique ID).
2. At the draw, on the recording, the Board Observer rolls a 10-sided die ten times (decided 2026-11-09) and reads the digits in order as a 10-digit **roll** (leading zeros allowed, for example 0384719265). Nobody knows it in advance, and the pools are already locked. Staff enter the roll exactly as read; the app keeps it.
   - **Seed** = MOD(roll, 2147483646) + 1, so every roll gives a valid seed from 1 to 2,147,483,646 and never 0.
3. Staff click Draw. Starting from the seed, the app computes `s = MOD(previous s x 16807, 2147483647)` (the published Park-Miller "minimal standard" generator), **throws away the first 10 values** (warm-up), then takes households in Unique ID order: each gets the next s, and lottery number = s / 2147483647.
   - **Why the warm-up:** with a small seed, the first value is just seed x 16807 with no wrap-around, so the first household would get a near-zero number and almost always rank last (seed 36 gives 0.0003). From the third value on, every seed is well mixed (seed 1: 0.0000078, 0.13, 0.76); 10 is a safety margin. Found in a 2026-11-09 review of another lottery tool.
4. Each list is ranked by tier (1 first), then lottery number (largest first), as in the procedure.
5. Anyone can check it: type the roll into the verifier workbook (docs/reference/lottery-verifier.xlsx, to be built). It computes the seed, shows the 10 warm-up rows, then one row per household in Unique ID order, and the numbers and ranks match exactly. For a weighted lottery it adds the chances and the key, lottery number ^ (1 / chances).
6. The Observer and the Lottery Administrator sign the certification; staff upload it, the recording and the pool lists to the project's folder and mark the round Certified.

**After the draw:** invite the top N per list with deadlines; replace households that miss the deadline, stop responding or are ineligible; offer homes to approved households in rank order; when a household accepts, its entries on other lists become Removed. The lists end when every home closes or on "lists end on", whichever is first.

### Certification

**Certification:**
- Links: household, application, project.
- Status: Reviewing, Waiting for more information, Certified, Not certified, Expired.
- The four certified figures: household size, annual income, assets, monthly debt.
- Certified by, certified on, expires on, not-certified reason, and the HUD AMI Limits record and year used.
- Affordability inputs: estimated purchase price, loan amount, rate, term, and estimated monthly taxes, insurance, mortgage insurance, association dues, land lease fee and utilities.
- Calculated: monthly housing payment, housing ratio, total debt ratio, income as % of AMI, AMI band.
- The verified income, assets and debt totals move here from Application, as rollups that show a running total while staff review. Income, debt and asset lines get a Certification lookup. Flows never rely on the rollups: Certify adds up the lines itself.
- Locking: when Certified, the certification and its line items are read-only. A Re-certify action returns it to Reviewing. See the v0.5 plan for how locking is enforced (form rules alone only lock the form, not the data).
- The household's certification fields are replaced by a **Current certification** lookup on Household, set at Certify.

**Eligibility check** (used at both stages, so every decision shows its working): stage (Pre-screen or Certification), application (pre-screen) or certification, test (Income limit, Minimum income, First-time buyer, Housing ratio, Total debt ratio, Asset limit, Credit, Bankruptcy, Household size fits, Homebuyer education, Primary residence), value, limit (including any buffer), result (Pass, Fail, Not applicable, Needs review), notes.

### Purchase financing

**Loan** (child of Sale): type (First mortgage, Second mortgage, Third mortgage, Funder assistance, Other down payment assistance), lender, amount, rate, term (years), amortization (years), payment deferred until sale or refinance, repayment required, monthly payment (standard payment formula; 0 if deferred).

### Changes to existing tables

- **Application:** add a project lookup, the Unique ID, a pre-screen result (Eligible for selection, Not eligible, Needs review) and pre-screen notes.
  - Replace the stage choice with: Screener submitted, Pre-screened, In selection, Invited to full application, Full application submitted, In certification, Certified, Matched, Purchased, Not selected, Not eligible, Withdrawn.
  - Add current housing costs: housing situation (Renting; Own a home with a mortgage; Own a home with no mortgage; Living with family or friends; No stable housing; Other, plus an "other" text column), monthly rent or mortgage, utilities included (multi-select: Electricity; Heat; Water and sewer; Garbage; Internet; None), monthly utilities, monthly property taxes, monthly homeowners insurance, monthly HOA dues, monthly lot or space rent.
  - Add calculated columns: current total monthly housing cost, and current housing cost as % of stated income.
  - Remove "100% AMI for household size" (replaced by the income limit table).
- **Household:** add demographics, all under column security.
  - Hispanic or Latino (Yes, No, Prefer not to say).
  - Race, multi-select fixed choice: American Indian or Alaska Native; Asian; Black or African American; Native Hawaiian; Pacific Islander; White; Other; Prefer not to say. Plus a race (other) text column.
  - Special needs, multi-select fixed choice matching the HTF list: None; Chronic Mental Illness; Developmental Disabilities; Domestic Violence; Elderly; Farmworker; HIV/AIDS; Households/Families with Children; Multiple Special Needs; Physical Disabilities; Substance Abuse; Veteran; Young Adult 18-24; Other Special Need(s). Plus a special needs (other) text column.
  - HTF ethnic origin (derived): Hispanic or Latino if Hispanic is Yes; otherwise the single race checked; Multi-ethnic if more than one race; Unspecified if skipped.
  - Derived from member dates of birth: Elderly (62+), Households/Families with Children, Young Adult 18-24. Show Multiple Special Needs when more than one applies.
  - Replace the certification fields with a Current certification lookup.
- **Sale:** add status Pre-purchase (statuses: Pre-purchase, Under contract, Closed, Cancelled), plus purchase price including closing costs, rehab cost, rehab included in price, buyer cash, sweat equity, other assistance, and monthly taxes, insurance, mortgage insurance, association dues and utilities. The land lease fee comes from the property's current Ground lease fee row. Calculated: total monthly housing payment, total monthly household debt, and both ratios (final).
- **Document:** retired. Files live in the SharePoint Property and Household libraries, with document type and date as SharePoint columns.

### Documents at certification

- Three SharePoint libraries (see Document storage): Property Documents and Household Documents, already built, and Project Documents for the lottery record and funder contracts.
- Applicant uploads stay in the forms platform until the household is certified.
- At Certify, flow D-flow-1 copies the household's uploads into its folder in the Household Documents library (creating the folder and its Dataverse document location if nobody has opened the household's Documents tab yet), with document type and date set.
- Uploads from households that are never certified stay in the forms platform. D-flow-2 lists the ones past the retention period so staff can purge them.

### HTF Homebuyer Information Form (FR-1)

From the state Housing Trust Fund homebuyer information workbook (not included in this repo):
- One form per homebuyer, with project info (HTF contract number, project name) and the contractor's contact info.
- Homebuyer: name(s), first-time buyer (Yes, No, N/A), address, city, zip, county, household size (1 to 10), special needs (one value), ethnic origin (one value), bedrooms, construction type (Stick Built, Manufactured, Modular/Factory-Built), housing type (Single Family Home, Condominium, Co-Op, Duplex, Townhouse), building status (New Construction, Pre-Owned), year built, gross annual household income.
- Qualification: anticipated or final closing date; contract targeted AMI (25, 30, 35, 40, 45, 50, 55, 60, 65, 80 or 100%); maximum income for the targeted AMI; purchase price including closing costs; rehab cost; homebuyer sources; HTF assistance (repayment required, rate, term, amortization, deferred); up to 3 mortgages.
- Benchmarks: total housing payment no more than 38% of gross monthly income; total household debt (housing + utilities + other debt) no more than 45%.
- Signed by the person completing it, with title and date.

## Intake: forms-platform agnostic

- **Per-platform adapter flow** (small, one per form): triggered by Cognito, Jotform or FormAssembly. It converts the entry to the **standard JSON format** and creates a Form submission (provider, form type, entry ID, payload).
- **Processing flows** (platform-neutral): read the Form submission and upsert Household, Members, Application, Income, Debts and Assets using the alternate keys.
  - They set Status to Processed or Needs attention, with problem details.
  - They never overwrite staff review columns.
- **Annual verification:**
  - Flow S-1 creates verifications 60 days before the anniversary, each with a unique code.
  - It emails a link built from an environment variable template, for example `https://www.cognitoforms.com/YourOrg/AnnualVerification?VerificationCode={code}`. URL prefill works on all three platforms.
  - The adapter and processing flows match the reply by code.
- The standard JSON format is **not yet defined** (step 7).
- **Screener intake (built 2026-11-09, `flows_intake.py`):**
  - The screener is **generic**: not tied to a project. Applications arrive with no project; staff add them to a project with bulk edit (view "Not in a project yet": tick rows, Edit, pick the Project). One application belongs to one project; a household interested in a later project fills in the screener again.
  - Adapter: the forms platform **posts the entry as JSON** to the flow's HTTP trigger (Cognito: Submission Settings, Post JSON Data to a Website, on Submit and on Update). This works the same for Cognito, Jotform and FormAssembly and avoids the Cognito connector's 1,024-field designer limit. The URL is a secret.
  - Adapter and processing are one flow for now: it keeps the raw entry as a Form submission (Received, then Processed or Needs attention with the error), then upserts Household (by primary email), the primary and co-applicant members (by household and role or name) and the Application (by screener entry ID).
  - New households are named "Last", then "Last, First", then "Last, First (6-12)" if both are taken.
  - After Unique IDs are assigned (answers frozen), a changed entry isn't applied: its Form submission is marked Needs attention with the reason. (A note on the application was the first idea, but the Dataverse connector won't save a flow that links a note to a custom table.) Every processed submission is linked to its household and application.
  - County, housing status and mailing state are matched to List values by name or form answers (counties within the address's state).
  - **Source form** (added 2026-11-10): one row per online form (forms platform + the platform's form ID, name, form type). The flow adds the row the first time a form sends an entry and links each Form submission and Application to it, so staff can filter applications by the form they came from (for example a spring screener versus a project-specific one) when building a project.
    - A Source form can name a project ("Add new applications to project"). New applications from that form go straight into the project; updates never move an application. A rolling or general form leaves it blank.
    - New forms need no rebuild: copy the screener in Cognito (field names stay the same) and paste the same flow URL. Reworded or new questions need a flow check.
  - **Add to a project page** (`webresources/assign.html`, Projects > Add to a project, added 2026-11-10): pick a project, filter screeners (not in a project / all / in another project, source form, county, home size wanted, household size, income, submission dates, first-time buyer), then add the ticked rows or everyone shown. Applications with a Unique ID are locked to their project. Bulk edit in a view still works for a few at a time.
  - **Start here** has two pages (2026-11-11): **Hub** (intake.html: Applications tiles, Applicant pool, Projects taking applications, Needs attention) and **How it works** (intake-guide.html: the steps from screener to handoff). **Projects taking applications**: one card per project with status Accepting applications or an open application window: the window (time bar, days left, or rolling), applications, eligible (Is eligible) and average % of AMI, applications per week for the last 8 weeks, home sizes wanted against homes offered (Project homes by bedrooms), and Add applicants (opens Add to a project with the project picked).
  - **Start here figures** (intake.html): tiles for Screeners, Full applications in progress (invited or incomplete), Full applications submitted (full application submitted date set), Open projects; Applicant pool cards for all screeners, not in a project yet, or one project: count, average household size, median and average income, average % of AMI and income bands, first-time buyers, home sizes wanted, counties, pre-approval and homebuyer education. % of AMI is each application's Stated income (% of AMI) (see Income limits). These are stated screener answers, not verified figures.

### The first installation's Cognito forms

- **Form 3, "Homebuyer Application Form" (the screener).** Statuses: Incomplete, Submitted for Review, Invited to Full Application. The form's schema is kept with the CLT's private files.
- **Form 2, the full application.**
  - Sections: PrimaryApplicant, HouseholdMembers, Income.IncomeSources[], Debts.Debts1[], AssetsAndAccounts.AccountsAndAssets[], Residency, LenderPreApprovalAndHomebuyerEducation, FirstTimeHomebuyerVerificationStatement, Signature.
  - Entry.Action options: Submit Eligibility Documents, Start Review, Request More Documents, Submit Follow-Up, Mark Approved, Notify Lender.
  - The form's schema is kept with the CLT's private files. Re-pull it before building flows, because field names change when questions are reworded.
  - Known rename: the page 8 ownership question is now `FirstTimeHomebuyerVerificationStatement.DoesThePrimaryApplicantOrCoapplicantCurrentlyOwnAnyHomeOrResidentialProperty`.
  - New fields: Debts.PleaseExplainTheLatePaymentsOrDelinquencies and Debts.PleaseExplainTheBankruptcyFiling.
- **"Other" fill-ins:**
  - Full application: TypeOfDebt, TypeOfEmploymentOrIncome, asset Type, Relationship1, RelationshipToPrimaryApplicant, CurrentCountyOfResidence.
  - Screener: WhatCountyDoYouResideWithin, CurrentHousingStatus, and the adults and children counts. The counts go to whole-number columns, with "Household counts as entered" as the fallback.
- **Full application changes for v0.5** (sent to the form builder; **pending internal names**, so update this list once the fields exist):
  - New optional "Household demographics" section: Hispanic or Latino; race (checkboxes, with Other text); special needs (checkboxes, with Other text, "None of these" and "Prefer not to say"); dates of birth for every household member.
  - New "Current housing costs" questions in the Residency section: housing situation; monthly rent or mortgage; utilities included; monthly utilities; owner costs.
  - The screener stays generic (no project choice; decided 2026-11-09). The full application needs hidden fields for the project and Unique ID, prefilled by the invite link (E-flow-4).
- **Cognito connector:**
  - Standard tier; needs the Cognito Pro plan.
  - The flow designer only shows 1,024 fields, so use Get entry plus Parse JSON.
  - Every repeating item has its own ID. Build the item key as `<formId>-<entryNumber>-<itemId>`.

## Flows to build (Power Automate, inside the solution)

**Stewardship:**
- S-1: Annual verifications (daily)
- S-2: Replacement cost sync to insurance policies
- S-3: Improvement credits sum
- S-4: Sale setup and snapshot (from v0.5, runs when M-flow-1 creates the sale)
- S-5: Sale closing
- S-6: Request approvals (optional)
- S-7: Monthly ERRR posting
- S-8: Reconciliation sum
- Also: keep Property.Current occupancy current

**Intake:**
- I-0: Adapters, one per form per platform
- I-1: Screener processing
- I-2: Invite to full application (**superseded in v0.5 by E-flow-4**)
- I-3: Full application processing
- I-4: Updates and follow-ups
- I-5: Approval (**superseded in v0.5 by C-flow-1 Certify**)

**Eligibility, selection and certification (v0.5):**
- E-flow-0 Assign Unique IDs: when a project's application period closes (or on a button), number its applications in submission order.
- E-flow-1 Pre-screen: when a screener is processed (and again on a button after the period closes), run the project's tests with buffers, write an Eligibility check per test, then set the pre-screen result and notes.
- E-flow-2 Build and lock pools: create one Selection entry per screened household per eligible bedroom size, with the tier from the project's priorities; lock the round.
- E-flow-3 Draw: from the seed, compute each household's lottery number in Unique ID order (Park-Miller), copy it to all its entries, and rank each list by tier then lottery number.
- E-flow-4 Invite: invite the next households on a list, up to the project's settings, with response deadlines. Email a full application link prefilled with the application's Unique ID, and set the stage.
- E-flow-5 Deadlines: daily, flag invitations past their deadline for staff to mark Unresponsive and replace.
- C-flow-1 Certify: check that the actor is a certifier, add up the lines, run all checks, refuse if any fail, otherwise lock, stamp, set the expiry, update the household's current certification and its list entries (Approved), and start the document transfer.
- C-flow-2 Expire: daily, mark expired certifications as Expired.
- D-flow-1 Transfer documents: copy the forms platform's uploads for the household into SharePoint (through the platform adapter) and set their document type and date.
- D-flow-2 Purge reminder: on a schedule, list uncertified households whose uploads are past the retention period.
- J-flow-1 Inherit funding: copy funding from project to property (new construction), or from property to project (resale).
- M-flow-1 Offer and match: check the offer order (no higher-ranked household on the list still within its deadline), create a Sale in Pre-purchase for the household and home, set the project home and application to Matched, and mark the household's other list entries Removed when it accepts.

**Licensing open question:** the Dataverse connector is premium. Per app licenses don't let a user own premium flows outside the app's context. Plan: associate the flows with the app and test this early. If it doesn't work, buy Power Apps Premium (Nonprofit Staff Pricing, $5/month) for the flow owner.

## Deployment model (multi-client)

- **One repo, one Dev environment.** Pull requests deploy to Dev.
- **A release exports the managed solution;** each client's production environment gets that managed import.
- **Per client:** a service account (app registration plus application user) in their tenant, a GitHub Environment with secrets, a client config file (form IDs, approver email, ACH draw day, SharePoint site), and seed data for their lists, funding programs and income limits (income limits entered yearly). Solutions don't carry data, so the SharePoint site record and document locations are created per environment by `build_schema.py --sharepoint-site`.
- **Environment variables:** branding and the CLT name exist (see Client settings and branding). Still to add: Cognito or forms settings, the verification form URL template, ACH draw day, approver email. Their defaults stay blank in the solution; values go in the client file.

## Open questions

- Should "Domestic partner" be its own relationship value? For now it's mapped to "Spouse or partner" through Form answers.
- Do any clients own and lease rental units directly?
- If a home's ERRR draw exceeds its balance, can the interest pool cover it? (Policy decision.)
- Results of the formula chaining test.
- Results of the flow licensing test.
- Which preference tiers a CLT uses besides household size, if any (default: none).
- Invites per list (default 10, at least 2x homes), pre-screen buffers (default 110% income) and the minimum-affordability check (default on).
- Declined offers (default: bottom of the list once, removed on a second decline) and offer order across bedroom sizes (default: largest first). From one CLT's draft lottery procedure, for its Board.
- Decided 2026-11-09: names visible, lottery blind by process; no manual re-ordering; missing documents warn at Certify; screener answers freeze at Unique IDs; resales choose own list or reuse; no lottery factors to start; gross income for now.
- Per-app pass rule for staff who use both apps.
- Reusing a valid certification for another project by re-running that project's checks (default: yes, while unexpired).
- HTF homeownership certification validity and whether homebuyer education is required (verify with Commerce or the contract).
- Household status values once Certification exists (for example whether "Invited to full application" and "Eligible" still belong on Household). See the v0.5 plan.
