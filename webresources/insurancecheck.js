// Insurance verification: the rules for the page (deployed as clt_/pages/insurancecheck.js by build_app.py).
// Plain functions with no Dataverse calls, so tests/test_insurance.py runs them in Node on worked examples. The page
// (insurance.html) loads, shows and saves.
var CLTInsuranceCheck = (function () {
  var REQUESTED = "Requested", REVIEW = "To review", CONTACT = "Needs contact", ONLINE = "Online form", PAPER = "Paper", CARD = "Insurer's card";
  // An issue stays open: it is saved on the request, which waits there until the insurance is approved (or it is cancelled).
  var OPEN = ["Requested", "To review", "Needs contact", "Issue found"], CLOSED = ["Approved"], CANCELLED = "Cancelled";
  var OUTCOMES = ["Approved", "Issue found"];
  function blank(v) { return v === null || v === undefined || v === ""; }
  function iso(v) { return blank(v) ? "" : String(v).slice(0, 10); }

  // One row per current occupancy for the list of who to ask.
  //   occupancies: [{ id, name, home, household, lastVerified, due: insurance is overdue or due soon }]
  //   list: [{ id, occupancy, status, method }] the insurance verifications
  // -> [{ ..., request: the occupancy's open one (or null), tick: suggested for this batch }]
  // A home with one already open isn't asked again. Homes whose insurance is overdue or due soon are ticked;
  // only: when the page was opened for particular households (from the Verification hub), just those are ticked.
  function choose(occupancies, list, only) {
    var want = only && only.length ? only.map(function (i) { return String(i).toLowerCase(); }) : null;
    return (occupancies || []).map(function (o) {
      var req = (list || []).filter(function (x) { return x.occupancy === o.id && OPEN.indexOf(x.status) >= 0; })[0] || null;
      var row = {}; Object.keys(o).forEach(function (k) { row[k] = o[k]; });
      row.request = req;
      row.tick = !req && (want ? want.indexOf(String(o.id).toLowerCase()) >= 0 : !!o.due);
      return row;
    });
  }

  // What's wrong with the requests about to start. picks: the households ticked; input: { due } -> [messages]
  // Stu sends nothing: a request records that the household was asked, and when the proof is due.
  function startProblems(picks, input, today) {
    var e = [];
    if (!(picks || []).length) e.push("Tick at least one household.");
    if (!iso(input.due)) e.push("Enter the date the proof is due.");
    else if (iso(input.due) < today) e.push("The due date is in the past.");
    return e;
  }

  // "$350,000" -> 350000; blank -> null; not a number -> NaN
  function money(v) {
    if (blank(v) || String(v).trim() === "") return null;
    var n = Number(String(v).replace(/[$,\s]/g, ""));
    return isNaN(n) ? NaN : n;
  }

  // What's wrong with saving a review ("" list when it's fine). input: { verified, outcome, notes, coverage }
  function closeProblems(input, today) {
    var e = [], c = money(input.coverage);
    if (c !== null && (isNaN(c) || c < 0)) e.push("The replacement coverage limit must be a number, 0 or more.");
    if (!iso(input.verified)) e.push("Enter the date you reviewed it.");
    else if (iso(input.verified) > today) e.push("The review date can't be in the future.");
    if (OUTCOMES.indexOf(input.outcome) < 0) e.push("Choose how it came out.");
    if (input.outcome === "Issue found" && !String(input.notes || "").trim()) e.push("Say what the issue is.");
    return e;
  }

  // The card an insurer mails when the organization is listed as additional insured. Entering one is an approved insurance
  // verification for that home, dated the day on the card (or the day it arrived).
  // What's wrong with it ("" list when it's fine). input: { occupancy, verified, coverage }
  function cardProblems(input, today) {
    var e = [], c = money(input.coverage);
    if (!input.occupancy) e.push("Choose the home the card is for.");
    if (!iso(input.verified)) e.push("Enter the date on the card, or the day it arrived.");
    else if (iso(input.verified) > today) e.push("The date can't be in the future.");
    if (c !== null && (isNaN(c) || c < 0)) e.push("The replacement coverage limit must be a number, 0 or more.");
    return e;
  }
  // Where a card goes: onto the home's open insurance verification when there is one (it closes it), else a new one.
  //   list: [{ id, occupancy, status }] -> the open one's id, or ""
  function cardTarget(occupancy, list) {
    var open = (list || []).filter(function (x) { return x.occupancy === occupancy && OPEN.indexOf(x.status) >= 0; })[0];
    return open ? open.id : "";
  }

  // Only an approved review counts as the insurance being verified.
  function counts(status) { return status === "Approved"; }

  // Cancelling one: what the occupancy's Last insurance verification date becomes.
  //   occupancyDate: the date on the occupancy now; cancelled: { verified, status }; others: [{ verified, status }]
  // -> undefined: leave the date alone (it didn't come from this one); otherwise the newest approved date left, or null.
  function afterCancel(occupancyDate, cancelled, others) {
    var was = cancelled && counts(cancelled.status) ? iso(cancelled.verified) : "";
    if (!was || was !== iso(occupancyDate)) return undefined;
    var left = (others || []).filter(function (x) { return counts(x.status) && iso(x.verified); }).map(function (x) { return iso(x.verified); }).sort();
    return left.length ? left[left.length - 1] : null;
  }

  // "2026-11-17, Rivera - 12 Pine St"
  function recordName(date, occupancyName) { return (iso(date) + (occupancyName ? ", " + occupancyName : "")).slice(0, 100); }

  var api = { REQUESTED: REQUESTED, REVIEW: REVIEW, CONTACT: CONTACT, ONLINE: ONLINE, PAPER: PAPER, CARD: CARD, OPEN: OPEN, CLOSED: CLOSED, CANCELLED: CANCELLED, OUTCOMES: OUTCOMES, money: money,
              choose: choose, startProblems: startProblems,
              closeProblems: closeProblems, cardProblems: cardProblems, cardTarget: cardTarget, counts: counts, afterCancel: afterCancel, recordName: recordName };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
