"""
Applications and Sales: the screener intake flow (used by build_flows.py).

The forms platform posts each screener entry here (in Cognito Forms: "Post JSON data to a website", on Submit
and on Update). Which question feeds which field comes from the organization's mapping file (form_mapping.py),
so nothing about a form's wording is in this code.
The screener is generic: it isn't tied to a project. Staff add applications to a project later.

What the flow does with one entry:
  1. Keeps a copy as a Form submission (provider, entry ID, the raw JSON), status Received.
  2. Household: matched by primary email (a returning applicant keeps their household).
     New households are named after the primary applicant: "Rivera", or "Rivera, Maria" if
     "Rivera" is taken, or "Rivera, Maria (6-12)" if that is taken too.
  3. Members: the primary applicant (if the household has none yet) and the co-applicant
     (if there is one and nobody in the household has that name yet).
  4. Application: matched by screener entry ID. New: created with stage "Screener submitted" and
     first submitted on. Existing: answers refreshed, unless the answers are frozen (Unique IDs
     assigned), in which case the change is kept as a note on the application instead.
  5. County, housing status and mailing state are matched to the List values (name or form answers).
  6. The Form submission is marked Processed, or Needs attention with the error.

Every field the flow writes is listed in SCREENER_COLUMNS and checked against schema.py by the tests.
"""
import json
import uuid

from schema import CHOICES

PREFIX = "clt"
DATAVERSE = "shared_commondataserviceforapps"
CHOICE_BASE = 768270000  # value of a choice's first label; the rest follow in schema.py order


def choice_value(choice, label):
    labels = CHOICES[choice][1]
    return CHOICE_BASE + labels.index(label)


def _api(connector):
    return f"/providers/Microsoft.PowerApps/apis/{connector}"


def dv(operation, parameters, after=None):
    a = {"type": "OpenApiConnection",
         "inputs": {"host": {"connectionName": DATAVERSE, "operationId": operation, "apiId": _api(DATAVERSE)},
                    "parameters": parameters, "authentication": "@parameters('$authentication')"}}
    if after:
        a["runAfter"] = {after: ["Succeeded"]}
    return a


def chain(actions):
    """Make each action run after the one before it (dict order)."""
    prev = None
    for name, a in actions.items():
        if prev and "runAfter" not in a:
            a["runAfter"] = {prev: ["Succeeded"]}
        prev = name
    return actions


def q(*path):
    """Expression for a field of the posted entry."""
    return "triggerBody()" + "".join(f"?['{p}']" for p in path)


def lit(s):
    """A string literal inside an expression."""
    return "'" + s.replace("'", "''") + "'"


def odata(expr):
    """Expression: a value made safe to put inside '...' in an OData filter."""
    return f"replace(coalesce({expr}, ''), '''', '''''')"


def setvar(name, value, after=None):
    a = {"type": "SetVariable", "inputs": {"name": name, "value": value}}
    if after:
        a["runAfter"] = {after: ["Succeeded"]}
    return a


def es(table):
    return {"household": "clt_households", "householdmember": "clt_householdmembers",
            "application": "clt_applications", "formsubmission": "clt_formsubmissions",
            "listitem": "clt_listitems", "sourceform": "clt_sourceforms", "project": "clt_projects",
            "incomelimitset": "clt_incomelimitsets", "eligibility": "clt_eligibilities",
            "incomesource": "clt_incomesources", "debt": "clt_debts", "asset": "clt_assets",
            "occupancy": "clt_occupancies", "annualverification": "clt_annualverifications",
            "insuranceverification": "clt_insuranceverifications", "homeownerrequest": "clt_homeownerrequests"}[table]


