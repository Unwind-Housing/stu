"""
Stewardship: the annual verification intake flow (used by build_flows.py).

The forms platform posts each submitted annual verification entry here (in Cognito Forms: "Post JSON data to a
website", on Submit and on Update). Which question feeds which field comes from the organization's mapping file
(form_mapping.py, type "annual-verification"), so nothing about a form's wording is in this code. The form needs
one hidden question that the link from the Occupancy verification page fills in: the occupancy's record number
(O-00012). That is what the entry is matched on.

What the flow does with one entry:
  1. Keeps a copy as a Form submission (form type Annual verification), status Received.
  2. Finds the occupancy by its record number. No match: the submission is marked Needs attention and nothing
     else changes.
  3. Finds the verification the entry answers, in this order:
       a. one already linked to this entry (the household or staff saved the entry again),
       b. the occupancy's open request (Due, Sent, Received or Issue found), newest first,
       c. none: a new verification is added for the year the entry was submitted, so an answer is never lost.
  4. Saves the answers on the verification with the date it came back, and marks it Received for staff to
     review and close. A verification staff have already closed keeps its status.
  5. Insurance: starts an Insurance verification for the occupancy (or brings its open one up to date):
     To review when proof was attached and no help was asked for, Needs contact otherwise, with a link to
     where the forms platform saved the uploads (when the organization's mapping names that folder). One staff
     have already closed is left alone.
  6. A household that asked for contact about its mortgage gets a Homeowner request ("Mortgage help requested",
     type Other), unless one is already open for the occupancy.
  7. The first file the household attached as proof of insurance is copied onto the Insurance verification
     (its Insurance document), so staff can view it in Stu. Staff are never sent to the forms platform (not
     everyone has an account there): when there are more files, or the copy fails, a note on the Insurance
     verification points to the uploaded documents, and everything else still stands.
  8. The Form submission is marked Processed, or Needs attention with the error.

Nothing here sets the occupancy's Last occupancy verification or Last insurance verification dates: those move
when staff close the request and approve the insurance.
"""
import uuid

import flows_intake as fi
from flows_intake import PREFIX, choice_value, dv, chain, odata, setvar, es, first_id, lit, source_form_actions, m

MORTGAGE_REQUEST = "Mortgage help requested"
OCC = "variables('OccupancyId')"
VER = "variables('VerificationId')"


def yes(key):
    """Expression: true when the answer is Yes (a choice) or true (a tick box)."""
    return f"contains(createArray('yes', 'true'), toLower(string(coalesce({m(key)}, ''))))"


def text_of(key):
    return f"string(coalesce({m(key)}, ''))"


def uploads_link(mapping):
    """Expression: where the forms platform saved this entry's uploads ('' when the organization hasn't said)."""
    if not mapping.uploads_folder:
        return "''"
    parts = [lit(mapping.uploads_folder.rstrip("/").replace(" ", "%20") + "/")]
    values = {"formName": m("entry.formName"), "number": m("entry.number")}
    rest = mapping.uploads_path
    while rest:
        i = rest.find("{")
        j = rest.find("}", i)
        if i < 0 or j < 0:
            parts.append(lit(rest.replace(" ", "%20")))
            break
        if i:
            parts.append(lit(rest[:i].replace(" ", "%20")))
        parts.append(f"encodeUriComponent(string(coalesce({values[rest[i + 1:j]]}, '')))")
        rest = rest[j + 1:]
    return "concat(" + ", ".join(parts) + ")"


