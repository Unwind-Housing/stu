"""Offline test: the pre-screen rules in webresources/prescreen.js, run with Node on worked examples."""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JS = r"""
const P = require(process.argv[process.argv.length - 1]);
const assert = require("assert");
const rules = (over) => Object.assign({
  maxAmi: 80, minAmi: null, incomeBuffer: 10, firstTimeBuyerRequired: true, localTieRequired: true, assetLimit: null,
  housingRatioMax: 35, debtRatioMax: 44, debtRatioBuffer: 0, minCredit: "580 - 669", bankruptcyYears: 3,
  checkAffordability: true, cost: { 2: 1600, 3: 1900 } }, over || {});
const app = (over) => Object.assign({
  householdSize: 4, income: 68500, monthlyDebt: 385, assets: 6200, amiPct: 64, credit: "670 - 739", bankruptcy: false,
  firstTimeBuyer: true, fthbException: false, localTie: true, primaryResidence: true, sizesWanted: [3] }, over || {});
const prio = [2, 3, 4].map(h => ({ bedrooms: 2, householdSize: h })).concat([3, 4, 5].map(h => ({ bedrooms: 3, householdSize: h })));
const find = (r, test, size) => r.checks.find(c => c.test === test && (size === undefined || c.size === size));

// The test household from the 2026-11-14 run: $68,500 a year, $385 a month in debt, a 3 bedroom at $1,900
let r = P.run(app(), rules(), prio);
assert.strictEqual(r.result, "Eligible for selection"); assert.deepStrictEqual(r.sizes, [3]);
assert.strictEqual(find(r, "Housing ratio", 3).value, 33.3); assert.strictEqual(find(r, "Housing ratio", 3).result, "Pass");
assert.strictEqual(find(r, "Total debt ratio", 3).value, 40); assert.strictEqual(find(r, "Total debt ratio", 3).limit, 44);
assert.ok(/\$1,900 \/ \$5,708 a month = 33.3%/.test(find(r, "Housing ratio", 3).notes), find(r, "Housing ratio", 3).notes);
assert.strictEqual(find(r, "Income limit").limit, 88);
assert.ok(!find(r, "Minimum income") && !find(r, "Asset limit"), "rules left blank aren't tested");
assert.deepStrictEqual(r.checks.map(c => c.result).filter(x => x !== "Pass"), []);

// Income: over the limit but inside the buffer passes with a note; over the buffer fails
r = P.run(app({ amiPct: 85 }), rules(), prio);
assert.strictEqual(r.result, "Eligible for selection"); assert.ok(/inside the 10% buffer \(88%\)/.test(r.notes), r.notes);
r = P.run(app({ amiPct: 85 }), rules({ incomeBuffer: 5 }), prio);          // 5 means 5% over: 80% becomes 84%
assert.strictEqual(find(r, "Income limit").limit, 84); assert.strictEqual(r.result, "Not eligible");
r = P.run(app({ amiPct: 85 }), rules({ incomeBuffer: null }), prio);       // blank is 10% over
assert.strictEqual(find(r, "Income limit").limit, 88); assert.strictEqual(r.result, "Eligible for selection");
r = P.run(app({ amiPct: 81 }), rules({ incomeBuffer: 0 }), prio);          // 0 is no buffer at all
assert.strictEqual(r.result, "Not eligible");
r = P.run(app({ amiPct: 89 }), rules(), prio);
assert.strictEqual(r.result, "Not eligible"); assert.ok(/^Income limit: /.test(r.notes)); assert.deepStrictEqual(r.sizes, []);
r = P.run(app({ amiPct: null }), rules(), prio);
assert.strictEqual(r.result, "Needs review");
r = P.run(app({ amiPct: 28 }), rules({ minAmi: 30 }), prio);
assert.strictEqual(find(r, "Minimum income").result, "Fail"); assert.strictEqual(r.result, "Not eligible");

// Two sizes asked for: affordable for the 2 bedroom only
r = P.run(app({ sizesWanted: [2, 3] }), rules({ cost: { 2: 1600, 3: 2400 } }), prio);
assert.strictEqual(r.result, "Eligible for selection"); assert.deepStrictEqual(r.sizes, [2]);
assert.strictEqual(find(r, "Housing ratio", 3).result, "Fail"); assert.ok(/Not for 3 bedrooms/.test(r.notes), r.notes);
// Can't afford anything asked for
r = P.run(app({ sizesWanted: [2, 3] }), rules({ cost: { 2: 2300, 3: 2400 } }), prio);
assert.strictEqual(r.result, "Not eligible"); assert.ok(/Can't afford any home size/.test(r.notes), r.notes);
// The back-end ratio can fail when the front-end passes; the buffer adds points
r = P.run(app({ monthlyDebt: 700 }), rules(), prio);
assert.strictEqual(find(r, "Housing ratio", 3).result, "Pass"); assert.strictEqual(find(r, "Total debt ratio", 3).result, "Fail");
r = P.run(app({ monthlyDebt: 700 }), rules({ debtRatioBuffer: 2 }), prio);
assert.strictEqual(find(r, "Total debt ratio", 3).result, "Pass"); assert.strictEqual(find(r, "Total debt ratio", 3).limit, 46);
// The front-end ratio has its own buffer, in points
r = P.run(app(), rules({ cost: { 3: 2100 } }), prio);                      // 36.8% against 35%
assert.strictEqual(find(r, "Housing ratio", 3).result, "Fail");
r = P.run(app(), rules({ cost: { 3: 2100 }, housingRatioBuffer: 2 }), prio);
assert.strictEqual(find(r, "Housing ratio", 3).result, "Pass"); assert.strictEqual(find(r, "Housing ratio", 3).limit, 37);
assert.ok(/plus a 2 point buffer/.test(find(r, "Housing ratio", 3).notes));
// No cost on the project for that size: someone has to look
r = P.run(app(), rules({ cost: { 2: 1600 } }), prio);
assert.strictEqual(r.result, "Needs review"); assert.ok(/no monthly housing cost for this home size/.test(r.notes), r.notes);
// Affordability switched off: no ratio rows, every size that fits counts
r = P.run(app({ sizesWanted: [2, 3] }), rules({ checkAffordability: false }), prio);
assert.ok(!find(r, "Housing ratio")); assert.deepStrictEqual(r.sizes, [2, 3]);

// Household size
r = P.run(app({ householdSize: 7 }), rules(), prio);
assert.strictEqual(find(r, "Household size fits").result, "Fail"); assert.strictEqual(r.result, "Not eligible");
r = P.run(app({ householdSize: 2, sizesWanted: [2, 3] }), rules(), prio);
assert.deepStrictEqual(r.sizes, [2]); assert.ok(/Doesn't fit: 3 bedrooms/.test(find(r, "Household size fits").notes));
r = P.run(app(), rules(), []);
assert.strictEqual(r.result, "Needs review"); assert.ok(/no priorities yet/.test(r.notes));
r = P.run(app({ householdSize: 6, sizesWanted: [4] }), rules({ cost: { 4: 2000 } }), [{ bedrooms: 5, householdSize: 6 }]);
assert.strictEqual(find(r, "Household size fits").result, "Pass", "4+ bedrooms matches a priority for 4 or more");

// Yes or no rules
r = P.run(app({ firstTimeBuyer: false }), rules(), prio); assert.strictEqual(r.result, "Not eligible");
r = P.run(app({ firstTimeBuyer: false, fthbException: true }), rules(), prio); assert.strictEqual(r.result, "Eligible for selection");
r = P.run(app({ firstTimeBuyer: false }), rules({ firstTimeBuyerRequired: false }), prio);
assert.ok(!find(r, "First-time buyer")); assert.strictEqual(r.result, "Eligible for selection");
r = P.run(app({ localTie: false }), rules(), prio); assert.strictEqual(find(r, "Local tie").result, "Fail");
r = P.run(app({ primaryResidence: false }), rules(), prio); assert.strictEqual(r.result, "Not eligible");
r = P.run(app({ bankruptcy: true }), rules(), prio); assert.strictEqual(find(r, "Bankruptcy").result, "Fail");
r = P.run(app({ bankruptcy: true }), rules({ bankruptcyYears: 2 }), prio); assert.strictEqual(r.result, "Needs review");
r = P.run(app({ credit: "I don't know" }), rules(), prio); assert.strictEqual(r.result, "Needs review");
r = P.run(app({ credit: "300 - 579" }), rules(), prio); assert.strictEqual(find(r, "Credit").result, "Fail");
r = P.run(app({ assets: 60000 }), rules({ assetLimit: 50000 }), prio); assert.strictEqual(find(r, "Asset limit").result, "Fail");
// A failure outranks an unknown
r = P.run(app({ credit: "I don't know", localTie: false }), rules(), prio); assert.strictEqual(r.result, "Not eligible");

// Income bands: the monthly housing cost depends on the band the household's stated income falls in
const bands = [{ name: "Up to 65% of AMI", maxAmi: 65, cost: { 3: 1900 } }, { name: "Above 65% of AMI", maxAmi: null, cost: { 3: 2300 } }];
r = P.run(app({ amiPct: 64 }), rules({ bands, cost: { 3: 9999 } }), prio);          // in the lower band: $1,900, as before; rules.cost is ignored
assert.strictEqual(r.result, "Eligible for selection"); assert.strictEqual(find(r, "Housing ratio", 3).value, 33.3);
assert.ok(/^3 bedrooms, up to 65% of ami: \$1,900 \//.test(find(r, "Housing ratio", 3).notes), find(r, "Housing ratio", 3).notes);
assert.ok(/Costs tested for the income band: up to 65% of ami\./.test(r.notes), r.notes);
r = P.run(app({ amiPct: 65 }), rules({ bands }), prio);                            // exactly on the line counts as in the band
assert.strictEqual(find(r, "Housing ratio", 3).value, 33.3);
r = P.run(app({ amiPct: 78, income: 84000 }), rules({ bands }), prio);             // upper band, and can afford it: $2,300 / $7,000 = 32.9%
assert.strictEqual(r.result, "Eligible for selection"); assert.strictEqual(find(r, "Housing ratio", 3).value, 32.9);
assert.ok(/above 65% of ami/.test(find(r, "Housing ratio", 3).notes));
r = P.run(app({ amiPct: 78 }), rules({ bands }), prio);                            // upper band, can't afford it, nowhere near the line: 40.3%
assert.strictEqual(find(r, "Housing ratio", 3).result, "Fail"); assert.strictEqual(r.result, "Not eligible");
// Just over the line, inside the 10% income buffer (65% becomes 71.5%): fails at the higher cost, passes at the lower, so a person decides
r = P.run(app({ amiPct: 68 }), rules({ bands }), prio);
assert.strictEqual(find(r, "Housing ratio", 3).result, "Needs review"); assert.strictEqual(find(r, "Housing ratio", 3).value, 40.3);
assert.strictEqual(r.result, "Needs review"); assert.deepStrictEqual(r.sizes, []);
assert.ok(/inside the 10% buffer of the up to 65% of ami band, where the cost is \$1,900 a month and both ratios pass/.test(r.notes), r.notes);
r = P.run(app({ amiPct: 72 }), rules({ bands }), prio);                            // 72% is outside the buffer: a plain fail
assert.strictEqual(r.result, "Not eligible");
r = P.run(app({ amiPct: 68 }), rules({ bands, incomeBuffer: 0 }), prio);           // no buffer, no benefit of the doubt
assert.strictEqual(r.result, "Not eligible");
r = P.run(app({ amiPct: 68, monthlyDebt: 900 }), rules({ bands }), prio);          // would fail in the lower band too (debt): a plain fail
assert.strictEqual(find(r, "Total debt ratio", 3).result, "Fail"); assert.strictEqual(r.result, "Not eligible");
r = P.run(app({ amiPct: 68, income: 84000 }), rules({ bands }), prio);             // passes at the higher cost: nothing to review
assert.strictEqual(r.result, "Eligible for selection");
r = P.run(app({ amiPct: null }), rules({ bands }), prio);                          // no % of AMI: tested at the highest band, and flagged
assert.strictEqual(find(r, "Housing ratio", 3).value, 40.3); assert.strictEqual(r.result, "Needs review");
// One band (every buyer gets the same rate): its cost is used and the band isn't mentioned
r = P.run(app(), rules({ bands: [{ name: "All buyers", maxAmi: null, cost: { 3: 1900 } }], cost: {} }), prio);
assert.strictEqual(r.result, "Eligible for selection"); assert.ok(!/band/i.test(r.notes + find(r, "Housing ratio", 3).notes));
// A band with no cost for the size: someone has to look
r = P.run(app({ amiPct: 78 }), rules({ bands: [bands[0], { name: "Above 65% of AMI", maxAmi: null, cost: {} }] }), prio);
assert.strictEqual(r.result, "Needs review");
// Three bands
const three = [{ name: "Up to 50% of AMI", maxAmi: 50, cost: { 3: 1500 } }, { name: "Up to 65% of AMI", maxAmi: 65, cost: { 3: 1900 } }, { name: "Above 65% of AMI", maxAmi: null, cost: { 3: 2300 } }];
assert.ok(/up to 50% of ami: \$1,500/.test(find(P.run(app({ amiPct: 45 }), rules({ bands: three }), prio), "Housing ratio", 3).notes));
assert.ok(/up to 65% of ami: \$1,900/.test(find(P.run(app({ amiPct: 51 }), rules({ bands: three }), prio), "Housing ratio", 3).notes));

assert.deepStrictEqual(P.sizesFromLabels("2 bedrooms; 3 bedrooms"), [2, 3]);
assert.deepStrictEqual(P.sizesFromLabels("Studio; 4+ bedrooms"), [0, 4]);
assert.deepStrictEqual(P.sizesFromLabels(""), []);
const all = JSON.stringify([P.run(app({ amiPct: 85, sizesWanted: [2, 3] }), rules({ cost: { 2: 1600, 3: 2400 }, assetLimit: 1, minAmi: 90 }), prio)]);
assert.ok(all.indexOf("\u2014") < 0, "no em dashes in what staff read");
console.log("ok");
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the pre-screen rules weren't run. Install Node to run this test.")
        return
    r = subprocess.run([node, "-e", JS, os.path.join(HERE, "..", "webresources", "prescreen.js")],
                       capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "ok":
        sys.exit("Pre-screen rules failed:\n" + r.stdout + r.stderr)
    # The test names the page writes must be choices in the schema, and the page must load the rules file.
    sys.path.insert(0, os.path.join(HERE, ".."))
    from schema import CHOICES
    src = open(os.path.join(HERE, "..", "webresources", "prescreen.js")).read()
    import re
    used = set(re.findall(r'add\("([^"]+)"', src)) | set(re.findall(r'test\("([^"]+)"', src))
    assert used and used <= set(CHOICES["checktest"][1]), used - set(CHOICES["checktest"][1])
    for label in ("Pass", "Fail", "Needs review"):
        assert label in CHOICES["checkresult"][1]
    for label in ("Eligible for selection", "Not eligible", "Needs review"):
        assert label in CHOICES["prescreenresult"][1] and f'"{label}"' in src
    assert re.search(r'SIZES = \[(.*?)\]', src)[1].replace('"', "").split(", ") == CHOICES["homesize"][1]
    assert re.search(r'CREDIT = \[(.*?)\]', src)[1].replace('"', "").split(", ") == CHOICES["creditrange"][1][:5]
    page_checks(node)
    print("OK: pre-screen rules give the expected result for each worked example, and use the schema's choices; "
          "the page is in the intake app and touches only real columns.")


def page_checks(node):
    import re
    import app_spec_intake as intake
    from schema import TABLES
    web = os.path.join(HERE, "..", "webresources")
    page = open(os.path.join(web, "prescreen.html")).read()
    assert intake.PAGES["prescreen"] == ("Pre-screen", "clt_/pages/prescreen.html")
    assert "page:prescreen" in dict(intake.NAVIGATION)["Projects"]
    for res in ("clt_/pages/prescreen.html", "clt_/pages/prescreen.js", "clt_/pages/pages.js"):
        assert res in intake.WEB_RESOURCES, res
    assert page.index('src="pages.js"') < page.index('src="prescreen.js"') < page.index("CLTPrescreen")
    # every script parses
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, open(os.path.join(web, "pages.js")).read(), open(os.path.join(web, "prescreen.js")).read()):
        r = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-600:]
    # every clt_ column the page names exists on one of the tables it uses
    cols = {"clt_name"}
    for t in TABLES:
        if t["name"] in ("application", "project", "eligibility", "eligibilitycheck", "projectpriority", "projectband"):
            cols |= {f"clt_{c['name']}" for c in t["columns"]} | {f"clt_{t['name']}id", f"clt_{t['name']}"}
    cols |= {"clt_application", "clt_project", "clt_projects", "clt_applications", "clt_checkstage", "clt_checktest",
             "clt_checkresult", "clt_prescreenresult", "clt_applicationstage", "clt_homesize"}
    used = set(re.findall(r"\bclt_[a-z0-9]+\b", script)) - {"clt_"}
    assert used <= cols, sorted(used - cols)
    # the fields the pre-screen writes are on the application form, and the costs on the project form
    forms = str(intake.FORMS["application"]) + str(intake.FORMS["project"])
    for f in ("prescreensizes", "prescreenedon", "prescreenoverridden", "monthlycoststudio", "monthlycost1br",
              "monthlycost2br", "monthlycost3br", "monthlycost4br"):
        assert f in forms, f
    assert "\u2014" not in page


if __name__ == "__main__":
    main()
