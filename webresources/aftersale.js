// After the sale: the stewardship work that follows a closing (deployed as clt_/pages/aftersale.js by build_app.py).
// Plain rules with no Dataverse calls, so tests/test_aftersale.py runs them in Node on worked examples. The page
// (aftersale.html) loads, shows and saves. The tasks themselves are the organization's own list (After-sale tasks).
var CLTAfterSale = (function () {
  var TODO = "To do", DONE = "Done", SKIPPED = "Not needed";
  var EVERY = "Every sale", RESALES = "Resales only", FIRST = "First sales only", RESALE = "Resale";
  var TICK = "Tick it off", INSURANCE = "Enter the insurance", STATEMENT = "Add the settlement statement", OCCUPANCY = "Open the new occupancy",
      FOLDER = "Open the documents folder", PROPERTY = "Open the property", WILD = "Open Stu in the wild";
  var ACTIONS = [TICK, INSURANCE, STATEMENT, OCCUPANCY, FOLDER, PROPERTY, WILD];

  function blank(v) { return v === null || v === undefined || v === ""; }
  function iso(v) { return blank(v) ? "" : String(v).slice(0, 10); }
  function num(v) {
    if (blank(v) || String(v).trim() === "") return null;
    var n = Number(String(v).replace(/[$,\s]/g, ""));
    return isNaN(n) ? NaN : n;
  }
  function byOrder(a, b) {
    var x = blank(a.order) ? 1e9 : +a.order, y = blank(b.order) ? 1e9 : +b.order;
    return x - y || (String(a.name || "") < String(b.name || "") ? -1 : String(a.name || "") > String(b.name || "") ? 1 : 0);
  }

  // The organization's tasks that apply to one sale, in order.
  //   templates: [{ name, order, action, appliesTo, details }]; saleType: "Resale" or "Initial sale"
  // -> the tasks to copy onto the sale: [{ name, order, action, details }]
  function tasksFor(templates, saleType) {
    var resale = saleType === RESALE;
    return (templates || []).filter(function (t) {
      return t.name && (t.appliesTo === RESALES ? resale : t.appliesTo === FIRST ? !resale : true);
    }).slice().sort(byOrder).map(function (t) {
      return { name: String(t.name).slice(0, 100), order: blank(t.order) ? null : +t.order, action: ACTIONS.indexOf(t.action) >= 0 ? t.action : TICK, details: t.details || "" };
    });
  }

  // How far one sale's tasks have got. tasks: [{ status }] -> { total, open, done }  (Not needed counts as dealt with)
  function progress(tasks) {
    var open = (tasks || []).filter(function (t) { return t.status !== DONE && t.status !== SKIPPED; }).length;
    return { total: (tasks || []).length, open: open, done: (tasks || []).length - open };
  }

  // The closed sales, with where each stands.
  //   sales: [{ id, name, closed: the sale is Closed, closingDate }]; tasks: [{ sale, status }]
  // -> [{ ..., total, open, state: "new" (no tasks yet) | "open" | "done" }], the ones with work left first, newest closing first
  function sales(list, tasks) {
    var mine = {};
    (tasks || []).forEach(function (t) { (mine[t.sale] = mine[t.sale] || []).push(t); });
    var rank = { "new": 0, open: 0, done: 1 };
    return (list || []).filter(function (s) { return s.closed; }).map(function (s) {
      var p = progress(mine[s.id]), row = {};
      Object.keys(s).forEach(function (k) { row[k] = s[k]; });
      row.total = p.total; row.open = p.open; row.state = !p.total ? "new" : p.open ? "open" : "done";
      return row;
    }).sort(function (a, b) {
      return rank[a.state] - rank[b.state] || (iso(a.closingDate) < iso(b.closingDate) ? 1 : iso(a.closingDate) > iso(b.closingDate) ? -1 : 0);
    });
  }
  // The Dashboard's figure: closed sales with after-sale work still to do (tasks open, or not set up yet).
  function unfinished(list, tasks) { return sales(list, tasks).filter(function (s) { return s.state !== "done"; }).length; }

  // What's wrong with the buyer's insurance as typed ("" list when it's fine).
  //   input: { carrier, policyNumber, coverage, effective, renewal }
  function insuranceProblems(input, today) {
    var e = [], c = num(input.coverage);
    if (!String(input.carrier || "").trim()) e.push("Enter the insurer.");
    if (c === null) e.push("Enter the dwelling coverage.");
    else if (isNaN(c) || c <= 0) e.push("The dwelling coverage must be a number above 0.");
    if (!iso(input.effective)) e.push("Enter the date the policy starts.");
    if (iso(input.renewal) && iso(input.effective) && iso(input.renewal) <= iso(input.effective)) e.push("The renewal date should be after the date the policy starts.");
    return e;
  }
  // "State Farm 2026-27" (the insurer, then the policy's years)
  function policyName(carrier, effective, renewal) {
    var a = iso(effective).slice(0, 4), b = iso(renewal).slice(2, 4);
    return (String(carrier || "").trim() + (a ? " " + a + (b && iso(renewal).slice(0, 4) !== a ? "-" + b : "") : "")).slice(0, 100);
  }
  // The date the insurance counts as verified: the closing, when the buyer had to show it. Today when there is no closing date.
  function verifiedOn(closingDate, today) { return iso(closingDate) && iso(closingDate) <= today ? iso(closingDate) : today; }
  // "2026-11-18, Okafor - 12 Pine St"
  function recordName(date, occupancyName) { return (iso(date) + (occupancyName ? ", " + occupancyName : "")).slice(0, 100); }

  var api = { TODO: TODO, DONE: DONE, SKIPPED: SKIPPED, EVERY: EVERY, RESALES: RESALES, FIRST: FIRST, RESALE: RESALE, ACTIONS: ACTIONS,
              TICK: TICK, INSURANCE: INSURANCE, STATEMENT: STATEMENT, OCCUPANCY: OCCUPANCY, FOLDER: FOLDER, PROPERTY: PROPERTY, WILD: WILD,
              num: num, tasksFor: tasksFor, progress: progress, sales: sales, unfinished: unfinished, insuranceProblems: insuranceProblems,
              policyName: policyName, verifiedOn: verifiedOn, recordName: recordName };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
