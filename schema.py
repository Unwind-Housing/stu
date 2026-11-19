"""
CLT Stewardship: Dataverse schema spec.

This file is the single source of truth for the tables, columns, choices,
lookups and alternate keys that build_schema.py creates. Read it like a
build sheet. Edit it and re-run the build to add things: the build skips
anything that already exists, so it never changes or deletes existing columns.

A table with documents="<library title>" gets SharePoint document management:
a Documents tab on its form, with one SharePoint folder per record in that library.

Not created here (add these by hand in the maker portal, step 4):
  - formula columns (resale price, age, annualized income, coverage check, ERRR signed amount)
  - rollup columns (ERRR balance, verified income/assets/debt on Application)
  - column security (step 8)

Logical names get the publisher prefix "clt_" automatically.
"""

# ---------------------------------------------------------------------------
# Global choices. Labels that Cognito sends are worded exactly as Cognito
# words them, so the flows can match on the label. Values are assigned by
# the build from the publisher's choice value prefix, in the order listed,
# and written to choice-values.json for use in the flows.
# ---------------------------------------------------------------------------
CHOICES = {
    "resaleformula": ("Resale formula", [
        "Fixed annual rate", "Appraisal share"]),
    "propertystatus": ("Property status", [
        "Prospective acquisition", "Under construction", "Vacant", "For sale",
        "Sale pending", "Owner-occupied", "Rented", "Left program"]),
    "householdstatus": ("Household status", [
        "Applicant", "Invited to full application", "Eligible", "Homeowner",
        "Tenant", "Past homeowner", "Inactive"]),
    "applicantrole": ("Applicant role", [
        "Primary applicant", "Co-applicant", "Other household member"]),
    "applicationstage": ("Application stage", [
        "Screener submitted", "Invited to full application", "Full application incomplete",
        "Full application submitted", "In review", "Needs follow-up", "Approved",
        "Lender notified", "Not eligible", "Withdrawn",
        # v0.5 intake pipeline (older values above stay for existing records)
        "Pre-screened", "In selection", "In certification", "Certified", "Matched", "Purchased",
        "Not selected"]),
    "localtie": ("Local tie", [
        "Lived in the area at least 1 year", "Worked for a local employer at least 1 year", "Other"]),
    "fthbexception": ("First-time buyer exception", [
        "a) Single parent, home owned only with a former spouse",
        "b) Displaced homemaker, home owned only with a spouse",
        "c) Home not on a permanent foundation",
        "d) Home found uninhabitable",
        "None of these apply"]),
    "homesize": ("Home size", [
        "Studio", "1 bedroom", "2 bedrooms", "3 bedrooms", "4+ bedrooms"]),
    "creditrange": ("Credit score range", [
        "300 - 579", "580 - 669", "670 - 739", "740 - 799", "800 - 850", "I don't know"]),
    "hbeducation": ("Homebuyer education", [
        "Completed", "Scheduled", "Not yet"]),
    "preapproval": ("Lender pre-approval", [
        "Yes, I have a pre-approval letter", "I am working with a lender", "Not yet"]),
    "incomestatus": ("Income status", [
        "This income is ongoing", "This income has ended or will end"]),
    "payfrequency": ("Pay frequency", [
        "Weekly", "Bi-weekly", "Semi-monthly", "Monthly", "Annually"]),
    "reviewstatus": ("Review status", [
        "Not reviewed", "Accepted", "Adjusted", "Excluded"]),
    "occupancyrole": ("Occupancy role", [
        "Owner", "Tenant"]),
    "occupancystatus": ("Occupancy status", [
        "Pending", "Current", "Past"]),
    "verificationstatus": ("Verification status", [
        "Due", "Sent", "Received", "Approved", "Issue found", "Waived", "Cancelled"]),
    "verificationmethod": ("Verification method", [
        "Online form", "Paper", "Insurer's card"]),
    "rentalstatus": ("Rental status", [
        "Not renting", "Renting ADU", "Renting rooms", "Renting whole home"]),
    "loanstatus": ("Loan status", [
        "Active", "Paid off"]),
    "insurancereviewstatus": ("Insurance verification status", [
        "To review", "Needs contact", "Approved", "Issue found", "Cancelled", "Requested"]),
    "followupstatus": ("Follow-up status", [
        "Open", "Done"]),
    "aftersaleaction": ("After-sale task: what it does", [
        "Tick it off", "Enter the insurance", "Add the settlement statement", "Open the new occupancy", "Open the documents folder",
        "Open the property", "Open Stu in the wild"]),
    "aftersaleapplies": ("After-sale task: which sales", [
        "Every sale", "Resales only", "First sales only"]),
    "saletaskstatus": ("Sale task status", [
        "To do", "Done", "Not needed"]),
    "purchasefundingtype": ("Purchase funding type", [
        "Buyer cash", "Loan", "Subsidy", "Other"]),
    "walkbystatus": ("Walk-by status", [
        "Draft", "Submitted"]),
    "contactmethod": ("Contact method", [
        "Phone", "Email", "In person", "Text", "Mail", "Other"]),
    "requesttype": ("Request type", [
        "Capital improvement", "ERRR repair draw", "Refinance", "Rent or sublet",
        "Leave of absence", "Intent to sell", "Transfer to heir or family", "Other"]),
    "requeststatus": ("Request status", [
        "Submitted", "Under review", "Approved", "Approved with conditions", "Denied",
        "Withdrawn", "Completed"]),
    "saletype": ("Sale type", [
        "Initial sale", "Resale", "Transfer to heir or family", "CLT buyback", "Other"]),
    "salestatus": ("Sale status", [
        "Pending", "Closed", "Cancelled"]),
    "feetype": ("Fee type", [
        "Ground lease fee", "ERRR", "Other"]),
    "listname": ("List", [
        "County", "Property type", "Tenure type", "Relationship", "Income type", "Debt type",
        "Asset type", "Housing status", "Document type", "State", "Funder", "Neighborhood"]),
    "formtype": ("Form type", [
        "Screener", "Full application", "Annual verification", "Insurance update", "Homeowner request", "Other"]),
    "submissionstatus": ("Submission status", [
        "Received", "Processed", "Needs attention", "Ignored"]),
    "errrtype": ("ERRR transaction type", [
        "Opening balance", "Contribution", "Returned contribution", "Repair draw",
        "Adjustment increase", "Adjustment decrease"]),
    # --- v0.5: funding, projects, selection, certification (docs/plans/v0.5-plan.md) ---
    "limitsource": ("AMI limit source", ["HUD", "Other"]),
    "rulechoice": ("Eligibility requirement", ["Required", "Not required"]),
    "projecttype": ("Project type", ["New construction sale", "Resale", "Rental lease-up"]),
    "projectstatus": ("Project status", [
        "Planning", "Accepting applications", "Selection", "Certifying", "Matching", "Closed"]),
    "selectionmethod": ("Selection method", ["Lottery", "First come first served"]),
    "listsource": ("Buyer list", ["Own selection", "Reuse a recent list"]),
    "projecthomestatus": ("Project home status", ["Available", "Matched", "Sold"]),
    "roundstatus": ("Selection round status", ["Open", "Pools locked", "Drawn", "Certified", "Closed"]),
    "entrystatus": ("List status", [
        "Waitlist", "Invited", "Application received", "Approved", "Offered", "Accepted", "Declined",
        "Unresponsive", "Ineligible", "Removed", "Withdrawn"]),
    "prescreenresult": ("Pre-screen result", ["Eligible for selection", "Not eligible", "Needs review"]),
    "certificationstatus": ("Certification status", [
        "Reviewing", "Waiting for more information", "Certified", "Not certified", "Expired"]),
    "checkstage": ("Check stage", ["Pre-screen", "Certification"]),
    "checktest": ("Check", [
        "Income limit", "Minimum income", "First-time buyer", "Housing ratio", "Total debt ratio", "Asset limit",
        "Credit", "Bankruptcy", "Household size fits", "Homebuyer education", "Primary residence", "Local tie"]),
    "checkresult": ("Check result", ["Pass", "Fail", "Not applicable", "Needs review"]),
    "documentstatus": ("Document status", ["Missing", "Received", "Accepted", "Rejected", "Expired", "Waived"]),
    "noticetype": ("Notice type", [
        "Screened out", "Not selected", "Invited to full application", "Reminder", "Offer", "Other", "Annual verification", "Insurance verification"]),
    "noticechannel": ("Sent by", ["Email", "Letter", "Phone", "Text message"]),
}


# ---------------------------------------------------------------------------
# Column helpers. Each returns a dict the build turns into Dataverse metadata.
#   text/email/phone/url: single line of text
#   memo: multiple lines of text
#   int: whole number, dec: decimal, money: currency, date: date only
#   bool: yes/no, choice: global choice, multi: multi-select global choice
# ---------------------------------------------------------------------------
def col(name, kind, label, desc="", **kw):
    return {"name": name, "kind": kind, "label": label, "desc": desc, **kw}

def text(n, l, d="", max=200, **k):  return col(n, "text", l, d, max=max, **k)
def email(n, l, d="", **k):          return col(n, "email", l, d, max=100, **k)
def phone(n, l, d="", **k):          return col(n, "phone", l, d, max=50, **k)
def url(n, l, d="", **k):            return col(n, "url", l, d, max=500, **k)
def memo(n, l, d="", max=4000, **k): return col(n, "memo", l, d, max=max, **k)
def int_(n, l, d="", **k):           return col(n, "int", l, d, **k)
def dec(n, l, d="", precision=2, **k): return col(n, "dec", l, d, precision=precision, **k)
def money(n, l, d="", **k):          return col(n, "money", l, d, **k)
def date(n, l, d="", **k):           return col(n, "date", l, d, **k)
def datetime_(n, l, d="", **k): return col(n, "datetime", l, d, **k)
def bool_(n, l, d="", default=False, **k): return col(n, "bool", l, d, default=default, **k)
def choice(n, l, choiceset, d="", default=None, **k):
    return col(n, "choice", l, d, choice=choiceset, default=default, **k)
def multi(n, l, choiceset, d="", **k): return col(n, "multi", l, d, choice=choiceset, **k)
def file(n, l, d="", max_kb=131072, **k): return col(n, "file", l, d, max_kb=max_kb, **k)
def fx(n, l, result, formula, d="", precision=2, **k):
    """Formula column (Power Fx), created by build_schema.py. result: dec, int, text or bool.
    Write the formula with internal names (clt_statedannualincome, clt_amilimits.clt_size4). Dataverse rules:
    Decimal() of a blank money column is 0, so test money as Decimal(x) = 0, never IsBlank(Decimal(x));
    every money column inside Decimal(...), even in IsBlank; a choice as [@'Choice display name'].'Label' (plain
    'Name'.'Label' fails when a column has the same display name); at most 1,000 characters. A changed formula is
    updated on the next build."""
    return col(n, "fx", l, d, result=result, formula=" ".join(formula.split()), precision=precision,
               **{"max": 200, **k})
def autonum(n, l, fmt, d="", **k):
    """Text column Dataverse fills on create, e.g. fmt "P-{SEQNUM:5}" gives P-00001. Numbering starts at 1."""
    return col(n, "autonumber", l, d, max=20, format=fmt, **k)

def address(prefix, label_prefix):
    """Street, unit, city and ZIP. State is a lookup to the State list (see LOOKUPS)."""
    p, L = prefix, label_prefix
    return [
        text(f"{p}street", f"{L}Street address"),
        text(f"{p}unit", f"{L}Unit", max=50),
        text(f"{p}city", f"{L}City", max=100),
        text(f"{p}zip", f"{L}ZIP code", max=20),
    ]


# ---------------------------------------------------------------------------
# Tables. "name" is the logical name without the prefix.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Formulas for formula columns (fx), built by build_schema.py. Internal names; money wrapped in Decimal();
# choices compared as 'Choice display name'.'Label'.
# ---------------------------------------------------------------------------
# % of AMI: 100% AMI = 2 x the 50% limit, so % = income x 50 / limit. Over 8 people: HUD's rule.
# Two columns, because a formula can be at most 1,000 characters: the household size's 50% limit, then the %.
_SIZE = "(clt_adults + clt_children)"
_LIMIT50 = ("Switch(" + _SIZE + ", "
            + ", ".join(f"{n}, clt_amilimits.clt_size{n}" for n in range(1, 9))
            + f", clt_amilimits.clt_size4 * (1.32 + 0.08 * ({_SIZE} - 8)))")
