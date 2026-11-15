# Stu: project brief for Claude

Stu is an open source stewardship system for community land trusts (CLTs). Read this first. If someone has asked you to **install Stu in their environment, read `INSTALL.md` next and follow it with them step by step.** If you are changing Stu, read `CONTRIBUTING.md`, then `docs/ROADMAP.md` for what's next and `docs/DESIGN.md` for the full design record.

- Feature requests are logged in the **Feature requests** table at the bottom of `docs/ROADMAP.md`: add a row when someone asks for something or a gap turns up, and update its status when it's picked up or done.
- `docs/FUNCTIONAL-SPEC.md` defines what the product must do. Check changes against it.
- `docs/PLAYBOOK.md` is the running guide for whoever looks after the system: yearly jobs (HUD AMI limits), adding a screener form, troubleshooting. When you work out a procedure that will come up again, add it there.
- `CLAUDE.local.md`, if it exists, holds this installation's own details (environment address, accounts, the person's preferences). It is not committed. Create it during the install.

## What this is

A lean, low-cost way for a CLT to track properties, households, the occupancies that link them, annual verifications, insurance, homeowner requests, resale prices, sales, documents and the per-home ERRR (external repair and replacement reserve), plus intake: screeners, projects, pre-screening, selection, full applications and certification. It is built on **Microsoft Power Platform: Dataverse plus one model-driven app (Stu)**, and installed by running the build scripts in this repo against a CLT's own environment.

- **Maintainer:** Unwind Housing & Advisory Services LLC. MIT licence. Each CLT owns its own environment and data.
- **Online forms** (screener, full application, annual verification) live in a forms platform, currently Cognito Forms. The design is deliberately **forms-platform agnostic** (Cognito, Jotform, FormAssembly).

## Environment

| Item | Value |
|---|---|
| Environment address | Each CLT's own, for example `https://yourorg.crm.dynamics.com`. Never assume one: ask, or read `CLAUDE.local.md`. |
| Solution | CLT Stewardship, unique name `CLTStewardship` |
| Publisher | Unwind Housing (`unwindhousing`), prefix `clt`, choice value prefix `76827`. **The same in every installation**, so a table or column means the same thing everywhere and changes can be merged back. |
| Licensing | Power Apps per app passes (nonprofits can get these donated) or Power Apps Premium. One app, so one pass per person. |
| Sign-in | Interactive browser sign-in through MSAL, as a person with the System Customizer or System Administrator role in that environment. Each script run asks once. |

## Portability rules

Stu is installed at more than one CLT, and each one should be able to pull new versions and send improvements back.

- **Nothing client-specific in core.** `schema.py`, the app specs, flows, pages and tools must work for any CLT. No organization names, tenant addresses, account names or local place names except as clearly made-up examples.
- **Each organization has one folder, `clients/<name>/`:** `client.json` (name, environment addresses, service account, SharePoint site, branding), `forms/` (its form mappings), `samples/` (sample entries from its forms) and its own notes. `clients/example/` is the template and the only folder there that is committed. An organization's own folder stays on its machine, ideally as its own private git repository.
- **Never commit client data.** Real properties, households and applicants go in `export/`, which git ignores. Tests and examples use made-up people at `example.com`.
- **A CLT that needs something different** changes it in core in a way every CLT can use (a setting, a list value, a field), and sends it back as a pull request. It doesn't keep a private edit of `schema.py`.
- **Prefer scripted steps to hand steps.** Where a step must be done by hand, write it in `INSTALL.md` or the playbook with exact menu paths.

## How the build works

