"""Offline test: the Insurance verification page's rules (webresources/insurancecheck.js) run in Node on worked
examples, and the page is checked against the schema. Skipped with a message if Node isn't installed."""
import os
import json
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert");
const I = require(process.argv[process.argv.length - 1]);
const today = "2026-11-17";

assert.strictEqual(I.fromForm, undefined, "the yearly occupancy form no longer starts an insurance verification");

// ---- who to ask: homes whose insurance is due, and never one that already has a request open
const occ = [{ id: "o1", name: "Rivera - 12 Pine St", household: "Rivera", email: "maria@example.com", due: true },
             { id: "o2", name: "Chen - 4 Oak Ave", household: "Chen", email: "", due: true },
             { id: "o3", name: "Okafor - 9 Elm Ct", household: "Okafor", email: "ada@example.com", due: false },
             { id: "o4", name: "Lee - 3 Fir Rd", household: "Lee", email: "lee@example.com", due: true }];
const list = [{ id: "i1", occupancy: "o4", status: "Requested", method: "Online form" }, { id: "i2", occupancy: "o1", status: "Approved" }, { id: "i3", occupancy: "o3", status: "Cancelled" }];
const rows = I.choose(occ, list);
assert.deepStrictEqual(rows.map(r => [r.id, r.tick, r.request && r.request.id]), [["o1", true, null], ["o2", true, null], ["o3", false, null], ["o4", false, "i1"]],
                       "due homes are ticked; up to date isn't ticked; one with a request open isn't asked again");
assert.strictEqual(rows[0].method, undefined, "there is no online form to choose: Stu sends nothing");
assert.deepStrictEqual(I.choose(occ, list, ["O3", "o4"]).map(r => r.tick), [false, false, true, false], "opened for particular households: only those, and never one already asked");
assert.strictEqual(rows[0].household, "Rivera");

// ---- starting requests: Stu records that the household was asked, and sends nothing
assert.deepStrictEqual(I.startProblems([rows[0], rows[1]], { due: "2026-12-17" }, today), []);
assert.ok(I.startProblems([], { due: "2026-12-17" }, today)[0].includes("Tick")); assert.ok(I.startProblems([rows[0]], { due: "2026-11-01" }, today)[0].includes("past"));
assert.ok(I.startProblems([rows[0]], { due: "" }, today)[0].includes("due"));
assert.strictEqual(I.DEFAULT, undefined); assert.strictEqual(I.BUTTON, undefined);

// ---- closing one
assert.deepStrictEqual(I.closeProblems({ verified: today, outcome: "Approved", notes: "" }, today), []);
assert.ok(I.closeProblems({ verified: "", outcome: "Approved" }, today)[0].includes("date")); assert.ok(I.closeProblems({ verified: "2026-11-18", outcome: "Approved" }, today)[0].includes("future"));
assert.ok(I.closeProblems({ verified: today, outcome: "" }, today)[0].includes("how it came out")); assert.ok(I.closeProblems({ verified: today, outcome: "Issue found", notes: " " }, today)[0].includes("issue"));
assert.deepStrictEqual(I.closeProblems({ verified: today, outcome: "Issue found", notes: "Coverage below replacement cost." }, today), []);
assert.strictEqual(I.money("$350,000"), 350000); assert.strictEqual(I.money(" "), null); assert.ok(isNaN(I.money("lots")));
assert.deepStrictEqual(I.closeProblems({ verified: today, outcome: "Approved", coverage: "$350,000" }, today), []); assert.ok(I.closeProblems({ verified: today, outcome: "Approved", coverage: "lots" }, today)[0].includes("coverage"));
assert.ok(I.OPEN.includes("Issue found") && !I.CLOSED.includes("Issue found"), "an issue is saved on the request, which stays open until the insurance is approved");
assert.strictEqual(I.choose([{ id: "o1", due: true }], [{ id: "i9", occupancy: "o1", status: "Issue found" }])[0].tick, false, "a home with an issue open isn't asked again");
assert.strictEqual(I.counts("Approved"), true); assert.strictEqual(I.counts("Issue found"), false, "only an approval counts as verified");

// ---- cancelling one: the occupancy's date falls back to the approval before it
const others = [{ verified: "2025-10-01", status: "Approved" }, { verified: "2026-02-01", status: "Issue found" }, { verified: "2026-03-01", status: "Cancelled" }, { verified: "", status: "To review" }];
assert.strictEqual(I.afterCancel("2026-11-10", { verified: "2026-11-10", status: "Approved" }, others), "2025-10-01");
assert.strictEqual(I.afterCancel("2026-11-10", { verified: "2026-11-10", status: "Approved" }, []), null, "nothing left: never verified");
assert.strictEqual(I.afterCancel("2026-11-10", { verified: "2026-11-10", status: "Issue found" }, others), undefined, "an issue never set the date");
assert.strictEqual(I.afterCancel("2026-11-12", { verified: "2026-11-10", status: "Approved" }, others), undefined, "a newer date on the occupancy stays");
assert.strictEqual(I.afterCancel("2025-10-01", { verified: "", status: "To review" }, others), undefined);
assert.strictEqual(I.recordName(today, "Rivera - 12 Pine St"), "2026-11-17, Rivera - 12 Pine St");

