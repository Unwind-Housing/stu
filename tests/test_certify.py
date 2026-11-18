"""Offline test: the certification rules (webresources/certify.js) run in Node on worked examples, and the Review
and certify page is checked against the schema. Skipped with a message if Node isn't installed."""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert");
const C = require(process.argv[process.argv.length - 1]), P = require(process.argv[process.argv.length - 2]);

// ---- what a pay line comes to in a year: pay per period x periods, plus bonus and overtime
assert.strictEqual(C.annual({ gross: 2000, frequency: "Bi-weekly" }), 52000);
assert.strictEqual(C.annual({ gross: "1,500", frequency: "Semi-monthly", bonus: 1000, overtime: "500" }), 37500);
assert.strictEqual(C.annual({ gross: 900, frequency: "Weekly" }), 46800); assert.strictEqual(C.annual({ gross: 4000, frequency: "Monthly" }), 48000);
assert.strictEqual(C.annual({ gross: 61000, frequency: "Annually" }), 61000); assert.strictEqual(C.annual({ gross: 2000 }), 0, "no pay frequency, no annual figure");

// ---- how a line counts, from staff's decision
assert.strictEqual(C.counted({ entered: 52000, decision: "Accepted" }), 52000);
assert.strictEqual(C.counted({ entered: 52000, decision: "Adjusted", verified: "$49,750.50" }), 49750.5);
assert.strictEqual(C.counted({ entered: 52000, decision: "Excluded" }), 0);
assert.strictEqual(C.counted({ entered: 52000, decision: "Not reviewed" }), null); assert.strictEqual(C.counted({ entered: 52000, decision: "Adjusted", verified: "" }), null);
let r = C.review([{ label: "Hospital", entered: 52000, decision: "Accepted" }, { label: "Cafe", entered: 18000, decision: "Adjusted", verified: 16500, reason: "Hours cut in October" },
                  { label: "Gift", entered: 3000, decision: "Excluded", reason: "One-time" }, { label: "Tips", entered: 2000, decision: "Not reviewed" }], "income");
assert.deepStrictEqual(r, { total: 68500, waiting: 1, problems: [] });
r = C.review([{ label: "Cafe", entered: 18000, decision: "Adjusted", verified: "", reason: "" }, { label: "Gift", entered: 3000, decision: "Excluded" }], "income");
assert.deepStrictEqual(r.problems, ["Cafe: type the verified amount for this adjusted income line.", "Cafe: say why this income line was adjusted.", "Gift: say why this income line was excluded."]);
assert.deepStrictEqual(C.review([], "debt"), { total: 0, waiting: 0, problems: [] });

// ---- percent of AMI: the same sum the application uses. 4 people, 50% limit $53,500: 100% is $107,000
const limits = { 1: 37450, 2: 42800, 3: 48150, 4: 53500, 5: 57800, 6: 62100, 7: 66350, 8: 70650 };
assert.strictEqual(C.ami100(limits, 4), 107000); assert.strictEqual(C.amiPct(68500, limits, 4), 64); assert.strictEqual(C.amiPct(68000, limits, 4), 64);
assert.strictEqual(C.amiPct(68500, limits, 3), 71, "a smaller household has a lower limit, so the same income is a higher percent");
assert.strictEqual(C.limit50(limits, 9), 53500 * 1.4); assert.strictEqual(C.limit50(limits, 10), 53500 * (1.32 + 0.16), "over 8 people: HUD's rule from the 4-person limit");
assert.strictEqual(C.amiPct(68500, null, 4), null); assert.strictEqual(C.amiPct(0, limits, 4), null); assert.strictEqual(C.ami100(limits, 0), null);

// ---- a whole review. The 2026-11-14 test household: $68,500 a year, $385 a month in debt, 4 people, a 3 bedroom
const rules = (over) => Object.assign({ maxAmi: 80, minAmi: null, firstTimeBuyerRequired: true, localTieRequired: true, educationRequired: true, assetLimit: 50000,
  housingRatioMax: 35, debtRatioMax: 44, checkAffordability: true, incomeBuffer: 10, housingRatioBuffer: 2, debtRatioBuffer: 2, minCredit: "740 - 799", bankruptcyYears: 3,
  bands: [{ name: "Up to 65% of AMI", maxAmi: 65, cost: { 2: 1600, 3: 1900 } }, { name: "Above 65% of AMI", maxAmi: null, cost: { 2: 1900, 3: 2300 } }] }, over || {});