# ---------------------------------------------------------------------------
# Stu's screener fields and their kinds. Which question on a form feeds each one comes from the organization's
# mapping file (form_mapping.py): "answers" maps the columns below, "applicant" the name, contact and address
# questions, "entry" what the forms platform adds (entry ID, dates, links).
# (column, kind). kinds: text, yesno, money, int, choice:<name>, multi:<name>
SCREENER_COLUMNS = [
    ("localtie", "yesno"),
    ("firsttimebuyer", "yesno"),
    ("fthbexceptions", "multi:fthbexception"),
    ("ownsproperty", "yesno"),
    ("adults", "int"),
    ("children", "int"),
    ("homesizes", "multi:homesize"),
    ("statedannualincome", "money"),
    ("incomepastyear", "yesno"),
    ("age62", "yesno"),
    ("statednonretirementassets", "money"),
    ("statedretirementassets", "money"),
    ("has1000forclosing", "yesno"),
    ("statedmonthlydebt", "money"),
    ("creditrange", "choice:creditrange"),
    ("bankruptcy3yrs", "yesno"),
    ("primaryresidence", "yesno"),
    ("hbeducation", "choice:hbeducation"),
    ("preapproval", "choice:preapproval"),
    ("accommodation", "text"),
    ("applicantquestions", "text"),
]

# Set by use_form() from the mapping of the form a flow is being built for.
MAP = None
PROVIDER = "Cognito Forms"
SCREENER_FIELDS = []   # (column, kind, path) for the columns this form asks
SCREENER_LISTS = []    # lookups to List values: (table, column, list name, path)
ENTRY_ID = SUBMITTED = FIRST = LAST = EMAIL = LAST_FIRST = CO_FIRST = CO_LAST = FORM_ID = None


def m(key):
    """Expression for the answer a mapping key points at (blank when the form doesn't ask it)."""
    return q(*MAP.path(key))


def use_form(mapping):
    """Point this module at one form's mapping. Every flow builder calls it first."""
    global MAP, PROVIDER, SCREENER_FIELDS, SCREENER_LISTS
    global ENTRY_ID, SUBMITTED, FIRST, LAST, EMAIL, LAST_FIRST, CO_FIRST, CO_LAST, FORM_ID
    MAP = mapping
    PROVIDER = mapping.provider
    ENTRY_ID = m("entry.id")                                   # "6-12"
    FORM_ID = f"string({m('entry.formId')})"                   # "6"
    SUBMITTED = f"coalesce({m('entry.submitted')}, utcNow())"
    FIRST = f"trim(coalesce({m('applicant.firstName')}, ''))"
    LAST = f"trim(coalesce({m('applicant.lastName')}, ''))"
    EMAIL = f"toLower(trim(coalesce({m('applicant.email')}, '')))"
    LAST_FIRST = f"concat({LAST}, ', ', {FIRST})"
    CO_FIRST = f"trim(coalesce({m('applicant.coFirstName')}, ''))"
    CO_LAST = f"trim(coalesce({m('applicant.coLastName')}, ''))"
    if mapping.type == "screener":
        SCREENER_FIELDS = [(col, kind, mapping.path(f"answers.{col}")) for col, kind in SCREENER_COLUMNS
                           if mapping.has(f"answers.{col}")]
        SCREENER_LISTS = ([("application", "housingstatus", "Housing status", mapping.path("applicant.housingStatus"))]
                          if mapping.has("applicant.housingStatus") else [])


def choice_maps():
    """Form answer -> Dataverse value, per choice used above (for the Choice_maps action)."""
    maps = {}
    for col, kind, path in SCREENER_FIELDS:
        if ":" not in kind:
            continue
        name = kind.split(":")[1]
        custom = MAP.choices(name)   # the form words its answers differently from Stu's labels
        if custom:
            maps[name] = {k: choice_value(name, v) for k, v in custom.items()}
        else:
            maps[name] = {label: choice_value(name, label) for label in CHOICES[name][1]}
    return maps


def field_value(col, kind, path):
    v = q(*path)
    if kind == "text":
        return f"@{v}"
    if kind == "money":
        return f"@{v}"
    if kind == "yesno":
        return f"@if(empty({v}), null, equals({v}, 'Yes'))"
    if kind == "int":
        return f"@if(empty({v}), null, int({v}))"
    if kind.startswith("choice:"):
        return f"@if(empty({v}), null, outputs('Choice_maps')?['{kind[7:]}']?[{v}])"
    if kind.startswith("multi:"):
        return f"@if(empty(body('{_multi_name(col)}_values')), null, join(body('{_multi_name(col)}_values'), ','))"
    raise ValueError(kind)