def verification_flow(mapping):
    fi.use_form(mapping)
    ENTRY_ID, SUBMITTED, FIRST, LAST, PROVIDER = fi.ENTRY_ID, fi.SUBMITTED, fi.FIRST, fi.LAST, fi.PROVIDER
    number = f"toUpper(trim(coalesce({m('match.occupancyId')}, '')))"
    # the date on the form (the household's own date), else when the entry was submitted; a blank date counts as none
    received_on = f"formatDateTime(if(equals(string(coalesce({m('answers.signedDate')}, '')), ''), {SUBMITTED}, {m('answers.signedDate')}), 'yyyy-MM-dd')"
    year = f"int(formatDateTime({SUBMITTED}, 'yyyy'))"
    files = f"greater(length(coalesce({m('answers.insuranceFiles')}, json('[]'))), 0)"
    link = uploads_link(mapping)
    # the first attached file: where to fetch it (the forms platform puts a link on each file it posts) and its name
    first_file = f"first(coalesce({m('answers.insuranceFiles')}, json('[]')))"
    file_link = f"string(coalesce({first_file}?['{mapping.paths.get('entry.fileLink', ('File',))[0]}'], ''))"
    file_name = f"string(coalesce({first_file}?['{mapping.paths.get('entry.fileName', ('Name',))[0]}'], 'Proof of insurance'))"
    vstatus = {s: choice_value("verificationstatus", s) for s in ("Due", "Sent", "Received", "Issue found")}   # still open
    review, contact = choice_value("insurancereviewstatus", "To review"), choice_value("insurancereviewstatus", "Needs contact")
    requested = choice_value("insurancereviewstatus", "Requested")   # staff asked for proof and are waiting
    issue = choice_value("insurancereviewstatus", "Issue found")     # staff found a problem and are waiting for it to be put right
    received, processed, attention = (choice_value("submissionstatus", s) for s in ("Received", "Processed", "Needs attention"))

    # ---- 1. keep a copy
    sub_find = "Find_submission"
    log = chain({
        sub_find: dv("ListRecords", {
            "entityName": es("formsubmission"), "$select": f"{PREFIX}_formsubmissionid",
            "$filter": f"{PREFIX}_provider eq '{PROVIDER}' and {PREFIX}_externalentryid eq '@{{{odata(ENTRY_ID)}}}'", "$top": 1}),
        "If_submission_exists": {
            "type": "If",
            "expression": {"greater": [f"@length(outputs('{sub_find}')?['body/value'])", 0]},
            "actions": chain({
                "Update_submission": dv("UpdateRecord", {
                    "entityName": es("formsubmission"), "recordId": f"@{{{first_id(sub_find, 'formsubmission')}}}",
                    f"item/{PREFIX}_payload": "@{string(triggerBody())}", f"item/{PREFIX}_receivedon": "@{utcNow('yyyy-MM-dd')}",
                    f"item/{PREFIX}_status": received, f"item/{PREFIX}_errordetail": ""}),
                "Remember_submission": setvar("SubmissionId", f"@{{{first_id(sub_find, 'formsubmission')}}}"),
            }),
            "else": {"actions": chain({
                "Create_submission": dv("CreateRecord", {
                    "entityName": es("formsubmission"),
                    f"item/{PREFIX}_name": f"@{{take(concat('Annual verification ', {ENTRY_ID}, ', ', {FIRST}, ' ', {LAST}), 100)}}",
                    f"item/{PREFIX}_provider": PROVIDER,
                    f"item/{PREFIX}_formtype": choice_value("formtype", "Annual verification"),
                    f"item/{PREFIX}_externalentryid": f"@{{{ENTRY_ID}}}",
                    f"item/{PREFIX}_receivedon": "@{utcNow('yyyy-MM-dd')}",
                    f"item/{PREFIX}_entrylink": f"@{m('entry.adminLink')}",
                    f"item/{PREFIX}_payload": "@{string(triggerBody())}",
                    f"item/{PREFIX}_status": received}),
                "Remember_new_submission": setvar("SubmissionId", f"@outputs('Create_submission')?['body/{PREFIX}_formsubmissionid']"),
            })}},
    })

    # ---- the answers
    renting = yes("answers.renting")
    blank = lambda key: f"equals({text_of(key)}, '')"   # noqa: E731
    tenant = ("if(" + renting + ", concat('Renting: ', " + text_of("answers.rentingWhat")
              + f", if({blank('answers.rentingDescription')}, '', concat(' (', {text_of('answers.rentingDescription')}, ')'))"
              + f", if({blank('answers.roomsRented')}, '', concat(', rooms: ', {text_of('answers.roomsRented')}))"
              + f", if({blank('answers.monthlyRent')}, '', concat(', rent per month: ', {text_of('answers.monthlyRent')}))), '')")
    rent_default = choice_value("rentalstatus", "Renting rooms")
    rental = (f"if({renting}, coalesce(outputs('Rental_answers')?[if({blank('answers.rentingWhat')}, '-', {text_of('answers.rentingWhat')})], {rent_default}), "
              f"{choice_value('rentalstatus', 'Not renting')})")
    # Power Automate works out both sides of an if(), so neither side may fail on a blank answer.
    people = (f"if({blank('answers.peopleInHome')}, null, int(first(split(string(coalesce({m('answers.peopleInHome')}, 0)), '.'))))")
    asked = {  # column -> expression, only for the questions this form asks
        "peopleinhome": ("answers.peopleInHome", people),
        "primaryresidence": ("answers.primaryResidence", yes("answers.primaryResidence")),
        "noshorttermrental": ("answers.noShortTermRental", yes("answers.noShortTermRental")),
        "rentalstatus": ("answers.renting", rental),
        "tenantdetails": ("answers.renting", tenant),
        "insurancecurrent": ("answers.insuranceCurrent", yes("answers.insuranceCurrent")),
        "insurancereceived": ("answers.insuranceFiles", files),
        "insurancecontact": ("answers.insuranceContact", yes("answers.insuranceContact")),
        "mortgagecontact": ("answers.mortgageContact", yes("answers.mortgageContact")),
        "signeddate": ("answers.signedDate", received_on),
        "phone": ("answers.phone", text_of("answers.phone")),
    }
    answers = {f"item/{PREFIX}_{col}": "@" + expr if col not in ("tenantdetails", "phone") else "@{" + expr + "}"
               for col, (key, expr) in asked.items() if mapping.has(key)}
    rental_map = {a: choice_value("rentalstatus", label) for a, label in (mapping.choices("rentalstatus") or {}).items()}

    by_entry, find_open, find_ins = "Find_request_for_this_entry", "Find_open_request", "Find_insurance_verification"
    open_filter = " or ".join(f"{PREFIX}_status eq {v}" for v in vstatus.values())
    current = (f"coalesce(first(outputs('{by_entry}')?['body/value'])?['{PREFIX}_status'], "
               f"first(outputs('{find_open}')?['body/value'])?['{PREFIX}_status'], {vstatus['Received']})")
    ins_status = f"if(and({files}, not({yes('answers.insuranceContact')})), {review}, {contact})"
    ins_fields = {
        f"item/{PREFIX}_status": "@" + ins_status,
        f"item/{PREFIX}_contactrequested": "@" + yes("answers.insuranceContact"),
        f"item/{PREFIX}_documentslink": f"@{{if({files}, {link}, '')}}",
        f"item/{PREFIX}_annualverification@odata.bind": f"/{es('annualverification')}(@{{{VER}}})",
    }
    ins_found = f"first(outputs('{find_ins}')?['body/value'])"
    # a household that asked for contact about its mortgage: one Homeowner request, not one per saved entry
    rstatus = [choice_value("requeststatus", s) for s in ("Submitted", "Under review")]
    mortgage = {} if not mapping.has("answers.mortgageContact") else {"If_asked_for_mortgage_help": {
        "type": "If",
        "expression": {"equals": ["@" + yes("answers.mortgageContact"), True]},
        "actions": chain({
            "Find_mortgage_request": dv("ListRecords", {
                "entityName": es("homeownerrequest"), "$select": f"{PREFIX}_homeownerrequestid",
                "$filter": f"_{PREFIX}_occupancy_value eq @{{{OCC}}} and statecode eq 0 and {PREFIX}_name eq '{MORTGAGE_REQUEST}' and "
                           f"({PREFIX}_status eq {rstatus[0]} or {PREFIX}_status eq {rstatus[1]})", "$top": 1}),
            "If_no_mortgage_request_is_open": {
                "type": "If",
                "expression": {"equals": ["@length(outputs('Find_mortgage_request')?['body/value'])", 0]},
                "actions": {"Create_mortgage_request": dv("CreateRecord", {
                    "entityName": es("homeownerrequest"),
                    f"item/{PREFIX}_name": MORTGAGE_REQUEST,
                    f"item/{PREFIX}_requesttype": choice_value("requesttype", "Other"),
                    f"item/{PREFIX}_requestdate": "@" + received_on,
                    f"item/{PREFIX}_status": rstatus[0],
                    f"item/{PREFIX}_details": f"@{{concat('On the annual verification form, the household asked staff to get in touch about difficulty "
                                              f"with its mortgage.', if(equals({text_of('answers.phone')}, ''), '', concat(' Phone on the form: ', {text_of('answers.phone')})))}}",
                    f"item/{PREFIX}_occupancy@odata.bind": f"/{es('occupancy')}(@{{{OCC}}})",
                    f"item/{PREFIX}_property@odata.bind": "/clt_properties(@{variables('PropertyId')})"})},
                "else": {"actions": {}}}}),
        "else": {"actions": {}}}}
    matched = chain({
        "Remember_occupancy": setvar("OccupancyId", f"@{{{first_id('Find_occupancy', 'occupancy')}}}"),
        "Remember_property": setvar("PropertyId", f"@{{coalesce(first(outputs('Find_occupancy')?['body/value'])?['_{PREFIX}_property_value'], '')}}"),
        "Remember_occupancy_name": setvar("OccupancyName", f"@{{coalesce(first(outputs('Find_occupancy')?['body/value'])?['{PREFIX}_name'], '')}}"),
        by_entry: dv("ListRecords", {
            "entityName": es("annualverification"), "$select": f"{PREFIX}_annualverificationid,{PREFIX}_status",
            "$filter": f"_{PREFIX}_occupancy_value eq @{{{OCC}}} and {PREFIX}_formentryid eq '@{{{odata(ENTRY_ID)}}}'", "$top": 1}),
        find_open: dv("ListRecords", {
            "entityName": es("annualverification"), "$select": f"{PREFIX}_annualverificationid,{PREFIX}_status",
            "$filter": f"_{PREFIX}_occupancy_value eq @{{{OCC}}} and statecode eq 0 and ({open_filter})",
            "$orderby": "createdon desc", "$top": 1}),
        "If_request_found": {
            "type": "If",
            "expression": {"or": [{"greater": [f"@length(outputs('{by_entry}')?['body/value'])", 0]},
                                  {"greater": [f"@length(outputs('{find_open}')?['body/value'])", 0]}]},
            "actions": {"Remember_request": setvar(
                "VerificationId", f"@{{coalesce({first_id(by_entry, 'annualverification')}, {first_id(find_open, 'annualverification')})}}")},
            "else": {"actions": chain({
                "Create_request": dv("CreateRecord", {
                    "entityName": es("annualverification"),
                    f"item/{PREFIX}_name": f"@{{take(concat(string({year}), ', ', variables('OccupancyName')), 100)}}",
                    f"item/{PREFIX}_year": "@" + year,
                    f"item/{PREFIX}_method": choice_value("verificationmethod", "Online form"),
                    f"item/{PREFIX}_status": vstatus["Received"],
                    f"item/{PREFIX}_occupancy@odata.bind": f"/{es('occupancy')}(@{{{OCC}}})"}),
                "Remember_new_request": setvar("VerificationId", f"@outputs('Create_request')?['body/{PREFIX}_annualverificationid']"),
            })}},
        "Rental_answers": {"type": "Compose", "inputs": rental_map},
        "Save_answers": dv("UpdateRecord", {
            "entityName": es("annualverification"), "recordId": f"@{VER}",
            # an open request becomes Received; one staff have already closed keeps its status
            f"item/{PREFIX}_status": f"@if(contains(createArray({', '.join(str(v) for v in vstatus.values())}), {current}), {vstatus['Received']}, {current})",
            f"item/{PREFIX}_receiveddate": "@" + received_on,
            f"item/{PREFIX}_formentryid": f"@{{{ENTRY_ID}}}",
            f"item/{PREFIX}_formlink": f"@{m('entry.adminLink')}",
            f"item/{PREFIX}_uploadslink": f"@{{if({files}, {link}, '')}}",
            **answers}),
        find_ins: dv("ListRecords", {
            "entityName": es("insuranceverification"), "$select": f"{PREFIX}_insuranceverificationid,{PREFIX}_status",
            "$filter": f"_{PREFIX}_occupancy_value eq @{{{OCC}}} and statecode eq 0 and (_{PREFIX}_annualverification_value eq @{{{VER}}} "
                       f"or {PREFIX}_status eq {requested} or {PREFIX}_status eq {review} or {PREFIX}_status eq {contact} or {PREFIX}_status eq {issue})",
            "$top": 1}),
        "If_insurance_verification_exists": {
            "type": "If",
            "expression": {"greater": [f"@length(outputs('{find_ins}')?['body/value'])", 0]},
            "actions": {"If_it_is_still_open": {
                "type": "If",
                "expression": {"or": [{"equals": [f"@{ins_found}?['{PREFIX}_status']", s]} for s in (requested, review, contact, issue)]},
                "actions": chain({
                    "Update_insurance_verification": dv("UpdateRecord", {
                        "entityName": es("insuranceverification"), "recordId": f"@{{{first_id(find_ins, 'insuranceverification')}}}", **ins_fields}),
                    "Remember_insurance_verification": setvar("InsuranceId", f"@{{{first_id(find_ins, 'insuranceverification')}}}")}),
                "else": {"actions": {}}}},
            "else": {"actions": chain({
                "Create_insurance_verification": dv("CreateRecord", {
                    "entityName": es("insuranceverification"),
                    f"item/{PREFIX}_name": f"@{{take(concat({received_on}, ', ', variables('OccupancyName')), 100)}}",
                    f"item/{PREFIX}_date": "@" + received_on,
                    f"item/{PREFIX}_occupancy@odata.bind": f"/{es('occupancy')}(@{{{OCC}}})",
                    **ins_fields}),
                "Remember_new_insurance_verification": setvar(
                    "InsuranceId", f"@outputs('Create_insurance_verification')?['body/{PREFIX}_insuranceverificationid']")})}},
        **mortgage,
    })
    process = chain({
        **source_form_actions("Annual verification"),
        "Find_occupancy": dv("ListRecords", {
            "entityName": es("occupancy"), "$select": f"{PREFIX}_occupancyid,{PREFIX}_name,_{PREFIX}_property_value",
            "$filter": f"{PREFIX}_recordnumber eq '@{{{odata(number)}}}'", "$top": 1}),
        "If_occupancy_found": {
            "type": "If",
            "expression": {"greater": ["@length(outputs('Find_occupancy')?['body/value'])", 0]},
            "actions": matched,
            "else": {"actions": {"No_occupancy": setvar(
                "Problem", f"@{{concat('No occupancy has the ID \"', {number}, '\". Check the occupancy ID on the entry, then save the entry "
                           "again, or record this verification by hand on the Occupancy verification page.')}")}}},
    })

    def init(name):
        return {"type": "InitializeVariable", "inputs": {"variables": [{"name": name, "type": "string", "value": ""}]}}
    actions = chain({
        "Init_submission": init("SubmissionId"), "Init_source_form": init("SourceFormId"), "Init_form_project": init("FormProjectId"),
        "Init_occupancy": init("OccupancyId"), "Init_occupancy_name": init("OccupancyName"), "Init_verification": init("VerificationId"),
        "Init_property": init("PropertyId"), "Init_insurance": init("InsuranceId"),
        "Init_problem": init("Problem"),
        "Keep_a_copy": {"type": "Scope", "actions": log},
        "Process_verification": {"type": "Scope", "actions": process},
    })
    # The proof of insurance, copied onto the Insurance verification. On its own, after everything else is saved, so a
    # file that can't be fetched costs nothing but the copy.
    actions["Copy_insurance_document"] = {
        "type": "Scope", "runAfter": {"Process_verification": ["Succeeded"]},
        "actions": {"If_there_is_a_file_to_copy": {
            "type": "If",
            "expression": {"and": [{"not": {"equals": ["@variables('InsuranceId')", ""]}}, {"not": {"equals": ["@" + file_link, ""]}}]},
            "actions": chain({
                "Get_the_file": {"type": "Http", "inputs": {"method": "GET", "uri": "@{" + file_link + "}"}},
                "Save_the_file": dv("UpdateEntityFileImageFieldContent", {
                    "entityName": es("insuranceverification"), "recordId": "@variables('InsuranceId')",
                    "fileImageFieldName": f"{PREFIX}_document", "item": "@body('Get_the_file')", "x-ms-file-name": "@{" + file_name + "}"}),
                # only the first file fits on the record: say so when there are more, and where they all are
                "If_more_than_one_file": {
                    "type": "If",
                    "expression": {"greater": [f"@length(coalesce({m('answers.insuranceFiles')}, json('[]')))", 1]},
                    "actions": {"Note_the_other_files": dv("UpdateRecord", {
                        "entityName": es("insuranceverification"), "recordId": "@variables('InsuranceId')",
                        f"item/{PREFIX}_notes": f"@{{concat('The household attached ', string(length(coalesce({m('answers.insuranceFiles')}, json('[]')))), "
                                                "' files. The first is copied here; all of them are in the uploaded documents.')}"})},
                    "else": {"actions": {}}}}),
            "else": {"actions": {}}}}}
    actions["Note_the_copy_failed"] = dv("UpdateRecord", {
        "entityName": es("insuranceverification"), "recordId": "@variables('InsuranceId')",
        f"item/{PREFIX}_notes": "The document attached to the form couldn't be copied here. Open the uploaded documents to see it."})
    actions["Note_the_copy_failed"]["runAfter"] = {"Copy_insurance_document": ["Failed", "TimedOut"]}
    actions["If_matched"] = {
        "type": "If", "runAfter": {"Process_verification": ["Succeeded"], "Copy_insurance_document": ["Succeeded", "Failed", "TimedOut"]},
        "expression": {"equals": ["@variables('Problem')", ""]},
        "actions": {"Mark_processed": dv("UpdateRecord", {
            "entityName": es("formsubmission"), "recordId": "@variables('SubmissionId')",
            f"item/{PREFIX}_status": processed, f"item/{PREFIX}_errordetail": "",
            f"item/{PREFIX}_annualverification@odata.bind": f"/{es('annualverification')}(@{{{VER}}})",
            f"item/{PREFIX}_sourceform@odata.bind": f"/{es('sourceform')}(@{{variables('SourceFormId')}})"})},
        "else": {"actions": {"Mark_not_matched": dv("UpdateRecord", {
            "entityName": es("formsubmission"), "recordId": "@variables('SubmissionId')",
            f"item/{PREFIX}_status": attention, f"item/{PREFIX}_errordetail": "@variables('Problem')",
            f"item/{PREFIX}_sourceform@odata.bind": f"/{es('sourceform')}(@{{variables('SourceFormId')}})"})}}}
    actions["Failed_steps"] = {"type": "Query", "runAfter": {"Process_verification": ["Failed", "TimedOut"]},
                               "inputs": {"from": "@result('Process_verification')",
                                          "where": "@not(contains(createArray('Succeeded', 'Skipped'), item()?['status']))"}}
    actions["Mark_needs_attention"] = dv("UpdateRecord", {
        "entityName": es("formsubmission"), "recordId": "@variables('SubmissionId')",
        f"item/{PREFIX}_status": attention, f"item/{PREFIX}_errordetail": "@{take(string(body('Failed_steps')), 3900)}"})
    actions["Mark_needs_attention"]["runAfter"] = {"Failed_steps": ["Succeeded"]}
    definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                       "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
        # Named "manual" with triggerAuthenticationType All, for the reasons given in flows_full_app.py: a designer
        # Save then changes neither the web address nor who may post to it.
        "triggers": {"manual": {
            "type": "Request", "kind": "Http",
            "inputs": {"triggerAuthenticationType": "All", "schema": {"type": "object"}},
            "runtimeConfiguration": {"concurrency": {"runs": 1}}}},
        "actions": actions,
    }
    return {
        "name": "CLT: Annual verification intake" + (f" ({mapping.label or mapping.slug})" if mapping.slug else ""),
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "clt-stewardship/flows/annual-verification-intake"
                             + (f"/{mapping.slug}" if mapping.slug else ""))),
        "description": "Receives annual verification entries posted by the forms platform, finds the occupancy's request, saves "
                       "the answers as Received for staff to review, and starts the insurance verification.",
        "definition": definition,
    }
