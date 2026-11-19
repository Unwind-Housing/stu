"""Offline test: the After the sale page's rules (webresources/aftersale.js) run in Node on worked examples, and the
page is checked against the schema. Skipped with a message if Node isn't installed."""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert");
const A = require(process.argv[process.argv.length - 1]);
const today = "2026-11-18";

// ---- the organization's list, for one sale: in order, and only the tasks that apply to that kind of sale
const list = [{ name: "Welcome the new homeowner", order: 70, action: "Tick it off", appliesTo: "Every sale", details: "Send the packet." },
              { name: "Enter the buyer's insurance", order: 10, action: "Enter the insurance", appliesTo: "Every sale", details: "" },
              { name: "Close out the seller's repair reserve", order: 80, action: "Tick it off", appliesTo: "Resales only" },
              { name: "Record the initial subsidy", order: 15, action: "Tick it off", appliesTo: "First sales only" },
              { name: "Something added by hand", order: null, action: "A choice from a later version", appliesTo: "" }, { name: "", order: 1 }];
assert.deepStrictEqual(A.tasksFor(list, "Resale").map(t => t.name), ["Enter the buyer's insurance", "Welcome the new homeowner", "Close out the seller's repair reserve", "Something added by hand"]);
assert.deepStrictEqual(A.tasksFor(list, "Initial sale").map(t => t.name), ["Enter the buyer's insurance", "Record the initial subsidy", "Welcome the new homeowner", "Something added by hand"]);
assert.deepStrictEqual(A.tasksFor(list, "Resale")[0], { name: "Enter the buyer's insurance", order: 10, action: "Enter the insurance", details: "" });
assert.strictEqual(A.tasksFor(list, "Resale")[3].action, "Tick it off", "an action this version doesn't know is a plain tick box"); assert.deepStrictEqual(A.tasksFor([], "Resale"), []);

// ---- how far a sale has got; Not needed counts as dealt with
assert.deepStrictEqual(A.progress([{ status: "Done" }, { status: "To do" }, { status: "Not needed" }, { status: "To do" }]), { total: 4, open: 2, done: 2 });
assert.deepStrictEqual(A.progress([]), { total: 0, open: 0, done: 0 }); assert.deepStrictEqual(A.progress(undefined), { total: 0, open: 0, done: 0 });

// ---- the closed sales: work left first (set up or not), newest closing first; a sale that isn't closed isn't listed
const sales = [{ id: "s1", name: "12 Pine St resale 2026", closed: true, closingDate: "2026-11-01" }, { id: "s2", name: "4 Oak Ave initial sale 2026", closed: true, closingDate: "2026-11-15" },
               { id: "s3", name: "9 Elm Ct resale 2025", closed: true, closingDate: "2025-06-01" }, { id: "s4", name: "3 Fir Rd resale 2026", closed: false, closingDate: "" }];
const tasks = [{ sale: "s1", status: "Done" }, { sale: "s1", status: "To do" }, { sale: "s3", status: "Done" }, { sale: "s3", status: "Not needed" }];
assert.deepStrictEqual(A.sales(sales, tasks).map(s => [s.id, s.state, s.open, s.total]), [["s2", "new", 0, 0], ["s1", "open", 1, 2], ["s3", "done", 0, 2]]);
assert.strictEqual(A.unfinished(sales, tasks), 2, "one with a task open and one not set up yet"); assert.strictEqual(A.unfinished([], []), 0);