def _multi_name(col):
    return f"Pick_{col}"


def multi_actions():
    """Select + Query per multi-select question: answers -> list of Dataverse values."""
    out = {}
    for col, kind, path in SCREENER_FIELDS:
        if not kind.startswith("multi:"):
            continue
        name = kind[6:]
        key = "substring(item(), 0, 1)" if MAP.first_letter(name) else "item()"
        out[_multi_name(col)] = {"type": "Select", "inputs": {
            "from": f"@coalesce({q(*path)}, json('[]'))",
            "select": f"@string(outputs('Choice_maps')?['{name}']?[{key}])"}}
        out[f"{_multi_name(col)}_values"] = {"type": "Query", "inputs": {
            "from": f"@body('{_multi_name(col)}')", "where": "@not(empty(item()))"}}
    return out


# ---------------------------------------------------------------------------

def first_id(action, table):
    return f"first(outputs('{action}')?['body/value'])?['{PREFIX}_{table}id']"


def list_value(list_name):
    return choice_value("listname", list_name)


def match_list_value(name, list_name, answer, extra_filter=""):
    """ListRecords that finds the List value whose name or form answers match the answer.
    A blank answer is swapped for a value that matches nothing (startswith '' would match everything)."""
    a = odata(f"if(empty({answer}), '-none-', {answer})")
    flt = (f"{PREFIX}_list eq {list_value(list_name)} and statecode eq 0 and "
           f"({PREFIX}_name eq '@{{{a}}}' or {PREFIX}_formanswers eq '@{{{a}}}' or "
           f"startswith({PREFIX}_formanswers, '@{{{a}}}'))" + extra_filter)
    return {name: dv("ListRecords", {"entityName": es("listitem"), "$select": f"{PREFIX}_listitemid",
                                     "$filter": flt, "$top": 1})}


def set_lookup_if_found(name, find, table, record_var, column, after=None):
    """If the find returned a row, point the record's lookup at it."""
    return {name: {"type": "If", "runAfter": {after or find: ["Succeeded"]},
                   "expression": {"greater": [f"@length(outputs('{find}')?['body/value'])", 0]},
                   "actions": {f"{name}_now": dv("UpdateRecord", {
                       "entityName": es(table), "recordId": f"@variables('{record_var}')",
                       f"item/{PREFIX}_{column}@odata.bind": f"/{es('listitem')}(@{{{first_id(find, 'listitem')}}})"})},
                   "else": {"actions": {}}}}


def source_form_actions(formtype="Screener"):
    """Find the Source form row for the form this entry came from (provider + form ID), or add it."""
    find = "Find_source_form"
    return chain({
        find: dv("ListRecords", {
            "entityName": es("sourceform"), "$select": f"{PREFIX}_sourceformid,_{PREFIX}_project_value",
            "$filter": f"{PREFIX}_provider eq '{PROVIDER}' and {PREFIX}_externalformid eq '@{{{odata(FORM_ID)}}}'",
            "$top": 1}),
        "If_source_form_exists": {
            "type": "If",
            "expression": {"greater": [f"@length(outputs('{find}')?['body/value'])", 0]},
            "actions": chain({
                "Remember_source_form": setvar("SourceFormId", f"@{{{first_id(find, 'sourceform')}}}"),
                # a form made for one project: its new applications go straight into that project
                "Remember_form_project": setvar(
                    "FormProjectId",
                    f"@{{coalesce(first(outputs('{find}')?['body/value'])?['_{PREFIX}_project_value'], '')}}"),
            }),
            "else": {"actions": chain({
                "Create_source_form": dv("CreateRecord", {
                    "entityName": es("sourceform"),
                    f"item/{PREFIX}_name": f"@{{coalesce({m('entry.formName')}, concat('{PROVIDER.split()[0]} form ', {FORM_ID}))}}",
                    f"item/{PREFIX}_provider": PROVIDER,
                    f"item/{PREFIX}_externalformid": f"@{{{FORM_ID}}}",
                    f"item/{PREFIX}_formtype": choice_value("formtype", formtype)}),
                "Remember_new_source_form": setvar("SourceFormId",
                                                   f"@outputs('Create_source_form')?['body/{PREFIX}_sourceformid']"),
            })}},
    })


