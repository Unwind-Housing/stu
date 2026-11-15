"""
Intake & Selection: the full application intake flow (used by build_flows.py).

The forms platform posts each full application entry here (in Cognito Forms: "Post JSON data to a website", on
Submit and on Update). Which question feeds which field comes from the organization's mapping file
(form_mapping.py), so nothing about a form's wording is in this code. The form should have a read-only
"Application Number" box near the top, filled in by the invite link (in Cognito Forms:
?entry={"PrimaryApplicant":{"ApplicationNumber":"A-00012"}}).

What the flow does with one entry:
  1. Keeps a copy as a Form submission (form type Full application), status Received.
  2. Finds the application, in this order:
       a. one already linked to this entry (the applicant or staff saved the entry again),
       b. by Application Number (the A-number on the invite link),
       c. by email: the newest active application of the household with that primary email.
     No match: the submission is marked Needs attention and nothing else changes.
  3. Saves the full application answers on the application, and moves its stage to
     "Full application submitted" unless staff have already moved it further.
  4. Household members: the primary applicant and co-applicant are matched to the members the
     screener added (and get their date of birth and relationship); other members are added, or
     updated when the same entry comes in again.
  5. One Income source, Debt and Asset per line on the form, linked to the household member whose name
     the applicant typed (when it matches), with the type matched to the List values. Lines are matched
     by the form's line ID, so a resubmitted entry updates its lines instead of adding them again.
     Staff review fields (review status, verified amounts) are never touched.
  6. The Form submission is marked Processed, or Needs attention with the error.

Lines the applicant deletes from the form before saving it again are left in Dataverse for staff to
exclude. Ethnic origin isn't copied: demographics wait for column security (step 8).
"""
import json
import uuid

from schema import CHOICES
import flows_intake as fi
from flows_intake import (PREFIX, choice_value, dv, chain, q, odata, setvar, es, first_id, match_list_value,
                          source_form_actions, m)

# Set by use_form() from the mapping of the form the flow is being built for.
ENTRY_ID = SUBMITTED = NUMBER = EMAIL = FIRST = LAST = CO_FIRST = CO_LAST = LINE_ID = None


def use_form(mapping):
    """Point this module (and flows_intake's shared helpers) at one full application form's mapping."""
    global ENTRY_ID, SUBMITTED, NUMBER, EMAIL, FIRST, LAST, CO_FIRST, CO_LAST, LINE_ID
    fi.use_form(mapping)
    ENTRY_ID, SUBMITTED, EMAIL, FIRST, LAST = fi.ENTRY_ID, fi.SUBMITTED, fi.EMAIL, fi.FIRST, fi.LAST   # "5-3" ...
    CO_FIRST, CO_LAST = fi.CO_FIRST, fi.CO_LAST
    NUMBER = f"toUpper(trim(coalesce({m('applicant.applicationNumber')}, '')))"
    LINE_ID = mapping.paths.get("entry.lineId", ("Id",))   # each line's own ID inside a repeating section


NO_MATCH = "00000000-0000-0000-0000-000000000000"
HH = "variables('HouseholdId')"
APP = "variables('ApplicationId')"


def it(loop, *path):
    """Expression for a field of the current line in a For each."""
    return f"items('{loop}')" + "".join(f"?['{p}']" for p in path)


def item(loop, key):
    """Expression for the answer a mapping key points at, inside the current line of a For each."""
    return it(loop, *fi.MAP.path(key))


def yesno(expr):
    return f"@if(empty({expr}), null, equals({expr}, 'Yes'))"


def opt(expr):
    """A date or other value that must be null rather than an empty string."""
    return f"@if(empty({expr}), null, {expr})"


def choice_of(name, expr):
    """Form answer -> choice value. The answers are Stu's labels word for word unless the mapping's "choices" says otherwise."""
    custom = fi.MAP.choices(name)
    pairs = ({k: choice_value(name, v) for k, v in custom.items()} if custom
             else {label: choice_value(name, label) for label in CHOICES[name][1]})
    labels = json.dumps(pairs).replace("'", "''")
    return f"@if(empty({expr}), null, json('{labels}')?[{expr}])"


