// Certify: the rules behind the page where staff review a full application and certify the household
// (deployed as clt_/pages/certify.js by build_app.py). Plain functions with no Dataverse calls, so
// tests/test_certify.py runs them in Node on worked examples. Requirements: docs/FUNCTIONAL-SPEC.md, C-1 to C-8.
//
// Certification asks the same questions as the pre-screen, but of verified figures instead of what the applicant
// said on the screener, and with no buffers: the limits are the limits. So the tests themselves are the pre-screen's
// (prescreen.js); this file works out the verified figures and hands them over.
var CLTCertify = (function () {
  var PERIODS = { "Weekly": 52, "Bi-weekly": 26, "Semi-monthly": 24, "Monthly": 12, "Annually": 1 };
  var DECISIONS = ["Not reviewed", "Accepted", "Adjusted", "Excluded"];
  var SIZES = ["Studio", "1 bedroom", "2 bedrooms", "3 bedrooms", "4+ bedrooms"];

  function blank(v) { return v === undefined || v === null || v === "" || (typeof v === "number" && isNaN(v)); }
  function num(v) {
    if (blank(v)) return null;
    var n = typeof v === "number" ? v : parseFloat(String(v).replace(/[$,\s]/g, ""));
    return isNaN(n) ? NaN : n;
  }
  function cents(n) { return Math.round(n * 100) / 100; }

  // What an income line comes to in a year, from what the applicant entered:
  //   gross pay per period x periods in a year, plus annual bonus and overtime. (The same sum as the
  //   Annualized income column in Dataverse.)
  function annual(line) {
    var gross = num(line.gross) || 0, periods = PERIODS[line.frequency] || 0;
    return cents(gross * periods + (num(line.bonus) || 0) + (num(line.overtime) || 0));
  }

  // The amount a line counts for, from staff's decision:
  //   Accepted: what the applicant entered.  Adjusted: the amount staff typed.  Excluded: nothing.
  //   Not reviewed: null (the review isn't finished).
  function counted(line) {
    if (line.decision === "Accepted") return blank(line.entered) ? 0 : cents(line.entered);
    if (line.decision === "Adjusted") { var v = num(line.verified); return v === null || isNaN(v) ? null : cents(v); }
    if (line.decision === "Excluded") return 0;
    return null;
  }

  // review(lines, what) -> { total, waiting, problems }
  //   lines: [{ label, entered, decision, verified, reason }]     what: "income" | "debt" | "asset" (for messages)
  //   total: the lines that count, added up.  waiting: how many aren't reviewed yet.  problems stop a certification.
  function review(lines, what) {
    var total = 0, waiting = 0, problems = [];
    (lines || []).forEach(function (l) {
      var name = l.label || "A line";
      if (!l.decision || l.decision === "Not reviewed") { waiting++; return; }
      if (DECISIONS.indexOf(l.decision) < 0) { problems.push(name + ": unknown decision."); return; }
      if (l.decision === "Adjusted") {
        var v = num(l.verified);
        if (v === null || isNaN(v) || v < 0) problems.push(name + ": type the verified amount for this adjusted " + what + " line.");
      }
      if ((l.decision === "Adjusted" || l.decision === "Excluded") && !String(l.reason || "").trim())
        problems.push(name + ": say why this " + what + " line was " + l.decision.toLowerCase() + ".");
      var c = counted(l);
      if (c !== null) total += c;
    });
    return { total: cents(total), waiting: waiting, problems: problems };
  }

  // 100% of AMI for a household size, from a county's 50% limits: twice the 50% limit. Over 8 people, HUD's rule:
  // the 4-person limit x (1.32 + 0.08 for each person over 8). limits: { 1: ..., 8: ... }. null when unknown.
  function limit50(limits, size) {
    if (!limits || blank(size) || size < 1) return null;
    var v = size <= 8 ? limits[size] : blank(limits[4]) ? null : limits[4] * (1.32 + 0.08 * (size - 8));
    return blank(v) || !(v > 0) ? null : v;
  }
  function ami100(limits, size) { var l = limit50(limits, size); return l === null ? null : cents(l * 2); }
  // Income as a percent of AMI, a whole number, worked out the way the application's own figure is:
  // income x 50 / the 50% limit.
  function amiPct(income, limits, size) {
    var l = limit50(limits, size);
    return l === null || blank(income) || !(income > 0) ? null : Math.round(income * 50 / l);
  }

  // figures(input) -> the verified figures and what's left to do.
  //   input: { size, income: [lines], debts: [lines], assets: [lines], limits }
  function figures(input) {
    var inc = review(input.income, "income"), debt = review(input.debts, "debt"), asset = review(input.assets, "asset");
    var size = num(input.size), problems = inc.problems.concat(debt.problems, asset.problems);
    if (size === null || isNaN(size) || size < 1 || size !== Math.round(size)) problems.unshift("Type the certified household size.");
    var waiting = inc.waiting + debt.waiting + asset.waiting;
    return { size: size, income: inc.total, monthlyDebt: debt.total, assets: asset.total, waiting: waiting, problems: problems,
             ami100: ami100(input.limits, size), amiPct: amiPct(inc.total, input.limits, size) };
  }

  // The words the pre-screen uses about a screener, said about a review instead.
  function reword(text) {
    return String(text == null ? "" : text)
      .replace(/Stated income as a % of AMI isn't worked out\. Check the county, household size and AMI limits on the application\./g,
               "Income as a % of AMI can't be worked out. Check that the application has AMI limits for its county, and the certified household size.")
      .replace(/Stated income/g, "Certified income").replace(/Stated non-retirement assets/g, "Certified assets")
      .replace(/no stated income on the screener/g, "no certified income").replace(/no stated monthly debt on the screener/g, "no certified monthly debt")
      .replace(/No stated non-retirement assets on the screener\./g, "No certified assets.")
      .replace(/Says they are a first-time buyer\./g, "Staff confirmed: a first-time buyer.")
      .replace(/Not a first-time buyer and no exception claimed\./g, "Staff have not confirmed the household is a first-time buyer.")
      .replace(/Says they have lived or worked locally for the required time\./g, "Staff confirmed: lived or worked locally for the required time.")
      .replace(/Says they have not lived or worked locally for the required time\./g, "Staff have not confirmed the local tie.")
      .replace(/Will live in the home as their primary residence\./g, "Staff confirmed: will live in the home as their primary residence.")
      .replace(/Says the home would not be their primary residence\./g, "Staff have not confirmed the home will be their primary residence.")
      .replace(/the limit with the 0% buffer is /g, "the limit is ")
      .replace(/Certification checks verified income\./g, "").replace(/ Certification checks it\./g, "")
      .replace(/The project has no priorities yet/g, "The project has no priorities");
  }

  // run(input, rules, priorities, prescreen) -> { figures, checks, sizes, result, notes, canCertify, blockers }
  //   input:  figures()'s input, plus { sizesListed: [home sizes they are on a list for],
  //           confirmed: { firstTimeBuyer, localTie, primaryResidence, education } }      what staff ticked
  //   rules:  as the pre-screen's (prescreen.js), plus educationRequired. Buffers, credit and bankruptcy are ignored.
  //   prescreen: the pre-screen rules (CLTPrescreen); left out in the page, where it is already loaded.
  // The household can be certified when the review is finished, every general test passes, and both ratios pass
  // for at least one home size it is on a list for.
  function run(input, rules, priorities, prescreen) {
    var P = prescreen || (typeof CLTPrescreen !== "undefined" ? CLTPrescreen : null);
    var f = figures(input), c = input.confirmed || {};
    var strict = {};
    Object.keys(rules || {}).forEach(function (k) { strict[k] = rules[k]; });
    strict.incomeBuffer = 0; strict.housingRatioBuffer = 0; strict.debtRatioBuffer = 0;     // no leeway on verified figures
    strict.minCredit = null; strict.bankruptcyYears = null;                              // the lender's business by now
    var out = P.run({ householdSize: f.size, income: f.income, monthlyDebt: f.monthlyDebt, assets: f.assets, amiPct: f.amiPct,
                      credit: null, bankruptcy: null, firstTimeBuyer: !!c.firstTimeBuyer, fthbException: false, localTie: !!c.localTie,
                      primaryResidence: !!c.primaryResidence, sizesWanted: input.sizesListed || [] }, strict, priorities || []);
    var checks = out.checks.map(function (k) {
      return { test: k.test, size: k.size, value: k.value, limit: k.limit, result: k.result, notes: reword(k.notes) };
    });
    if (rules && rules.educationRequired) {
      checks.push({ test: "Homebuyer education", size: null, value: null, limit: null, result: c.education ? "Pass" : "Fail",
                    notes: c.education ? "Staff confirmed: homebuyer education is complete." : "Staff have not confirmed that homebuyer education is complete." });
    }
    var general = checks.filter(function (k) { return k.size === null; });
    var failed = general.filter(function (k) { return k.result === "Fail"; }), unsure = general.filter(function (k) { return k.result === "Needs review"; });
    var sizes = out.result === "Eligible for selection" ? out.sizes : [];
    var blockers = f.problems.slice();
    if (f.waiting) blockers.push(f.waiting + (f.waiting === 1 ? " line still isn't reviewed." : " lines still aren't reviewed."));
    failed.forEach(function (k) { blockers.push(k.test + ": " + k.notes); });
    unsure.forEach(function (k) { blockers.push(k.test + ": " + k.notes); });
    if (!failed.length && !unsure.length && !sizes.length) {
      var why = checks.filter(function (k) { return k.size !== null && k.result !== "Pass"; }).map(function (k) { return k.test + ", " + k.notes; });
      blockers.push("The household doesn't pass both ratios for any home size it is on a list for." + (why.length ? " " + why.join(" ") : ""));
    }
    var result = failed.length || (!unsure.length && !sizes.length && !f.waiting && !f.problems.length) ? "Does not pass" : blockers.length ? "Not finished" : "Passes";
    return { figures: f, checks: checks, sizes: sizes, result: result, canCertify: !blockers.length, blockers: blockers,
             notes: blockers.length ? blockers.join("\n") : "Passes every test. Certified for: " + sizes.map(function (s) { return SIZES[Math.min(s, 4)]; }).join(", ") + "." };
  }

  // ---------------------------------------------------------------- the household's documents
  // The form saves each household's uploads in the organization's own share. Stu never holds a file: it knows the
  // names (they arrive with the entry) and where the household's folder is.
  var FOLDER_PATTERN = "{last name} - Entry {entry number}";

  function isFile(v) { return v && typeof v === "object" && typeof v.Name === "string" && ("ContentType" in v || "Size" in v); }
  // "MostRecentFederalTaxReturnForm1040ForEachAdultWhoFiles" -> "Most recent federal tax return form 1040 for each adult who files"
  function humanize(key) {
    var words = String(key).replace(/([a-z])([A-Z0-9])/g, "$1 $2").replace(/([0-9])([A-Za-z])/g, "$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
      .replace(/\s+\d+$/, "").trim().split(/\s+/);
    return words.map(function (w, i) { return i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : /^[A-Z0-9]{2,}$/.test(w) ? w : w.toLowerCase(); }).join(" ")
      .replace(/\b([Ww]) (\d)\b/g, "$1-$2").replace(/(\d) s\b/g, "$1s");
  }
  // A long question shortened to something that fits a table.
  function shorten(label, max) {
    max = max || 80;
    if (label.length <= max) return label;
    var cut = label.slice(0, max); cut = cut.slice(0, Math.max(cut.lastIndexOf(" "), 20));
    return cut + "...";
  }
  // documents(entry) -> { lines: [{ id, number, values, files }], groups: [{ label, files }], lastName }
  //   entry: the form entry as it was posted (kept on the Form submission).
  //   lines:  every line of a repeating section, with its own ID, its number in that section (1, 2, 3: the form's own
  //           item number where it gives one, else its position), the text answers on it, and the files uploaded on it.
  //   groups: uploads that belong to the household as a whole, by what the question asked for.
  //   lastName: the first name answer's last name (the primary applicant's, as typed on this entry), which is what
  //             a form names the household's folder with.
  // It needs no knowledge of the form: any answer that is a list of files is a set of documents.
  function documents(entry) {
    var lines = [], groups = [], lastName = "";
    function walk(node, line) {
      Object.keys(node || {}).forEach(function (key) {
        var v = node[key];
        if (!lastName && !line && v && typeof v === "object" && !Array.isArray(v) && typeof v.Last === "string" && "First" in v) lastName = v.Last.trim();
        if (Array.isArray(v) && v.length && v.every(isFile)) {
          var names = v.map(function (f) { return f.Name; });
          if (line) line.files = line.files.concat(names); else groups.push({ label: shorten(humanize(key)), files: names });
        } else if (Array.isArray(v) && v.some(function (x) { return x && typeof x === "object" && !isFile(x); })) {
          v.forEach(function (item, index) {
            if (!item || typeof item !== "object") return;
            var rec = line || { id: blank(item.Id) ? "" : String(item.Id), files: [],
                                number: typeof item.ItemNumber === "number" && item.ItemNumber > 0 ? item.ItemNumber : index + 1,
                                values: Object.keys(item).map(function (k) { return item[k]; }).filter(function (x) { return typeof x === "string" && x.trim(); })
                                                         .map(function (x) { return x.trim().toLowerCase(); }) };
            if (!line) lines.push(rec);
            walk(item, rec);
          });
        } else if (v && typeof v === "object" && !Array.isArray(v) && !isFile(v)) walk(v, line);
      });
    }
    if (entry && typeof entry === "object") walk(entry, null);
    return { lines: lines, groups: groups, lastName: lastName };
  }
  // Where a household-wide upload belongs in the review, from what its question asked for:
  //   income | debts | assets (shown with that section), firstTimeBuyer | localTie | education (shown with that
  //   confirmation), or other. It reads the wording, so it works for any form that asks in ordinary words.
  var PLACES = [["education", /education|course|certificate/i], ["localTie", /resid|local|address|live[sd]? in|work(ed)? (in|for)/i],
                ["firstTimeBuyer", /first.?time|homebuyer verification|supporting documentation|divorce|inspector/i],
                ["income", /tax return|1040|w-?2|pay ?stub|income|benefit|award letter/i], ["debts", /credit report|debt|loan statement/i],
                ["assets", /gift|asset|bank statement|account statement/i]];
  function place(groups) {
    var out = { income: [], debts: [], assets: [], firstTimeBuyer: [], localTie: [], education: [], other: [] };
    (groups || []).forEach(function (g) {
      var hit = PLACES.filter(function (p) { return p[1].test(g.label); })[0];
      out[hit ? hit[0] : "other"].push(g);
    });
    return out;
  }
  // What a line is called, the way a form that numbers its uploads calls it: "Income 1", "Debt 2", "Account 1".
  // The number is the line's number in its section on the form, so it matches the start of that line's file names
  // in the folder.
  var TAGS = { income: "Income", debt: "Debt", asset: "Account" };
  function lineTag(kind, number) { return number > 0 ? TAGS[kind] + " " + number : ""; }

  // The files uploaded on one of Stu's lines. formItemId is the line's own (the entry ID, the kind, then the form's
  // line ID); label is something the applicant typed on that line (the payer, creditor or institution), used to
  // tell lines apart when two sections number their lines the same way. null when it can't be told.
  function lineFor(docs, formItemId, label) {
    var id = String(formItemId || "").split("-").pop(), want = String(label || "").trim().toLowerCase();
    var same = (docs.lines || []).filter(function (l) { return l.id !== "" && l.id === id; });
    var hit = same.filter(function (l) { return want && l.values.indexOf(want) >= 0; });
    if (hit.length) return hit[0];
    return same.length === 1 ? same[0] : null;
  }
  function filesFor(docs, formItemId, label) { var l = lineFor(docs, formItemId, label); return l ? l.files : null; }
  // "5-3" -> "3": the entry's own number, without the form's.
  function entryNumber(entryId) { return String(entryId == null ? "" : entryId).split("-").pop(); }
  // The name of a household's folder, from the organization's pattern.
  function folderName(pattern, values) {
    return String(pattern || FOLDER_PATTERN).replace(/\{([^{}]+)\}/g, function (all, key) {
      var k = key.trim().toLowerCase();
      return Object.prototype.hasOwnProperty.call(values, k) && !blank(values[k]) ? String(values[k]) : all;
    }).trim();
  }
  // What's wrong with the folder address staff pasted, or "".
  function folderProblem(parent) {
    var t = String(parent == null ? "" : parent).trim();
    if (!t) return "The project has no application documents folder yet.";
    if (!/^https:\/\//i.test(t)) return "The address must start with https://";
    if (/sharepoint\.com\/:[a-z]:\//i.test(t)) return "That is a sharing link. Open the folder in your browser and copy the address from the address bar instead.";
    return "";
  }
  // The address of one household's folder inside the folder staff pasted.
  //   An address with {folder} in it (any share): the folder's name goes there. A Google Drive search works this way.
  //   A SharePoint address: as copied from the browser (…/Forms/AllItems.aspx?id=%2Fsites%2F…), or a plain path.
  function folderLink(parent, name) {
    if (folderProblem(parent) || blank(name) || /[{}]/.test(name)) return "";
    var t = String(parent).trim();
    if (/\{folder\}|%7Bfolder%7D/i.test(t)) return t.replace(/\{folder\}|%7Bfolder%7D/gi, encodeURIComponent(name));
    var m = /^(https:\/\/[^\/]+)\/.*[?&]id=([^&]+)/i.exec(t), base;
    if (m) { try { base = m[1] + decodeURIComponent(m[2]); } catch (e) { return ""; } }
    else base = t.split(/[?#]/)[0];
    try { base = decodeURI(base); } catch (e) { /* leave it as it is */ }
    return encodeURI(base.replace(/\/+$/, "") + "/" + name).replace(/#/g, "%23").replace(/\?/g, "%3F");
  }

  // The day a certification stops being good: the certified date plus the rules' days. null when the rules give none.
  function expires(date, days) {
    if (blank(days) || !(days > 0)) return null;
    var d = new Date(String(date).slice(0, 10) + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  }

  var api = { PERIODS: PERIODS, DECISIONS: DECISIONS, SIZES: SIZES, num: num, annual: annual, counted: counted, review: review,
              limit50: limit50, ami100: ami100, amiPct: amiPct, figures: figures, reword: reword, run: run, expires: expires,
              FOLDER_PATTERN: FOLDER_PATTERN, humanize: humanize, documents: documents, place: place, lineTag: lineTag, lineFor: lineFor, filesFor: filesFor, entryNumber: entryNumber,
              folderName: folderName, folderProblem: folderProblem, folderLink: folderLink };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
