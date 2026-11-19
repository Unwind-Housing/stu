"""Offline test: a project's journey (webresources/journey.js). The rules that say where a project picks up run in
Node on worked examples, and the project pages are checked for the row of steps. Skipped with a message if Node
isn't installed."""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert");
const J = require(process.argv[process.argv.length - 1]);

assert.deepStrictEqual(J.STEPS.map(s => s.key), ["assign", "prescreen", "selection", "invite", "certify"]);
assert.strictEqual(J.step("prescreen").page, "clt_/pages/prescreen.html"); assert.strictEqual(J.step("nope"), null);

// ---- where a project picks up
const next = f => { const n = J.next(f); return n && n.key; };
assert.strictEqual(next({ status: "Planning", applications: 0 }), "assign", "a new project: add people first");
assert.strictEqual(next({ status: "Accepting applications", applications: 12, untested: 3, round: "" }), "prescreen");
assert.ok(J.next({ status: "Planning", applications: 12, untested: 3, round: "" }).why.includes("3 still to pre-screen"));
assert.strictEqual(next({ status: "Accepting applications", applications: 12, untested: 0, round: "" }), "selection", "everyone tested: on to buyer selection");
for (const r of ["Open", "Pools locked", "Drawn"]) assert.strictEqual(next({ status: "Selection", applications: 12, untested: 2, round: r }), "selection", "a round under way: " + r);
assert.strictEqual(next({ status: "Selection", applications: 12, round: "Certified", invited: 0 }), "invite", "results certified, nobody invited yet");
assert.strictEqual(next({ status: "Certifying", applications: 12, round: "Certified", invited: 4 }), "certify");
assert.ok(J.next({ status: "Certifying", applications: 12, round: "Closed", invited: 1 }).why.startsWith("1 household invited"));
assert.strictEqual(J.next({ status: "Closed", applications: 12 }), null, "a closed project has no next step");
assert.strictEqual(next({}), "assign"); assert.strictEqual(next(undefined), "assign");
assert.strictEqual(J.next({ applications: 1, untested: 1 }).why, "1 screener, 1 still to pre-screen");

// ---- the projects in progress, for the hub: closed ones are left out; the newest round is the one that counts
const rows = J.inProgress(
  [{ id: "p2", name: "Maple Court", status: "Selection" }, { id: "p1", name: "12 Pine St resale", status: "Planning" },
   { id: "p3", name: "Old project", status: "Closed" }, { id: "p4", name: "alder Row", status: "Planning" }],
  [{ project: "p1", tested: true }, { project: "p1", tested: false }, { project: "p2", tested: true }, { project: "", tested: false }, { project: "p3", tested: true }],
  [{ project: "p2", status: "Closed", created: "2025-01-01T00:00:00Z" }, { project: "p2", status: "Certified", created: "2026-10-01T00:00:00Z" }],
  [{ project: "p2" }, { project: "p2" }, { project: undefined }]);
assert.deepStrictEqual(rows.map(r => [r.id, r.applications, r.next.key]), [["p1", 2, "prescreen"], ["p4", 0, "assign"], ["p2", 1, "certify"]], "by name, whatever the capitals");
assert.ok(rows[2].next.why.startsWith("2 households invited"));
assert.deepStrictEqual(J.inProgress([], [], [], []), []); assert.deepStrictEqual(J.inProgress(), []);

// ---- one project's progress, for its workflow page: each step done, next or waiting, with a few words on where it stands
const t = f => J.track(f).map(s => [s.key, s.state]);
assert.deepStrictEqual(t({ status: "Planning", applications: 0 }), [["assign", "next"], ["prescreen", "waiting"], ["selection", "waiting"], ["invite", "waiting"], ["certify", "waiting"]]);
assert.deepStrictEqual(t({ status: "Planning", applications: 12, untested: 3 }).slice(0, 3), [["assign", "done"], ["prescreen", "next"], ["selection", "waiting"]]);
assert.deepStrictEqual(t({ status: "Selection", applications: 12, untested: 0, round: "Drawn" }).slice(0, 4), [["assign", "done"], ["prescreen", "done"], ["selection", "next"], ["invite", "waiting"]]);
assert.deepStrictEqual(t({ status: "Certifying", applications: 12, untested: 0, round: "Certified", invited: 4, certified: 1 }),
                       [["assign", "done"], ["prescreen", "done"], ["selection", "done"], ["invite", "done"], ["certify", "next"]]);
