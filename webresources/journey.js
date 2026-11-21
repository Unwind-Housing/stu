// A project's journey: the steps from a new project to certified buyers, and where each project picks up (deployed
// as clt_/pages/journey.js by build_app.py). The rules are plain, with no Dataverse calls, so tests/test_journey.py
// runs them in Node on worked examples. bar() draws the row of steps at the top of each project page.
var CLTJourney = (function () {
  var STEPS = [
    { key: "assign",    label: "Add people",         page: "clt_/pages/assign.html" },
    { key: "prescreen", label: "Pre-screen",         page: "clt_/pages/prescreen.html" },
    { key: "selection", label: "Buyer Selection",    page: "clt_/pages/selection.html" },
    { key: "invite",    label: "Invite",             page: "clt_/pages/invite.html" },
    { key: "certify",   label: "Review and certify", page: "clt_/pages/certify.html" }
  ];
  var CLOSED = "Closed", DRAWING = ["Open", "Pools locked", "Drawn"];
  // The page that shows one project's progress through the steps, and leads into each.
  var OVERVIEW = "clt_/pages/project.html";

  function step(key) { return STEPS.filter(function (s) { return s.key === key; })[0] || null; }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : many); }

  // Where a project picks up.
  //   facts: { status: the project's status, applications: screeners in it, untested: those with no pre-screen result,
  //            round: its newest selection round's status ("" when it has none), invited: households invited so far }
  // -> { key, label, page, why } for the step to do next, or null for a closed project
  function next(facts) {
    var f = facts || {}, n = f.applications || 0, key, why;
    if (f.status === CLOSED) return null;
    if (!n) { key = "assign"; why = "No screeners in it yet"; }
    else if (!f.round && f.untested > 0) { key = "prescreen"; why = plural(n, "screener", "screeners") + ", " + f.untested + " still to pre-screen"; }
    else if (!f.round) { key = "selection"; why = plural(n, "screener", "screeners") + ", all pre-screened: ready for buyer selection"; }
    else if (DRAWING.indexOf(f.round) >= 0) { key = "selection"; why = "Buyer selection is under way (" + f.round.toLowerCase() + ")"; }
    else if (!f.invited) { key = "invite"; why = "The results are certified: invite households to the full application"; }
    else { key = "certify"; why = plural(f.invited, "household", "households") + " invited: review their applications as they come in"; }
    var s = step(key);
    return { key: s.key, label: s.label, page: s.page, why: why };
  }

  // One project's progress, step by step, for its overview.
  //   facts: as for next(), plus eligible (screeners the pre-screen passed) and certified (households certified)
  // -> [{ key, label, page, state: "done" | "next" | "waiting", line: where it stands in a few words }]
  function track(facts) {
    var f = facts || {}, n = f.applications || 0, nx = next(f), settled = !!f.round && DRAWING.indexOf(f.round) < 0;
    var done = { assign: n > 0, prescreen: n > 0 && !f.untested, selection: settled, invite: f.invited > 0, certify: f.status === CLOSED };
    var line = {
      assign: n ? plural(n, "screener", "screeners") + " in the project" : "Nobody in the project yet",
      prescreen: !n ? "Nothing to test yet" : f.untested ? f.untested + " of " + n + " still to pre-screen"
                 : "All " + n + " pre-screened" + (f.eligible == null ? "" : ", " + f.eligible + " eligible for selection"),
      selection: !f.round ? "Not started" : settled ? "The results are certified" : "Under way: " + f.round.toLowerCase(),
      invite: f.invited ? plural(f.invited, "household", "households") + " invited" : "Nobody invited yet",
      certify: f.certified ? plural(f.certified, "household", "households") + " certified" : "Nobody certified yet"
    };
    return STEPS.map(function (s) {
      return { key: s.key, label: s.label, page: s.page, state: nx && nx.key === s.key ? "next" : done[s.key] ? "done" : "waiting", line: line[s.key] };
    });
  }

  // A project that is finding the buyer for a resale: one track for the whole sale. The resale's first steps come
  // before the project's, and its last ones after, so the sale is walked from the notice to the closing in one place.
  //   facts: as for track(); sale: { done: { start, price, offer, buyer, contract, closing }, closed, cancelled, lines: { step: words } }, or null
  // -> the steps of track(), with the resale's around them: { key: "resale:price", resale: "price", page: the Resale page, ... }
  //    Only one step is "next": the first of the resale's opening steps not done; then the project's own next step, or
  //    Offer the home once a household is certified; then their answer, the purchase and sale agreement and the closing.
  var RESALE_PAGE = "clt_/pages/resale.html";
  var RESALE_BEFORE = [["start", "Start the resale"], ["price", "Price and what the seller owes"]];
  var RESALE_AFTER = [["offer", "Offer the home"], ["buyer", "The household's answer"], ["contract", "Purchase and sale agreement"], ["closing", "Closing"]];
  function whole(facts, sale) {
    var steps = track(facts);
    if (!sale) return steps;
    var d = sale.done || {}, lines = sale.lines || {}, f = facts || {};
    var make = function (x) { return { key: "resale:" + x[0], resale: x[0], label: x[1], page: RESALE_PAGE, state: d[x[0]] ? "done" : "waiting", line: lines[x[0]] || "" }; };
    var before = RESALE_BEFORE.map(make), after = RESALE_AFTER.map(make);
    if (d.buyer) steps.forEach(function (s) { s.state = "done"; });   // the buyer is chosen: the project has done its job
    var undone = function (list) { return list.filter(function (s) { return s.state !== "done"; })[0] || null; };
    var mine = steps.filter(function (s) { return s.state === "next"; })[0] || null;
    var next = sale.closed || sale.cancelled ? null : undone(before) || (d.buyer || d.offer || f.certified > 0 ? undone(after) : mine);
    if (next === after[0] && !next.line) next.line = plural(f.certified, "household", "households") + " certified: offer the home";
    var all = before.concat(steps, after);
    all.forEach(function (s) { if (s.state === "next" && s !== next) s.state = "waiting"; });
    if (next) next.state = "next";
    return all;
  }

  // Selling the homes of a project that isn't a resale: each home has its own sale, walked on the sale page from the
  // offer to the closing.
  //   homes: [{ id, name, price, status, sale: its sale's id (or "") }]
  //   sales: { sale id: { next: the step it is waiting on, closed, cancelled, closedOn, buyer, offeredTo } }
  //   certified: how many households the project has certified
  // -> [{ id, name, price, sale, state: "wait" | "start" | "open" | "sold", line, button }], homes in name order
  function homesToSell(homes, sales, certified) {
    var name = function (h) { return String(h.name || "").toLowerCase(); };
    return (homes || []).slice().sort(function (a, b) { return name(a) < name(b) ? -1 : name(a) > name(b) ? 1 : 0; }).map(function (h) {
      var s = h.sale ? (sales || {})[h.sale] : null, row = { id: h.id, name: h.name || "", price: h.price, sale: s && !s.cancelled ? h.sale : "" };
      if (!s || s.cancelled) {
        row.state = certified > 0 ? "start" : "wait";
        row.line = certified > 0 ? "Not started" : "Waiting for a certified household";
        row.button = certified > 0 ? "Start the sale" : "";
      } else if (s.closed) { row.state = "sold"; row.line = "Sold" + (s.buyer ? " to " + s.buyer : "") + (s.closedOn ? ", closed " + s.closedOn : ""); row.button = "Open"; }
      else {
        row.state = "open"; row.button = "Continue";
        row.line = (s.next || "In progress") + (s.buyer ? ": " + s.buyer + " is the buyer" : s.offeredTo ? ": offered to " + s.offeredTo : "");
      }
      return row;
    });
  }

  // Every project with where it stands, by name; the ones that aren't closed first.
  //   projects: [{ id, name, status }]; apps: [{ project, tested, eligible }]; rounds: [{ project, status, created }];
  //   invited: [{ project }]; certified: [{ project }]
  // -> [{ id, name, status, applications, facts, next }]
  function standing(projects, apps, rounds, invited, certified) {
    var count = {}, untested = {}, eligible = {}, round = {}, inv = {}, cert = {};
    (apps || []).forEach(function (a) {
      if (!a.project) return;
      count[a.project] = (count[a.project] || 0) + 1;
      if (!a.tested) untested[a.project] = (untested[a.project] || 0) + 1;
      if (a.eligible) eligible[a.project] = (eligible[a.project] || 0) + 1;
    });
    (rounds || []).forEach(function (r) { if (r.project && (!round[r.project] || String(r.created || "") > String(round[r.project].created || ""))) round[r.project] = r; });
    (invited || []).forEach(function (e) { if (e.project) inv[e.project] = (inv[e.project] || 0) + 1; });
    (certified || []).forEach(function (c) { if (c.project) cert[c.project] = (cert[c.project] || 0) + 1; });
    var name = function (p) { return String(p.name || "").toLowerCase(); };
    return (projects || []).map(function (p) {
      var facts = { status: p.status, applications: count[p.id] || 0, untested: untested[p.id] || 0, eligible: eligible[p.id] || 0, round: round[p.id] ? round[p.id].status || "" : "",
                    invited: inv[p.id] || 0, certified: cert[p.id] || 0 };
      return { id: p.id, name: p.name || "", status: p.status || "", applications: facts.applications, facts: facts, next: next(facts) };
    }).sort(function (a, b) { return (a.status === CLOSED) - (b.status === CLOSED) || (name(a) < name(b) ? -1 : name(a) > name(b) ? 1 : 0); });
  }
  // The projects that aren't closed, each with its next step, by name.
  function inProgress(projects, apps, rounds, invited, certified) {
    return standing(projects, apps, rounds, invited, certified).filter(function (p) { return p.status !== CLOSED; }).sort(function (a, b) { return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : a.name.toLowerCase() > b.name.toLowerCase() ? 1 : 0; });
  }

  // The row of steps at the top of a project page. The step you are on is filled in; choosing another opens that page
  // on the same project, so a project can be walked from start to finish, left, and picked up again.
  //   el: the <ol class="steps">; current: this page's key; projectId: a function giving the project chosen on the page
  function bar(el, current, projectId) {
    if (!el) return;
    var at = STEPS.map(function (s) { return s.key; }).indexOf(current);
    el.innerHTML = '<li><button type="button" data-step="overview" title="This project\'s progress through every step">&lsaquo; Project overview</button></li>' + STEPS.map(function (s, i) {
      return '<li class="' + (i === at ? "on" : i < at ? "seen" : "") + '"><button type="button" data-step="' + s.key + '"' + (i === at ? " disabled" : "") +
             "><span>" + (i + 1) + "</span>" + s.label + "</button></li>";
    }).join("");
    el.addEventListener("click", function (e) {
      var b = e.target.closest ? e.target.closest("button[data-step]") : null, s = b && (b.dataset.step === "overview" ? { page: OVERVIEW } : step(b.dataset.step));
      if (!s) return;
      var id = projectId ? projectId() : "", to = { pageType: "webresource", webresourceName: s.page };
      if (id) to.data = id;
      CLTPage.go(to);
    });
  }

  var api = { STEPS: STEPS, OVERVIEW: OVERVIEW, step: step, next: next, track: track, whole: whole, homesToSell: homesToSell, RESALE_PAGE: RESALE_PAGE, standing: standing, inProgress: inProgress, bar: bar };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
