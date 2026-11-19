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

  var api = { STEPS: STEPS, OVERVIEW: OVERVIEW, step: step, next: next, track: track, standing: standing, inProgress: inProgress, bar: bar };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