// ---- the buyer's insurance
const ins = { carrier: "State Farm", policyNumber: "HO-123", coverage: "$410,000", effective: "2026-11-17", renewal: "2027-11-17" };
assert.deepStrictEqual(A.insuranceProblems(ins, today), []); assert.deepStrictEqual(A.insuranceProblems({ ...ins, policyNumber: "", renewal: "" }, today), [], "the policy number and renewal date can come later");
assert.ok(A.insuranceProblems({ ...ins, carrier: " " }, today)[0].includes("insurer")); assert.ok(A.insuranceProblems({ ...ins, coverage: "" }, today)[0].includes("dwelling coverage"));
assert.ok(A.insuranceProblems({ ...ins, coverage: "plenty" }, today)[0].includes("above 0")); assert.ok(A.insuranceProblems({ ...ins, effective: "" }, today)[0].includes("starts"));
assert.ok(A.insuranceProblems({ ...ins, renewal: "2026-11-17" }, today)[0].includes("after"));
assert.strictEqual(A.policyName("State Farm", "2026-11-17", "2027-11-17"), "State Farm 2026-27"); assert.strictEqual(A.policyName("State Farm", "2026-01-01", "2026-12-31"), "State Farm 2026");
assert.strictEqual(A.policyName("State Farm", "2026-11-17", ""), "State Farm 2026");
assert.strictEqual(A.verifiedOn("2026-11-17", today), "2026-11-17", "the insurance counts from the closing, so the next check is a year after the purchase");
assert.strictEqual(A.verifiedOn("", today), today); assert.strictEqual(A.verifiedOn("2026-12-01", today), today, "never a date in the future");
assert.strictEqual(A.recordName("2026-11-17", "Okafor - 12 Pine St"), "2026-11-17, Okafor - 12 Pine St");
process.stdout.write(JSON.stringify({ actions: A.ACTIONS, statuses: [A.TODO, A.DONE, A.SKIPPED], applies: [A.EVERY, A.RESALES, A.FIRST], resale: A.RESALE }));
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the After the sale rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "aftersale.js")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("After the sale rules failed:\n" + r.stdout + r.stderr)
    out = json.loads(r.stdout.strip().splitlines()[-1])

    import app_spec as core
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES, SEED_ROWS
    PREFIX = "clt"
    tables = {t["name"]: t for t in TABLES}
    cols = {t: {c["name"]: c for c in tables[t]["columns"]} for t in tables}
    rules = open(os.path.join(web, "aftersale.js")).read()
    page = open(os.path.join(web, "aftersale.html")).read()
    # the rules' words are the choices' words
    assert out["actions"] == CHOICES["aftersaleaction"][1] and out["statuses"] == CHOICES["saletaskstatus"][1] and out["applies"] == CHOICES["aftersaleapplies"][1]
    assert out["resale"] in CHOICES["saletype"][1]
    # each organization edits its own list, from a starting point; a sale's copy is its own
    start = SEED_ROWS["aftersaletask"]
    assert len(start) >= 6 and all(t["action"] in out["actions"] and t["appliesto"] in out["applies"] and t["details"] for t in start)
    assert len({t["order"] for t in start}) == len(start) and len({t["name"] for t in start}) == len(start)
    assert {t["action"] for t in start} >= {"Enter the insurance", "Add the settlement statement", "Tick it off"} and any(t["appliesto"] == "Resales only" for t in start)
    assert not re.search(r"\bOHT\b|Olympic", json.dumps(start)), "the starting list names no organization"
    assert {"order", "action", "appliesto", "details"} <= set(cols["aftersaletask"]) and {"order", "action", "details", "status", "donedate", "notes"} <= set(cols["saletask"])
    assert ("saletask", "sale", "sale", "Sale", "Cascade", True) in LOOKUPS and cols["saletask"]["status"]["default"] == "To do"
    # in the app: the page under Activities, the list under Settings, in the core app and Stu
    assert core.PAGES["aftersale"] == ("After the sale", "clt_/pages/aftersale.html") and "page:aftersale" in dict(core.NAVIGATION)["Activities"]
    assert "aftersaletask" in dict(core.NAVIGATION)["Settings"] and "aftersaletask" in core.FORMS and "saletask" in core.FORMS
    for res in ("clt_/pages/aftersale.html", "clt_/pages/aftersale.js"):
        assert res in core.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    assert "clt_sale_saletask_sale" in str(core.FORMS["sale"])
    # recording a closing leads here, and the Dashboard counts what is left
    resale = open(os.path.join(web, "resale.html")).read()
    assert resale.count("clt_/pages/aftersale.html") == 2 and '"sale=" + id' in resale
    dash = open(os.path.join(web, "overview.html")).read()
    assert "afterSaleTile(" in dash and "CLTAfterSale.unfinished(" in dash and dash.index('src="aftersale.js"') < dash.index("CLTAfterSale")
    assert page.index('src="pages.js"') < page.index('src="resale.js"') < page.index('src="aftersale.js"') < page.index("CLTAfterSale")
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    for piece in ("A.tasksFor(", "A.sales(", "A.insuranceProblems(", "A.verifiedOn(", "A.policyName(", "ch.review.Approved", "clt_lastinsuranceverified", "clt_settlementstatement"):
        assert piece in script, piece
    # every clt_ name is real
    used_tables = ("sale", "saletask", "aftersaletask", "occupancy", "insurancepolicy", "insuranceverification", "property")
    known = {f"{PREFIX}_name", f"{PREFIX}_settlementstatement_name"} | {f"{PREFIX}_{c}" for c in ("salestatus", "saletype", "saletaskstatus", "aftersaleaction", "insurancereviewstatus", "verificationmethod")}
    for t in used_tables:
        known |= {f"{PREFIX}_{c}" for c in cols[t]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    used = set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script)) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    assert "—" not in page and "—" not in rules
    assert 'id="aftersale"' in open(os.path.join(web, "guides.html")).read()
    print("OK: After the sale rules give the expected tasks, order, progress and insurance checks for each worked example; "
          "the page is in the app, the starting list is seeded, and it uses only real columns and choices.")


if __name__ == "__main__":
    main()