def household_actions():
    taken = "body('Taken_names')"
    name = (f"if(not(contains({taken}, {LAST})), {LAST}, "
            f"if(not(contains({taken}, {LAST_FIRST})), {LAST_FIRST}, "
            f"concat({LAST}, ', ', {FIRST}, ' (', {ENTRY_ID}, ')')))")
    new_household = chain({
        "Find_names_in_use": dv("ListRecords", {
            "entityName": es("household"), "$select": f"{PREFIX}_name",
            "$filter": f"{PREFIX}_name eq '@{{{odata(LAST)}}}' or "
                       f"{PREFIX}_name eq '@{{{odata(LAST_FIRST)}}}'"}),
        "Taken_names": {"type": "Select", "inputs": {
            "from": "@outputs('Find_names_in_use')?['body/value']", "select": f"@item()?['{PREFIX}_name']"}},
        "Create_household": dv("CreateRecord", {
            "entityName": es("household"),
            f"item/{PREFIX}_name": f"@{{{name}}}",
            f"item/{PREFIX}_primaryemail": f"@{{{EMAIL}}}",
            f"item/{PREFIX}_phone": f"@{m('applicant.phone')}",
            f"item/{PREFIX}_mailingstreet": f"@{m('applicant.street')}",
            f"item/{PREFIX}_mailingcity": f"@{m('applicant.city')}",
            f"item/{PREFIX}_mailingzip": f"@{m('applicant.zip')}"}),
        "Remember_new_household": setvar("HouseholdId", f"@outputs('Create_household')?['body/{PREFIX}_householdid']"),
        **set_lookup_if_found("Set_mailing_state", "Find_state", "household", "HouseholdId", "mailingstate",
                              after="Remember_new_household"),
    })
    return chain({
        "Find_household": dv("ListRecords", {
            "entityName": es("household"), "$select": f"{PREFIX}_householdid",
            # no email: match nothing, so a new household is made
            "$filter": f"@{{if(empty({EMAIL}), '{PREFIX}_householdid eq null', "
                       f"concat('{PREFIX}_primaryemail eq ''', {odata(EMAIL)}, ''''))}}",
            "$top": 1}),
        "If_household_exists": {
            "type": "If",
            "expression": {"greater": ["@length(outputs('Find_household')?['body/value'])", 0]},
            "actions": {"Remember_household": setvar("HouseholdId", f"@{{{first_id('Find_household', 'household')}}}")},
            "else": {"actions": new_household}},
    })


