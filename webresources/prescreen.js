// Stu pre-screen: the rules, as one plain function (deployed as clt_/pages/prescreen.js by build_app.py).
// No Dataverse calls in here, so the same code runs in the page and in the offline test (tests/test_prescreen.py).
// It tests what the screener says (self-reported) against the project's rules. Certification checks the same
// rules again later against verified figures. Plan and decisions: docs/plans/prescreen-plan.md.
//
// run(app, rules, priorities) -> { checks: [{test, size, value, limit, result, notes}], result, notes, sizes }
//   app:        { householdSize, income, monthlyDebt, assets, amiPct, credit, bankruptcy, firstTimeBuyer,
//                 fthbException, localTie, primaryResidence, sizesWanted: [bedrooms] }
//   rules:      { maxAmi, minAmi, incomeBuffer (% over the limit), firstTimeBuyerRequired, localTieRequired, assetLimit,
//                 housingRatioMax, housingRatioBuffer, debtRatioMax, debtRatioBuffer (points), minCredit, bankruptcyYears, checkAffordability,
//                 cost: {bedrooms: monthly housing cost},      (project value, else the organization's)
//                 bands: [{ name, maxAmi, cost: {bedrooms: monthly housing cost} }] }
//               bands are the project's income bands, lowest first; the last has no maxAmi (everyone above the
//               band before it). When a project has them, the monthly housing cost comes from the band the
//               household's stated income falls in, because the interest rate or the price depends on income.
//               With no bands, cost is used for everyone.
//   priorities: [{ bedrooms, householdSize }]   which household sizes may apply for a home size
// Bedrooms: 0 = studio, 4 = 4 or more.
var CLTPrescreen = (function () {
  var PASS = "Pass", FAIL = "Fail", REVIEW = "Needs review";
  var CREDIT = ["300 - 579", "580 - 669", "670 - 739", "740 - 799", "800 - 850"];
  var SIZES = ["Studio", "1 bedroom", "2 bedrooms", "3 bedrooms", "4+ bedrooms"];

  function blank(v) { return v === null || v === undefined || v === ""; }
  function money(n) { return "$" + Math.round(n).toLocaleString("en-US"); }
  function pct(n) { return (Math.round(n * 10) / 10) + "%"; }
  function sizeName(b) { return SIZES[Math.min(b, 4)]; }
  // "2 bedrooms; 3 bedrooms" (how Dataverse shows a multi-select) -> [2, 3]
  function sizesFromLabels(text) {
    return (text || "").split(";").map(function (s) { return SIZES.indexOf(s.trim()); })
      .filter(function (i) { return i >= 0; }).sort();
  }

  function run(app, rules, priorities) {
    var checks = [];
    function add(test, result, value, limit, notes, size) {
      checks.push({ test: test, size: blank(size) ? null : size, value: blank(value) ? null : value,
                    limit: blank(limit) ? null : limit, result: result, notes: notes });
    }

    // ---- income, both ends
    if (!blank(rules.maxAmi)) {
      // The buffer is how far over the limit a stated income may be: 10 means up to 10% over (80% becomes 88%).
      var buffer = blank(rules.incomeBuffer) ? 10 : rules.incomeBuffer;
      var top = Math.round(rules.maxAmi * (100 + buffer)) / 100;
      if (blank(app.amiPct)) {
        add("Income limit", REVIEW, null, top, "Stated income as a % of AMI isn't worked out. Check the county, household size and AMI limits on the application.");
      } else if (app.amiPct <= rules.maxAmi) {
        add("Income limit", PASS, app.amiPct, top, "Stated income is " + app.amiPct + "% of AMI; the limit is " + rules.maxAmi + "%.");
      } else if (app.amiPct <= top) {
        add("Income limit", PASS, app.amiPct, top, "Stated income is " + app.amiPct + "% of AMI: over the " + rules.maxAmi +
            "% limit but inside the " + buffer + "% buffer (" + top + "%). Certification checks verified income.");
      } else {
        add("Income limit", FAIL, app.amiPct, top, "Stated income is " + app.amiPct + "% of AMI; the limit with the " + buffer + "% buffer is " + top + "%.");
      }
    }
    if (!blank(rules.minAmi)) {
      if (blank(app.amiPct)) add("Minimum income", REVIEW, null, rules.minAmi, "Stated income as a % of AMI isn't worked out.");
      else add("Minimum income", app.amiPct >= rules.minAmi ? PASS : FAIL, app.amiPct, rules.minAmi,
               "Stated income is " + app.amiPct + "% of AMI; the minimum is " + rules.minAmi + "%.");
    }

    // ---- yes or no rules
    if (rules.firstTimeBuyerRequired) {
      if (app.firstTimeBuyer === true) add("First-time buyer", PASS, null, null, "Says they are a first-time buyer.");
      else if (app.firstTimeBuyer === false && app.fthbException) add("First-time buyer", PASS, null, null, "Not a first-time buyer, but claims an exception. Certification checks it.");
      else if (app.firstTimeBuyer === false) add("First-time buyer", FAIL, null, null, "Not a first-time buyer and no exception claimed.");
      else add("First-time buyer", REVIEW, null, null, "The screener doesn't say whether they are a first-time buyer.");
    }
    if (rules.localTieRequired) {
      if (app.localTie === true) add("Local tie", PASS, null, null, "Says they have lived or worked locally for the required time.");
      else if (app.localTie === false) add("Local tie", FAIL, null, null, "Says they have not lived or worked locally for the required time.");
      else add("Local tie", REVIEW, null, null, "The screener doesn't say whether they have a local tie.");
    }
    if (app.primaryResidence === true) add("Primary residence", PASS, null, null, "Will live in the home as their primary residence.");
    else if (app.primaryResidence === false) add("Primary residence", FAIL, null, null, "Says the home would not be their primary residence.");
    else add("Primary residence", REVIEW, null, null, "The screener doesn't say whether the home would be their primary residence.");

    // ---- assets, credit, bankruptcy
    if (!blank(rules.assetLimit) && rules.assetLimit > 0) {
      if (blank(app.assets)) add("Asset limit", REVIEW, null, rules.assetLimit, "No stated non-retirement assets on the screener.");
      else add("Asset limit", app.assets <= rules.assetLimit ? PASS : FAIL, app.assets, rules.assetLimit,
               "Stated non-retirement assets are " + money(app.assets) + "; the limit is " + money(rules.assetLimit) + ".");
    }
    if (!blank(rules.minCredit)) {
      var have = CREDIT.indexOf(app.credit), need = CREDIT.indexOf(rules.minCredit);
      if (need < 0) add("Credit", REVIEW, null, null, "The project's minimum credit range (" + rules.minCredit + ") isn't a score range.");
      else if (have < 0) add("Credit", REVIEW, null, null, "The applicant " + (blank(app.credit) ? "gave no credit range" : "doesn't know their credit range") +
                             "; the minimum is " + rules.minCredit + ".");
      else add("Credit", have >= need ? PASS : FAIL, null, null, "Credit range " + app.credit + "; the minimum is " + rules.minCredit + ".");
    }
    if (!blank(rules.bankruptcyYears) && rules.bankruptcyYears > 0) {
      var yrs = rules.bankruptcyYears;   // the screener asks about the past 3 years
      if (blank(app.bankruptcy)) add("Bankruptcy", REVIEW, null, yrs, "The screener doesn't say whether there was a bankruptcy.");
      else if (app.bankruptcy === false) add("Bankruptcy", PASS, null, yrs, "No bankruptcy in the past 3 years." +
               (yrs > 3 ? " The look-back is " + yrs + " years; certification checks the rest." : ""));
      else if (yrs >= 3) add("Bankruptcy", FAIL, null, yrs, "A bankruptcy in the past 3 years; the look-back is " + yrs + " years.");
      else add("Bankruptcy", REVIEW, null, yrs, "A bankruptcy in the past 3 years, but the look-back is only " + yrs + ". Ask when it was.");
    }

    // ---- which home sizes fit the household
    var wanted = (app.sizesWanted || []).slice().sort(), fits = [], misfits = [];
    function fit(b) {
      return priorities.some(function (p) {
        return p.householdSize === app.householdSize && (b >= 4 ? p.bedrooms >= 4 : p.bedrooms === b);
      });
    }
    if (blank(app.householdSize) || !wanted.length) {
      add("Household size fits", REVIEW, null, null, blank(app.householdSize) ? "No household size on the screener." : "The screener doesn't say which home sizes they want.");
    } else if (!priorities.length) {
      add("Household size fits", REVIEW, null, null, "The project has no priorities yet (which household sizes fit each home size).");
    } else {
      wanted.forEach(function (b) { (fit(b) ? fits : misfits).push(b); });
      add("Household size fits", fits.length ? PASS : FAIL, fits.length, 1,
          "Household of " + app.householdSize + ". " + (fits.length ? "Fits: " + fits.map(sizeName).join(", ") + ". " : "") +
          (misfits.length ? "Doesn't fit: " + misfits.map(sizeName).join(", ") + "." : ""));
    }

    // ---- which income band the household is in (when the project's costs depend on income)
    var bands = rules.bands || [], band = null, lower = null, lowerWhy = "";
    var ibuf = blank(rules.incomeBuffer) ? 10 : rules.incomeBuffer;
    if (bands.length) {
      var at = bands.length - 1;
      if (!blank(app.amiPct)) {
        for (var i = 0; i < bands.length - 1; i++) {
          if (!blank(bands[i].maxAmi) && app.amiPct <= bands[i].maxAmi) { at = i; break; }
        }
      }
      band = bands[at];
      // Screener income is rough. A household just over a band's top, inside the income buffer, may really
      // belong in the band below, where the home costs less.
      if (at > 0 && !blank(app.amiPct) && app.amiPct <= bands[at - 1].maxAmi * (100 + ibuf) / 100) {
        lower = bands[at - 1];
        lowerWhy = "Stated income is " + app.amiPct + "% of AMI, inside the " + ibuf + "% buffer of the " + lower.name.toLowerCase() + " band";
      } else if (at > 0 && blank(app.amiPct)) {
        // No % of AMI, so the band is unknown: tested at the highest band, with the lowest as the other possibility.
        lower = bands[0];
        lowerWhy = "Stated income as a % of AMI isn't worked out, so they could be in the " + lower.name.toLowerCase() + " band";
      }
    }
    function costIn(which, b) { return which ? (which.cost || {})[b] : (rules.cost || {})[b]; }

    // ---- can they afford it: both ratios, once per home size that fits
    var sizeOk = {}, sizeReview = {};
    fits.forEach(function (b) { sizeOk[b] = true; });
    if (rules.checkAffordability !== false && fits.length &&
        (!blank(rules.housingRatioMax) || !blank(rules.debtRatioMax))) {
      var monthly = blank(app.income) ? 0 : app.income / 12;
      // The ratio rows for one home size at one monthly cost: [{ label, result, value, limit, notes }]
      var ratios = function (cost) {
        var rows = [], row = function (label, result, value, limit, notes) {
          rows.push({ label: label, result: result, value: value, limit: limit, notes: notes });
          return rows;
        };
        if (monthly <= 0) return row("Housing ratio", REVIEW, null, rules.housingRatioMax, "no stated income on the screener.");
        if (blank(cost) || cost <= 0) return row("Housing ratio", REVIEW, null, rules.housingRatioMax, "the project has no monthly housing cost for this home size.");
        if (!blank(rules.housingRatioMax)) {
          var front = cost / monthly * 100;
          var fcap = rules.housingRatioMax + (rules.housingRatioBuffer || 0);
          row("Housing ratio", front <= fcap ? PASS : FAIL, Math.round(front * 10) / 10, fcap,
              money(cost) + " / " + money(monthly) + " a month = " + pct(front) + "; the limit is " + rules.housingRatioMax + "%" +
              (rules.housingRatioBuffer ? " plus a " + rules.housingRatioBuffer + " point buffer" : "") + ".");
        }
        if (!blank(rules.debtRatioMax)) {
          var cap = rules.debtRatioMax + (rules.debtRatioBuffer || 0);
          if (blank(app.monthlyDebt)) return row("Total debt ratio", REVIEW, null, cap, "no stated monthly debt on the screener.");
          var back = (cost + app.monthlyDebt) / monthly * 100;
          row("Total debt ratio", back <= cap ? PASS : FAIL, Math.round(back * 10) / 10, cap,
              "(" + money(cost) + " + " + money(app.monthlyDebt) + " debt) / " + money(monthly) + " a month = " + pct(back) + "; the limit is " +
              rules.debtRatioMax + "%" + (rules.debtRatioBuffer ? " plus a " + rules.debtRatioBuffer + " point buffer" : "") + ".");
        }
        return rows;
      };
      fits.forEach(function (b) {
        var name = sizeName(b) + (band && bands.length > 1 ? ", " + band.name.toLowerCase() : "");
        var rows = ratios(costIn(band, b));
        // Fails at this band's cost, but would pass in the band just below, and stated income is close enough
        // to the line that it could be either: a person decides.
        if (lower && rows.some(function (r) { return r.result === FAIL; })) {
          var low = costIn(lower, b), alt = ratios(low);
          if (alt.length && alt.every(function (r) { return r.result === PASS; })) {
            rows.forEach(function (r) {
              if (r.result !== FAIL) return;
              r.result = REVIEW;
              r.notes += " " + lowerWhy + ", where the cost is " + money(low) + " a month and both ratios pass. Check which band they belong in.";
            });
          }
        }
        rows.forEach(function (r) {
          add(r.label, r.result, r.value, r.limit, name + ": " + r.notes, b);
          if (r.result === FAIL) sizeOk[b] = false;
          if (r.result === REVIEW) { sizeOk[b] = false; sizeReview[b] = true; }
        });
      });
    }
    var sizes = fits.filter(function (b) { return sizeOk[b]; });

    // ---- the result. Ratio rows don't fail a household by themselves: it only needs one home size to work.
    var general = checks.filter(function (c) { return c.size === null; });
    var failed = general.filter(function (c) { return c.result === FAIL; });
    var unsure = general.filter(function (c) { return c.result === REVIEW; });
    var result, why = [];
    if (failed.length) {
      result = "Not eligible";
      why = failed.map(function (c) { return c.test + ": " + c.notes; });
    } else if (fits.length && !sizes.length && !Object.keys(sizeReview).length) {
      result = "Not eligible";
      why = ["Can't afford any home size they asked for at the project's ratios."].concat(
        checks.filter(function (c) { return c.size !== null && c.result === FAIL; }).map(function (c) { return c.test + ", " + c.notes; }));
    } else if (unsure.length || !sizes.length) {
      result = "Needs review";
      why = checks.filter(function (c) { return c.result === REVIEW; }).map(function (c) { return c.test + ": " + c.notes; });
    } else {
      result = "Eligible for selection";
      why = ["Eligible for: " + sizes.map(sizeName).join(", ") + "."];
      var out = fits.filter(function (b) { return !sizeOk[b]; });
      if (out.length) why.push("Not for " + out.map(sizeName).join(", ") + " (see the ratio checks).");
      if (misfits.length) why.push("Household size doesn't fit: " + misfits.map(sizeName).join(", ") + ".");
      if (band && bands.length > 1) why.push("Costs tested for the income band: " + band.name.toLowerCase() + ".");
      checks.forEach(function (c) { if (c.test === "Income limit" && /inside the /.test(c.notes)) why.push(c.notes); });
    }
    return { checks: checks, result: result, notes: why.join("\n"), sizes: result === "Eligible for selection" ? sizes : [] };
  }

  return { run: run, sizeName: sizeName, sizesFromLabels: sizesFromLabels, SIZES: SIZES };
})();
if (typeof module !== "undefined") module.exports = CLTPrescreen;
