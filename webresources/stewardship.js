// Verification hub: which homes are due for an occupancy verification or an insurance verification (deployed as clt_/pages/stewardship.js by build_app.py). Plain rules with no Dataverse calls, so
// tests/test_regular.py runs them in Node on worked examples. The page (stewardship.html) loads, shows and saves.
var CLTRegular = (function () {
  // The two verifications: the organization setting that says how often, and the date on the occupancy.
  var ACTIVITIES = [
    { key: "occupancy", label: "Occupancy verification", setting: "OccupancyVerificationMonths", field: "clt_lastoccupancyverified" },
    { key: "insurance", label: "Insurance verification", setting: "InsuranceVerificationMonths", field: "clt_lastinsuranceverified" }
  ];
  var CONTACT_FIELD = "clt_lastcontact";
  var DEFAULT_MONTHS = 12, SOON_DAYS = 30;
  var OVERDUE = "Overdue", SOON = "Due soon", OK = "Up to date";

  function blank(v) { return v === null || v === undefined || v === ""; }
  function iso(v) { return blank(v) ? "" : String(v).slice(0, 10); }
  function pad(n) { return ("0" + n).slice(-2); }

  // How often, in months, from a setting: a whole number of 1 or more, else every 12 months.
  function months(setting) {
    var n = Number(String(blank(setting) ? "" : setting).trim());
    return n >= 1 && Math.floor(n) === n ? n : DEFAULT_MONTHS;
  }

  // "2026-01-31" plus 1 month -> "2026-02-28" (the last day of a shorter month, never rolling into the next one)
  function addMonths(date, n) {
    var p = iso(date).split("-"), y = +p[0], m = +p[1] - 1 + n, d = +p[2];
    y += Math.floor(m / 12); m = ((m % 12) + 12) % 12;
    var last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    return y + "-" + pad(m + 1) + "-" + pad(Math.min(d, last));
  }
  function addDays(date, n) {
    var p = iso(date).split("-"), x = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + n));
    return x.getUTCFullYear() + "-" + pad(x.getUTCMonth() + 1) + "-" + pad(x.getUTCDate());
  }

  // The newest of some dates ("" when there are none)
  function latest(dates) {
    return (dates || []).map(iso).filter(Boolean).sort().pop() || "";
  }

  // Where one activity stands. last: the date it was last done ("" if never), every: months between, today: "yyyy-mm-dd"
  // -> { state, last, dueOn }. Never done counts as overdue, with no due date. Due today is due soon, not overdue.
  function status(last, every, today) {
    last = iso(last);
    if (!last) return { state: OVERDUE, last: "", dueOn: "" };
    var due = addMonths(last, every);
    return { state: due < today ? OVERDUE : due <= addDays(today, SOON_DAYS) ? SOON : OK, last: last, dueOn: due };
  }

  // One row per current occupancy.
  //   occupancies: [{ id, name, property, household, role, dates: { occupancy, insurance, contact } }]  the dates typed on the occupancy
  //   records:     { occupancy: { <occupancy id>: [dates] }, insurance: {...}, contact: {...} }  dates from its records
  //                (contact: every time staff were in touch: relationship notes, and verifications that came back)
  //   settings:    the organization's settings; today: "yyyy-mm-dd"
  // The date used is the newest of the one on the occupancy and the ones on its records, so history typed straight
  // onto the occupancy (an import) and records added later both count.
  //   records.requests: { <occupancy id>: { id, status, method, sent } }  the occupancy verification request that is open, if any
  //   records.insuranceRequests: { <occupancy id>: { id, status } }  the insurance verification that is open, if any
  // -> rows, most urgent first: [{ ..., activities: { occupancy: {state, last, dueOn}, ... }, lastContact, worst, fix, request, insuranceRequest }]
  //    fix: the occupancy's dates that are behind its records ({ field: date }), for the page to bring up to date.
  function rows(occupancies, records, settings, today) {
    records = records || {}; settings = settings || {};
    var rank = {}; rank[OVERDUE] = 0; rank[SOON] = 1; rank[OK] = 2;
    var out = (occupancies || []).map(function (o) {
      var acts = {}, fix = {}, worst = OK, soonest = "";
      ACTIVITIES.forEach(function (a) {
        var typed = iso((o.dates || {})[a.key]), newest = latest([typed].concat((records[a.key] || {})[o.id] || []));
        var s = status(newest, months(settings[a.setting]), today);
        acts[a.key] = s;
        if (newest && newest !== typed) fix[a.field] = newest;
        if (rank[s.state] < rank[worst]) worst = s.state;
        if (!soonest || s.dueOn < soonest) soonest = s.dueOn;   // "" (never done) sorts first
      });
      var typedContact = iso((o.dates || {}).contact), contact = latest([typedContact].concat((records.contact || {})[o.id] || []));
      if (contact && contact !== typedContact) fix[CONTACT_FIELD] = contact;
      return { id: o.id, name: o.name || "", property: o.property || "", household: o.household || "", role: o.role || "",
               activities: acts, lastContact: contact, worst: worst, soonest: soonest, fix: fix, request: (records.requests || {})[o.id] || null,
               insuranceRequest: (records.insuranceRequests || {})[o.id] || null };
    });
    return out.sort(function (x, y) {
      return rank[x.worst] - rank[y.worst] || (x.soonest < y.soonest ? -1 : x.soonest > y.soonest ? 1 : 0) ||
             (x.property < y.property ? -1 : x.property > y.property ? 1 : 0);
    });
  }

  // The figures across the top: for each activity, how many homes are overdue, due soon and up to date.
  function summary(list) {
    var out = {};
    ACTIVITIES.forEach(function (a) {
      var c = { overdue: 0, soon: 0, ok: 0 };
      (list || []).forEach(function (r) {
        var s = r.activities[a.key].state;
        c[s === OVERDUE ? "overdue" : s === SOON ? "soon" : "ok"]++;
      });
      out[a.key] = c;
    });
    return out;
  }

  // The Dashboard's two figures: occupancy and insurance verifications that are overdue (or never done), and those
  // coming due between today and the end of this month. Each verification is counted once.
  //   occupancies: [{ dates: { occupancy, insurance } }]  the dates on each current occupancy
  function dashboard(occupancies, settings, today) {
    settings = settings || {};
    var out = { overdue: 0, thisMonth: 0 }, month = iso(today).slice(0, 7);
    (occupancies || []).forEach(function (o) {
      ACTIVITIES.forEach(function (a) {
        var s = status((o.dates || {})[a.key], months(settings[a.setting]), today);
        if (s.state === OVERDUE) out.overdue++;
        else if (s.dueOn.slice(0, 7) === month) out.thisMonth++;
      });
    });
    return out;
  }

  // The households to ask next: occupancy verification overdue or due soon, and no request already open.
  // -> [occupancy ids]
  function toAsk(list) {
    return (list || []).filter(function (r) { return r.activities.occupancy.state !== OK && !r.request; }).map(function (r) { return r.id; });
  }

  // Which rows to show. activity: "" (any) or an activity key; show: "attention" (overdue or due soon), "overdue" or "all".
  function filter(list, activity, show) {
    return (list || []).filter(function (r) {
      var states = activity ? [r.activities[activity].state] : ACTIVITIES.map(function (a) { return r.activities[a.key].state; });
      if (show === "overdue") return states.indexOf(OVERDUE) >= 0;
      if (show === "all") return true;
      return states.indexOf(OVERDUE) >= 0 || states.indexOf(SOON) >= 0;
    });
  }

  var api = { ACTIVITIES: ACTIVITIES, CONTACT_FIELD: CONTACT_FIELD, DEFAULT_MONTHS: DEFAULT_MONTHS, SOON_DAYS: SOON_DAYS,
              OVERDUE: OVERDUE, SOON: SOON, OK: OK, months: months, addMonths: addMonths, addDays: addDays, latest: latest,
              status: status, rows: rows, summary: summary, filter: filter, toAsk: toAsk, dashboard: dashboard };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
