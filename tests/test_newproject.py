"""Offline test: the New project guided page. Its rules (webresources/newproject.js) run in Node on worked
examples; the page is checked against the schema. Skipped with a message if Node isn't installed."""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert");
const N = require(process.argv[process.argv.length - 1]);
const choices = { projecttype: { "New construction sale": 1, "Resale": 2 }, selectionmethod: { "Lottery": 10, "First come first served": 11 },
                  projectstatus: { "Planning": 20 }, rulechoice: { "Required": 30, "Not required": 31 },
                  creditrange: { "580 - 669": 41, "670 - 739": 42 }, projecthomestatus: { "Available": 50 } };
// Two income bands: households up to 65% of AMI can borrow at 5%, everyone else at 7.4%. 3% down, 30 years.
const base = () => ({ name: " Maple Court phase 1 ", type: "New construction sale", method: "Lottery", opens: "2027-01-05", closes: "2027-02-05",
  homes: [{ propertyId: "p-1", name: "12 Pine St", bedrooms: 2 }, { propertyId: "p-2", name: "14 Pine St", bedrooms: "3" },
          { propertyId: "p-3", name: "16 Pine St", bedrooms: 2 }, { propertyId: "p-4", name: "18 Pine St", bedrooms: 5 }],
  finance: { down: "3", term: "", perBandPrice: false },
  bands: [{ maxami: "65", rate: "5" }, { maxami: "", rate: "7.4" }],
  // 2 bedrooms: everything filled in. 3 bedrooms: no price. 4+: nothing typed.
  costs: { 2: { price: "$245,000", taxes: 180, insurance: "95", hoa: "150", lease: 75, reserve: "100" },
           3: { price: "", taxes: "210", hoa: 150 }, 4: {} },
  rules: { maxami: "80", incomebuffer: "5", firsttimebuyer: "Required", mincreditrange: "670 - 739", minaffordabilitycheck: true },
  priorities: { 2: { 2: 1, 3: 1, 4: 1, 1: 2 }, 3: { 3: 1 } } });
const one = () => { const s = base(); s.bands = [{ maxami: "", rate: "6" }]; s.finance.down = ""; s.costs[2].price = "100000"; return s; };

// sizes: 5 bedrooms counts as "4+ bedrooms"; the list is smallest first with no repeats
assert.deepStrictEqual(N.sizesFor(base()), [2, 3, 4]);
assert.strictEqual(N.sizeName(4), "4+ bedrooms"); assert.strictEqual(N.sizeOf(0), 0);
assert.strictEqual(N.num("$1,850.50"), 1850.5); assert.strictEqual(N.num("7.4%"), 7.4); assert.strictEqual(N.num(""), null); assert.ok(isNaN(N.num("abc")));

// the mortgage payment: the standard formula. $100,000 at 6% for 30 years is $599.55 a month.
assert.strictEqual(N.payment(100000, 0, 6, 30), 599.55);
assert.strictEqual(N.payment(100000, "", 6, ""), 599.55, "blank down payment is 0, blank term is 30 years");
assert.strictEqual(N.payment(245000, 3, 5, 30), 1275.76);     // loan $237,650
assert.strictEqual(N.payment(245000, 3, 7.4, 30), 1645.44);
assert.strictEqual(N.payment(120000, 0, 0, 30), 333.33, "a 0% loan is the loan divided by the months");
assert.strictEqual(N.payment(200000, 20, 6, 15), 1350.17);
assert.strictEqual(N.payment("", 3, 5, 30), null); assert.strictEqual(N.payment(245000, 3, "", 30), null);