def member_actions():
    role = lambda r: choice_value("applicantrole", r)
    hh = "variables('HouseholdId')"
    co_name = f"concat({CO_FIRST}, ' ', {CO_LAST})"
    return chain({
        "Find_primary_applicant": dv("ListRecords", {
            "entityName": es("householdmember"), "$select": f"{PREFIX}_householdmemberid",
            "$filter": f"_{PREFIX}_household_value eq @{{{hh}}} and {PREFIX}_applicantrole eq {role('Primary applicant')}",
            "$top": 1}),
        "If_no_primary_applicant": {
            "type": "If",
            "expression": {"equals": ["@length(outputs('Find_primary_applicant')?['body/value'])", 0]},
            "actions": {"Create_primary_applicant": dv("CreateRecord", {
                "entityName": es("householdmember"),
                f"item/{PREFIX}_name": f"@{{concat({FIRST}, ' ', {LAST})}}",
                f"item/{PREFIX}_firstname": f"@{{{FIRST}}}",
                f"item/{PREFIX}_lastname": f"@{{{LAST}}}",
                f"item/{PREFIX}_applicantrole": role("Primary applicant"),
                f"item/{PREFIX}_email": f"@{{{EMAIL}}}",
                f"item/{PREFIX}_phone": f"@{m('applicant.phone')}",
                f"item/{PREFIX}_formitemid": f"@{{concat({ENTRY_ID}, '-primary')}}",
                f"item/{PREFIX}_household@odata.bind": f"/{es('household')}(@{{{hh}}})"})},
            "else": {"actions": {}}},
        "If_co_applicant": {
            "type": "If",
            "expression": {"and": [{"equals": [f"@{m('applicant.hasCoApplicant')}", "Yes"]},
                                   {"not": {"equals": [f"@{CO_FIRST}", ""]}}]},
            "actions": chain({
                "Find_co_applicant": dv("ListRecords", {
                    "entityName": es("householdmember"), "$select": f"{PREFIX}_householdmemberid",
                    "$filter": f"_{PREFIX}_household_value eq @{{{hh}}} and "
                               f"{PREFIX}_firstname eq '@{{{odata(CO_FIRST)}}}' and "
                               f"{PREFIX}_lastname eq '@{{{odata(CO_LAST)}}}'",
                    "$top": 1}),
                "If_co_applicant_is_new": {
                    "type": "If",
                    "expression": {"equals": ["@length(outputs('Find_co_applicant')?['body/value'])", 0]},
                    "actions": {"Create_co_applicant": dv("CreateRecord", {
                        "entityName": es("householdmember"),
                        f"item/{PREFIX}_name": f"@{{{co_name}}}",
                        f"item/{PREFIX}_firstname": f"@{{{CO_FIRST}}}",
                        f"item/{PREFIX}_lastname": f"@{{{CO_LAST}}}",
                        f"item/{PREFIX}_applicantrole": role("Co-applicant"),
                        f"item/{PREFIX}_formitemid": f"@{{concat({ENTRY_ID}, '-co')}}",
                        f"item/{PREFIX}_household@odata.bind": f"/{es('household')}(@{{{hh}}})"})},
                    "else": {"actions": {}}},
            }),
            "else": {"actions": {}}},
    })


