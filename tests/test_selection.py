"""Offline test: the selection rules (webresources/selection.js: Unique IDs, lists, check numbers, the draw,
ranking, progress) run in Node on worked examples, and the Buyer Selection page is checked against the schema.
Skipped with a message if Node isn't installed."""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert");
const S = require(process.argv[process.argv.length - 1]);

// ---- Unique IDs: in the order screeners were first submitted; existing IDs are kept and numbering carries on
let apps = [{ id: "c", firstSubmittedOn: "2027-01-09T10:00:00Z" }, { id: "a", firstSubmittedOn: "2027-01-05T09:00:00Z" },
            { id: "b", firstSubmittedOn: "2027-01-05T09:00:01Z" }, { id: "w", firstSubmittedOn: "2027-01-01T00:00:00Z", out: true }];
assert.deepStrictEqual(S.assignIds(apps), [{ id: "a", uniqueId: "ID-0001" }, { id: "b", uniqueId: "ID-0002" }, { id: "c", uniqueId: "ID-0003" }]);
apps = [{ id: "a", uniqueId: "ID-0002", firstSubmittedOn: "2027-01-05" }, { id: "late", firstSubmittedOn: "2027-02-01" }, { id: "nodate" }];
assert.deepStrictEqual(S.assignIds(apps), [{ id: "late", uniqueId: "ID-0003" }, { id: "nodate", uniqueId: "ID-0004" }]);
assert.deepStrictEqual(S.assignIds([{ id: "a", uniqueId: "ID-0001" }]), []);
assert.strictEqual(S.idText(7), "ID-0007"); assert.strictEqual(S.idText(12345), "ID-12345"); assert.strictEqual(S.idNumber("ID-0042"), 42);

// ---- the lists: one entry per eligible household per home size it is eligible for, in its tier
const prio = [{ bedrooms: 2, householdSize: 2, tier: 1 }, { bedrooms: 2, householdSize: 3, tier: 1 }, { bedrooms: 2, householdSize: 1, tier: 2 },
              { bedrooms: 3, householdSize: 3, tier: 1 }, { bedrooms: 3, householdSize: 2, tier: 2 }, { bedrooms: 4, householdSize: 6, tier: 1 }];
const E = "Eligible for selection";
const pool = [
  { id: "a1", uniqueId: "ID-0001", result: E, sizes: [2, 3], householdSize: 2, firstSubmittedOn: "2027-01-05T09:00:00Z" },
  { id: "a2", uniqueId: "ID-0002", result: E, sizes: [2], householdSize: 3, firstSubmittedOn: "2027-01-05T10:00:00Z" },
  { id: "a3", uniqueId: "ID-0003", result: E, sizes: [2, 3], householdSize: 1, firstSubmittedOn: "2027-01-06T08:00:00Z" },
  { id: "a4", uniqueId: "ID-0004", result: E, sizes: [2], householdSize: 2, firstSubmittedOn: "2027-01-07T08:00:00Z" },
  { id: "a5", uniqueId: "ID-0005", result: "Not eligible", sizes: [], householdSize: 2 },
  { id: "a6", uniqueId: "ID-0006", result: "Needs review", sizes: [], householdSize: 2 },
  { id: "a7", uniqueId: "ID-0007", result: E, sizes: [2], householdSize: 2, out: true }];
// ID-0003 (1 person) is tier 2 for a 2 bedroom and has no tier for a 3 bedroom, which is a problem to fix, not a silent skip
let built = S.buildEntries(pool, prio);
assert.strictEqual(built.problems.length, 1); assert.ok(built.problems[0].startsWith("ID-0003: the project's priorities have no tier for a household of 1 in 3 bedrooms homes"));
pool[2].sizes = [2]; pool[2].householdSize = 1;
pool[0].sizes = [2, 3];
built = S.buildEntries(pool, prio);
assert.deepStrictEqual(built.problems, []);
assert.deepStrictEqual(built.entries.map(e => [e.uniqueId, e.bedrooms, e.tier]),
  [["ID-0001", 2, 1], ["ID-0002", 2, 1], ["ID-0003", 2, 2], ["ID-0004", 2, 1], ["ID-0001", 3, 2]]);
