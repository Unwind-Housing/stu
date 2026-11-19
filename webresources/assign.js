// Add to a project: the rules for who can be added, and how (deployed as clt_/pages/assign.js by build_app.py).
// Plain functions with no Dataverse calls, so tests/test_assign.py runs them in Node on worked examples. The page
// (assign.html) loads, shows and saves.
var CLTAssign = (function () {
  var MOVE = "move", COPY = "copy", HELD = "held", HERE = "here", CLOSED = "Closed";
  // A household that has been invited, or is further along than that, is being worked on in its project and stays there.
  var IN_PROCESS = ["Invited", "Application received", "Approved", "Offered", "Accepted"];
  // What a copy carries: the screener answers, and nothing a project decided (Unique ID, pre-screen, stage, review).
  var COPIED = ["clt_name", "clt_firstsubmittedon", "clt_screenersubmitted", "clt_screenerlink", "clt_localtie", "clt_localtiemethod", "clt_housingstatusother",
                "clt_firsttimebuyer", "clt_fthbexceptions", "clt_ownsproperty", "clt_adults", "clt_children", "clt_householdcountsasentered", "clt_homesizes",
                "clt_statedannualincome", "clt_incomepastyear", "clt_age62", "clt_statednonretirementassets", "clt_statedretirementassets", "clt_has1000forclosing",
                "clt_statedmonthlydebt", "clt_creditrange", "clt_bankruptcy3yrs", "clt_primaryresidence", "clt_hbeducation", "clt_preapproval", "clt_accommodation",
                "clt_applicantquestions"];
  // The links a copy keeps: [lookup column, the table it points at]
  var LINKS = [["clt_household", "clt_household"], ["clt_county", "clt_listitem"], ["clt_housingstatus", "clt_listitem"], ["clt_sourceform", "clt_sourceform"],
               ["clt_amilimits", "clt_incomelimitset"], ["clt_eligibilityrules", "clt_eligibility"]];

  function blank(v) { return v === null || v === undefined || v === ""; }

  // How one screener can join a project.
  //   app: { id, project: the project it is in now (or ""), projectName, projectStatus, uniqueId, household }
  //   entries: the List statuses of its entries on its project's lists ([] when it is on none)
  //   target: the project being added to; inTarget: the households already in that project { household id: true }
  // -> { how, why }
  //   here: already in this project, or its household is.
  //   move: not in a project, or in one whose applications haven't closed (no Unique ID yet): it simply moves.
  //   copy: locked to another project, and free to try for another home: it stays there and a copy joins this one.
  //         That is a household on a waitlist that hasn't been invited, one that isn't on a list (not eligible there,
  //         or the lists aren't built yet), one that is out of the running there, and any household of a closed project.
  //   held: invited, or further along, in a project that is still open: it stays where it is.
  function stand(app, entries, target, inTarget) {
    var where = app.projectName || "another project";
    if (app.project && app.project === target) return { how: HERE, why: "Already in this project" };
    if (!app.uniqueId) {
      if (app.household && (inTarget || {})[app.household]) return { how: HERE, why: "This household is already in this project" };
      return { how: MOVE, why: app.project ? "Moves from " + where : "" };
    }
    if (app.household && (inTarget || {})[app.household]) return { how: HERE, why: "This household is already in this project" };
    if (app.projectStatus === CLOSED) return { how: COPY, why: where + " is closed: joins as a copy" };
    var busy = (entries || []).filter(function (s) { return IN_PROCESS.indexOf(s) >= 0; })[0];
    if (busy) return { how: HELD, why: busy + " in " + where + ": stays there" };
    if ((entries || []).indexOf("Waitlist") >= 0) return { how: COPY, why: "On the waitlist in " + where + ", not invited: joins as a copy and keeps its place there" };
    return { how: COPY, why: (entries || []).length ? "Out of the running in " + where + ": joins as a copy" : "Not on a list in " + where + ": joins as a copy" };
  }

  // The copy's screener entry ID. Each application needs its own, and one household gets one copy per project:
  // "1234" into project 9f8e7d6c-... -> "1234~9f8e7d6c"
  function copyEntryId(entryId, target) { return (String(entryId || "") + "~" + String(target || "").replace(/[{}]/g, "").slice(0, 8)).slice(0, 50); }

  // A copy's entry ID has the mark copyEntryId() puts in it.
  function isCopy(entryId) { return String(entryId || "").indexOf("~") >= 0; }
  // One application per household, for counting households and not applications: the original where there is one,
  // else the first in the list. An application with no household counts on its own.
  //   apps: [{ household, entryId, ... }] -> the same rows, fewer of them, in the order given
  function onePerHousehold(apps) {
    var best = {}, out = [];
    (apps || []).forEach(function (a) {
      if (!a.household) return;
      var b = best[a.household];
      if (!b || (isCopy(b.entryId) && !isCopy(a.entryId))) best[a.household] = a;
    });
    (apps || []).forEach(function (a) { if (!a.household || best[a.household] === a) out.push(a); });
    return out;
  }

  // The new application for a copy.   row: the application as read (the COPIED columns and the _..._value of each link)
  //   sets: { table: its entity set name }; stage: the value of the stage Screener submitted
  // -> the body to create. Blank answers are left out.
  function copyBody(row, target, sets, stage) {
    var body = {};
    COPIED.forEach(function (c) { if (!blank(row[c])) body[c] = row[c]; });
    LINKS.forEach(function (l) {
      var id = row["_" + l[0] + "_value"];
      if (id && sets[l[1]]) body[l[0] + "@odata.bind"] = "/" + sets[l[1]] + "(" + id + ")";
    });
    body["clt_project@odata.bind"] = "/" + sets.clt_project + "(" + target + ")";
    body.clt_screenerentryid = copyEntryId(row.clt_screenerentryid, target);
    if (!blank(stage)) body.clt_stage = stage;
    return body;
  }

  // "Add 5 applications to Maple Court? 2 of them are in another project now and will move. 1 is on another project's list ..."
  function confirmText(list, name) {
    var n = (list || []).length, moving = list.filter(function (x) { return x.how === MOVE && x.moving; }).length, copies = list.filter(function (x) { return x.how === COPY; }).length;
    return "Add " + n + " application" + (n === 1 ? "" : "s") + " to " + name + "?" +
      (moving ? " " + moving + (moving === 1 ? " is" : " are") + " in another project now and will move." : "") +
      (copies ? " " + copies + (copies === 1 ? " is" : " are") + " locked to another project and will join as a copy: the original stays where it is, with its Unique ID and its place on any list." : "");
  }

  var api = { MOVE: MOVE, COPY: COPY, HELD: HELD, HERE: HERE, IN_PROCESS: IN_PROCESS, COPIED: COPIED, LINKS: LINKS, stand: stand, copyEntryId: copyEntryId, isCopy: isCopy, onePerHousehold: onePerHousehold,
              copyBody: copyBody, confirmText: confirmText };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