LIMIT50_FOR_SIZE = f"If(IsBlank(clt_amilimits) || {_SIZE} < 1, Blank(), {_LIMIT50})"
AMI_PCT = ("If(Decimal(clt_statedannualincome) = 0 || IsBlank(clt_limit50forsize) || clt_limit50forsize = 0, "
           "Blank(), Round(Decimal(clt_statedannualincome) * 50 / clt_limit50forsize, 0))")

# Screener answers against the organization's eligibility rules (Application, over "Eligibility rules used").
# Housing ratios need a home's monthly cost, so they're checked at pre-screen, not here.
_E = "clt_eligibilityrules"
ELIGIBILITY_FAILS = (
    "Concatenate("
    f"If({_E}.clt_maxami > 0 && !IsBlank(clt_amipct) && clt_amipct > {_E}.clt_maxami, "
    f"Concatenate(\"Over the max AMI (\", Text(clt_amipct, \"0\"), \"% vs \", Text({_E}.clt_maxami, \"0\"), \"%). \"), \"\"), "
    f"If({_E}.clt_minami > 0 && !IsBlank(clt_amipct) && clt_amipct < {_E}.clt_minami, "
    f"Concatenate(\"Under the min AMI (\", Text(clt_amipct, \"0\"), \"% vs \", Text({_E}.clt_minami, \"0\"), \"%). \"), \"\"), "
    f"If({_E}.clt_requiresftb && clt_firsttimebuyer = false, \"Not a first-time buyer (check exceptions). \", \"\"), "
    f"If({_E}.clt_requireslocal && clt_localtie = false, \"No local tie. \", \"\"), "
    f"If({_E}.clt_assetlimitwhole > 0 && Decimal(clt_statednonretirementassets) <> 0 && "
    f"Decimal(clt_statednonretirementassets) > {_E}.clt_assetlimitwhole, \"Assets over the limit. \", \"\"))")
ELIGIBILITY_GAPS = (
    "Concatenate("
    "If(IsBlank(clt_amipct), \"No % of AMI (county, household size or income missing). \", \"\"), "
    f"If({_E}.clt_requiresftb && IsBlank(clt_firsttimebuyer), \"First-time buyer not answered. \", \"\"), "
    f"If({_E}.clt_requireslocal && IsBlank(clt_localtie), \"Local tie not answered. \", \"\"))")
ORG_ELIGIBILITY = (
    f"If(IsBlank({_E}), \"No eligibility rules linked\", "
    "If(Len(clt_eligibilityfails) > 0, Concatenate(\"Not eligible: \", clt_eligibilityfails), "
    "If(Len(clt_eligibilitygaps) > 0, Concatenate(\"Needs review: \", clt_eligibilitygaps), \"Eligible\")))")

_END = "If(IsBlank(clt_enddate), UTCToday(), clt_enddate)"
_YEARS = f"DateDiff(clt_basedate, {_END}, TimeUnit.Days) / 365"
# Resale price before floor, cap and rounding (docs/DESIGN.md, Resale formulas). Valued at the occupancy's end
# date, or today while it's current.
RAW_FORMULA_PRICE = (
    "If(IsBlank(clt_resaleformula) || Decimal(clt_baseprice) = 0, Blank(), "
    "If(clt_resaleformula = [@'Resale formula'].'Fixed annual rate', "
    f"If(IsBlank(clt_basedate), Blank(), Decimal(clt_baseprice) * Decimal(Power(1 + If(IsBlank(clt_annualrate), 0, clt_annualrate) / 100, "
    f"If(clt_wholeyearsonly, RoundDown({_YEARS}, 0), {_YEARS})))), "
    "If(Decimal(clt_appraisalatpurchase) = 0 || Decimal(clt_latestappraisal) = 0, Blank(), "
    "Decimal(clt_baseprice) + (Decimal(clt_latestappraisal) - Decimal(clt_appraisalatpurchase)) "
    "* (Decimal(clt_baseprice) / Decimal(clt_appraisalatpurchase)) * If(IsBlank(clt_ownershare), 0, clt_ownershare) / 100)))")
_FLOORED = "If(clt_floorbaseprice, Max(clt_rawformulaprice, Decimal(clt_baseprice)), clt_rawformulaprice)"
_CAPPED = f"If(Decimal(clt_pricecap) = 0, {_FLOORED}, Min({_FLOORED}, Decimal(clt_pricecap)))"
FORMULA_PRICE = (f"If(IsBlank(clt_rawformulaprice), Blank(), If(IsBlank(clt_roundto) || clt_roundto = 0, {_CAPPED}, "
                 f"Round({_CAPPED} / clt_roundto, 0) * clt_roundto))")
# An improvement credit falls evenly from its original value to zero over its depreciation period (straight line, by the day).
IMPROVEMENT_VALUE = ("If(IsBlank(clt_valuedate) || IsBlank(clt_depreciationyears) || clt_depreciationyears <= 0, Decimal(clt_originalvalue), "
                     "Decimal(clt_originalvalue) * Max(0, Min(1, 1 - DateDiff(clt_valuedate, UTCToday(), TimeUnit.Days) / (clt_depreciationyears * 365.25))))")
MAX_RESALE_PRICE = ("If(IsBlank(clt_formulaprice), Blank(), clt_formulaprice + "
                    "Decimal(clt_improvementcredits))")
_DWELLING = "Decimal(clt_coveragea) * (1 + If(IsBlank(clt_extendeddwelling), 0, clt_extendeddwelling) / 100)"
_PAY = ", ".join(f"[@'Pay frequency'].'{k}', {v}" for k, v in
                 [("Weekly", 52), ("Bi-weekly", 26), ("Semi-monthly", 24), ("Monthly", 12), ("Annually", 1)])
_MINUS = " || ".join(f"clt_type = [@'ERRR transaction type'].'{t}'" for t in
                     ("Returned contribution", "Repair draw", "Adjustment decrease"))