assert.deepStrictEqual(built.entries[0], { applicationId: "a1", uniqueId: "ID-0001", bedrooms: 2, householdSize: 2, tier: 1, chances: 1, submittedOn: "2027-01-05T09:00:00Z" });
assert.deepStrictEqual(S.listSizes(built.entries), [2, 3]);
assert.strictEqual(S.tierFor(prio, 4, 6), 1, "4+ bedrooms matches a priority for 4 or more"); assert.strictEqual(S.tierFor(prio, 3, 6), null);
assert.ok(S.buildEntries([{ id: "x", result: E, sizes: [2], householdSize: 2 }], prio).problems[0].includes("no Unique ID"));
assert.ok(S.buildEntries([pool[0], { ...pool[1], uniqueId: "ID-0001" }], prio).problems[0].includes("on two applications"));

// ---- check numbers: MOD(SUM(row x (ID number x 100 + tier x 10 + chances)), 999983), list sorted by Unique ID
// 2 bedrooms: 1x(100+10+1) + 2x(200+10+1) + 3x(300+20+1) + 4x(400+10+1) = 111 + 422 + 963 + 1644 = 3140
// 3 bedrooms: 1x(100+20+1) = 121
const entries = built.entries;
assert.strictEqual(S.checkNumber(S.listOf(entries, 2)), 3140); assert.strictEqual(S.checkNumber(S.listOf(entries, 3)), 121);
assert.strictEqual(S.checkNumber(S.listOf(entries, 2).reverse()), 3140, "the order the list arrives in doesn't matter");
assert.strictEqual(S.checkText(entries), "2 bedrooms: 4 entries, check number 3140\n3 bedrooms: 1 entry, check number 121");
// any change shows: a different tier, a missing entry, an extra entry
const changed = entries.map(e => ({ ...e })); changed[2].tier = 1;
assert.notStrictEqual(S.checkNumber(S.listOf(changed, 2)), 3140);
assert.notStrictEqual(S.checkNumber(S.listOf(entries, 2).slice(1)), 3140);
assert.strictEqual(S.checkNumber(Array.from({ length: 400 }, (_, i) => ({ uniqueId: S.idText(i + 1), tier: 1, chances: 1 }))) < 999983, true);

// ---- the roll and the seed
assert.strictEqual(S.parseRoll("0384719265"), "0384719265"); assert.strictEqual(S.parseRoll(" 03847-19265 "), "0384719265");
assert.strictEqual(S.parseRoll("384719265"), null); assert.strictEqual(S.parseRoll("03847192650"), null); assert.strictEqual(S.parseRoll("03847x9265"), null);
assert.strictEqual(S.seedOf("0000000000"), 1); assert.strictEqual(S.seedOf("0384719265"), 384719266);
assert.strictEqual(S.seedOf("2147483646"), 1); assert.strictEqual(S.seedOf("2147483645"), 2147483646); assert.strictEqual(S.seedOf("9999999999"), 9999999999 % 2147483646 + 1);
// ---- the generator: the published Park-Miller sequence. From seed 1 the values run 16807, 282475249, 1622650073 ...
// and the 10,000th is 1043618065 (the check value Park and Miller give). The first 10 are thrown away.
assert.deepStrictEqual(S.generator(1, 5), [823564440, 1115438165, 1784484492, 74243042, 114807987]);
assert.strictEqual(S.generator(1, 9990)[9989], 1043618065);
assert.ok(S.generator(2147483646, 50).every(s => s >= 1 && s <= 2147483646 && Number.isInteger(s)));

// ---- the draw: households in Unique ID order each get the next value; the same number on every list they are on
let d = S.draw("0000000000", entries);
assert.strictEqual(d.seed, 1); assert.strictEqual(d.roll, "0000000000");
assert.deepStrictEqual(d.households, [{ uniqueId: "ID-0001", seq: 823564440, number: 0.3835020775 }, { uniqueId: "ID-0002", seq: 1115438165, number: 0.5194163721 },
  { uniqueId: "ID-0003", seq: 1784484492, number: 0.8309653461 }, { uniqueId: "ID-0004", seq: 74243042, number: 0.0345721105 }]);