def application_actions():
    answers = {f"item/{PREFIX}_{col}": field_value(col, kind, path) for col, kind, path in SCREENER_FIELDS}
    answers[f"item/{PREFIX}_screenersubmitted"] = f"@{{formatDateTime({SUBMITTED}, 'yyyy-MM-dd')}}"
    answers[f"item/{PREFIX}_screenerlink"] = f"@{m('entry.adminLink')}"
    answers[f"item/{PREFIX}_sourceform@odata.bind"] = f"/{es('sourceform')}(@{{variables('SourceFormId')}})"
    create = {"entityName": es("application"),
              f"item/{PREFIX}_name": f"@{{{LAST}}}",
              f"item/{PREFIX}_screenerentryid": f"@{{{ENTRY_ID}}}",
              f"item/{PREFIX}_stage": choice_value("applicationstage", "Screener submitted"),
              f"item/{PREFIX}_firstsubmittedon": f"@{SUBMITTED}",
              f"item/{PREFIX}_household@odata.bind": f"/{es('household')}(@{{variables('HouseholdId')}})",
              **answers}
    update = {"entityName": es("application"), "recordId": f"@{{{first_id('Find_application', 'application')}}}",
              **answers}
    frozen = f"first(outputs('Find_application')?['body/value'])?['{PREFIX}_answersfrozenon']"
    # Answers are frozen once Unique IDs are assigned: don't apply the change, flag the submission instead.
    frozen_msg = (f"@{{concat('The applicant changed this screener on ', "
                  f"formatDateTime({m('entry.updated')}, 'yyyy-MM-dd'), "
                  "'. The changes were not applied because Unique IDs have been assigned. "
                  "Compare the entry with the application and update it by hand if needed.')}")
    actions = chain({
        "Find_application": dv("ListRecords", {
            "entityName": es("application"), "$select": f"{PREFIX}_applicationid,{PREFIX}_answersfrozenon",
            "$filter": f"{PREFIX}_screenerentryid eq '@{{{odata(ENTRY_ID)}}}'", "$top": 1}),
        "If_application_exists": {
            "type": "If",
            "expression": {"greater": ["@length(outputs('Find_application')?['body/value'])", 0]},
            "actions": {"If_answers_frozen": {
                "type": "If", "expression": {"not": {"equals": [f"@empty({frozen})", True]}},
                "actions": chain({
                    "Remember_frozen_change": setvar("FrozenChange", frozen_msg),
                    "Remember_frozen_application": setvar("ApplicationId",
                                                          f"@{{{first_id('Find_application', 'application')}}}"),
                }),
                "else": {"actions": chain({
                    "Update_application": dv("UpdateRecord", update),
                    "Remember_application": setvar("ApplicationId", f"@{{{first_id('Find_application', 'application')}}}"),
                })}}},
            "else": {"actions": chain({
                "Create_application": dv("CreateRecord", create),
                "Remember_new_application": setvar("ApplicationId",
                                                   f"@outputs('Create_application')?['body/{PREFIX}_applicationid']"),
                # "Smith - A-00012": the record number only exists once the application is created.
                "Name_application": dv("UpdateRecord", {
                    "entityName": es("application"), "recordId": "@variables('ApplicationId')",
                    f"item/{PREFIX}_name": f"@{{concat({LAST}, ' - ', "
                                           f"outputs('Create_application')?['body/{PREFIX}_recordnumber'])}}"}),
                "If_form_has_project": {
                    "type": "If", "expression": {"not": {"equals": ["@variables('FormProjectId')", ""]}},
                    "actions": {"Add_to_form_project": dv("UpdateRecord", {
                        "entityName": es("application"), "recordId": "@variables('ApplicationId')",
                        f"item/{PREFIX}_project@odata.bind": f"/{es('project')}(@{{variables('FormProjectId')}})"})},
                    "else": {"actions": {}}},
            })}},
    })
    # List lookups: only when the application was created or updated (not frozen)
    lookups = {"If_answers_applied": {
        "type": "If", "expression": {"and": [{"not": {"equals": ["@variables('ApplicationId')", ""]}},
                                             {"equals": ["@variables('FrozenChange')", ""]}]},
        "actions": chain({
            **match_list_value("Find_county", "County", m("applicant.county"),
                               f" and _{PREFIX}_state_value eq @{{if(empty(outputs('Find_state')?['body/value']), "
                               f"'00000000-0000-0000-0000-000000000000', {first_id('Find_state', 'listitem')})}}"),
            **set_lookup_if_found("Set_county", "Find_county", "application", "ApplicationId", "county"),
            **ami_actions(),
            **{k: v for col_table, col, lst, path in SCREENER_LISTS for k, v in {
                **match_list_value(f"Find_{col}", lst, q(*path)),
                **set_lookup_if_found(f"Set_{col}", f"Find_{col}", col_table, "ApplicationId", col)}.items()},
        }),
        "else": {"actions": {}}}}
    return actions, lookups


HUD = choice_value("limitsource", "HUD")