TABLES = [
    # 1 -------------------------------------------------------------------
    dict(name="property", label="Property", plural="Properties", notes=True,
         primary_required=False,  # name is filled by the form script (webresources/names.js)
         documents="Property Documents",  # SharePoint library title; see build_schema.ensure_sharepoint
         desc="A home or lot in the CLT portfolio.",
         primary=("Property name", "Short name, usually the street address"),
         columns=[
             autonum("recordnumber", "Record number", "P-{SEQNUM:5}", "Assigned when the record is created"),
             *address("", ""),
             text("apn", "Parcel number", "Assessor's parcel number (APN)", max=50),
             choice("status", "Status", "propertystatus"),
             int_("bedrooms", "Bedrooms"),
             dec("bathrooms", "Bathrooms", precision=1),
             int_("squarefeet", "Square feet"),
             int_("yearbuilt", "Year built"),
             dec("amitarget", "AMI target (%)", "Income target for buyers, for example 80 for 80% AMI", precision=0),
             date("acquisitiondate", "Acquisition date"),
             money("replacementcost", "Replacement cost", "Estimated cost to rebuild. Copied to insurance policies for the coverage check."),
             date("replacementcostdate", "Replacement cost as of"),
             date("lastwalkby", "Last staff walk-by", "When staff last walked or drove by the home. Set when a walk-by is submitted on the Stu in the wild page."),
             url("documentsfolder", "Documents folder", "Opens this record's folder in SharePoint. Filled in by the folder flow."),
             memo("notes", "Notes"),
         ]),

    # 2 -------------------------------------------------------------------
    dict(name="household", label="Household", plural="Households", notes=True,
         primary_required=False,  # name is filled by the form script (webresources/names.js)
         documents="Household Documents",  # restricted library: eligibility packet, income certs, closing/loan docs
         desc="A household that applies for, buys, or lives in a CLT home.",
         primary=("Household name", "For example: Rivera household"),
         columns=[
             autonum("recordnumber", "Record number", "H-{SEQNUM:5}", "Assigned when the record is created"),
             choice("status", "Status", "householdstatus", default="Applicant"),
             email("primaryemail", "Primary email", "Used to match form submissions to this household"),
             phone("phone", "Phone"),
             *address("mailing", "Mailing "),
             text("preferredlanguage", "Preferred language", max=50),
             date("certificationdate", "Income certification date"),
             date("certificationexpires", "Certification expires"),
             int_("certifiedhouseholdsize", "Certified household size"),
             money("certifiedincome", "Certified annual income"),
             dec("certifiedamipercent", "Certified income (% of AMI)", precision=1),
             url("documentsfolder", "Documents folder", "Opens this record's folder in SharePoint. Filled in by the folder flow."),
             memo("notes", "Notes"),
         ]),

    # 3 -------------------------------------------------------------------
    dict(name="householdmember", label="Household member", plural="Household members",
         desc="A person in a household.",
         primary=("Full name", ""),
         columns=[
             text("firstname", "First name", max=100),
             text("lastname", "Last name", max=100),
             choice("applicantrole", "Applicant role", "applicantrole", default="Other household member"),
             text("relationshipother", "Relationship (other)", "What the applicant typed when they chose Other"),
             date("dateofbirth", "Date of birth"),
             fx("age", "Age", "int", "If(IsBlank(clt_dateofbirth), Blank(), RoundDown(DateDiff(clt_dateofbirth, UTCToday(), TimeUnit.Days) / 365.25, 0))"),
             fx("isadult", "Is adult", "bool", "!IsBlank(clt_dateofbirth) && DateDiff(clt_dateofbirth, UTCToday(), TimeUnit.Days) / 365.25 >= 18"),
             email("email", "Email"),
             phone("phone", "Phone"),
             bool_("ontitle", "On title"),
             text("formitemid", "Form item ID", "Set by the intake flows. Do not edit.", max=100),
         ]),

    # 4 -------------------------------------------------------------------
    dict(name="application", audit=True, solution="intake", label="Application", plural="Applications", notes=True,
         desc="A household's screener and full application, with staff review.",
         primary=("Application", "For example: Rivera, Maple Court 2026"),
         columns=[
             autonum("recordnumber", "Record number", "A-{SEQNUM:5}", "Assigned when the record is created"),
             choice("stage", "Stage", "applicationstage", default="Screener submitted"),
             # v0.5 selection
             text("uniqueid", "Unique ID", "ID-0001: assigned in submission order when the window closes", max=20),
             datetime_("firstsubmittedon", "First submitted",
                       "First screener submission. Ranks rolling first come first served lists; never changes."),
             datetime_("answersfrozenon", "Screener answers frozen",
                       "Set when Unique IDs are assigned. Later edits are kept as a note, not applied."),
             choice("prescreenresult", "Pre-screen result", "prescreenresult"),
             memo("prescreennotes", "Pre-screen notes", "Why, including any staff override (who, when, reason)"),
             multi("prescreensizes", "Home sizes eligible for", "homesize",
                   "Set by the pre-screen: the sizes they asked for that fit the household and pass the ratios. "
                   "The lottery lists are built from this."),
             datetime_("prescreenedon", "Pre-screened on", "When the pre-screen last saved a result"),
             bool_("prescreenoverridden", "Pre-screen overridden",
                   "Tick when staff change the result by hand, and say who, when and why in the notes. "
                   "The pre-screen then leaves this application alone."),
             text("program", "Program or project", "For example: Maple Court"),
             # Screener
             text("screenerentryid", "Screener entry ID", "Forms platform entry ID. Set by the intake flows.", max=50),
             date("screenersubmitted", "Screener submitted"),
             url("screenerlink", "Screener entry link"),
             url("invitelink", "Invite link", "This household's own link to the full application. Filled in when they are invited."),
             bool_("localtie", "Lived or worked locally 1+ year"),
             choice("localtiemethod", "How local tie is shown", "localtie"),
             text("housingstatusother", "Current housing status (other)"),
             bool_("firsttimebuyer", "First-time homebuyer"),
             multi("fthbexceptions", "First-time buyer exception", "fthbexception"),
             bool_("ownsproperty", "Currently owns residential property"),
             int_("adults", "Adults (18+)"),
             int_("children", "Children"),
             text("householdcountsasentered", "Household counts as entered",
                  "Filled when the form answer was not a number"),
             multi("homesizes", "Home sizes of interest", "homesize"),
             money("statedannualincome", "Stated combined annual income"),
             fx("limit50forsize", "50% limit for household size", "dec", LIMIT50_FOR_SIZE,
                "From AMI limits used, for adults plus children. Over 8 people: HUD's rule"),
             fx("amipct", "Stated income (% of AMI)", "int", AMI_PCT,
                "Stated income / (2 x the 50% limit for adults plus children) on AMI limits used. Over 8 people: HUD's rule"),
             fx("householdsize", "Household size (stated)", "int",
                "If(IsBlank(clt_adults) && IsBlank(clt_children), Blank(), clt_adults + clt_children)", "Adults plus children"),
             # Organization eligibility from the screener answers (formulas above TABLES). Ratios come at pre-screen.
             fx("eligibilityfails", "Eligibility: rules not met", "text", ELIGIBILITY_FAILS, max=500),
             fx("eligibilitygaps", "Eligibility: missing answers", "text", ELIGIBILITY_GAPS, max=500),
             fx("orgeligibility", "Organization eligibility", "text", ORG_ELIGIBILITY,
                "Screener answers against the organization's rules: % of AMI, first-time buyer, local tie, assets. "
                "Housing ratios are checked at pre-screen, once there's a home and a price.", max=600),
             fx("iseligible", "Is eligible", "bool", 'clt_orgeligibility = "Eligible"',
                "Yes when Organization eligibility says Eligible. Doesn't include the housing ratios."),
             bool_("incomepastyear", "Has had income for the past year"),
             bool_("age62", "Applicant or co-applicant 62+"),
             money("statednonretirementassets", "Stated non-retirement assets"),
             money("statedretirementassets", "Stated retirement assets"),
             bool_("has1000forclosing", "Has $1,000 for closing"),
             money("statedmonthlydebt", "Stated monthly debt payments"),
             choice("creditrange", "Credit score range", "creditrange"),
             bool_("bankruptcy3yrs", "Bankruptcy in past 3 years"),
             bool_("primaryresidence", "Will use as primary residence"),
             choice("hbeducation", "Homebuyer education", "hbeducation"),
             choice("preapproval", "Lender pre-approval", "preapproval"),
             memo("accommodation", "Accommodation request"),
             memo("applicantquestions", "Applicant questions or comments"),
             # Full application
             text("fullappentryid", "Full application entry ID", "Forms platform entry ID. Set by the intake flows.", max=50),
             date("fullappsubmitted", "Full application submitted"),
             url("fullapplink", "Full application entry link"),
             bool_("expectsincomechange", "Expects income change in 12 months"),
             bool_("adultwithnoincome", "Adult in household with no income"),
             bool_("latepayments", "Late payments in past 12 months"),
             memo("latepaymentsexplanation", "Late payments explanation"),
             memo("bankruptcyexplanation", "Bankruptcy explanation"),
             bool_("giftfunds", "Receiving gift funds for purchase"),
             money("giftamount", "Gift amount"),
             text("giftgiver", "Gift giver and relationship"),
             memo("incomechangedetails", "Expected income change"),
             memo("noincomedetails", "Adults with no income", "Who, and how their living expenses are covered"),
             memo("creditexplanation", "Credit report explanation"),
             money("currenthousingcost", "Current monthly rent or mortgage"),
             memo("residencydetails", "Residency (full application)",
                  "County, and how a year of local residence or work is shown, for the applicant and co-applicant"),
             bool_("ownedhome3yrs", "Owned a home in the past 3 years"),
             bool_("fthbcertified", "Signed the first-time buyer statement"),
             text("lender", "Lender and loan officer"),
             email("loanofficeremail", "Loan officer email"),
             phone("loanofficerphone", "Loan officer phone"),
             text("hbeducationdetails", "Homebuyer education (full application)",
                  "Completed or scheduled, with the course provider and date"),
             memo("fullappcomments", "Anything else (full application)"),
             # Staff review
             money("ami100", "100% AMI for household size", "Area median income for this household size. Entered by staff."),
             date("decisiondate", "Decision date"),
             memo("reviewnotes", "Review notes"),
         ]),

    # 5 -------------------------------------------------------------------
    dict(name="incomesource", solution="intake", label="Income source", plural="Income sources",
         desc="One source of income for a household member, from the full application.",
         primary=("Income source", "For example: Rivera, Jefferson Healthcare"),
         columns=[
             text("memberasentered", "Household member as entered"),
             text("incometypeother", "Income type (other)"),
             text("payer", "Employer or payer"),
             text("jobtitle", "Job title or occupation"),
             date("startdate", "Hire or start date"),
             choice("incomestatus", "Income status", "incomestatus"),
             date("enddate", "End date"),
             choice("payfrequency", "Pay frequency", "payfrequency"),
             money("grosspayperperiod", "Average gross pay per period"),
             dec("hoursperperiod", "Average hours per period"),
             money("annualbonus", "Annual bonus"),
             money("annualovertime", "Annual overtime or differential pay"),
             fx("annualizedincome", "Annualized income", "dec",
                "Decimal(clt_grosspayperperiod) * Switch(clt_payfrequency, " + _PAY + ", 0)"
                " + Decimal(clt_annualbonus) + Decimal(clt_annualovertime)"),
             date("paystubenddate", "Most recent pay stub period end"),
             money("ytdgross", "Year-to-date gross income"),
             memo("applicantnotes", "Applicant notes"),
             choice("reviewstatus", "Review status", "reviewstatus", default="Not reviewed"),
             text("excludedreason", "Adjusted or excluded because"),
             money("verifiedannualamount", "Verified annual amount", "Entered by staff. Rolls up to the application."),
             memo("reviewnotes", "Review notes"),
             text("formitemid", "Form item ID", "Set by the intake flows. Do not edit.", max=100),
         ]),

    # 6 -------------------------------------------------------------------
    dict(name="debt", solution="intake", label="Debt", plural="Debts",
         desc="A monthly debt payment for a household member, from the full application.",
         primary=("Debt", ""),
         columns=[
             text("memberasentered", "Household member as entered"),
             text("debttypeother", "Debt type (other)"),
             text("creditor", "Lender or creditor"),
             money("monthlypayment", "Monthly payment"),
             money("remainingbalance", "Remaining balance"),
             memo("description", "Description"),
             choice("reviewstatus", "Review status", "reviewstatus", default="Not reviewed"),
             text("excludedreason", "Adjusted or excluded because"),
             money("verifiedmonthlypayment", "Verified monthly payment"),
             text("formitemid", "Form item ID", "Set by the intake flows. Do not edit.", max=100),
         ]),

    # 7 -------------------------------------------------------------------
    dict(name="asset", solution="intake", label="Asset", plural="Assets",
         desc="An account or asset, from the full application.",
         primary=("Asset", ""),
         columns=[
             text("holderasentered", "Account holder as entered"),
             text("assettypeother", "Asset type (other)"),
             text("institution", "Institution"),
             memo("description", "Description"),
             money("currentvalue", "Current balance or value"),
             choice("reviewstatus", "Review status", "reviewstatus", default="Not reviewed"),
             text("excludedreason", "Adjusted or excluded because"),
             money("verifiedvalue", "Verified value"),
             text("formitemid", "Form item ID", "Set by the intake flows. Do not edit.", max=100),
         ]),

    # 8 -------------------------------------------------------------------
    dict(name="occupancy", label="Occupancy", plural="Occupancies", notes=True,
         primary_required=False,  # name is filled by the form script (webresources/names.js)
         documents="Occupancy Documents",  # ground lease, closing papers, ERRR requests for this household's time in this home
         desc="Links a household to a property for a period of time, with its resale formula terms.",
         primary=("Occupancy", "For example: Rivera at 12 Pine St"),
         columns=[
             autonum("recordnumber", "Record number", "O-{SEQNUM:5}", "Assigned when the record is created"),
             choice("role", "Role", "occupancyrole", default="Owner"),
             choice("status", "Status", "occupancystatus", default="Current"),
             date("startdate", "Start date", "Closing or move-in date. Annual verifications fall on this anniversary."),
             date("enddate", "End date"),
             text("recordingnumber", "Lease or covenant recording number", max=100),
             text("agreementversion", "Agreement version", "Which lease or covenant template this household signed", max=100),
             # Resale formula inputs
             choice("resaleformula", "Resale formula", "resaleformula"),
             money("baseprice", "Base price", "Purchase price the formula starts from"),
             date("basedate", "Base date", "Purchase date the formula starts from"),
             dec("annualrate", "Annual rate (%)", "Fixed rate formulas, for example 1.5", precision=3),
             bool_("wholeyearsonly", "Count whole years only"),
             money("appraisalatpurchase", "Appraisal at purchase", "Appraisal share formulas"),
             money("latestappraisal", "Latest appraisal"),
             date("latestappraisaldate", "Latest appraisal date"),
             dec("ownershare", "Owner share (%)", "Appraisal share formulas, for example 25", precision=2),
             bool_("floorbaseprice", "Floor at purchase price"),
             money("pricecap", "Price cap"),
             int_("roundto", "Round to nearest ($)", "For example 100. Leave blank for no rounding."),
             money("improvementcredits", "Improvement credits", "The current value of this occupancy's improvement credits, added together. Kept in step with the "
                   "Improvement credits list by the Verification hub and Resale pages; type it only when the list is empty."),
             fx("rawformulaprice", "Raw formula price", "dec", RAW_FORMULA_PRICE, "The resale formula before floor, cap and rounding"),
             fx("formulaprice", "Formula price", "dec", FORMULA_PRICE, "After the floor, price cap and rounding"),
             fx("maximumresaleprice", "Maximum resale price", "dec", MAX_RESALE_PRICE, "Formula price plus improvement credits"),
             url("documentsfolder", "Documents folder", "Opens this record's folder in SharePoint. Filled in by the folder flow."),
             # Verification hub: when each recurring check was last done. Type them, or let the Verification hub
             # page keep them in step with the records (verifications, policies, walk-bys, relationship notes).
             date("lastoccupancyverified", "Last occupancy verification", "When this household was last confirmed to live in the home. Blank counts as overdue."),
             date("lastinsuranceverified", "Last insurance verification", "When this home's insurance was last checked. Blank counts as overdue."),
             date("lastcontact", "Last contact", "The newest relationship note, or verification that came back."),
             memo("notes", "Notes"),
         ]),

    # 9 -------------------------------------------------------------------
    dict(name="annualverification", label="Annual verification", plural="Annual verifications",
         desc="Yearly owner-occupancy verification.",
         primary=("Verification", "For example: 2026, 12 Pine St"),
         columns=[
             int_("year", "Year"),
             date("duedate", "Due date"),
             choice("status", "Status", "verificationstatus", default="Due"),
             choice("method", "How", "verificationmethod", "An online form the household fills in, or a paper copy staff close by hand"),
             date("sentdate", "Sent date"),
             date("receiveddate", "Received date"),
             bool_("primaryresidence", "Primary residence confirmed"),
             choice("rentalstatus", "Rental status", "rentalstatus", default="Not renting"),
             memo("tenantdetails", "Tenant details", "Tenant household size, income and rent, if renting"),
             int_("peopleinhome", "People living in the home", "From the online form"),
             bool_("noshorttermrental", "No short-term rental certified", "The household certified it does not use the home as a short-term rental"),
             bool_("mortgagecontact", "Asked for contact about the mortgage", "The household asked staff to get in touch about difficulty with its mortgage"),
             date("signeddate", "Signed on"),
             phone("phone", "Phone on the form"),
             text("verificationcode", "Verification code", "Unique code sent in the form link so the reply matches this record. Set by a flow.", max=20),
             email("sentto", "Sent to"),
             text("formentryid", "Form entry ID", "Forms platform entry ID. Set by the intake flow.", max=100),
             url("formlink", "Form entry link"),
             memo("sentlink", "Link sent", "The household's own link to the online form, as it was sent. Set by the Occupancy verification page.", max=4000),
             file("signedform", "Signed form", "The signed paper verification, as a PDF or a photo. Added on the Occupancy verification page."),
             memo("notes", "Notes"),
         ]),

    # 10 ------------------------------------------------------------------
    dict(name="insurancepolicy", label="Insurance policy", plural="Insurance policies",
         desc="A homeowner's insurance policy term.",
         primary=("Policy", "For example: State Farm 2026-27"),
         columns=[
             text("carrier", "Carrier"),
             text("policynumber", "Policy number", max=100),
             money("coveragea", "Dwelling coverage (A)"),
             dec("extendeddwelling", "Extended dwelling (%)", "For example 25 for 25% extended replacement cost", precision=0),
             money("liability", "Liability coverage"),
             money("deductible", "Deductible"),
             money("premium", "Annual premium"),
             date("effectivedate", "Effective date"),
             date("renewaldate", "Renewal date"),
             bool_("cltadditionalinsured", "CLT listed as additional insured"),
             date("verifieddate", "Verified date"),
             money("replacementcost", "Replacement cost", "Copied from the property by a flow"),
             fx("totaldwellingcoverage", "Total dwelling coverage", "dec",
                f"If(Decimal(clt_coveragea) = 0, Blank(), {_DWELLING})", "Dwelling coverage plus any extended dwelling %"),
             # These three deliberately don't refer to each other, so Coverage check works in the Underinsured view.
             fx("coveragecheck", "Coverage check", "text",
                f"If(Decimal(clt_coveragea) = 0 || Decimal(clt_replacementcost) = 0, \"Not enough info\", "
                f"If({_DWELLING} >= Decimal(clt_replacementcost), \"Adequate\", \"Underinsured\"))"),
             fx("coveragegap", "Coverage gap", "dec",
                f"If(Decimal(clt_coveragea) = 0 || Decimal(clt_replacementcost) = 0, Blank(), Max(0, Decimal(clt_replacementcost) - {_DWELLING}))"),
             memo("notes", "Notes"),
         ]),

    dict(name="insuranceverification", label="Insurance verification", plural="Insurance verifications",
         primary_required=False,  # name is filled by the form script (webresources/names.js), the Insurance verification page or the intake flow
         desc="A check of a home's insurance coverage: the card the insurer mailed, or proof the household sent in for staff to review.",
         primary=("Insurance verification", "For example: 2026-11-17, Rivera - 12 Pine St"),
         columns=[
             date("date", "Started"),
             choice("status", "Status", "insurancereviewstatus", "Requested: the household has been asked for proof. To review: proof is waiting for staff. "
                    "Needs contact: the household asked for help, or sent no proof.", default="To review"),
             choice("method", "How", "verificationmethod", "An online form the household fills in, a paper copy staff close by hand, or the card the insurer mails"),
             date("duedate", "Due date"),
             date("sentdate", "Sent date"),
             email("sentto", "Sent to"),
             memo("sentlink", "Link sent", "The household's own link to the online form, as it was sent. Set by the Insurance verification page.", max=4000),
             text("verificationcode", "Verification code", "Unique code sent in the form link so the reply matches this record.", max=20),
             bool_("contactrequested", "Asked to be contacted"),
             file("document", "Insurance document", "Proof of insurance added by staff on the Insurance verification page."),
             date("verifieddate", "Reviewed on"),
             money("replacementcoverage", "Replacement coverage limit", "The dwelling replacement coverage shown on the proof of insurance"),
             memo("notes", "Notes"),
         ]),
    dict(name="followup", label="Follow-up", plural="Follow-ups",
         desc="Something staff need to come back to, with the date it is due: for a home (its property), for the household in it "
              "(its occupancy), or both.",
         primary=("Follow-up", "What to follow up on, for example: Call about the fence"),
         columns=[
             date("duedate", "Due date"),
             choice("status", "Status", "followupstatus", default="Open"),
             date("donedate", "Done on"),
             memo("notes", "Notes"),
         ]),
    dict(name="improvementcredit", label="Improvement credit", plural="Improvement credits",
         desc="A capital improvement that adds to a home's maximum resale price, with the value it was given, the date of that value and "
              "how many years it loses value over.",
         primary=("Improvement", "For example: New roof"),
         columns=[
             money("originalvalue", "Original value", "The credit approved for this improvement"),
             date("valuedate", "Value as of", "The date the original value is from. The credit loses value from this date."),
             dec("depreciationyears", "Depreciation period (years)", "Years over which the credit falls evenly to zero. Leave blank for a credit that keeps its value.", precision=1),
             fx("currentvalue", "Current value", "dec", IMPROVEMENT_VALUE, "The original value less what it has lost so far"),
             memo("notes", "Notes"),
         ]),
    dict(name="walkby", label="Staff walk-by", plural="Staff walk-bys",
         primary_required=False,  # name is filled by the form script (webresources/names.js) or the Stu in the wild page
         desc="A staff visit to look at a home from the outside, with what they saw. It belongs to the property, so an empty "
              "home can have one; the occupancy at the time is linked too when there is one.",
         primary=("Walk-by", "For example: 2026-11-17, 12 Pine St"),
         columns=[
             date("date", "Date"),
             choice("status", "Status", "walkbystatus", "Draft: saved on the Stu in the wild page and not finished yet. Submitted: done; it counts "
                    "as the home's last walk-by.", default="Submitted"),
             bool_("followupneeded", "Follow-up needed", "Submitting the walk-by adds an open follow-up for the home."),
             date("followupdue", "Follow-up due", "The due date for that follow-up. The day of the walk-by unless changed."),
             memo("notes", "Notes", "What you saw from the street: the yard, the outside of the home, anything to follow up."),
         ]),
    dict(name="walkbyphoto", label="Walk-by photo", plural="Walk-by photos",
         primary_required=False,  # name is filled by the Stu in the wild page
         desc="A photo taken on a staff walk-by. Added on the Stu in the wild page, which shrinks it first.",
         primary=("Photo", "For example: Photo 1"),
         columns=[
             file("photo", "Photo", "The picture, as a JPG.", max_kb=10240),
         ]),
    dict(name="relationshipnote", label="Relationship note", plural="Relationship notes",
         primary_required=False,  # name is filled by the form script (webresources/names.js) or the Verification hub page
         desc="A note staff add each time they are in contact with a household about its home.",
         primary=("Note", "For example: 2026-11-17, Rivera - 12 Pine St"),
         columns=[
             date("date", "Date"),
             choice("method", "How", "contactmethod"),
             memo("notes", "Notes", "Who you talked to and what about."),
         ]),

    dict(name="loan", label="Loan", plural="Loans",
         desc="A loan the organization made to a homeowner, tied to their time in a home. What is still owed comes off the seller's side at a resale.",
         primary=("Loan", "For example: Down payment loan"),
         columns=[
             choice("status", "Status", "loanstatus", default="Active"),
             money("startingbalance", "Starting balance"),
             dec("interestrate", "Interest rate (%)", "Yearly rate, for example 3. Leave blank or 0 for no interest.", precision=3),
             date("startdate", "Start date"),
             date("enddate", "End date", "When the last payment is due"),
             money("payment", "Regular payment", "Monthly. Filled in from the balance, rate and dates; change it if the real payment differs. "
                   "Leave it at 0 for a loan with no payments until the home is sold."),
             memo("notes", "Notes"),
         ]),

    # 11 ------------------------------------------------------------------
    dict(name="homeownerrequest", label="Homeowner request", plural="Homeowner requests", notes=True,
         desc="A request from a homeowner that needs CLT approval.",
         primary=("Request", "Short description, for example: Roof replacement"),
         columns=[
             autonum("recordnumber", "Record number", "R-{SEQNUM:5}", "Assigned when the record is created"),
             choice("requesttype", "Request type", "requesttype"),
             date("requestdate", "Request date"),
             choice("status", "Status", "requeststatus", default="Submitted"),
             memo("details", "Details"),
             date("decisiondate", "Decision date"),
             memo("conditions", "Conditions"),
             money("estimatedcost", "Estimated cost"),
             money("approvedcredit", "Approved resale credit", "Capital improvements only: amount added to the maximum resale price"),
             money("approveddraw", "Approved ERRR draw", "ERRR repair draws only"),
             date("completeddate", "Completed date"),
         ]),

    # 12 ------------------------------------------------------------------
    dict(name="sale", label="Sale", plural="Sales", notes=True,
         desc="An initial sale or resale of a CLT home.",
         primary=("Sale", "For example: 12 Pine St resale 2026"),
         columns=[
             autonum("recordnumber", "Record number", "S-{SEQNUM:5}", "Assigned when the record is created"),
             choice("saletype", "Sale type", "saletype", "Set automatically: Resale if the property has a current owner, otherwise Initial sale"),
             choice("status", "Status", "salestatus", default="Pending"),
             date("noticedate", "Notice of intent to sell", "Resales: the date the homeowner said they want to sell"),
             date("contractdate", "Purchase and sale agreement signed"),
             date("closingdate", "Closing date"),
             money("appraisedvalue", "Appraised value"),
             money("formulapriceatsale", "Formula price at sale", "Snapshot from the seller's occupancy"),
             money("creditsatsale", "Added value at sale", "Capital improvements that raise the price"),
             money("maxpriceatsale", "Maximum resale price at sale"),
             money("purchaseprice", "Purchase price"),
             money("subsidyrecapture", "Subsidy recaptured", "The purchase price above the maximum resale price, which goes back to the organization"),
             money("loanpayoff", "Loans owed to the organization", "What the seller still owes on loans from the organization, paid from the sale"),
             money("othercredits", "Other credits to the seller"),
             text("othercreditsnote", "Other credits: what for"),
             money("otherdebits", "Other debits"),
             text("otherdebitsnote", "Other debits: what for"),
             text("lender", "Lender"),
             text("titlecompany", "Title or escrow company"),
             money("closingcosts", "Closing costs", "The buyer's closing costs, from the final settlement statement"),
             file("settlementstatement", "Final settlement statement", "The final settlement statement, as a PDF or a photo. Added on the Resale page."),
             memo("notes", "Notes"),
         ]),
    dict(name="aftersaletask", label="After-sale task", plural="After-sale tasks",
         desc="The organization's own list of what has to happen after a sale closes. Each closed sale gets a copy of the tasks that "
              "apply to it, on the After the sale page. Change, add or deactivate tasks here; sales already set up keep their copy.",
         primary=("Task", "For example: Enter the buyer's insurance"),
         columns=[
             int_("order", "Order", "Tasks are listed lowest first"),
             choice("action", "What it does", "aftersaleaction", "Tick it off: staff mark it done. The others also do the work, or open "
                    "the place to do it, on the After the sale page.", default="Tick it off"),
             choice("appliesto", "Which sales", "aftersaleapplies", default="Every sale"),
             memo("details", "Details", "A line or two telling staff what to do", max=2000),
         ]),
    dict(name="saletask", label="Sale task", plural="Sale tasks",
         primary_required=False,  # copied from the After-sale tasks by the After the sale page
         desc="One after-sale task for one sale, with whether it is done.",
         primary=("Task", "For example: Enter the buyer's insurance"),
         columns=[
             int_("order", "Order"),
             choice("action", "What it does", "aftersaleaction", default="Tick it off"),
             memo("details", "Details", max=2000),
             choice("status", "Status", "saletaskstatus", default="To do"),
             date("donedate", "Done on"),
             memo("notes", "Notes", max=2000),
         ]),
    dict(name="salefunding", label="Purchase funding", plural="Purchase funding",
         primary_required=False,  # name is filled by the Resale page
         desc="One part of how a sale's purchase price is made up: the buyer's cash, a loan, a subsidy or something else.",
         primary=("Funding", "For example: Loan, first mortgage"),
         columns=[
             choice("type", "Type", "purchasefundingtype"),
             money("amount", "Amount"),
             dec("interestrate", "Interest rate (%)", "For a loan. 0 for a loan with no interest.", precision=3),
             text("notes", "Notes", "Who it is from, or what it is: the lender, the program, the gift giver", max=500),
         ]),

    # 13 ------------------------------------------------------------------
    dict(name="fee", label="Fee", plural="Fee schedule",
         desc="A monthly fee for a property, with effective dates. ERRR rows drive the monthly ERRR posting.",
         primary=("Fee", "For example: ERRR from Jan 2026"),
         columns=[
             choice("feetype", "Fee type", "feetype"),
             money("amount", "Monthly amount"),
             date("effectivestart", "Effective start"),
             date("effectiveend", "Effective end", "Blank means current"),
             memo("notes", "Notes"),
         ]),

    # 14 ------------------------------------------------------------------
    dict(name="errrtransaction", label="ERRR transaction", plural="ERRR transactions",
         desc="One entry in a property's ERRR (external repair and replacement reserve) ledger.",
         primary=("ERRR transaction", "For example: Contribution 2026-11"),
         columns=[
             date("date", "Date"),
             choice("type", "Type", "errrtype"),
             money("amount", "Amount", "Always enter as a positive number. The type sets the sign."),
             fx("signedamount", "Signed amount", "dec", f"If({_MINUS}, -Decimal(clt_amount), Decimal(clt_amount))",
                "Negative for returned contributions, repair draws and decreases"),
             text("qboreference", "QuickBooks reference", "Deposit, check or bill number", max=100),
             text("postingkey", "Posting key", "Set by the monthly posting flow to prevent duplicates. Blank for manual entries.", max=100),
             memo("notes", "Notes"),
         ]),

    # 15 ------------------------------------------------------------------
    dict(name="errrreconciliation", label="ERRR reconciliation", plural="ERRR reconciliations",
         desc="Monthly check that the per-property ERRR ledger agrees with QuickBooks.",
         primary=("Month", "For example: 2026-11"),
         columns=[
             date("monthend", "Month end"),
             money("qbobalance", "QuickBooks ERRR balance"),
             money("unallocatedinterest", "Unallocated interest to date"),
             money("propertybalances", "Sum of property balances", "Filled by the reconciliation flow"),
             fx("difference", "Difference", "dec",
                "Decimal(clt_qbobalance) - If(Decimal(clt_unallocatedinterest) = 0, 0, "
                "Decimal(clt_unallocatedinterest)) - Decimal(clt_propertybalances)"),
             memo("notes", "Notes"),
         ]),

    # 17 ------------------------------------------------------------------
    dict(name="listitem", label="List item", plural="Lists",
         desc="Values for the editable dropdowns (County, Property type, Income type and so on). Staff can add, rename and deactivate these in the app.",
         primary=("Value", "What staff see in the dropdown"),
         columns=[
             choice("list", "List", "listname", required=True),
             int_("sortorder", "Sort order", "Lower numbers appear first"),
             memo("formanswers", "Form answers",
                  "Answers from online forms that mean this value, one per line. The intake flows use these to match form answers to this value.",
                  max=2000),
             memo("description", "Description"),
         ]),

    # 19 ------------------------------------------------------------------
    dict(name="formsubmission", label="Form submission", plural="Form submissions",
         desc="One entry received from an online forms platform (Cognito Forms, Jotform, FormAssembly or other), in a standard format. The intake flows read these and update the other tables.",
         primary=("Submission", "For example: Annual verification, 12 Pine St, 2026"),
         columns=[
             text("provider", "Forms platform", "For example: Cognito Forms, Jotform, FormAssembly", max=50),
             choice("formtype", "Form type", "formtype"),
             text("externalentryid", "Entry ID", "The forms platform's ID for this entry", max=100),
             date("receivedon", "Received on"),
             choice("status", "Status", "submissionstatus", default="Received"),
             url("entrylink", "Entry link"),
             memo("payload", "Submission data", "The entry in the standard format, as JSON", max=1048576),
             memo("errordetail", "Problem details"),
         ]),

    # 19b -----------------------------------------------------------------
    dict(name="sourceform", label="Source form", plural="Source forms",
         desc="One online form on a forms platform (a Cognito, Jotform or FormAssembly form). The intake flows add a row the first time a form sends an entry, and link each submission and application to it, so staff can tell which form an application came from. A form made for one project names that project, and its new applications are added to it automatically; a rolling form leaves it blank.",
         primary=("Form", "The form's name on the forms platform"),
         columns=[
             text("provider", "Forms platform", "For example: Cognito Forms, Jotform, FormAssembly", max=50),
             text("externalformid", "Form ID", "The forms platform's ID for this form", max=100),
             choice("formtype", "Form type", "formtype"),
             memo("notes", "Notes", "For example: which projects or season this form was used for"),
         ]),

    # =====================================================================
    # v0.5: funding (core), projects, selection, certification (intake).
    # Design: docs/DESIGN.md "Eligibility, selection and certification" and "Blind lottery";
    # build plan: docs/plans/v0.5-plan.md (read its 2026-11-09 revision first).
    # =====================================================================
    dict(name="incomelimitset", label="HUD AMI Limits", plural="HUD AMI Limits",
         desc="One county's published income limits for one year: the 50% (very low income) limit for each household size.",
         primary=("Name", "For example: Jefferson 2026"),
         columns=[
             int_("year", "Year"),
             choice("limitsource", "Source", "limitsource", "HUD's published limits, or another table (a funder's own)",
                    default="HUD"),
             text("source", "Source details", "For example: HUD FY2026 Income Limits Summary"),
             date("effectivedate", "Effective date"),
             money("medianfamilyincome", "Median family income",
                   "For reference only: HUD's 'family' isn't our household, so AMI comes from the 50% limits"),
             # Whole dollars, not money: formula columns can't calculate with money on a linked table.
             *[int_(f"size{n}", f"50% limit, {n} {'person' if n == 1 else 'people'} ($)",
                    "100% AMI = 2 x this. Over 8 people: this x (1.32 + 0.08 per person over 8)" if n == 4
                    else "100% AMI = 2 x this")
               for n in range(1, 9)],
             memo("notes", "Notes"),
         ]),
    dict(name="eligibility", solution="intake", label="Organization eligibility", plural="Organization eligibility",
         desc="The CLT's own eligibility rules, used by every project unless the project sets its own. Keep one record.",
         primary=("Name", "For example: Our eligibility rules"),
         columns=[
             dec("maxami", "Max income (% of AMI)", "For example 80. Applicants above this aren't eligible", precision=0),
             dec("minami", "Min income (% of AMI)", "Blank means no minimum", precision=0),
             choice("firsttimebuyer", "First-time buyer", "rulechoice", ""),
             money("assetlimit", "Asset limit", "Blank means no limit"),
             dec("housingratiomax", "Housing ratio max (%)", "Front-end ratio: housing costs as a share of gross income"),
             dec("debtratiomax", "Total debt ratio max (%)", "Back-end ratio: all monthly debt as a share of gross income"),
             choice("education", "Homebuyer education", "rulechoice", ""),
             int_("validdays", "Certification valid for (days)", ""),
             choice("localtie", "Lives or works locally", "rulechoice", "Must have lived or worked in the local area (screener: local tie)"),
             text("localarea", "Local area", "For example: Lived or worked in the county for at least 1 year"),
             # Helpers the application's eligibility formulas read through their lookup (a formula can't compare
             # a choice or calculate with money on a linked table).
             fx("requiresftb", "First-time buyer is required", "bool", "clt_firsttimebuyer = [@'Eligibility requirement'].'Required'"),
             fx("requireslocal", "Local tie is required", "bool", "clt_localtie = [@'Eligibility requirement'].'Required'"),
             fx("assetlimitwhole", "Asset limit (whole dollars)", "int",
                "Round(Decimal(clt_assetlimit), 0)", "0 means no limit"),
             memo("notes", "Notes", "Anything the rules above don't cover"),
         ]),
    dict(name="propertyfunding", label="Property funding", plural="Property funding",
         primary_required=False,
         desc="A funder's covenant on one home: who funded it, the contract, target AMI and how long it lasts.",
         primary=("Name", "Funder and contract number"),
         columns=[
             text("contractnumber", "Contract number", max=100),
             dec("targetami", "Target AMI (%)"),
             date("covenantstart", "Covenant start"),
             int_("covenantyears", "Covenant years"),
             date("covenantend", "Covenant end"),
             memo("notes", "Notes", "The funder's requirements, reporting and anything else to remember"),
         ]),
    dict(name="project", solution="intake", label="Project", plural="Projects", notes=True,
         documents="Project Documents",  # lottery record, funder contracts
         desc="A selling campaign for one or more homes: a new development phase, or the resale of one home.",
         primary=("Project", "For example: Maple Court phase 1"),
         columns=[
             choice("projecttype", "Type", "projecttype"),
             choice("status", "Status", "projectstatus", default="Planning"),
             date("applicationopens", "Applications open"),
             date("applicationcloses", "Applications close", "Blank for a rolling first come first served list"),
             choice("selectionmethod", "Selection method", "selectionmethod"),
             bool_("rolling", "Rolling list", "First come first served only: rank as people apply, no closing date",
                   default=True),
             choice("listsource", "Buyer list", "listsource",
                    "Resales: run an own selection, or reuse a recent project's list that's still in effect"),
             dec("maxami", "Max income (% of AMI)", "Blank uses the organization's rule", precision=0),
             dec("minami", "Min income (% of AMI)", "Blank uses the organization's rule", precision=0),
             choice("firsttimebuyer", "First-time buyer", "rulechoice", "Blank uses the organization's rule"),
             money("assetlimit", "Asset limit", "Blank uses the organization's rule"),
             dec("housingratiomax", "Housing ratio max (%)", "Blank uses the organization's rule"),
             dec("debtratiomax", "Total debt ratio max (%)", "Blank uses the organization's rule"),
             choice("education", "Homebuyer education", "rulechoice", "Blank uses the organization's rule"),
             int_("validdays", "Certification valid for (days)", "Blank uses the organization's rule"),
             choice("localtie", "Lives or works locally", "rulechoice", "Blank uses the organization's rule"),
             text("localarea", "Local area", "Blank uses the organization's rule"),
             # How far over a limit a self-reported figure may be and still pass the pre-screen.
             dec("incomebuffer", "Income buffer (% over the limit)",
                 "Blank is 10. With an 80% limit, 10 lets stated income up to 88% of AMI through; 0 is no buffer."),
             dec("housingratiobuffer", "Housing ratio buffer (points)",
                 "Points added to the housing ratio max. With a 35% limit, 2 lets up to 37% through."),
             dec("debtratiobuffer", "Total debt ratio buffer (points)",
                 "Points added to the total debt ratio max. With a 44% limit, 2 lets up to 46% through."),
             choice("mincreditrange", "Minimum credit range", "creditrange"),
             int_("bankruptcyyears", "Bankruptcy look-back (years)"),
             bool_("minaffordabilitycheck", "Check minimum affordability", default=True),
             # What a home of each size costs a month in this project (every home of a size costs the same):
             # mortgage, taxes, insurance, dues and lease fee. The pre-screen's two ratios come from these.
             money("monthlycoststudio", "Monthly housing cost: studio"),
             money("monthlycost1br", "Monthly housing cost: 1 bedroom"),
             money("monthlycost2br", "Monthly housing cost: 2 bedrooms"),
             money("monthlycost3br", "Monthly housing cost: 3 bedrooms"),
             money("monthlycost4br", "Monthly housing cost: 4+ bedrooms"),
             dec("downpaymentpct", "Down payment (%)", "Share of the sale price the buyer pays up front. The rest is the loan the mortgage payment is worked out on."),
             int_("loantermyears", "Loan term (years)", "Blank is 30"),
             int_("invitesperlist", "Invites per list", "Default 10"),
             int_("invitesperhome", "Minimum invites per home", "Default 2"),
             int_("responsedays", "Response deadline (days)", "Default 15"),
             int_("waitlistmonths", "Lists stay in effect (months)", "Default 12"),
             text("documentsfolderlink", "Application documents folder",
                  "Only if this project's documents are somewhere other than your organization's usual folder: the web address "
                  "of the folder the form saves this project's documents into.", max=500),
             text("fullappformlink", "Full application link",
                  "Only if this project uses a different full application form from your organization's usual one (a setting): "
                  "its web address. Each invited household gets its own link made from this, with its application number "
                  "added (Projects > Invite).", max=500),
             memo("notes", "Notes"),
         ]),
    dict(name="projectpriority", solution="intake", label="Project priority", plural="Project priorities",
         primary_required=False,
         desc="Which household sizes may apply for a bedroom size, and in which tier. No row means not eligible.",
         primary=("Name", "For example: 2 BR, 4 persons"),
         columns=[
             int_("bedrooms", "Bedrooms", "0 for a studio"),
             int_("householdsize", "Household size"),
             int_("tier", "Tier", "1 ranks first"),
             text("preference", "Preference", "Optional, for preference tiers"),
             memo("notes", "Notes"),
         ]),
    dict(name="projectband", solution="intake", label="Income band", plural="Income bands",
         primary_required=False,
         desc="A band of buyers by income in a project. Each band has its own interest rate, and can have its own sale "
              "prices, so the monthly housing cost the pre-screen tests against depends on the household's income.",
         primary=("Name", "For example: Up to 65% of AMI"),
         columns=[
             dec("maxami", "Up to (% of AMI)", "Blank on the last band: everyone above the band before it"),
             dec("interestrate", "Interest rate (%)", "The mortgage rate buyers in this band can expect", precision=3),
             int_("sortorder", "Order", "Lowest income band first"),
             money("pricestudio", "Sale price: studio"),
             money("price1br", "Sale price: 1 bedroom"),
             money("price2br", "Sale price: 2 bedrooms"),
             money("price3br", "Sale price: 3 bedrooms"),
             money("price4br", "Sale price: 4+ bedrooms"),
             money("pistudio", "Principal and interest: studio"),
             money("pi1br", "Principal and interest: 1 bedroom"),
             money("pi2br", "Principal and interest: 2 bedrooms"),
             money("pi3br", "Principal and interest: 3 bedrooms"),
             money("pi4br", "Principal and interest: 4+ bedrooms"),
             money("monthlycoststudio", "Monthly housing cost: studio"),
             money("monthlycost1br", "Monthly housing cost: 1 bedroom"),
             money("monthlycost2br", "Monthly housing cost: 2 bedrooms"),
             money("monthlycost3br", "Monthly housing cost: 3 bedrooms"),
             money("monthlycost4br", "Monthly housing cost: 4+ bedrooms"),
         ]),
    dict(name="projecthome", solution="intake", label="Project home", plural="Project homes",
         primary_required=False,
         desc="A home offered in a project.",
         primary=("Name", "The property's name"),
         columns=[
             int_("bedrooms", "Bedrooms", "Decides which list the home belongs to"),
             dec("targetami", "Target AMI (%)"),
             money("estimatedprice", "Sale price"),
             money("principalinterest", "Principal and interest (monthly)", "The buyer's expected mortgage payment"),
             money("propertytaxes", "Property taxes (monthly)"),
             money("insurance", "Homeowner's insurance (monthly)"),
             money("hoadues", "HOA dues (monthly)"),
             money("leasefee", "Ground lease fee (monthly)"),
             money("reservefee", "Reserve fee (monthly)", "The repair and replacement reserve contribution"),
             money("estimatedmonthlycost", "Monthly housing cost",
                   "The six monthly amounts above added together. The pre-screen uses the figure for this home size on the project."),
             choice("status", "Status", "projecthomestatus", default="Available"),
         ]),
    dict(name="lotteryfactor", solution="intake", label="Lottery factor", plural="Lottery factors",
         desc="Extra lottery chances a project gives for one factor. Needs a stated basis and a fair housing review.",
         primary=("Factor", "For example: Works in the county"),
         columns=[
             dec("extrachances", "Extra chances", "Added to the household's 1 chance"),
             memo("definition", "Plain definition"),
             text("questionkey", "Screener question key", "Field in the standard form format that decides it"),
             memo("qualifyinganswers", "Answers that qualify", "One per line"),
             memo("proof", "Proof at certification"),
             memo("basis", "Basis", "Board policy or funder requirement, with date"),
             date("fairhousingreviewed", "Fair housing review date"),
             bool_("active", "Active", default=True),
         ]),
    dict(name="selectionround", solution="intake", label="Selection round", plural="Selection rounds", notes=True,
         desc="One lottery or first come first served ranking for a project.",
         primary=("Round", "For example: Maple Court lottery 2026-12-03"),
         columns=[
             choice("method", "Method", "selectionmethod"),
             choice("status", "Status", "roundstatus", default="Open"),
             datetime_("poolslockedon", "Pools locked on"),
             memo("checknumbers", "Check numbers", "One per list, computed at the lock and printed on the pool lists"),
             text("observer", "Board Observer", "Name (trustees may not be app users)"),
             text("diceroll", "Dice roll", "Ten d10 rolls read in order, for example 0384719265", max=10),
             int_("seed", "Seed", "MOD(roll, 2147483646) + 1, computed by the draw"),
             datetime_("drawnon", "Drawn on"),
             datetime_("certifiedon", "Result certified on"),
             date("listsendon", "Lists end on", "Draw date plus the project's months in effect"),
         ]),
    dict(name="selectionentry", solution="intake", label="Selection entry", plural="Selection entries",
         primary_required=False,
         desc="One household on one bedroom-size list. Read-only once the pools lock.",
         primary=("Name", "Unique ID and bedroom size"),
         columns=[
             text("uniqueid", "Unique ID", max=20),
             int_("bedrooms", "Bedrooms", "Which list"),
             int_("householdsize", "Household size"),
             int_("tier", "Tier"),
             dec("chances", "Chances", "1 plus any lottery factors"),
             datetime_("submittedon", "First submitted", "First come first served tiebreaker"),
             int_("lotteryseq", "Generator value", "The s value, kept so anyone can check the arithmetic"),
             dec("lotterynumber", "Lottery number", precision=10),
             dec("rankingkey", "Ranking key", "Lottery number ^ (1 / chances)", precision=10),
             int_("rank", "Rank", "Within the list; never edited by hand"),
             choice("status", "List status", "entrystatus", default="Waitlist"),
             text("statusreason", "Status reason"),
             date("statusdate", "Status date"),
             date("invitedon", "Invited on"),
             date("responsedue", "Response due"),
         ]),
    dict(name="entryfactor", solution="intake", label="Entry factor", plural="Entry factors",
         primary_required=False,
         desc="A lottery factor a household claimed on one entry, and whether certification confirmed it.",
         primary=("Name", "Factor"),
         columns=[
             bool_("verified", "Verified at certification"),
             memo("notes", "Notes"),
         ]),
    dict(name="certification", solution="intake", label="Certification", plural="Certifications", notes=True,
         desc="Staff review and certification of a household's size, income, assets and debt for a project.",
         primary=("Certification", "Household and date"),
         columns=[
             choice("status", "Status", "certificationstatus", default="Reviewing"),
             int_("certifiedsize", "Certified household size"),
             money("certifiedincome", "Certified annual income"),
             money("certifiedassets", "Certified assets"),
             money("certifiedmonthlydebt", "Certified monthly debt"),
             dec("certifiedamipct", "Certified income (% of AMI)", "Certified annual income against 100% of AMI for the certified household size"),
             multi("certifiedsizes", "Home sizes certified for", "homesize", "The home sizes the household passed both ratios for"),
             bool_("confirmedfthb", "Confirmed: first-time buyer", "Ticked by staff in the review"),
             bool_("confirmedlocal", "Confirmed: lives or works locally"),
             bool_("confirmedresidence", "Confirmed: will be their primary residence"),
             bool_("confirmededucation", "Confirmed: homebuyer education complete"),
             datetime_("certifiedon", "Certified on"),
             date("expireson", "Expires on"),
             memo("notcertifiedreason", "Not certified because"),
             memo("opendocuments", "Open documents at certification",
                  "Checklist items still open when certified (a warning, not a block)"),
             int_("limityear", "Income limit year used"),
             money("ami100", "100% AMI for certified size", "Written by the checks"),
             money("estprice", "Estimated purchase price"),
             money("estloan", "Estimated loan"),
             dec("estrate", "Estimated rate (%)", precision=3),
             int_("estterm", "Loan term (years)"),
             money("esttaxes", "Monthly property taxes"),
             money("estinsurance", "Monthly homeowners insurance"),
             money("estmi", "Monthly mortgage insurance"),
             money("estdues", "Monthly association dues"),
             money("estlandlease", "Monthly land lease fee"),
             money("estutilities", "Monthly utilities"),
             datetime_("checksrunon", "Checks last run"),
         ]),
    dict(name="eligibilitycheck", solution="intake", label="Eligibility check", plural="Eligibility checks",
         primary_required=False,
         desc="One test of one eligibility rule, with its value and limit, so every decision shows its working.",
         primary=("Name", "For example: Max income"),
         columns=[
             choice("stage", "Stage", "checkstage"),
             choice("test", "Test", "checktest"),
             dec("value", "Value"),
             dec("limit", "Limit", "Including any buffer"),
             choice("result", "Result", "checkresult"),
             memo("notes", "How it was worked out"),
         ]),
    dict(name="checklistitem", solution="intake", label="Checklist item", plural="Checklist items",
         primary_required=False,
         desc="One document certification needs from the household (or one member). Staff add the items.",
         primary=("Name", "Document and person"),
         columns=[
             choice("status", "Status", "documentstatus", default="Missing"),
             date("receivedon", "Received on"),
             date("documentdate", "Document date"),
             date("reviewedon", "Reviewed on"),
             memo("note", "Note", "What's wrong, or why it's waived"),
         ]),
    dict(name="messagetemplate", solution="intake", label="Message template", plural="Message templates",
         desc="The wording of a message staff send to applicants. Staff can change it. Words in curly brackets are filled in for each household.",
         primary=("Name", "For example: Invitation to the full application"),
         columns=[
             choice("noticetype", "Used for", "noticetype"),
             text("subject", "Subject line", max=200),
             memo("body", "Message", "Words in curly brackets are filled in for each household: {first name}, {household}, {project}, "
                  "{application number}, {link}, {deadline}, {organization}. The insurance request also takes {home} and {due date}.", max=10000),
         ]),
    dict(name="notice", solution="intake", label="Notice", plural="Notices",
         desc="A message sent to an applicant: screened out, not selected, invited, reminders, offers.",
         primary=("Subject", "Subject line"),
         columns=[
             choice("noticetype", "Type", "noticetype"),
             choice("channel", "Sent by", "noticechannel"),
             datetime_("senton", "Sent on"),
             text("sentto", "Sent to", "Email address or mailing address"),
             memo("body", "Message", max=10000),
         ]),
]


