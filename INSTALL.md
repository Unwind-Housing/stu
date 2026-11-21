# Installing Stu

This guide is written so that a staff person who is comfortable with computers can install Stu with Claude's help. Open this folder in Claude Code and say:

> Help me install Stu in our environment. Follow INSTALL.md with me, one step at a time.

**For Claude:** go one step at a time and wait for the person. Say what each command does before running it, and which environment it changes. Announce every browser sign-in before it happens: which organization, which account, and why. Install into a Dev (sandbox) environment first, never straight into production. Write what you learn about this installation (addresses, accounts, decisions) into `CLAUDE.local.md` as you go.

Plan on half a day for a first install. Most of the time is waiting for Dataverse.

## What you need first

| You need | Notes |
|---|---|
| A Microsoft 365 tenant for your organization | Most CLTs already have one. |
| Power Apps licences | Either **Power Apps per app** passes (one per person who will use Stu; nonprofits can claim a donation from Microsoft directly, under Billing > Purchase services in admin.microsoft.com) or **Power Apps Premium** per person. Per app passes are assigned to the **environment** in the Power Platform admin center, not to people. |
| One **Power Apps Premium** licence for a service account | Flows that use Dataverse check the licence of the flow's **owner**. Create a service account (for example `automation@yourorg...`), give it Power Apps Premium and a Microsoft 365 licence that includes SharePoint, and let it own every flow. |
| A Dataverse environment | A **Sandbox** for Dev, later a **Production** one. Dynamics 365 apps: off. |
| A SharePoint site for documents | For example a site called Stewardship. You must be a site owner. |
| A forms platform account | Cognito Forms today. Only needed for online screeners and applications. |
| A computer with Python 3.9 or newer and Git | Node.js is optional (one test uses it). |
| The System Administrator role in the environment | For the person who signs in to run the build. |

## Step 1. Get the code

```
git clone https://github.com/<owner>/stu.git
cd stu
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell the activate line is `.venv\Scripts\Activate.ps1`.

Then check everything runs, with no sign-in:

```
python3 build_schema.py --check && python3 build_app.py --check && python3 build_flows.py --check
```

## Step 2. Create the environment

In **admin.powerplatform.microsoft.com > Environments > + New**: type Sandbox, add a Dataverse data store, Dynamics 365 apps off, sample apps off. Limit access with a security group that holds the people who will use it, and add the service account to that group. Note the environment's address (like `https://yourorg-dev.crm.dynamics.com`).

If you use per app passes, assign some to this environment: **Licensing > Products > Power Apps > Environments > (the environment) > Manage capacity**.

## Step 3. Create the publisher and the solution

These names must be exact. Every Stu installation uses the same ones, which is what lets you take new versions and send changes back.

In **make.powerapps.com**, with your environment picked at the top right: **Solutions > + New solution**.

| Field | Value |
|---|---|
| Display name | `CLT Stewardship` |
| Name | `CLTStewardship` |
| Publisher | **+ New publisher**: display name `Unwind Housing`, name `unwindhousing`, prefix `clt`, choice value prefix `76827` |

## Step 4. Make your organization's folder

```
cp -R clients/example clients/yourname
```

Open `clients/yourname/client.json` and fill in your organization's name, environment addresses, service account, SharePoint site, header colors and logo address. The `forms/` folder inside holds your form mappings (step 10). This folder is yours: git ignores it, so nothing in it goes to the public repository. To keep it backed up and versioned, make it its own private repository (`cd clients/yourname && git init`).

## Step 5. Build the tables

```
caffeinate -i python3 build_schema.py --url https://yourorg-dev.crm.dynamics.com --sharepoint-site https://yourorg.sharepoint.com/sites/Stewardship
```

- A browser opens to sign in. Use an account with the System Administrator role in this environment.
- `caffeinate -i` keeps a Mac awake; leave it off on Windows.
- A first run takes 20 to 40 minutes. It is safe to run again: what's there is skipped.
- If a Dev environment shares the SharePoint site with production, add `--sharepoint-folder DEV`.

The script can't create SharePoint libraries in every tenant. If it prints steps to create them by hand, follow them: **New > Document library**, named exactly as printed (`clt_property`, `clt_household`, `clt_occupancy`).

Then switch SharePoint on, once per environment: **admin.powerplatform.microsoft.com > Environments > (the environment) > Settings > Integration > Document management settings > Enable server-based SharePoint integration**, enter the site address, validate, enable. Then **Document Management Settings**: tick Property, Household and Occupancy, same address, leave "Based on entity" unticked.

**Set who can see the files.** Dataverse security does not carry over to SharePoint. Give staff access to the site through a group, and restrict the Household Documents library to the staff who should see applicants' papers.

## Step 6. Add the rollup columns by hand

A few rollup columns can't be scripted yet. Follow `docs/STEP4-columns.md`. Schema names must match exactly.

