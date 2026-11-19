"""Offline test: Add to a project (webresources/assign.js). The rules for who can join a project, and whether by
moving or as a copy, run in Node on worked examples, and the copy is checked against the schema. Skipped with a
message if Node isn't installed."""
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
const how = (app, entries, inTarget) => A.stand(app, entries, "p2", inTarget).how;
const free = { id: "a1", project: "", uniqueId: "", household: "h1" };
const open = { id: "a2", project: "p1", projectName: "Maple Court", projectStatus: "Accepting applications", uniqueId: "", household: "h2" };
const locked = { id: "a3", project: "p1", projectName: "Maple Court", projectStatus: "Selection", uniqueId: "ID-0007", household: "h3" };

// ---- not locked: it simply moves, as before
assert.strictEqual(how(free, []), "move"); assert.strictEqual(A.stand(free, [], "p2").why, "");
assert.strictEqual(how(open, []), "move"); assert.strictEqual(A.stand(open, [], "p2").why, "Moves from Maple Court");
assert.strictEqual(how({ ...open, project: "p2" }, []), "here");

// ---- locked to a project: on a waitlist and not invited, it joins another project as a copy and keeps its place
assert.strictEqual(how(locked, ["Waitlist"]), "copy");
assert.ok(A.stand(locked, ["Waitlist"], "p2").why.startsWith("On the waitlist in Maple Court, not invited"));
assert.strictEqual(how(locked, ["Waitlist", "Waitlist"]), "copy", "on two home sizes' lists");
assert.strictEqual(how(locked, []), "copy", "not on a list: not eligible there, or the lists aren't built yet");
for (const s of ["Declined", "Unresponsive", "Ineligible", "Removed", "Withdrawn"]) assert.strictEqual(how(locked, [s]), "copy", s + ": out of the running there");
// invited, or further along: it stays where it is until that is settled
for (const s of A.IN_PROCESS) assert.strictEqual(how(locked, ["Waitlist", s]), "held", s);
assert.deepStrictEqual(A.IN_PROCESS, ["Invited", "Application received", "Approved", "Offered", "Accepted"]);
assert.strictEqual(A.stand(locked, ["Invited"], "p2").why, "Invited in Maple Court: stays there");
// ... unless its project is closed
assert.strictEqual(how({ ...locked, projectStatus: "Closed" }, ["Invited"]), "copy");
// never twice in one project: the same application, or another one from the same household (a copy made earlier)
assert.strictEqual(how({ ...locked, project: "p2" }, ["Waitlist"]), "here");
assert.strictEqual(how(locked, ["Waitlist"], { h3: true }), "here"); assert.strictEqual(how(free, [], { h1: true }), "here");
assert.strictEqual(how(locked, ["Waitlist"], { h9: true }), "copy");

// ---- the copy: the screener answers and links, a fresh start in the new project, and its own entry ID
assert.strictEqual(A.copyEntryId("1234", "9F8E7D6C-0000-1111-2222-333344445555"), "1234~9F8E7D6C"); assert.ok(A.copyEntryId("x".repeat(60), "p").length <= 50);
const row = { clt_name: "Rivera", clt_adults: 2, clt_children: 0, clt_firsttimebuyer: false, clt_homesizes: "768270001,768270002", clt_accommodation: "", clt_statedannualincome: null,
              clt_firstsubmittedon: "2026-03-01T17:00:00Z", clt_screenerentryid: "1234", clt_uniqueid: "ID-0007", clt_prescreenresult: 768270000, clt_stage: 768270005,
              _clt_household_value: "h3", _clt_county_value: "c1", _clt_sourceform_value: null, _clt_project_value: "p1" };
const body = A.copyBody(row, "p2", { clt_project: "clt_projects", clt_household: "clt_households", clt_listitem: "clt_listitems", clt_sourceform: "clt_sourceforms" }, 768270000);
assert.deepStrictEqual(body, { clt_name: "Rivera", clt_firstsubmittedon: "2026-03-01T17:00:00Z", clt_firsttimebuyer: false, clt_adults: 2, clt_children: 0, clt_homesizes: "768270001,768270002",
  "clt_household@odata.bind": "/clt_households(h3)", "clt_county@odata.bind": "/clt_listitems(c1)", "clt_project@odata.bind": "/clt_projects(p2)",
  clt_screenerentryid: "1234~p2", clt_stage: 768270000 }, "a false or 0 answer is kept, a blank one is left out; nothing the first project decided comes along");

