# CLT Stewardship playbook

How to run CLT Stewardship day to day: the jobs that come round every year, the ones you do when something new starts, and what to do when something doesn't work.

This is for whoever looks after the system at a CLT (a staff person, or a consultant working with them). Menu paths are for the **Intake & Selection** area of Stu unless they say otherwise (switch areas at the bottom left of the sidebar; where a step says **CLT Intake & Selection**, that is this area). Where a step needs a command, it's run from the project folder in Terminal; each command is explained, with the Windows PowerShell equivalent where it helps.

Add to this whenever you work out how to do something that will come up again.

## Calendar

| When | Job | Section |
|---|---|---|
| Every year, when HUD publishes new income limits (usually April to June) | Add the new HUD AMI Limits for each county you serve | [HUD AMI limits](#every-year-hud-ami-limits) |
| When you start taking screeners for a new project or a new rolling list | Add a screener form | [New screener form](#when-needed-add-a-screener-form) |
| When a project opens its full application | Connect the full application form | [Full application form](#when-needed-connect-a-full-application-form) |
| When a client's existing homes and homeowners need loading, or a batch of new homes | Load them from spreadsheets | [Load from spreadsheets](#when-needed-load-properties-and-households-from-spreadsheets) |
| Before a release goes to a new environment | Walk one made-up household from screener to occupancy | [Test run](#test-run-screener-to-occupancy) |

---

## Every year: HUD AMI limits

**Why:** every applicant's **Stated income (% of AMI)** is worked out from HUD's income limits for their county and household size. Until the new year's limits are in, everyone is measured against last year's.

**When:** HUD publishes new limits each spring, usually between April and June, with an effective date in HUD's notice. Do this as soon as they're out. Until then, last year's limits keep working.

**Time:** about 10 minutes per county.

### 1. Get the figures from HUD

1. Go to **huduser.gov/portal/datasets/il.html** and open the **Income Limits Documentation System** for the new fiscal year (for example FY 2027).
2. Choose the **state** and **county** (for example Washington, then Jefferson County; repeat for each county you serve).
3. You'll see the **Income Limits Summary** table. You need two things from it:
   - **Median Family Income** (one figure, for example $107,000).
   - The **Very Low (50%) Income Limits** row: eight figures, one for each household size from 1 to 8 people.
4. Note the **effective date** from HUD's notice for that year, if you have it.

You don't need the Extremely Low or Low (80%) rows. AMI is worked out from the 50% row: 100% AMI is twice the 50% limit.

**Quick check that you copied the row right:** HUD's 50% limits follow a fixed pattern from the 4-person figure, rounded up to the next $50:

| People | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| % of the 4-person figure | 70% | 80% | 90% | 100% | 108% | 116% | 124% | 132% |

For example, Jefferson County 2026: 4 people = $53,500, so 1 person = 70% of 53,500 = 37,450. If a figure is far off this pattern, check you're reading the 50% row. (HUD occasionally adjusts a county, so small differences can be real.)

### 2. Add one record per county

In **CLT Intake & Selection**:

1. Go to **Settings › HUD AMI Limits** and select **+ New**.
2. Fill in:
   - **Name:** county and year, for example `Jefferson 2027`.
   - **County:** pick the county (for example Jefferson County, WA).
   - **Year:** for example `2027`.
   - **Source:** `HUD`. (Only HUD records are used for % of AMI. `Other` is for a funder's own table, kept for reference.)
   - **Source details:** for example `HUD FY2027 Income Limits Summary`.
   - **Effective date:** from HUD's notice, if you have it.
   - **Median family income:** the one figure from the top of HUD's table. This is for reference only: HUD's "family" isn't the same as our household, so it isn't used in any calculation.
   - **50% limit, 1 person** through **50% limit, 8 people:** the eight figures from the Very Low (50%) row, in order.
3. Select **Save**.
4. Repeat for each county you serve.

**Keep last year's records.** Don't change or delete them: certifications and older applications may refer to them.

**Larger households:** there's nothing to enter for 9 or more people. The system uses HUD's rule: the 4-person limit × (1.32 + 0.08 for each person over 8).

**Shortcut:** you can send Claude a screenshot of HUD's summary table for each county instead, and it will add the records and check the figures against HUD's pattern.

### 3. Move existing applicants to the new limits

New screeners pick up the newest limits automatically. Applicants who came in earlier still point at last year's until you run this once. Someone with the project set up on their Mac runs it (or ask Claude to):

```
cd ~/Code/stu
```
Go to the project folder. (PowerShell: `Set-Location ~/Code/clt-stewardship`.)

```
source .venv/bin/activate
```
Switch on the project's Python setup, so the next commands use it. (PowerShell: `.venv\Scripts\Activate.ps1`.)

```
python3 tools/recalc_ami.py --url https://yourorg.crm.dynamics.com --dry-run
```
A trial run: lists the applications that would move to the new limits, and changes nothing. A browser window opens to sign in: use your CLT account. Put your own environment's address in place of `yourorg`.

```
python3 tools/recalc_ami.py --url https://yourorg.crm.dynamics.com
```
The real run. It points each screener's **AMI limits used** at its county's newest HUD record. Their **Stated income (% of AMI)** then recalculates by itself. It's safe to run again: a second run changes nothing.

The last line says how many it updated, and how many have **no HUD limits for their county**. A number there usually means an applicant lives in a county you haven't added (or gave no county).

### 4. Check

1. Open **Start here › Hub** and look at **Average % of AMI**: the note under it says how many screeners have a figure.
2. Open any screener (**Applicants › Applications**) and check **AMI limits used** shows the new year, for example `Jefferson 2027`, and **Stated income (% of AMI)** has a figure.

To check one by hand: stated income × 50 ÷ the 50% limit for their household size. For example $68,000 for 4 people in Jefferson County 2026: 68,000 × 50 ÷ 53,500 = 64%.

---

## When needed: add a screener form

Every screener form posts its entries to the same **Screener intake** flow. The flow adds the household, its members and the application, and records which form it came from under **Settings › Source forms**.

**Make a new screener by copying an existing one in Cognito** (the form's **⋯** menu › **Copy**). The copy keeps:

- the question names the flow reads (rename a question and the flow can't find its answer), and
- the **Submission Settings**, including the flow's address, so there's nothing to set up.

Then:

1. **Rolling or general list:** nothing else to do. Its first entry adds it to **Settings › Source forms**, and its applications arrive without a project, ready to add from **Projects › Add to a project**.
2. **Form for one project:** before the form goes live, go to **Settings › Source forms › + New** and fill in **Forms platform** `Cognito Forms`, **Form ID** (the number in the form's Cognito web address) and **Add new applications to project**. Every new application from that form then goes straight into that project.

If you change or add questions on a copied form, tell Claude: the flow reads the questions by name, from your mapping file (`clients/<name>/forms/screener.json`). A screener whose questions differ gets its own mapping file (`screener-<name>.json`) and its own flow, with its own address: run `build_flows.py` again after adding it.

**Building a form from scratch** (not recommended): in Cognito, open the form's **Settings › Submission Settings**, switch on **Post JSON Data to a Website**, and paste the flow's address into both **Submit Entry Endpoint** and **Update Entry Endpoint**. The address is in Power Automate: **Solutions › CLT Stewardship › CLT: Screener intake › Edit**, then click the first box, **When Cognito posts a screener**, and copy the **HTTP URL**. Treat the address like a password: don't put it in documents or the repo.

---

## When needed: connect a full application form

Every full application form posts its entries to the **Full application intake** flow. The flow finds the applicant's application, saves the answers on it (**Full application** tab), adds the household members, and adds one record per income source, debt and account (**Income, debts and assets** tab), each marked *Not reviewed*.

**How it finds the application:** the form has a read-only **Application Number** box at the top of page 1, which the invite link fills in (A-00012). If it's empty, the flow uses the primary applicant's email and picks that household's newest application. If neither matches, the entry shows up under **Messages › Form submissions** as *Needs attention*.

**To connect a form** (one time per form; a Cognito copy of a connected form keeps its settings):

1. In Power Automate: **Solutions › CLT Stewardship › CLT: Full application intake › Edit**. Click the first box, **manual**, and copy the **HTTP URL**. It should end in `&sig=` and a long code; if it stops at `api-version=1`, see the troubleshooting section below. Treat it like a password. Close the designer without saving.
2. In Cognito, open the form's **Settings › Submission Settings**, switch on **Post JSON Data to a Website**, and paste the address into both **Submit Entry Endpoint** and **Update Entry Endpoint**. **Save**.
3. Check the form has the **Application Number** box: a Textbox labelled exactly `Application Number`, inside the **Primary Applicant** section, **Read Only: Always**.

**The invite link** is the form's public address plus the applicant's A-number:

```
https://www.cognitoforms.com/YourOrg/YourFullApplicationForm?entry={"PrimaryApplicant":{"ApplicationNumber":"A-00012"}}
```

Swap in the form's own address (Cognito: the form's **Share** page) and the applicant's record number (top of their application). Open the link once yourself to check the box fills in.

**When the applicant saves the entry again** (or staff change it in Cognito), the flow updates the same records: answers, members and lines are matched, nothing is added twice. Lines the applicant deleted from the form stay in Dataverse: set them to *Excluded*. Review status and verified amounts are never overwritten.

**Not copied:** uploaded documents (they stay in Cognito until the household is certified) and ethnic origin (waits for column security).

---

## When needed: load properties and households from spreadsheets

For a new client's existing homes and homeowners, or a batch of new homes. The tool is `tools/import_records.py`; the file layouts and rules are in `docs/templates/README.md`.

1. Put the source files in `export/<client> properties/` in the repo. Git ignores `export/`, so client data can't be committed. No Social Security numbers or bank account numbers.
2. Fill in up to five files in `export/<client> load/`: `properties.csv`, `households.csv`, `members.csv`, `occupancies.csv`, `fees.csv`. Copy the headers from `docs/templates/`.
3. Dry run. It reads the environment, checks every row and lists what it would create. Nothing changes.
   ```
   python3 tools/import_records.py "export/load" --url https://yourorg.crm.dynamics.com --dry-run --add-list-values
   ```
4. Fix anything it lists (each problem names its file and row), and read the list of records it would create.
5. Run it again without `--dry-run`.
6. Spot-check in the app: **Portfolio > Properties**, **People > Households**, and one occupancy's **Formula price**.

Good to know:
- **It's safe to run twice.** A property with the same name, a household whose primary applicant has the same name, and occupancies and fees that are already there are left alone.
- **Document folders.** Each new property and household gets a SharePoint folder from the folder flows, in whichever site the environment points at. When Dev shares the production SharePoint site, so its folders go inside a **DEV** folder in each library (set once with `build_schema.py ... --sharepoint-folder DEV`). A production environment is set up without that option.
- **Where the figures come from.** Base price and dates: the recorded memorandum of ground lease. Bedrooms, baths, square feet and year built: the county assessor's page for the homeowner's parcel (the land parcel has no building details).
- **Common parcels** (shared parking, open space) are loaded as a property with type *Common area*, no status, and no occupancy. Give them the same **Neighborhood** as the homes that share them.
- **Occupancy folders.** Each occupancy gets its own folder (ground lease, closing papers, ERRR requests). The household folder is for application and certification documents only.

---

## Start from scratch and load test homes

For a **test** environment only: clear out every record and load a small made-up portfolio, so a round of testing starts from a known place. One command does all of it. Never run it where real records live. It can't be undone.

**What goes:** every property, household, member, application (with income, debts and assets), occupancy and everything recorded on one (verifications, insurance, follow-ups, loans, requests), sale, fee, ERRR entry, certification, selection round, notice and form submission, and every project with its homes, priorities, income bands and lottery factors (add `--keep-projects` to leave the projects; their homes still go, because they point at properties).

**What stays:** **Settings > Lists** (with the counties), HUD AMI Limits, eligibility rules, source forms, message templates, settings, flows.

**What gets loaded:** 20 homes in a made-up town.
- 10 occupied. 5 of those have been resold 1 to 3 times, so they have past owners and a price history. 2 use the Appraisal share formula.
- 10 empty: 4 vacant, 4 for sale, 2 under construction.
- 19 households, each with a last name ending in **-Test** and an email at `example.com`.
- History: a closed sale for each of the 10 first purchases and 9 resales; insurance policies (two under-insured, two renewing soon, two homes with none); loans; improvements; homeowner requests at different stages; follow-ups (one overdue); notes; ERRR entries; past verifications. Dates are worked out from the day you run it, so the Verification hub and the dashboard show a mix of up to date, due soon, overdue and never done.
- No applicants and no projects: make a project in the app, and applicants arrive through the sandbox screener form.

Steps, from the repo root with `.venv` active:

1. **If the environment holds anything real, save it first.** There is no general export tool yet; ask the maintainer. Keep the saved files in `export/` with a note on how to load them back.
2. Count what would go. Changes nothing.
   ```
   python3 tools/start_from_scratch.py --url https://yourtest.crm.dynamics.com --sharepoint-site https://yourorg.sharepoint.com/sites/Stewardship --sharepoint-folder DEV
   ```
3. Read the list. Then run it for real by adding `--confirm` with the first part of the environment's address, so a slip can't clear the wrong one.
   ```
   python3 tools/start_from_scratch.py --url https://yourtest.crm.dynamics.com --sharepoint-site https://yourorg.sharepoint.com/sites/Stewardship --sharepoint-folder DEV --confirm yourtest
   ```
   Expect the test portfolio line to say 105 created (20 properties, 19 households, 27 members, 19 occupancies, 20 fees), then the history counts.
4. In the app: make a test project (**Projects**), and add homes to it from the four *For sale* homes (40 Harbor Row, Units 5 to 8). Point the sandbox screener's source form at the project if new screeners should land in it.

Good to know:
- **If the sign-in can't reach SharePoint** (in some tenants Microsoft's sign-in app for Dataverse tools isn't allowed into SharePoint), the command says so, clears the records, and stops before loading. That is the moment to empty the folders by hand, because every folder there is an old one: in SharePoint, open each of the four libraries (Property, Household, Occupancy and Project Documents), open the **DEV** folder, tick the circle at the top of the list to select everything, and **Delete**. Then run the command again with `--confirm` and without the two `--sharepoint` options: it finds nothing to delete and loads the test homes.
- **SharePoint.** With the two `--sharepoint` options, the old record folders go to the site's recycle bin (kept there about 93 days). Only folders inside the named parent folder (`DEV`) of the Property, Household, Occupancy and Project libraries are touched, so an environment that shares a site can't clear another one's folders. Leave the options off and SharePoint isn't touched. Loading makes a new folder per property, household and occupancy when the folder flows are on.
- **Record numbers carry on.** After a reset the next property is not P-00001; the counter keeps going.
- **The forms platform isn't touched.** Old sandbox entries stay there; delete them in the forms platform if you want a clean list.
- **Emails go nowhere.** `example.com` addresses can't receive mail. To try the verification emails for real, change a test household's **Primary email** to an address of your own.
- **Just the pieces.** `tools/reset_records.py` only clears records (it keeps projects unless given `--with-projects`); `tools/make_test_data.py` only writes the five import files to `export/test-data`; `--no-test-data` on the one command leaves the environment empty.
- **To change the test portfolio,** edit `tools/make_test_data.py` (a short list of rules: `build` for the homes and people, `history` for the rest) and add a check to `tests/test_reset.py`.

---

## Test run: screener to occupancy

One made-up household through the whole path, before a release goes to a new environment. Use the sandbox forms and an email address you can tell apart (for example `test.rivera@example.com`). Steps marked **by hand** aren't automated yet: note anything that's slow or confusing, it decides what gets automated next.

**1. Screener.** Submit the sandbox screener. In **CLT Intake & Selection › Applicants › Applications**, the new application appears as `Last - A-000xx`, with **Stated income (% of AMI)** and **Organization eligibility** filled in.

**2. Add to the project.** **Projects › Add to a project**: tick the applicant, pick the project, **Add**.

**3. Pre-screen.** The real order is screener, pre-screen, lottery, then the full application for the top households on each list. First check the project has **Priorities** and a **Monthly housing cost** for each home size it's selling. Then **Projects › Pre-screen**: pick the project, select a result to see its tests, and **Save results**. The application gets its **Pre-screen result**, the **Home sizes eligible for**, and one row per test under **Pre-screen checks**; its stage becomes *Pre-screened*.

**3a. Lottery (not built).** Closing applications, Unique IDs, locking the lists and the draw aren't built yet, so the test run skips from pre-screen to the invite. Set **Stage** to *In selection* if you want to see it pass through.

**3b. Invite (by hand).** In a real round only the top households on each list are invited (**Invites per list** on the project, default 10). On the application, set **Stage** to *Invited to full application* and **Save**. Build the invite link (above) with their A-number and open it.

**4. Full application.** Fill in the form: a co-applicant, a child, two income sources, a debt, two accounts, a gift. Submit. Within a minute or so, on the application:
- **Stage** is *Full application submitted*.
- **Full application** tab: income change, gift, lender, residency and comments are filled in.
- **Income, debts and assets** tab: one row per line, each linked to the right person (if a name you typed didn't match a member, **Household member** is empty and **Household member as entered** shows what was typed).
- The household's members have dates of birth and relationships.
- **Messages › Form submissions**: the entry is *Processed*.

**5. Certify (by hand).**
1. On each income, debt and asset row: set **Review status** (*Accepted*, *Adjusted* or *Excluded*) and fill in the verified amount.
2. **Applicants › Certifications › + New**: pick the household, application and project. Type **Certified household size**, **Certified annual income**, **Certified assets** and **Certified monthly debt** (the totals of the verified amounts). Set **Certified on** and **Expires on**, **Status** *Certified*, and **Save**.
3. On the application, set **Stage** to *Certified*.

**6. Sale and occupancy (by hand), in CLT Stewardship.**
1. **People › Households**: open the household. Copy the certified figures onto it: **Income certification date**, **Certification expires**, **Certified household size**, **Certified annual income**, **Certified income (% of AMI)**. Set **Status** to *Eligible*.
2. **Portfolio › Sales › + New**: pick the **Property** and **Buyer household**, **Status** *Pending*, **Contract date**, **Purchase price**, **Lender**. **Save**.
3. **Portfolio › Occupancies › + New**: pick the **Property** and **Household**, **Role** *Owner*, **Status** *Pending*, the resale formula terms. **Save**, then set **Buyer occupancy** on the sale.
4. At closing: sale **Status** *Closed* with the **Closing date**; occupancy **Status** *Current* with the **Start date**; household **Status** *Homeowner*; application **Stage** *Purchased*.

**7. Tidy up.** Deactivate the test household and application (**⋯ › Deactivate**), so they don't count in the Hub figures, and delete the test entries in Cognito.

---

## Troubleshooting

### A screener was submitted but no application appeared

1. **Check Form submissions** (**Messages › Form submissions**). If the entry is there:
   - **Needs attention:** open it and read **Error detail**. A frozen change (Unique IDs already assigned) is expected: compare the entry with the application and update it by hand. Anything else: send Claude the error detail.
   - **Processed:** the application is there; search for the applicant's last name.
2. **If it isn't in Form submissions at all**, the form didn't reach the flow. Usually the flow's address in Cognito is missing or out of date. Copy the address from Power Automate and paste it into the form's **Submit Entry Endpoint** and **Update Entry Endpoint** (see [Building a form from scratch](#when-needed-add-a-screener-form) for where both are). Cognito also emails the form owner when a post fails.
3. **To send the entry through again** without the applicant resubmitting: in Cognito, open the entry, make a tiny change (a space in a comment box), and **Save**. That sends it to the Update endpoint.

### A form was submitted, nothing arrived, and the flow's run history is empty

The form's post is being refused before a run starts. The address saved in the form has no signature on the end (it stops at `api-version=1`), because the flow's first step was set to accept only signed-in people from the organization. That happens when a flow is saved in the Power Automate designer.

1. In Power Automate, open the flow, select **Edit**, and select the first step.
2. Set **Who can trigger the flow?** to **Anyone**. The signature in the address is what keeps it private.
3. **Save**, select the first step again, and copy the **HTTP URL**. It now ends in `&sig=` and a long code.
4. Paste it into the form's **Submit Entry Endpoint** and **Update Entry Endpoint**, and save the form.
5. Send the entry through again (see the step above).

To avoid it: don't select **Save** in the designer for the intake flows unless you mean to. Saving the screener flow there also renames its first step, which changes the address every screener form posts to; each form then needs the new address.

On a form with workflow statuses (the full application), an entry can only be saved with one of its action buttons, for example **Start Review**. Pick one that doesn't email the applicant.

### A page shows an error or an old version after an update

The browser is holding on to the old copy. Press **Cmd+Shift+R** (Windows: Ctrl+F5) on the page. If that doesn't help, open the app in a private window (Cmd+Shift+N). If it works there, sign out of the app and back in, or clear the site data for your environment's address.

### The app header isn't in the CLT's colors

Same cause and fix as above: a hard refresh or a private window. If it's still the default purple, ask Claude to re-run the branding step (`tools/apply_branding.py`).

## Annual verification form: connect it to Stu

The yearly form's answers arrive by themselves once the form posts each entry to the **CLT: Annual verification intake** flow.

1. The form needs a hidden question for the occupancy ID. The link from Activities > Occupancy verification fills it in (put `{occupancy id}` in the form link where that question goes).
2. Map the form's questions in `clients/<organization>/forms/annual-verification.json` (copy the example), then deploy the flow: `python3 build_flows.py --url <environment> --only "Annual verification"`.
3. In Power Automate: Solutions > CLT Stewardship > CLT: Annual verification intake > Edit > pick the Dataverse connection > Save > Turn on.
4. Copy the web address from the flow's trigger and paste it into the form's post-on-submit setting (in Cognito Forms: Build > Form settings > Post JSON data to a website > Submit Entry Endpoint, and the Update one too). Treat the address like a password: never write it in a file or a message.
5. Test: start one online request, fill in the form from its link, and check that the request turns to Received with the answers, and that an Insurance verification appears with the document on it.

If an entry doesn't show up, look in Settings > Form submissions: an entry that couldn't be matched is there as Needs attention, with the reason.

