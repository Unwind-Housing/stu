"""
CLT Stewardship: model-driven app spec (navigation, views, forms).

build_app.py turns this into the app. Unlike the schema build, the app build
OVERWRITES the forms and views it manages each time it runs, so make layout
changes here rather than in the form designer, at least until the build settles.

Field names are logical names without the "clt_" prefix. A name starting with
"?" is optional: it is placed only if the column exists. That is how the formula
and rollup columns you add by hand in step 4 get onto the forms: add them, then
run build_app.py again.
"""

APP = {
    "name": "CLT Stewardship",
    "uniquename": "clt_CLTStewardship",
    "description": "Properties, households, occupancies and stewardship for community land trusts.",
}

# Intake tables this app still needs: the shared Household form lists a household's applications and
# certifications. Revisit when the solutions are split for deployment (an intake-only Household form, or
# dropping these lists from the core form).
APP_EXTRA_TABLES = ["application", "certification"]

# Pages (HTML web resources in webresources/): id -> (navigation label, web resource name).
# Put one in NAVIGATION as "page:<id>". The first navigation item is where the app opens.
PAGES = {
    "overview": ("Overview", "clt_/pages/overview.html"),
    "guides":   ("How-to guides", "clt_/pages/guides.html"),
}

# Navigation: (group title, [table or "page:<id>", ...])
NAVIGATION = [
    ("Start here",  ["page:overview", "page:guides"]),
    ("Portfolio",   ["property", "occupancy", "sale"]),
    ("People",      ["household"]),
    ("Stewardship", ["annualverification", "insurancepolicy", "homeownerrequest"]),
    ("Finance",     ["fee", "errrtransaction", "errrreconciliation"]),
    ("Settings",    ["listitem", "formsubmission", "sourceform"]),
]

# ---------------------------------------------------------------------------
# Views.
#   columns: [(field, width)]   sort: (field, descending) or a list of them
#   filters: [(field, operator, value)]  value for choices is the option label;
#            operators: eq, ne, in (value is a list), null, not-null, next-x-days
#   default=True updates the table's built-in "Active ..." view instead of adding one.
# ---------------------------------------------------------------------------
def v(table, name, columns, sort=None, filters=(), default=False, desc=""):
    return dict(table=table, name=name, columns=columns, sort=sort or ("name", False),
                filters=list(filters), default=default, desc=desc)

# Property status -> the name of its view (also the Overview tiles, in webresources/overview.html).
PROPERTY_STATUS_VIEWS = {
    "Owner-occupied": "Owner-occupied properties",
    "Rented": "Rented properties",
    "For sale": "Properties for sale",
    "Sale pending": "Properties with a sale pending",
    "Vacant": "Vacant properties",
    "Under construction": "Properties under construction",
    "Prospective acquisition": "Prospective acquisitions",
    "Left program": "Properties that left the program",
}
HOUSEHOLD_COLUMNS = [("recordnumber", 90), ("name", 200), ("status", 160), ("primaryemail", 200), ("phone", 130)]

