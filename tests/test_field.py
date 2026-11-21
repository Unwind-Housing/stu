"""Offline test: the Stu in the wild page's rules (webresources/field.js) run in Node on worked examples, and the page is
checked against the schema. Skipped with a message if Node isn't installed."""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert");
const F = require(process.argv[process.argv.length - 1]);
const today = "2026-11-18";

// ---- where one home stands: red until a walk-by is submitted, amber while one is saved, green for 12 months after
assert.deepStrictEqual(F.stand([], 12, today), { state: "todo", draft: "", last: "" }, "never walked");
assert.deepStrictEqual(F.stand(undefined, 12, today), { state: "todo", draft: "", last: "" });
assert.deepStrictEqual(F.stand([{ id: "w1", date: "2026-11-18", status: "Draft" }], 12, today), { state: "started", draft: "w1", last: "" }, "saved, not submitted");
assert.deepStrictEqual(F.stand([{ id: "w1", date: "2026-11-18", status: "Submitted" }], 12, today), { state: "done", draft: "", last: "2026-11-18" }, "submitted today");
assert.strictEqual(F.stand([{ id: "w1", date: "2025-11-19", status: "Submitted" }], 12, today).state, "done", "a day short of a year ago");
assert.deepStrictEqual(F.stand([{ id: "w1", date: "2025-11-18", status: "Submitted" }], 12, today), { state: "todo", draft: "", last: "2025-11-18" }, "a year ago today: red again");
assert.strictEqual(F.stand([{ id: "w1", date: "2026-06-01", status: "Submitted" }], 3, today).state, "todo", "the setting: every 3 months");
assert.deepStrictEqual(F.stand([{ id: "w1", date: "2026-03-01", status: "Submitted" }, { id: "w2", date: "2026-11-17", status: "Draft" }, { id: "w0", date: "2024-01-01", status: "Submitted" }], 12, today),
                       { state: "started", draft: "w2", last: "2026-03-01" }, "a draft shows even on a home that was done");
assert.strictEqual(F.months(""), 12); assert.strictEqual(F.months("6"), 6); assert.strictEqual(F.months("0"), 12); assert.strictEqual(F.months("often"), 12);

// ---- the neighborhoods: a card for every home, empty ones too
const props = [{ id: "p1", name: "103 Maple Ct", neighborhood: "Maple Court", status: "Owner-occupied" },
               { id: "p2", name: "1010 Maple Ct", neighborhood: "Maple Court", status: "Owner-occupied" },
               { id: "p3", name: "101 Maple Ct", neighborhood: "Maple Court", status: "Vacant" },
               { id: "p4", name: "40 Harbor Row, Unit 10", neighborhood: "Harbor Row", status: "For sale" },
               { id: "p5", name: "40 Harbor Row, Unit 2", neighborhood: "Harbor Row", status: "Owner-occupied" },
               { id: "p6", name: "9 Elm Ct", neighborhood: "", status: "Owner-occupied" },
               { id: "p7", name: "Lot 12", neighborhood: "Maple Court", status: "Prospective acquisition" },
               { id: "p8", name: "2 Old Rd", neighborhood: "Maple Court", status: "Left program" }];
const occ = [{ id: "o1", property: "p1", household: "Rivera" }, { id: "o2", property: "p2", household: "Chen" }, { id: "o5", property: "p5", household: "Okafor" }, { id: "o6", property: "p6", household: "Lee" }];
const walks = [{ id: "w1", property: "p1", date: "2026-11-10", status: "Submitted" }, { id: "w2", property: "p3", date: "2026-11-18", status: "Draft" },
               { id: "w3", property: "p5", date: "2025-01-05", status: "Submitted" }, { id: "w4", property: "p4", date: "2026-10-01", status: "Submitted" }];
const hoods = F.neighborhoods(props, occ, walks, {}, today);
assert.deepStrictEqual(hoods.map(h => [h.name, h.total, h.done, h.started]), [["Harbor Row", 2, 1, 0], ["Maple Court", 3, 1, 1], ["No neighborhood", 1, 0, 0]],
                       "by name, homes with no neighborhood last; not yet acquired and left the program get no card");
assert.deepStrictEqual(hoods[1].homes.map(h => [h.name, h.household, h.occupancy, h.state]),
                       [["101 Maple Ct", "", "", "started"], ["103 Maple Ct", "Rivera", "o1", "done"], ["1010 Maple Ct", "Chen", "o2", "todo"]], "in address order; an empty home has a card and no occupancy");
assert.deepStrictEqual(hoods[0].homes.map(h => [h.name, h.state, h.last]), [["40 Harbor Row, Unit 2", "todo", "2025-01-05"], ["40 Harbor Row, Unit 10", "done", "2026-10-01"]], "Unit 2 before Unit 10; an empty home can be done");
assert.strictEqual(hoods[1].homes[0].draft, "w2");
assert.deepStrictEqual(F.neighborhoods([], [], [], {}, today), []);
assert.strictEqual(F.neighborhoods(props, occ, walks, { WalkByMonths: "1" }, today)[0].done, 0, "the setting changes what counts as done");