# ---------------------------------------------------------------------------
# Lookups (one-to-many relationships).
# (child table, lookup column, parent table, label, on delete of parent, required)
#   on delete: "Cascade"   delete the child rows too
#              "RemoveLink" keep the child rows, clear the lookup
#              "Restrict"  block deleting the parent while child rows exist
# ---------------------------------------------------------------------------
# Lookups that an earlier version made required, or deleted with their parent. The schema build brings one that already
# exists in line with LOOKUPS, and only ever in the looser direction: required to optional, Cascade to RemoveLink.
LOOSENED = [("walkby", "occupancy"), ("followup", "occupancy")]

LOOKUPS = [
    ("householdmember",   "household",       "household",        "Household",            "Cascade",    True),
    ("application",       "household",       "household",        "Household",            "Restrict",   True),
    ("incomesource",      "application",     "application",      "Application",          "Cascade",    True),
    ("incomesource",      "member",          "householdmember",  "Household member",     "RemoveLink", False),
    ("debt",              "application",     "application",      "Application",          "Cascade",    True),
    ("debt",              "member",          "householdmember",  "Household member",     "RemoveLink", False),
    ("asset",             "application",     "application",      "Application",          "Cascade",    True),
    ("asset",             "member",          "householdmember",  "Household member",     "RemoveLink", False),
    ("occupancy",         "property",        "property",         "Property",             "Restrict",   True),
    ("occupancy",         "household",       "household",        "Household",            "Restrict",   True),
    ("annualverification","occupancy",       "occupancy",        "Occupancy",            "Cascade",    True),
    ("insurancepolicy",   "occupancy",       "occupancy",        "Occupancy",            "Cascade",    True),
    ("walkby",            "property",        "property",         "Property",             "Cascade",    True),
    ("walkby",            "occupancy",       "occupancy",        "Occupancy",            "RemoveLink", False),
    ("walkbyphoto",       "walkby",          "walkby",           "Staff walk-by",        "Cascade",    True),
    ("insuranceverification", "occupancy",   "occupancy",        "Occupancy",            "Cascade",    True),
    ("followup",          "occupancy",       "occupancy",        "Occupancy",            "RemoveLink", False),
    ("followup",          "property",        "property",         "Property",             "Cascade",    False),
    ("followup",          "walkby",          "walkby",           "Staff walk-by",        "RemoveLink", False),
    ("improvementcredit", "occupancy",       "occupancy",        "Occupancy",            "Cascade",    True),
    ("improvementcredit", "homeownerrequest", "homeownerrequest", "Homeowner request",   "RemoveLink", False),
    ("loan",              "occupancy",       "occupancy",        "Occupancy",            "Cascade",    True),
    ("relationshipnote",  "occupancy",       "occupancy",        "Occupancy",            "Cascade",    True),
    ("homeownerrequest",  "occupancy",       "occupancy",        "Occupancy",            "Restrict",   True),
    ("homeownerrequest",  "property",        "property",         "Property",             "RemoveLink", False),
    ("sale",              "property",        "property",         "Property",             "Restrict",   True),
    ("salefunding",       "sale",            "sale",             "Sale",                 "Cascade",    True),
    ("saletask",          "sale",            "sale",             "Sale",                 "Cascade",    True),
    ("sale",              "selleroccupancy", "occupancy",        "Seller's occupancy",   "RemoveLink", False),
    ("sale",              "buyerhousehold",  "household",        "Buyer household",      "RemoveLink", False),
    ("sale",              "buyeroccupancy",  "occupancy",        "Buyer's occupancy",    "RemoveLink", False),
    ("fee",               "property",        "property",         "Property",             "Cascade",    True),
    ("errrtransaction",   "property",        "property",         "Property",             "Restrict",   True),
    ("errrtransaction",   "occupancy",       "occupancy",        "Occupancy",            "RemoveLink", False),
    ("errrtransaction",   "homeownerrequest","homeownerrequest", "Homeowner request",    "RemoveLink", False),
    # Editable lists and new tables
    ("property",          "state",           "listitem",         "State",                "Restrict",   False),
    ("household",         "mailingstate",    "listitem",         "Mailing state",        "Restrict",   False),
    ("listitem",          "state",           "listitem",         "State (counties only)", "RemoveLink", False),
    ("property",          "county",          "listitem",         "County",               "Restrict",   False),
    ("property",          "propertytype",    "listitem",         "Property type",        "Restrict",   False),
    ("property",          "tenuretype",      "listitem",         "Tenure type",          "Restrict",   False),
    ("property",          "neighborhood",    "listitem",         "Neighborhood",         "Restrict",   False),
    ("property",          "currentoccupancy","occupancy",        "Current occupancy",    "RemoveLink", False),
    ("householdmember",   "relationship",    "listitem",         "Relationship to primary applicant", "Restrict", False),
    ("application",       "county",          "listitem",         "County",               "Restrict",   False),
    ("application",       "housingstatus",   "listitem",         "Current housing status", "Restrict", False),
    ("incomesource",      "incometype",      "listitem",         "Income type",          "Restrict",   False),
    ("debt",              "debttype",        "listitem",         "Debt type",            "Restrict",   False),
    ("asset",             "assettype",       "listitem",         "Asset type",           "Restrict",   False),
    ("formsubmission",    "household",       "household",        "Household",            "RemoveLink", False),
    ("formsubmission",    "application",     "application",      "Application",          "RemoveLink", False),
    ("formsubmission",    "annualverification", "annualverification", "Annual verification", "RemoveLink", False),
    ("formsubmission",    "sourceform",      "sourceform",       "Source form",          "RemoveLink", False),
    ("application",       "sourceform",      "sourceform",       "Source form",          "RemoveLink", False),
    ("sourceform",        "project",         "project",          "Add new applications to project", "RemoveLink", False),
    # v0.5 funding, projects, selection, certification
    ("propertyfunding",   "property",        "property",         "Property",             "Cascade",    True),
    ("propertyfunding",   "funder",          "listitem",         "Funder",               "Restrict",   False),
    ("incomelimitset",    "county",          "listitem",         "County",               "Restrict",   True),
    ("projectpriority",   "project",         "project",          "Project",              "Cascade",    True),
    ("projecthome",       "project",         "project",          "Project",              "Cascade",    True),
    ("projectband",       "project",         "project",          "Project",              "Cascade",    True),
    ("projecthome",       "property",        "property",         "Property",             "Restrict",   True),
    ("lotteryfactor",     "project",         "project",          "Project",              "Cascade",    True),
    ("project",           "reuseround",      "selectionround",   "Reuse list from round","RemoveLink", False),
    ("selectionround",    "project",         "project",          "Project",              "Restrict",   True),
    ("selectionround",    "drawnby",         "systemuser",       "Drawn by",             "RemoveLink", False),
    ("selectionentry",    "round",           "selectionround",   "Selection round",      "Cascade",    True),
    ("selectionentry",    "application",     "application",      "Application",          "Restrict",   True),
    ("entryfactor",       "entry",           "selectionentry",   "Selection entry",      "Cascade",    True),
    ("entryfactor",       "factor",          "lotteryfactor",    "Lottery factor",       "Restrict",   True),
    ("application",       "project",         "project",          "Project",              "Restrict",   False),
    ("application",       "amilimits",       "incomelimitset",   "AMI limits used",      "RemoveLink", False),
    ("application",       "eligibilityrules","eligibility",      "Eligibility rules used","RemoveLink", False),
    ("certification",     "household",       "household",        "Household",            "Restrict",   True),
    ("certification",     "application",     "application",      "Application",          "RemoveLink", False),
    ("certification",     "project",         "project",          "Project",              "RemoveLink", False),
    ("certification",     "limitset",        "incomelimitset",   "Income limit set",     "Restrict",   False),
    ("certification",     "certifiedby",     "systemuser",       "Certified by",         "RemoveLink", False),
    ("eligibilitycheck",  "application",     "application",      "Application",          "Cascade",    False),
    ("eligibilitycheck",  "certification",   "certification",    "Certification",        "RemoveLink", False),
    ("incomesource",      "certification",   "certification",    "Certification",        "RemoveLink", False),
    ("debt",              "certification",   "certification",    "Certification",        "RemoveLink", False),
    ("asset",             "certification",   "certification",    "Certification",        "RemoveLink", False),
    ("checklistitem",     "certification",   "certification",    "Certification",        "Cascade",    True),
    ("checklistitem",     "member",          "householdmember",  "Household member",     "RemoveLink", False),
    ("checklistitem",     "reviewedby",      "systemuser",       "Reviewed by",          "RemoveLink", False),
    ("notice",            "application",     "application",      "Application",          "RemoveLink", False),
    ("notice",            "household",       "household",        "Household",            "RemoveLink", False),
    ("notice",            "project",         "project",          "Project",              "RemoveLink", False),
]


