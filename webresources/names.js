// CLT Stewardship: fill record names from their parts (deployed as clt_/scripts/names.js by build_app.py).
// Kept small on purpose. Rules are in docs/DESIGN.md, "Record names and numbers".
var CLT = window.CLT || {};
CLT.Names = (function () {
  function val(fc, f) { var a = fc.getAttribute(f); return a ? a.getValue() : null; }
  function text(fc, f) { return (val(fc, f) || "").trim(); }
  function lookupName(fc, f) { var v = val(fc, f); return v && v.length ? v[0].name || "" : ""; }
  function setName(fc, name) {
    var a = fc.getAttribute("clt_name");
    if (a && name && a.getValue() !== name) { a.setValue(name); a.setSubmitMode("always"); }
  }

  // Property: "123 Main St" or "123 Main St, Unit 4"
  function property(ctx) {
    var fc = ctx.getFormContext(), street = text(fc, "clt_street"), unit = text(fc, "clt_unit");
    if (street) setName(fc, unit ? street + ", Unit " + unit : street);
  }

  // Occupancy: "Rivera - 123 Main St" (household last name, then the property's name)
  function occupancy(ctx) {
    var fc = ctx.getFormContext();
    var last = lookupName(fc, "clt_household").split(",")[0].trim(), home = lookupName(fc, "clt_property");
    if (last && home) setName(fc, last + " - " + home);
  }

  // Household: the primary applicant's last name; "Rivera, Maria" (then "Rivera, Maria 2") if another household has it.
  function nameHousehold(id, last, first) {
    // Rivera, then Rivera, Maria, then Rivera, Maria 2 ... (no first name: Rivera 2, Rivera 3 ...)
    var names = [last];
    for (var i = 1; i < 10; i++) names.push(first ? last + ", " + first + (i > 1 ? " " + i : "") : last + " " + (i + 1));
    function next(k) {
      if (k >= names.length) return null;
      var q = "?$select=clt_householdid&$top=1&$filter=clt_name eq '" + names[k].replace(/'/g, "''") +
              "' and clt_householdid ne " + id;
      return Xrm.WebApi.retrieveMultipleRecords("clt_household", q).then(function (r) {
        return r.entities.length ? next(k + 1) : Xrm.WebApi.updateRecord("clt_household", id, { clt_name: names[k] });
      });
    }
    return next(0);
  }

  // Household member form, on save
  function member(ctx) {
    var fc = ctx.getFormContext(), role = fc.getAttribute("clt_applicantrole"), hh = val(fc, "clt_household");
    if (role && role.getText() === "Primary applicant" && hh && hh.length && text(fc, "clt_lastname")) {
      nameHousehold(hh[0].id.replace(/[{}]/g, "").toLowerCase(), text(fc, "clt_lastname"), text(fc, "clt_firstname"));
    }
  }

  // Household form, on load: name it if it has no name yet and has a primary applicant
  function household(ctx) {
    var fc = ctx.getFormContext(), id = fc.data.entity.getId().replace(/[{}]/g, "").toLowerCase();
    if (!id || text(fc, "clt_name")) return;
    Xrm.WebApi.retrieveMultipleRecords("clt_householdmember", "?$select=clt_firstname,clt_lastname,clt_applicantrole" +
      "&$filter=_clt_household_value eq " + id).then(function (r) {
      var p = r.entities.filter(function (m) {
        return m["clt_applicantrole@OData.Community.Display.V1.FormattedValue"] === "Primary applicant" && m.clt_lastname;
      })[0];
      if (p) return nameHousehold(id, p.clt_lastname.trim(), (p.clt_firstname || "").trim());
    });
  }

  return { property: property, occupancy: occupancy, member: member, household: household };
})();