const by = (size) => d.entries.filter(e => e.bedrooms === size).sort((x, y) => x.rank - y.rank).map(e => e.uniqueId);
// 2 bedrooms: tier 1 by lottery number, largest first (0002 .519, 0001 .384, 0004 .035), then tier 2 (0003, whatever its number)
assert.deepStrictEqual(by(2), ["ID-0002", "ID-0001", "ID-0004", "ID-0003"]);
assert.deepStrictEqual(by(3), ["ID-0001"]);
const e1 = d.entries.filter(e => e.uniqueId === "ID-0001");
assert.strictEqual(e1.length, 2); assert.strictEqual(e1[0].lotteryNumber, e1[1].lotteryNumber); assert.strictEqual(e1[0].lotterySeq, 823564440);
assert.strictEqual(e1[0].rankingKey, e1[0].lotteryNumber, "with one chance the ranking key is the lottery number");
assert.strictEqual(d.entries[0].applicationId, "a1"); assert.ok(!("key" in d.entries[0]));
// the same roll always gives the same result; a different roll gives a different one; the input isn't changed
assert.deepStrictEqual(S.draw("0000000000", entries), d); assert.ok(!("rank" in entries[0]));
assert.notDeepStrictEqual(S.draw("0000000001", entries).households, d.households);
assert.throws(() => S.draw("123", entries), /exactly ten digits/);
// extra chances: key = number ^ (1 / chances), so a household with 2 chances and number 0.25 has key 0.5
const w = S.draw("0000000000", [{ uniqueId: "ID-0001", bedrooms: 2, tier: 1, chances: 2 }, { uniqueId: "ID-0002", bedrooms: 2, tier: 1, chances: 1 }]);
assert.strictEqual(w.entries[0].rankingKey, Math.round(Math.sqrt(823564440 / 2147483647) * 1e10) / 1e10); assert.strictEqual(w.entries[0].rank, 1);
// every household gets a number in (0, 1), and a big pool has no ties in rank
const big = Array.from({ length: 500 }, (_, i) => ({ uniqueId: S.idText(i + 1), bedrooms: 2, tier: 1 + (i % 2), chances: 1 }));
const bd = S.draw("0384719265", big);
assert.ok(bd.households.every(h => h.number > 0 && h.number < 1));
assert.deepStrictEqual(bd.entries.map(e => e.rank).sort((a, b) => a - b), Array.from({ length: 500 }, (_, i) => i + 1));
assert.ok(bd.entries.filter(e => e.tier === 1).every(e => e.rank <= 250), "every tier 1 household ranks ahead of every tier 2 household");

// ---- first come, first served: tier, then the earlier first submission
const f = S.rankBySubmission(entries);
assert.deepStrictEqual(f.filter(e => e.bedrooms === 2).sort((x, y) => x.rank - y.rank).map(e => e.uniqueId), ["ID-0001", "ID-0002", "ID-0004", "ID-0003"]);
assert.ok(!("rank" in entries[0]));

// ---- how long the lists last
assert.strictEqual(S.listsEndOn("2026-12-03T18:30:00Z", 12), "2027-12-03"); assert.strictEqual(S.listsEndOn("2026-12-03", null), "2027-12-03");
assert.strictEqual(S.listsEndOn("2027-01-31", 1), "2027-02-28"); assert.strictEqual(S.listsEndOn("2026-08-31", 6), "2027-02-28");

// ---- the project at a glance, once invitations are out
const dapps = [{ id: "a1", result: E, fullAppSubmitted: "2026-11-20", stage: "Full application submitted" }, { id: "a2", result: E }, { id: "a3", result: E }, { id: "a4", result: E },
               { id: "a5", result: "Not eligible" }, { id: "a6", result: E, out: true }, { id: "a7", result: E }];
const dent = [
  { applicationId: "a1", bedrooms: 2, rank: 2, status: "Invited", invitedOn: "2026-11-16", responseDue: "2026-12-01" },
  { applicationId: "a1", bedrooms: 3, rank: 1, status: "Invited", invitedOn: "2026-11-16", responseDue: "2026-12-01" },
  { applicationId: "a2", bedrooms: 2, rank: 1, status: "Invited", invitedOn: "2026-11-16", responseDue: "2026-12-01" },
  { applicationId: "a3", bedrooms: 2, rank: 3, status: "Invited", invitedOn: "2026-11-02", responseDue: "2026-11-17" },
  { applicationId: "a4", bedrooms: 2, rank: 4, status: "Waitlist" },
  { applicationId: "a7", bedrooms: 2, rank: 5, status: "Invited", invitedOn: "2026-11-05T08:00:00Z", responseDue: "2026-11-20" },
  { applicationId: "a6", bedrooms: 2, rank: 6, status: "Invited", invitedOn: "2026-11-16", responseDue: "2026-12-01" }];
