// Resale: the rules for the guided Resale page (deployed as clt_/pages/resale.js by build_app.py). Plain functions with
// no Dataverse calls, so tests/test_resale.py runs them in Node on worked examples. The page (resale.html) loads,
// shows and saves. Loan sums come from loan.js.
var CLTResale = (function () {
  var L = typeof CLTLoan !== "undefined" ? CLTLoan : require("./loan.js");
  var STEPS = [
    { key: "start", title: "Start the resale" },
    { key: "price", title: "Price and what the seller owes" },
    { key: "buyer", title: "Find the buyer" },
    { key: "contract", title: "Contract" },
    { key: "closing", title: "Closing" }
  ];

  function blank(v) { return v === null || v === undefined || v === ""; }
  function num(v) {
    if (blank(v)) return null;
    var n = Number(String(v).replace(/[$,\s]/g, ""));
    return isNaN(n) ? NaN : n;
  }
  function cents(v) { return Math.round(v * 100) / 100; }
  function iso(v) { return blank(v) ? "" : String(v).slice(0, 10); }

  // Each loan with what is still owed on a date, and the total. Loans that are paid off (status) are left out.
  // loans: [{ name, balance, rate, start, end, payment, status }]
  function loansOwed(loans, asOf) {
    var lines = (loans || []).filter(function (l) { return l.status !== "Paid off"; }).map(function (l) {
      return { name: l.name || "Loan", owed: L.owed(l, asOf) || 0 };
    });
    return { lines: lines, total: cents(lines.reduce(function (t, l) { return t + l.owed; }, 0)) };
  }

  // What an improvement credit is worth on a date: it falls evenly, by the day, from its original value to zero over
  // its depreciation period. No period (or no date) means it keeps its value. Never more than the original, never below 0.
  //   credit: { original, date: the date the original value is from, years: the depreciation period }
  function creditValue(credit, asOf) {
    var original = num(credit.original) || 0, years = num(credit.years), from = iso(credit.date), on = iso(asOf);
    if (!(years > 0) || !from || !on) return cents(original);
    var days = (Date.UTC(+on.slice(0, 4), +on.slice(5, 7) - 1, +on.slice(8, 10)) - Date.UTC(+from.slice(0, 4), +from.slice(5, 7) - 1, +from.slice(8, 10))) / 86400000;
    return cents(original * Math.max(0, Math.min(1, 1 - days / (years * 365.25))));
  }
  // The occupancy's improvement credits at their value on a date, added together (null when the list is empty).
  function creditsTotal(credits, asOf) {
    return (credits || []).length ? cents(credits.reduce(function (t, c) { return t + creditValue(c, asOf); }, 0)) : null;
  }

  // What adds to the price for this occupancy: each improvement credit on its list at its value on the date, and any
  // capital improvement request the organization approved with a credit that isn't on the list yet.
  //   requests: [{ id, name, type, status, credit }]; credits: [{ name, original, date, years, request: the request it came from }]
  // -> { lines: [{ name, credit }], total }
  var COUNTED = ["Approved", "Approved with conditions", "Completed"];
  function improvements(requests, credits, asOf) {
    var listed = {}, lines = (credits || []).map(function (c) {
      if (c.request) listed[c.request] = 1;
      return { name: c.name || "Improvement credit", credit: creditValue(c, asOf) };   // a fully depreciated one still shows, at 0
    });
    (requests || []).forEach(function (r) {
      if (r.type === "Capital improvement" && COUNTED.indexOf(r.status) >= 0 && num(r.credit) > 0 && !(r.id && listed[r.id])) {
        lines.push({ name: r.name || "Capital improvement", credit: num(r.credit) });
      }
    });
    return { lines: lines, total: cents(lines.reduce(function (t, l) { return t + l.credit; }, 0)) };
  }

  // The project (if any) set up to find this home's buyer, and who it has certified.
  //   projects: [{ id, name, status }] the projects that include the home, newest first
  //   certified: [{ household, project }] certified households by project; buyers: [{ id, ... }] every certified household
  // -> { project, fromProject: [buyers], others: [buyers] }   project: the newest one that isn't closed, else the newest
  function buyerGroups(projects, certified, buyers) {
    var open = (projects || []).filter(function (p) { return p.status !== "Closed"; }), project = open[0] || (projects || [])[0] || null;
    var mine = {};
    (certified || []).forEach(function (c) { if (project && c.project === project.id) mine[c.household] = 1; });
    return { project: project, fromProject: (buyers || []).filter(function (b) { return mine[b.id]; }), others: (buyers || []).filter(function (b) { return !mine[b.id]; }) };
  }

  // The figures on the Price step.
  //   formula: the formula price; addedValue: capital improvements that raise the price
  //   loans: owed to the organization; credits / debits: other amounts for or against the seller
  //   price: the purchase price once there is a contract (until then the maximum resale price stands in for it)
  // -> { maxPrice, basis, recapture, net }   maxPrice = formula + added value; net = basis - loans + credits - debits.
  //    A home can sell for more than its maximum resale price: the seller's side stops at the maximum (basis), and
  //    the rest (recapture) goes back to the organization as recaptured subsidy.
  //    net is what the seller is left with before their own mortgage payoff and closing costs.
  function figures(input) {
    var f = num(input.formula), add = num(input.addedValue) || 0, price = num(input.price);
    var max = f === null || isNaN(f) ? null : cents(f + add);
    var sold = price !== null && !isNaN(price);
    var basis = sold ? (max === null ? price : Math.min(price, max)) : max;
    var recapture = sold && max !== null && price > max ? cents(price - max) : 0;
    var net = basis === null ? null : cents(basis - (num(input.loans) || 0) + (num(input.credits) || 0) - (num(input.debits) || 0));
    return { maxPrice: max, basis: basis, recapture: recapture, net: net };
  }

  // ---- how the purchase price is made up: the buyer's cash, loans, subsidies and anything else
  var FUNDING_TYPES = ["Buyer cash", "Loan", "Subsidy", "Other"], LOAN = "Loan", STATEMENT_TYPES = ["pdf", "jpg", "jpeg", "png"], STATEMENT_MAX_MB = 25;
  function usd(v) { return "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  // The lines as typed -> the ones with something on them, with numbers read: [{ id, type, amount, rate, notes }]
  // (rate is kept only for a loan). A line with nothing typed is dropped.
  function fundingLines(lines) {
    return (lines || []).filter(function (l) { return !blank(l.type) || !blank(l.amount) || !blank(l.rate) || String(l.notes || "").trim(); }).map(function (l) {
      return { id: l.id || "", type: l.type || "", amount: num(l.amount), rate: l.type === LOAN ? num(l.rate) : null, notes: String(l.notes || "").trim() };
    });
  }
  function fundingTotal(lines) { return cents(fundingLines(lines).reduce(function (t, l) { return t + (l.amount > 0 ? l.amount : 0); }, 0)); }
  // What's wrong with the lines -> [messages]. Every line needs a type and an amount; a loan needs its interest rate (0 is fine).
  function fundingProblems(lines) {
    var e = [];
    fundingLines(lines).forEach(function (l, i) {
      var which = "Funding line " + (i + 1) + (l.type ? " (" + l.type + ")" : "");
      if (FUNDING_TYPES.indexOf(l.type) < 0) e.push(which + ": choose the type.");
      if (l.amount === null) e.push(which + ": enter the amount.");
      else if (isNaN(l.amount) || l.amount <= 0) e.push(which + ": the amount must be a number above 0.");
      if (l.type === LOAN) {
        if (l.rate === null) e.push(which + ": enter the interest rate (0 for a loan with no interest).");
        else if (isNaN(l.rate) || l.rate < 0 || l.rate > 100) e.push(which + ": the interest rate must be a number from 0 to 100.");
      }
    });
    return e;
  }
  // Worth a second look: lines were entered and don't add up to the purchase price. No lines at all is fine.
  function fundingWarnings(lines, price) {
    var p = num(price), total = fundingTotal(lines);
    if (!fundingLines(lines).length || !(p > 0) || total === cents(p)) return [];
    var gap = cents(p - total);
    return ["The funding adds up to " + usd(total) + ", " + usd(Math.abs(gap)) + (gap > 0 ? " less" : " more") + " than the purchase price."];
  }
  // "Loan, Test Credit Union first mortgage"
  function fundingName(line) { return ((line.type || "Funding") + (line.notes ? ", " + line.notes : "")).slice(0, 100); }
  // "Loan $180,000.00 at 6.5%, Buyer cash $20,000.00"
  function fundingSummary(lines) {
    return fundingLines(lines).map(function (l) { return l.type + " " + usd(l.amount || 0) + (l.type === LOAN && l.rate !== null && !isNaN(l.rate) ? " at " + l.rate + "%" : ""); }).join(", ");
  }
  // What's wrong with a settlement statement file ("" when it's fine, or when there isn't one).
  function statementProblem(file) {
    if (!file) return "";
    var ext = (/\.([A-Za-z0-9]+)$/.exec(file.name || "") || [])[1];
    if (STATEMENT_TYPES.indexOf(String(ext || "").toLowerCase()) < 0) return "The settlement statement should be a PDF, or a JPG or PNG photo.";
    if (file.size > STATEMENT_MAX_MB * 1024 * 1024) return "That file is over " + STATEMENT_MAX_MB + " MB. Scan it at a lower quality and try again.";
    return "";
  }

  // What's wrong with a step's answers. -> [messages]; empty means it can be saved.
  function check(step, input, today) {
    var e = [], money = function (label, v, required) {
      var n = num(v);
      if (n === null) { if (required) e.push("Enter the " + label + "."); }
      else if (isNaN(n) || n < 0) e.push("The " + label + " must be a number, 0 or more.");
    };
    if (step === "start") {
      if (blank(input.occupancy)) e.push("Choose the home being sold.");
      if (!iso(input.noticeDate)) e.push("Enter the date the homeowner gave notice.");
      else if (iso(input.noticeDate) > today) e.push("The notice date can't be in the future.");
    } else if (step === "price") {
      money("formula price", input.formula, true); money("added value", input.addedValue); money("appraised value", input.appraised);
      money("loans owed", input.loans); money("other credits", input.credits); money("other debits", input.debits);
      if (num(input.credits) > 0 && !String(input.creditsNote || "").trim()) e.push("Say what the other credits are for.");
      if (num(input.debits) > 0 && !String(input.debitsNote || "").trim()) e.push("Say what the other debits are for.");
    } else if (step === "buyer") {
      if (blank(input.household)) e.push("Choose the buyer.");
      else if (input.sameAsSeller) e.push("The buyer can't be the household that is selling.");
    } else if (step === "contract") {
      var p = num(input.price);
      if (p === null || isNaN(p) || !(p > 0)) e.push("Enter the purchase price.");
      if (!iso(input.contractDate)) e.push("Enter the date the purchase and sale agreement was signed.");
      else if (iso(input.contractDate) > today) e.push("The date the purchase and sale agreement was signed can't be in the future.");
    } else if (step === "closing") {
      if (!iso(input.closingDate)) e.push("Enter the closing date.");
      else if (iso(input.closingDate) > today) e.push("Record the closing once it has happened: the date can't be in the future.");
      else if (iso(input.contractDate) && iso(input.closingDate) < iso(input.contractDate)) e.push("The closing can't be before the purchase and sale agreement was signed.");
      money("closing costs", input.closingCosts, false);
    }
    return e;
  }

  // Things worth a second look that don't stop a step.
  function warnings(step, input, today) {
    var w = [];
    if (step === "buyer" && !blank(input.household)) {
      // No expiry date means the certification doesn't run out (the organization set no validity period), not that there isn't one.
      if (iso(input.certificationExpires) && iso(input.certificationExpires) < today) w.push("This household's certification expired on " + iso(input.certificationExpires) + ".");
    }
    if (step === "contract" && num(input.price) > 0 && num(input.maxPrice) !== null) {
      var over = cents(num(input.price) - num(input.maxPrice));
      if (over < 0) w.push("The purchase price is below the maximum resale price.");
      if (over > 0) w.push("The purchase price is $" + over.toLocaleString("en-US") + " above the maximum resale price. The seller's side stops at the maximum, " +
                           "and that amount is recorded as subsidy recaptured by the organization.");
    }
    return w;
  }

  // Where a resale stands, from its sale record: which steps are done and which is next.
  // sale: { noticeDate, maxPrice, buyer, contractDate, price, status }
  function progress(sale) {
    var done = {
      start: !!sale, price: !!sale && !blank(sale.maxPrice), buyer: !!sale && !blank(sale.buyer),
      contract: !!sale && !blank(sale.contractDate) && !blank(sale.price), closing: !!sale && sale.status === "Closed"
    };
    var next = "";
    STEPS.forEach(function (s) { if (!next && !done[s.key]) next = s.key; });
    return { done: done, next: next, closed: done.closing, cancelled: !!sale && sale.status === "Cancelled" };
  }

  // The sales in progress for the page's opening list, each with the step it is waiting on.
  //   rows: [{ id, resale: this page walks it, ...the facts progress() reads }] -> [{ id, resale, next: the step's title }]
  //   A sale of another kind isn't walked here: it is listed, and opens as its own record.
  function pending(rows) {
    return (rows || []).map(function (r) {
      if (!r.resale) return { id: r.id, resale: false, next: "Open the sale to carry on" };
      var key = progress(r).next, st = STEPS.filter(function (s) { return s.key === key; })[0];
      return { id: r.id, resale: true, next: st ? st.title : "" };
    });
  }

  function saleName(property, date) { return ((property || "Home") + " resale " + iso(date).slice(0, 4)).slice(0, 100); }
  // "Rivera - 12 Pine St" from a household named "Rivera" or "Rivera, Maria"
  function occupancyName(household, property) { return (String(household || "").split(",")[0].trim() + " - " + (property || "")).slice(0, 100); }

  // The buyer's resale terms: the seller's formula and limits, starting again from this sale's price and closing date.
  // seller: the seller's occupancy row (clt_ columns); -> the columns for the buyer's occupancy
  var COPIED = ["clt_resaleformula", "clt_annualrate", "clt_wholeyearsonly", "clt_ownershare", "clt_floorbaseprice", "clt_pricecap", "clt_roundto", "clt_agreementversion"];
  function newTerms(seller, price, closingDate, appraised) {
    var out = {};
    COPIED.forEach(function (c) { if (!blank(seller[c])) out[c] = seller[c]; });
    out.clt_baseprice = num(price); out.clt_basedate = iso(closingDate);
    if (!blank(appraised)) out.clt_appraisalatpurchase = num(appraised);
    return out;
  }

  // Everything that changes at closing, as one all-or-nothing batch. The first change makes the buyer's occupancy,
  // and "$1" in the later ones means "the record the first change made".
  //   d: { saleId, closingDate, price, appraised, seller (occupancy row), sellerHouseholdId, sellerHasOtherHome,
  //        buyerHouseholdId, buyerHouseholdName, propertyId, propertyName, sets: { <table>: set name },
  //        values: { current, past, owner, closed, homeowner, pastHomeowner, ownerOccupied } }
  function closing(d) {
    var s = d.sets, v = d.values, at = iso(d.closingDate);
    var occ = newTerms(d.seller, d.price, at, d.appraised);
    occ.clt_name = occupancyName(d.buyerHouseholdName, d.propertyName);
    occ.clt_role = v.owner; occ.clt_status = v.current; occ.clt_startdate = at;
    occ["clt_property@odata.bind"] = "/" + s.clt_property + "(" + d.propertyId + ")";
    occ["clt_household@odata.bind"] = "/" + s.clt_household + "(" + d.buyerHouseholdId + ")";
    var ops = [
      { method: "POST", path: s.clt_occupancy, body: occ },
      { method: "PATCH", path: s.clt_sale + "(" + d.saleId + ")", body: { clt_status: v.closed, clt_closingdate: at, "clt_buyeroccupancy@odata.bind": "$1" } },
      { method: "PATCH", path: s.clt_occupancy + "(" + d.seller.clt_occupancyid + ")", body: { clt_status: v.past, clt_enddate: at } },
      { method: "PATCH", path: s.clt_property + "(" + d.propertyId + ")", body: { clt_status: v.ownerOccupied, "clt_currentoccupancy@odata.bind": "$1" } },
      { method: "PATCH", path: s.clt_household + "(" + d.buyerHouseholdId + ")", body: { clt_status: v.homeowner } }
    ];
    // The seller becomes a past homeowner, unless they still own another home in the program.
    if (d.sellerHouseholdId && !d.sellerHasOtherHome) {
      ops.push({ method: "PATCH", path: s.clt_household + "(" + d.sellerHouseholdId + ")", body: { clt_status: v.pastHomeowner } });
    }
    return ops;
  }

  var api = { pending: pending, FUNDING_TYPES: FUNDING_TYPES, LOAN: LOAN, fundingLines: fundingLines, fundingTotal: fundingTotal, fundingProblems: fundingProblems, fundingWarnings: fundingWarnings,
              fundingName: fundingName, fundingSummary: fundingSummary, statementProblem: statementProblem, usd: usd,
              STEPS: STEPS, COPIED: COPIED, num: num, loansOwed: loansOwed, creditValue: creditValue, creditsTotal: creditsTotal, improvements: improvements, buyerGroups: buyerGroups, figures: figures, check: check, warnings: warnings,
              progress: progress, saleName: saleName, occupancyName: occupancyName, newTerms: newTerms, closing: closing };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