def stage_after_submit():
    """Move to Full application submitted, unless staff have already moved it past that point."""
    v = lambda s: str(choice_value("applicationstage", s))
    early = ", ".join(f"'{v(s)}'" for s in ("Screener submitted", "Invited to full application",
                                            "Full application incomplete", "Pre-screened", "In selection"))
    return (f"@if(or(equals(variables('Stage'), ''), contains(createArray({early}), variables('Stage'))), "
            f"{choice_value('applicationstage', 'Full application submitted')}, int(variables('Stage')))")


def remember(find):
    """Set ApplicationId, HouseholdId and Stage from the first application a ListRecords returned."""
    row = f"first(outputs('{find}')?['body/value'])"
    return chain({
        f"{find}_application": setvar("ApplicationId", f"@{{{first_id(find, 'application')}}}"),
        f"{find}_household": setvar("HouseholdId", f"@{{coalesce({row}?['_{PREFIX}_household_value'], '')}}"),
        f"{find}_stage": setvar("Stage", f"@{{string(coalesce({row}?['{PREFIX}_stage'], ''))}}"),
    })


def found(find):
    return {"greater": [f"@length(outputs('{find}')?['body/value'])", 0]}


APP_SELECT = f"{PREFIX}_applicationid,_{PREFIX}_household_value,{PREFIX}_stage"


def find_application_actions():
    by_email = chain({
        "Find_household_by_email": dv("ListRecords", {
            "entityName": es("household"), "$select": f"{PREFIX}_householdid",
            "$filter": f"@{{if(empty({EMAIL}), '{PREFIX}_householdid eq null', "
                       f"concat('{PREFIX}_primaryemail eq ''', {odata(EMAIL)}, ''''))}}",
            "$top": 1}),
        "If_household_found": {
            "type": "If", "expression": found("Find_household_by_email"),
            "actions": chain({
                "Find_by_email": dv("ListRecords", {
                    "entityName": es("application"), "$select": APP_SELECT,
                    "$filter": f"_{PREFIX}_household_value eq @{{{first_id('Find_household_by_email', 'household')}}}"
                               " and statecode eq 0",
                    "$orderby": "createdon desc", "$top": 1}),
                "If_found_by_email": {"type": "If", "expression": found("Find_by_email"),
                                      "actions": remember("Find_by_email"), "else": {"actions": {}}},
            }),
            "else": {"actions": {}}},
    })
    by_number = chain({
        "Find_by_number": dv("ListRecords", {
            "entityName": es("application"), "$select": APP_SELECT,
            "$filter": f"@{{if(empty({NUMBER}), '{PREFIX}_applicationid eq null', "
                       f"concat('{PREFIX}_recordnumber eq ''', {odata(NUMBER)}, ''''))}}",
            "$top": 1}),
        "If_found_by_number": {"type": "If", "expression": found("Find_by_number"),
                               "actions": remember("Find_by_number"), "else": {"actions": by_email}},
    })
    return chain({
        "Find_by_entry": dv("ListRecords", {
            "entityName": es("application"), "$select": APP_SELECT,
            "$filter": f"{PREFIX}_fullappentryid eq '@{{{odata(ENTRY_ID)}}}'", "$top": 1}),
        "If_found_by_entry": {"type": "If", "expression": found("Find_by_entry"),
                              "actions": remember("Find_by_entry"), "else": {"actions": by_number}},
    })


