// Loans a homeowner has from the organization (deployed as clt_/pages/loan.js by build_app.py). The sums are plain
// functions with no Dataverse calls, so tests/test_resale.py runs them in Node. The Resale page uses them for the
// payoff figure, and the Loan form uses fill() to suggest the regular payment.
var CLTLoan = (function () {
  function blank(v) { return v === null || v === undefined || v === ""; }
  function num(v) { return blank(v) ? null : Number(v); }
  function cents(v) { return Math.round(v * 100) / 100; }
  function parts(d) { var p = String(d).slice(0, 10).split("-"); return { y: +p[0], m: +p[1], d: +p[2] }; }

  // Whole months from one date to another (0 when the second isn't after the first): Jan 15 to Mar 14 is 1, to Mar 15 is 2.
  function monthsBetween(from, to) {
    if (blank(from) || blank(to)) return 0;
    var a = parts(from), b = parts(to), n = (b.y - a.y) * 12 + (b.m - a.m) - (b.d < a.d ? 1 : 0);
    return Math.max(0, n);
  }

  // The monthly payment that pays a loan off between its start and end dates. null when it can't be worked out
  // (no balance, no dates, or less than a month between them). No interest: the balance split evenly.
  function payment(balance, ratePct, start, end) {
    balance = num(balance); var n = monthsBetween(start, end), r = (num(ratePct) || 0) / 100 / 12;
    if (balance === null || !(balance > 0) || n < 1) return null;
    return cents(r === 0 ? balance / n : balance * r / (1 - Math.pow(1 + r, -n)));
  }

  // What is still owed on a date, if every regular payment so far was made on time. Interest is added monthly.
  // A loan with no payment (a deferred loan) grows with its interest, or stays level when it has none.
  // loan: { balance, rate, start, end, payment }; null when there's no starting balance.
  function owed(loan, asOf) {
    var b = num(loan && loan.balance);
    if (b === null) return null;
    var r = (num(loan.rate) || 0) / 100 / 12, p = num(loan.payment) || 0, n = monthsBetween(loan.start, asOf);
    for (var i = 0; i < n && b > 0; i++) b = b * (1 + r) - p;
    return cents(Math.max(0, b));
  }

  // The Loan form: suggest the regular payment from the balance, rate and dates. It only fills a blank payment, or
  // replaces one this form suggested earlier, so a payment someone typed is never overwritten.
  var suggested = null;
  function fill(ctx) {
    var fc = ctx.getFormContext(), get = function (f) { var a = fc.getAttribute(f); return a ? a.getValue() : null; };
    var day = function (d) { return d ? d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2) : ""; };
    var pay = fc.getAttribute("clt_payment");
    if (!pay) return;
    var want = payment(get("clt_startingbalance"), get("clt_interestrate"), day(get("clt_startdate")), day(get("clt_enddate")));
    if (want === null) return;
    var now = pay.getValue();
    if (now === null || now === suggested) { pay.setValue(want); pay.setSubmitMode("always"); suggested = want; }
  }

  var api = { monthsBetween: monthsBetween, payment: payment, owed: owed, fill: fill };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
var CLT = (typeof window !== "undefined" && window.CLT) || (typeof CLT !== "undefined" ? CLT : {});
CLT.Loans = { fill: CLTLoan.fill };
if (typeof window !== "undefined") window.CLT = CLT;
