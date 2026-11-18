"""Offline test: the Verification hub rules (webresources/stewardship.js) run in Node on worked examples, and the
page is checked against the schema. Skipped with a message if Node isn't installed."""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert");
const R = require(process.argv[process.argv.length - 1]);
const today = "2026-11-17";

// ---- how often: a setting in months, every 12 when blank or not a whole number of 1 or more
assert.strictEqual(R.months(""), 12); assert.strictEqual(R.months(undefined), 12); assert.strictEqual(R.months("6"), 6);
assert.strictEqual(R.months(" 24 "), 24); assert.strictEqual(R.months("0"), 12); assert.strictEqual(R.months("yearly"), 12); assert.strictEqual(R.months("1.5"), 12);

// ---- dates
assert.strictEqual(R.addMonths("2025-11-17", 12), "2026-11-17"); assert.strictEqual(R.addMonths("2026-01-31", 1), "2026-02-28");
assert.strictEqual(R.addMonths("2024-02-29", 12), "2025-02-28"); assert.strictEqual(R.addMonths("2026-08-15", 6), "2027-02-15");
assert.strictEqual(R.addDays("2026-12-20", 30), "2027-01-19");
assert.strictEqual(R.latest(["2025-03-01", "", null, "2026-01-15T00:00:00Z", "2024-12-31"]), "2026-01-15"); assert.strictEqual(R.latest([]), "");

// ---- where one activity stands
assert.deepStrictEqual(R.status("", 12, today), { state: "Overdue", last: "", dueOn: "" }, "never recorded counts as overdue");
assert.deepStrictEqual(R.status("2025-11-16", 12, today), { state: "Overdue", last: "2025-11-16", dueOn: "2026-11-16" }, "due yesterday");
assert.strictEqual(R.status("2025-11-17", 12, today).state, "Due soon", "due today is due soon, not overdue");
assert.strictEqual(R.status("2025-12-17", 12, today).state, "Due soon", "due in exactly 30 days");
assert.strictEqual(R.status("2025-12-18", 12, today).state, "Up to date", "due in 31 days");
assert.strictEqual(R.status("2026-06-01", 6, today).state, "Due soon", "a six-month cycle");
assert.strictEqual(R.status("2026-06-01", 12, today).state, "Up to date");

// ---- one row per occupancy: the newest of the typed date and the records, most urgent first
const occ = [
  { id: "a", name: "Rivera - 12 Pine St", property: "12 Pine St", household: "Rivera", role: "Owner",
    dates: { occupancy: "2026-03-01", insurance: "2026-02-01", contact: "" } },
  { id: "b", name: "Chen - 4 Oak Ave", property: "4 Oak Ave", household: "Chen", role: "Owner", dates: {} },
  { id: "c", name: "Okafor - 9 Elm Ct", property: "9 Elm Ct", household: "Okafor", role: "Tenant",
    dates: { occupancy: "2025-12-01", insurance: "2025-06-01", contact: "2026-01-05" } },
];
const records = { occupancy: { b: ["2025-01-10", "2024-01-08"] }, insurance: { a: ["2026-04-15"] }, contact: { a: ["2026-11-01", "2026-07-04"], c: ["2025-12-25"] } };
const rows = R.rows(occ, records, {}, today);
assert.deepStrictEqual(rows.map(r => [r.id, r.worst]), [["b", "Overdue"], ["c", "Overdue"], ["a", "Up to date"]], "never done first, then the oldest due date");
const a = rows[2], b = rows[0], c = rows[1];
assert.deepStrictEqual(b.activities.occupancy, { state: "Overdue", last: "2025-01-10", dueOn: "2026-01-10" }, "a record counts when nothing is typed");
assert.strictEqual(b.activities.insurance.state, "Overdue"); assert.strictEqual(b.activities.walkby, undefined, "walk-bys aren't on the hub");
assert.deepStrictEqual(b.fix, { clt_lastoccupancyverified: "2025-01-10" }, "the occupancy's date is brought up to its newest record");
assert.strictEqual(a.activities.insurance.last, "2026-04-15", "a record newer than the typed date wins");
assert.deepStrictEqual(a.fix, { clt_lastinsuranceverified: "2026-04-15", clt_lastcontact: "2026-11-01" }); assert.strictEqual(a.lastContact, "2026-11-01");
assert.deepStrictEqual(c.fix, {}, "nothing to bring up to date"); assert.strictEqual(c.lastContact, "2026-01-05", "a typed date newer than the records stays");
assert.deepStrictEqual([c.activities.occupancy.state, c.activities.insurance.state], ["Due soon", "Overdue"]);
// the setting changes what is due: insurance every 6 months puts Rivera's April approval overdue
const six = R.rows(occ, records, { InsuranceVerificationMonths: "6" }, today).find(r => r.id === "a");
assert.deepStrictEqual(six.activities.insurance, { state: "Overdue", last: "2026-04-15", dueOn: "2026-10-15" }); assert.strictEqual(six.activities.occupancy.state, "Up to date");

// ---- who to ask next: occupancy verification overdue or due soon, and not already asked
assert.deepStrictEqual(R.toAsk(rows), ["b", "c"]);
const asked = R.rows(occ, { ...records, requests: { b: { status: "Sent", method: "Online form", sent: "2026-11-10" } } }, {}, today);
assert.deepStrictEqual(R.toAsk(asked), ["c"], "a household with a request open isn't asked again"); assert.strictEqual(asked.find(r => r.id === "b").request.status, "Sent");
assert.strictEqual(rows[0].request, null); assert.deepStrictEqual(R.toAsk([]), []);