# ---------------------------------------------------------------------------
# Alternate keys, so the flows can match and upsert rows.
# Blank values are allowed and are not checked for uniqueness.
# (table, key name, [columns])
# ---------------------------------------------------------------------------
KEYS = [
    ("household",          "primaryemail",    ["primaryemail"]),
    ("householdmember",    "formitemid",      ["formitemid"]),
    ("application",        "screenerentryid", ["screenerentryid"]),
    ("application",        "fullappentryid",  ["fullappentryid"]),
    ("incomesource",       "formitemid",      ["formitemid"]),
    ("debt",               "formitemid",      ["formitemid"]),
    ("asset",              "formitemid",      ["formitemid"]),
    ("annualverification", "verificationcode",["verificationcode"]),
    ("formsubmission",     "providerentry",   ["provider", "externalentryid"]),
    ("sourceform",         "providerform",    ["provider", "externalformid"]),
    ("errrtransaction",    "postingkey",      ["postingkey"]),
    ("projectpriority",   "projectbedsize",  ["project", "bedrooms", "householdsize"]),
    ("projecthome",       "projectproperty", ["project", "property"]),
    ("selectionentry",    "roundappbeds",    ["round", "application", "bedrooms"]),
]


# ---------------------------------------------------------------------------
# Lookups that point at one list in the List item table. The app filters
# each of these dropdowns to its own list.
# ---------------------------------------------------------------------------
LIST_LOOKUPS = {(child, col): None for child, col, parent, *_ in LOOKUPS if parent == "listitem"}
_LIST_FOR = {"county": "County", "propertytype": "Property type", "tenuretype": "Tenure type",
             "relationship": "Relationship", "housingstatus": "Housing status", "incometype": "Income type",
             "debttype": "Debt type", "assettype": "Asset type", "state": "State", "mailingstate": "State",
             "funder": "Funder", "neighborhood": "Neighborhood"}
