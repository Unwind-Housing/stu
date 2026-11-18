// Invite: the rules behind the page that invites households to the full application after the results are
// certified (deployed as clt_/pages/invite.js by build_app.py). Plain functions with no Dataverse calls, so
// tests/test_invite.py runs them in Node on worked examples.
var CLTInvite = (function () {
  // The starting words, used when Settings > Message templates has no invitation. Same as the starter row in schema.py.
  var DEFAULT = {
    subject: "You're invited to apply: {project}",
    body: "Hello {first name},\n\n" +
      "Good news. Your household's place in the {project} selection means you are invited to complete a full application.\n\n" +
      "Your personal link:\n{link}\n\n" +
      "Please use this link and not one passed on by someone else. It carries your application number ({application number}), " +
      "which is how we match your full application to you.\n\n" +
      "Please finish the application by {deadline}. If we haven't received it by then, we will offer your place to the next household on the list.\n\n" +
      "It will ask about everyone in your household, your income, debts and savings, and for copies of recent pay stubs, " +
      "bank statements and tax returns. You can save it and come back.\n\n" +
      "Being invited is not yet an offer of a home. We check each full application against the program's rules first.\n\n" +
      "If you have questions, or need help or an accommodation to complete the application, reply to this email.\n\n" +
      "{organization}"
  };
  // The words in curly brackets a message can use, and what each stands for.
  var FIELDS = [["first name", "the primary applicant's first name"], ["household", "the household's name"], ["project", "the project's name"],
                ["application number", "their application number, like A-00012"], ["link", "their own link to the full application"],
                ["deadline", "the date to reply by"], ["organization", "your organization's name"]];
  // List statuses that mean a household is using one of a list's places.
  var ACTIVE = ["Invited", "Application received", "Approved", "Offered", "Accepted"];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  function blank(v) { return v === undefined || v === null || v === ""; }

  // fill("Hello {first name}", { "first name": "Marisol" }) -> "Hello Marisol". A field with no value is left as
  // it is, curly brackets and all, so a gap is obvious before the message is sent.
  function fill(text, values) {
    return String(text == null ? "" : text).replace(/\{([^{}]+)\}/g, function (all, key) {
      var k = key.trim().toLowerCase();
      return Object.prototype.hasOwnProperty.call(values, k) && !blank(values[k]) ? String(values[k]) : all;
    });
  }

  // Staff paste the plain address of the full application form. Stu adds each household's application number to
  // the end, in the way the forms platform expects, so the form opens with the number already filled in.
  //   Cognito Forms: ...?entry={"PrimaryApplicant":{"ApplicationNumber":"A-00012"}}
  //                  NUMBER_FIELD is the form's Application Number question (section, then question). An organization
  //                  whose form names it differently sets FullAppNumberField in its client.json settings.
  //   Any other platform: put {number} in the address where the application number goes.
  var NUMBER_FIELD = "PrimaryApplicant.ApplicationNumber";
  var COGNITO = /^https:\/\/(www\.)?cognitoforms\.com\//i, PLACE = /\{number\}|%7Bnumber%7D/i;

  // What's wrong with a project's full application link, or "" when it will work.
  function linkProblem(template) {
    var t = String(template == null ? "" : template).trim();
    if (!t) return "The project has no full application link yet.";
    if (!/^https?:\/\//i.test(t)) return "The link must start with https://";
    if (PLACE.test(t)) return "";
    if (!COGNITO.test(t)) return "Stu doesn't know how to add the application number to this address. Put {number} in it where the number goes.";
    if (/[?&]entry=/i.test(t)) return "This address already has an entry= part. Paste the form's plain address, the part before the question mark.";
    return "";
  }
  // {"PrimaryApplicant":{"ApplicationNumber":"A-00012"}} from "PrimaryApplicant.ApplicationNumber"
  function prefill(field, number) {
    var parts = String(field || NUMBER_FIELD).split("."), value = String(number);
    for (var i = parts.length - 1; i >= 0; i--) { var o = {}; o[parts[i]] = value; value = o; }
    return JSON.stringify(value);
  }
  // One household's link, made safe to paste into an email (the curly brackets and quotes a form's address can
  // contain are encoded). field: the form's Application Number question, when it isn't NUMBER_FIELD.
  function linkFor(template, number, field) {
    if (linkProblem(template) || blank(number)) return "";
    var t = String(template).trim();
    var link = PLACE.test(t) ? t.replace(new RegExp(PLACE.source, "gi"), String(number))
                             : t + (t.indexOf("?") < 0 ? "?" : "&") + "entry=" + prefill(field, number);
    try { return encodeURI(decodeURI(link)); } catch (e) { return link; }
  }

  // The date to reply by: today plus the project's response days (15 when blank). "yyyy-mm-dd".
  function deadline(today, days) {
    var d = new Date(String(today).slice(0, 10) + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + (blank(days) ? 15 : days));
    return d.toISOString().slice(0, 10);
  }
  // What's wrong with the date staff typed for the full application to be in by, or "" when it's fine.
  function dueProblem(date, today) {
    var d = String(date == null ? "" : date).slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || isNaN(new Date(d + "T00:00:00Z").getTime())) return "Choose the date the full application is due.";
    if (d < String(today).slice(0, 10)) return "The due date is in the past.";
    return "";
  }
  // "2026-12-18" -> "December 18, 2026"
  function longDate(iso) {
    var p = String(iso).slice(0, 10).split("-");
    return MONTHS[+p[1] - 1] + " " + (+p[2]) + ", " + p[0];
  }

  // How many households a list should have invited at once: the project's invites per list (10 when blank), or
  // its minimum per home (2 when blank) times the homes of that size, whichever is more.
  function quota(settings, homes) {
    var perList = blank(settings.perList) ? 10 : settings.perList, perHome = blank(settings.perHome) ? 2 : settings.perHome;
    return Math.max(perList, perHome * (homes || 0));
  }

  // Who to invite next. entries: [{ applicationId, bedrooms, rank, status }], homes: { <size>: how many },
  // settings: { perList, perHome }
  // -> { lists: [{ size, quota, active, suggested: [applicationId] }], applications: { <applicationId>: true } }
  // Each list fills its open places from the top of its waitlist, in rank order. One invitation covers every list
  // a household is on, so a household invited through one list uses a place on its other lists too.
  function suggest(entries, homes, settings) {
    var sizes = {}, chosen = {};
    entries.forEach(function (e) { sizes[e.bedrooms] = 1; });
    var lists = Object.keys(sizes).map(Number).sort(function (a, b) { return a - b; }).map(function (size) {
      var list = entries.filter(function (e) { return e.bedrooms === size; }).sort(function (x, y) { return x.rank - y.rank; });
      var q = quota(settings, (homes || {})[size]);
      var active = list.filter(function (e) { return ACTIVE.indexOf(e.status) >= 0 || chosen[e.applicationId]; }).length;
      var suggested = [];
      list.forEach(function (e) {
        if (active + suggested.length >= q || e.status !== "Waitlist" || chosen[e.applicationId]) return;
        suggested.push(e.applicationId); chosen[e.applicationId] = true;
      });
      return { size: size, quota: q, active: active, suggested: suggested };
    });
    return { lists: lists, applications: chosen };
  }

  var api = { DEFAULT: DEFAULT, FIELDS: FIELDS, ACTIVE: ACTIVE, fill: fill, NUMBER_FIELD: NUMBER_FIELD, linkProblem: linkProblem, linkFor: linkFor,
              deadline: deadline, dueProblem: dueProblem, longDate: longDate, quota: quota, suggest: suggest };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