def application_update():
    def s(key):
        return f"coalesce({m(key)}, '')"
    a = lambda key: m(f"answers.{key}")
    hbe = (f"if(startsWith({s('answers.hbeStatus')}, 'I have completed'), "
           f"trim(concat('Completed: ', {s('answers.hbeCompletedProvider')}, ' ', "
           f"{s('answers.hbeCompletedDate')})), "
           f"if(empty({a('hbeStatus')}), '', "
           f"trim(concat('Scheduled: ', {s('answers.hbeScheduledProvider')}, ' ', "
           f"{s('answers.hbeScheduledDate')}))))")
    no_income = (f"if(empty({a('adultsWithNoIncomeNames')}), '', concat({s('answers.adultsWithNoIncomeNames')}, "
                 f"'. Expenses covered by: ', {s('answers.noIncomeExpensesCoveredBy')}))")
    residency = (f"concat('Applicant: ', {s('answers.county')}, '. ', "
                 f"{s('answers.residencyProof')}, "
                 f"if(empty({a('coCounty')}), '', concat(decodeUriComponent('%0A'), 'Co-applicant: ', "
                 f"{s('answers.coCounty')}, '. ', "
                 f"{s('answers.coResidencyProof')})))")
    p = lambda col: f"item/{PREFIX}_{col}"
    return dv("UpdateRecord", {
        "entityName": es("application"), "recordId": f"@{APP}",
        p("fullappentryid"): f"@{{{ENTRY_ID}}}",
        p("fullappsubmitted"): f"@{{formatDateTime({SUBMITTED}, 'yyyy-MM-dd')}}",
        p("fullapplink"): f"@{m('entry.adminLink')}",
        p("stage"): stage_after_submit(),
        p("expectsincomechange"): yesno(a("expectsIncomeChange")),
        p("incomechangedetails"): f"@{a('incomeChangeDetails')}",
        p("adultwithnoincome"): yesno(a("adultWithNoIncome")),
        p("noincomedetails"): f"@{{{no_income}}}",
        p("latepayments"): yesno(a("latePayments")),
        p("latepaymentsexplanation"): f"@{a('latePaymentsExplanation')}",
        p("bankruptcyexplanation"): f"@{a('bankruptcyExplanation')}",
        p("creditexplanation"): f"@{a('creditExplanation')}",
        p("giftfunds"): yesno(a("giftFunds")),
        p("giftamount"): f"@{a('giftAmount')}",
        p("giftgiver"): f"@{a('giftGiver')}",
        p("currenthousingcost"): f"@{a('currentHousingCost')}",
        p("residencydetails"): f"@{{{residency}}}",
        p("ownedhome3yrs"): yesno(a("ownedHome3Yrs")),
        p("fthbcertified"): f"@coalesce({a('fthbCertified')}, false)",
        p("lender"): f"@{a('lender')}",
        p("loanofficeremail"): f"@{a('loanOfficerEmail')}",
        p("loanofficerphone"): f"@{a('loanOfficerPhone')}",
        p("hbeducationdetails"): f"@{{{hbe}}}",
        p("fullappcomments"): f"@{a('comments')}",
        p("sourceform@odata.bind"): f"/{es('sourceform')}(@{{variables('SourceFormId')}})",
    })


def bind_if_found(name, find, find_table, table, record, column, else_actions=None):
    """If the find returned a row, point the record's lookup at it (otherwise run else_actions)."""
    return {name: {"type": "If", "expression": found(find),
                   "actions": {f"{name}_now": dv("UpdateRecord", {
                       "entityName": es(table), "recordId": f"@{record}",
                       f"item/{PREFIX}_{column}@odata.bind": f"/{es(find_table)}(@{{{first_id(find, find_table)}}})"})},
                   "else": {"actions": else_actions or {}}}}


def relationship_actions(prefix, answer, record):
    """Match the relationship answer to the Relationship list; keep the typed answer when it doesn't match."""
    find = f"Find_{prefix}_relationship"
    return chain({
        **match_list_value(find, "Relationship", answer),
        **bind_if_found(f"Set_{prefix}_relationship", find, "listitem", "householdmember", record, "relationship",
                        else_actions={f"Keep_{prefix}_relationship": dv("UpdateRecord", {
                            "entityName": es("householdmember"), "recordId": f"@{record}",
                            f"item/{PREFIX}_relationshipother": f"@{answer}"})}),
    })