LIST_LOOKUPS = {k: _LIST_FOR[k[1]] for k in LIST_LOOKUPS}


# ---------------------------------------------------------------------------
# Starting values for the editable lists: (value, [form answers that mean it]).
# Loaded once by build_schema.py --seed-lists; after that, staff own them.
# County and Neighborhood are left empty for each CLT to fill in.
# ---------------------------------------------------------------------------
def same(*labels):
    return [(x, [x]) for x in labels]

SEED_LISTS = {
    "Property type": same("Single-family detached", "Townhome", "Condominium", "Duplex or multiplex unit",
                          "ADU or cottage", "Manufactured home", "Land only", "Common area", "Commercial",
                          "Agricultural"),
    "Tenure type": same("Ground lease", "Deed restriction or covenant", "Co-op share", "Rental", "Other"),
    "Relationship": [
        ("Self", []),
        ("Spouse or partner", ["Spouse or partner", "Spouse", "Domestic partner"]),
        ("Child", ["Child"]), ("Adult child", ["Adult child"]), ("Grandchild", ["Grandchild"]),
        ("Parent", ["Parent"]), ("Sibling", ["Sibling"]), ("Other relative", ["Other relative"]),
        ("Other", []),
    ],
    "Housing status": same("Homeowner", "Renter", "Homeless", "Other"),
    "Funder": same("WA State Housing Trust Fund (Commerce)", "HOME (HUD)", "County affordable housing funds", "Other"),
    "Income type": same(
        "Full-time employment", "Part-time employment", "Self-employment", "Tips", "Military pay",
        "Spousal support / alimony", "Child support", "Social Security", "SSI", "SSDI", "Pension or annuity",
        "Unemployment", "Public assistance (TANF)", "Regular help from family or friends",
        "Student financial aid", "Investment income", "Casual or intermittent work", "Other"),
    "Debt type": same(
        "Student loan", "Auto loan or lease", "Credit card", "Personal loan", "Medical payment plan",
        "Buy now, pay later plan", "Child support or alimony you pay", "Other"),
    "Asset type": same(
        "Checking", "Savings", "Certificate of deposit (CD)", "Money market", "Prepaid debit card",
        "Investment or brokerage account", "Retirement account (401(k), 403(b), IRA, etc.)", "Trust",
        "Cash on hand", "Real estate or land", "Other"),
    # Form answers: the two-letter code and the name, so either spelling matches.
    "State": [
        ("Alabama", ["AL", "Alabama"]),
        ("Alaska", ["AK", "Alaska"]),
        ("Arizona", ["AZ", "Arizona"]),
        ("Arkansas", ["AR", "Arkansas"]),
        ("California", ["CA", "California"]),
        ("Colorado", ["CO", "Colorado"]),
        ("Connecticut", ["CT", "Connecticut"]),
        ("Delaware", ["DE", "Delaware"]),
        ("District of Columbia", ["DC", "District of Columbia"]),
        ("Florida", ["FL", "Florida"]),
        ("Georgia", ["GA", "Georgia"]),
        ("Hawaii", ["HI", "Hawaii"]),
        ("Idaho", ["ID", "Idaho"]),
        ("Illinois", ["IL", "Illinois"]),
        ("Indiana", ["IN", "Indiana"]),
        ("Iowa", ["IA", "Iowa"]),
        ("Kansas", ["KS", "Kansas"]),
        ("Kentucky", ["KY", "Kentucky"]),
        ("Louisiana", ["LA", "Louisiana"]),
        ("Maine", ["ME", "Maine"]),
        ("Maryland", ["MD", "Maryland"]),
        ("Massachusetts", ["MA", "Massachusetts"]),
        ("Michigan", ["MI", "Michigan"]),
        ("Minnesota", ["MN", "Minnesota"]),
        ("Mississippi", ["MS", "Mississippi"]),
        ("Missouri", ["MO", "Missouri"]),
        ("Montana", ["MT", "Montana"]),
        ("Nebraska", ["NE", "Nebraska"]),
        ("Nevada", ["NV", "Nevada"]),
        ("New Hampshire", ["NH", "New Hampshire"]),
        ("New Jersey", ["NJ", "New Jersey"]),
        ("New Mexico", ["NM", "New Mexico"]),
        ("New York", ["NY", "New York"]),
        ("North Carolina", ["NC", "North Carolina"]),
        ("North Dakota", ["ND", "North Dakota"]),
        ("Ohio", ["OH", "Ohio"]),
        ("Oklahoma", ["OK", "Oklahoma"]),
        ("Oregon", ["OR", "Oregon"]),
        ("Pennsylvania", ["PA", "Pennsylvania"]),
        ("Rhode Island", ["RI", "Rhode Island"]),
        ("South Carolina", ["SC", "South Carolina"]),
        ("South Dakota", ["SD", "South Dakota"]),
        ("Tennessee", ["TN", "Tennessee"]),
        ("Texas", ["TX", "Texas"]),
        ("Utah", ["UT", "Utah"]),
        ("Vermont", ["VT", "Vermont"]),
        ("Virginia", ["VA", "Virginia"]),
        ("Washington", ["WA", "Washington"]),
        ("West Virginia", ["WV", "West Virginia"]),
        ("Wisconsin", ["WI", "Wisconsin"]),
        ("Wyoming", ["WY", "Wyoming"]),
    ],
}


