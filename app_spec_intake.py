"""
CLT Intake & Selection: the second model-driven app (navigation, views, forms).

Built by the same code as CLT Stewardship:  python3 build_app.py --app intake --url ...
Projects, screeners and applications, selection (lottery or first come first served), certification,
document checklists and notices. Design: docs/DESIGN.md ("Two apps", "Eligibility, selection and
certification", "Blind lottery"). Tables are tagged solution="intake" in schema.py.

Blind lottery: names are visible on applications, but the lists the Board Observer sees (selection
entry views) show Unique IDs only, never the application or household.
"""
from app_spec import v, sub, tab, spdocs  # noqa: F401  (same helpers as the core app)

APP = {
    "name": "CLT Intake & Selection",
    "uniquename": "clt_CLTIntake",
    "description": "Projects, applications, selection and certification for community land trusts.",
}

# Pages (webresources/), sharing styles with the core app's pages. The first navigation item is where the app opens.
PAGES = {"intake": ("Hub", "clt_/pages/intake.html"),                # figures and what needs attention
         "guide":  ("How it works", "clt_/pages/intake-guide.html"),  # the steps, from screener to handoff
         "assign": ("Add to a project", "clt_/pages/assign.html"),
         "prescreen": ("Pre-screen", "clt_/pages/prescreen.html")}   # test a project's screeners against its rules

NAVIGATION = [
    ("Start here", ["page:intake", "page:guide"]),
    ("Projects",   ["project", "page:assign", "page:prescreen", "selectionround"]),
    ("Applicants", ["application", "household", "certification"]),
    ("Messages",   ["notice", "formsubmission"]),
    ("Settings",   ["eligibility", "incomelimitset", "listitem", "sourceform"]),
]

# Reached through related lists and lookups, not navigation.
APP_TABLES = ["projectpriority", "projecthome", "lotteryfactor", "selectionentry", "entryfactor",
              "eligibilitycheck", "checklistitem", "incomesource", "debt", "asset", "householdmember",
              "property", "propertyfunding"]