def member_actions():
    role = lambda r: choice_value("applicantrole", r)
    hhbind = f"/{es('household')}(@{{{HH}}})"
    primary_find = "Find_primary_member"
    co_find = "Find_co_member"
    primary_fields = {f"item/{PREFIX}_dateofbirth": opt(m("applicant.dateOfBirth")),
                      f"item/{PREFIX}_email": f"@{{{EMAIL}}}",
                      f"item/{PREFIX}_phone": f"@{m('applicant.phone')}"}
    co_fields = {f"item/{PREFIX}_dateofbirth": opt(m("applicant.coDateOfBirth")),
                 f"item/{PREFIX}_email": f"@{m('applicant.coEmail')}",
                 f"item/{PREFIX}_phone": f"@{m('applicant.coPhone')}"}
    loop = "Each_other_member"
    oname = lambda part: f"trim(coalesce({item(loop, 'otherMembers.' + part.lower() + 'Name')}, ''))"
    other_id = f"concat({ENTRY_ID}, '-member-', {it(loop, *LINE_ID)})"
    other_fields = {f"item/{PREFIX}_name": f"@{{concat({oname('First')}, ' ', {oname('Last')})}}",
                    f"item/{PREFIX}_firstname": f"@{{{oname('First')}}}",
                    f"item/{PREFIX}_lastname": f"@{{{oname('Last')}}}",
                    f"item/{PREFIX}_dateofbirth": opt(item(loop, "otherMembers.dateOfBirth")),
                    f"item/{PREFIX}_formitemid": f"@{{{other_id}}}"}
    other = chain({
        "Find_other_member": dv("ListRecords", {
            "entityName": es("householdmember"), "$select": f"{PREFIX}_householdmemberid",
            # the same line from an earlier save of this entry, or someone already in the household by name
            "$filter": f"_{PREFIX}_household_value eq @{{{HH}}} and ({PREFIX}_formitemid eq '@{{{odata(other_id)}}}' or "
                       f"({PREFIX}_firstname eq '@{{{odata(oname('First'))}}}' and "
                       f"{PREFIX}_lastname eq '@{{{odata(oname('Last'))}}}'))",
            "$top": 1}),
        "If_other_member_exists": {
            "type": "If", "expression": found("Find_other_member"),
            "actions": chain({
                "Update_other_member": dv("UpdateRecord", {
                    "entityName": es("householdmember"),
                    "recordId": f"@{{{first_id('Find_other_member', 'householdmember')}}}", **other_fields}),
                "Remember_other_member": setvar("MemberId", f"@{{{first_id('Find_other_member', 'householdmember')}}}"),
            }),
            "else": {"actions": chain({
                "Create_other_member": dv("CreateRecord", {
                    "entityName": es("householdmember"), **other_fields,
                    f"item/{PREFIX}_applicantrole": role("Other household member"),
                    f"item/{PREFIX}_household@odata.bind": hhbind}),
                "Remember_new_other_member": setvar(
                    "MemberId", f"@outputs('Create_other_member')?['body/{PREFIX}_householdmemberid']"),
            })}},
        **relationship_actions("other", item(loop, "otherMembers.relationship"), "variables('MemberId')"),
    })
    return chain({
        # Primary applicant: the screener added them; add them now if not (an application keyed in by staff).
        primary_find: dv("ListRecords", {
            "entityName": es("householdmember"), "$select": f"{PREFIX}_householdmemberid",
            "$filter": f"_{PREFIX}_household_value eq @{{{HH}}} and {PREFIX}_applicantrole eq {role('Primary applicant')}",
            "$top": 1}),
        "If_primary_member_exists": {
            "type": "If", "expression": found(primary_find),
            "actions": chain({
                "Update_primary_member": dv("UpdateRecord", {
                    "entityName": es("householdmember"),
                    "recordId": f"@{{{first_id(primary_find, 'householdmember')}}}", **primary_fields}),
                "Remember_primary_member": setvar("MemberId", f"@{{{first_id(primary_find, 'householdmember')}}}"),
            }),
            "else": {"actions": chain({
                "Create_primary_member": dv("CreateRecord", {
                    "entityName": es("householdmember"), **primary_fields,
                    f"item/{PREFIX}_name": f"@{{concat({FIRST}, ' ', {LAST})}}",
                    f"item/{PREFIX}_firstname": f"@{{{FIRST}}}",
                    f"item/{PREFIX}_lastname": f"@{{{LAST}}}",
                    f"item/{PREFIX}_applicantrole": role("Primary applicant"),
                    f"item/{PREFIX}_formitemid": f"@{{concat({ENTRY_ID}, '-primary')}}",
                    f"item/{PREFIX}_household@odata.bind": hhbind}),
                "Remember_new_primary_member": setvar(
                    "MemberId", f"@outputs('Create_primary_member')?['body/{PREFIX}_householdmemberid']"),
            })}},
        **relationship_actions("primary", "'Self'", "variables('MemberId')"),
        "If_co_applicant": {
            "type": "If",
            "expression": {"and": [{"equals": [f"@{m('applicant.hasCoApplicant')}", "Yes"]},
                                   {"not": {"equals": [f"@{CO_FIRST}", ""]}}]},
            "actions": chain({
                co_find: dv("ListRecords", {
                    "entityName": es("householdmember"), "$select": f"{PREFIX}_householdmemberid",
                    "$filter": f"_{PREFIX}_household_value eq @{{{HH}}} and ({PREFIX}_applicantrole eq "
                               f"{role('Co-applicant')} or ({PREFIX}_firstname eq '@{{{odata(CO_FIRST)}}}' and "
                               f"{PREFIX}_lastname eq '@{{{odata(CO_LAST)}}}'))",
                    "$top": 1}),
                "If_co_member_exists": {
                    "type": "If", "expression": found(co_find),
                    "actions": chain({
                        "Update_co_member": dv("UpdateRecord", {
                            "entityName": es("householdmember"),
                            "recordId": f"@{{{first_id(co_find, 'householdmember')}}}", **co_fields,
                            f"item/{PREFIX}_applicantrole": role("Co-applicant")}),
                        "Remember_co_member": setvar("MemberId", f"@{{{first_id(co_find, 'householdmember')}}}"),
                    }),
                    "else": {"actions": chain({
                        "Create_co_member": dv("CreateRecord", {
                            "entityName": es("householdmember"), **co_fields,
                            f"item/{PREFIX}_name": f"@{{concat({CO_FIRST}, ' ', {CO_LAST})}}",
                            f"item/{PREFIX}_firstname": f"@{{{CO_FIRST}}}",
                            f"item/{PREFIX}_lastname": f"@{{{CO_LAST}}}",
                            f"item/{PREFIX}_applicantrole": role("Co-applicant"),
                            f"item/{PREFIX}_formitemid": f"@{{concat({ENTRY_ID}, '-co')}}",
                            f"item/{PREFIX}_household@odata.bind": hhbind}),
                        "Remember_new_co_member": setvar(
                            "MemberId", f"@outputs('Create_co_member')?['body/{PREFIX}_householdmemberid']"),
                    })}},
                **relationship_actions("co", m("applicant.coRelationship"), "variables('MemberId')"),
            }),
            "else": {"actions": {}}},
        loop: {"type": "Foreach", "foreach": f"@coalesce({m('otherMembers.list')}, json('[]'))",
               "actions": other, "runtimeConfiguration": {"concurrency": {"repetitions": 1}}},
    })