// ---- the insurer's card: entering it is an approved insurance verification
assert.deepStrictEqual(I.cardProblems({ occupancy: "o1", verified: today, coverage: "" }, today), []);
assert.deepStrictEqual(I.cardProblems({ occupancy: "o1", verified: "2026-10-30", coverage: "$410,000" }, today), []);
assert.ok(I.cardProblems({ occupancy: "", verified: today }, today)[0].includes("home")); assert.ok(I.cardProblems({ occupancy: "o1", verified: "" }, today)[0].includes("date"));
assert.ok(I.cardProblems({ occupancy: "o1", verified: "2026-11-18" }, today)[0].includes("future")); assert.ok(I.cardProblems({ occupancy: "o1", verified: today, coverage: "lots" }, today)[0].includes("coverage"));
assert.strictEqual(I.cardTarget("o4", list), "i1", "a home with a request open: the card closes that one");
assert.strictEqual(I.cardTarget("o1", list), "", "an approved one stays as it is: the card is a new verification"); assert.strictEqual(I.cardTarget("o3", list), "");
assert.strictEqual(I.CARD, "Insurer's card");
process.stdout.write(JSON.stringify({ card: I.CARD }));
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the Insurance verification rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "insurancecheck.js")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Insurance verification rules failed:\n" + r.stdout + r.stderr)

    import app_spec as core
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES
    PREFIX = "clt"
    tables = {t["name"]: t for t in TABLES}
    cols = {t: {c["name"]: c for c in tables[t]["columns"]} for t in tables}
    rules = open(os.path.join(web, "insurancecheck.js")).read()
    page = open(os.path.join(web, "insurance.html")).read()
    hub = open(os.path.join(web, "stewardship.html")).read()
    # every status is open, closed or cancelled
    listed = re.search(r'OPEN = \[(.*?)\], CLOSED = \[(.*?)\], CANCELLED = "(.*?)"', rules)
    assert sorted((listed[1] + ", " + listed[2] + ", " + listed[3]).replace('"', "").split(", ")) == sorted(CHOICES["insurancereviewstatus"][1])
    assert cols["insuranceverification"]["status"]["choice"] == "insurancereviewstatus" and cols["insuranceverification"]["document"]["kind"] == "file"
    assert ("insuranceverification", "occupancy", "occupancy", "Occupancy", "Cascade", True) in LOOKUPS
    from schema import RETIRED
    assert not any(l[0] == "insuranceverification" and l[1] == "annualverification" for l in LOOKUPS) and ("insuranceverification", "annualverification", "annualverification") in RETIRED["lookups"], \
        "insurance is checked on its own: nothing ties an insurance verification to the yearly occupancy form"
    assert "documentslink" not in cols["insuranceverification"] and "annualverification" not in page and "documentslink" not in page
    # in the app, under Activities, in the core app and Stu; the hub leads to it
    assert core.PAGES["insurance"] == ("Insurance verification", "clt_/pages/insurance.html") and "page:insurance" in dict(core.NAVIGATION)["Activities"]
    for res in ("clt_/pages/insurance.html", "clt_/pages/insurancecheck.js"):
        assert res in core.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    assert "insuranceverification" in core.FORMS and "insuranceverification" in dict(core.NAVIGATION)["Stewardship"]
    assert 'data-goto="insurance"' in hub and 'data-goto="verify"' in hub and '"In progress"' in hub and "Asked<" not in hub
    assert page.index('src="pages.js"') < page.index('src="stewardship.js"') < page.index('src="verify.js"') < page.index('src="insurancecheck.js"') < page.index("CLTInsuranceCheck")
    # no emailed form link: asking a household is one list and one button, and the page never writes a link or a code
    for gone in ('id="steps"', 'data-step=', 'id="link"', 'id="subject"', 'id="sentit"', "mailto:", "clt_sentlink", "clt_verificationcode", "clt_sentto", "InsuranceFormLink", "saveSetting", "V.email"):
        assert gone not in page, gone
    for piece in ('id="all"', 'id="due"', 'id="next"', 'id="showall"', 'id="dash"', "I.startProblems(", "ch.method[I.PAPER]"):
        assert piece in page, piece
    from schema import ENVIRONMENT_VARIABLES
    assert not any(v["name"] == "InsuranceFormLink" for v in ENVIRONMENT_VARIABLES)
    assert CHOICES["insurancereviewstatus"][1][:5] == ["To review", "Needs contact", "Approved", "Issue found", "Cancelled"], "new statuses go on the end, so existing values keep their meaning"
    assert {"method", "duedate", "sentdate", "sentto", "sentlink", "verificationcode", "replacementcoverage"} <= set(cols["insuranceverification"])
    assert json.loads(r.stdout.strip().splitlines()[-1])["card"] in CHOICES["verificationmethod"][1] and CHOICES["verificationmethod"][1][:2] == ["Online form", "Paper"]
    for piece in ('id="k-open"', 'id="k-home"', 'id="k-date"', 'id="k-file"', 'id="k-save"', "I.cardProblems(", "I.cardTarget(", "card=", "ch.method[I.CARD]", "ch.status.Approved"):
        assert piece in page, piece
    assert 'data: "card=' in hub, "the hub leads to the card form"
    assert "toreview" not in page.lower().replace("to review", ""), "no move-to-review step: staff save the outcome"
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    assert "sendEmail" not in script   # the page never sends anything
    # every clt_ name is real
    used_tables = ("occupancy", "insuranceverification")
    known = {f"{PREFIX}_name", f"{PREFIX}_document_name"} | {f"{PREFIX}_{c}" for c in ("occupancystatus", "insurancereviewstatus", "verificationmethod")}
    for t in used_tables:
        known |= {f"{PREFIX}_{c}" for c in cols[t]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    used = set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script)) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    assert "—" not in page and "—" not in rules
    assert 'id="insurance"' in open(os.path.join(web, "guides.html")).read()
    print("OK: Insurance verification rules give the expected statuses, checks and dates for each worked example; "
          "the page is in the app, the hub leads to it, and it uses only real columns and choices.")


if __name__ == "__main__":
    main()