// ---- the figures and the filters
assert.deepStrictEqual(R.summary(rows), { occupancy: { overdue: 1, soon: 1, ok: 1 }, insurance: { overdue: 2, soon: 0, ok: 1 } });
assert.deepStrictEqual(R.filter(rows, "", "attention").map(r => r.id), ["b", "c"]); assert.deepStrictEqual(R.filter(rows, "", "all").length, 3);
assert.deepStrictEqual(R.filter(rows, "insurance", "attention").map(r => r.id), ["b", "c"]); assert.deepStrictEqual(R.filter(rows, "occupancy", "overdue").map(r => r.id), ["b"]);
assert.deepStrictEqual(R.filter(rows, "occupancy", "attention").map(r => r.id), ["b", "c"]);
assert.deepStrictEqual(R.rows([], {}, {}, today), []); assert.deepStrictEqual(R.summary([]).insurance, { overdue: 0, soon: 0, ok: 0 });

process.stdout.write(JSON.stringify({ activities: R.ACTIVITIES, contact: R.CONTACT_FIELD }));
// ---- the Dashboard's figures: each occupancy and insurance verification once
assert.deepStrictEqual(R.dashboard([{ dates: { occupancy: "2025-11-25", insurance: "2025-11-10" } },                   // due the 25th: this month; insurance a week overdue
                                    { dates: { occupancy: "", insurance: "2025-12-01" } },                              // never: overdue; insurance due next month
                                    { dates: { occupancy: "2025-11-17", insurance: "2025-11-30" } }], {}, "2026-11-17"), // due today and on the 30th: both this month
                       { overdue: 2, thisMonth: 3 });
assert.deepStrictEqual(R.dashboard([{ dates: { occupancy: "2026-05-20", insurance: "2026-08-20" } }], { OccupancyVerificationMonths: "6", InsuranceVerificationMonths: "3" }, "2026-11-17"), { overdue: 0, thisMonth: 2 });
assert.deepStrictEqual(R.dashboard([], {}, "2026-11-17"), { overdue: 0, thisMonth: 0 });
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the Verification hub rules weren't run. Install Node to run this test.")
        return
    import json
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "stewardship.js")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Verification hub rules failed:\n" + r.stdout + r.stderr)
    out = json.loads(r.stdout.strip().splitlines()[-1])

    import app_spec as core
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES, ENVIRONMENT_VARIABLES
    PREFIX = "clt"
    tables = {t["name"]: t for t in TABLES}
    cols = {t: {c["name"]: c for c in tables[t]["columns"]} for t in tables}
    rules = open(os.path.join(web, "stewardship.js")).read()
    page = open(os.path.join(web, "stewardship.html")).read()
    # every activity has its setting and its date on the occupancy; the dates are dates
    settings = {v["name"] for v in ENVIRONMENT_VARIABLES}
    for a in out["activities"]:
        assert a["setting"] in settings, a
        assert cols["occupancy"][a["field"][len(PREFIX) + 1:]]["kind"] == "date", a
    assert cols["occupancy"][out["contact"][len(PREFIX) + 1:]]["kind"] == "date"
    assert [a["key"] for a in out["activities"]] == ["occupancy", "insurance"], "walk-bys aren't a verification, so they aren't on the hub"
    assert "Record</button>" not in page and "r-save" not in page, "nothing is recorded from the hub: it leads to the request pages"
    # in the app: the page is under Activities, the two new lists are under Stewardship, and the occupancy form shows them
    assert core.PAGES["regular"] == ("Verification hub", "clt_/pages/stewardship.html")
    nav = dict(core.NAVIGATION)["Stewardship"]
    assert "page:regular" in dict(core.NAVIGATION)["Start here"] and "walkby" in nav and "relationshipnote" in nav
    for res in ("clt_/pages/stewardship.html", "clt_/pages/stewardship.js"):
        assert res in core.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    occ_form = str(core.FORMS["occupancy"])
    for piece in ("lastoccupancyverified", "lastinsuranceverified", "lastwalkby", "lastcontact", "relationshipnote", "walkby", "followup", "improvementcredit"):
        assert piece in occ_form, piece
    assert "walkby" in core.FORMS and "relationshipnote" in core.FORMS
    names = open(os.path.join(web, "names.js")).read()
    assert "dated: dated" in names and all(f[2] == "CLT.Names.dated" for f in core.FORM_SCRIPTS["walkby"] + core.FORM_SCRIPTS["relationshipnote"])
    guides = open(os.path.join(web, "guides.html")).read()
    assert 'id="regular"' in guides and "insurancepolicy" not in occ_form, "insurance policies are off the occupancy form"
    assert page.index('src="pages.js"') < page.index('src="stewardship.js"') < page.index("CLTRegular")
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    # every clt_ name is real
    used_tables = ("occupancy", "annualverification", "insurancepolicy", "relationshipnote", "insuranceverification", "improvementcredit")
    known = {f"{PREFIX}_name", f"{PREFIX}_occupancystatus"}
    assert all(s in CHOICES["verificationstatus"][1] for s in ("Due", "Sent", "Received"))
    for t in used_tables:
        known |= {f"{PREFIX}_{c}" for c in cols[t]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    used = (set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script)) | set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", rules))) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    # the dashboard leads into the Occupancy verification page, and that page leads back
    assert "clt_/pages/verify.html" in script and "occupancies=" in script and 'id="ask"' in page
    verify = open(os.path.join(web, "verify.html")).read()
    assert "occupancies=" in verify and "clt_/pages/stewardship.html" in verify
    # recording is one change set; no em dashes
    assert script.count("P.batch(") == 1 and "—" not in page and "—" not in rules
    print("OK: Verification hub rules give the expected due dates, order, figures and fixes for each worked example; "
          "the page is in the app and uses only real columns, choices and settings.")


if __name__ == "__main__":
    main()