def line_loop(kind, table, section, member_key, type_list, type_other, main_key, fields):
    """For each line of a repeating section: add or update its row, then link its type and household member.
    section is the mapping's name for it (income, debts, assets); fields is {column: (mapping key, kind)}."""
    loop = f"Each_{kind}"
    cap = kind.capitalize()
    line_id = f"concat({ENTRY_ID}, '-{kind}-', {it(loop, *LINE_ID)})"
    member = f"trim(coalesce({item(loop, f'{section}.{member_key}')}, ''))"
    type_answer = item(loop, f"{section}.type")
    # "Rivera, County Hospital", or the type when there's no payer
    main, fallback = item(loop, f"{section}.{main_key}"), type_answer
    name = f"take(concat({member}, ', ', if(empty({main}), coalesce({fallback}, ''), {main})), 100)"
    values = {f"item/{PREFIX}_{col}": LINE_KINDS[how](item(loop, f"{section}.{key}"))
              for col, (key, how) in fields.items()}
    values[f"item/{PREFIX}_name"] = f"@{{{name}}}"
    values[f"item/{PREFIX}_formitemid"] = f"@{{{line_id}}}"
    find = f"Find_{kind}"
    type_find = f"Find_{kind}_type"
    member_find = f"Find_{kind}_member"
    rec = "variables('LineId')"
    actions = chain({
        find: dv("ListRecords", {
            "entityName": es(table), "$select": f"{PREFIX}_{table}id",
            "$filter": f"{PREFIX}_formitemid eq '@{{{odata(line_id)}}}'", "$top": 1}),
        f"If_{kind}_exists": {
            "type": "If", "expression": found(find),
            "actions": chain({
                f"Update_{kind}": dv("UpdateRecord", {"entityName": es(table),
                                                      "recordId": f"@{{{first_id(find, table)}}}", **values}),
                f"Remember_{kind}": setvar("LineId", f"@{{{first_id(find, table)}}}"),
            }),
            "else": {"actions": chain({
                f"Create_{kind}": dv("CreateRecord", {
                    "entityName": es(table), **values,
                    f"item/{PREFIX}_application@odata.bind": f"/{es('application')}(@{{{APP}}})"}),
                f"Remember_new_{kind}": setvar("LineId", f"@outputs('Create_{kind}')?['body/{PREFIX}_{table}id']"),
            })}},
        **match_list_value(type_find, type_list, type_answer),
        **bind_if_found(f"Set_{kind}_type", type_find, "listitem", table, rec, type_field_column(table),
                        else_actions={f"Keep_{kind}_type": dv("UpdateRecord", {
                            "entityName": es(table), "recordId": f"@{rec}",
                            f"item/{PREFIX}_{type_other}": f"@{type_answer}"})}),
        # the applicant types a name: match a member of the household by full name or first name
        member_find: dv("ListRecords", {
            "entityName": es("householdmember"), "$select": f"{PREFIX}_householdmemberid",
            "$filter": f"_{PREFIX}_household_value eq @{{if(empty({member}), '{NO_MATCH}', {HH})}} and "
                       f"({PREFIX}_name eq '@{{{odata(member)}}}' or {PREFIX}_firstname eq '@{{{odata(member)}}}')",
            "$top": 1}),
        **bind_if_found(f"Set_{kind}_member", member_find, "householdmember", table, rec, "member"),
    })
    # The form always sends one row per section, blank when the household has none (no debts, say): skip a row
    # with no type, no person and no payer, lender or institution.
    filled = (f"@trim(concat(string(coalesce({type_answer}, '')), {member}, "
              f"string(coalesce({main}, ''))))")
    return {loop: {"type": "Foreach", "foreach": f"@coalesce({m(f'{section}.list')}, json('[]'))",
                   "actions": {f"If_{kind}_filled_in": {
                       "type": "If", "expression": {"not": {"equals": [filled, ""]}},
                       "actions": actions, "else": {"actions": {}}}},
                   "runtimeConfiguration": {"concurrency": {"repetitions": 1}}}}