const input = (over) => Object.assign({ size: 4, limits, sizesListed: [3],
  income: [{ label: "County Hospital", entered: 52000, decision: "Accepted" }, { label: "Cafe", entered: 18000, decision: "Adjusted", verified: "16,500", reason: "Hours cut" }],
  debts: [{ label: "Car loan", entered: 385, decision: "Accepted" }],
  assets: [{ label: "Savings", entered: 6200, decision: "Accepted" }, { label: "401(k)", entered: 90000, decision: "Excluded", reason: "Retirement account" }],
  confirmed: { firstTimeBuyer: true, localTie: true, primaryResidence: true, education: true } }, over || {});
const prio = [3, 4, 5].map(h => ({ bedrooms: 3, householdSize: h })).concat([2, 3, 4].map(h => ({ bedrooms: 2, householdSize: h })));
const find = (o, test, size) => o.checks.find(c => c.test === test && (size === undefined || c.size === size));
let o = C.run(input(), rules(), prio, P);
assert.deepStrictEqual(o.figures, { size: 4, income: 68500, monthlyDebt: 385, assets: 6200, waiting: 0, problems: [], ami100: 107000, amiPct: 64 });
assert.strictEqual(o.result, "Passes"); assert.ok(o.canCertify); assert.deepStrictEqual(o.sizes, [3]); assert.deepStrictEqual(o.blockers, []);
assert.strictEqual(o.notes, "Passes every test. Certified for: 3 bedrooms.");
assert.deepStrictEqual(o.checks.map(c => c.test + (c.size === null ? "" : " " + c.size) + ":" + c.result),
  ["Income limit:Pass", "First-time buyer:Pass", "Local tie:Pass", "Primary residence:Pass", "Asset limit:Pass", "Household size fits:Pass",
   "Housing ratio 3:Pass", "Total debt ratio 3:Pass", "Homebuyer education:Pass"]);
assert.strictEqual(find(o, "Income limit").limit, 80, "no buffer at certification: the limit is the limit");
assert.strictEqual(find(o, "Housing ratio", 3).limit, 35); assert.strictEqual(find(o, "Total debt ratio", 3).limit, 44);
assert.ok(!find(o, "Credit") && !find(o, "Bankruptcy"), "credit and bankruptcy are pre-screen tests only");
assert.strictEqual(find(o, "Income limit").notes, "Certified income is 64% of AMI; the limit is 80%.");
assert.ok(find(o, "Housing ratio", 3).notes.startsWith("3 bedrooms, up to 65% of ami: $1,900 / $5,708 a month = 33.3%"));
assert.ok(!/[Ss]tated|screener/.test(JSON.stringify(o.checks)), "nothing in a certification talks about the screener");
assert.strictEqual(find(o, "Asset limit").value, 6200, "the excluded retirement account isn't counted");