VIEWS = [
    # Property
    v("property", None, [("recordnumber", 90), ("name", 200), ("neighborhood", 140), ("city", 120), ("status", 140),
                         ("propertytype", 150), ("bedrooms", 80), ("county", 120), ("?errrbalance", 120)], default=True),
    v("property", "Properties by neighborhood", [("neighborhood", 160), ("name", 200), ("status", 140),
                                                 ("propertytype", 150), ("bedrooms", 80), ("currentoccupancy", 200)],
      sort=[("neighborhood", False), ("name", False)], desc="Every active property, sorted by neighborhood"),
] + [
    # One view per property status: the Overview's figures. Left program has a view but no figure, and a
    # property with no status (a common area) is in none of them.
    v("property", name, [("recordnumber", 90), ("name", 200), ("neighborhood", 140), ("city", 120),
                         ("propertytype", 150), ("bedrooms", 80), ("currentoccupancy", 200)],
      filters=[("status", "eq", status)], desc=f"Active properties with status {status}")
    for status, name in PROPERTY_STATUS_VIEWS.items()
] + [
    # Household
    v("listitem", None, [("list", 140), ("name", 220), ("sortorder", 80), ("formanswers", 260)],
      sort=[("list", False), ("sortorder", False), ("name", False)], default=True),
    v("formsubmission", None, [("name", 220), ("formtype", 140), ("sourceform", 200), ("receivedon", 110),
                               ("status", 120), ("household", 160)], sort=("receivedon", True), default=True),
    v("sourceform", None, [("name", 260), ("provider", 130), ("externalformid", 90), ("formtype", 140),
                           ("project", 200)],
      sort=("name", False), default=True),
    v("formsubmission", "Submissions needing attention", [("name", 220), ("formtype", 140), ("provider", 120),
                                                          ("receivedon", 110), ("errordetail", 300)],
      sort=("receivedon", True), filters=[("status", "eq", "Needs attention")],
      desc="Form entries the intake flows could not process"),
    v("household", None, [("recordnumber", 90), ("name", 200), ("status", 160), ("primaryemail", 200), ("phone", 130),
                          ("certificationexpires", 130)], default=True),
    v("household", "Homeowners", HOUSEHOLD_COLUMNS, filters=[("status", "eq", "Homeowner")],
      desc="Households that own a home now"),
    v("household", "Former homeowners", HOUSEHOLD_COLUMNS, filters=[("status", "eq", "Past homeowner")],
      desc="Households that owned a home and have sold or left"),
    v("household", "Applicants", HOUSEHOLD_COLUMNS, filters=[("status", "eq", "Applicant")],
      desc="Households that have sent a screener and haven't been invited further"),
    v("household", "Potential purchasers", HOUSEHOLD_COLUMNS + [("certificationexpires", 130)],
      filters=[("status", "in", ["Invited to full application", "Eligible"])],
      desc="Households invited to the full application, or certified and waiting for a home"),
    v("householdmember", None, [("name", 180), ("applicantrole", 150), ("relationship", 160),
                                ("?age", 60), ("ontitle", 80), ("household", 180)], default=True),
    # Portfolio
    v("occupancy", None, [("recordnumber", 90), ("name", 200), ("property", 160), ("household", 160), ("role", 80),
                          ("status", 90), ("startdate", 100), ("resaleformula", 130),
                          ("?maximumresaleprice", 130)], default=True),
    v("occupancy", "Current occupancies", [("name", 200), ("property", 160), ("household", 160),
                                           ("startdate", 100), ("resaleformula", 130), ("?maximumresaleprice", 130)],
      filters=[("status", "eq", "Current")]),
    v("sale", None, [("recordnumber", 90), ("name", 200), ("property", 160), ("saletype", 120), ("status", 90),
                     ("contractdate", 100), ("closingdate", 100), ("purchaseprice", 120)],
      sort=("closingdate", True), default=True),
    v("sale", "Pending sales", [("name", 200), ("property", 160), ("selleroccupancy", 160),
                                ("buyerhousehold", 160), ("closingdate", 100), ("maxpriceatsale", 120),
                                ("purchaseprice", 120)],
      sort=("closingdate", False), filters=[("status", "eq", "Pending")]),
    # Stewardship
    v("annualverification", None, [("name", 200), ("occupancy", 180), ("year", 60), ("duedate", 100),
                                   ("status", 100), ("receiveddate", 100)], sort=("duedate", True), default=True),
    v("annualverification", "Verifications to do", [("name", 200), ("occupancy", 180), ("duedate", 100),
                                                    ("status", 100), ("sentdate", 100), ("receiveddate", 100)],
      sort=("duedate", False), filters=[("status", "in", ["Due", "Sent", "Received", "Issue found"])]),
    v("insurancepolicy", None, [("name", 180), ("occupancy", 180), ("carrier", 130), ("coveragea", 120),
                                ("renewaldate", 100), ("?coveragecheck", 120)], sort=("renewaldate", False), default=True),
    v("insurancepolicy", "Renewing in the next 60 days", [("name", 180), ("occupancy", 180), ("carrier", 130),
                                                          ("renewaldate", 100), ("verifieddate", 100)],
      sort=("renewaldate", False), filters=[("renewaldate", "next-x-days", 60)]),
    v("insurancepolicy", "Underinsured policies", [("name", 180), ("occupancy", 180), ("carrier", 130),
                                                   ("coveragea", 120), ("?totaldwellingcoverage", 130),
                                                   ("replacementcost", 120), ("?coveragegap", 110)],
      sort=("renewaldate", False), filters=[("?coveragecheck", "eq", "Underinsured")]),
    v("homeownerrequest", None, [("recordnumber", 90), ("name", 200), ("occupancy", 180), ("requesttype", 150),
                                 ("requestdate", 100), ("status", 140)], sort=("requestdate", True), default=True),
    v("homeownerrequest", "Open requests", [("name", 200), ("occupancy", 180), ("requesttype", 150),
                                            ("requestdate", 100), ("status", 140), ("estimatedcost", 110)],
      sort=("requestdate", False), filters=[("status", "in", ["Submitted", "Under review"])]),
    v("propertyfunding", None, [("name", 180), ("funder", 180), ("contractnumber", 120), ("targetami", 90),
                                ("covenantstart", 100), ("covenantend", 100)], default=True),
    # Finance
    v("fee", None, [("name", 180), ("property", 180), ("feetype", 120), ("amount", 100),
                    ("effectivestart", 100), ("effectiveend", 100)], default=True),
    v("fee", "Current ERRR rates", [("property", 180), ("amount", 100), ("effectivestart", 100), ("name", 180)],
      sort=("effectivestart", True), filters=[("feetype", "eq", "ERRR"), ("effectiveend", "null", None)]),
    v("errrtransaction", None, [("date", 100), ("property", 180), ("type", 150), ("amount", 100),
                                ("?signedamount", 100), ("qboreference", 120), ("name", 180)],
      sort=("date", True), default=True),
    v("errrreconciliation", None, [("name", 100), ("monthend", 100), ("qbobalance", 130),
                                   ("unallocatedinterest", 130), ("propertybalances", 130), ("?difference", 110)],
      sort=("monthend", True), default=True),
]