def type_field_column(table):
    return {"incomesource": "incometype", "debt": "debttype", "asset": "assettype"}[table]


# How a line's answer is written: as it is, as null when blank (dates), or as a choice value.
LINE_KINDS = {
    "raw": lambda v: f"@{v}",
    "optional": opt,
    "incomestatus": lambda v: choice_of("incomestatus", v),
    "payfrequency": lambda v: choice_of("payfrequency", v),
}


def income_loop():
    return line_loop(
        "income", "incomesource", "income", "member", "Income type", "incometypeother", "payer",
        {"memberasentered": ("member", "raw"),
         "payer": ("payer", "raw"),
         "jobtitle": ("jobtitle", "raw"),
         "startdate": ("startdate", "optional"),
         "incomestatus": ("incomestatus", "incomestatus"),
         "enddate": ("enddate", "optional"),
         "payfrequency": ("payfrequency", "payfrequency"),
         "grosspayperperiod": ("grosspayperperiod", "raw"),
         "hoursperperiod": ("hoursperperiod", "raw"),
         "annualbonus": ("annualbonus", "raw"),
         "annualovertime": ("annualovertime", "raw"),
         "paystubenddate": ("paystubenddate", "optional"),
         "ytdgross": ("ytdgross", "raw"),
         "applicantnotes": ("applicantnotes", "raw")})