// bands are named from where they stop
assert.strictEqual(N.bandName(one(), 0), "All buyers");
assert.strictEqual(N.bandName(base(), 0), "Up to 65% of AMI"); assert.strictEqual(N.bandName(base(), 1), "Above 65% of AMI");
// what a home costs a month in each band: the mortgage payment plus the costs every buyer pays
assert.strictEqual(N.sharedCost(base(), 2), 600); assert.strictEqual(N.sharedCost(base(), 4), null);
assert.deepStrictEqual(N.bandCost(base(), 2, 0), { price: 245000, pi: 1275.76, shared: 600, total: 1875.76 });
assert.deepStrictEqual(N.bandCost(base(), 2, 1), { price: 245000, pi: 1645.44, shared: 600, total: 2245.44 });
assert.deepStrictEqual(N.bandCost(base(), 3, 0), { price: null, pi: null, shared: 360, total: null });
assert.deepStrictEqual(N.bandCost(one(), 2, 0), { price: 100000, pi: 599.55, shared: 600, total: 1199.55 });

// a complete project has no errors; what's missing shows as warnings that don't stop anyone
let r = N.check(base());
assert.deepStrictEqual(r.errors, []);
for (const t of ["3 bedrooms homes have no sale price yet", "4+ bedrooms homes have no sale price yet", "No household sizes are chosen for 4+ bedrooms homes"])
  assert.ok(r.warnings.some(w => w.includes(t)), t + " not in " + r.warnings.join(" | "));
assert.strictEqual(r.warnings.length, 3, r.warnings.join(" | "));

// step 1
let s = base(); s.name = "  "; s.type = ""; s.method = "Raffle"; s.closes = "2027-01-01";
r = N.check(s, 1);
assert.strictEqual(r.errors.length, 4, r.errors.join(" | "));
s = base(); s.closes = ""; assert.ok(N.check(s, 1).warnings[0].includes("lottery needs a date"));
s.method = "First come first served"; assert.deepStrictEqual(N.check(s, 1), { errors: [], warnings: [] });
// each step only reports its own problems
s = base(); s.name = ""; assert.deepStrictEqual(N.check(s, 2).errors, []);

// step 2
s = base(); s.homes = []; assert.deepStrictEqual(N.check(s, 2).errors, ["Tick at least one home."]);
s = base(); s.homes[0].bedrooms = ""; s.homes[1].bedrooms = 2.5; s.homes[3].propertyId = "p-1";
r = N.check(s, 2); assert.strictEqual(r.errors.length, 3, r.errors.join(" | "));

// step 3: the loan
s = base(); s.finance.down = "100"; s.finance.term = "0";
r = N.check(s, 3); assert.ok(r.errors[0].includes("Down payment") && r.errors[1].includes("Loan term"), r.errors.join(" | "));
s = base(); s.finance.down = ""; assert.ok(N.check(s, 3).warnings[0].includes("borrows the whole price"));
// step 3: the bands. Every band but the last needs a top, each higher than the one before; rates from 0 to 25
s = base(); s.bands[0].maxami = "";
r = N.check(s, 3); assert.ok(r.errors[0].includes("Income band 1: type the top of the band"), r.errors.join(" | "));
s = base(); s.bands = [{ maxami: "65", rate: "5" }, { maxami: "50", rate: "6" }, { maxami: "", rate: "7.4" }];
r = N.check(s, 3); assert.ok(r.errors[0].includes("Income band 2 must go higher than the band before it (65% of AMI)"), r.errors.join(" | "));
s = base(); s.bands[1].rate = "74";
r = N.check(s, 3); assert.deepStrictEqual(r.errors, ["Above 65% of AMI: the interest rate must be from 0 to 25 percent."]);
s = base(); s.bands[0].rate = "";
assert.ok(N.check(s, 3).warnings.some(w => w.includes("Up to 65% of AMI has no interest rate")));
// step 3: the amounts
s = base(); s.costs[2].price = "lots"; s.costs[2].hoa = "-5"; s.costs[3].taxes = "n/a";
r = N.check(s, 3); assert.strictEqual(r.errors.length, 3, r.errors.join(" | "));
assert.ok(r.errors[0].includes("2 bedrooms: hoa dues") && r.errors[1].includes("2 bedrooms: the sale price") && r.errors[2].includes("3 bedrooms: property taxes"), r.errors.join(" | "));
// a different price for each band: each band's price is asked for by name
s = base(); s.finance.perBandPrice = true; s.costs[2].prices = { 0: "200000" };
r = N.check(s, 3); assert.ok(r.warnings.some(w => w.includes("2 bedrooms homes have no sale price yet (above 65% of ami)")), r.warnings.join(" | "));
assert.ok(!r.warnings.some(w => w.includes("2 bedrooms homes have no sale price yet (up to 65%")));
// step 4
s = base(); s.rules.maxami = "800"; s.rules.debtratiobuffer = "-1"; assert.strictEqual(N.check(s, 4).errors.length, 2);
s = base(); s.rules.minami = "80"; assert.ok(N.check(s, 4).errors[0].includes("lower than max"));
// step 5
s = base(); s.priorities[2][2] = 12; assert.ok(N.check(s, 5).errors[0].includes("2 BR, 2 persons"));