let board = S.dashboard(dapps, dent, "2026-11-20");
assert.deepStrictEqual(board.figures, { applications: 6, eligible: 5, listed: 5, invited: 4, submitted: 1, waiting: 2, late: 1, out: 0, certified: 0, notCertified: 0, toReview: 1 });
assert.deepStrictEqual(board.invited.map(r => r.review), ["", "", "", "To review"]);
// once it's reviewed, the row and the figures say how it came out
const certified = S.dashboard(dapps.map(a => a.id === "a1" ? { ...a, stage: "Certified" } : a), dent, "2026-11-20");
assert.strictEqual(certified.invited[3].review, "Certified"); assert.strictEqual(certified.figures.certified, 1); assert.strictEqual(certified.figures.toReview, 0);
assert.strictEqual(S.dashboard(dapps.map(a => a.id === "a1" ? { ...a, stage: "Not eligible" } : a), dent, "2026-11-20").invited[3].review, "Not certified");
const facts9 = { method: "Lottery", homes: 1, priorities: 1, costs: true, apps: [{ uniqueId: "ID-0001", result: E }], round: { status: "Certified" }, entries: 1 };
assert.deepStrictEqual(S.progress({ ...facts9, invited: board.figures }).slice(8).map(s => [s.id, s.state, s.summary]),
  [["invite", "byhand", "4 households invited, 1 full application in, 1 past their date."], ["review", "byhand", "1 full application in: 0 certified, 1 to review."]]);
assert.deepStrictEqual(S.progress({ ...facts9, invited: certified.figures })[9], { id: "review", title: "Review and certify", state: "done", summary: "1 full application in: 1 certified." });
assert.strictEqual(S.progress({ ...facts9, invited: { ...board.figures, submitted: 0, toReview: 0 } })[9].summary, "No full applications in yet.");
// late first, then waiting with the soonest date first, then the ones that are in; a withdrawn household is left out
assert.deepStrictEqual(board.invited.map(r => [r.applicationId, r.state, r.text]), [
  ["a3", "late", "Overdue by 3 days"], ["a7", "waiting", "Not yet, due today"], ["a2", "waiting", "Not yet, 11 days left"], ["a1", "in", "Submitted 2026-11-20"]]);
assert.deepStrictEqual(board.invited[3].lists, [{ bedrooms: 2, rank: 2 }, { bedrooms: 3, rank: 1 }], "a household on two lists is one row");
assert.strictEqual(board.invited[1].invitedOn, "2026-11-05");
assert.strictEqual(S.dashboard(dapps, dent, "2026-11-18").invited[0].text, "Overdue by 1 day");
// ---- a household drops out: it said no, or never answered. Every entry it has takes that status; it isn't waited for any more
const lists = [{ id: "e1", applicationId: "a1", bedrooms: 2, rank: 1, status: "Invited", invitedOn: "2026-11-16", uniqueId: "ID-0001" },
               { id: "e2", applicationId: "a1", bedrooms: 3, rank: 2, status: "Waitlist", uniqueId: "ID-0001" },
               { id: "e3", applicationId: "a2", bedrooms: 2, rank: 2, status: "Invited", invitedOn: "2026-11-16", uniqueId: "ID-0002" },
               { id: "e4", applicationId: "a3", bedrooms: 2, rank: 3, status: "Waitlist", uniqueId: "ID-0003" },
               { id: "e5", applicationId: "a4", bedrooms: 2, rank: 4, status: "Waitlist", uniqueId: "ID-0004" },
               { id: "e6", applicationId: "a5", bedrooms: 3, rank: 1, status: "Declined", uniqueId: "ID-0005" },
               { id: "e7", applicationId: "a6", bedrooms: 3, rank: null, status: "Waitlist", uniqueId: "ID-0006" }];