// ---- counting households: a household in two projects is two applications and one household; the original stands for it
assert.strictEqual(A.isCopy("1234~p2"), true); assert.strictEqual(A.isCopy("1234"), false); assert.strictEqual(A.isCopy(null), false);
const pool = [{ id: 1, household: "h1", entryId: "10~p2" }, { id: 2, household: "h2", entryId: "11" }, { id: 3, household: "h1", entryId: "10" }, { id: 4, household: "", entryId: "12" },
              { id: 5, household: null, entryId: "13" }, { id: 6, household: "h3", entryId: "14~p2" }, { id: 7, household: "h3", entryId: "14~p3" }, { id: 8, household: "h2", entryId: "15" }];
assert.deepStrictEqual(A.onePerHousehold(pool).map(a => a.id), [2, 3, 4, 5, 6], "the original, else the first; one with no household counts on its own");
assert.deepStrictEqual(A.onePerHousehold([]), []); assert.deepStrictEqual(A.onePerHousehold(), []);

// ---- what the confirmation says
assert.strictEqual(A.confirmText([{ how: "move" }], "Elm Row"), "Add 1 application to Elm Row?");
const text = A.confirmText([{ how: "move", moving: true }, { how: "move" }, { how: "copy" }, { how: "copy" }], "Elm Row");
assert.ok(text.startsWith("Add 4 applications to Elm Row? 1 is in another project now and will move. 2 are locked to another project and will join as a copy"));
process.stdout.write(JSON.stringify({ copied: A.COPIED, links: A.LINKS, busy: A.IN_PROCESS }));
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the Add to a project rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "assign.js")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Add to a project rules failed:\n" + r.stdout + r.stderr)
    out = json.loads(r.stdout.strip().splitlines()[-1])

    import app_spec_intake as intake
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES, KEYS
    cols = {c["name"]: c for c in {t["name"]: t for t in TABLES}["application"]["columns"]}
    # every copied column is a real one that can be written (never a formula or a file), and none is a project's own decision
    for c in out["copied"]:
        name = c[4:]
        assert c == "clt_name" or (name in cols and cols[name]["kind"] not in ("fx", "file", "autonum")), c
    for kept_back in ("uniqueid", "answersfrozenon", "prescreenresult", "prescreennotes", "prescreensizes", "prescreenedon", "prescreenoverridden", "stage", "invitelink",
                      "fullappentryid", "fullappsubmitted", "reviewnotes", "decisiondate", "recordnumber", "screenerentryid"):
        assert "clt_" + kept_back not in out["copied"], kept_back
    # every screener answer is copied: the columns between the screener's first and the full application's first
    names = list(cols)
    screener = [n for n in names[names.index("localtie"):names.index("fullappentryid")] if cols[n]["kind"] != "fx"]
    assert not [n for n in screener if "clt_" + n not in out["copied"]], [n for n in screener if "clt_" + n not in out["copied"]]
    # the links are real lookups on the application
    real = {(col, parent) for child, col, parent, *_ in LOOKUPS if child == "application"}
    assert {(l[0][4:], l[1][4:]) for l in out["links"]} == real - {("project", "project")}
    assert ("application", "screenerentryid", ["screenerentryid"]) in KEYS, "each application has its own entry ID, which is why a copy gets a new one"
    assert set(out["busy"]) <= set(CHOICES["entrystatus"][1]) and "Waitlist" in CHOICES["entrystatus"][1] and "Screener submitted" in CHOICES["applicationstage"][1]
    assert "clt_/pages/assign.js" in intake.WEB_RESOURCES and "clt_/pages/assign.js" in stu.WEB_RESOURCES
    page = open(os.path.join(web, "assign.html")).read()
    rules = open(os.path.join(web, "assign.js")).read()
    assert page.index('src="pages.js"') < page.index('src="assign.js"') < page.index("CLTAssign")
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for piece in ("A.stand(", "A.copyBody(", "A.confirmText(", "clt_applicationstage", "_clt_household_value", 'P.create("clt_applications"'):
        assert piece in script, piece
    assert "locked(a)" not in script
    hub = open(os.path.join(web, "intake.html")).read()
    assert hub.index('src="assign.js"') < hub.index("CLTAssign.onePerHousehold(") and "Households screened" in hub and 'v === "all" ? people(apps)' in hub
    assert "_clt_household_value" in hub and "clt_screenerentryid" in hub
    for src in (script, rules):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    assert "—" not in page and "—" not in rules
    print("OK: Add to a project rules give the expected move, copy or stay for each worked example; a copy carries "
          "every screener answer and nothing a project decided, using only real columns and lookups.")


if __name__ == "__main__":
    main()
