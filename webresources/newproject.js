// New project: the rules behind the guided page (deployed as clt_/pages/newproject.js by build_app.py).
// Plain functions with no Dataverse calls, so tests/test_newproject.py runs them in Node on worked examples.
// The page (newproject.html) only collects answers, calls check() and plan(), and sends what plan() returns.
//
// state: { name, type, method, opens, closes,                     dates are "yyyy-mm-dd" or ""
//          homes: [{ propertyId, name, bedrooms }],
//          finance: { down, term, perBandPrice },                  down payment %, loan term in years (blank is 30),
//                                                                  and whether each income band has its own prices
//          bands: [{ maxami, rate }],                              income bands, lowest first; the last one has no
//                                                                  maxami: it is everyone above the band before it
//          costs: { <size>: { price, prices: { <band>: price }, taxes, insurance, hoa, lease, reserve } },
//                                                                  size 0 = studio ... 4 = 4 or more bedrooms;
//                                                                  every home of a size has the same price and costs
//          rules: { maxami, minami, firsttimebuyer, localtie, assetlimit, housingratiomax, debtratiomax,
//                   incomebuffer, housingratiobuffer, debtratiobuffer, mincreditrange, bankruptcyyears,
//                   minaffordabilitycheck },                       blank = use the organization's rule
//          priorities: { <size>: { <household size>: tier } } }
//
// Income bands: some loan programs give lower-income buyers a lower interest rate, and some organizations price
// a home by the buyer's income band. Either way the monthly housing cost depends on the household's income, so
// the project keeps one cost per home size for each band and the pre-screen picks the band from stated income.
// A project with no such program has one band, "All buyers".
var CLTNewProject = (function () {
  var SIZES = ["Studio", "1 bedroom", "2 bedrooms", "3 bedrooms", "4+ bedrooms"];
  var SIZE_KEYS = ["studio", "1br", "2br", "3br", "4br"];   // column endings: clt_monthlycost2br, clt_price2br, clt_pi2br
  var COST_COLUMNS = SIZE_KEYS.map(function (k) { return "clt_monthlycost" + k; });
  var STEPS = ["The basics", "The homes", "Price and monthly cost", "The rules", "Who fits which home", "Review and create"];
  // The monthly costs that are the same whatever the loan: [key, project home column, label]
  var COST_PARTS = [
    ["taxes", "clt_propertytaxes", "Property taxes"],
    ["insurance", "clt_insurance", "Homeowner's insurance"],
    ["hoa", "clt_hoadues", "HOA dues"],
    ["lease", "clt_leasefee", "Ground lease fee"],
    ["reserve", "clt_reservefee", "Reserve fee"]
  ];
  var TYPES = ["New construction sale", "Resale"];
  var METHODS = ["Lottery", "First come first served"];
  var MAX_HOUSEHOLD = 8, DEFAULT_TERM = 30;
  // Rule fields that are numbers: [key, column, label, lowest, highest]
  var NUMBER_RULES = [
    ["maxami", "clt_maxami", "Max income (% of AMI)", 1, 300],
    ["minami", "clt_minami", "Min income (% of AMI)", 0, 300],
    ["assetlimit", "clt_assetlimit", "Asset limit", 0, 100000000],
    ["housingratiomax", "clt_housingratiomax", "Housing ratio max (%)", 1, 100],
    ["debtratiomax", "clt_debtratiomax", "Total debt ratio max (%)", 1, 100],
    ["incomebuffer", "clt_incomebuffer", "Income buffer (% over the limit)", 0, 100],
    ["housingratiobuffer", "clt_housingratiobuffer", "Housing ratio buffer (points)", 0, 50],
    ["debtratiobuffer", "clt_debtratiobuffer", "Total debt ratio buffer (points)", 0, 50],
    ["bankruptcyyears", "clt_bankruptcyyears", "Bankruptcy look-back (years)", 0, 20]
  ];
  // Rule fields that are a choice: [key, column, choice name]
  var CHOICE_RULES = [
    ["firsttimebuyer", "clt_firsttimebuyer", "rulechoice"],
    ["localtie", "clt_localtie", "rulechoice"],
    ["mincreditrange", "clt_mincreditrange", "creditrange"]
  ];

  function blank(v) { return v === undefined || v === null || v === "" || (typeof v === "number" && isNaN(v)); }
  function num(v) {
    if (blank(v)) return null;
    var n = typeof v === "number" ? v : parseFloat(String(v).replace(/[$,%\s]/g, ""));
    return isNaN(n) ? NaN : n;
  }
  function ok(n) { return n !== null && !isNaN(n); }
  function cents(n) { return Math.round(n * 100) / 100; }
  // 0 = studio ... 4 = 4 or more bedrooms. The same sizes the screener, the pre-screen and the lists use.
  function sizeOf(bedrooms) { return Math.max(0, Math.min(4, Math.round(bedrooms))); }
  function sizeName(size) { return SIZES[size]; }

  // The home sizes this project sells, smallest first.
  function sizesFor(state) {
    var seen = {};
    (state.homes || []).forEach(function (h) { if (ok(num(h.bedrooms))) seen[sizeOf(num(h.bedrooms))] = 1; });
    return Object.keys(seen).map(Number).sort(function (a, b) { return a - b; });
  }

  // ---------------------------------------------------------------- income bands and what a home costs a month
  function bandsOf(state) { return state.bands && state.bands.length ? state.bands : [{ maxami: "", rate: "" }]; }

  // "All buyers", "Up to 65% of AMI", "Above 65% of AMI" (the last band of several)
  function bandName(state, i) {
    var bands = bandsOf(state);
    if (bands.length === 1) return "All buyers";
    if (i < bands.length - 1) return "Up to " + num(bands[i].maxami) + "% of AMI";
    return "Above " + num(bands[i - 1].maxami) + "% of AMI";
  }

  // The monthly principal and interest on a level-payment loan: the standard mortgage formula.
  //   loan = price less the down payment;  payment = loan x r / (1 - (1 + r)^-n),  r = monthly rate, n = months
  // null when the price or the rate is missing.
  function payment(price, downPct, ratePct, years) {
    price = num(price); ratePct = num(ratePct); downPct = num(downPct); years = num(years);
    if (!ok(price) || !ok(ratePct)) return null;
    var loan = price * (1 - (ok(downPct) ? downPct : 0) / 100);
    var n = (ok(years) && years > 0 ? years : DEFAULT_TERM) * 12, r = ratePct / 100 / 12;
    return cents(r === 0 ? loan / n : loan * r / (1 - Math.pow(1 + r, -n)));
  }

  // The costs that don't depend on the loan, added up (blank parts count as 0). null when nothing is typed.
  function sharedCost(state, size) {
    var c = (state.costs || {})[size] || {}, total = 0, any = false;
    COST_PARTS.forEach(function (part) {
      var v = num(c[part[0]]);
      if (v !== null) { any = true; total += v; }
    });
    return any ? cents(total) : null;
  }

  function priceFor(state, size, band) {
    var c = (state.costs || {})[size] || {}, f = state.finance || {};
    return num(f.perBandPrice && bandsOf(state).length > 1 ? (c.prices || {})[band] : c.price);
  }

  // What a home of this size costs a month for a household in this band:
  //   { price, pi, shared, total }   total is null until there's a mortgage payment to add the rest to
  function bandCost(state, size, band) {
    var f = state.finance || {}, price = priceFor(state, size, band);
    var pi = payment(price, f.down, bandsOf(state)[band].rate, f.term), shared = sharedCost(state, size);
    var total = pi === null || isNaN(pi) || (shared !== null && isNaN(shared)) ? null : cents(pi + (shared || 0));
    return { price: price, pi: pi, shared: shared, total: total };
  }

  function priorityName(size, people) {
    return (size === 0 ? "Studio" : size + (size === 4 ? "+" : "") + " BR") + ", " + people + (people === 1 ? " person" : " persons");
  }

  // A common starting point, for staff to change: at least one person per bedroom and no more than two is
  // tier 1; one person fewer than the bedrooms is tier 2. A studio takes one or two people.
  function startingPriorities(sizes) {
    var out = {};
    sizes.forEach(function (size) {
      var row = {}, beds = Math.max(size, 1);
      for (var n = beds; n <= Math.min(beds * 2, MAX_HOUSEHOLD); n++) row[n] = 1;
      if (size >= 2) row[size - 1] = 2;
      out[size] = row;
    });
    return out;
  }

  // check(state, step) -> { errors: [...], warnings: [...] }. Errors stop Next; warnings are shown and allowed.
  // step is 1 to 5; leave it out to check everything (the Review screen).
  function check(state, step) {
    var errors = [], warnings = [], rules = state.rules || {}, sizes = sizesFor(state);
    var on = function (n) { return !step || step === n; };
    if (on(1)) {
      if (blank(state.name) || !String(state.name).trim()) errors.push("Give the project a name.");
      if (TYPES.indexOf(state.type) < 0) errors.push("Choose what kind of project this is.");
      if (METHODS.indexOf(state.method) < 0) errors.push("Choose how buyers will be selected.");
      if (state.opens && state.closes && state.closes < state.opens) errors.push("Applications can't close before they open.");
      if (state.method === "Lottery" && !state.closes) warnings.push("A lottery needs a date when applications close. You can add it later on the project.");
    }
    if (on(2)) {
      var homes = state.homes || [], ids = {};
      if (!homes.length) errors.push("Tick at least one home.");
      homes.forEach(function (h) {
        var b = num(h.bedrooms);
        if (ids[h.propertyId]) errors.push(h.name + " is ticked twice.");
        ids[h.propertyId] = 1;
        if (b === null) errors.push(h.name + ": type the number of bedrooms (0 for a studio).");
        else if (isNaN(b) || b < 0 || b > 12 || b !== Math.round(b)) errors.push(h.name + ": bedrooms must be a whole number from 0 to 12.");
      });
    }
    if (on(3)) {
      var f = state.finance || {}, bands = bandsOf(state), down = num(f.down), term = num(f.term), last = bands.length - 1;
      var several = bands.length > 1, bandsOk = true;
      if (down !== null && (isNaN(down) || down < 0 || down >= 100)) errors.push("Down payment must be from 0 to 99 percent.");
      else if (down === null) warnings.push("Down payment is blank, so the mortgage payment assumes the buyer borrows the whole price.");
      if (term !== null && (isNaN(term) || term < 1 || term > 50 || term !== Math.round(term))) errors.push("Loan term must be a whole number of years from 1 to 50.");
      bands.forEach(function (b, i) {
        var cut = num(b.maxami), rate = num(b.rate), prev = i ? num(bands[i - 1].maxami) : null;
        if (i < last) {
          if (!ok(cut) || cut < 1 || cut > 300) { bandsOk = false; errors.push("Income band " + (i + 1) + ": type the top of the band as a percent of AMI, from 1 to 300."); }
          else if (ok(prev) && cut <= prev) { bandsOk = false; errors.push("Income band " + (i + 1) + " must go higher than the band before it (" + prev + "% of AMI)."); }
        }
      });
      bands.forEach(function (b, i) {
        var rate = num(b.rate), name = bandsOk ? bandName(state, i) : "Income band " + (i + 1);
        if (rate !== null && (isNaN(rate) || rate < 0 || rate > 25)) errors.push(name + ": the interest rate must be from 0 to 25 percent.");
        else if (rate === null) warnings.push(name + " has no interest rate, so its mortgage payment and monthly housing cost can't be worked out.");
      });
      sizes.forEach(function (size) {
        var c = (state.costs || {})[size] || {}, bad = false;
        COST_PARTS.forEach(function (part) {
          var v = num(c[part[0]]);
          if (v !== null && (isNaN(v) || v < 0)) { bad = true; errors.push(sizeName(size) + ": " + part[2].toLowerCase() + " isn't a number."); }
        });
        bands.forEach(function (b, i) {
          var price = priceFor(state, size, i), who = several && f.perBandPrice && bandsOk ? " (" + bandName(state, i).toLowerCase() + ")" : "";
          if (several && !f.perBandPrice && i) return;   // one price for every band: say it once
          if (price !== null && (isNaN(price) || price <= 0)) { bad = true; errors.push(sizeName(size) + who + ": the sale price isn't a number."); }
          else if (price === null) warnings.push(sizeName(size) + " homes have no sale price yet" + who + ", so there is no monthly housing cost to test applicants against.");
        });
      });
    }
    if (on(4)) {
      NUMBER_RULES.forEach(function (r) {
        var v = num(rules[r[0]]);
        if (v !== null && (isNaN(v) || v < r[3] || v > r[4])) errors.push(r[2] + " must be from " + r[3] + " to " + r[4] + ".");
      });
      var lo = num(rules.minami), hi = num(rules.maxami);
      if (ok(lo) && ok(hi) && lo >= hi) errors.push("Min income must be lower than max income.");
    }
    if (on(5)) {
      sizes.forEach(function (size) {
        var row = (state.priorities || {})[size] || {};
        var any = Object.keys(row).some(function (n) { return !blank(row[n]); });
        if (!any) warnings.push("No household sizes are chosen for " + sizeName(size).toLowerCase() + " homes, so nobody can be eligible for them until you add priorities on the project.");
        Object.keys(row).forEach(function (n) {
          var t = num(row[n]);
          if (t !== null && (isNaN(t) || t < 1 || t > 9 || t !== Math.round(t))) errors.push(priorityName(size, +n) + ": the tier must be a whole number from 1 to 9.");
        });
      });
    }
    return { errors: errors, warnings: warnings };
  }

  // plan(state, choices) -> the one record to send: the project, with its income bands, homes and priorities
  // inside it, so Dataverse creates all of them or none. choices: { <choice name>: { <label>: value } }.
  function plan(state, choices) {
    var rules = state.rules || {}, sizes = sizesFor(state), f = state.finance || {}, bands = bandsOf(state);
    var pick = function (name, label) {
      var v = (choices[name] || {})[label];
      if (v === undefined) throw new Error("Unknown " + name + " value: " + label);
      return v;
    };
    var project = {
      clt_name: String(state.name).trim(),
      clt_projecttype: pick("projecttype", state.type),
      clt_selectionmethod: pick("selectionmethod", state.method),
      clt_status: pick("projectstatus", "Planning"),
      // a first come, first served list with no closing date ranks people as they apply
      clt_rolling: state.method === "First come first served" && !state.closes,
      clt_minaffordabilitycheck: rules.minaffordabilitycheck !== false,
      clt_loantermyears: ok(num(f.term)) ? num(f.term) : DEFAULT_TERM
    };
    if (state.opens) project.clt_applicationopens = state.opens;
    if (state.closes) project.clt_applicationcloses = state.closes;
    if (ok(num(f.down))) project.clt_downpaymentpct = num(f.down);
    NUMBER_RULES.forEach(function (r) { var v = num(rules[r[0]]); if (v !== null) project[r[1]] = v; });
    CHOICE_RULES.forEach(function (r) { if (!blank(rules[r[0]])) project[r[1]] = pick(r[2], rules[r[0]]); });

    // One record per income band, with its price, mortgage payment and monthly housing cost for each home size.
    // This is what the pre-screen reads.
    project.clt_project_projectband_project = bands.map(function (b, i) {
      var band = { clt_name: bandName(state, i), clt_sortorder: i + 1 };
      if (i < bands.length - 1) band.clt_maxami = num(b.maxami);
      if (ok(num(b.rate))) band.clt_interestrate = num(b.rate);
      sizes.forEach(function (size) {
        var c = bandCost(state, size, i), k = SIZE_KEYS[size];
        if (ok(c.price)) band["clt_price" + k] = c.price;
        if (ok(c.pi)) band["clt_pi" + k] = c.pi;
        if (c.total) band["clt_monthlycost" + k] = c.total;
      });
      return band;
    });
    // The project's own figure per home size is the highest band's: what someone sees at a glance on the project.
    sizes.forEach(function (size) { var t = bandCost(state, size, bands.length - 1).total; if (t) project[COST_COLUMNS[size]] = t; });

    // Each home keeps the costs that are the same for every buyer. Its price is filled in when every band pays
    // the same, and its mortgage payment and total when there is only one band.
    project.clt_project_projecthome_project = (state.homes || []).map(function (h) {
      var size = sizeOf(num(h.bedrooms)), c = (state.costs || {})[size] || {};
      var home = { clt_name: h.name, clt_bedrooms: num(h.bedrooms), clt_status: pick("projecthomestatus", "Available"),
                   "clt_property@odata.bind": "/clt_properties(" + h.propertyId + ")" };
      var costs = bands.map(function (b, i) { return bandCost(state, size, i); });
      var same = costs.every(function (x) { return ok(x.price) && x.price === costs[0].price; });
      if (same) home.clt_estimatedprice = costs[0].price;
      COST_PARTS.forEach(function (part) { var v = num(c[part[0]]); if (v !== null) home[part[1]] = v; });
      if (bands.length === 1 && ok(costs[0].pi)) home.clt_principalinterest = costs[0].pi;
      if (bands.length === 1 && costs[0].total) home.clt_estimatedmonthlycost = costs[0].total;
      return home;
    });
    var priorities = [];
    sizes.forEach(function (size) {
      var row = (state.priorities || {})[size] || {};
      Object.keys(row).map(Number).sort(function (a, b) { return a - b; }).forEach(function (people) {
        var tier = num(row[people]);
        if (tier !== null) priorities.push({ clt_name: priorityName(size, people), clt_bedrooms: size,
                                             clt_householdsize: people, clt_tier: tier });
      });
    });
    project.clt_project_projectpriority_project = priorities;
    return project;
  }

  var api = { SIZES: SIZES, SIZE_KEYS: SIZE_KEYS, STEPS: STEPS, TYPES: TYPES, METHODS: METHODS, MAX_HOUSEHOLD: MAX_HOUSEHOLD,
              DEFAULT_TERM: DEFAULT_TERM, NUMBER_RULES: NUMBER_RULES, CHOICE_RULES: CHOICE_RULES, COST_COLUMNS: COST_COLUMNS,
              COST_PARTS: COST_PARTS, num: num, sizeOf: sizeOf, sizeName: sizeName, sizesFor: sizesFor,
              bandsOf: bandsOf, bandName: bandName, payment: payment, sharedCost: sharedCost, priceFor: priceFor,
              bandCost: bandCost, priorityName: priorityName, startingPriorities: startingPriorities,
              check: check, plan: plan };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