// income between 80% and 88% passed the pre-screen's buffer; it does not pass here
o = C.run(input({ income: [{ label: "Hospital", entered: 90000, decision: "Accepted" }] }), rules(), prio, P);
assert.strictEqual(o.figures.amiPct, 84); assert.strictEqual(find(o, "Income limit").result, "Fail"); assert.strictEqual(o.result, "Does not pass"); assert.ok(!o.canCertify);
assert.ok(o.blockers[0].startsWith("Income limit: Certified income is 84% of AMI; the limit is 80%."), o.blockers[0]);
// verified income puts them in the upper band, where the home costs more: 3 bedroom fails, so nothing to certify for
o = C.run(input({ income: [{ label: "Hospital", entered: 72000, decision: "Accepted" }] }), rules(), prio, P);
assert.strictEqual(o.figures.amiPct, 67); assert.strictEqual(find(o, "Housing ratio", 3).result, "Fail"); assert.strictEqual(find(o, "Housing ratio", 3).value, 38.3);
assert.ok(!o.canCertify && o.result === "Does not pass" && o.blockers[0].startsWith("The household doesn't pass both ratios for any home size it is on a list for."), o.blockers.join(" | "));
// on two lists: passes for the 2 bedroom only, and is certified for that size alone
o = C.run(input({ income: [{ label: "Hospital", entered: 72000, decision: "Accepted" }], sizesListed: [2, 3] }), rules(), prio, P);
assert.ok(o.canCertify); assert.deepStrictEqual(o.sizes, [2]); assert.strictEqual(o.notes, "Passes every test. Certified for: 2 bedrooms.");
// the certified household size is what counts: 2 people don't fit the 3 bedroom list
o = C.run(input({ size: 2 }), rules(), prio, P);
assert.strictEqual(find(o, "Household size fits").result, "Fail"); assert.ok(!o.canCertify);
// staff haven't confirmed something that's required
o = C.run(input({ confirmed: { firstTimeBuyer: true, localTie: false, primaryResidence: true, education: false } }), rules(), prio, P);
assert.strictEqual(find(o, "Local tie").result, "Fail"); assert.strictEqual(find(o, "Homebuyer education").result, "Fail"); assert.strictEqual(o.result, "Does not pass");
assert.ok(o.blockers.includes("Local tie: Staff have not confirmed the local tie.") && o.blockers.includes("Homebuyer education: Staff have not confirmed that homebuyer education is complete."));
o = C.run(input({ confirmed: {} }), rules({ firstTimeBuyerRequired: false, localTieRequired: false, educationRequired: false }), prio, P);
assert.ok(!find(o, "First-time buyer") && !find(o, "Local tie") && !find(o, "Homebuyer education")); assert.strictEqual(find(o, "Primary residence").result, "Fail");
// the review isn't finished: not ready, but not a fail
o = C.run(input({ debts: [{ label: "Car loan", entered: 385, decision: "Not reviewed" }] }), rules(), prio, P);
assert.strictEqual(o.result, "Not finished"); assert.ok(!o.canCertify && o.blockers.includes("1 line still isn't reviewed."));
o = C.run(input({ size: "" }), rules(), prio, P);
assert.ok(!o.canCertify && o.blockers[0] === "Type the certified household size.");
o = C.run(input({ assets: [{ label: "Savings", entered: 6200, decision: "Adjusted", verified: "", reason: "" }] }), rules(), prio, P);
assert.ok(o.blockers.some(b => b.includes("type the verified amount for this adjusted asset line")));
// assets over the limit once verified
o = C.run(input({ assets: [{ label: "Savings", entered: 6200, decision: "Adjusted", verified: 61000, reason: "Statement" }] }), rules(), prio, P);
assert.strictEqual(find(o, "Asset limit").result, "Fail"); assert.ok(o.blockers[0].includes("Certified assets are $61,000; the limit is $50,000"));
// no AMI limits on the application: someone has to fix that first
o = C.run(input({ limits: null }), rules(), prio, P);
assert.strictEqual(find(o, "Income limit").result, "Needs review"); assert.ok(!o.canCertify && o.blockers.some(b => b.includes("can't be worked out")));

// ---- documents: Stu knows the file names from the form entry, and which line each belongs to, without knowing the form
const entry = { Id: "5-5", PrimaryApplicant: { PrimaryApplicantName: { First: "Jesse", Last: "Testcase" } },
  Income: { MostRecentFederalTaxReturnForm1040ForEachAdultWhoFiles: [{ Name: "Jesse and Robin - 2025 Form 1040.pdf", ContentType: "application/pdf", Id: "F-1", Size: 900 }],
            W2sFromEveryEmployerInThePastYear: [{ Name: "Jesse - 2025 W-2.pdf", ContentType: "application/pdf", Size: 1 }, { Name: "Robin - 2025 W-2.pdf", ContentType: "application/pdf", Size: 1 }],
            IncomeSources: [{ Id: "1", EmployerOrPayerName: "County Hospital", SupportingDocumentsForThisIncome: [{ Name: "paystubs 1.pdf", ContentType: "application/pdf", Size: 1 }, { Name: "paystubs 2.pdf", ContentType: "application/pdf", Size: 1 }] },
                            { Id: "2", EmployerOrPayerName: "Corner Cafe ", SupportingDocumentsForThisIncome: [] }] },
  Debts: { Debts1: [{ Id: "1", LenderOrCreditorName: "Example Credit Union", Statement: [{ Name: "auto loan statement.pdf", ContentType: "application/pdf", Size: 1 }] }] },
  AssetsAndAccounts: { AccountsAndAssets: [{ Id: "1", InstitutionName: "Example Bank", Statements: [{ Name: "Checking Sep.pdf", Size: 1 }, { Name: "Checking Oct.pdf", Size: 1 }] }],
                       SignedGiftLetter: [] },
  WhichExceptionApplies: ["a) something"], Entry: { Number: 5 } };
