"""Offline test: the Invite page's rules (webresources/invite.js) run in Node on worked examples, and the page is
checked against the schema. Skipped with a message if Node isn't installed."""
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
const I = require(process.argv[process.argv.length - 1]);

// ---- filling in the words in curly brackets
const v = { "first name": "Marisol", household: "Quintero", project: "Maple Court phase 1", "application number": "A-00012",
            link: "https://example.com/f?n=A-00012", deadline: "December 18, 2026", organization: "Example Community Land Trust" };
assert.strictEqual(I.fill("Hello {first name}, about {project}. Reply by {deadline}.", v), "Hello Marisol, about Maple Court phase 1. Reply by December 18, 2026.");
assert.strictEqual(I.fill("{First Name} / { household } / {APPLICATION NUMBER}", v), "Marisol / Quintero / A-00012", "spacing and capitals don't matter");
assert.strictEqual(I.fill("Hi {first name}, {nickname}, {link}", { "first name": "", link: null }), "Hi {first name}, {nickname}, {link}",
                   "a field with no value, or one Stu doesn't know, is left showing so the gap is obvious");
const filled = I.fill(I.DEFAULT.body, v);
assert.ok(!/[{}]/.test(filled) && !/[{}]/.test(I.fill(I.DEFAULT.subject, v)), "the starting words use only fields Stu fills in");
assert.ok(filled.startsWith("Hello Marisol,") && filled.includes("https://example.com/f?n=A-00012") && filled.includes("(A-00012)") && filled.endsWith("Example Community Land Trust"));
assert.deepStrictEqual(I.FIELDS.map(f => f[0]).sort(), Object.keys(v).sort());

// ---- the link: staff paste the form's plain address and Stu adds the application number the way the platform expects
const plain = "https://www.cognitoforms.com/YourOrg/FullApplication";
assert.strictEqual(I.linkProblem(plain), "");
assert.strictEqual(I.linkFor(plain, "A-00012"), "https://www.cognitoforms.com/YourOrg/FullApplication?entry=%7B%22PrimaryApplicant%22:%7B%22ApplicationNumber%22:%22A-00012%22%7D%7D");
assert.strictEqual(decodeURI(I.linkFor(plain, "A-00012")), plain + '?entry={"PrimaryApplicant":{"ApplicationNumber":"A-00012"}}');
assert.strictEqual(I.linkFor("  " + plain + " ", "A-00007"), I.linkFor(plain, "A-00007"), "spaces around a pasted address don't matter");
assert.strictEqual(decodeURI(I.linkFor("https://cognitoforms.com/YourOrg/Apply?source=web", "A-00012")), 'https://cognitoforms.com/YourOrg/Apply?source=web&entry={"PrimaryApplicant":{"ApplicationNumber":"A-00012"}}');
// a form that names the question differently: the organization's setting says where it is
assert.strictEqual(decodeURI(I.linkFor(plain, "A-00012", "Applicant.AppNo")), plain + '?entry={"Applicant":{"AppNo":"A-00012"}}');
assert.strictEqual(decodeURI(I.linkFor(plain, "A-00012", "")), decodeURI(I.linkFor(plain, "A-00012")), "a blank setting uses the usual question");
assert.strictEqual(I.NUMBER_FIELD, "PrimaryApplicant.ApplicationNumber");
assert.ok(I.linkProblem(plain + '?entry={"PrimaryApplicant":{"ApplicationNumber":"A-00001"}}').includes("already has an entry="), "a link copied with someone's number in it is refused");
// ---- or, for any platform: an address with {number} where the application number goes
const form = 'https://www.cognitoforms.com/YourOrg/FullApplication?entry={"PrimaryApplicant":{"ApplicationNumber":"{number}"}}';
assert.strictEqual(I.linkProblem(form), "");
const want = "https://www.cognitoforms.com/YourOrg/FullApplication?entry=%7B%22PrimaryApplicant%22:%7B%22ApplicationNumber%22:%22A-00012%22%7D%7D";
assert.strictEqual(I.linkFor(form, "A-00012"), want);
assert.strictEqual(I.linkFor("https://www.cognitoforms.com/YourOrg/FullApplication?entry=%7B%22PrimaryApplicant%22:%7B%22ApplicationNumber%22:%22%7Bnumber%7D%22%7D%7D", "A-00012"), want,
                   "an address that was already encoded gives the same link");
