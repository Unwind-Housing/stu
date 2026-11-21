"""Offline test: the Occupancy verification page's rules (webresources/verify.js) run in Node on worked examples, and
the page is checked against the schema. Skipped with a message if Node isn't installed."""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert");
const V = require(process.argv[process.argv.length - 1]);
const today = "2026-11-17";

// ---- filling in the words in curly brackets
const vals = { "first name": "Maria", household: "Rivera", home: "12 Pine St", year: 2026, link: "https://example.com/f", "due date": "December 17, 2026", organization: "Example Community Land Trust" };
const body = V.fill(V.DEFAULT.body, vals), subject = V.fill(V.DEFAULT.subject, vals);
assert.ok(!/[{}]/.test(body) && !/[{}]/.test(subject), "the starting words use only fields the page fills in");
assert.strictEqual(subject, "Your 2026 occupancy verification for 12 Pine St"); assert.ok(body.startsWith("Hello Maria,") && body.includes("by December 17, 2026:\nhttps://example.com/f") && body.endsWith("Example Community Land Trust"));
assert.strictEqual(V.fill("{First Name} / { YEAR } / {nickname} / {home}", { "first name": "Maria", year: 2026, home: "" }), "Maria / 2026 / {nickname} / {home}", "a gap stays showing");
assert.deepStrictEqual(V.FIELDS.map(f => f[0]).sort(), Object.keys(vals).sort());
assert.strictEqual(V.longDate("2026-12-07"), "December 7, 2026"); assert.strictEqual(V.defaultDue(today), "2026-12-17"); assert.strictEqual(V.defaultDue("2026-12-15"), "2027-01-14");