VIEWS = [
    # Projects
    v("project", None, [("name", 220), ("projecttype", 150), ("status", 150), ("selectionmethod", 150),
                        ("applicationopens", 110), ("applicationcloses", 110)], default=True),
    v("project", "Open projects", [("name", 220), ("projecttype", 150), ("status", 150), ("selectionmethod", 150),
                                   ("applicationcloses", 110)],
      filters=[("status", "ne", "Closed")]),
    v("projectpriority", None, [("name", 160), ("bedrooms", 80), ("householdsize", 110), ("tier", 60),
                                ("preference", 200)], sort=[("bedrooms", False), ("tier", False)], default=True),
    v("projecthome", None, [("name", 200), ("property", 180), ("bedrooms", 80), ("estimatedprice", 120),
                            ("estimatedmonthlycost", 130), ("status", 100)], sort=("bedrooms", False), default=True),
    v("lotteryfactor", None, [("name", 220), ("extrachances", 100), ("active", 70), ("fairhousingreviewed", 130)],
      default=True),
    # Selection: Unique IDs only (blind lottery)
    v("selectionround", None, [("name", 240), ("project", 180), ("method", 140), ("status", 120),
                               ("poolslockedon", 140), ("drawnon", 140)], sort=("drawnon", True), default=True),
    v("selectionentry", None, [("uniqueid", 90), ("bedrooms", 70), ("tier", 50), ("chances", 70),
                               ("lotterynumber", 120), ("rankingkey", 120), ("rank", 60), ("status", 130),
                               ("statusreason", 200)],
      sort=[("bedrooms", False), ("rank", False)], default=True,
      desc="Ranked lists by bedroom size. Unique IDs only, for the Board Observer."),
    v("selectionentry", "Pool lists (for the Board Observer)", [("uniqueid", 90), ("bedrooms", 70),
                                                                ("householdsize", 90), ("tier", 50), ("chances", 70)],
      sort=[("bedrooms", False), ("uniqueid", False)],
      desc="What the Board Observer initials at the lock: Unique ID, list, tier and chances. No names."),
    v("entryfactor", None, [("name", 200), ("factor", 200), ("verified", 80)], default=True),
    # Applicants
    # Also the Applications list on the Household form: the self-declared figures and eligibility.
    v("application", None, [("recordnumber", 90), ("name", 200), ("household", 180), ("stage", 170),
                            ("screenersubmitted", 110), ("statedannualincome", 120), ("householdsize", 80),
                            ("statednonretirementassets", 120), ("amipct", 80), ("iseligible", 80),
                            ("orgeligibility", 260), ("project", 150), ("sourceform", 180)], default=True),
    v("application", "New screeners", [("name", 200), ("household", 180), ("screenersubmitted", 120),
                                       ("county", 110), ("statedannualincome", 130), ("amipct", 90),
                                       ("adults", 70), ("children", 70)],
      sort=("screenersubmitted", True), filters=[("stage", "eq", "Screener submitted")],
      desc="Screeners waiting for a decision to invite"),
    v("application", "Not in a project yet", [("name", 200), ("household", 180), ("screenersubmitted", 120),
                                              ("county", 110), ("statedannualincome", 130), ("amipct", 90), ("adults", 70),
                                              ("children", 70), ("homesizes", 150), ("sourceform", 180)],
      sort=("screenersubmitted", False), filters=[("project", "null", None)],
      desc="Screeners not added to a project yet. Tick rows, Edit, pick the Project."),
    v("application", "Screeners", [("name", 200), ("household", 180), ("sourceform", 180), ("project", 160),
                                    ("stage", 150), ("screenersubmitted", 120), ("county", 110),
                                    ("statedannualincome", 130), ("amipct", 90), ("homesizes", 150)],
      sort=("screenersubmitted", True), filters=[("screenerentryid", "not-null", None)],
      desc="Every application that came in through a screener"),
    v("application", "Full applications in progress", [("name", 200), ("household", 180), ("project", 160),
                                                       ("stage", 170), ("fullappentryid", 110)],
      sort=("name", False), filters=[("stage", "in", ["Invited to full application", "Full application incomplete"])],
      desc="Invited to the full application, or started it, and not submitted yet"),
    v("application", "Full applications submitted", [("name", 200), ("household", 180), ("project", 160),
                                                     ("stage", 170), ("fullappsubmitted", 120)],
      sort=("fullappsubmitted", True), filters=[("fullappsubmitted", "not-null", None)],
      desc="Every application whose full application has been submitted"),
    v("application", "Applications in review", [("name", 200), ("household", 180), ("stage", 170),
                                                ("fullappsubmitted", 120), ("?verifiedannualincome", 130),
                                                ("?incomepctami", 100)],
      sort=("fullappsubmitted", False),
      filters=[("stage", "in", ["Full application submitted", "In review", "Needs follow-up"])],
      desc="Full applications staff need to review"),
    v("incomesource", None, [("name", 180), ("member", 150), ("incometype", 160), ("payfrequency", 110),
                             ("grosspayperperiod", 120), ("?annualizedincome", 120),
                             ("verifiedannualamount", 120), ("reviewstatus", 110)], default=True),
    v("debt", None, [("name", 160), ("member", 150), ("debttype", 160), ("monthlypayment", 110),
                     ("verifiedmonthlypayment", 120), ("reviewstatus", 110)], default=True),
    v("asset", None, [("name", 160), ("member", 150), ("assettype", 180), ("currentvalue", 120),
                      ("verifiedvalue", 120), ("reviewstatus", 110)], default=True),
    v("application", "Pre-screen needs review", [("name", 200), ("project", 160), ("uniqueid", 90),
                                                  ("prescreenresult", 150), ("prescreennotes", 260)],
      sort=("name", False), filters=[("prescreenresult", "eq", "Needs review")],
      desc="Screeners the automatic pre-screen couldn't decide"),
    v("certification", None, [("name", 220), ("household", 180), ("project", 160), ("status", 150),
                              ("certifiedon", 130), ("expireson", 100)], sort=("certifiedon", True), default=True),
    v("certification", "Certifications in progress", [("name", 220), ("household", 180), ("project", 160),
                                                      ("status", 150), ("checksrunon", 130)],
      sort=("name", False), filters=[("status", "in", ["Reviewing", "Waiting for more information"])]),
    v("eligibilitycheck", None, [("name", 200), ("stage", 110), ("test", 150), ("value", 100), ("limit", 100),
                                 ("result", 100)], default=True),
    v("checklistitem", None, [("name", 220), ("member", 160), ("status", 110), ("documentdate", 110),
                              ("receivedon", 110), ("reviewedon", 110)], default=True),
    v("checklistitem", "Documents to review", [("name", 220), ("certification", 200), ("member", 160),
                                               ("receivedon", 110)],
      sort=("receivedon", False), filters=[("status", "eq", "Received")]),
    # Messages
    v("notice", None, [("name", 240), ("noticetype", 170), ("channel", 100), ("senton", 140), ("sentto", 200)],
      sort=("senton", True), default=True),
    # Settings
    v("eligibility", None, [("name", 220), ("maxami", 110), ("minami", 110), ("firsttimebuyer", 110),
                            ("housingratiomax", 110), ("debtratiomax", 110)], default=True),
    v("incomelimitset", None, [("name", 180), ("county", 140), ("year", 70), ("limitsource", 80), ("size1", 100),
                               ("size4", 100), ("size8", 100), ("medianfamilyincome", 120)],
      sort=[("year", True), ("name", False)], default=True),
]

