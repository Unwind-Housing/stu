# Import templates

Example files for loading properties, households, occupancies and monthly fees with `tools/import_records.py`. Every row is made up. Replace the rows, keep the header row. A file you don't need can be left out.

- **properties.csv**: one row per home or parcel. **Property ref** is any short key you make up (P1, P2), used only to link occupancies and fees. Leave **Record number** blank for a new property. To update an existing one, give its record number (P-00002) and fill only the columns to change; blank cells are left alone.
- **households.csv**: one row per household. **Household ref** is any short key you make up (H1, H2), used only to link members. Use an existing record number (H-00003) to update a household. There's no name column: the household is named after its primary applicant.
- **members.csv**: one row per person, linked by **Household ref**. Exactly one **Primary applicant** per household.
- **occupancies.csv**: who owns or rents which home, linked by **Property ref** and **Household ref** (or an existing record number, P-00002 or H-00003). Carries the resale formula terms. A **Current** occupancy is also set as the property's current occupancy.
- **fees.csv**: monthly fees per property, linked by **Property ref**. **Fee type**: Ground lease fee, ERRR, Other.

Rules:
- Dates as YYYY-MM-DD. Money as plain numbers (285000, not $285,000).
- **State**: two letters (WA) or the full name. **County**: as listed in Settings > Lists (Jefferson County); it's matched within the State, so same-named counties in other states are never mixed up.
- **Property type**, **Tenure type**, **Neighborhood**, **Relationship to primary applicant**: must match a value in Settings > Lists (or add `--add-list-values`).
- **Status** (property): Prospective acquisition, Under construction, Vacant, For sale, Sale pending, Owner-occupied, Rented, Left program.
- **Status** (household): Applicant, Invited to full application, Eligible, Homeowner, Tenant, Past homeowner, Inactive.
- **Applicant role**: Primary applicant, Co-applicant, Other household member. **On title**: Yes or No.
- **Role** (occupancy): Owner, Tenant. **Status** (occupancy): Pending, Current, Past. **Resale formula**: Fixed annual rate, Appraisal share.
- **Count whole years only**: Yes or No. No means a sale partway through a year is priced to that date.
- Never include Social Security numbers or bank account numbers.

To load them (from the repo root, with `.venv` active). The first command is a dry run: it checks every row and lists what it would create, and changes nothing.

```
python3 tools/import_records.py docs/templates --url https://yourorg.crm.dynamics.com --dry-run
python3 tools/import_records.py docs/templates --url https://yourorg.crm.dynamics.com
```

- If any row has a problem, nothing is loaded and every problem is listed with its file and row.
- It's safe to run twice: records that are already there are left alone.
- Add `--add-list-values` to add a Property type, Tenure type, Neighborhood or Relationship the files use that isn't under Settings > Lists yet.