const docs = C.documents(entry);
assert.deepStrictEqual(docs.groups, [{ label: "Most recent federal tax return form 1040 for each adult who files", files: ["Jesse and Robin - 2025 Form 1040.pdf"] },
                                     { label: "W2s from every employer in the past year", files: ["Jesse - 2025 W-2.pdf", "Robin - 2025 W-2.pdf"] }]);
assert.deepStrictEqual(docs.lines.map(l => [l.id, l.number, l.files.length]), [["1", 1, 2], ["2", 2, 0], ["1", 1, 1], ["1", 1, 2]]);
// three sections each have a line 1: the payer, creditor or institution tells them apart
assert.deepStrictEqual(C.filesFor(docs, "5-5-income-1", "County Hospital"), ["paystubs 1.pdf", "paystubs 2.pdf"]);
assert.deepStrictEqual(C.filesFor(docs, "5-5-debt-1", "example credit union"), ["auto loan statement.pdf"]);
assert.deepStrictEqual(C.filesFor(docs, "5-5-asset-1", "Example Bank"), ["Checking Sep.pdf", "Checking Oct.pdf"]);
assert.deepStrictEqual(C.filesFor(docs, "5-5-income-2", "Corner Cafe"), [], "a line with nothing uploaded is known to have nothing");
assert.strictEqual(C.filesFor(docs, "5-5-income-1", "Somewhere else"), null, "when it can't tell which line 1, it says nothing rather than guess");
assert.strictEqual(C.filesFor(docs, "5-5-income-9", "County Hospital"), null); assert.deepStrictEqual(C.documents(null), { lines: [], groups: [], lastName: "" });
assert.strictEqual(docs.lastName, "Testcase", "the last name as typed on this entry is what the form named the folder with");
assert.strictEqual(C.humanize("PreapprovalLetterFromAMortgageLender"), "Preapproval letter from a mortgage lender"); assert.strictEqual(C.humanize("Statement1"), "Statement");
assert.ok(C.documents({ A: { HomebuyerEducationCourseCertificateForEachPersonWhoWillBeOnTheLoancertifiedByWSHFCHUDOrNeighborWorksAmerica: [{ Name: "x.pdf", Size: 1 }] } }).groups[0].label.length <= 83);
// each line is called what a form that numbers its uploads calls it, so it matches the start of its file names in the folder
assert.strictEqual(C.lineTag("income", 1), "Income 1"); assert.strictEqual(C.lineTag("debt", 2), "Debt 2"); assert.strictEqual(C.lineTag("asset", 12), "Account 12");
assert.strictEqual(C.lineTag("income", undefined), "");
// the number is the form's own item number where the entry gives one (line IDs are often random letters), else the line's position
const real = C.documents({ Income: { IncomeSources: [{ Id: "31zPvq", ItemNumber: 1, EmployerOrPayerName: "Clinic", Docs: [{ Name: "a.pdf", Size: 1 }] }, { Id: "2JjJ9D", ItemNumber: 2, EmployerOrPayerName: "School", Docs: [] }] },
                           Debts: { Debts1: [{ Id: "32syeQ", LenderOrCreditorName: "Credit Union", Statement: [] }, { Id: "3C8vEl", LenderOrCreditorName: "Nelnet", Statement: [{ Name: "n.pdf", Size: 1 }] }] } });
