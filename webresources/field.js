// Field: the phone page for work done away from a desk, starting with the staff walk-by (deployed as clt_/pages/field.js
// by build_app.py). Plain rules with no Dataverse calls, so tests/test_field.py runs them in Node on worked examples.
// The page (field.html) loads, shows and saves.
var CLTField = (function () {
  var DRAFT = "Draft", SUBMITTED = "Submitted";
  var TODO = "todo", STARTED = "started", DONE = "done";
  var DEFAULT_MONTHS = 12, NO_NEIGHBORHOOD = "No neighborhood", PHOTO_MAX = 1600, PHOTO_LIMIT = 12, PHONE_WIDTH = 600;
  // Homes that aren't in the portfolio yet, or have left it, get no card.
  var NO_CARD = ["Prospective acquisition", "Left program"];

  function blank(v) { return v === null || v === undefined || v === ""; }
  function iso(v) { return blank(v) ? "" : String(v).slice(0, 10); }
  function pad(n) { return ("0" + n).slice(-2); }

  // How often, in months, from the setting: a whole number of 1 or more, else every 12 months.
  function months(setting) {
    var n = Number(String(blank(setting) ? "" : setting).trim());
    return n >= 1 && Math.floor(n) === n ? n : DEFAULT_MONTHS;
  }
  // "2026-01-31" plus 1 month -> "2026-02-28"
  function addMonths(date, n) {
    var p = iso(date).split("-"), y = +p[0], m = +p[1] - 1 + n, d = +p[2];
    y += Math.floor(m / 12); m = ((m % 12) + 12) % 12;
    var last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    return y + "-" + pad(m + 1) + "-" + pad(Math.min(d, last));
  }

  // "101 Maple Ct" before "1010 Maple Ct", "Unit 2" before "Unit 10": numbers compare as numbers
  function byAddress(a, b) {
    var x = String(a || "").toLowerCase().match(/\d+|\D+/g) || [], y = String(b || "").toLowerCase().match(/\d+|\D+/g) || [];
    for (var i = 0; i < Math.min(x.length, y.length); i++) {
      var n = /^\d/.test(x[i]) && /^\d/.test(y[i]);
      if (n ? +x[i] !== +y[i] : x[i] !== y[i]) return n ? +x[i] - +y[i] : x[i] < y[i] ? -1 : 1;
    }
    return x.length - y.length;
  }

  // Where one home stands.   walkbys: [{ id, date, status }] the home's own; every: months between walk-bys
  // -> { state, draft: the id of its draft (or ""), last: the date of its newest submitted walk-by (or "") }
  //   started (amber): a walk-by has been saved and not submitted yet
  //   done (green):    its newest submitted walk-by is within the last `every` months
  //   todo (red):      never walked, or longer ago than that
  function stand(walkbys, every, today) {
    var draft = (walkbys || []).filter(function (w) { return w.status === DRAFT; })[0];
    var last = (walkbys || []).filter(function (w) { return w.status === SUBMITTED && iso(w.date); }).map(function (w) { return iso(w.date); }).sort().pop() || "";
    return { state: draft ? STARTED : last && addMonths(last, every) > today ? DONE : TODO, draft: draft ? draft.id : "", last: last };
  }

  // The neighborhoods, each with a card per home.
  //   properties:  [{ id, name, neighborhood, status }]
  //   occupancies: [{ id, property, household }]  the current ones (an empty home has none)
  //   walkbys:     [{ id, property, date, status }]
  // -> [{ name, homes: [{ id, name, household, occupancy, state, draft, last }], total, done, started }]
  //    by name, with the homes that have no neighborhood last; homes in address order.
  function neighborhoods(properties, occupancies, walkbys, settings, today) {
    var every = months((settings || {}).WalkByMonths), occ = {}, mine = {}, groups = {};
    (occupancies || []).forEach(function (o) { occ[o.property] = o; });
    (walkbys || []).forEach(function (w) { (mine[w.property] = mine[w.property] || []).push(w); });
    (properties || []).filter(function (p) { return NO_CARD.indexOf(p.status) < 0; }).forEach(function (p) {
      var s = stand(mine[p.id], every, today), o = occ[p.id] || {}, n = p.neighborhood || NO_NEIGHBORHOOD;
      (groups[n] = groups[n] || []).push({ id: p.id, name: p.name || "", household: o.household || "", occupancy: o.id || "",
                                           state: s.state, draft: s.draft, last: s.last });
    });
    return Object.keys(groups).sort(function (a, b) {
      return (a === NO_NEIGHBORHOOD) - (b === NO_NEIGHBORHOOD) || byAddress(a, b);
    }).map(function (n) {
      var homes = groups[n].sort(function (a, b) { return byAddress(a.name, b.name); });
      return { name: n, homes: homes, total: homes.length,
               done: homes.filter(function (h) { return h.state === DONE; }).length,
               started: homes.filter(function (h) { return h.state === STARTED; }).length };
    });
  }

  // What's wrong with a walk-by about to be saved or submitted ("" list when it's fine).
  //   input: { notes, followUp: the box is ticked, due, photos: how many it will have }   submit: true for Submit
  // Save keeps anything. Submit with the follow-up box ticked needs to say what to follow up, and when.
  function problems(input, submit, today) {
    var e = [];
    if ((input.photos || 0) > PHOTO_LIMIT) e.push("That is more than " + PHOTO_LIMIT + " photos. Take some off.");
    if (submit && input.followUp) {
      if (!String(input.notes || "").trim()) e.push("Say in the notes what needs following up.");
      if (!iso(input.due)) e.push("Enter the date the follow-up is due.");
      else if (iso(input.due) < today) e.push("The follow-up's due date is in the past.");
    }
    return e;
  }

  // "2026-11-17, 105 Maple Ct"
  function recordName(date, home) { return (iso(date) + (home ? ", " + home : "")).slice(0, 100); }
  // The follow-up's name: the first line of the notes, or a plain one when there are none.
  function followUpName(notes, home) {
    var first = String(notes || "").split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean)[0];
    return (first || "Follow up on the walk-by" + (home ? " at " + home : "")).slice(0, 100);
  }

  // A home's walk-bys for the history on the property form: newest first, a draft before a submitted one on the same day.
  function history(walkbys) {
    return (walkbys || []).slice().sort(function (a, b) {
      var x = iso(a.date), y = iso(b.date);
      return x < y ? 1 : x > y ? -1 : (b.status === DRAFT) - (a.status === DRAFT);
    });
  }
  // The record a form hands its page: "?id=%7b1A2B...%7d&typename=clt_walkby" -> { id: "1a2b...", table: "clt_walkby" }
  function formRecord(search) {
    var q = {};
    String(search || "").replace(/^\?/, "").split("&").forEach(function (kv) {
      var i = kv.indexOf("="); if (i > 0) { try { q[kv.slice(0, i).toLowerCase()] = decodeURIComponent(kv.slice(i + 1)); } catch (e) { /* not ours */ } }
    });
    var id = String(q.id || "").replace(/[{}]/g, "").toLowerCase();
    return { id: /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(id) ? id : "", table: String(q.typename || "").toLowerCase() };
  }

  // Where Stu opens. On a phone the Dashboard hands over to this page, once: after that the Dashboard is a tap away
  // like every other page.   formFactor: the app's (1 desktop, 2 tablet, 3 phone; blank outside the app)
  //   width: the screen's width in CSS pixels, used when the app doesn't say; seen: this already happened this session
  function startHere(formFactor, width, seen) {
    if (seen) return false;
    var f = Number(formFactor);
    return f === 3 || (!(f >= 1) && Number(width) > 0 && Number(width) <= PHONE_WIDTH);
  }

  // A photo is shrunk before upload so its longer side is at most PHOTO_MAX. A smaller one is left as it is.
  function fit(w, h, max) {
    max = max || PHOTO_MAX;
    var k = Math.min(1, max / Math.max(w, h, 1));
    return { w: Math.max(1, Math.round(w * k)), h: Math.max(1, Math.round(h * k)) };
  }

  var api = { DRAFT: DRAFT, SUBMITTED: SUBMITTED, TODO: TODO, STARTED: STARTED, DONE: DONE, DEFAULT_MONTHS: DEFAULT_MONTHS,
              NO_NEIGHBORHOOD: NO_NEIGHBORHOOD, NO_CARD: NO_CARD, PHOTO_MAX: PHOTO_MAX, PHOTO_LIMIT: PHOTO_LIMIT, months: months, addMonths: addMonths,
              byAddress: byAddress, stand: stand, neighborhoods: neighborhoods, problems: problems, recordName: recordName,
              followUpName: followUpName, fit: fit, history: history, formRecord: formRecord, startHere: startHere, PHONE_WIDTH: PHONE_WIDTH };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