// the starting point: one to two people per bedroom is tier 1, one fewer than the bedrooms is tier 2
assert.deepStrictEqual(N.startingPriorities([0, 1, 2, 3, 4]),
  { 0: { 1: 1, 2: 1 }, 1: { 1: 1, 2: 1 }, 2: { 2: 1, 3: 1, 4: 1, 1: 2 }, 3: { 3: 1, 4: 1, 5: 1, 6: 1, 2: 2 }, 4: { 4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 3: 2 } });

// plan: one record with the bands, homes and priorities inside it
const p = N.plan(base(), choices);
assert.strictEqual(p.clt_name, "Maple Court phase 1");
assert.strictEqual(p.clt_projecttype, 1); assert.strictEqual(p.clt_selectionmethod, 10); assert.strictEqual(p.clt_status, 20);
assert.strictEqual(p.clt_rolling, false); assert.strictEqual(p.clt_applicationopens, "2027-01-05"); assert.strictEqual(p.clt_applicationcloses, "2027-02-05");
assert.strictEqual(p.clt_maxami, 80); assert.strictEqual(p.clt_incomebuffer, 5); assert.strictEqual(p.clt_firsttimebuyer, 30);
assert.strictEqual(p.clt_mincreditrange, 42); assert.strictEqual(p.clt_minaffordabilitycheck, true);
assert.ok(!("clt_minami" in p) && !("clt_localtie" in p) && !("clt_housingratiomax" in p), "blank rules are left out, so the organization's apply");
assert.strictEqual(p.clt_downpaymentpct, 3); assert.strictEqual(p.clt_loantermyears, 30);
// the bands: what the pre-screen reads
assert.deepStrictEqual(p.clt_project_projectband_project, [
  { clt_name: "Up to 65% of AMI", clt_sortorder: 1, clt_maxami: 65, clt_interestrate: 5, clt_price2br: 245000, clt_pi2br: 1275.76, clt_monthlycost2br: 1875.76 },
  { clt_name: "Above 65% of AMI", clt_sortorder: 2, clt_interestrate: 7.4, clt_price2br: 245000, clt_pi2br: 1645.44, clt_monthlycost2br: 2245.44 }]);
// the project's own figure is the highest band's
assert.strictEqual(p.clt_monthlycost2br, 2245.44); assert.ok(!("clt_monthlycost3br" in p) && !("clt_monthlycost4br" in p) && !("clt_monthlycost1br" in p));
const homes = p.clt_project_projecthome_project;
assert.strictEqual(homes.length, 4);
// each home carries its price (the same in both bands) and the costs every buyer pays; the mortgage payment depends on the band, so it isn't on the home
assert.deepStrictEqual(homes[0], { clt_name: "12 Pine St", clt_bedrooms: 2, clt_status: 50, "clt_property@odata.bind": "/clt_properties(p-1)", clt_estimatedprice: 245000,
  clt_propertytaxes: 180, clt_insurance: 95, clt_hoadues: 150, clt_leasefee: 75, clt_reservefee: 100 });