// ---- saving and submitting
assert.deepStrictEqual(F.problems({ notes: "", followUp: false, due: "", photos: 0 }, true, today), [], "a walk-by with nothing to say can be submitted");
assert.deepStrictEqual(F.problems({ notes: "", followUp: true, due: "", photos: 0 }, false, today), [], "Save keeps anything");
assert.ok(F.problems({ notes: " ", followUp: true, due: today }, true, today)[0].includes("notes")); assert.ok(F.problems({ notes: "Gutter down", followUp: true, due: "" }, true, today)[0].includes("due"));
assert.ok(F.problems({ notes: "Gutter down", followUp: true, due: "2026-11-17" }, true, today)[0].includes("past"));
assert.deepStrictEqual(F.problems({ notes: "Gutter down", followUp: true, due: today, photos: 3 }, true, today), [], "due the day of the walk-by");
assert.ok(F.problems({ photos: 13 }, false, today)[0].includes("12 photos"));
assert.strictEqual(F.recordName(today, "105 Maple Ct"), "2026-11-18, 105 Maple Ct");
assert.strictEqual(F.followUpName("  \nGutter is coming off the north side.\nAlso the fence.", "105 Maple Ct"), "Gutter is coming off the north side.");
assert.strictEqual(F.followUpName("", "105 Maple Ct"), "Follow up on the walk-by at 105 Maple Ct"); assert.ok(F.followUpName("x".repeat(300)).length === 100);

// ---- photos are shrunk to 1600 on the longer side
assert.deepStrictEqual(F.fit(4032, 3024), { w: 1600, h: 1200 }); assert.deepStrictEqual(F.fit(3024, 4032), { w: 1200, h: 1600 });
assert.deepStrictEqual(F.fit(800, 600), { w: 800, h: 600 }, "a small one is left alone"); assert.deepStrictEqual(F.fit(0, 0), { w: 1, h: 1 });

// ---- the history on the property form, and the record a form hands its page
assert.deepStrictEqual(F.history([{ id: "a", date: "2025-03-01", status: "Submitted" }, { id: "b", date: "2026-11-18", status: "Submitted" }, { id: "c", date: "2026-11-18", status: "Draft" }, { id: "d", date: "", status: "Submitted" }]).map(w => w.id),
                       ["c", "b", "a", "d"], "newest first, a draft before a submitted one on the same day, no date last");
assert.deepStrictEqual(F.history(undefined), []);
assert.deepStrictEqual(F.formRecord("?id=%7b1A2B3C4D-0000-1111-2222-333344445555%7d&typename=clt_walkby&type=10123"), { id: "1a2b3c4d-0000-1111-2222-333344445555", table: "clt_walkby" });
assert.deepStrictEqual(F.formRecord("?typename=clt_property&id=1a2b3c4d-0000-1111-2222-333344445555"), { id: "1a2b3c4d-0000-1111-2222-333344445555", table: "clt_property" });
assert.deepStrictEqual(F.formRecord("?typename=clt_walkby"), { id: "", table: "clt_walkby" }, "a record that isn't saved yet has no id");
assert.deepStrictEqual(F.formRecord("?id=x' or 1 eq 1&typename=clt_walkby").id, "", "only a real id is ever put in a query");
assert.deepStrictEqual(F.formRecord(""), { id: "", table: "" });