# ---------------------------------------------------------------------------
# Environment variables: per-client settings. The solution carries these
# definitions with blank defaults; each environment holds its own values
# (set by tools/apply_branding.py from clients/<client>/client.json).
# ---------------------------------------------------------------------------
# Starter rows for ordinary tables, created only when the table is empty (build_schema.seed_rows).
# Choice values by label; multi-select as a list of labels.
SEED_ROWS = {
    # A starting point: each organization edits its own list (Settings > After-sale tasks).
    "aftersaletask": [
        dict(name="Enter the buyer's insurance", order=10, action="Enter the insurance", appliesto="Every sale",
             details="The policy the buyer had in place at closing. Saving it also records the home's first insurance verification, so the next one is due a year after the purchase."),
        dict(name="Add the final settlement statement", order=20, action="Add the settlement statement", appliesto="Every sale",
             details="The final settlement statement from the title or escrow company, as a PDF or a photo."),
        dict(name="File the recorded ground lease and closing documents", order=30, action="Open the documents folder", appliesto="Every sale",
             details="Put the recorded ground lease, its memorandum and the closing documents in the occupancy's documents folder."),
        dict(name="Check the new occupancy's resale terms", order=40, action="Open the new occupancy", appliesto="Every sale",
             details="The formula and limits were copied from the last owner. Change them if this buyer's ground lease differs."),
        dict(name="Set up the monthly fees for the new owner", order=50, action="Open the property", appliesto="Every sale",
             details="Check the fee schedule on the property's ERRR and fees tab: the lease fee and the repair reserve contribution."),
        dict(name="Take photos of the home at purchase", order=60, action="Open Stu in the wild", appliesto="Every sale",
             details="Record a staff walk-by with photos, so there is a picture of the home on the day this owner took it on."),
        dict(name="Welcome the new homeowner", order=70, action="Tick it off", appliesto="Every sale",
             details="Send the welcome letter or packet, and tell them when their first yearly verification will come."),
        dict(name="Close out the seller's repair reserve and loans", order=80, action="Tick it off", appliesto="Resales only",
             details="Settle what the seller is owed or owes: the repair reserve balance and any loan from the organization."),
    ],
    # Starting point only: each CLT confirms its own figures (DESIGN.md, Eligibility).
    "eligibility": [dict(name="Organization eligibility", maxami=80, firsttimebuyer="Required",
                         housingratiomax=38, debtratiomax=45)],
    # A starting point for each CLT to reword (Settings > Message templates). The Invite page falls back to the
    # same words (webresources/invite.js) if this row is deleted.
    "messagetemplate": [dict(
        name="Invitation to the full application", noticetype="Invited to full application",
        subject="You're invited to apply: {project}",
        body="Hello {first name},\n\n"
             "Good news. Your household's place in the {project} selection means you are invited to complete a full application.\n\n"
             "Your personal link:\n{link}\n\n"
             "Please use this link and not one passed on by someone else. It carries your application number ({application number}), "
             "which is how we match your full application to you.\n\n"
             "Please finish the application by {deadline}. If we haven't received it by then, we will offer your place to the next household on the list.\n\n"
             "It will ask about everyone in your household, your income, debts and savings, and for copies of recent pay stubs, "
             "bank statements and tax returns. You can save it and come back.\n\n"
             "Being invited is not yet an offer of a home. We check each full application against the program's rules first.\n\n"
             "If you have questions, or need help or an accommodation to complete the application, reply to this email.\n\n"
             "{organization}"),
        # The email the Insurance verification page hands staff to copy. Falls back to the same words
        # (webresources/insurancecheck.js) if this row is deleted.
        dict(name="Request for proof of insurance", noticetype="Insurance verification",
             subject="Proof of homeowner's insurance for {home}",
             body="Hello {first name},\n\n"
                  "Each year we check that every home has homeowner's insurance in place. Please send us proof of your current policy by {due date}.\n\n"
                  "The declarations page is what we need: it shows the insurer, the policy dates and the coverage amounts. "
                  "You can reply to this email with a PDF or a photo of it.\n\n"
                  "If you have any questions, or can't find the document, just reply to this email.\n\n"
                  "Thank you,\n{organization}")],
}