assert.deepStrictEqual(homes[2], { ...homes[0], clt_name: "16 Pine St", "clt_property@odata.bind": "/clt_properties(p-3)" });
assert.deepStrictEqual(homes[1], { clt_name: "14 Pine St", clt_bedrooms: 3, clt_status: 50, "clt_property@odata.bind": "/clt_properties(p-2)", clt_propertytaxes: 210, clt_hoadues: 150 });
assert.deepStrictEqual(Object.keys(homes[3]).sort(), ["clt_bedrooms", "clt_name", "clt_property@odata.bind", "clt_status"]); assert.strictEqual(homes[3].clt_bedrooms, 5);
const prio = p.clt_project_projectpriority_project;
assert.deepStrictEqual(prio.map(x => x.clt_name), ["2 BR, 1 person", "2 BR, 2 persons", "2 BR, 3 persons", "2 BR, 4 persons", "3 BR, 3 persons"]);
assert.deepStrictEqual(prio[0], { clt_name: "2 BR, 1 person", clt_bedrooms: 2, clt_householdsize: 1, clt_tier: 2 });
assert.strictEqual(N.priorityName(0, 2), "Studio, 2 persons"); assert.strictEqual(N.priorityName(4, 5), "4+ BR, 5 persons");

// one band (every buyer gets the same rate): one band record, and the home carries the mortgage payment and the total too
let q = N.plan(one(), choices);
assert.deepStrictEqual(q.clt_project_projectband_project, [{ clt_name: "All buyers", clt_sortorder: 1, clt_interestrate: 6, clt_price2br: 100000, clt_pi2br: 599.55, clt_monthlycost2br: 1199.55 }]);
assert.ok(!("clt_downpaymentpct" in q)); assert.strictEqual(q.clt_monthlycost2br, 1199.55);
assert.strictEqual(q.clt_project_projecthome_project[0].clt_principalinterest, 599.55); assert.strictEqual(q.clt_project_projecthome_project[0].clt_estimatedmonthlycost, 1199.55);
assert.strictEqual(q.clt_project_projecthome_project[0].clt_estimatedprice, 100000);
// priced by income band: each band has its own price, so the home has no single price
s = base(); s.finance.perBandPrice = true; s.finance.term = "15"; s.costs[2].prices = { 0: "200000", 1: "245000" };
q = N.plan(s, choices);
assert.strictEqual(q.clt_project_projectband_project[0].clt_price2br, 200000); assert.strictEqual(q.clt_project_projectband_project[1].clt_price2br, 245000);
assert.strictEqual(q.clt_project_projectband_project[0].clt_pi2br, N.payment(200000, 3, 5, 15)); assert.strictEqual(q.clt_loantermyears, 15);
assert.ok(!("clt_estimatedprice" in q.clt_project_projecthome_project[0]));
// first come, first served with no closing date is a rolling list; turning the ratio tests off is kept
s = base(); s.method = "First come first served"; s.closes = ""; s.type = "Resale"; s.rules.minaffordabilitycheck = false;
q = N.plan(s, choices);
assert.strictEqual(q.clt_rolling, true); assert.ok(!("clt_applicationcloses" in q)); assert.strictEqual(q.clt_projecttype, 2);
assert.strictEqual(q.clt_minaffordabilitycheck, false);
// a choice the environment doesn't have stops the plan with a clear message
assert.throws(() => N.plan(base(), { ...choices, projectstatus: {} }), /Unknown projectstatus value: Planning/);
assert.ok(JSON.stringify([N.check(base()), N.STEPS]).indexOf("\u2014") < 0, "no em dashes in what staff read");
console.log("ok");
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the New project rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "newproject.js")], capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "ok":
        sys.exit("New project rules failed:\n" + r.stdout + r.stderr)

    import app_spec_intake as intake
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES
    PREFIX = "clt"
    rules = open(os.path.join(web, "newproject.js")).read()
    page = open(os.path.join(web, "newproject.html")).read()
    # in the app: a page under Projects, in both the intake app and Stu, with its scripts
    assert intake.PAGES["newproject"] == ("New project", "clt_/pages/newproject.html")
    assert dict(intake.NAVIGATION)["Projects"][:2] == ["project", "page:newproject"]
    for res in ("clt_/pages/newproject.html", "clt_/pages/newproject.js", "clt_/pages/pages.js", "clt_/pages/pages.css"):
        assert res in intake.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    assert page.index('src="pages.js"') < page.index('src="newproject.js"') < page.index("CLTNewProject")
    # every script parses
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules, open(os.path.join(web, "pages.js")).read()):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src,
                           capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    assert "function create(" in open(os.path.join(web, "pages.js")).read() and "P.create(" in script
    # every clt_ name the page and its rules use is real: a column of a table they touch, a table, or a relationship
    tables = {t["name"]: t for t in TABLES}
    used_tables = ("project", "projecthome", "projectpriority", "projectband", "eligibility", "property")
    known = {f"{PREFIX}_name", f"{PREFIX}_properties", f"{PREFIX}_projects", f"{PREFIX}_brandlogo"}
    for t in used_tables:
        known |= {f"{PREFIX}_{c['name']}" for c in tables[t]["columns"]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    known |= {f"{PREFIX}_{parent}_{child}_{col}" for child, col, parent, *_ in LOOKUPS}   # deep insert uses these
    # the band columns are built from a beginning and a home size ending: check every one of them is real
    band = {c["name"] for c in tables["projectband"]["columns"]}
    endings = re.search(r"SIZE_KEYS = \[(.*?)\]", rules)[1].replace('"', "").split(", ")
    assert len(endings) == 5 and all(f"{start}{k}" in band for start in ("price", "pi", "monthlycost") for k in endings)
    assert all(f"monthlycost{k}" in {c["name"] for c in tables["project"]["columns"]} for k in endings)
    known |= {f"{PREFIX}_price", f"{PREFIX}_pi", f"{PREFIX}_monthlycost"}
    used = set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script + rules)) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    for nav in ("clt_project_projecthome_project", "clt_project_projectpriority_project", "clt_project_projectband_project"):
        assert nav in rules and nav in known, nav
    # the labels it sends are choices in the schema
    for name, labels in (("projecttype", ["New construction sale", "Resale"]), ("selectionmethod", ["Lottery", "First come first served"]),
                         ("projectstatus", ["Planning"]), ("rulechoice", ["Required", "Not required"]), ("projecthomestatus", ["Available"])):
        for label in labels:
            assert label in CHOICES[name][1], (name, label)
            assert f'"{label}"' in rules or f">{label}<" in page or f'value="{label}"' in page, label
    assert re.search(r"SIZES = \[(.*?)\]", rules)[1].replace('"', "").split(", ") == CHOICES["homesize"][1]
    # the cost columns line up with the home sizes, and every rule column is a real project column
    project = {c["name"] for c in tables["project"]["columns"]}
    home = {c["name"] for c in tables["projecthome"]["columns"]}
    for col in re.findall(r'\["\w+", "clt_(\w+)"', rules):
        assert col in project or col in home, col
    parts = re.findall(r'\["\w+", "clt_(\w+)", "[^"]+"\]', rules[rules.index("COST_PARTS = ["):rules.index("];", rules.index("COST_PARTS = ["))])
    assert parts == ["propertytaxes", "insurance", "hoadues", "leasefee", "reservefee"] and set(parts) <= home, parts
    assert "principalinterest" in home and "clt_principalinterest" in rules
    # the bands and the loan are on the project form, and a band has its own form
    pform = str(intake.FORMS["project"])
    assert "projectband" in pform and "downpaymentpct" in pform and "loantermyears" in pform
    assert "interestrate" in str(intake.FORMS["projectband"]) and "projectband" in intake.APP_TABLES
    # the breakdown is on the Project home form, so one home can be changed later
    form = str(intake.FORMS["projecthome"])
    for col in parts + ["estimatedprice", "principalinterest", "estimatedmonthlycost"]:
        assert col in form, col
    # every field the page reads by id is on the page
    ids = set(re.findall(r'id="([\w-]+)"', page))
    for ref in set(re.findall(r'\$\("([\w-]+)"\)', script)):
        assert ref in ids or ref in ("open",) or ref.startswith("r-"), ref
    assert "\u2014" not in page and "\u2014" not in rules
    print("OK: New project rules give the expected checks and record for each worked example; the page is in the app "
          "and uses only real columns, relationships and choices.")


if __name__ == "__main__":
    main()
