# Stu

Stu is an open source stewardship system for community land trusts (CLTs): one place to track homes, the households that apply for and live in them, and the ongoing obligations that come with permanently affordable homeownership.

It runs on **Microsoft Power Platform** (Dataverse and one model-driven app) in your own Microsoft 365 tenant. You own your environment and your data. Nonprofits can usually run it on donated Power Apps licences.

## What it does

**Stewardship**
- Properties, households and the occupancies that link them, with record numbers and document folders in SharePoint
- Resale formula and maximum resale price, sales
- Annual verifications, insurance policies, homeowner requests
- Monthly fees and the per-home repair and replacement reserve (ERRR)

**Applications and Sales**
- Online screeners and full applications arrive from your forms platform (Cognito Forms today)
- Projects with their own eligibility rules, home sizes and monthly housing costs
- Pre-screen: tests each screener against the project's rules and records every test
- Selection by lottery or first come, first served, then certification (in progress: see `docs/ROADMAP.md`)

## How it's built

Everything is defined in code and built by script, so an install is repeatable and an update is a re-run:

| File | What it holds |
|---|---|
| `schema.py` | Tables, columns, choices, lookups, starting list values. Readable as a build sheet. |
| `app_spec.py`, `app_spec_intake.py`, `app_spec_stu.py` | Navigation, views and forms for the two sides, and the one app that holds both. |
| `build_schema.py`, `build_app.py`, `build_flows.py` | The scripts that build tables, the app and the Power Automate flows in your environment. Safe to run again. |
| `form_mapping.py`, `clients/example/` | Each organization's own settings and form mappings: which question on its forms feeds which field. Copy the example folder to start. |
| `webresources/` | The Start here pages, in-app guides and guided pages such as Pre-screen. |
| `tools/` | Loading counties, branding, importing your existing records from spreadsheets, yearly AMI updates. |
| `tests/` | Offline tests against a fake Dataverse. No environment needed. |
| `docs/` | Design record, functional spec, roadmap, and the playbook for whoever looks after the system. |

## Install

See **[INSTALL.md](INSTALL.md)**. It is written to be followed with [Claude Code](https://claude.com/claude-code): open this folder and say "Help me install Stu in our environment."

## Contribute

See **[CONTRIBUTING.md](CONTRIBUTING.md)**. Improvements made at one CLT are meant to reach the others. Report security problems privately: **[SECURITY.md](SECURITY.md)**.

## Status

Stu is in active development and not yet at v1.0. Tables and forms can still change between versions. Try it in a sandbox environment first.

## Licence

MIT. See [LICENSE](LICENSE). Maintained by Unwind Housing & Advisory Services LLC.

## Versions

Each release is a Git tag (`v0.4`) with a GitHub release titled `v0.4 (2026-11-07)`. The schema build also sets the CLT Stewardship solution's version to match (v0.4 becomes 0.4.0.0), so the solution in each environment shows which build it has. Before the repo existed, releases were zip files named `clt-dataverse_<date>_v<main>.<sub>.zip`.

| Version | Date | What changed |
|---|---|---|
| v0.1 | 2026-11-05 | Schema: 15 tables, choices, lookups, keys |
| v0.2 | 2026-11-06 | App build: navigation, forms, views |
| v0.3 | 2026-11-07 | Editable lists, Developments, Documents, Form submissions, sale workflow layout; property resale formula and sale ERRR snapshot removed |
| v0.4 | 2026-11-07 | Fix: app build runs on an environment that doesn't have the new tables yet, so the upgrade order works; hides the macOS SSL warning. Moved to a Git repo with CLAUDE.md, docs and CI tests. |
| v0.5 | in progress | SharePoint document storage (Property and Household libraries, `--sharepoint-site`). Portfolio cleanup: Development and Document tables removed, insurance on the occupancy only, State list with counties linked to a state, APN renamed Parcel number, display-name sync. Next: projects, eligibility, selection, certification. |