- `schema.py`: tables, columns, global choices, lookups, alternate keys, seed list values, retired items.
- `build_schema.py`: creates the schema through the Dataverse Web API, inside the solution. It's idempotent: it never changes or deletes existing items, except `--remove-retired`, which deletes items listed in `RETIRED`, tables marked `documents=` in `schema.py`, which get SharePoint document management switched on (never off), formula columns, whose formulas are updated to match `schema.py`, and table and column display names, which are updated to match `schema.py` (labels only). `RETIRED` can hold columns, lookups, tables and choices. It also sets the solution version from `VERSION`.
- `--sharepoint-site <url>` on the schema build sets up per-environment SharePoint storage: the default site record, a library per `documents=` table (URL = table logical name, title from `schema.py`) and its document location. These are data, so each client environment runs it with its own site. `--sharepoint-folder DEV` adds a parent folder inside every library for an environment that shares the site with another one (for example a Dev environment that shares the production site): the folder flows then put new record folders in `clt_property/DEV/...`. The folder per environment is noted in `clients/<client>/client.json` (`sharepointFolder`).
- `app_spec.py`: navigation, views and work queues, main form layouts for the **Stewardship** side. `app_spec_intake.py`: the same for the **Intake & Selection** side.
- `app_spec_stu.py`: the one app staff use, **Stu** (`clt_Stu`). It defines nothing itself: it puts the two specs above into one app as two areas (the switcher at the bottom left of the sidebar). `build_app.py` builds Stu by default; `--app core` and `--app intake` still build one side as an app of its own, for a client that wants only that side. One app because per app passes are counted per person per app; who sees which side is down to security roles (step 8).
- **Guided processes:** anything with steps that must happen in order (lottery, sale, resale) gets a guided page inside Stu with an app feel, like Projects > Pre-screen: the page walks through the steps and the rules sit in a plain JavaScript function with Node tests. Not a separate Power App (that would cost another pass per person).
- Tables in `schema.py` carry `solution="intake"` when they belong to the intake side; untagged tables are core. Dev builds everything into the CLTStewardship solution for now; the split into two installable solutions happens at deployment.
- `build_app.py`: builds the app, its navigation, views and forms. It **overwrites** the forms and views it manages, so layout changes go in `app_spec.py`. Fields prefixed `?` are placed only if they exist (formula and rollup columns made by hand). File fields are dragged onto a form once by hand, and the script keeps them in place after that.
- `build_flows.py`: Power Automate cloud flows, defined in Python and deployed into the solution (`workflows`, category 5) with connection references. `--only "document folder"` deploys just the flows whose name contains that text and leaves the rest untouched (a full run overwrites a flow that was saved in the designer). Connections can't be scripted: the first time, someone picks them in each flow and turns it on. Flows are owned by whoever signs in, so the build signs in as `flowServiceAccount` from `clients/<client>/client.json` (or `--as`) and stops if anyone else signs in. Current flows: Property, Household and Occupancy document folders (`412 Fir St - P-00004` instead of Dataverse's `<name>_<GUID>`; the occupancy folder holds the ground lease, closing papers and ERRR requests, the household folder only application and certification documents), and the intake flows.
- **Intake flows and form mappings.** `flows_intake.py` (screener: the forms platform posts each entry to the flow's HTTP trigger; it upserts household, members and application, with no project) and `flows_full_app.py` (full application: finds the application by the form's Application Number, then email, and upserts the answers, members, income sources, debts and assets, never staff review fields). **Neither file names a question on any form.** Which question feeds which field is in the organization's mapping files, `clients/<name>/forms/*.json` (`form_mapping.py` explains the format; `python3 form_mapping.py <mapping> <sample entry>` checks one against a real entry). `screener.json` and `full-application.json` are the main forms and keep the flow names and IDs `CLT: Screener intake` and `CLT: Full application intake`; a form with different questions gets its own file (`screener-rental.json`) and the build makes it its own flow. Forms that are copies of each other share one mapping. A question a form doesn't ask is left out of the mapping and that field is left blank. `build_flows.py` picks the organization by `--url` (the folder whose `client.json` lists it) or `--client`. The full application trigger is named `manual`, the name the designer gives it, so a designer Save doesn't change the form's address. Both intake triggers set `triggerAuthenticationType: All` (Who can trigger the flow: Anyone); without it a designer Save drops the signature from the address and the form's posts are refused.
- `tests/`: offline tests against a fake Dataverse. Run them before every commit.
- `webresources/`: small form scripts (`names.js`, `tips.js`) and the Start here pages (`overview.html`, `guides.html` for the core app, `intake.html` (Hub), `intake-guide.html` (How it works) `assign.html` (Add to a project: filter screeners, add ticked or all) and `prescreen.html` (Pre-screen: tests a project's screeners against its rules and saves the result and one Eligibility check per test) for the intake app, sharing `pages.css` and `pages.js`), uploaded by `build_app.py` (`WEB_RESOURCES`, `PAGES`, `FORM_SCRIPTS` and `SCRIPT_LIBRARIES` in `app_spec.py`). The guides describe the real screens: when a form or workflow changes, update `guides.html` too. A little JavaScript for obvious conveniences is fine; keep it small.
- The pre-screen rules are one plain function in `webresources/prescreen.js`, with no Dataverse calls, so `tests/test_prescreen.py` runs them in Node on worked examples (the test is skipped with a message if Node isn't installed). Change a rule there and add an example to the test. The page (`prescreen.html`) only loads data, calls the function and saves. Monthly housing cost per home size is typed on the project.
- Form fields prefixed `!` in `app_spec.py` are read-only on the form.
- Tables marked `audit=True` in `schema.py` get auditing switched on (and auditing for the environment); see Related > Audit history on a record.
- `clients/<client>/client.json`: per-client settings (name, branding, SharePoint site). `tools/apply_branding.py` writes them into the environment variables (defined in `schema.py` `ENVIRONMENT_VARIABLES`) and themes the app header. Values and theme stay out of the solution.
- `tools/load_counties.py`: loads all 3,143 US counties into the County list, linked to their State (data, per environment; safe to re-run).
- `tools/import_records.py`: loads properties, households, members, occupancies and monthly fees from CSV files in a folder (templates and rules in `docs/templates/`). Dry run first; all rows are checked before anything is written; safe to re-run. Client data goes in `export/`, which git ignores.
- `tools/recalc_ami.py`: points every screener's AMI limits used at its county's newest HUD AMI Limits record (Stated income (% of AMI) is a formula over that link). Run it after loading a new year's limits; the intake flow links new screeners.
- Formula columns are `fx(...)` columns in `schema.py` (Power Fx with internal names; every money column wrapped in `Decimal()`, and a blank money value reads as 0, so test it as `Decimal(x) = 0`, never `IsBlank`; numbers in `Text()` need a format, `Text(x, "0")`; choices as `[@'Choice display name'].'Label'`; at most 1,000 characters, so split a long one into two columns; `--check` catches the money and length rules). The schema build creates them after the lookups and updates a changed formula in place. Rollup columns, and the two formulas over them, are still created **by hand**: see `docs/STEP4-columns.md` (schema names must match).

Commands (from the repo root, with `.venv` active):

```
python3 build_schema.py --check && python3 build_app.py --check && python3 build_app.py --check --app core && python3 build_app.py --check --app intake && python3 build_flows.py --check
python3 tests/test_offline.py && python3 tests/test_app_offline.py && python3 tests/test_counties.py && python3 tests/test_branding.py && python3 tests/test_flows.py && python3 tests/test_ami.py && python3 tests/test_import.py && python3 tests/test_prescreen.py
python3 build_schema.py --url https://yourorg.crm.dynamics.com --sharepoint-site https://yourorg.sharepoint.com/sites/Stewardship --sharepoint-folder DEV
python3 build_app.py --url https://yourorg.crm.dynamics.com
python3 build_flows.py --url https://yourorg.crm.dynamics.com
```


## Conventions

- **Versions:** `main.sub`. Bump the sub version for each change set (v0.5, v0.6). v1.0 = first production go-live. For each release:
  - Update `VERSION`, `build_schema.VERSION` and the README version table.
  - Tag the commit `v0.x`, with a GitHub release titled `v0.x (YYYY-MM-DD)`.
  - The schema build stamps the solution version as `0.x.0.0`.
- **Branches:** work on a branch based on `main` and open a pull request. No stacked pull requests.
- **Never commit** credentials, `.env`, logs, `choice-values.json`, `.venv`, a flow's HTTP address (treat it like a password), anything in `clients/` except the example, or anything in `export/`.
- **Data safety:** no SSNs or bank account numbers in Dataverse. Applicants' uploaded documents stay in the forms platform until the household is certified; only certified households' documents are copied, into the restricted Household Documents library in SharePoint. Uploads from households never certified are purged on a schedule. Column security goes on income, asset values, dates of birth and demographics (step 8).

## Working with the person in front of you

They may be a CLT staff person, not a developer. Unless `CLAUDE.local.md` says otherwise:

- Use plain language and step-by-step instructions with exact menu paths. Give terminal commands one at a time, and say briefly what each one does.
- **Before running anything that changes an environment, say what it will do,** and which environment. Try a Dev or sandbox environment before production.
- **Before any command that opens a browser sign-in, say so first:** which organization, which account, and what it's for.
- Never run `--remove-retired` without their go-ahead, because it deletes data.
- Explain tradeoffs briefly, then recommend.