// ---- each household's link carries the year, the household ID and the request's code
const v = { year: 2026, householdId: "H-00012", code: "K7QM2XPA" };
// Cognito Forms, plain link: the entry is added the way Cognito fills in a form
const cog = "https://www.cognitoforms.com/YourOrg/AnnualVerification";
assert.strictEqual(decodeURIComponent(V.linkFor(cog, v)), cog + '?entry={"Year":"2026","HouseholdID":"H-00012","VerificationCode":"K7QM2XPA"}');
assert.ok(!/[{}" ]/.test(V.linkFor(cog, v)), "safe to paste into an email");
// Jotform (or any other platform), plain link: ordinary address fields
assert.strictEqual(V.linkFor("https://form.jotform.com/241234567890", v), "https://form.jotform.com/241234567890?year=2026&householdId=H-00012&code=K7QM2XPA");
assert.strictEqual(V.linkFor("https://form.jotform.com/241234567890?lang=es", v), "https://form.jotform.com/241234567890?lang=es&year=2026&householdId=H-00012&code=K7QM2XPA");
// a link that says where they go: any platform, any question names
assert.strictEqual(V.linkFor("https://form.jotform.com/241234567890?verificationYear={year}&hh={Household ID}", v), "https://form.jotform.com/241234567890?verificationYear=2026&hh=H-00012");
assert.strictEqual(decodeURIComponent(V.linkFor('https://www.cognitoforms.com/YourOrg/Verify?entry={"Info":{"Yr":"{year}","Household":"{household id}","Ref":"{code}"}}', v)),
                   'https://www.cognitoforms.com/YourOrg/Verify?entry={"Info":{"Yr":"2026","Household":"H-00012","Ref":"K7QM2XPA"}}');
assert.strictEqual(V.linkFor("  " + cog + " ", v), V.linkFor(cog, v));
// a form that opens with the owner's name and the home's address already filled in
const who = { ...v, firstName: "Maria", lastName: 'O\'Brien "Mo" & Lee', street: "12 Pine St", unit: "#3", city: "Port Example", state: "WA", zip: "98000" };
const named = 'https://www.cognitoforms.com/YourOrg/Verify?entry={"OwnerName":{"First":"{first name}","Last":"{Last Name}"},"PropertyAddress":{"Line1":"{street}","Line2":"{unit}","City":"{city}","State":"{state}","PostalCode":"{zip}"},"Code":"{code}"}';
const filled = V.linkFor(named, who), entry = JSON.parse(decodeURIComponent(filled.split("?entry=")[1]));
assert.deepStrictEqual(entry, { OwnerName: { First: "Maria", Last: 'O\'Brien "Mo" & Lee' }, PropertyAddress: { Line1: "12 Pine St", Line2: "#3", City: "Port Example", State: "WA", PostalCode: "98000" }, Code: "K7QM2XPA" });
assert.ok(!/[{}"#& ']/.test(filled.split("?")[1]), "quotes, &, # and spaces in a name or address can't break the link");
assert.strictEqual(V.linkFor("https://form.jotform.com/241234567890?first={first name}&unit={unit}&lang=es", who), "https://form.jotform.com/241234567890?first=Maria&unit=%233&lang=es");
assert.strictEqual(V.linkFor(named, v).includes("undefined"), false, "a missing detail is left empty");
assert.strictEqual(V.linkFor("https://form.jotform.com/1?occ={Occupancy ID}&y={year}", { ...v, occupancyId: "O-00007" }), "https://form.jotform.com/1?occ=O-00007&y=2026");
// the state goes as two letters when the State list has them
assert.strictEqual(V.stateCode("Washington", "WA\nWashington"), "WA"); assert.strictEqual(V.stateCode("Washington", ""), "Washington"); assert.strictEqual(V.stateCode("", null), "");
assert.strictEqual(V.linkProblem(cog), ""); assert.ok(V.linkProblem("").includes("no annual verification form link")); assert.ok(V.linkProblem("www.example.com/form").includes("https://"));
// the code: 8 characters, none easy to misread
assert.strictEqual(V.code([0, 1, 2, 31, 32, 255, 100, 7, 99]), "ABC9A9E" + "H"); assert.ok(!/[IO01]/.test(V.code(Array.from({ length: 8 }, (_, i) => i * 37))));

// ---- who can be asked: one request per household per year
const occ = [{ id: "o1", name: "Rivera - 12 Pine St", home: "12 Pine St", household: "Rivera", householdId: "H-00012", email: "maria@example.com", firstName: "Maria", lastVerified: "2025-10-01" },
             { id: "o2", name: "Chen - 4 Oak Ave", home: "4 Oak Ave", household: "Chen", householdId: "H-00013", email: "", firstName: "Wei" },
             { id: "o3", name: "Okafor - 9 Elm Ct", home: "9 Elm Ct", household: "Okafor", householdId: "H-00014", email: "ada@example.com" },
             { id: "o4", name: "Lee - 3 Fir Rd", home: "3 Fir Rd", household: "Lee", householdId: "H-00015", email: "lee@example.com" }];
const reqs = [{ id: "v1", occupancy: "o3", year: 2026, status: "Sent", method: "Online form" }, { id: "v2", occupancy: "o4", year: 2026, status: "Approved", method: "Paper" },
              { id: "v3", occupancy: "o1", year: 2025, status: "Approved", method: "Paper" }];
const rows = V.choose(occ, reqs, 2026);
assert.deepStrictEqual(rows.map(r => [r.id, r.state, r.tick, r.method]), [["o1", "", true, "Online form"], ["o2", "", true, "Paper"], ["o3", "Open", false, "Online form"], ["o4", "Done", false, "Online form"]],
                       "last year's request doesn't count; no email means paper; open or finished this year isn't asked again");
assert.strictEqual(rows[2].request.id, "v1");
// opened from Verification hub for particular households: only those are ticked (and never one already asked)
assert.deepStrictEqual(V.choose(occ, reqs, 2026, ["O2", "o3"]).map(r => r.tick), [false, true, false, false]); assert.deepStrictEqual(V.choose(occ, reqs, 2026, []).map(r => r.tick), [true, true, false, false]); assert.strictEqual(V.choose(occ, reqs, "2027").filter(r => r.tick).length, 4);

// ---- starting a batch
const inp = { year: 2026, due: "2026-12-17", link: cog, subject: V.DEFAULT.subject, body: V.DEFAULT.body };
const picks = [{ ...rows[0] }, { ...rows[1] }];
assert.deepStrictEqual(V.startProblems(picks, inp, today), []);
assert.deepStrictEqual(V.startProblems([{ ...rows[1] }], { year: 2026, due: "2026-12-17", link: "", subject: "", body: "" }, today), [], "paper only needs no link or email");
assert.ok(V.startProblems([], inp, today)[0].includes("Tick")); assert.ok(V.startProblems(picks, { ...inp, due: "2026-11-01" }, today)[0].includes("past"));
assert.ok(V.startProblems(picks, { ...inp, link: "" }, today)[0].includes("no annual verification form link")); assert.ok(V.startProblems(picks, { ...inp, body: "Hello" }, today)[0].includes("{link}"));
assert.ok(V.startProblems([{ ...rows[1], method: "Online form" }], inp, today)[0].includes("Chen has no email address"));
assert.ok(V.startProblems(picks, { ...inp, year: "" }, today)[0].includes("year"));
const mail = V.email(rows[0], inp, "Example Community Land Trust", "K7QM2XPA");
assert.strictEqual(mail.to, "maria@example.com"); assert.strictEqual(mail.subject, "Your 2026 occupancy verification for 12 Pine St");
assert.strictEqual(mail.link, V.linkFor(cog, v)); assert.ok(mail.body.includes(mail.link) && mail.body.includes("December 17, 2026") && !/\{[a-z ]+\}/.test(mail.body));
assert.strictEqual(V.requestName(2026, "Rivera - 12 Pine St"), "2026, Rivera - 12 Pine St");
// copied into a mail program, the long link is a button, not spelled out
const rich = V.emailHtml(mail, "#526B50");
assert.strictEqual(rich.split(mail.link.replace(/&/g, "&amp;")).length, 2, "the link appears once, as the button's address");
assert.ok(rich.includes('<a href="' + mail.link.replace(/&/g, "&amp;") + '"') && rich.includes(">" + V.BUTTON + "</a>") && rich.includes("#526B50") && rich.includes("Hello Maria,<br><br>Each year"));
assert.ok(rich.includes("by December 17, 2026:<table") && rich.includes("</table><br>If you would rather"), "no stray blank lines around the button");
assert.ok(V.emailHtml({ body: "<b>Hi</b> & bye", link: "" }, "red").includes("&lt;b&gt;Hi&lt;/b&gt; &amp; bye") && !V.emailHtml({ body: "x", link: "" }, "red").includes("red"), "typed words can't become markup");
// the email's link fills in the form from the household's row (the home's state is kept apart from the request's state)
const full = V.choose([{ ...occ[0], lastName: "Rivera", street: "12 Pine St", city: "Port Example", homeState: "WA", zip: "98000" }], [], 2026)[0];
assert.strictEqual(full.state, ""); assert.deepStrictEqual(JSON.parse(decodeURIComponent(V.email(full, { ...inp, link: named }, "Org", "K7QM2XPA").link.split("?entry=")[1])).PropertyAddress,
                   { Line1: "12 Pine St", Line2: "", City: "Port Example", State: "WA", PostalCode: "98000" });

// ---- closing a request
assert.deepStrictEqual(V.closeProblems({ received: today, outcome: "Approved", notes: "" }, today), []);
assert.ok(V.closeProblems({ received: "", outcome: "Approved" }, today)[0].includes("date")); assert.ok(V.closeProblems({ received: "2026-11-18", outcome: "Approved" }, today)[0].includes("future"));
assert.ok(V.closeProblems({ received: today, outcome: "" }, today)[0].includes("how it came out")); assert.ok(V.closeProblems({ received: today, outcome: "Issue found", notes: " " }, today)[0].includes("issue"));
assert.deepStrictEqual(V.closeProblems({ received: today, outcome: "Issue found", notes: "Renting the whole home." }, today), []);

// ---- the signed form
assert.strictEqual(V.fileProblem(null), ""); assert.strictEqual(V.fileProblem({ name: "Rivera 2026.PDF", size: 300000 }), "");
assert.ok(V.fileProblem({ name: "form.docx", size: 10 }).includes("PDF")); assert.ok(V.fileProblem({ name: "scan.pdf", size: 21 * 1024 * 1024 }).includes("20 MB"));
assert.deepStrictEqual(["a.pdf", "b.JPG", "c.png", "d.txt", ""].map(V.fileKind), ["pdf", "image", "image", "", ""]);

// ---- cancelling a verification: the occupancy's date falls back to what is left
const others = [{ received: "2025-10-01", status: "Approved" }, { received: "2024-09-15", status: "Approved" }, { received: "2026-01-05", status: "Cancelled" }, { received: "", status: "Sent" }];
assert.strictEqual(V.afterCancel("2026-11-10", { received: "2026-11-10", status: "Approved" }, others), "2025-10-01", "back to the one before, which is now over a year old");
assert.strictEqual(V.afterCancel("2026-11-10", { received: "2026-11-10", status: "Approved" }, []), null, "nothing left: never verified");
assert.strictEqual(V.afterCancel("2026-11-12", { received: "2026-11-10", status: "Approved" }, others), undefined, "a newer date typed on the occupancy stays");
assert.strictEqual(V.afterCancel("2025-10-01", { received: "", status: "Sent" }, others), undefined, "an open request never set the date");
assert.strictEqual(V.afterCancel("2026-11-10", { received: "2026-11-10", status: "Issue found" }, others), undefined, "an issue never set the date");
assert.strictEqual(V.afterCancel("2026-11-10", { received: "2026-11-10", status: "Approved" }, [{ received: "2026-06-01", status: "Issue found" }, { received: "2026-05-01", status: "Received" }]), null, "only approved ones are left to fall back on");
// an issue is saved on the request and stays open, so the household isn't asked again while it is being put right
assert.ok(V.OPEN.includes("Issue found") && !V.CLOSED.includes("Issue found") && V.counts("Approved") && V.counts("Waived") && !V.counts("Issue found") && !V.counts("Received"));
assert.deepStrictEqual(V.choose(occ, [{ id: "v8", occupancy: "o1", year: 2026, status: "Issue found", method: "Paper" }], 2026).map(r => [r.state, r.tick])[0], ["Open", false]);
// a cancelled request doesn't stop the household being asked again
assert.deepStrictEqual(V.choose(occ, [{ id: "v9", occupancy: "o1", year: 2026, status: "Cancelled", method: "Online form" }], 2026).map(r => [r.state, r.tick])[0], ["", true]);
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the Occupancy verification rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "verify.js")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Occupancy verification rules failed:\n" + r.stdout + r.stderr)

    import app_spec as core
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES, ENVIRONMENT_VARIABLES
    PREFIX = "clt"
    tables = {t["name"]: t for t in TABLES}
    cols = {t: {c["name"]: c for c in tables[t]["columns"]} for t in tables}
    rules = open(os.path.join(web, "verify.js")).read()
    page = open(os.path.join(web, "verify.html")).read()
    # the method, the statuses and the setting are real
    assert CHOICES["verificationmethod"][1][:2] == ["Online form", "Paper"] and cols["annualverification"]["method"]["choice"] == "verificationmethod"
    listed = re.search(r'OPEN = \[(.*?)\], CLOSED = \[(.*?)\], CANCELLED = "(.*?)"', rules)
    assert sorted((listed[1] + ", " + listed[2] + ", " + listed[3]).replace('"', "").split(", ")) == sorted(CHOICES["verificationstatus"][1]), "every status is open, closed or cancelled"
    assert cols["annualverification"]["signedform"]["kind"] == "file" and cols["annualverification"]["sentlink"]["kind"] == "memo"
    assert "Annual verification" in CHOICES["noticetype"][1] and "Primary applicant" in CHOICES["applicantrole"][1]
    assert any(v["name"] == "VerificationFormLink" for v in ENVIRONMENT_VARIABLES) and "VerificationFormLink" in page
    assert "recordnumber" in cols["household"] and "verificationcode" in cols["annualverification"]
    # in the app, under Activities, in the core app and Stu
    assert core.PAGES["verify"] == ("Occupancy verification", "clt_/pages/verify.html") and "page:verify" in dict(core.NAVIGATION)["Activities"]
    for res in ("clt_/pages/verify.html", "clt_/pages/verify.js"):
        assert res in core.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    assert "method" in str(core.FORMS["annualverification"])
    assert page.index('src="pages.js"') < page.index('src="verify.js"') < page.index("CLTVerify")
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    # every clt_ name is real
    used_tables = ("occupancy", "annualverification", "household", "householdmember", "messagetemplate", "property", "listitem")
    assert {"peopleinhome", "noshorttermrental", "mortgagecontact", "signeddate", "phone"} <= set(cols["annualverification"])
    assert not {"insurancecurrent", "insurancecontact", "insurancereceived", "uploadslink"} & set(cols["annualverification"]) and "insurance" not in page.lower().replace("insurance verification", ""), \
        "the yearly form is about occupancy only: insurance is checked on its own"
    known = {f"{PREFIX}_name", f"{PREFIX}_signedform_name"} | {f"{PREFIX}_{c}" for c in ("occupancystatus", "verificationstatus", "verificationmethod", "rentalstatus", "applicantrole", "noticetype")}
    for t in used_tables:
        known |= {f"{PREFIX}_{c}" for c in cols[t]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    used = set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script)) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    # the page hands the email to staff; it never sends one itself. No em dashes.
    assert "forms platform</a>" not in page, "staff aren't sent into the forms platform: not everyone has an account there"
    assert "sendEmail" not in script and "fetch(" not in script and "mailto:" in script
    assert "—" not in page and "—" not in rules
    assert 'id="verification"' in open(os.path.join(web, "guides.html")).read()
    print("OK: Occupancy verification rules give the expected links, emails, choices and checks for each worked example; "
          "the page is in the app and uses only real columns, choices and settings.")


if __name__ == "__main__":
    main()