def ami_actions():
    """Point the application's "AMI limits used" at its county's newest HUD AMI Limits record. The application's
    Stated income (% of AMI) is a formula column over that link (schema.py AMI_PCT), so it recalculates whenever
    the income, household size or limits change. tools/recalc_ami.py re-points existing applications each year.
    If the county has no HUD limits, the link is left as it is."""
    county = (f"if(empty(outputs('Find_county')?['body/value']), '00000000-0000-0000-0000-000000000000', "
              f"{first_id('Find_county', 'listitem')})")
    return chain({
        "Find_ami_limits": dv("ListRecords", {
            "entityName": es("incomelimitset"), "$select": f"{PREFIX}_incomelimitsetid",
            "$filter": f"_{PREFIX}_county_value eq @{{{county}}} and {PREFIX}_limitsource eq {HUD} and statecode eq 0",
            "$orderby": f"{PREFIX}_year desc", "$top": 1}),
        "If_ami_limits_found": {
            "type": "If", "expression": {"greater": ["@length(outputs('Find_ami_limits')?['body/value'])", 0]},
            "actions": {"Set_ami_limits": dv("UpdateRecord", {
                "entityName": es("application"), "recordId": "@variables('ApplicationId')",
                f"item/{PREFIX}_amilimits@odata.bind":
                    f"/{es('incomelimitset')}(@{{{first_id('Find_ami_limits', 'incomelimitset')}}})"})},
            "else": {"actions": {}}},
        # Organization eligibility is a formula over "Eligibility rules used": link the organization's rules
        # (the oldest active record, if there's ever more than one).
        "Find_eligibility_rules": dv("ListRecords", {
            "entityName": es("eligibility"), "$select": f"{PREFIX}_eligibilityid",
            "$filter": "statecode eq 0", "$orderby": "createdon asc", "$top": 1}),
        "If_eligibility_rules_found": {
            "type": "If", "expression": {"greater": ["@length(outputs('Find_eligibility_rules')?['body/value'])", 0]},
            "actions": {"Set_eligibility_rules": dv("UpdateRecord", {
                "entityName": es("application"), "recordId": "@variables('ApplicationId')",
                f"item/{PREFIX}_eligibilityrules@odata.bind":
                    f"/{es('eligibility')}(@{{{first_id('Find_eligibility_rules', 'eligibility')}}})"})},
            "else": {"actions": {}}},
    })