assert.strictEqual(decodeURI(want), form.replace("{number}", "A-00012"), "the form receives exactly the address staff pasted, with the number in place");
assert.strictEqual(I.linkFor("https://form.example.org/apply?number={number}", "A-00007"), "https://form.example.org/apply?number=A-00007");
assert.ok(I.linkProblem("").includes("no full application link")); assert.ok(I.linkProblem("www.example.org/{number}").includes("https://"));
assert.ok(I.linkProblem("https://example.org/apply").includes("Put {number} in it"), "another platform needs to be told where the number goes");
assert.strictEqual(I.linkFor("https://example.org/apply", "A-00012"), "", "no link is made from an address that can't tell households apart");
assert.strictEqual(I.linkFor(form, ""), "");

// ---- the reply-by date
assert.strictEqual(I.deadline("2026-12-03", 15), "2026-12-18"); assert.strictEqual(I.deadline("2026-12-03", null), "2026-12-18");
assert.strictEqual(I.deadline("2026-12-20", 15), "2027-01-04"); assert.strictEqual(I.deadline("2027-02-20T10:00:00Z", 10), "2027-03-02");
// the date staff type instead: a real date, today or later
assert.strictEqual(I.dueProblem("2026-12-18", "2026-12-03"), ""); assert.strictEqual(I.dueProblem("2026-12-03", "2026-12-03"), "", "due today is allowed");
assert.ok(I.dueProblem("2026-12-02", "2026-12-03").includes("in the past")); assert.ok(I.dueProblem("", "2026-12-03").includes("Choose the date"));
assert.ok(I.dueProblem("2026-13-45", "2026-12-03").includes("Choose the date")); assert.ok(I.dueProblem(null, "2026-12-03").includes("Choose the date"));
assert.strictEqual(I.longDate("2026-12-18"), "December 18, 2026"); assert.strictEqual(I.longDate("2027-01-04"), "January 4, 2027");

// ---- how many places a list has: invites per list, or the minimum per home times its homes, whichever is more
assert.strictEqual(I.quota({}, 3), 10); assert.strictEqual(I.quota({ perList: 4, perHome: 2 }, 3), 6); assert.strictEqual(I.quota({ perList: 4 }, 1), 4);
assert.strictEqual(I.quota({ perList: 0, perHome: 0 }, 5), 0);