assert.deepStrictEqual(S.dropPlan("a1", lists), ["e1", "e2"], "both of its lists, the one it was invited on and the one it was waiting on");
assert.deepStrictEqual(S.dropPlan("a5", lists), [], "already out"); assert.deepStrictEqual(S.dropPlan("zz", lists), []);
assert.deepStrictEqual(S.nextUp("a1", lists), [{ bedrooms: 2, uniqueId: "ID-0003", rank: 3 }], "the best-ranked household still waiting; nobody is left on the 3 bedroom list (one declined, one unranked)");
assert.strictEqual(S.nextText(S.nextUp("a1", lists)), "Next on the 2 bedrooms list: ID-0003 (rank 3), not invited yet."); assert.strictEqual(S.nextText([]), "");
const dropped = lists.map(e => e.applicationId === "a1" ? { ...e, status: "Declined", statusDate: "2026-11-19", statusReason: "Bought another home" } : e);
assert.deepStrictEqual(S.restorePlan("a1", dropped), [{ id: "e1", status: "Invited" }, { id: "e2", status: "Waitlist" }], "put back as it was");
assert.deepStrictEqual(S.restorePlan("a2", dropped), []);
assert.deepStrictEqual(S.DROPS, ["Declined", "Unresponsive"]); assert.ok(S.DROPS.every(s => S.OUT.includes(s)));
assert.strictEqual(S.householdAfterDrop("Invited to full application", false), "Applicant");
assert.strictEqual(S.householdAfterDrop("Invited to full application", true), "", "still invited in another project");
assert.strictEqual(S.householdAfterDrop("Eligible", false), "", "a certified household keeps its status"); assert.strictEqual(S.householdAfterDrop("Homeowner", false), "");
assert.strictEqual(S.householdAfterRestore("Applicant", [{ status: "Invited" }]), "Invited to full application"); assert.strictEqual(S.householdAfterRestore("Applicant", [{ status: "Waitlist" }]), "");
assert.strictEqual(S.householdAfterRestore("Eligible", [{ status: "Invited" }]), "");
const gone = S.dashboard([{ id: "a1" }, { id: "a2" }], dropped, "2026-11-20");
assert.deepStrictEqual(gone.invited.map(r => [r.applicationId, r.state, r.text]), [["a2", "waiting", "Not yet (no due date)"], ["a1", "out", "Declined 2026-11-19"]], "dropped out: last, and not waited for");
assert.strictEqual(gone.invited[1].reason, "Bought another home"); assert.strictEqual(gone.figures.out, 1); assert.strictEqual(gone.figures.waiting, 1); assert.strictEqual(gone.figures.late, 0);
assert.ok(S.progress({ method: "Lottery", homes: 1, priorities: 1, costs: true, apps: [{ uniqueId: "ID-0001", result: E }], round: { status: "Certified" }, entries: 1, invited: gone.figures })[8].summary.endsWith(", 1 dropped out."));
assert.strictEqual(S.dashboard(dapps, dent, "2026-11-30").invited.find(r => r.applicationId === "a2").text, "Not yet, 1 day left");
assert.deepStrictEqual(S.dashboard(dapps, [], "2026-11-20").figures, { applications: 6, eligible: 5, listed: 0, invited: 0, submitted: 0, waiting: 0, late: 0, out: 0, certified: 0, notCertified: 0, toReview: 0 });
assert.strictEqual(S.progress({ method: "Lottery", homes: 1, priorities: 1, costs: true, apps: [{ uniqueId: "ID-0001", result: E }], round: { status: "Certified" }, entries: 1,
  invited: board.figures })[8].summary, "4 households invited, 1 full application in, 1 past their date.");