## Step 7. Build the app

```
caffeinate -i python3 build_app.py --url https://yourorg-dev.crm.dynamics.com
```

This builds **Stu**: one app with two areas, Stewardship and Applications and Sales. Open it from **make.powerapps.com > Apps > Stu > Play**. A CLT that wants one side only can build `--app core` or `--app intake` instead.

## Step 8. Load the reference data and branding

```
python3 tools/load_counties.py --url https://yourorg-dev.crm.dynamics.com --dry-run
python3 tools/load_counties.py --url https://yourorg-dev.crm.dynamics.com
python3 tools/apply_branding.py --url https://yourorg-dev.crm.dynamics.com --client clients/yourname/client.json
```

Then, in Stu, under **Applications and Sales > Settings**: fill in **Organization eligibility** (your income limit, ratios and other rules) and add **HUD AMI Limits** for your counties (`docs/PLAYBOOK.md`, "Every year: HUD AMI limits").

## Step 9. Build the flows

Sign in as the **service account** for this step, so it owns the flows:

```
python3 build_flows.py --url https://yourorg-dev.crm.dynamics.com
```

Then, once, by hand, still as the service account: **make.powerapps.com > Solutions > CLT Stewardship > Connection references**. Open each one and pick or create the service account's connection (Dataverse, SharePoint). Then open each flow under **Cloud flows** and **Turn on**.

## Step 10. Connect your online forms (optional)

You will have one **screener** form and one **full application** form, in your forms platform (Cognito Forms today). You can have more than one screener.

Stu doesn't care how your questions are worded. A **mapping file** per form says which question feeds which field:

- `clients/yourname/forms/screener.json`
- `clients/yourname/forms/full-application.json`
- `clients/yourname/forms/screener-<name>.json` for another screener with different questions. A screener that is a **copy** of your first one needs no file of its own.

To make your mappings:

1. Build your forms. The example mappings in `clients/example/forms/` show every question Stu can use; a question you don't ask is simply left out.
2. Connect each form to its flow: `docs/PLAYBOOK.md`, "add a screener form" and "connect a full application form". (Step 9 already built the flows, from the example mappings you copied.)
3. Submit one made-up entry on each form. Stu keeps a copy of every entry it receives, even one it can't read yet: in Stu, **Applications and Sales > Messages > Form submissions**, open the entry and copy its **Payload**. Save it as `clients/yourname/samples/screener.json` (and `full-application.json`).
4. Ask Claude: "Write my form mappings from these sample entries." Then check each one:

```
python3 form_mapping.py clients/yourname/forms/screener.json clients/yourname/samples/screener.json
```

It lists any mapped question the entry doesn't have, and the questions in the entry that Stu isn't reading.

5. Run step 9 again, so the flows read your questions. Then open each made-up entry in the forms platform and save it again: it should now arrive as an application.

A flow's HTTP address works like a password. Never put it in a file, an email or an issue.

## Step 11. Load your existing records (optional)

Fill in the spreadsheet templates in `docs/templates/` (their README explains each column), put them in a folder under `export/`, and run a dry run first:

```
python3 tools/import_records.py "export/load" --url https://yourorg-dev.crm.dynamics.com --dry-run
python3 tools/import_records.py "export/load" --url https://yourorg-dev.crm.dynamics.com
```

## Step 12. Check it works

Walk through `docs/PLAYBOOK.md`, "Test run: screener to occupancy", with made-up people.

## Going to production

Repeat steps 2 to 9 against a Production environment, with the production address in your client file. Give each staff person a security role and, with per app passes, make sure the environment has enough passes.

## Getting new versions

```
git pull
python3 build_schema.py --check && python3 build_app.py --check && python3 build_flows.py --check
```

Read the version table in `README.md` for anything a version asks you to do, then run steps 5, 7 and 9 again, Dev first. The scripts add and update; they don't delete. If a release retires something, its notes will say so, and removing it (`--remove-retired`) is always a separate, deliberate step because it deletes data.

## If something goes wrong

| What you see | Do this |
|---|---|
| Sign-in error mentioning AADSTS | Run again with `--device-code` added. You'll get a code to enter at microsoft.com/devicelogin. |
| Sign-in goes to the wrong organization | Add `--tenant yourorg.org`, using your organization's email domain. |
| `Solution 'CLTStewardship' not found` | Step 3 isn't done, or the name differs. |
| `Publisher prefix is ..., expected 'clt'` | The solution was made with a different publisher. Make it again as in step 3. |
| `STOPPED:` followed by a message | Run the same command again. If it stops in the same place twice, give Claude the message. |
| Saving a flow asks for a premium licence | The flow's owner needs Power Apps Premium. Build the flows signed in as the service account. |
| The Documents tab says "ask your admin to enable it" | SharePoint integration isn't switched on (step 5). |

More in `docs/PLAYBOOK.md`, "Troubleshooting".