# ---------------------------------------------------------------------------
# Forms (each table's main "Information" form).
#   header: up to 4 fields shown across the top
#   tabs: [(tab label, [column, column?])]   column: [section]
#   section: (section label, [field | sub(...)])
# ---------------------------------------------------------------------------
def sub(label, child, lookup, parent, rows=6):
    """Related list: rows of `child` whose `lookup` points at this `parent` record."""
    return {"subgrid": True, "label": label, "child": child, "lookup": lookup,
            "relationship": f"clt_{parent}_{child}_{lookup}", "rows": rows}

def spdocs(parent, rows=10):
    """SharePoint documents for this record (needs documents= on the table in schema.py).
    Same as the form designer's Documents component: the record's SharePoint folder, on the form."""
    return {"subgrid": True, "sharepoint": True, "label": "Documents", "child": "sharepointdocument",
            "lookup": None, "relationship": f"clt_{parent}_SharePointDocuments", "rows": rows}

def tab(label, *columns):
    return (label, list(columns))

FORMS = {
    "property": dict(
        header=["status", "propertytype", "currentoccupancy", "?errrbalance"],
        tabs=[
            tab("Overview",
                [("Property", ["!recordnumber", "street", "unit", "city", "state", "county", "zip", "neighborhood",
                               "!name", "apn"]),
                 ("Details", ["propertytype", "bedrooms", "bathrooms", "squarefeet", "yearbuilt", "acquisitiondate"])],
                [("Program", ["status", "tenuretype", "amitarget", "currentoccupancy"]),
                 ("Replacement cost", ["replacementcost", "replacementcostdate"]),
                 ("Notes", ["notes"])]),
            tab("Occupancies and sales",
                [("Occupancies", [sub("Occupancies", "occupancy", "property", "property")]),
                 ("Sales", [sub("Sales", "sale", "property", "property", rows=4)])]),
            tab("Stewardship",
                [("Homeowner requests", [sub("Homeowner requests", "homeownerrequest", "property", "property")])]),
            tab("ERRR and fees",
                [("ERRR balance", ["?errrbalance", "?errrincreases", "?errrdecreases"]),
                 ("ERRR ledger", [sub("ERRR transactions", "errrtransaction", "property", "property", rows=10)])],
                [("Fee schedule", [sub("Fees", "fee", "property", "property", rows=5)])]),
            tab("Funding",
                [("Funding and covenants", [sub("Funding", "propertyfunding", "property", "property", rows=5)])]),
            tab("Documents",
                [("Documents", ["!documentsfolder", spdocs("property")])]),
        ]),

    "household": dict(
        header=["status", "primaryemail", "phone", "certificationexpires"],
        tabs=[
            tab("Overview",
                [("Contact", ["!recordnumber", "!name", "status", "primaryemail", "phone", "preferredlanguage"]),
                 ("Mailing address", ["mailingstreet", "mailingunit", "mailingcity", "mailingstate", "mailingzip"])],
                [("Income certification", ["certificationdate", "certificationexpires", "certifiedhouseholdsize",
                                           "certifiedincome", "certifiedamipercent"]),
                 ("Notes", ["notes"])]),
            tab("Members",
                [("Household members", [sub("Members", "householdmember", "household", "household")])]),
            tab("Applications and homes",
                [("Applications", [sub("Applications", "application", "household", "household", rows=4)]),
                 ("Certifications", [sub("Certifications", "certification", "household", "household", rows=4)]),
                 ("Occupancies", [sub("Occupancies", "occupancy", "household", "household", rows=4)])]),
            tab("Documents",
                [("Documents", ["!documentsfolder", spdocs("household")])]),
        ]),

    "householdmember": dict(
        header=["applicantrole", "relationship", "?age"],
        tabs=[
            tab("General",
                [("Person", ["name", "firstname", "lastname", "household", "applicantrole",
                             "relationship", "relationshipother"])],
                [("Details", ["dateofbirth", "?age", "?isadult", "email", "phone", "ontitle"]),
                 ("Integration", ["formitemid"])]),
        ]),

    "occupancy": dict(
        header=["status", "role", "startdate", "?maximumresaleprice"],
        tabs=[
            tab("Overview",
                [("Occupancy", ["!recordnumber", "property", "household", "!name", "role", "status", "startdate", "enddate"]),
                 ("Agreement", ["recordingnumber", "agreementversion"])],
                [("Notes", ["notes"])]),
            tab("Resale price",
                [("Formula", ["resaleformula", "baseprice", "basedate", "annualrate", "wholeyearsonly"]),
                 ("Appraisal share terms", ["appraisalatpurchase", "latestappraisal", "latestappraisaldate",
                                            "ownershare"])],
                [("Limits", ["floorbaseprice", "pricecap", "roundto"]),
                 ("Result", ["?rawformulaprice", "?formulaprice", "improvementcredits", "?maximumresaleprice"])]),
            tab("Stewardship",
                [("Annual verifications", [sub("Annual verifications", "annualverification", "occupancy", "occupancy", rows=5)]),
                 ("Insurance policies", [sub("Insurance policies", "insurancepolicy", "occupancy", "occupancy", rows=4)]),
                 ("Homeowner requests", [sub("Homeowner requests", "homeownerrequest", "occupancy", "occupancy", rows=5)])]),
            tab("Documents",
                [("Documents", ["!documentsfolder", spdocs("occupancy")])]),
        ]),

    "annualverification": dict(
        header=["status", "year", "duedate"],
        tabs=[
            tab("General",
                [("Verification", ["name", "occupancy", "year", "duedate", "status", "sentdate", "receiveddate"])],
                [("Findings", ["primaryresidence", "rentalstatus", "tenantdetails", "insurancereceived"]),
                 ("Form", ["verificationcode", "sentto", "formlink", "formentryid"]),
                 ("Notes", ["notes"])]),
        ]),

    "insurancepolicy": dict(
        header=["?coveragecheck", "renewaldate", "cltadditionalinsured"],
        tabs=[
            tab("General",
                [("Policy", ["name", "occupancy", "carrier", "policynumber", "effectivedate",
                             "renewaldate", "verifieddate", "cltadditionalinsured"])],
                [("Coverage", ["coveragea", "extendeddwelling", "?totaldwellingcoverage", "replacementcost",
                               "?coveragecheck", "?coveragegap", "liability", "deductible", "premium"]),
                 ("Notes", ["notes"])]),
        ]),

    "homeownerrequest": dict(
        header=["requesttype", "status", "requestdate"],
        tabs=[
            tab("General",
                [("Request", ["!recordnumber", "name", "occupancy", "property", "requesttype", "requestdate", "status", "details"])],
                [("Decision", ["decisiondate", "conditions", "estimatedcost", "approvedcredit", "approveddraw",
                               "completeddate"])]),
            tab("ERRR draws",
                [("ERRR transactions", [sub("ERRR transactions", "errrtransaction", "homeownerrequest",
                                            "homeownerrequest", rows=4)])]),
        ]),

    "sale": dict(
        header=["saletype", "status", "closingdate", "purchaseprice"],
        tabs=[
            tab("Sale",
                [("1. Property", ["!recordnumber", "name", "property", "saletype", "selleroccupancy"]),
                 ("2. Buyer and contract", ["buyerhousehold", "contractdate", "purchaseprice", "lender",
                                            "titlecompany"]),
                 ("3. Closing", ["closingdate", "status", "buyeroccupancy"])],
                [("Resale price (set when the sale is created)", ["maxpriceatsale", "formulapriceatsale",
                                                                  "creditsatsale", "appraisedvalue"]),
                 ("Notes", ["notes"])]),
        ]),

    "propertyfunding": dict(
        header=["funder", "targetami", "covenantend"],
        tabs=[
            tab("General",
                [("Funding", ["name", "property", "funder", "contractnumber", "targetami"]),
                 ("Covenant", ["covenantstart", "covenantyears", "covenantend"])],
                [("Notes", ["notes"])]),
        ]),
    "fee": dict(
        header=["feetype", "amount"],
        tabs=[
            tab("General",
                [("Fee", ["name", "property", "feetype", "amount", "effectivestart", "effectiveend"])],
                [("Notes", ["notes"])]),
        ]),

    "errrtransaction": dict(
        header=["type", "amount", "date"],
        tabs=[
            tab("General",
                [("Transaction", ["name", "property", "occupancy", "date", "type", "amount", "?signedamount"])],
                [("References", ["homeownerrequest", "qboreference", "postingkey"]),
                 ("Notes", ["notes"])]),
        ]),

    "listitem": dict(
        header=["list"],
        tabs=[
            tab("General",
                [("Value", ["list", "name", "sortorder", "state"])],
                [("Matching form answers", ["formanswers"]),
                 ("Description", ["description"])]),
        ]),

    "sourceform": dict(
        header=["provider", "formtype"],
        tabs=[tab("General", [("Form", ["name", "provider", "externalformid", "formtype"]),
                              ("Project", ["project"])],
                  [("Notes", ["notes"])])]),

    "formsubmission": dict(
        header=["formtype", "status", "receivedon"],
        tabs=[
            tab("General",
                [("Submission", ["name", "formtype", "sourceform", "provider", "externalentryid", "receivedon",
                                 "status", "entrylink"]),
                 ("Matched to", ["household", "application", "annualverification"])],
                [("Problems", ["errordetail"])]),
            tab("Submission data",
                [("Data", ["payload"])]),
        ]),

    "errrreconciliation": dict(
        header=["monthend", "?difference"],
        tabs=[
            tab("General",
                [("Reconciliation", ["name", "monthend", "qbobalance", "unallocatedinterest", "propertybalances",
                                     "?difference"])],
                [("Notes", ["notes"])]),
        ]),
}

