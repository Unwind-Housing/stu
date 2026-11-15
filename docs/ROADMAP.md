# Roadmap

Stu is in active development and not yet at v1.0 (v1.0 is the first production go-live).

## Done

| Version | Date | What |
|---|---|---|
| v0.1 | 2026-11-05 | Schema build: 15 tables |
| v0.2 | 2026-11-06 | App build: navigation, forms, views |
| v0.3 | 2026-11-07 | Lists, Form submissions, sale workflow layout |
| v0.4 | 2026-11-07 | Upgrade-order fix; CI tests |
| v0.5 | in progress | SharePoint document storage, intake and selection tables, screener and full application intake flows, pre-screen, import tool, one app with two areas, form mappings per organization, public release |

## Next

1. **The middle of the selection path, in order:** close applications and assign Unique IDs, build and lock the lists, the draw, then invitations to the top households on each list. As one guided page (request 13).
2. **Project homes as a picker** (request 12).
3. **Map the remaining workflows** (resale, annual verification, requests, insurance, leaving without a sale): trigger, steps, records changed, documents and flows.
4. **Rollup columns by script** (docs/STEP4-columns.md): test whether the Web API can create them, so that hand step goes away.
5. **More environment variables:** forms settings, verification link template, ACH draw day, approver email.
6. **Stewardship flows:** annual verification, insurance renewals, homeowner requests, and keeping Current occupancy up to date.
7. **Security:** roles (Staff, Intake Reviewer, Certifier, Board / Read-only), column security on income, asset values, dates of birth and demographics. With one app, roles are what separates intake data from stewardship staff.
8. **Certification and the handoff to stewardship** at purchase and sale agreement, document transfer for certified households, funder reporting.

## Later

- Starter forms for each supported forms platform, with their mapping files, so a new CLT can copy a form instead of building one.
- Fetch income limits from HUD USER's Income Limits API instead of typing them in each year.
- Deploy by GitHub Actions, and a managed solution package for CLTs that prefer to import one.
- Business process flows for Application and Sale; a dashboard home page.

## Feature requests

The public list of things asked for or noticed while using Stu, from any organization that runs it. To ask for something, open an issue on GitHub; a maintainer adds accepted requests here. An organization can keep its own private list beside its settings (`clients/<name>/FEATURE-REQUESTS.md`) for requests that are about its own data or setup.

Status: **Asked** (logged, not decided), **Planned** (agreed, not built), **Building**, **Built** (with the version once released), **Parked** (not now, with the reason).

| # | Logged | From | Request | Why | Status |
|---|---|---|---|---|---|
| 1 | 2026-11-14 | Maintainer | Property type **Common area**, for shared parcels that are not homes. | Land only reads like a lot waiting to be built on. Any townhome or condo project has one. | Built |
| 2 | 2026-11-14 | Maintainer | Import tool: load properties, households, members, occupancies and fees from spreadsheets, with a dry run. | Every new organization has existing homes and homeowners to load. | Built: `tools/import_records.py` |
| 3 | 2026-11-13 | Maintainer | **Invite to full application** page under Projects: offers the next households by rank on each list, sets the stage and the household's status, and shows each invite link with Copy and Email buttons. | Setting the stage and building the link by hand is clunky. Invitations go out after the lottery, to the top households on each list. | Planned, after the lottery |
| 4 | 2026-11-13 | Maintainer | A way to keep test documents out of production SharePoint libraries. | Dev often shares the production site. | Built: a parent folder inside each library (`--sharepoint-folder DEV`). A separate site per environment is still an option. |
| 5 | 2026-11-14 | Maintainer | Load reserve (ERRR) and lease fee history from accounting ledgers. | Balances should match the books from the first day. | Asked |
| 6 | 2026-11-14 | Maintainer | Amount field on property funding. | Subsidy amounts per home only fit in notes today. | Asked |
| 7 | 2026-11-14 | Maintainer | Homeowner association dues and shared costs for a community. | The fee schedule can hold a monthly amount per home, nothing more. | Asked |
| 8 | 2026-11-13 | Maintainer | Flag a form submission when the household was matched by email but the last name differs. | A screener can join another household because the email matched. | Asked |
| 9 | 2026-11-14 | Maintainer | Simple-interest option on the resale formula. | Some ground leases use simple interest. Today the fixed-rate formula compounds annually, with part years counted to the sale date. | Parked (until an organization's lease needs it) |
| 10 | 2026-11-14 | Maintainer | A document folder per occupancy (ground lease, reserve requests, closing papers). The household folder keeps only application and certification documents. | Lease and home documents belong to that household's time in that home. A resale starts a fresh folder. | Built |
| 11 | 2026-11-14 | Maintainer | Application form: hide the lists that only automation fills (pre-screen checks, selection lists, notices) until their feature is built, and take the + New buttons off them. | Empty lists with a + New button invite adding rows by hand that only a flow should write. | Asked |
| 12 | 2026-11-14 | Maintainer | Project homes as a picker: tick properties already in Stu, each home takes its name and bedrooms from the property, then type the sale price. Target AMI comes from the project. | The Project home form asks staff to retype what Stu already knows. | Asked |
| 13 | 2026-11-14 | Maintainer | A guided page that walks staff through running a lottery: close applications, pre-screen, build and lock the lists, draw, results, invite. | The steps have to happen in order, in front of an observer, and can't be redone. A checklist of separate buttons is easy to get wrong. | Asked |
| 14 | 2026-11-15 | Maintainer | Guided processes with an app feel inside Stu, for work that has steps in order: lottery, sale, resale and the like. | Records and lists are fine for looking things up, but a multi-step process run from separate forms is easy to get wrong. | Asked. Pre-screen is the first; the lottery (13) is next, then sale and resale. |
| 15 | 2026-11-15 | Maintainer | One app, Stu, with two areas (Stewardship, Intake & Selection). | Staff who do both jobs needed two per app passes, and a household that buys a home had to be followed across two apps. | Built: `app_spec_stu.py` |
| 16 | 2026-11-15 | Maintainer | Form mappings per organization: which question on a form feeds which field is a file in the organization's folder, with one flow per form that has its own questions. | Every organization has its own screener and full application, and may have several screeners. | Built: `form_mapping.py`, `clients/example/forms/` |
| 17 | 2026-11-15 | Maintainer | Commercial and Agricultural property types; a Neighborhood list on Property; property figures by status on the Overview; household views by group (homeowners, former homeowners, applicants, potential purchasers). | Land trusts hold land that isn't housing, and staff think of homes by neighborhood and households by where they are in the process. | Built |
