// Resale: the rules for the guided Resale page (deployed as clt_/pages/resale.js by build_app.py). Plain functions with
// no Dataverse calls, so tests/test_resale.py runs them in Node on worked examples. The page (resale.html) loads,
// shows and saves. Loan sums come from loan.js.
var CLTResale = (function () {
  var L = typeof CLTLoan !== "undefined" ? CLTLoan : require("./loan.js");
  var STEPS = [
    { key: "start", title: "Start the resale" },
    { key: "price", title: "Price and what the seller owes" },
    { key: "offer", title: "Offer the home" },
    { key: "buyer", title: "The household's answer" },
    { key: "contract", title: "Purchase and sale agreement" },
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

  // Each household's priority on the project's lists: its place on the list for this home's size when it is on that
  // one, else its best place on any list. A lower tier comes first, then a lower rank.
  //   entries: [{ household, bedrooms, tier, rank, status }] the newest round's; bedrooms: this home's size (or null)
  // -> { household id: { rank, tier, bedrooms, status, thisSize: it is this home's list } }   Unranked entries are left out.
  function priorities(entries, bedrooms) {
    var out = {}, beds = blank(bedrooms) ? null : Math.min(4, Math.round(bedrooms));
    var better = function (a, b) { return (a.thisSize !== b.thisSize) ? a.thisSize : a.tier !== b.tier ? a.tier < b.tier : a.rank < b.rank; };
    (entries || []).forEach(function (e) {
      if (!e.household || blank(e.rank)) return;
      var p = { rank: +e.rank, tier: blank(e.tier) ? 1 : +e.tier, bedrooms: blank(e.bedrooms) ? null : +e.bedrooms, status: e.status || "",
                thisSize: beds !== null && !blank(e.bedrooms) && Math.min(4, +e.bedrooms) === beds };
      if (!out[e.household] || better(p, out[e.household])) out[e.household] = p;
    });
    return out;
  }
  // "rank 2, tier 1" on this home's list; "rank 2, tier 1 on the 3 bedroom list" when it is another size's
  function priorityText(p) {
    if (!p) return "not on the list";
    return "rank " + p.rank + ", tier " + p.tier + (p.thisSize || p.bedrooms === null ? "" : " on the " + (p.bedrooms === 0 ? "studio" : p.bedrooms + " bedroom") + " list");
  }
  // The project's certified households in priority order: this home's list first, then tier, then rank; ones not on a list last.
  function byPriority(buyers, prio) {
    var key = function (b) { var p = (prio || {})[b.id]; return p ? [p.thisSize ? 0 : 1, p.tier, p.rank] : [2, 0, 0]; };
    return (buyers || []).slice().sort(function (a, b) { var x = key(a), y = key(b); return x[0] - y[0] || x[1] - y[1] || x[2] - y[2]; });
  }
  // The certified household that comes before this one on the list (the first of them), or null.
  // A household that is out of the running on the list (it declined, didn't respond, was removed) isn't ahead of anyone.
  var OUT_OF_RUNNING = ["Declined", "Unresponsive", "Removed", "Withdrawn", "Ineligible"];
  function ahead(household, ordered, prio) {
    var i = (ordered || []).map(function (b) { return b.id; }).indexOf(household);
    for (var j = 0; j < i; j++) {
      var p = (prio || {})[ordered[j].id];
      if (p && OUT_OF_RUNNING.indexOf(p.status) < 0) return ordered[j];
    }
    return null;
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
    } else if (step === "offer") {
      if (blank(input.household)) e.push("Choose the household to offer the home to.");
      else if (input.sameAsSeller) e.push("The home can't be offered to the household that is selling it.");
      if (!iso(input.due)) e.push("Enter the date they need to answer by.");
      else if (iso(input.due) < today) e.push("The date to answer by is in the past.");
    } else if (step === "answer") {
      if (ANSWERS.indexOf(input.answer) < 0) e.push("Choose what the household said.");
      if (!iso(input.date)) e.push("Enter the date they answered.");
      else if (iso(input.date) > today) e.push("The date they answered can't be in the future.");
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
    if ((step === "buyer" || step === "offer") && !blank(input.household)) {
      // No expiry date means the certification doesn't run out (the organization set no validity period), not that there isn't one.
      if (iso(input.certificationExpires) && iso(input.certificationExpires) < today) w.push("This household's certification expired on " + iso(input.certificationExpires) + ".");
      // The project's list gives the order homes are offered in. Picking someone further down is allowed, with a reason to give.
      if (input.ahead) w.push(input.ahead + " comes before this household on the project's list. Pick this household only if those ahead of it have declined or can't buy this home.");
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
  // sale: { noticeDate, maxPrice, buyer, contractDate, price, status, offered: an offer is out and waiting for an answer }
  // The home is offered to one household at a time. The buyer is the household that accepted: a sale with a buyer
  // has been through both steps (so has one from before offers were kept).
  function progress(sale) {
    var done = {
      start: !!sale, price: !!sale && !blank(sale.maxPrice), offer: !!sale && (!blank(sale.buyer) || !!sale.offered), buyer: !!sale && !blank(sale.buyer),
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

  // ---- offering the home: one household at a time, with an email and a one-page flyer; they accept, or the next is offered
  var OFFERED = "Offered", ACCEPTED = "Accepted", DECLINED = "Declined", NO_RESPONSE = "No response", WITHDRAWN = "Withdrawn";
  var ANSWERS = [ACCEPTED, DECLINED, NO_RESPONSE], OFFER_DAYS = 7;
  // The date an offer made today has to be answered by: the project's days to respond, else 7.
  function offerDue(today, days) {
    var n = num(days), p = iso(today).split("-"), d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + (n >= 1 ? Math.round(n) : OFFER_DAYS)));
    return d.toISOString().slice(0, 10);
  }
  // Where the offers on a sale stand.   offers: [{ id, household, status, offeredOn, due, respondedOn, reason }]
  // -> { open: the one waiting for an answer (or null), accepted (or null), past: the ones declined or not answered,
  //      newest first, out: { household id: true } for every household that has said no or not answered }
  function offers(list) {
    var by = function (a, b) { return iso(a.offeredOn) < iso(b.offeredOn) ? 1 : iso(a.offeredOn) > iso(b.offeredOn) ? -1 : 0; };
    var all = (list || []).slice().sort(by), out = {};
    var past = all.filter(function (o) { return o.status === DECLINED || o.status === NO_RESPONSE; });
    past.forEach(function (o) { out[o.household] = true; });
    return { open: all.filter(function (o) { return o.status === OFFERED; })[0] || null, accepted: all.filter(function (o) { return o.status === ACCEPTED; })[0] || null, past: past, out: out };
  }
  // The household to offer the home to next: the first in priority order that hasn't said no. -> the buyer row, or null
  function nextToOffer(ordered, out) { return (ordered || []).filter(function (b) { return !(out || {})[b.id]; })[0] || null; }
  // "Rivera, 12 Pine St"
  function offerName(household, home) { return (String(household || "").split(",")[0].trim() + ", " + (home || "")).slice(0, 100); }
  // What a household's answer does to its place on the project's lists: an offer shows as Offered, yes as Accepted,
  // no as Declined, silence as Unresponsive. A household declines once for the whole project.
  function entryStatus(offerStatus) { return { Offered: "Offered", Accepted: "Accepted", Declined: "Declined", "No response": "Unresponsive", Withdrawn: "Approved" }[offerStatus] || ""; }

  // The offer email. Stu writes it; staff send it with the flyer attached. The organization's own wording is a
  // message template used for Offer (Settings > Message templates); these words are the starting point.
  var OFFER_DEFAULT = {
    subject: "A home for you: {home}",
    body: "Hello {first name},\n\nGood news. We would like to offer your household the home at {home}.\n\n" +
          "The sale price is {price}. The attached flyer has the details of the home and what it costs each month.\n\n" +
          "Please let us know by {respond by} whether you would like to go ahead. If we haven't heard from you by then, we will offer the home to the next household.\n\n" +
          "If you say yes, the next step is the purchase and sale agreement. If you have questions, or would like to see the home, just reply to this email.\n\n" +
          "Thank you,\n{organization}"
  };
  var OFFER_FIELDS = [["first name", "The primary applicant's first name"], ["household", "The household's name"], ["home", "The home's address"],
                      ["price", "The sale price"], ["respond by", "The date they need to answer by"], ["organization", "Your organization's name"]];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  function longDate(d) { var p = iso(d).split("-"); return p.length === 3 ? MONTHS[+p[1] - 1] + " " + (+p[2]) + ", " + p[0] : ""; }
  function fill(text, values) {
    var v = {};
    Object.keys(values || {}).forEach(function (k) { v[k.toLowerCase()] = values[k]; });
    return String(text || "").replace(/\{([^{}]+)\}/g, function (all, name) {
      var val = v[name.trim().toLowerCase().replace(/\s+/g, " ")];
      return blank(val) ? all : String(val);
    });
  }
  //   o: { email, firstName, household, home, price, due, organization }; template: { subject, body } or nothing -> { to, subject, body }
  function offerEmail(o, template) {
    var t = template && String(template.body || "").trim() ? template : OFFER_DEFAULT;
    var v = { "first name": o.firstName || o.household, household: o.household, home: o.home, price: num(o.price) > 0 ? usd(num(o.price)).replace(/\.00$/, "") : "",
              "respond by": longDate(o.due), organization: o.organization };
    return { to: o.email || "", subject: fill(String(t.subject || "").trim() || OFFER_DEFAULT.subject, v), body: fill(t.body, v) };
  }
  // The photo of the home that goes on its flyer: the one marked for it, else the first one added. -> the photo, or null
  //   photos: [{ id, flyer, created }]
  function flyerPhoto(photos) {
    var list = (photos || []).slice().sort(function (a, b) { return String(a.created || "") < String(b.created || "") ? -1 : String(a.created || "") > String(b.created || "") ? 1 : 0; });
    return list.filter(function (p) { return p.flyer; })[0] || list[0] || null;
  }
  // The one-page flyer for the home, as a document for CLTPdf.make (pdf.js).
  //   h.photo (optional): { jpeg: the picture's bytes, width, height }, placed at the top
  //   h: { home, address, bedrooms, bathrooms, squareFeet, yearBuilt, price, due, organization,
  //        monthly: { principalInterest, taxes, insurance, hoa, leaseFee, reserveFee, total } (any of them, from the project) }
  function flyer(h) {
    var dollars0 = function (v) { return usd(num(v)).replace(/\.00$/, ""); }, has = function (v) { return !blank(v) && !isNaN(num(v)) && num(v) > 0; };
    var facts = [has(h.bedrooms) || h.bedrooms === 0 ? (num(h.bedrooms) === 0 ? "Studio" : num(h.bedrooms) + (num(h.bedrooms) === 1 ? " bedroom" : " bedrooms")) : "",
                 has(h.bathrooms) ? num(h.bathrooms) + (num(h.bathrooms) === 1 ? " bathroom" : " bathrooms") : "",
                 has(h.squareFeet) ? Number(num(h.squareFeet)).toLocaleString("en-US") + " square feet" : "", has(h.yearBuilt) ? "built " + num(h.yearBuilt) : ""].filter(Boolean);
    var blocks = [];
    if (h.photo && h.photo.jpeg) blocks.push({ gap: 4 }, { image: h.photo, maxHeight: 270 });
    if (h.address && h.address !== h.home) blocks.push({ p: h.address });
    if (facts.length) blocks.push({ p: facts.join(", ") + "." });
    if (has(h.price)) blocks.push({ gap: 6 }, { p: "Sale price: " + dollars0(h.price), bold: true, size: 14 });
    var m = h.monthly || {}, parts = [["Principal and interest", m.principalInterest], ["Property taxes", m.taxes], ["Homeowner's insurance", m.insurance], ["HOA dues", m.hoa],
                                      ["Ground lease fee", m.leaseFee], ["Reserve fee", m.reserveFee]].filter(function (x) { return has(x[1]); });
    if (parts.length) {
      var total = has(m.total) ? num(m.total) : cents(parts.reduce(function (t, x) { return t + num(x[1]); }, 0));
      blocks.push({ h: "What it costs each month" }, { table: { columns: [{ label: "", width: 260 }, { label: "Each month", width: 110, align: "right" }],
        rows: parts.map(function (x) { return [x[0], dollars0(x[1])]; }).concat([["Estimated monthly housing cost", dollars0(total)]]) } },
        { p: "An estimate. Your own mortgage payment depends on your loan and your down payment.", size: 9 });
    }
    blocks.push({ h: "Next step" }, { p: (iso(h.due) ? "Let us know by " + longDate(h.due) + " whether you would like to go ahead." : "Let us know whether you would like to go ahead.") +
                                         " If you say yes, the next step is the purchase and sale agreement." });
    if (h.organization) blocks.push({ gap: 6 }, { p: h.organization, bold: true });
    return { title: h.home || "A home for you", footer: (h.organization ? h.organization + ", " : "") + (h.home || ""), blocks: blocks };
  }

  // The first sale of a home (new construction, or a home the organization bought): there is no seller, so no seller's
  // steps. Its price comes from the project. Everything from the offer on is the same as a resale.
  var FIRST = "Initial sale", RESALE = "Resale";
  function stepsFor(type) { return type === FIRST ? STEPS.filter(function (s) { return s.key !== "start" && s.key !== "price"; }) : STEPS; }
  // The project's certified households that can still be offered a home: not one that is out of the running, and not
  // one already offered, or matched to, another home (mine: the household this sale's own offer is with).
  //   buyers: [{ id, ... }]; prio: from priorities()
  function available(buyers, prio, mine) {
    return (buyers || []).filter(function (b) {
      var p = (prio || {})[b.id];
      if (!p || b.id === mine) return true;
      return OUT_OF_RUNNING.indexOf(p.status) < 0 && p.status !== OFFERED && p.status !== ACCEPTED;
    });
  }
  // "12 Pine St resale 2026"; a first sale is "111 Maple Ct sale 2026"
  function saleName(property, date, type) { return ((property || "Home") + (type === FIRST ? " sale " : " resale ") + iso(date).slice(0, 4)).slice(0, 100); }
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
    var occ = newTerms(d.seller || {}, d.price, at, d.appraised), selling = d.seller && d.seller.clt_occupancyid;
    occ.clt_name = occupancyName(d.buyerHouseholdName, d.propertyName);
    occ.clt_role = v.owner; occ.clt_status = v.current; occ.clt_startdate = at;
    occ["clt_property@odata.bind"] = "/" + s.clt_property + "(" + d.propertyId + ")";
    occ["clt_household@odata.bind"] = "/" + s.clt_household + "(" + d.buyerHouseholdId + ")";
    var ops = [
      { method: "POST", path: s.clt_occupancy, body: occ },
      { method: "PATCH", path: s.clt_sale + "(" + d.saleId + ")", body: { clt_status: v.closed, clt_closingdate: at, "clt_buyeroccupancy@odata.bind": "$1" } },
      { method: "PATCH", path: s.clt_property + "(" + d.propertyId + ")", body: { clt_status: v.ownerOccupied, "clt_currentoccupancy@odata.bind": "$1" } },
      { method: "PATCH", path: s.clt_household + "(" + d.buyerHouseholdId + ")", body: { clt_status: v.homeowner } }
    ];
    // A resale ends the seller's occupancy (a first sale has none). It goes third, where it has always been.
    if (selling) ops.splice(2, 0, { method: "PATCH", path: s.clt_occupancy + "(" + d.seller.clt_occupancyid + ")", body: { clt_status: v.past, clt_enddate: at } });
    // The seller becomes a past homeowner, unless they still own another home in the program.
    if (selling && d.sellerHouseholdId && !d.sellerHasOtherHome) {
      ops.push({ method: "PATCH", path: s.clt_household + "(" + d.sellerHouseholdId + ")", body: { clt_status: v.pastHomeowner } });
    }
    return ops;
  }

  var api = { pending: pending, OFFERED: OFFERED, ACCEPTED: ACCEPTED, DECLINED: DECLINED, NO_RESPONSE: NO_RESPONSE, WITHDRAWN: WITHDRAWN, ANSWERS: ANSWERS, OFFER_DAYS: OFFER_DAYS,
              offerDue: offerDue, offers: offers, nextToOffer: nextToOffer, offerName: offerName, entryStatus: entryStatus, OFFER_DEFAULT: OFFER_DEFAULT, OFFER_FIELDS: OFFER_FIELDS,
              offerEmail: offerEmail, flyer: flyer, flyerPhoto: flyerPhoto, longDate: longDate, priorities: priorities, priorityText: priorityText, byPriority: byPriority, ahead: ahead, FUNDING_TYPES: FUNDING_TYPES, LOAN: LOAN, fundingLines: fundingLines, fundingTotal: fundingTotal, fundingProblems: fundingProblems, fundingWarnings: fundingWarnings,
              fundingName: fundingName, fundingSummary: fundingSummary, statementProblem: statementProblem, usd: usd,
              STEPS: STEPS, COPIED: COPIED, num: num, loansOwed: loansOwed, creditValue: creditValue, creditsTotal: creditsTotal, improvements: improvements, buyerGroups: buyerGroups, figures: figures, check: check, warnings: warnings,
              progress: progress, FIRST: FIRST, RESALE: RESALE, stepsFor: stepsFor, available: available, saleName: saleName, occupancyName: occupancyName, newTerms: newTerms, closing: closing };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