assert.ok(J.track({ status: "Closed", applications: 12, untested: 0, round: "Closed", invited: 4, certified: 2 }).every(s => s.state === "done"), "a closed project has nothing next");
const lines = J.track({ status: "Selection", applications: 12, untested: 0, eligible: 9, round: "Pools locked", invited: 0, certified: 0 }).map(s => s.line);
assert.deepStrictEqual(lines, ["12 screeners in the project", "All 12 pre-screened, 9 eligible for selection", "Under way: pools locked", "Nobody invited yet", "Nobody certified yet"]);
assert.strictEqual(J.track({ applications: 5, untested: 2 })[1].line, "2 of 5 still to pre-screen"); assert.strictEqual(J.track({})[1].line, "Nothing to test yet");
assert.strictEqual(J.track({ applications: 5, round: "Certified", invited: 1, certified: 1 })[4].line, "1 household certified");
// every project for the workflow page's list: closed ones last, with the figures the steps need
const all = J.standing([{ id: "p3", name: "Old project", status: "Closed" }, { id: "p1", name: "12 Pine St resale", status: "Planning" }],
                       [{ project: "p1", tested: true, eligible: true }, { project: "p1", tested: true, eligible: false }], [], [], [{ project: "p1" }, { project: "p3" }]);
assert.deepStrictEqual(all.map(p => [p.id, p.next && p.next.key]), [["p1", "selection"], ["p3", null]]);
assert.deepStrictEqual(all[0].facts, { status: "Planning", applications: 2, untested: 0, eligible: 1, round: "", invited: 0, certified: 1 });
assert.strictEqual(J.OVERVIEW, "clt_/pages/project.html");
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the project journey rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "journey.js")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Project journey rules failed:\n" + r.stdout + r.stderr)

    import app_spec_intake as intake
    import app_spec_stu as stu
    from schema import CHOICES
    rules = open(os.path.join(web, "journey.js")).read()
    assert "clt_/pages/journey.js" in intake.WEB_RESOURCES and "clt_/pages/journey.js" in stu.WEB_RESOURCES
    # every step is a real page in the app, in the order the menu has them
    pages = {wr: key for key, (label, wr) in intake.PAGES.items()}
    keys = re.findall(r'key: "(\w+)",\s+label: "[^"]+",\s+page: "([^"]+)"', rules)
    assert [pages[wr] for k, wr in keys] == [k for k, wr in keys] == ["assign", "prescreen", "selection", "invite", "certify"]
    nav = [t[5:] for t in dict(intake.NAVIGATION)["Projects"] if t.startswith("page:")]
    assert nav == ["newproject", "workflow"] + [k for k, wr in keys]
    assert intake.PAGES["workflow"] == ("Project workflow", "clt_/pages/project.html") and "clt_/pages/project.html" in stu.WEB_RESOURCES
    # the workflow page: every project in progress, then one project's steps with the way into each
    flow = open(os.path.join(web, "project.html")).read()
    assert flow.index('src="pages.js"') < flow.index('src="journey.js"') < flow.index("CLTJourney")
    for piece in ('id="landing"', 'id="track"', "J.standing(", "J.track(", 'get("data")', "Do this next", "data-step=", "data-open=", "clt_invitedon ne null", '"Eligible for selection"', '"Certified"'):
        assert piece in flow, piece
    assert "Eligible for selection" in CHOICES["prescreenresult"][1] and "Certified" in CHOICES["certificationstatus"][1]
    p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=re.findall(r"<script>(.*?)</script>", flow, re.S)[-1], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-600:]
    assert 'data-step="overview"' in rules and "—" not in flow, "each step's row of steps has a way back to the workflow page"
    # the statuses the rules name are real
    for s in ("Open", "Pools locked", "Drawn"):
        assert s in CHOICES["roundstatus"][1] and f'"{s}"' in rules, s
    assert "Closed" in CHOICES["projectstatus"][1]
    # each project page shows the row of steps and carries its project along; it takes a project from the address
    for key in [k for k, wr in keys]:
        page = open(os.path.join(web, key + ".html")).read()
        assert page.index('src="pages.js"') < page.index('src="journey.js"') < page.index('id="journey"') < page.index(f'CLTJourney.bar(document.getElementById("journey"), "{key}"'), key
        assert 'id="project"' in page and 'get("data")' in page, key
    # New project hands over to the first step; the hub lists the projects in progress
    new = open(os.path.join(web, "newproject.html")).read()
    assert 'webresourceName: "clt_/pages/project.html", data: rec.clt_projectid' in new and "P.openRecord(\"clt_project\", rec.clt_projectid);\n      //" not in new
    hub = open(os.path.join(web, "intake.html")).read()
    for piece in ('id="inprogress"', "data-workflow=", "J.OVERVIEW", "J.inProgress(", 'src="journey.js"', "clt_prescreenresult", "clt_invitedon ne null", "Continue: "):
        assert piece in hub, piece
    for src in (rules,):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    assert "—" not in rules and "—" not in hub
    print("OK: the project journey rules give the expected next step for each worked example; every project page "
          "shows the steps, New project hands over to the workflow page, and the hub lists the projects in progress.")


if __name__ == "__main__":
    main()