FORMS = {
    "project": dict(
        header=["projecttype", "status", "selectionmethod", "applicationcloses"],
        tabs=[
            tab("General",
                [("Project", ["name", "projecttype", "status", "applicationopens", "applicationcloses"]),
                 ("Selection", ["selectionmethod", "rolling", "listsource", "reuseround"])],
                [("Eligibility (blank uses the organization's rules)",
                  ["maxami", "minami", "firsttimebuyer", "localtie", "localarea", "assetlimit", "housingratiomax",
                   "debtratiomax", "education", "validdays"]),
                 ("Pre-screen", ["incomebuffer", "housingratiobuffer", "debtratiobuffer", "mincreditrange",
                                 "bankruptcyyears", "minaffordabilitycheck"]),
                 ("Monthly housing cost by home size (mortgage, taxes, insurance, dues and lease fee)",
                  ["monthlycoststudio", "monthlycost1br", "monthlycost2br", "monthlycost3br", "monthlycost4br"]),
                 ("Invitations and lists", ["invitesperlist", "invitesperhome", "responsedays", "waitlistmonths"]),
                 ("Notes", ["notes"])]),
            tab("Homes",
                [("Homes", [sub("Homes", "projecthome", "project", "project", rows=6)])]),
            tab("Priorities",
                [("Who can apply for each home size, and in which tier",
                  [sub("Priorities", "projectpriority", "project", "project", rows=10)])],
                [("Lottery factors (extra chances; needs a fair housing review)",
                  [sub("Lottery factors", "lotteryfactor", "project", "project", rows=5)])]),
            tab("Applications and selection",
                [("Applications", [sub("Applications", "application", "project", "project", rows=10)]),
                 ("Selection rounds", [sub("Selection rounds", "selectionround", "project", "project", rows=3)])],
                [("Certifications", [sub("Certifications", "certification", "project", "project", rows=6)])]),
            tab("Documents",
                [("Documents", [spdocs("project")])]),
        ]),
    "projectpriority": dict(
        header=["bedrooms", "householdsize", "tier"],
        tabs=[tab("General", [("Priority", ["name", "project", "bedrooms", "householdsize", "tier", "preference"])],
                  [("Notes", ["notes"])])]),
    "projecthome": dict(
        header=["bedrooms", "status", "estimatedprice"],
        tabs=[tab("General", [("Home", ["name", "project", "property", "bedrooms", "status"])],
                  [("Price and cost", ["targetami", "estimatedprice", "estimatedmonthlycost"])])]),
    "lotteryfactor": dict(
        header=["extrachances", "active", "fairhousingreviewed"],
        tabs=[tab("General",
                  [("Factor", ["name", "project", "extrachances", "active", "definition"]),
                   ("How it's decided", ["questionkey", "qualifyinganswers", "proof"])],
                  [("Basis and review", ["basis", "fairhousingreviewed"])])]),
    "selectionround": dict(
        header=["method", "status", "drawnon"],
        tabs=[
            tab("Round",
                [("Round", ["name", "project", "method", "status"]),
                 ("Lock", ["poolslockedon", "!checknumbers", "observer"])],
                [("Draw", ["diceroll", "!seed", "!drawnon", "!drawnby", "certifiedon", "listsendon"])]),
            tab("Lists",
                [("Ranked lists (Unique IDs only)",
                  [sub("Entries", "selectionentry", "round", "selectionround", rows=15)])]),
        ]),
    "selectionentry": dict(
        header=["bedrooms", "tier", "rank", "status"],
        tabs=[tab("General",
                  [("Entry", ["name", "round", "application", "!uniqueid", "!bedrooms", "!householdsize", "!tier"]),
                   ("Ranking", ["!chances", "!submittedon", "!lotteryseq", "!lotterynumber", "!rankingkey", "!rank"])],
                  [("Status", ["status", "statusreason", "statusdate", "invitedon", "responsedue"]),
                   ("Lottery factors", [sub("Factors", "entryfactor", "entry", "selectionentry", rows=4)])])]),
    "entryfactor": dict(
        header=["verified"],
        tabs=[tab("General", [("Factor", ["name", "entry", "factor", "verified"])], [("Notes", ["notes"])])]),
    "certification": dict(
        header=["status", "household", "project", "expireson"],
        tabs=[
            tab("Review",
                [("Certification", ["name", "household", "application", "project", "status"]),
                 ("Income", [sub("Income sources", "incomesource", "certification", "certification", rows=6)])],
                [("Debts", [sub("Debts", "debt", "certification", "certification", rows=4)]),
                 ("Assets", [sub("Assets", "asset", "certification", "certification", rows=4)])]),
            tab("Documents",
                [("Checklist", [sub("Checklist", "checklistitem", "certification", "certification", rows=12)])],
                [("Open at certification", ["!opendocuments"])]),
            tab("Certify",
                [("Certified figures", ["certifiedsize", "certifiedincome", "certifiedassets", "certifiedmonthlydebt"]),
                 ("Affordability inputs", ["estprice", "estloan", "estrate", "estterm", "esttaxes", "estinsurance",
                                           "estmi", "estdues", "estlandlease", "estutilities"])],
                [("Result", ["!certifiedon", "!certifiedby", "expireson", "limitset", "!limityear", "!ami100",
                             "!checksrunon", "notcertifiedreason"]),
                 ("Checks", [sub("Eligibility checks", "eligibilitycheck", "certification", "certification", rows=8)])]),
        ]),
    "eligibilitycheck": dict(
        header=["stage", "test", "result"],
        tabs=[tab("General", [("Check", ["name", "stage", "test", "value", "limit", "result"]),
                              ("For", ["application", "certification"])], [("Working", ["notes"])])]),
    "checklistitem": dict(
        header=["status", "documentdate", "receivedon"],
        tabs=[tab("General", [("Document", ["name", "certification", "member", "status"])],
                  [("Dates", ["documentdate", "receivedon", "reviewedon", "reviewedby"]), ("Note", ["note"])])]),
    "notice": dict(
        header=["noticetype", "channel", "senton"],
        tabs=[tab("General", [("Notice", ["name", "noticetype", "channel", "senton", "sentto"]),
                              ("About", ["application", "household", "project"])], [("Message", ["body"])])]),
    "eligibility": dict(
        header=["maxami", "firsttimebuyer"],
        tabs=[tab("General",
                  [("Income", ["name", "maxami", "minami", "assetlimit"]),
                   ("Ratios", ["housingratiomax", "debtratiomax"])],
                  [("Requirements", ["firsttimebuyer", "localtie", "localarea", "education", "validdays"]),
                   ("Notes", ["notes"])])]),
    "incomelimitset": dict(
        header=["county", "year", "limitsource"],
        tabs=[tab("General",
                  [("Limits", ["name", "county", "year", "limitsource", "source", "effectivedate",
                               "medianfamilyincome"]),
                   ("Notes", ["notes"])],
                  [("50% (very low income) limit by household size",
                    [f"size{n}" for n in range(1, 9)])])]),
    "application": dict(
        header=["stage", "household", "iseligible", "prescreenresult"],
        tabs=[
            tab("Summary",
                [("Application", ["!recordnumber", "name", "household", "stage", "program", "decisiondate"]),
                 ("Selection", ["project", "!uniqueid", "!firstsubmittedon", "!answersfrozenon", "prescreenresult",
                                "!prescreensizes", "!prescreenedon", "prescreenoverridden", "prescreennotes"]),
                 ("Staff review", ["ami100", "?verifiedannualincome", "?incomepctami", "?verifiedassets",
                                   "?verifiedmonthlydebt", "reviewnotes"])],
                [("Organization eligibility (from the screener)",
                  ["!orgeligibility", "!iseligible", "!householdsize", "!amipct", "eligibilityrules", "amilimits",
                   "!limit50forsize"]),
                 ("Screener answers (self-reported, read-only)",
                  ["!statedannualincome", "!statednonretirementassets", "!statedretirementassets",
                   "!statedmonthlydebt", "!creditrange", "!adults", "!children", "!householdcountsasentered",
                   "!homesizes"])]),
            tab("Eligibility",
                [("Residency and housing", ["!county", "!localtie", "!localtiemethod", "!housingstatus", "!housingstatusother", "!primaryresidence"]),
                 ("First-time buyer", ["!firsttimebuyer", "!fthbexceptions", "!ownsproperty"])],
                [("Readiness", ["!incomepastyear", "!age62", "!has1000forclosing", "!hbeducation", "!preapproval"]),
                 ("Credit", ["!bankruptcy3yrs"])]),
            tab("Full application",
                [("Income and housing", ["!expectsincomechange", "!incomechangedetails", "!adultwithnoincome",
                                         "!noincomedetails", "!currenthousingcost"]),
                 ("Residency and first-time buyer", ["!residencydetails", "!ownedhome3yrs", "!fthbcertified"])],
                [("Credit and gifts", ["!latepayments", "!latepaymentsexplanation", "!bankruptcyexplanation",
                                       "!creditexplanation", "!giftfunds", "!giftamount", "!giftgiver"]),
                 ("Lender and homebuyer education", ["lender", "loanofficeremail", "loanofficerphone",
                                                     "!hbeducationdetails"]),
                 ("Comments", ["!fullappcomments"])]),
            tab("Income, debts and assets",
                [("Income", [sub("Income sources", "incomesource", "application", "application")]),
                 ("Debts", [sub("Debts", "debt", "application", "application", rows=4)]),
                 ("Assets", [sub("Assets", "asset", "application", "application", rows=4)])]),
            tab("Selection and certification",
                [("Pre-screen checks", [sub("Eligibility checks", "eligibilitycheck", "application", "application", rows=6)]),
                 ("Lists", [sub("Selection entries", "selectionentry", "application", "application", rows=4)])],
                [("Certifications", [sub("Certifications", "certification", "application", "application", rows=3)]),
                 ("Notices", [sub("Notices", "notice", "application", "application", rows=4)])]),
            tab("Forms",
                [("Screener", ["sourceform", "screenerentryid", "screenersubmitted", "screenerlink"]),
                 ("Full application", ["fullappentryid", "fullappsubmitted", "fullapplink"])],
                [("Applicant comments", ["!accommodation", "!applicantquestions"])]),
        ]),
    "incomesource": dict(
        header=["incometype", "reviewstatus", "?annualizedincome", "verifiedannualamount"],
        tabs=[
            tab("General",
                [("Income", ["name", "application", "member", "memberasentered", "incometype", "incometypeother",
                             "payer", "jobtitle", "startdate", "incomestatus", "enddate"])],
                [("Pay", ["payfrequency", "grosspayperperiod", "hoursperperiod", "annualbonus", "annualovertime",
                          "paystubenddate", "ytdgross", "?annualizedincome"]),
                 ("Review", ["reviewstatus", "verifiedannualamount", "reviewnotes", "applicantnotes"]),
                 ("Integration", ["formitemid"])]),
        ]),
    "debt": dict(
        header=["debttype", "reviewstatus", "verifiedmonthlypayment"],
        tabs=[
            tab("General",
                [("Debt", ["name", "application", "member", "memberasentered", "debttype", "debttypeother",
                           "creditor", "description"])],
                [("Amounts", ["monthlypayment", "remainingbalance"]),
                 ("Review", ["reviewstatus", "verifiedmonthlypayment"]),
                 ("Integration", ["formitemid"])]),
        ]),
    "asset": dict(
        header=["assettype", "reviewstatus", "verifiedvalue"],
        tabs=[
            tab("General",
                [("Asset", ["name", "application", "member", "holderasentered", "assettype", "assettypeother",
                            "institution", "description"])],
                [("Value", ["currentvalue"]),
                 ("Review", ["reviewstatus", "verifiedvalue"]),
                 ("Integration", ["formitemid"])]),
        ]),
}

WEB_RESOURCES = {
    "clt_/pages/pages.css":   "webresources/pages.css",
    "clt_/pages/pages.js":    "webresources/pages.js",
    "clt_/pages/intake.html": "webresources/intake.html",
    "clt_/pages/intake-guide.html": "webresources/intake-guide.html",
    "clt_/pages/assign.html": "webresources/assign.html",
    "clt_/pages/prescreen.html": "webresources/prescreen.html",
    "clt_/pages/prescreen.js": "webresources/prescreen.js",
}
FORM_SCRIPTS = {}
SCRIPT_LIBRARIES = {}
DEPENDENT_LOOKUPS = {}

# Formula and rollup columns added by hand (docs/STEP4-columns.md). Moved from the core app spec with the forms.
MANUAL_COLUMNS = [
    ("incomesource", "annualizedincome", "Annualized income", "Formula"),
    ("application", "verifiedannualincome", "Verified annual income", "Rollup"),
    ("application", "verifiedassets", "Verified assets", "Rollup"),
    ("application", "verifiedmonthlydebt", "Verified monthly debt", "Rollup"),
    ("application", "incomepctami", "Income as % of AMI", "Formula"),
]