# Web resources (webresources/), uploaded by build_app.py: form scripts and the pages above.
# Keep the scripts tiny; they're the only custom code on the forms.
WEB_RESOURCES = {
    "clt_/scripts/names.js":    "webresources/names.js",
    "clt_/scripts/tips.js":     "webresources/tips.js",
    "clt_/pages/pages.css":     "webresources/pages.css",
    "clt_/pages/pages.js":      "webresources/pages.js",
    "clt_/pages/overview.html": "webresources/overview.html",
    "clt_/pages/guides.html":   "webresources/guides.html",
}
# table -> [(event, field or None, function)]. Events: onload, onsave, onchange (needs a field).
FORM_SCRIPTS = {
    "property":        [("onchange", "street", "CLT.Names.property"), ("onchange", "unit", "CLT.Names.property"),
                        ("onsave", None, "CLT.Names.property"), ("onload", None, "CLT.Tips.documents")],
    "occupancy":       [("onchange", "household", "CLT.Names.occupancy"), ("onchange", "property", "CLT.Names.occupancy"),
                        ("onsave", None, "CLT.Names.occupancy"), ("onload", None, "CLT.Tips.documents")],
    "householdmember": [("onsave", None, "CLT.Names.member")],
    "household":       [("onload", None, "CLT.Names.household"), ("onload", None, "CLT.Tips.documents")],
}
# Which web resource holds each script namespace (CLT.Names.property lives in names.js).
SCRIPT_LIBRARIES = {"CLT.Names": "clt_/scripts/names.js", "CLT.Tips": "clt_/scripts/tips.js"}