// ---- on a phone Stu opens on this page, once a session
assert.strictEqual(F.startHere(3, 1200, null), true, "the app says phone"); assert.strictEqual(F.startHere(1, 390, null), false, "the app says desktop, whatever the width");
assert.strictEqual(F.startHere(2, 390, null), false, "a tablet gets the Dashboard"); assert.strictEqual(F.startHere("", 390, null), true, "outside the app: a narrow screen");
assert.strictEqual(F.startHere(undefined, 1440, null), false); assert.strictEqual(F.startHere(3, 390, "1"), false, "only the first time: after that the Dashboard is a tap away");
assert.strictEqual(F.startHere("", 0, null), false);
process.stdout.write(JSON.stringify({ draft: F.DRAFT, submitted: F.SUBMITTED, noCard: F.NO_CARD }));
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the Stu in the wild page's rules weren't run. Install Node to run this test.")
        return
    import json
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "field.js")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Field rules failed:\n" + r.stdout + r.stderr)
    out = json.loads(r.stdout.strip().splitlines()[-1])

    import app_spec as core
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES, ENVIRONMENT_VARIABLES, RETIRED
    PREFIX = "clt"
    tables = {t["name"]: t for t in TABLES}
    cols = {t: {c["name"]: c for c in tables[t]["columns"]} for t in tables}
    rules = open(os.path.join(web, "field.js")).read()
    page = open(os.path.join(web, "field.html")).read()
    # the statuses and the homes left out are real choices
    assert [out["draft"], out["submitted"]] == CHOICES["walkbystatus"][1] and cols["walkby"]["status"]["choice"] == "walkbystatus"
    assert cols["walkby"]["status"]["default"] == "Submitted", "a walk-by typed at a desk is a finished one"
    assert set(out["noCard"]) <= set(CHOICES["propertystatus"][1])
    assert any(v["name"] == "WalkByMonths" for v in ENVIRONMENT_VARIABLES) and "WalkByMonths" in rules
    # a walk-by belongs to the property, so an empty home can have one; the occupancy and a follow-up's links are optional
    look = {(l[0], l[1]): l for l in LOOKUPS}
    assert look[("walkby", "property")][2] == "property" and look[("walkby", "property")][5] is True
    assert look[("walkby", "occupancy")][4:] == ("RemoveLink", False) and look[("followup", "occupancy")][4:] == ("RemoveLink", False)
    assert look[("followup", "property")][5] is False and look[("followup", "walkby")][4:] == ("RemoveLink", False)
    assert look[("walkbyphoto", "walkby")][4:] == ("Cascade", True) and cols["walkbyphoto"]["photo"]["kind"] == "file"
    assert cols["property"]["lastwalkby"]["kind"] == "date" and "lastwalkby" not in cols["occupancy"] and ("occupancy", "lastwalkby") in RETIRED["columns"]
    assert {"followupneeded", "followupdue", "notes", "date"} <= set(cols["walkby"]) and "result" not in cols["walkby"]
    # in the app: under Start here, in the core app and Stu; the property shows its walk-bys and follow-ups
    assert core.PAGES["field"] == ("Stu in the wild", "clt_/pages/field.html") and "page:field" in dict(core.NAVIGATION)["Start here"]
    for res in ("clt_/pages/field.html", "clt_/pages/field.js"):
        assert res in core.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    prop_form, walk_form = str(core.FORMS["property"]), str(core.FORMS["walkby"])
    assert "clt_property_walkby_property" in prop_form and "clt_property_followup_property" in prop_form and "lastwalkby" in prop_form
    assert "'property'" in walk_form and "walkbyphoto" in core.FORMS
    # at a desk: the walk-by form shows its photos, and the property form shows every walk-by with its photos
    for form in (prop_form, walk_form):
        assert "clt_/pages/walkbys.html" in form and "'page': True" in form
    assert "clt_/pages/walkbys.html" in core.WEB_RESOURCES and "clt_/pages/walkbys.html" in stu.WEB_RESOURCES
    viewer = open(os.path.join(web, "walkbys.html")).read()
    vscript = re.findall(r"<script>(.*?)</script>", viewer, re.S)[-1]
    p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=vscript, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-600:]
    assert "F.formRecord(location.search)" in vscript and "F.history(" in vscript and "P.patch" not in vscript and "P.create" not in vscript and "P.del" not in vscript, "the viewer only reads"
    dash = open(os.path.join(web, "overview.html")).read()
    assert dash.index('src="pages.js"') < dash.index('src="field.js"') < dash.index("CLTField.startHere(") and 'location.replace("field.html")' in dash and "sessionStorage" in dash
    css = open(os.path.join(web, "pages.css")).read()
    assert "[hidden] { display: none !important; }" in css and 'href="pages.css"' in page and 'href="pages.css"' in viewer, "a hidden Save and Submit bar, or photo viewer, must not show"
    assert 'id="bar" hidden' in page and 'if (busy || !home || view !== "home") return;' in page, "Save and Submit only exist for the home that is open"
    assert viewer.index('src="pages.js"') < viewer.index('src="field.js"') and "—" not in viewer
    assert "'property'" in str(core.FORMS["followup"])
    # the page: phone first, camera and library, Save and Submit
    assert "width=device-width" in page and 'capture="environment"' in page and 'id="library"' in page and "multiple" in page
    for piece in ('id="save"', 'id="submit"', 'id="follow"', 'id="due"', 'id="notes"', 'data-view="hoods"', 'data-view="homes"', 'data-view="home"',
                  "F.neighborhoods(", "F.problems(", "F.fit(", "F.followUpName(", "F.recordName("):
        assert piece in page, piece
    assert page.index('src="pages.js"') < page.index('src="field.js"') < page.index("CLTField")
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    # submitting is one change set; a walk-by is always written as a draft first
    assert script.count("P.batch(") == 1 and "ch.walkbystatus[F.DRAFT]" in script and "ch.walkbystatus[F.SUBMITTED]" in script
    # every clt_ name is real
    used_tables = ("property", "occupancy", "walkby", "walkbyphoto", "followup")
    known = {f"{PREFIX}_name"} | {f"{PREFIX}_{c}" for c in ("occupancystatus", "walkbystatus", "followupstatus")}
    for t in used_tables:
        known |= {f"{PREFIX}_{c}" for c in cols[t]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    used = (set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script)) | set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", vscript))) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    assert "—" not in page and "—" not in rules
    assert 'id="field"' in open(os.path.join(web, "guides.html")).read()
    print("OK: Field rules give the expected colors, neighborhoods, checks and photo sizes for each worked example; "
          "the page is in the app and uses only real columns and choices.")


if __name__ == "__main__":
    main()