def debt_loop():
    return line_loop(
        "debt", "debt", "debts", "member", "Debt type", "debttypeother", "creditor",
        {"memberasentered": ("member", "raw"),
         "creditor": ("creditor", "raw"),
         "monthlypayment": ("monthlypayment", "raw"),
         "remainingbalance": ("remainingbalance", "raw"),
         "description": ("description", "raw")})


def asset_loop():
    return line_loop(
        "asset", "asset", "assets", "holder", "Asset type", "assettypeother", "institution",
        {"holderasentered": ("holder", "raw"),
         "institution": ("institution", "raw"),
         "description": ("description", "raw"),
         "currentvalue": ("currentvalue", "raw")})


def full_application_flow(mapping):
    """The full application intake flow for one form mapping. The main form (full-application.json) keeps the
    name and ID the flow has always had, so its web address doesn't change; another form gets its own flow."""
    use_form(mapping)
    received = choice_value("submissionstatus", "Received")
    sub_find = "Find_submission"
    log = chain({
        sub_find: dv("ListRecords", {
            "entityName": es("formsubmission"), "$select": f"{PREFIX}_formsubmissionid",
            "$filter": f"{PREFIX}_provider eq '{fi.PROVIDER}' and {PREFIX}_externalentryid eq '@{{{odata(ENTRY_ID)}}}'",
            "$top": 1}),
        "If_submission_exists": {
            "type": "If", "expression": found(sub_find),
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
                    f"item/{PREFIX}_name": f"@{{concat('Full application ', {ENTRY_ID}, ', ', {FIRST}, ' ', {LAST})}}",
                    f"item/{PREFIX}_provider": fi.PROVIDER,
                    f"item/{PREFIX}_formtype": choice_value("formtype", "Full application"),
                    f"item/{PREFIX}_externalentryid": f"@{{{ENTRY_ID}}}",
                    f"item/{PREFIX}_receivedon": "@{utcNow('yyyy-MM-dd')}",
                    f"item/{PREFIX}_entrylink": f"@{m('entry.adminLink')}",
                    f"item/{PREFIX}_payload": "@{string(triggerBody())}",
                    f"item/{PREFIX}_status": received}),
                "Remember_new_submission": setvar("SubmissionId",
                                                  f"@outputs('Create_submission')?['body/{PREFIX}_formsubmissionid']"),
            })}},
    })
    no_household = ("@{concat('The matching application has no household. Link it to a household, then in "
                    "the forms platform open the entry, make a small change and save it: that sends it again.')}")
    no_match = (f"@{{concat('No application matches this full application (Application Number: ', "
                f"if(empty({NUMBER}), 'blank', {NUMBER}), ', email: ', if(empty({EMAIL}), 'blank', {EMAIL}), "
                "'). In the forms platform, type the applicant''s A-number into Application Number on the entry and save it: "
                "that sends it again.')}")
    process = chain({
        **source_form_actions("Full application"),
        **find_application_actions(),
        "If_application_found": {
            "type": "If", "expression": {"and": [{"not": {"equals": [f"@{APP}", ""]}},
                                                 {"not": {"equals": [f"@{HH}", ""]}}]},
            "actions": chain({
                "Update_application": application_update(),
                **member_actions(),
                **income_loop(),
                **debt_loop(),
                **asset_loop(),
            }),
            "else": {"actions": {"Remember_no_match": setvar(
                "Problem", f"@{{if(empty({APP}), {no_match[2:-1]}, {no_household[2:-1]})}}")}}},
    })
    init = lambda name: {"type": "InitializeVariable",
                         "inputs": {"variables": [{"name": name, "type": "string", "value": ""}]}}
    actions = chain({
        **{f"Init_{v}": init(v) for v in ("SubmissionId", "SourceFormId", "FormProjectId", "ApplicationId",
                                          "HouseholdId", "Stage", "MemberId", "LineId", "Problem")},
        "Keep_a_copy": {"type": "Scope", "actions": log},
        "Process_full_application": {"type": "Scope", "actions": process},
    })
    processed, attention = (choice_value("submissionstatus", s) for s in ("Processed", "Needs attention"))
    actions["If_matched"] = {
        "type": "If", "runAfter": {"Process_full_application": ["Succeeded"]},
        "expression": {"equals": ["@variables('Problem')", ""]},
        "actions": {"Mark_processed": dv("UpdateRecord", {
            "entityName": es("formsubmission"), "recordId": "@variables('SubmissionId')",
            f"item/{PREFIX}_status": processed, f"item/{PREFIX}_errordetail": "",
            f"item/{PREFIX}_household@odata.bind": f"/{es('household')}(@{{{HH}}})",
            f"item/{PREFIX}_application@odata.bind": f"/{es('application')}(@{{{APP}}})",
            f"item/{PREFIX}_sourceform@odata.bind": f"/{es('sourceform')}(@{{variables('SourceFormId')}})"})},
        "else": {"actions": {"Mark_no_match": dv("UpdateRecord", {
            "entityName": es("formsubmission"), "recordId": "@variables('SubmissionId')",
            f"item/{PREFIX}_status": attention, f"item/{PREFIX}_errordetail": "@variables('Problem')",
            f"item/{PREFIX}_sourceform@odata.bind": f"/{es('sourceform')}(@{{variables('SourceFormId')}})"})}}}
    actions["Failed_steps"] = {"type": "Query", "runAfter": {"Process_full_application": ["Failed", "TimedOut"]},
                               "inputs": {"from": "@result('Process_full_application')",
                                          "where": "@not(contains(createArray('Succeeded', 'Skipped'), item()?['status']))"}}
    actions["Mark_needs_attention"] = dv("UpdateRecord", {
        "entityName": es("formsubmission"), "recordId": "@variables('SubmissionId')",
        f"item/{PREFIX}_status": attention,
        f"item/{PREFIX}_errordetail": "@{take(string(body('Failed_steps')), 3900)}"})
    actions["Mark_needs_attention"]["runAfter"] = {"Failed_steps": ["Succeeded"]}
    definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                       "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
        # Named "manual" because that's what the Power Automate designer renames it to on Save, and the name is
        # part of the web address the forms platform posts to. triggerAuthenticationType All = "Who can trigger
        # the flow? Anyone": without it a designer Save limits the trigger to signed-in tenant users, the address
        # loses its signature, and the form's posts are refused.
        "triggers": {"manual": {
            "type": "Request", "kind": "Http",
            "inputs": {"triggerAuthenticationType": "All", "schema": {"type": "object"}},
            "runtimeConfiguration": {"concurrency": {"runs": 1}}}},
        "actions": actions,
    }
    return {
        "name": "CLT: Full application intake" + (f" ({mapping.label or mapping.slug})" if mapping.slug else ""),
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "clt-stewardship/flows/full-application-intake"
                             + (f"/{mapping.slug}" if mapping.slug else ""))),
        "description": "Receives full application entries posted by the forms platform, finds the application "
                       "(Application Number, then email) and adds its members, income sources, debts and assets.",
        "definition": definition,
    }