def screener_flow(mapping):
    """The screener intake flow for one form mapping. The main screener (screener.json) keeps the name and ID
    the flow has always had, so its web address doesn't change; another screener gets its own flow."""
    use_form(mapping)
    received = choice_value("submissionstatus", "Received")
    sub_find = "Find_submission"
    log = chain({
        sub_find: dv("ListRecords", {
            "entityName": es("formsubmission"), "$select": f"{PREFIX}_formsubmissionid",
            "$filter": f"{PREFIX}_provider eq '{PROVIDER}' and {PREFIX}_externalentryid eq '@{{{odata(ENTRY_ID)}}}'",
            "$top": 1}),
        "If_submission_exists": {
            "type": "If",
            "expression": {"greater": [f"@length(outputs('{sub_find}')?['body/value'])", 0]},
            "actions": chain({
                "Update_submission": dv("UpdateRecord", {
                    "entityName": es("formsubmission"), "recordId": f"@{{{first_id(sub_find, 'formsubmission')}}}",
                    f"item/{PREFIX}_payload": "@{string(triggerBody())}",
                    f"item/{PREFIX}_receivedon": "@{utcNow('yyyy-MM-dd')}",
                    f"item/{PREFIX}_status": received, f"item/{PREFIX}_errordetail": ""}),
                "Remember_submission": setvar("SubmissionId", f"@{{{first_id(sub_find, 'formsubmission')}}}"),
            }),
            "else": {"actions": chain({
                "Create_submission": dv("CreateRecord", {
                    "entityName": es("formsubmission"),
                    f"item/{PREFIX}_name": f"@{{concat('Screener ', {ENTRY_ID}, ', ', {FIRST}, ' ', {LAST})}}",
                    f"item/{PREFIX}_provider": PROVIDER,
                    f"item/{PREFIX}_formtype": choice_value("formtype", "Screener"),
                    f"item/{PREFIX}_externalentryid": f"@{{{ENTRY_ID}}}",
                    f"item/{PREFIX}_receivedon": "@{utcNow('yyyy-MM-dd')}",
                    f"item/{PREFIX}_entrylink": f"@{m('entry.adminLink')}",
                    f"item/{PREFIX}_payload": "@{string(triggerBody())}",
                    f"item/{PREFIX}_status": received}),
                "Remember_new_submission": setvar("SubmissionId",
                                                  f"@outputs('Create_submission')?['body/{PREFIX}_formsubmissionid']"),
            })}},
    })
    app_actions, lookups = application_actions()
    process = chain({
        "Choice_maps": {"type": "Compose", "inputs": choice_maps()},
        **multi_actions(),
        **match_list_value("Find_state", "State", m("applicant.state")),
        **source_form_actions(),
        **household_actions(),
        **member_actions(),
        **app_actions,
        **lookups,
    })
    actions = chain({
        "Init_household": {"type": "InitializeVariable",
                           "inputs": {"variables": [{"name": "HouseholdId", "type": "string", "value": ""}]}},
        "Init_application": {"type": "InitializeVariable",
                             "inputs": {"variables": [{"name": "ApplicationId", "type": "string", "value": ""}]}},
        "Init_submission": {"type": "InitializeVariable",
                            "inputs": {"variables": [{"name": "SubmissionId", "type": "string", "value": ""}]}},
        "Init_form_project": {"type": "InitializeVariable",
                              "inputs": {"variables": [{"name": "FormProjectId", "type": "string", "value": ""}]}},
        "Init_source_form": {"type": "InitializeVariable",
                             "inputs": {"variables": [{"name": "SourceFormId", "type": "string", "value": ""}]}},
        "Init_frozen_change": {"type": "InitializeVariable",
                               "inputs": {"variables": [{"name": "FrozenChange", "type": "string", "value": ""}]}},
        "Keep_a_copy": {"type": "Scope", "actions": log},
        "Process_screener": {"type": "Scope", "actions": process},
    })
    # Processed, or Needs attention when a frozen application's screener changed. Either way, link the
    # submission to its household and application.
    processed, attention = (choice_value("submissionstatus", s) for s in ("Processed", "Needs attention"))
    actions["Mark_processed"] = dv("UpdateRecord", {
        "entityName": es("formsubmission"), "recordId": "@variables('SubmissionId')",
        f"item/{PREFIX}_status": f"@if(empty(variables('FrozenChange')), {processed}, {attention})",
        f"item/{PREFIX}_errordetail": "@variables('FrozenChange')",
        f"item/{PREFIX}_household@odata.bind": f"/{es('household')}(@{{variables('HouseholdId')}})",
        f"item/{PREFIX}_application@odata.bind": f"/{es('application')}(@{{variables('ApplicationId')}})",
        f"item/{PREFIX}_sourceform@odata.bind": f"/{es('sourceform')}(@{{variables('SourceFormId')}})"})
    actions["Mark_processed"]["runAfter"] = {"Process_screener": ["Succeeded"]}
    # Only the steps that didn't succeed, so the error isn't cut off by pages of successful steps.
    actions["Failed_steps"] = {"type": "Query", "runAfter": {"Process_screener": ["Failed", "TimedOut"]},
                               "inputs": {"from": "@result('Process_screener')",
                                          "where": "@not(contains(createArray('Succeeded', 'Skipped'), item()?['status']))"}}
    actions["Mark_needs_attention"] = dv("UpdateRecord", {
        "entityName": es("formsubmission"), "recordId": "@variables('SubmissionId')",
        f"item/{PREFIX}_status": choice_value("submissionstatus", "Needs attention"),
        f"item/{PREFIX}_errordetail": "@{take(string(body('Failed_steps')), 3900)}"})
    actions["Mark_needs_attention"]["runAfter"] = {"Failed_steps": ["Succeeded"]}

    definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                       "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
        # triggerAuthenticationType All = "Who can trigger the flow? Anyone" (the address's signature is the key).
        # Don't Save this flow in the Power Automate designer: it renames the trigger to "manual", which changes
        # the web address every connected form posts to. The name stays as it is so those addresses keep working.
        "triggers": {"When_Cognito_posts_a_screener": {
            "type": "Request", "kind": "Http",
            "inputs": {"triggerAuthenticationType": "All", "schema": {"type": "object"}},
            # One at a time, so two entries from the same person can't both make a household.
            "runtimeConfiguration": {"concurrency": {"runs": 1}}}},
        "actions": actions,
    }
    return {
        "name": "CLT: Screener intake" + (f" ({mapping.label or mapping.slug})" if mapping.slug else ""),
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "clt-stewardship/flows/screener-intake"
                             + (f"/{mapping.slug}" if mapping.slug else ""))),
        "description": "Receives screener entries posted by the forms platform and creates or updates the "
                       "household, its members and the application. Not tied to a project.",
        "definition": definition,
    }