# Lookups whose choices depend on another field on the same form:
# (table, lookup) -> (field on the form, relationship on the target that must match it).
# Property's County dropdown only shows counties whose State matches the property's State.
DEPENDENT_LOOKUPS = {
    ("property", "county"): ("state", "clt_listitem_listitem_state"),
}

# Formula and rollup columns to add by hand in step 4, with the schema name to use
# (Advanced options > Schema name). The app build places them once they exist.
MANUAL_COLUMNS = [
    ("occupancy", "rawformulaprice", "Raw formula price", "Formula"),
    ("occupancy", "formulaprice", "Formula price", "Formula"),
    ("occupancy", "maximumresaleprice", "Maximum resale price", "Formula"),
    ("householdmember", "age", "Age", "Formula"),
    ("householdmember", "isadult", "Is adult", "Formula"),
    ("insurancepolicy", "totaldwellingcoverage", "Total dwelling coverage", "Formula"),
    ("insurancepolicy", "coveragecheck", "Coverage check", "Formula"),
    ("insurancepolicy", "coveragegap", "Coverage gap", "Formula"),
    ("errrtransaction", "signedamount", "Signed amount", "Formula"),
    ("property", "errrincreases", "ERRR increases", "Rollup"),
    ("property", "errrdecreases", "ERRR decreases", "Rollup"),
    ("property", "errrbalance", "ERRR balance", "Formula"),
    ("errrreconciliation", "difference", "Difference", "Formula"),
]