assert.deepStrictEqual(real.lines.map(l => [l.id, l.number]), [["31zPvq", 1], ["2JjJ9D", 2], ["32syeQ", 1], ["3C8vEl", 2]]);
assert.strictEqual(C.lineTag("income", C.lineFor(real, "5-5-income-2JjJ9D", "School").number), "Income 2");
assert.strictEqual(C.lineTag("debt", C.lineFor(real, "5-5-debt-3C8vEl", "Nelnet").number), "Debt 2"); assert.deepStrictEqual(C.lineFor(real, "5-5-debt-3C8vEl", "Nelnet").files, ["n.pdf"]);
assert.strictEqual(C.lineFor(real, "5-5-debt-nope", "Nelnet"), null);
// household-wide uploads are shown with the step they support, worked out from what the question asked for
const G = (label) => ({ label, files: ["x.pdf"] });
const placed = C.place(["Most recent federal tax return form 1040 for each adult who files", "W2s from every employer in the past year",
  "Credit reports from all three bureaus for each person who will be on the loan", "Signed gift letter confirming it is a gift and not a loan",
  "Document from about 12 months ago showing a county address", "Co applicant proof of one year of local residence or work", "Preapproval letter from a mortgage lender",
  "Homebuyer education course certificate for each person who will be on the loan", "Supporting documentation such as a divorce decree or inspectors report"].map(G));
assert.deepStrictEqual(Object.fromEntries(Object.entries(placed).map(([k, v]) => [k, v.length])), { income: 2, debts: 1, assets: 1, firstTimeBuyer: 1, localTie: 2, education: 1, other: 1 });
assert.strictEqual(placed.other[0].label, "Preapproval letter from a mortgage lender"); assert.strictEqual(placed.education[0].label.slice(0, 19), "Homebuyer education");
assert.deepStrictEqual(C.place([]), { income: [], debts: [], assets: [], firstTimeBuyer: [], localTie: [], education: [], other: [] });
// the household's folder: named by the organization's pattern, inside the organization's documents folder
assert.strictEqual(C.entryNumber("5-5"), "5"); assert.strictEqual(C.entryNumber("12-304"), "304");
const who = { "last name": "Testcase", "entry number": "5", entry: "5-5", "application number": "A-00003", household: "Testcase" };
assert.strictEqual(C.folderName("", who), "Testcase - Entry 5"); assert.strictEqual(C.folderName("{application number} {household}", who), "A-00003 Testcase");
const sp = "https://example.sharepoint.com/sites/Stewardship/Application%20Documents/Forms/AllItems.aspx?id=%2Fsites%2FStewardship%2FApplication%20Documents%2FSANDBOX&viewid=1b2c";
assert.strictEqual(C.folderProblem(sp), "");
assert.strictEqual(C.folderLink(sp, "Testcase - Entry 5"), "https://example.sharepoint.com/sites/Stewardship/Application%20Documents/SANDBOX/Testcase%20-%20Entry%205",
                   "the address copied from the browser's address bar works as it is");
assert.strictEqual(C.folderLink("https://example.sharepoint.com/sites/Stewardship/Application Documents/SANDBOX/", "Testcase - Entry 5"), C.folderLink(sp, "Testcase - Entry 5"));
assert.strictEqual(C.folderLink("https://example.sharepoint.com/sites/S/Docs", "O'Brien #2 - Entry 12"), "https://example.sharepoint.com/sites/S/Docs/O'Brien%20%232%20-%20Entry%2012");
assert.strictEqual(C.folderLink("https://drive.google.com/drive/search?q={folder}", "Testcase - Entry 5"), "https://drive.google.com/drive/search?q=Testcase%20-%20Entry%205",
                   "another share: an address with {folder} in it, such as a Google Drive search");
assert.ok(C.folderProblem("https://example.sharepoint.com/:f:/s/Stewardship/EabcDEF123").includes("sharing link"));
assert.ok(C.folderProblem("").includes("no application documents folder")); assert.strictEqual(C.folderLink("", "x"), "");
assert.strictEqual(C.folderLink(sp, "{last name} - Entry 5"), "", "no link is made from a folder name with a gap in it");

