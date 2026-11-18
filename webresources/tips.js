// CLT Stewardship: helpful notes at the top of forms (deployed as clt_/scripts/tips.js by build_app.py).
// Kept small on purpose. The checks only read; they never create anything (the folder flow does that).
var CLT = window.CLT || {};
CLT.Tips = (function () {
  var ID = "clt_documents_tip";
  var NEW = {
    clt_property: "Fill in the address and save; the name and the document folder are set up for you.",
    clt_occupancy: "Pick the property and household and save; the name and the document folder are set up for you.",
    clt_household: "Save, then add the primary applicant on the Members tab; the household is named after them, " +
                   "and its document folder is set up once it has a name."
  };
  var WAIT_ID = "clt_folder_wait", WHAT = { clt_property: "property", clt_household: "household", clt_occupancy: "occupancy" };

  function folderExists(id) {
    return Xrm.WebApi.retrieveMultipleRecords("sharepointdocumentlocation",
      "?$select=sharepointdocumentlocationid&$top=1&$filter=_regardingobjectid_value eq " + id)
      .then(function (r) { return r.entities.length > 0; });
  }

  // After a new record's first save, the folder flow takes a few seconds. If the Documents tab is opened
  // before then, Dataverse makes its own "<name>_<GUID>" folder. So wait for the flow's folder, then reopen
  // the record so the form sees it. Skipped for Save & Close and Save & New, and for unnamed households.
  function waitForFolder(fc, entity, saveMode) {
    var id = fc.data.entity.getId().replace(/[{}]/g, ""), name = fc.getAttribute("clt_name");
    if (!id || saveMode === 2 || saveMode === 59 || !(name && name.getValue())) return;
    fc.ui.clearFormNotification(ID);
    fc.ui.setFormNotification("Setting up this " + WHAT[entity] + "'s document folder...", "INFO", WAIT_ID);
    var tries = 0;
    (function check() {
      folderExists(id).then(function (found) {
        if (found) return Xrm.Navigation.openForm({ entityName: entity, entityId: id });
        if (++tries < 15) return setTimeout(check, 2000);
        fc.ui.clearFormNotification(WAIT_ID);  // flow off or slow: the Documents tab still works, Dataverse's way
      }, function () { fc.ui.clearFormNotification(WAIT_ID); });
    })();
  }

  // Property, household and occupancy forms, on load: hide Related > Documents; on a new record, a hint, then wait for
  // the folder after the first save.
  function documents(ctx) {
    var fc = ctx.getFormContext(), entity = fc.data.entity.getEntityName();
    // The form's own Documents tab (with its SharePoint link) replaces Related > Documents.
    var related = fc.ui.navigation && fc.ui.navigation.items.get("navSPDocuments");
    if (related) related.setVisible(false);
    fc.ui.clearFormNotification(ID);
    if (fc.ui.getFormType() === 1) {
      if (NEW[entity]) fc.ui.setFormNotification(NEW[entity], "INFO", ID);
      var mode = 1;
      fc.data.entity.addOnSave(function (e) { mode = e.getEventArgs().getSaveMode(); });
      if (fc.data.entity.addOnPostSave) {
        var done = false;
        fc.data.entity.addOnPostSave(function (e) {
          if (done || (e.getEventArgs && !e.getEventArgs().getIsSaveSuccess())) return;
          done = true;
          waitForFolder(fc, entity, mode);
        });
      }
      return;
    }
  }

  // Occupancy form, on load and when the resale formula changes: the Appraisal share terms section only shows for an
  // appraisal based formula. Its fields keep whatever they hold; they are just out of the way.
  function resaleTerms(ctx) {
    var fc = ctx.getFormContext(), formula = fc.getAttribute("clt_resaleformula");
    var show = /apprais/i.test((formula && formula.getText && formula.getText()) || "");
    fc.ui.tabs.forEach(function (tab) {
      tab.sections.forEach(function (section) { if (section.getLabel() === "Appraisal share terms") section.setVisible(show); });
    });
  }

  return { documents: documents, resaleTerms: resaleTerms };
})();
