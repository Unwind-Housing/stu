// Insurance verification: the rules for the guided page (deployed as clt_/pages/insurancecheck.js by build_app.py).
// Plain functions with no Dataverse calls, so tests/test_insurance.py runs them in Node on worked examples. The page
// (insurance.html) loads, shows and saves.
var CLTInsuranceCheck = (function () {
  var REQUESTED = "Requested", REVIEW = "To review", CONTACT = "Needs contact", ONLINE = "Online form", PAPER = "Paper";
  // An issue stays open: it is saved on the request, which waits there until the insurance is approved (or it is cancelled).
  var OPEN = ["Requested", "To review", "Needs contact", "Issue found"], CLOSED = ["Approved"], CANCELLED = "Cancelled";
  var OUTCOMES = ["Approved", "Issue found"];
  var DEFAULT = {
    subject: "Proof of homeowner's insurance for {home}",
    body: "Hello {first name},\n\nEach year we check that every home is insured. Please send us proof of your homeowner's insurance: " +
          "usually your policy declarations page, a renewal notice, or a certificate of insurance.\n\n" +
          "Please send it by {due date} using this form:\n{link}\n\nIf you can't find it, or have any questions, just reply to this email.\n\n" +
          "Thank you,\n{organization}"
  };
  var BUTTON = "Send your proof of insurance";

  function blank(v) { return v === null || v === undefined || v === ""; }
  function iso(v) { return blank(v) ? "" : String(v).slice(0, 10); }

  // What an answer on the yearly form starts.   answer: { uploaded: proof of insurance was attached, contact: they asked to be contacted }
  //   - proof attached and no help asked for: To review (staff look at the document and approve it)
  //   - help asked for, or nothing attached: Needs contact (staff get in touch)
  function fromForm(answer) { return answer && answer.uploaded && !answer.contact ? REVIEW : CONTACT; }

  // One row per current occupancy for the Choose step.
  //   occupancies: [{ id, name, home, household, ..., email, lastVerified, due: insurance is overdue or due soon }]
  //   list: [{ id, occupancy, status, method }] the insurance verifications
  // -> [{ ..., request: the occupancy's open one (or null), method: the suggested way (online when there's an email),
  //        tick: suggested for this batch }]
  // A home with one already open isn't asked again. Homes whose insurance is overdue or due soon are ticked;
  // only: when the page was opened for particular households (from the Verification hub), just those are ticked.
  function choose(occupancies, list, only) {
    var want = only && only.length ? only.map(function (i) { return String(i).toLowerCase(); }) : null;
    return (occupancies || []).map(function (o) {
      var req = (list || []).filter(function (x) { return x.occupancy === o.id && OPEN.indexOf(x.status) >= 0; })[0] || null;
      var row = {}; Object.keys(o).forEach(function (k) { row[k] = o[k]; });
      row.request = req; row.method = o.email ? ONLINE : PAPER;
      row.tick = !req && (want ? want.indexOf(String(o.id).toLowerCase()) >= 0 : !!o.due);
      return row;
    });
  }

  // What's wrong with the batch about to start. picks: [{ household, method, email }]; input: { due, link, subject, body } -> [messages]
  function startProblems(picks, input, today) {
    var e = [], online = (picks || []).filter(function (p) { return p.method === ONLINE; });
    if (!(picks || []).length) e.push("Tick at least one household.");
    if (!iso(input.due)) e.push("Enter the date the proof is due.");
    else if (iso(input.due) < today) e.push("The due date is in the past.");
    online.forEach(function (p) { if (!p.email) e.push((p.household || "A household") + " has no email address: use a paper copy for them."); });
    if (online.length) {
      var link = String(input.link || "").trim();
      if (!link) e.push("There is no insurance form link yet. Paste it here, or have whoever looks after Stu put it in your organization's settings.");
      else if (!/^https?:\/\//i.test(link)) e.push("The form link should start with https://");
      if (!String(input.subject || "").trim() || !String(input.body || "").trim()) e.push("The email needs a subject and a message.");
      else if (!/\{link\}/i.test(input.body)) e.push("The message doesn't have {link} in it, so nobody would get their link.");
    }
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

  var api = { REQUESTED: REQUESTED, REVIEW: REVIEW, CONTACT: CONTACT, ONLINE: ONLINE, PAPER: PAPER, OPEN: OPEN, CLOSED: CLOSED, CANCELLED: CANCELLED, OUTCOMES: OUTCOMES, money: money,
              DEFAULT: DEFAULT, BUTTON: BUTTON, fromForm: fromForm, choose: choose, startProblems: startProblems,
              closeProblems: closeProblems, counts: counts, afterCancel: afterCancel, recordName: recordName };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