ENVIRONMENT_VARIABLES = [
    dict(name="OrgName", label="CLT name", desc="The CLT's name, shown on the home page and in emails."),
    dict(name="BrandHeaderColor", label="Brand: header color",
         desc="App header background as a hex color, for example #344734. Blank uses the Dataverse default."),
    dict(name="BrandHeaderTextColor", label="Brand: header text color",
         desc="Text and icon color on the header, for example #FFFFFF."),
    dict(name="BrandAccentColor", label="Brand: accent color",
         desc="Header hover and selected color, for example #526B50."),
    dict(name="ApplicationDocumentsFolder", label="Full application: where documents are saved",
         desc="The web address of the folder your full application form saves documents into (the one holding a folder for "
              "each household). Review and certify opens each household's own folder inside it. A project can name a different one."),
    dict(name="ApplicationFolderName", label="Full application: name of each household's documents folder",
         desc="How your form names the folder it saves a household's documents into. Blank uses "
              "{last name} - Entry {entry number}. Also available: {application number}, {household}, {entry}."),
    dict(name="FullAppNumberField", label="Full application: Application Number question",
         desc="Cognito Forms only: the form's Application Number question as Section.Question. Blank uses "
              "PrimaryApplicant.ApplicationNumber. The Invite page uses it to put each household's number on its link."),
    dict(name="FullAppFormLink", label="Full application: form link",
         desc="The web address of your full application form. The Invite page makes each invited household its own link from "
              "this, with its application number added. A project that uses a different form has its own link on the "
              "project record (Full application link), which is used in place of this one."),
    dict(name="VerificationFormLink", label="Annual verification: form link",
         desc="The web address of your annual occupancy verification form. Stu adds the year, the household ID and a code to each household's "
              "link so the reply can be matched. To fill in your form's own questions, put {year}, {household id}, {code}, {first name}, "
              "{last name}, {street}, {unit}, {city}, {state} and {zip} in the link the way your forms platform fills in a form from its "
              "address; a plain link gets the year, household ID and code added the usual way for Cognito Forms or Jotform."),
    dict(name="OccupancyVerificationMonths", label="Verification hub: months between occupancy verifications",
         desc="Occupancy verification is due on each anniversary of the occupancy's start date. This is used only for an "
              "occupancy with no start date: months from its last verification. Blank means 12."),
    dict(name="InsuranceVerificationMonths", label="Verification hub: months between insurance verifications",
         desc="How often each home's insurance is checked, in months. Blank means every 12."),
    dict(name="WalkByMonths", label="Verification hub: months between staff walk-bys",
         desc="How often staff walk or drive by each home, in months. Blank means every 12. On the Stu in the wild page a home is green "
              "while its last submitted walk-by is newer than this."),
    dict(name="BrandLogoUrl", label="Brand: logo URL",
         desc="Web address of the CLT's logo (PNG or SVG; square works best). Shown on the home page."),
]

# ---------------------------------------------------------------------------
# Retired items. build_schema.py --remove-retired deletes these (keys, then
# columns, then lookups, then tables, then choices). Any data in them is lost.
#   v0.3: columns and choices replaced by list lookups.
#   v0.5: State text columns become State list lookups; Insurance policy's
#         Property link, and the Development and Document tables, are removed.
#         Simplified eligibility (2026-11-10): Funding programs, Project funding,
#         Document requirements and the per-size AMI limit rows are removed;
#         eligibility is the organization's rules plus each project's overrides.
# "columns" are only removed while they are NOT lookups, so a column can be
# replaced by a lookup with the same name.
# ---------------------------------------------------------------------------
RETIRED = {
    "keys": [
        ("householdmember", "cognitoitemid"), ("incomesource", "cognitoitemid"), ("debt", "cognitoitemid"),
        ("asset", "cognitoitemid"), ("annualverification", "cognitoentryid"),
    ],
    "columns": [
        ("property", "county"), ("property", "development"), ("property", "propertytype"),
        ("property", "tenuretype"), ("property", "defaultresaleformula"),
        ("householdmember", "relationship"), ("householdmember", "cognitoitemid"),
        ("application", "county"), ("application", "housingstatus"),
        ("incomesource", "incometype"), ("incomesource", "cognitoitemid"),
        ("debt", "debttype"), ("debt", "cognitoitemid"),
        ("asset", "assettype"), ("asset", "cognitoitemid"),
        ("annualverification", "cognitoentryid"),
        ("sale", "errrbalanceatsale"),
        ("property", "state"), ("household", "mailingstate"),
        ("propertyfunding", "origin"), ("incomelimitset", "roundto"),
        ("application", "statedamipct"),  # now the formula column amipct
        # insurance is checked on its own, so the yearly occupancy form's insurance answers and uploads are gone
        ("annualverification", "insurancereceived"), ("annualverification", "insurancecurrent"), ("annualverification", "insurancecontact"),
        ("annualverification", "uploadslink"), ("insuranceverification", "documentslink"),
        ("walkby", "result"), ("occupancy", "lastwalkby"),  # a walk-by has a follow-up tick box; the last walk-by is on the property
        *[("incomelimitset", f"limit{n}") for n in range(1, 9)],  # money; now whole-dollar size1..size8
    ],
    # (child, column, parent): lookups deleted by removing their relationship
    "lookups": [
        ("property", "development", "development"), ("insurancepolicy", "property", "property"),
        ("propertyfunding", "fundingprogram", "fundingprogram"), ("eligibilitycheck", "fundingprogram", "fundingprogram"),
        ("checklistitem", "requirement", "documentrequirement"),
        ("insuranceverification", "annualverification", "annualverification"),
    ],
    # In order: a table goes after any retired table that looks it up (Funding program last).
    "tables": ["development", "document", "projectfunding", "documentrequirement", "incomelimit", "fundingprogram"],
    "choices": ["propertytype", "tenuretype", "relationship", "housingstatus", "incometype", "debttype",
                "assettype", "fundingtype", "incomedefinition", "housingratioincludes", "debtratioincludes",
                "reportformat", "fundingorigin", "documentscope", "walkbyresult"],
}