// ---- where the project is: the first step that isn't done is "next", the rest wait
const states = (facts) => S.progress(facts).map(s => s.id + ":" + s.state).join(" ");
const A = (uniqueId, result, out) => ({ uniqueId, result, out });
let facts = { method: "Lottery", homes: 5, priorities: 9, costs: true, apps: [], round: null, entries: 0 };
assert.strictEqual(states(facts), "setup:done applications:next close:waiting prescreen:waiting lists:waiting lock:waiting draw:waiting certify:waiting invite:waiting review:waiting");
assert.strictEqual(states({ ...facts, homes: 0 }).split(" ")[0], "setup:next");
assert.ok(S.progress({ ...facts, priorities: 0, costs: false })[0].summary.includes("priorities (who fits which home), monthly housing costs"));
facts.apps = [A("", E), A("", "")];
assert.ok(states(facts).startsWith("setup:done applications:done close:next prescreen:waiting"));
assert.strictEqual(S.progress(facts)[2].summary, "2 applications without a Unique ID.");
facts.apps = [A("ID-0001", E), A("ID-0002", "")];
assert.ok(states(facts).startsWith("setup:done applications:done close:done prescreen:next lists:waiting"));
facts.apps = [A("ID-0001", E), A("ID-0002", "Needs review"), A("ID-0003", "Not eligible"), A("", "", true)];
assert.ok(states(facts).includes("prescreen:next"), "a household still to review holds the lists back");
assert.strictEqual(S.progress(facts)[3].summary, "1 household eligible, 1 not eligible, 1 to review: decide these before building the lists.");
facts.apps[1].result = "Not eligible";
assert.ok(states(facts).includes("prescreen:done lists:next lock:waiting"));
facts.round = { status: "Open" }; facts.entries = 3;
assert.ok(states(facts).includes("lists:done lock:next draw:waiting")); assert.strictEqual(S.progress(facts)[4].summary, "3 list entries.");
facts.round = { status: "Pools locked" }; assert.ok(states(facts).includes("lock:done draw:next certify:waiting"));
facts.round = { status: "Drawn" }; assert.ok(states(facts).includes("draw:done certify:next invite:waiting"));
facts.round = { status: "Certified" }; assert.ok(states(facts).endsWith("certify:done invite:byhand review:waiting"));
assert.strictEqual(S.progress({ ...facts, method: "First come first served" })[6].title, "Rank by first submission");
// an application that arrives after the lists are locked shows as needing a Unique ID, without undoing the lock
facts.apps.push(A("", ""));
assert.ok(states(facts).includes("close:next") && states(facts).includes("lock:done"));
assert.ok(JSON.stringify(S.progress(facts)).indexOf("\u2014") < 0);
console.log("ok");
"""


PDF_JS = r"""
const S = require(process.argv[process.argv.length - 2]), P = require(process.argv[process.argv.length - 1]);
const entries = S.draw("0384719265", Array.from({ length: 90 }, (_, i) => ({ uniqueId: S.idText(i + 1), bedrooms: 2 + (i % 2), householdSize: 2 + (i % 3), tier: 1 + (i % 2), chances: 1 }))).entries;
const info = { project: "Maple Court (phase 1) caf\u00e9", method: "Lottery", lockedOn: "2026-12-01", observer: "Pat Lee", roll: "0384719265", seed: 384719266, drawnOn: "2026-12-03", entries };
process.stdout.write(Buffer.concat([Buffer.from(P.make(S.listsDocument(info)), "latin1"), Buffer.from("\n=====\n"), Buffer.from(P.make(S.resultsDocument(info)), "latin1")]));
"""


def check_pdf(name, data):
    """A PDF reader finds every object where the file says it is, each page's length is right, and the text is escaped."""
    assert data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF"), name
    start = int(re.search(rb"startxref\n(\d+)\n%%EOF", data)[1])
    assert data[start:start + 4] == b"xref", f"{name}: the table of contents isn't where the file says"
    rows = re.findall(rb"(\d{10}) 00000 n \n", data[start:])
    assert len(rows) >= 6
    for i, off in enumerate(rows, 1):
        assert data[int(off):].startswith(f"{i} 0 obj".encode()), f"{name}: object {i} isn't where the table says"
    for m in re.finditer(rb"<< /Length (\d+) >>\nstream\n", data):
        end = m.end() + int(m[1])
        assert data[end:end + 11] == b"\nendstream\n", f"{name}: a page's length is wrong"
    pages = int(re.search(rb"/Count (\d+)", data)[1])
    assert pages >= 2 and data.count(b"/Type /Page ") == pages, name
    text = data.decode("latin1")
    assert "(ID-0090)" in text and "Board Observer: Pat Lee" in text and f"Page {pages} of {pages}" in text, name
    assert "caf\\351" in text and "\\(phase 1\\)" in text, f"{name}: accents and brackets must be escaped"
    if name == "results":
        assert "How to check this draw" in text and "Dice roll 0384719265, seed 384719266" in text


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the selection rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "selection.js")], capture_output=True, text=True)
    if r.returncode != 0 or r.stdout.strip() != "ok":
        sys.exit("Selection rules failed:\n" + r.stdout + r.stderr)

    import app_spec_intake as intake
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES
    PREFIX = "clt"
    rules = open(os.path.join(web, "selection.js")).read()
    page = open(os.path.join(web, "selection.html")).read()
    pages = open(os.path.join(web, "pages.js")).read()
    assert intake.PAGES["selection"] == ("Buyer Selection", "clt_/pages/selection.html")
    assert "page:selection" in dict(intake.NAVIGATION)["Projects"]
    for res in ("clt_/pages/selection.html", "clt_/pages/selection.js", "clt_/pages/pages.js"):
        assert res in intake.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    assert page.index('src="pages.js"') < page.index('src="selection.js"') < page.index("CLTSelection")
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules, pages):
        p = subprocess.run([node, "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    # changes that must all happen together go through one change set
    assert "function batch(" in pages and "function batchBody(" in pages and script.count("P.batch(") >= 3
    # every clt_ name is real: a column of a table the page touches, a table, a choice or a relationship
    tables = {t["name"]: t for t in TABLES}
    used_tables = ("project", "application", "projecthome", "projectpriority", "projectband", "selectionround", "selectionentry", "household")
    known = {f"{PREFIX}_name", f"{PREFIX}_projects", f"{PREFIX}_applications"}
    for t in used_tables:
        known |= {f"{PREFIX}_{c['name']}" for c in tables[t]["columns"]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    known |= {f"{PREFIX}_{parent}_{child}_{col}" for child, col, parent, *_ in LOOKUPS}
    used = set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script)) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    assert "clt_selectionround_selectionentry_round" in script
    # the labels the page and the rules rely on are choices in the schema
    for name, labels in (("roundstatus", ["Open", "Pools locked", "Drawn", "Certified", "Closed"]), ("entrystatus", ["Waitlist"]),
                         ("applicationstage", ["In selection", "Pre-screened", "Screener submitted", "Withdrawn"]),
                         ("projectstatus", ["Selection", "Planning", "Accepting applications", "Closed"]),
                         ("selectionmethod", ["Lottery", "First come first served"]),
                         ("prescreenresult", ["Eligible for selection", "Needs review"])):
        for label in labels:
            assert label in CHOICES[name][1], (name, label)
            assert label in script or label in rules, label
    assert re.search(r"SIZES = \[(.*?)\]", rules)[1].replace('"', "").split(", ") == CHOICES["homesize"][1]
    # the lists the observer sees never show names: the page asks for no name or household column of an application
    apps_query = re.search(r'clt_applications\?\$select=([^"]+)"\s*\+\s*"([^"]+)"', script)
    assert apps_query and "clt_name" not in apps_query[1] + apps_query[2] and "household_value" not in apps_query[1] + apps_query[2]
    # names are loaded in one place only, and only once the results are certified and someone has been invited
    assert script.count("loadNames(") == 2 and re.search(r'=== "Certified" && D\.entries\.some\(function \(e\) \{ return e\.invitedOn; \}\)\) return loadNames\(', script)
    # households are still read only after certification (loadNames), and when one of the invited drops out
    assert script.count("_clt_household_value") == 4 and script.index("_clt_household_value") > script.index("function loadNames(")
    for piece in ("S.dropPlan(", "S.restorePlan(", "S.nextUp(", "S.householdAfterDrop(", "S.householdAfterRestore(", 'data-act="drop"', 'data-act="undrop"', 'id="dropreason"',
                  "clt_statusreason", "clt_statusdate", "objectid_clt_application@odata.bind"):
        assert piece in script, piece
    assert {"Declined", "Unresponsive", "Removed", "Withdrawn"} <= set(CHOICES["entrystatus"][1]) and {"Applicant", "Invited to full application"} <= set(CHOICES["householdstatus"][1])
    # the generator constants are the published ones
    assert "M = 2147483647, A = 16807, WARMUP = 10" in rules and "CHECK_MOD = 999983" in rules
    # the documents the observer signs are real PDF files: build both and check their structure
    doc = subprocess.run([node, "-e", PDF_JS, os.path.join(web, "selection.js"), os.path.join(web, "pdf.js")], capture_output=True)
    assert doc.returncode == 0, doc.stderr.decode()[-600:]
    for name, data in zip(("lists", "results"), doc.stdout.split(b"\n=====\n")):
        check_pdf(name, data)
    assert "window.print" not in page and "clt_/pages/pdf.js" in intake.WEB_RESOURCES and 'src="pdf.js"' in page
    assert "\u2014" not in page and "\u2014" not in rules
    print("OK: selection rules give the expected Unique IDs, lists, check numbers, draw and ranks for each worked example "
          "(the generator matches the published Park-Miller values); the page is in the app and uses only real columns and choices.")


if __name__ == "__main__":
    main()
