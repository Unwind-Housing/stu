// Selection: the rules behind the guided page that runs a project's lottery (or first come, first served list)
// and shows where the project is in the process. Deployed as clt_/pages/selection.js by build_app.py.
// Plain functions with no Dataverse calls, so tests/test_selection.py runs them in Node on worked examples,
// and so anyone can check a draw by hand. Design: docs/DESIGN.md, "Blind lottery" and "Selection".
//
// The order of things, and what makes it fair:
//   1. Close applications: every application gets a Unique ID (ID-0001, ID-0002 ...) in the order the screeners
//      were first submitted. The clock decides, nobody types them. Screener answers freeze.
//   2. Pre-screen: the project's written rules decide who is eligible, and for which home sizes.
//   3. Build the lists: one list per home size. Each eligible household goes on the list for every size it is
//      eligible for, in its priority tier.
//   4. Lock: each list gets a check number worked out from its contents, so any later change would show.
//   5. Draw: ten rolls of a ten-sided die give a seed. From the seed, each household gets one lottery number,
//      in Unique ID order, used on every list it is on. Each list is ranked by tier, then lottery number.
//   6. Certify: the observer signs the results. The same rolls always give the same order.
// Lists show Unique IDs only, never names.
var CLTSelection = (function () {
  var M = 2147483647, A = 16807, WARMUP = 10;   // the published Park-Miller "minimal standard" generator
  var CHECK_MOD = 999983;
  var SIZES = ["Studio", "1 bedroom", "2 bedrooms", "3 bedrooms", "4+ bedrooms"];
  var LOTTERY = "Lottery", FCFS = "First come first served";

  function blank(v) { return v === undefined || v === null || v === ""; }
  function sizeName(size) { return SIZES[Math.min(size, 4)]; }
  // "2 bedrooms; 3 bedrooms" (how Dataverse shows a multi-select) -> [2, 3]
  function sizesFromLabels(text) {
    return (text || "").split(";").map(function (s) { return SIZES.indexOf(s.trim()); })
      .filter(function (i) { return i >= 0; }).sort();
  }
  // "ID-0007" -> 7
  function idNumber(uniqueId) { var m = /(\d+)\s*$/.exec(uniqueId || ""); return m ? parseInt(m[1], 10) : null; }
  function idText(n) { var s = String(n); while (s.length < 4) s = "0" + s; return "ID-" + s; }

  // ---------------------------------------------------------------- 1. Unique IDs
  // apps: [{ id, uniqueId, firstSubmittedOn, out }]   out = withdrawn, so it gets no ID
  // -> [{ id, uniqueId }] for the applications that need one, numbered after any that already have one,
  //    in the order the screeners were first submitted (earliest first).
  function assignIds(apps) {
    var next = 1;
    apps.forEach(function (a) { var n = idNumber(a.uniqueId); if (n !== null && n >= next) next = n + 1; });
    return apps.filter(function (a) { return blank(a.uniqueId) && !a.out; })
      .sort(function (a, b) {
        var x = a.firstSubmittedOn || "9999", y = b.firstSubmittedOn || "9999";
        return x < y ? -1 : x > y ? 1 : String(a.id) < String(b.id) ? -1 : 1;
      })
      .map(function (a) { return { id: a.id, uniqueId: idText(next++) }; });
  }

  // ---------------------------------------------------------------- 3. the lists
  // The tier a household of this size gets for a home size, from the project's priorities; null = may not apply.
  function tierFor(priorities, size, people) {
    var best = null;
    priorities.forEach(function (p) {
      if (p.householdSize !== people || (size >= 4 ? p.bedrooms < 4 : p.bedrooms !== size)) return;
      var t = blank(p.tier) ? 1 : p.tier;
      if (best === null || t < best) best = t;
    });
    return best;
  }

  // apps: [{ id, uniqueId, result, sizes: [size], householdSize, firstSubmittedOn, out }]
  // -> { entries: [{ applicationId, uniqueId, bedrooms, householdSize, tier, chances, submittedOn }], problems: [...] }
  // One entry per eligible household per home size it is eligible for. Problems stop the build.
  function buildEntries(apps, priorities) {
    var entries = [], problems = [], seen = {};
    apps.forEach(function (a) {
      if (a.out || a.result !== "Eligible for selection") return;
      if (blank(a.uniqueId)) { problems.push("An eligible application has no Unique ID. Close applications first."); return; }
      if (seen[a.uniqueId]) { problems.push(a.uniqueId + " is on two applications."); return; }
      seen[a.uniqueId] = 1;
      if (!(a.sizes || []).length) { problems.push(a.uniqueId + " is eligible but has no home sizes from the pre-screen. Run the pre-screen again."); return; }
      a.sizes.forEach(function (size) {
        var tier = tierFor(priorities, size, a.householdSize);
        if (tier === null) { problems.push(a.uniqueId + ": the project's priorities have no tier for a household of " + a.householdSize + " in " + sizeName(size).toLowerCase() + " homes. Run the pre-screen again."); return; }
        entries.push({ applicationId: a.id, uniqueId: a.uniqueId, bedrooms: size, householdSize: a.householdSize, tier: tier,
                       chances: 1, submittedOn: a.firstSubmittedOn || null });
      });
    });
    entries.sort(function (x, y) { return x.bedrooms - y.bedrooms || idNumber(x.uniqueId) - idNumber(y.uniqueId); });
    return { entries: entries, problems: problems };
  }

  // The home sizes that have a list, smallest first.
  function listSizes(entries) {
    var seen = {};
    entries.forEach(function (e) { seen[e.bedrooms] = 1; });
    return Object.keys(seen).map(Number).sort(function (a, b) { return a - b; });
  }
  function listOf(entries, size) { return entries.filter(function (e) { return e.bedrooms === size; }); }

  // ---------------------------------------------------------------- 4. check numbers
  // A list's check number: sort it by Unique ID, then
  //   MOD( SUM( row x (Unique ID number x 100 + tier x 10 + chances) ), 999983 ),   row = 1, 2, 3 ...
  // It is a plain checksum, not a secret: change, add or remove an entry and the number changes.
  function checkNumber(list) {
    var sum = 0;
    list.slice().sort(function (x, y) { return idNumber(x.uniqueId) - idNumber(y.uniqueId); })
      .forEach(function (e, i) { sum += (i + 1) * (idNumber(e.uniqueId) * 100 + e.tier * 10 + (e.chances || 1)); });
    return sum % CHECK_MOD;
  }
  // [{ size, name, count, check }] for every list
  function checkNumbers(entries) {
    return listSizes(entries).map(function (size) {
      var list = listOf(entries, size);
      return { size: size, name: sizeName(size), count: list.length, check: checkNumber(list) };
    });
  }
  // What is kept on the round: one line per list.
  function checkText(entries) {
    return checkNumbers(entries).map(function (c) {
      return c.name + ": " + c.count + (c.count === 1 ? " entry" : " entries") + ", check number " + c.check;
    }).join("\n");
  }

  // ---------------------------------------------------------------- 5. the draw
  // The roll: ten digits, read in order from ten rolls of a ten-sided die. Spaces and dashes are ignored.
  function parseRoll(text) {
    var digits = String(text == null ? "" : text).replace(/[\s-]/g, "");
    return /^\d{10}$/.test(digits) ? digits : null;
  }
  // seed = MOD(roll, 2147483646) + 1: every roll gives a seed from 1 to 2,147,483,646, never 0.
  function seedOf(roll) { return parseInt(roll, 10) % (M - 1) + 1; }
  // s = MOD(previous s x 16807, 2147483647). The first 10 values are thrown away (a small seed's first values
  // aren't well mixed), then `count` values are returned.
  function generator(seed, count) {
    var s = seed, out = [], i;
    for (i = 0; i < WARMUP; i++) s = s * A % M;
    for (i = 0; i < count; i++) { s = s * A % M; out.push(s); }
    return out;
  }
  function round10(n) { return Math.round(n * 1e10) / 1e10; }

  // Rank every list: tier first (1 ahead of 2), then `better` decides within a tier. Ties go to the lower Unique ID.
  function rankLists(entries, better) {
    listSizes(entries).forEach(function (size) {
      listOf(entries, size).sort(function (x, y) {
        return x.tier - y.tier || better(x, y) || idNumber(x.uniqueId) - idNumber(y.uniqueId);
      }).forEach(function (e, i) { e.rank = i + 1; });
    });
    return entries;
  }

  // draw(roll, entries) -> { roll, seed, households: [{ uniqueId, seq, number }], entries: [...] }
  // Households are taken in Unique ID order; each gets the next generator value s, and its lottery number is
  // s / 2147483647. A household on several lists has the same number on each. Ranking key = number ^ (1 / chances),
  // which is just the number when chances is 1. Larger ranks first within a tier.
  function draw(roll, entries) {
    var digits = parseRoll(roll);
    if (!digits) throw new Error("The roll must be exactly ten digits.");
    var seed = seedOf(digits), ids = {}, order;
    entries.forEach(function (e) { ids[e.uniqueId] = 1; });
    order = Object.keys(ids).sort(function (a, b) { return idNumber(a) - idNumber(b); });
    var values = generator(seed, order.length), by = {};
    var households = order.map(function (uniqueId, i) {
      by[uniqueId] = values[i];
      return { uniqueId: uniqueId, seq: values[i], number: round10(values[i] / M) };
    });
    var ranked = entries.map(function (e) {
      var s = by[e.uniqueId], u = s / M, w = e.chances || 1;
      var out = {}; Object.keys(e).forEach(function (k) { out[k] = e[k]; });
      out.lotterySeq = s; out.lotteryNumber = round10(u); out.key = Math.pow(u, 1 / w); out.rankingKey = round10(out.key);
      return out;
    });
    rankLists(ranked, function (x, y) { return y.key - x.key; });
    ranked.forEach(function (e) { delete e.key; });
    return { roll: digits, seed: seed, households: households, entries: ranked };
  }

  // First come, first served: no dice. Within a tier, the earlier first submission ranks first.
  function rankBySubmission(entries) {
    var ranked = entries.map(function (e) { var out = {}; Object.keys(e).forEach(function (k) { out[k] = e[k]; }); return out; });
    return rankLists(ranked, function (x, y) {
      var a = x.submittedOn || "9999", b = y.submittedOn || "9999";
      return a < b ? -1 : a > b ? 1 : 0;
    });
  }

  // The day the lists stop being used: the draw date plus the project's months (12 when blank). "yyyy-mm-dd".
  function listsEndOn(drawDate, months) {
    var d = new Date(String(drawDate).slice(0, 10) + "T00:00:00Z"), day = d.getUTCDate();
    d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() + (blank(months) ? 12 : months));
    var last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
    d.setUTCDate(Math.min(day, last));
    return d.toISOString().slice(0, 10);
  }

  // ---------------------------------------------------------------- the documents the observer signs
  // info: { project, method, lockedOn, observer, roll, seed, drawnOn, entries }   dates as "yyyy-mm-dd"
  // -> a document for CLTPdf.make (pdf.js). Unique IDs only, never names.
  function listsDocument(info) {
    var blocks = [{ p: info.method + ". Lists locked " + info.lockedOn + ". Unique IDs only: no names appear on these lists." },
                  { p: "Each list's check number is worked out from its contents. If an entry were added, removed or changed after the lock, the number would no longer match." }];
    checkNumbers(info.entries).forEach(function (c) {
      blocks.push({ h: c.name + ": " + c.count + (c.count === 1 ? " household" : " households") + ", check number " + c.check });
      blocks.push({ table: { columns: [{ label: "Unique ID", width: 110 }, { label: "Household size", width: 110, align: "right" }, { label: "Tier", width: 70, align: "right" }],
        rows: listOf(info.entries, c.size).slice().sort(function (x, y) { return idNumber(x.uniqueId) - idNumber(y.uniqueId); })
          .map(function (e) { return [e.uniqueId, e.householdSize, e.tier]; }) } });
    });
    blocks.push({ h: "Reviewed before the draw" }, { sign: ["Board Observer: " + (info.observer || ""), "Staff"] });
    return { title: info.project + ": lists at the lock", footer: info.project + ", lists locked " + info.lockedOn, blocks: blocks };
  }
  function resultsDocument(info) {
    var lottery = info.method !== FCFS, ids = {}, households = [];
    var blocks = [{ p: info.method + ". Lists locked " + info.lockedOn + (lottery ? ". Drawn " + info.drawnOn + "." : ". Ranked " + info.drawnOn + ".") +
                       " Unique IDs only: no names appear on these results." }];
    if (lottery) blocks.push({ p: "Dice roll " + info.roll + ", seed " + info.seed + ".", bold: true });
    blocks.push({ p: "Each list is ranked by tier first (tier 1 ahead of tier 2), then by " +
                     (lottery ? "lottery number, largest first. A household has the same lottery number on every list it is on." : "when the household first applied, earliest first.") });
    checkNumbers(info.entries).forEach(function (c) {
      blocks.push({ h: c.name + ": " + c.count + (c.count === 1 ? " household" : " households") + ", check number " + c.check });
      blocks.push({ table: { columns: [{ label: "Rank", width: 50, align: "right", bold: true }, { label: "Unique ID", width: 100 }, { label: "Household size", width: 100, align: "right" },
                                       { label: "Tier", width: 60, align: "right" }, { label: lottery ? "Lottery number" : "First submitted", width: 130, align: "right" }],
        rows: listOf(info.entries, c.size).slice().sort(function (x, y) { return x.rank - y.rank; }).map(function (e) {
          return [e.rank, e.uniqueId, e.householdSize, e.tier,
                  lottery ? Number(e.lotteryNumber).toFixed(10) : String(e.submittedOn || "").replace("T", " ").slice(0, 16)]; }) } });
    });
    if (lottery) {
      info.entries.forEach(function (e) { if (!ids[e.uniqueId]) { ids[e.uniqueId] = 1; households.push(e); } });
      households.sort(function (x, y) { return idNumber(x.uniqueId) - idNumber(y.uniqueId); });
      blocks.push({ h: "How to check this draw" },
        { p: "Anyone can repeat the draw from the dice roll. Seed = (roll, as a number) mod " + (M - 1) + ", plus 1. Then, starting from the seed, " +
             "work out s = (previous s x " + A + ") mod " + M + " over and over. Throw away the first " + WARMUP + " values. Taking households in Unique ID order, " +
             "each gets the next value of s, and its lottery number is s divided by " + M + "." },
        { table: { columns: [{ label: "Unique ID", width: 110 }, { label: "Value of s", width: 130, align: "right" }, { label: "Lottery number", width: 130, align: "right" }],
                   rows: households.map(function (e) { return [e.uniqueId, e.lotterySeq, Number(e.lotteryNumber).toFixed(10)]; }) } });
    }
    blocks.push({ h: "Certified" }, { sign: ["Board Observer: " + (info.observer || ""), "Staff"] });
    return { title: info.project + ": ranked results", footer: info.project + (lottery ? ", dice roll " + info.roll : "") + ", " + info.drawnOn, blocks: blocks };
  }

  // ---------------------------------------------------------------- the project at a glance
  // apps:    [{ id, result, out, fullAppSubmitted, stage }]     fullAppSubmitted = the date their full application arrived
  // entries: [{ applicationId, bedrooms, rank, status, invitedOn, responseDue }]
  // -> { figures: { applications, eligible, listed, invited, submitted, waiting, late, certified, notCertified, toReview },
  //      invited: [{ applicationId, lists: [{ bedrooms, rank }], invitedOn, due, submittedOn, state, days, text, review }] }
  // review (once the full application is in): "Certified", "Not certified" or "To review", from the application's stage.
  // A household counts as invited once any of its list entries has an invited date. state: late | waiting | in.
  // Late ones come first, then the ones waiting (soonest due first), then the ones whose application is in.
  function dashboard(apps, entries, today) {
    var day = function (d) { return d ? String(d).slice(0, 10) : ""; }, t = day(today);
    var between = function (a, b) { return Math.round((new Date(b + "T00:00:00Z") - new Date(a + "T00:00:00Z")) / 86400000); };
    var active = apps.filter(function (a) { return !a.out; }), by = {}, listed = {}, rows = [];
    active.forEach(function (a) { by[a.id] = a; });
    entries.forEach(function (e) {
      if (!by[e.applicationId]) return;
      listed[e.applicationId] = 1;
      if (!e.invitedOn) return;
      var row = rows.filter(function (r) { return r.applicationId === e.applicationId; })[0];
      if (!row) { row = { applicationId: e.applicationId, lists: [], invitedOn: day(e.invitedOn), due: day(e.responseDue) }; rows.push(row); }
      row.lists.push({ bedrooms: e.bedrooms, rank: e.rank });
      if (day(e.invitedOn) < row.invitedOn) row.invitedOn = day(e.invitedOn);
      if (day(e.responseDue) && (!row.due || day(e.responseDue) < row.due)) row.due = day(e.responseDue);
    });
    rows.forEach(function (r) {
      r.lists.sort(function (x, y) { return x.bedrooms - y.bedrooms; });
      r.submittedOn = day(by[r.applicationId].fullAppSubmitted);
      var stage = by[r.applicationId].stage;
      r.review = !r.submittedOn ? "" : stage === "Certified" ? "Certified" : stage === "Not eligible" ? "Not certified" : "To review";
      if (r.submittedOn) { r.state = "in"; r.days = 0; r.text = "Submitted " + r.submittedOn; return; }
      if (!r.due) { r.state = "waiting"; r.days = 0; r.text = "Not yet (no due date)"; return; }
      r.days = between(t, r.due);
      r.state = r.days < 0 ? "late" : "waiting";
      r.text = r.days < 0 ? "Overdue by " + (-r.days) + (r.days === -1 ? " day" : " days")
             : r.days === 0 ? "Not yet, due today" : "Not yet, " + r.days + (r.days === 1 ? " day left" : " days left");
    });
    var order = { late: 0, waiting: 1, "in": 2 };
    rows.sort(function (x, y) {
      return order[x.state] - order[y.state] || (x.state === "in" ? (x.submittedOn < y.submittedOn ? -1 : 1) : (x.due || "9999") < (y.due || "9999") ? -1 : (x.due || "9999") > (y.due || "9999") ? 1 : 0);
    });
    var n = function (state) { return rows.filter(function (r) { return r.state === state; }).length; };
    return { figures: { applications: active.length, eligible: active.filter(function (a) { return a.result === "Eligible for selection"; }).length,
                        listed: Object.keys(listed).length, invited: rows.length, submitted: n("in"), waiting: n("waiting"), late: n("late"),
                        certified: rows.filter(function (r) { return r.review === "Certified"; }).length,
                        notCertified: rows.filter(function (r) { return r.review === "Not certified"; }).length,
                        toReview: rows.filter(function (r) { return r.review === "To review"; }).length },
             invited: rows };
  }

  // ---------------------------------------------------------------- where the project is in the process
  // facts: { method, homes, priorities, costs (home sizes with a monthly cost), apps: [{ uniqueId, result, out }],
  //          round: { status } or null, entries (how many), invited: the dashboard's figures (optional) }
  // -> [{ id, title, state, summary }]   state: done | next | waiting | byhand
  // "next" is the first step that isn't done; the steps after it wait.
  function progress(f) {
    var apps = (f.apps || []).filter(function (a) { return !a.out; }), n = apps.length;
    var count = function (test) { return apps.filter(test).length; };
    var noId = count(function (a) { return blank(a.uniqueId); });
    var eligible = count(function (a) { return a.result === "Eligible for selection"; });
    var review = count(function (a) { return a.result === "Needs review"; });
    var untested = count(function (a) { return blank(a.result); });
    var status = f.round ? f.round.status : "", lottery = f.method !== FCFS;
    var at = ["", "Open", "Pools locked", "Drawn", "Certified", "Closed"].indexOf(status);
    var plural = function (k, word) { return k + " " + word + (k === 1 ? "" : "s"); };
    var missing = [];
    if (!f.homes) missing.push("homes"); if (!f.priorities) missing.push("priorities (who fits which home)");
    if (!f.costs) missing.push("monthly housing costs");
    var steps = [
      { id: "setup", title: "Set up the project", done: !missing.length,
        summary: missing.length ? "Still needed on the project: " + missing.join(", ") + "." : plural(f.homes, "home") + ", " + (lottery ? "lottery" : "first come, first served") + "." },
      { id: "applications", title: "Add applications", done: n > 0,
        summary: n ? plural(n, "application") + " in the project." : "No applications in the project yet." },
      { id: "close", title: "Close applications", done: n > 0 && noId === 0,
        summary: !n ? "" : noId ? plural(noId, "application") + " without a Unique ID." : "Every application has a Unique ID. Screener answers are frozen." },
      { id: "prescreen", title: "Pre-screen", done: n > 0 && untested === 0 && review === 0,
        summary: !n ? "" : untested === n ? "Not run yet."
          : plural(eligible, "household") + " eligible, " + (n - eligible - review - untested) + " not eligible" +
            (review ? ", " + review + " to review: decide these before building the lists" : "") + (untested ? ", " + untested + " not tested yet" : "") + "." },
      { id: "lists", title: "Build the lists", done: at >= 1 && f.entries > 0,
        summary: at >= 1 ? plural(f.entries, "list entry").replace("entrys", "entries") + "." : "" },
      { id: "lock", title: "Lock the lists", done: at >= 2, summary: at >= 2 ? "Locked. Nothing on the lists can change." : "" },
      { id: "draw", title: lottery ? "Draw" : "Rank by first submission", done: at >= 3,
        summary: at >= 3 ? (lottery ? "Drawn. Every list is ranked." : "Ranked by when each household first applied.") : "" },
      { id: "certify", title: "Certify the results", done: at >= 4, summary: at >= 4 ? "Certified." : "" },
      { id: "invite", title: "Invite the top households", done: false, summary: "" },
      { id: "review", title: "Review and certify", done: false, summary: "" }
    ];
    var found = false;
    return steps.map(function (s) {
      var state = s.done ? "done" : found ? "waiting" : "next";
      if (!s.done) found = true;
      if (s.id === "invite" && at >= 4) state = "byhand";
      var summary = s.summary;
      if (s.id === "invite" && at >= 4 && f.invited) summary = plural(f.invited.invited, "household") + " invited, " + f.invited.submitted + " full " +
        (f.invited.submitted === 1 ? "application" : "applications") + " in" + (f.invited.late ? ", " + f.invited.late + " past their date" : "") + ".";
      if (s.id === "review") {
        var v = f.invited || {};
        state = at >= 4 && v.submitted ? (v.toReview ? "byhand" : "done") : "waiting";
        if (at >= 4 && v.submitted) summary = plural(v.submitted, "full application") + " in: " + v.certified + " certified" +
          (v.notCertified ? ", " + v.notCertified + " not certified" : "") + (v.toReview ? ", " + v.toReview + " to review" : "") + ".";
        else if (at >= 4 && v.invited) summary = "No full applications in yet.";
      }
      return { id: s.id, title: s.title, state: state, summary: summary };
    });
  }

  var api = { M: M, A: A, WARMUP: WARMUP, CHECK_MOD: CHECK_MOD, SIZES: SIZES, LOTTERY: LOTTERY, FCFS: FCFS,
              sizeName: sizeName, sizesFromLabels: sizesFromLabels, idNumber: idNumber, idText: idText,
              assignIds: assignIds, tierFor: tierFor, buildEntries: buildEntries, listSizes: listSizes, listOf: listOf,
              checkNumber: checkNumber, checkNumbers: checkNumbers, checkText: checkText,
              parseRoll: parseRoll, seedOf: seedOf, generator: generator, draw: draw,
              rankBySubmission: rankBySubmission, listsEndOn: listsEndOn, listsDocument: listsDocument,
              resultsDocument: resultsDocument, dashboard: dashboard, progress: progress };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