// ---- how long a certification lasts
assert.strictEqual(C.expires("2026-11-20", 120), "2027-03-20"); assert.strictEqual(C.expires("2026-11-20T10:00:00Z", 30), "2026-12-20");
assert.strictEqual(C.expires("2026-11-20", null), null); assert.strictEqual(C.expires("2026-11-20", 0), null);
assert.ok(JSON.stringify(o).indexOf("—") < 0);
console.log("ok");
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the certification rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "prescreen.js"), os.path.join(web, "certify.js")], capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "ok":
        sys.exit("Certification rules failed:\n" + r.stdout + r.stderr)

    import app_spec_intake as intake
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES
    PREFIX = "clt"
    rules = open(os.path.join(web, "certify.js")).read()
    page = open(os.path.join(web, "certify.html")).read()
    assert intake.PAGES["certify"] == ("Review and certify", "clt_/pages/certify.html")
    assert "page:certify" in dict(intake.NAVIGATION)["Projects"]
    for res in ("clt_/pages/certify.html", "clt_/pages/certify.js", "clt_/pages/prescreen.js"):
        assert res in intake.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    assert page.index('src="pages.js"') < page.index('src="prescreen.js"') < page.index('src="certify.js"') < page.index("CLTCertify")
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    tables = {t["name"]: t for t in TABLES}
    used_tables = ("project", "application", "certification", "incomesource", "debt", "asset", "eligibilitycheck", "householdmember", "household",
                   "incomelimitset", "eligibility", "projectpriority", "projectband", "selectionround", "selectionentry", "formsubmission")
    known = {f"{PREFIX}_name", f"{PREFIX}_projects", f"{PREFIX}_applications", f"{PREFIX}_formsubmissions"}
    for t in used_tables:
        known |= {f"{PREFIX}_{c['name']}" for c in tables[t]["columns"]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    used = set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script)) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    # the labels it relies on are choices in the schema; the decisions are the review statuses, the periods the pay frequencies
    assert re.search(r"DECISIONS = \[(.*?)\]", rules)[1].replace('"', "").split(", ") == CHOICES["reviewstatus"][1]
    assert sorted(re.findall(r'"([A-Za-z-]+)": \d+', rules[rules.index("PERIODS = {"):rules.index("}", rules.index("PERIODS = {"))])) == sorted(CHOICES["payfrequency"][1])
    for name, labels in (("certificationstatus", ["Reviewing", "Waiting for more information", "Certified", "Not certified"]), ("checkstage", ["Certification"]),
                         ("applicationstage", ["Certified", "Not eligible", "In certification", "Full application submitted"]), ("householdstatus", ["Eligible"]),
                         ("entrystatus", ["Approved", "Ineligible", "Declined", "Removed", "Withdrawn", "Unresponsive"]), ("checkresult", ["Pass", "Fail", "Needs review"])):
        for label in labels:
            assert label in CHOICES[name][1], (name, label)
            assert label in script or label in rules, label
    assert "Homebuyer education" in CHOICES["checktest"][1] and '"Homebuyer education"' in rules
    # the page keeps what staff confirmed and what the household is certified for, and those are on the Certification form
    form = str(intake.FORMS["certification"])
    for f in ("confirmedfthb", "confirmedlocal", "confirmedresidence", "confirmededucation", "certifiedamipct", "certifiedsizes"):
        assert f in form and f"clt_{f}" in script, f
    # documents: the page reads file names from the kept form entry, opens the household's folder through the project's
    # setting, and never calls SharePoint itself (so another share works the same way)
    assert "clt_documentsfolderlink" in script and "documentsfolderlink" in str(intake.FORMS["project"]) and "ApplicationFolderName" in script
    # the folder is set once for the organization (a project can override it): staff don't paste it for each household
    assert "ApplicationDocumentsFolder" in script and "D.project.clt_documentsfolderlink || orgFolder" in script
    assert "sharepoint" not in script.lower() and "_api/" not in script
    from schema import ENVIRONMENT_VARIABLES
    assert {"ApplicationFolderName", "ApplicationDocumentsFolder"} <= {v["name"] for v in ENVIRONMENT_VARIABLES}
    import json as _json
    example = _json.load(open(os.path.join(HERE, "..", "clients", "example", "client.json")))
    assert example["settings"]["ApplicationDocumentsFolder"].startswith("https://yourorg.")
    # everything after the certification record exists is one change set; the page never writes to the household's applicant
    assert script.count("P.batch(") == 2 and "mailto:" not in page
    assert "—" not in page and "—" not in rules
    print("OK: certification rules give the expected figures, tests and decisions for each worked example (no buffers, verified "
          "figures, the same tests as the pre-screen); the page is in the app and uses only real columns and choices.")


if __name__ == "__main__":
    main()