// ---- who to invite next
const E = (applicationId, bedrooms, rank, status) => ({ applicationId, bedrooms, rank, status: status || "Waitlist" });
let entries = [E("a", 2, 1), E("b", 2, 2), E("c", 2, 3), E("d", 2, 4), E("e", 2, 5)];
let s = I.suggest(entries, { 2: 1 }, { perList: 3, perHome: 2 });
assert.deepStrictEqual(s.lists, [{ size: 2, quota: 3, active: 0, suggested: ["a", "b", "c"] }]);
assert.deepStrictEqual(Object.keys(s.applications), ["a", "b", "c"]);
// rank decides, not the order the entries arrive in
assert.deepStrictEqual(I.suggest(entries.slice().reverse(), { 2: 1 }, { perList: 2 }).lists[0].suggested, ["a", "b"]);
// two already invited and one who declined: one place is open, and it goes to the next household still waiting
entries = [E("a", 2, 1, "Invited"), E("b", 2, 2, "Declined"), E("c", 2, 3, "Application received"), E("d", 2, 4), E("e", 2, 5)];
assert.deepStrictEqual(I.suggest(entries, { 2: 1 }, { perList: 3 }).lists, [{ size: 2, quota: 3, active: 2, suggested: ["d"] }]);
// a full list suggests nobody
assert.deepStrictEqual(I.suggest(entries, { 2: 1 }, { perList: 2 }).lists[0].suggested, []);
// the minimum per home can raise a list's places: 3 homes x 2 = 6
assert.strictEqual(I.suggest(entries, { 2: 3 }, { perList: 3, perHome: 2 }).lists[0].quota, 6);
// two lists: household a is first on both. One invitation covers both lists, so it uses a place on the 3 bedroom list too
entries = [E("a", 2, 1), E("b", 2, 2), E("a", 3, 1), E("c", 3, 2), E("d", 3, 3)];
s = I.suggest(entries, { 2: 1, 3: 1 }, { perList: 2 });
assert.deepStrictEqual(s.lists, [{ size: 2, quota: 2, active: 0, suggested: ["a", "b"] }, { size: 3, quota: 2, active: 1, suggested: ["c"] }]);
assert.deepStrictEqual(Object.keys(s.applications).sort(), ["a", "b", "c"]);
assert.deepStrictEqual(I.suggest([], {}, {}), { lists: [], applications: {} });
assert.ok(JSON.stringify(I.DEFAULT).indexOf("\u2014") < 0, "no em dashes in what applicants read");
console.log(JSON.stringify(I.DEFAULT));
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the Invite rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "invite.js")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Invite rules failed:\n" + r.stdout + r.stderr)
    default = json.loads(r.stdout.strip().splitlines()[-1])

    import app_spec_intake as intake
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES, SEED_ROWS
    PREFIX = "clt"
    rules = open(os.path.join(web, "invite.js")).read()
    page = open(os.path.join(web, "invite.html")).read()
    # the starter template staff can edit says the same as the page's built-in words, and is used for invitations
    seed = SEED_ROWS["messagetemplate"][0]
    assert seed["subject"] == default["subject"] and seed["body"] == default["body"]
    assert seed["noticetype"] == "Invited to full application" and seed["noticetype"] in CHOICES["noticetype"][1]
    fields = set(re.findall(r"\{([^{}]+)\}", seed["subject"] + seed["body"]))
    assert fields <= set(re.findall(r'\["([a-z ]+)", "', rules[rules.index("var FIELDS"):rules.index("var ACTIVE")])), fields
    tables = {t["name"]: t for t in TABLES}
    desc = next(c for c in tables["messagetemplate"]["columns"] if c["name"] == "body")["desc"]
    assert all("{" + f + "}" in desc for f in fields), "the template's own help text lists every field"
    # the question Stu puts the number in is the one the example full application mapping reads it from
    example = json.load(open(os.path.join(HERE, "..", "clients", "example", "forms", "full-application.json")))
    assert example["applicant"]["applicationNumber"] == re.search(r'NUMBER_FIELD = "([\w.]+)"', rules)[1]
    from schema import ENVIRONMENT_VARIABLES
    assert any(v["name"] == "FullAppNumberField" for v in ENVIRONMENT_VARIABLES) and "FullAppNumberField" in page
    # in the app: a page under Projects, templates under Settings, in both the intake app and Stu
    assert intake.PAGES["invite"] == ("Invite", "clt_/pages/invite.html")
    assert "page:invite" in dict(intake.NAVIGATION)["Projects"] and "messagetemplate" in dict(intake.NAVIGATION)["Settings"]
    for res in ("clt_/pages/invite.html", "clt_/pages/invite.js"):
        assert res in intake.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    assert "messagetemplate" in intake.FORMS and "body" in str(intake.FORMS["messagetemplate"])
    assert "fullappformlink" in str(intake.FORMS["project"]) and "invitelink" in str(intake.FORMS["application"])
    assert page.index('src="pages.js"') < page.index('src="invite.js"') < page.index("CLTInvite")
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    # every clt_ name is real
    used_tables = ("project", "application", "projecthome", "selectionround", "selectionentry", "household", "householdmember",
                   "messagetemplate", "notice")
    known = {f"{PREFIX}_name", f"{PREFIX}_projects", f"{PREFIX}_applications"}
    for t in used_tables:
        known |= {f"{PREFIX}_{c['name']}" for c in tables[t]["columns"]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    used = set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script)) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    # the labels it relies on are choices in the schema
    for name, labels in (("entrystatus", ["Waitlist", "Invited", "Application received", "Approved", "Offered", "Accepted"]),
                         ("applicationstage", ["Invited to full application", "In selection", "Pre-screened", "Screener submitted"]),
                         ("householdstatus", ["Invited to full application", "Applicant"]), ("noticetype", ["Invited to full application"]),
                         ("noticechannel", ["Email"]), ("applicantrole", ["Primary applicant"]), ("roundstatus", ["Certified"])):
        for label in labels:
            assert label in CHOICES[name][1], (name, label)
            assert label in script or label in rules, label
    assert re.search(r"SIZES = \[(.*?)\]", script)[1].replace('"', "").split(", ") == CHOICES["homesize"][1]
    # marking is one change set, and the page never sends email itself
    assert script.count("P.batch(") == 1 and "\u2014" not in page and "\u2014" not in rules
    # three steps: choose, the email (editable, with the link), then one email at a time with Sent and Skip
    for piece in ('data-step="1"', 'data-step="2"', 'data-step="3"', 'id="due" type="date"', 'id="subject"', '<textarea id="body"', 'id="link"', "sentit", "skipit", "mailto:"):
        assert piece in page, piece
    assert "sendEmail" not in script and "fetch(" not in script, "the page hands the email to staff; it never sends one itself"
    print("OK: Invite rules give the expected links, dates, places and next households for each worked example; the starter "
          "template matches the page's words; the page is in the app and uses only real columns and choices.")


if __name__ == "__main__":
    main()
