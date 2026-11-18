// Occupancy verification: the rules for the guided page (deployed as clt_/pages/verify.js by build_app.py). Plain
// functions with no Dataverse calls, so tests/test_verify.py runs them in Node on worked examples. The page
// (verify.html) loads, shows and saves. Stu does not send email: the page hands each finished email to staff.
var CLTVerify = (function () {
  var ONLINE = "Online form", PAPER = "Paper";
  // An issue stays open: it is saved on the request, which waits there until the verification is approved (or it is cancelled).
  var OPEN = ["Due", "Sent", "Received", "Issue found"], CLOSED = ["Approved", "Waived"], CANCELLED = "Cancelled";
  var OUTCOMES = ["Approved", "Issue found"];
  // Only an approved (or waived) verification counts as the household being verified.
  function counts(status) { return CLOSED.indexOf(status) >= 0; }
  var DEFAULT = {
    subject: "Your {year} occupancy verification for {home}",
    body: "Hello {first name},\n\nEach year we ask every homeowner to confirm that they still live in their home. It takes a few minutes.\n\n" +
          "Please fill in this form by {due date}:\n{link}\n\nIf you would rather have a paper copy, or have any questions, just reply to this email.\n\n" +
          "Thank you,\n{organization}"
  };
  // The words in curly brackets the page fills in: [field, what it is]
  var FIELDS = [["first name", "The primary applicant's first name"], ["household", "The household's name"], ["home", "The home's address"],
                ["year", "The year being verified"], ["link", "This household's own link to the form"], ["due date", "The date the form is due"],
                ["organization", "Your organization's name"]];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  function blank(v) { return v === null || v === undefined || v === ""; }
  function iso(v) { return blank(v) ? "" : String(v).slice(0, 10); }

  // "Hello {first name}" -> "Hello Maria". Spacing and capitals inside the brackets don't matter. A field with no
  // value, or one the page doesn't know, is left showing so the gap is obvious.
  function fill(text, values) {
    var v = {};
    Object.keys(values || {}).forEach(function (k) { v[k.toLowerCase()] = values[k]; });
    return String(text || "").replace(/\{([^{}]+)\}/g, function (all, name) {
      var val = v[name.trim().toLowerCase().replace(/\s+/g, " ")];
      return blank(val) ? all : String(val);
    });
  }

  // "2026-12-18" -> "December 18, 2026"
  function longDate(d) { var p = iso(d).split("-"); return p.length === 3 ? MONTHS[+p[1] - 1] + " " + (+p[2]) + ", " + p[0] : ""; }

  // What's wrong with the form link from the organization's settings ("" when it's usable).
  function linkProblem(template) {
    var t = String(template || "").trim();
    if (!t) return "There is no annual verification form link yet. Paste it here, or have whoever looks after Stu put it in your organization's settings.";
    if (!/^https?:\/\//i.test(t)) return "The form link should start with https://";
    return "";
  }

  // What a form link can have filled in for each household: [field, what it is]
  var LINK_FIELDS = [["year", "The year being verified"], ["household id", "The household's ID, like H-00012"], ["occupancy id", "The occupancy's record number, like O-00007"], ["code", "The request's own code"],
                     ["first name", "The primary applicant's first name"], ["last name", "The primary applicant's last name"],
                     ["street", "The home's street address"], ["unit", "The home's unit"], ["city", "The home's city"],
                     ["state", "The home's state, as two letters"], ["zip", "The home's ZIP code"]];
  var LINK_NAMES = LINK_FIELDS.map(function (f) { return f[0]; }).join("|");

  // "WA" for a state called "Washington" whose form answers are "WA" and "Washington": the first two-letter answer, else the name.
  function stateCode(name, formAnswers) {
    var two = String(formAnswers || "").split(/\r?\n/).map(function (x) { return x.trim(); }).filter(function (x) { return /^[A-Za-z]{2}$/.test(x); })[0];
    return two ? two.toUpperCase() : String(name || "").trim();
  }

  // This household's own link to the form, filled in so the form opens with their details and the reply can be
  // matched when it comes back.   v: { year, householdId, occupancyId, code, firstName, lastName, street, unit, city, state, zip }
  //   - A link that says where they go ({year}, {household id}, {code}, {first name}, {street} and the rest of
  //     LINK_FIELDS) has them put there. This works for any forms platform: write the link the way that platform
  //     fills in a form from its address, with the form's own question names. This is the one place the form's
  //     questions are matched to Stu. For Cognito Forms:
  //       ...?entry={"OwnerName":{"First":"{first name}","Last":"{last name}"},"Address":{"Line1":"{street}","City":"{city}"},"Code":"{code}"}
  //   - A plain Cognito Forms link gets  ?entry={"Year":"2026","HouseholdID":"H-00012","VerificationCode":"..."}
  //   - Any other plain link (Jotform and most others) gets  ?year=2026&householdId=H-00012&code=...
  // Every value is made safe for an address (and for JSON, inside an entry), so "Unit #3" or "O'Brien & Lee" can't break the link.
  // encodeURIComponent, plus the few marks it leaves alone that mail programs can cut a link at
  function enc(x) { return encodeURIComponent(x).replace(/[!'()*]/g, function (c) { return "%" + c.charCodeAt(0).toString(16).toUpperCase(); }); }
  function linkFor(template, v) {
    v = v || {};
    var t = String(template || "").trim();
    var vals = { "year": v.year, "household id": v.householdId, "occupancy id": v.occupancyId, "code": v.code, "first name": v.firstName, "last name": v.lastName,
                 "street": v.street, "unit": v.unit, "city": v.city, "state": v.state, "zip": v.zip };
    var q = t.indexOf("?"), base = q < 0 ? t : t.slice(0, q), query = q < 0 ? "" : t.slice(q + 1);
    var names = new RegExp("\\{\\s*(" + LINK_NAMES + ")\\s*\\}", "gi");
    function val(name) { var x = vals[name.toLowerCase().replace(/\s+/g, " ")]; return blank(x) ? "" : String(x); }
    if (!new RegExp(names.source, "i").test(t)) {
      var add = /cognitoforms\.com/i.test(t)
        ? "entry=" + enc(JSON.stringify({ Year: String(v.year), HouseholdID: String(v.householdId || ""), VerificationCode: String(v.code || "") }))
        : "year=" + enc(v.year) + "&householdId=" + enc(v.householdId || "") + "&code=" + enc(v.code || "");
      return base + "?" + (query ? query + "&" : "") + add;
    }
    base = base.replace(names, function (all, name) { return enc(val(name)); });
    if (q < 0) return base;
    return base + "?" + query.split("&").map(function (pair) {
      var eq = pair.indexOf("=");
      if (eq < 0) return pair;
      var value = pair.slice(eq + 1), encoded = /%[0-9A-F]{2}/i.test(value), json = /^\s*(\{|\[|%7B|%5B)/i.test(value);
      var filled = value.replace(names, function (all, name) {
        var x = val(name);
        if (json) x = JSON.stringify(x).slice(1, -1);   // quotes and backslashes made safe inside the entry
        return encoded ? enc(x) : x;
      });
      return pair.slice(0, eq) + "=" + (encoded ? filled : enc(filled));
    }).join("&");
  }

  // A code for a request, from random numbers (0 to 255 each): 8 letters and digits with nothing easy to misread.
  function code(bytes) {
    var A = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    return (bytes || []).slice(0, 8).map(function (b) { return A[b % A.length]; }).join("");
  }

  // The default due date: 30 days from today.
  function defaultDue(today) {
    var p = iso(today).split("-"), x = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + 30));
    return x.getUTCFullYear() + "-" + ("0" + (x.getUTCMonth() + 1)).slice(-2) + "-" + ("0" + x.getUTCDate()).slice(-2);
  }

  // One row per current occupancy for the Choose step.
  //   occupancies: [{ id, name, home, household, householdId, email, firstName, lastName, street, unit, city, homeState, zip, lastVerified }]
  //   verifications: [{ id, occupancy, year, status, method }]   year: the year being verified
  // -> [{ ..., request: the occupancy's verification for that year (or null), state: "" | "Open" | "Done",
  //        method: the suggested way (online when there's an email), tick: suggested for this batch }]
  // A household with a request already open or finished for the year isn't suggested again.
  // only: when the page was opened for particular households (from Verification hub), just those are ticked.
  function choose(occupancies, verifications, year, only) {
    var want = only && only.length ? only.map(function (i) { return String(i).toLowerCase(); }) : null;
    return (occupancies || []).map(function (o) {
      var mine = (verifications || []).filter(function (x) { return x.occupancy === o.id && +x.year === +year; });
      var open = mine.filter(function (x) { return OPEN.indexOf(x.status) >= 0; })[0], done = mine.filter(function (x) { return CLOSED.indexOf(x.status) >= 0; })[0];
      var req = open || done || null;
      return { id: o.id, name: o.name || "", home: o.home || "", household: o.household || "", householdId: o.householdId || "", occupancyId: o.occupancyId || "", email: o.email || "",
               firstName: o.firstName || "", lastName: o.lastName || "", street: o.street || "", unit: o.unit || "", city: o.city || "", homeState: o.homeState || "", zip: o.zip || "",
               lastVerified: iso(o.lastVerified), request: req, state: open ? "Open" : done ? "Done" : "",
               method: o.email ? ONLINE : PAPER, tick: !req && (!want || want.indexOf(String(o.id).toLowerCase()) >= 0) };
    });
  }

  // What's wrong with the batch about to start. picks: [{ id, method, email }]; -> [messages]
  function startProblems(picks, input, today) {
    var e = [], online = (picks || []).filter(function (p) { return p.method === ONLINE; });
    if (!(picks || []).length) e.push("Tick at least one household.");
    if (!(+input.year >= 2000 && +input.year <= 2100)) e.push("Enter the year being verified.");
    if (!iso(input.due)) e.push("Enter the date the verification is due.");
    else if (iso(input.due) < today) e.push("The due date is in the past.");
    online.forEach(function (p) { if (!p.email) e.push((p.household || "A household") + " has no email address: use a paper copy for them."); });
    if (online.length) {
      var lp = linkProblem(input.link);
      if (lp) e.push(lp);
      if (!String(input.subject || "").trim() || !String(input.body || "").trim()) e.push("The email needs a subject and a message.");
      else if (!/\{link\}/i.test(input.body)) e.push("The message doesn't have {link} in it, so nobody would get their link.");
    }
    return e;
  }

  // The finished email for one household.   row: from choose(); input: { year, due, link, subject, body }; organization, code
  function email(row, input, organization, requestCode) {
    var link = linkFor(input.link, { year: input.year, householdId: row.householdId, occupancyId: row.occupancyId, code: requestCode, firstName: row.firstName, lastName: row.lastName,
                                     street: row.street, unit: row.unit, city: row.city, state: row.homeState, zip: row.zip });
    var v = { "first name": row.firstName, household: row.household, home: row.home, year: input.year, link: link, "due date": longDate(input.due), organization: organization };
    return { to: row.email, subject: fill(input.subject, v), body: fill(input.body, v), link: link };
  }

  // The message as it goes into a mail program when copied: the same words, with the household's long link as a
  // button instead of the address spelled out. Built as a small table, which every mail program draws the same way.
  //   mail: from email(); color: the organization's accent color ("#526B50"); label: the button's words (else BUTTON)
  var BUTTON = "Open your verification form";
  function emailHtml(mail, color, label) {
    function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
    function text(s) { return esc(s).replace(/\r?\n/g, "<br>"); }
    var bg = /^#[0-9a-f]{6}$/i.test(color || "") ? color : "#2f5d50";
    var button = '<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:8px 0"><tr><td bgcolor="' + bg + '" style="background:' + bg + ';border-radius:6px;padding:12px 22px">' +
                 '<a href="' + esc(mail.link) + '" style="color:#ffffff;text-decoration:none;font-weight:bold;font-family:Arial,sans-serif;font-size:15px">' + esc(label || BUTTON) + "</a></td></tr></table>";
    var parts = String(mail.body || "").split(mail.link);
    // a line break right before or after the button isn't needed: the table sits on its own line
    return '<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5">' + parts.map(function (p, i) {
      if (i > 0) p = p.replace(/^\r?\n/, "");
      if (i < parts.length - 1) p = p.replace(/\r?\n$/, "");
      return text(p);
    }).join(mail.link ? button : "") + "</div>";
  }

  function requestName(year, occupancyName) { return (year + ", " + (occupancyName || "")).slice(0, 100); }

  // What's wrong with closing a request ("" list when it's fine). input: { received, outcome, notes }
  function closeProblems(input, today) {
    var e = [];
    if (!iso(input.received)) e.push("Enter the date the verification came back.");
    else if (iso(input.received) > today) e.push("The received date can't be in the future.");
    if (OUTCOMES.indexOf(input.outcome) < 0) e.push("Choose how it came out.");
    if (input.outcome === "Issue found" && !String(input.notes || "").trim()) e.push("Say what the issue is.");
    return e;
  }

  // What's wrong with a file chosen as the signed form ("" when it's fine).   file: { name, size }
  var FILE_TYPES = ["pdf", "jpg", "jpeg", "png"], FILE_MAX_MB = 20;
  function fileProblem(file) {
    if (!file) return "";
    var ext = (/\.([A-Za-z0-9]+)$/.exec(file.name || "") || [])[1];
    if (FILE_TYPES.indexOf(String(ext || "").toLowerCase()) < 0) return "The signed form should be a PDF, or a JPG or PNG photo.";
    if (file.size > FILE_MAX_MB * 1024 * 1024) return "That file is over " + FILE_MAX_MB + " MB. Scan it at a lower quality and try again.";
    return "";
  }
  // How to show a stored file: "pdf", "image" or "" (offer it as a download).
  function fileKind(name) {
    var ext = String((/\.([A-Za-z0-9]+)$/.exec(name || "") || [])[1] || "").toLowerCase();
    return ext === "pdf" ? "pdf" : ext === "jpg" || ext === "jpeg" || ext === "png" ? "image" : "";
  }

  // Cancelling a verification: what the occupancy's Last occupancy verification date becomes.
  //   occupancyDate: the date on the occupancy now; cancelled: { received, status } the verification being cancelled;
  //   others: [{ received, status }] the occupancy's other verifications
  // -> undefined: leave the date alone (it didn't come from this verification);
  //    otherwise the newest received date among the others that still count, or null when there are none,
  //    so the home shows as overdue again if that was more than the usual time ago (or never).
  function afterCancel(occupancyDate, cancelled, others) {
    var was = cancelled && counts(cancelled.status) ? iso(cancelled.received) : "";
    if (!was || was !== iso(occupancyDate)) return undefined;
    var left = (others || []).filter(function (x) { return counts(x.status) && iso(x.received); }).map(function (x) { return iso(x.received); }).sort();
    return left.length ? left[left.length - 1] : null;
  }

  var api = { ONLINE: ONLINE, PAPER: PAPER, OPEN: OPEN, CLOSED: CLOSED, CANCELLED: CANCELLED, OUTCOMES: OUTCOMES, counts: counts, fileProblem: fileProblem, fileKind: fileKind, afterCancel: afterCancel, DEFAULT: DEFAULT, FIELDS: FIELDS, LINK_FIELDS: LINK_FIELDS, stateCode: stateCode, fill: fill, longDate: longDate,
              linkProblem: linkProblem, linkFor: linkFor, code: code, defaultDue: defaultDue, choose: choose, startProblems: startProblems,
              email: email, emailHtml: emailHtml, BUTTON: BUTTON, requestName: requestName, closeProblems: closeProblems };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
