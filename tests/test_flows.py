"""Offline test: build_flows.py definitions and deployment against a fake Dataverse."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import build_schema as b  # noqa: E402
import build_flows as bf  # noqa: E402
import form_mapping  # noqa: E402
import schema  # noqa: E402
from test_offline import Resp  # noqa: E402


class Fake:
    def __init__(self):
        self.refs, self.flows, self.writes = {}, {}, []

    def request(self, method, url, headers=None, data=None, timeout=None):
        path = url.split("/api/data/v9.2/", 1)[1]
        body = json.loads(data) if data else None
        if method != "GET":
            self.writes.append((method, path.split("(")[0]))
            assert headers.get("MSCRM.SolutionUniqueName") == "CLTStewardship", "flows must go in the solution"
        if path == "WhoAmI":
            return Resp(200, {"UserId": "u-1"})
        if path.startswith("systemusers(u-1)"):
            return Resp(200, {"fullname": "CLT Flow Automation", "domainname": "automation@example.org"})
        if path.startswith("connectionreferences"):
            if method == "GET":
                name = re.search(r"logicalname eq '(\w+)'", path)[1]
                return Resp(200, {"value": [v for k, v in self.refs.items() if k == name]})
            self.refs[body["connectionreferencelogicalname"]] = {"connectionreferenceid": "x", "connectionid": None}
            return Resp(204)
        if path.startswith("workflows"):
            one = re.match(r"workflows\(([\w-]+)\)", path)
            if method == "GET" and one:
                return Resp(200, self.flows[one[1]])
            if method == "GET":
                wid = re.search(r"workflowid eq ([\w-]+)", path)[1]
                return Resp(200, {"value": [{"workflowid": wid, **self.flows[wid]}] if wid in self.flows else []})
            if method == "POST":
                assert body["category"] == 5
                self.flows[body["workflowid"]] = {"clientdata": body["clientdata"], "statecode": 0}
                return Resp(204)
            if "clientdata" in body and self.flows[one[1]]["statecode"] == 1:
                body = {**body, "statecode": 0}  # like Dataverse: an update can switch the flow off
            self.flows[one[1]].update(body)
            return Resp(204)
        raise AssertionError(f"unexpected {method} {path}")


def screener_checks(flow):
    import schema
    import flows_intake as fi
    fi.use_form(form_mapping.mappings(bf.EXAMPLE)[0])
    defn = flow["definition"]
    cd = json.loads(bf.clientdata(flow))
    assert set(cd["properties"]["connectionReferences"]) == {bf.DATAVERSE}, "screener intake uses Dataverse only"
    tables = {t["name"]: t for t in schema.TABLES}
    lookups = {(c, n): p for c, n, p, *_ in schema.LOOKUPS}
    cols = lambda t: {c["name"]: c for c in tables[t]["columns"]} | {"name": {"kind": "text"}}
    sets = {fi.es(t): t for t in ("household", "householdmember", "application", "formsubmission", "listitem", "sourceform", "project")}
    # every column written exists on its table (lookups via @odata.bind)
    written = 0
    for a in bf._actions(defn):
        if a.get("type") != "OpenApiConnection" or a["inputs"]["host"]["operationId"] not in ("CreateRecord", "UpdateRecord"):
            continue
        p = a["inputs"]["parameters"]
        if p["entityName"] == "annotations":
            continue
        table = sets[p["entityName"]]
        for k in p:
            if not k.startswith("item/"):
                continue
            written += 1
            col = k[5:].removeprefix("clt_")
            if col.endswith("@odata.bind"):
                assert (table, col[:-11]) in lookups, f"{table}.{col}: no such lookup"
            else:
                assert col in cols(table), f"{table}.{col}: no such column"
    assert written > 40, written
    # field kinds match the schema, and choice maps use real labels
    app = cols("application")
    kinds = {"yesno": "bool", "money": "money", "int": "int", "text": ("text", "memo")}
    for col, kind, path in fi.SCREENER_FIELDS:
        want = kinds.get(kind) or ("choice" if kind.startswith("choice:") else "multi")
        assert app[col]["kind"] in (want if isinstance(want, tuple) else (want,)), (col, app[col]["kind"], kind)
        if ":" in kind:
            assert app[col]["choice"] == kind.split(":")[1], col
    maps = fi.choice_maps()
    for name, m in maps.items():
        labels = schema.CHOICES[name][1]
        assert all(fi.CHOICE_BASE <= v < fi.CHOICE_BASE + len(labels) for v in m.values()), name
    # the sample entry has every path the flow reads, and its answers are all in the maps
    sample = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "cognito-screener-entry.json")))
    text = json.dumps(defn)
    for path in set(re.findall(r"triggerBody\(\)((?:\?\['\w+'\])+)", text)):
        node = sample
        for key in re.findall(r"'(\w+)'", path):
            assert isinstance(node, dict) and key in node, f"sample entry has no {path}"
            node = node[key]
    for col, kind, path in fi.SCREENER_FIELDS:
        v = sample
        for key in path:
            v = v[key]
        if kind.startswith("choice:"):
            assert v in maps[kind[7:]], (col, v)
        if kind == "multi:homesize":
            assert all(x in maps["homesize"] for x in v), (col, v)
    # every action named in outputs()/body()/result() exists, and every variable is initialized
    names, actions_by_name = set(), {}
    for scope in bf._scopes(defn):
        names |= set(scope)
        actions_by_name.update(scope)
    for ref in set(re.findall(r"(?:outputs|body|result)\('(\w+)'\)", text)):
        assert ref in names, f"refers to missing action {ref}"
    init = {v["name"] for a in defn["actions"].values() if a.get("type") == "InitializeVariable"
            for v in a["inputs"]["variables"]}
    used = set(re.findall(r"variables\('(\w+)'\)", text)) | {a["inputs"]["name"] for a in bf._actions(defn)
                                                              if a.get("type") == "SetVariable"}
    assert used <= init, used - init
    # expressions are balanced
    for s in re.findall(r'"@\{?(.*?)\}?"(?=[,}\]])', text):
        assert s.count("(") == s.count(")"), s[:120]
    # the frozen case flags the submission and never updates the application or its lists
    assert "Remember_frozen_change" in names and "Update_application" in names
    assert "annotations" not in text and "objectid_" not in text   # the connector rejects note links
    mark = defn["actions"]["Mark_processed"]["inputs"]["parameters"]
    assert "FrozenChange" in mark["item/clt_status"] and "item/clt_application@odata.bind" in mark
    # the source form is found or added, and linked from the submission and the application
    assert "Find_source_form" in names and "Create_source_form" in names
    # a form that names a project adds new applications to it (only new ones: staff may have moved others)
    assert "item/clt_project@odata.bind" in actions_by_name["Add_to_form_project"]["inputs"]["parameters"]
    assert "Add_to_form_project" not in str(defn["actions"]["Process_screener"]["actions"]["If_application_exists"]["actions"])
    assert "item/clt_sourceform@odata.bind" in mark
    for a in ("Create_application", "Update_application"):
        assert "item/clt_sourceform@odata.bind" in actions_by_name[a]["inputs"]["parameters"], a
    assert defn["triggers"]["When_Cognito_posts_a_screener"]["runtimeConfiguration"]["concurrency"]["runs"] == 1
    assert defn["triggers"]["When_Cognito_posts_a_screener"]["inputs"]["triggerAuthenticationType"] == "All"
    # new applications are named "Smith - A-00012" from the record number the create returns
    name = actions_by_name["Name_application"]["inputs"]["parameters"]["item/clt_name"]
    assert "body/clt_recordnumber" in name and "' - '" in name, name
    # % of AMI is a formula column: the flow only links the county's newest HUD AMI Limits record
    find = actions_by_name["Find_ami_limits"]["inputs"]["parameters"]
    assert find["entityName"] == "clt_incomelimitsets" and "clt_limitsource eq 768270000" in find["$filter"]
    assert find["$orderby"] == "clt_year desc" and find["$top"] == 1
    link = actions_by_name["Set_ami_limits"]["inputs"]["parameters"]
    assert link["item/clt_amilimits@odata.bind"].startswith("/clt_incomelimitsets(")
    rules = actions_by_name["Set_eligibility_rules"]["inputs"]["parameters"]
    assert rules["item/clt_eligibilityrules@odata.bind"].startswith("/clt_eligibilities(")
    assert actions_by_name["Find_eligibility_rules"]["inputs"]["parameters"]["$filter"] == "statecode eq 0"
    assert "Set_stated_ami" not in names and "clt_amipct" not in text and "clt_statedamipct" not in text
    # a failed run records only the steps that didn't succeed
    assert "Failed_steps" in defn["actions"]["Mark_needs_attention"]["runAfter"]


def find_action(actions, name):
    """An action by name, at any depth (inside scopes, conditions and loops)."""
    for k, a in actions.items():
        if k == name:
            return a
        for nested in (a.get("actions"), (a.get("else") or {}).get("actions")):
            hit = find_action(nested, name) if nested else None
            if hit:
                return hit
    return None


def full_app_checks(flow):
    import schema
    import flows_intake as fi
    import flows_full_app as fa
    fa.use_form(form_mapping.mappings(bf.EXAMPLE)[1])
    defn = flow["definition"]
    text = json.dumps(defn)
    assert set(json.loads(bf.clientdata(flow))["properties"]["connectionReferences"]) == {bf.DATAVERSE}
    tables = {t["name"]: t for t in schema.TABLES}
    lookups = {(c, n) for c, n, *_ in schema.LOOKUPS}
    cols = lambda t: {c["name"]: c for c in tables[t]["columns"]} | {"name": {"kind": "text"}}
    sets = {fi.es(t): t for t in ("household", "householdmember", "application", "formsubmission", "listitem",
                                  "sourceform", "incomesource", "debt", "asset")}
    written = {}
    for a in bf._actions(defn):
        if a.get("type") != "OpenApiConnection" or a["inputs"]["host"]["operationId"] not in ("CreateRecord", "UpdateRecord"):
            continue
        p = a["inputs"]["parameters"]
        table = sets[p["entityName"]]
        for k in p:
            if k.startswith("item/"):
                col = k[5:].removeprefix("clt_")
                written.setdefault(table, set()).add(col)
                if col.endswith("@odata.bind"):
                    assert (table, col[:-11]) in lookups, f"{table}.{col}: no such lookup"
                else:
                    assert col in cols(table), f"{table}.{col}: no such column"
    # staff review fields are never written by the flow
    for t in ("incomesource", "debt", "asset"):
        assert not {c for c in written[t] if c.startswith("verified") or c in ("reviewstatus", "reviewnotes",
                                                                                 "excludedreason")}, t
        assert {"application@odata.bind", "member@odata.bind", "formitemid", "name"} <= written[t], t
    assert {"incometype@odata.bind", "incometypeother", "grosspayperperiod", "payfrequency"} <= written["incomesource"]
    assert {"fullappentryid", "fullappsubmitted", "stage", "giftamount", "lender"} <= written["application"]
    assert {"dateofbirth", "relationship@odata.bind", "relationshipother"} <= written["householdmember"]
    # the sample entry has every path the flow reads, top level and per line
    sample = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "cognito-full-application-entry.json")))

    def has(node, keys, where):
        for key in keys:
            assert isinstance(node, dict) and key in node, f"sample entry has no {where}"
            node = node[key]
        return node
    for path in set(re.findall(r"triggerBody\(\)((?:\?\['\w+'\])+)", text)):
        has(sample, re.findall(r"'(\w+)'", path), path)
    loops = {"Each_other_member": ("HouseholdMembers", "OtherHouseholdMembers"),
             "Each_income": ("Income", "IncomeSources"), "Each_debt": ("Debts", "Debts1"),
             "Each_asset": ("AssetsAndAccounts", "AccountsAndAssets")}
    for loop, path in re.findall(r"items\('(\w+)'\)((?:\?\['\w+'\])+)", text):
        for line in has(sample, loops[loop], loop):
            has(line, re.findall(r"'(\w+)'", path), f"{loop}{path}")
    # choice answers on the sample are labels the maps know
    for line in sample["Income"]["IncomeSources"]:
        assert line["PayFrequency"] in schema.CHOICES["payfrequency"][1]
        assert line["EmploymentStatus"] in schema.CHOICES["incomestatus"][1]
    for t, lst, key, path in (("incomesource", "Income type", "TypeOfEmploymentOrIncome", ("Income", "IncomeSources")),
                              ("debt", "Debt type", "TypeOfDebt", ("Debts", "Debts1")),
                              ("asset", "Asset type", "Type", ("AssetsAndAccounts", "AccountsAndAssets"))):
        names = {v for v, _ in schema.SEED_LISTS[lst]}
        assert all(x[key] in names for x in has(sample, path, t)), t
    # actions and variables referred to exist; loops that set variables run one line at a time
    names = set()
    for scope in bf._scopes(defn):
        names |= set(scope)
    for ref in set(re.findall(r"(?:outputs|body|result|items)\('(\w+)'\)", text)):
        assert ref in names, f"refers to missing action {ref}"
    init = {v["name"] for a in defn["actions"].values() if a.get("type") == "InitializeVariable"
            for v in a["inputs"]["variables"]}
    used = set(re.findall(r"variables\('(\w+)'\)", text)) | {a["inputs"]["name"] for a in bf._actions(defn)
                                                              if a.get("type") == "SetVariable"}
    assert used <= init, used - init
    for a in bf._actions(defn):
        if a.get("type") == "Foreach":
            assert a["runtimeConfiguration"]["concurrency"]["repetitions"] == 1
    for s_ in re.findall(r'"@\{?(.*?)\}?"(?=[,}\]])', text):
        assert s_.count("(") == s_.count(")"), s_[:120]
    assert "createObject" not in text and "oncat(" not in text.replace("concat(", "")
    # finds the application by entry, then A-number, then email; no match leaves a note and changes nothing
    for a in ("Find_by_entry", "Find_by_number", "Find_by_email", "Remember_no_match", "Mark_no_match"):
        assert a in names, a
    assert "clt_recordnumber eq" in text and "Needs attention" not in text
    # the stage only moves forward
    stage = fa.stage_after_submit()
    assert str(fi.choice_value("applicationstage", "Screener submitted")) in stage
    assert str(fi.choice_value("applicationstage", "Certified")) not in stage
    # ethnic origin waits for column security
    assert "EthnicOrigin" not in text
    trig = defn["triggers"]["manual"]   # the designer's name for it: the build must not rename it (the address has it)
    assert list(defn["triggers"]) == ["manual"] and trig["runtimeConfiguration"]["concurrency"]["runs"] == 1
    assert trig["inputs"]["triggerAuthenticationType"] == "All", "Anyone can trigger: the form can't sign in"
    # A blank row (the form sends one when the household has no debts) is skipped
    for kind in ("income", "debt", "asset"):
        loop = find_action(defn["actions"], f"Each_{kind}")
        assert list(loop["actions"]) == [f"If_{kind}_filled_in"], kind
        cond = loop["actions"][f"If_{kind}_filled_in"]
        assert cond["expression"]["not"]["equals"][1] == "" and f"Create_{kind}" in json.dumps(cond["actions"])
        assert cond["else"] == {"actions": {}}


def sample_file(path):
    """The sample entry's first attached file has the link the flow fetches it from."""
    return json.load(open(path))["ProofOfInsurance"][0]["File"].startswith("https://")


def verification_checks(flow):
    import schema
    import flows_intake as fi
    defn, text = flow["definition"], json.dumps(flow["definition"])
    assert list(defn["triggers"]) == ["manual"] and defn["triggers"]["manual"]["inputs"]["triggerAuthenticationType"] == "All"
    tables = {t["name"]: t for t in schema.TABLES}
    sets = {fi.es(t): t for t in ("formsubmission", "sourceform", "occupancy", "annualverification", "insuranceverification", "homeownerrequest")}
    # every column written is real, on the table it is written to
    wrote = {}
    for a in bf._actions(defn):
        params = a.get("inputs", {}).get("parameters", {}) if a.get("type", "").startswith("OpenApi") else {}
        if "entityName" not in params:
            continue
        t = sets[params["entityName"]]
        cols = {c["name"] for c in tables[t]["columns"]} | {"name"} | {l[1] for l in schema.LOOKUPS if l[0] == t}
        for k in params:
            if k.startswith("item/"):
                col = k[len("item/clt_"):].split("@")[0]
                assert col in cols, (t, col)
                wrote.setdefault(t, set()).add(col)
    assert "occupancy" not in wrote, "the flow never changes an occupancy: its dates move when staff close and approve"
    assert "lastoccupancyverified" not in text and "lastinsuranceverified" not in text
    assert {"peopleinhome", "primaryresidence", "noshorttermrental", "rentalstatus", "tenantdetails", "insurancecurrent", "insurancereceived",
            "insurancecontact", "mortgagecontact", "signeddate", "phone", "receiveddate", "formentryid", "uploadslink", "status"} <= wrote["annualverification"]
    assert {"status", "contactrequested", "documentslink", "annualverification", "occupancy", "date", "name"} <= wrote["insuranceverification"]
    # the entry is matched on the occupancy's record number; no match changes nothing but the submission
    find = find_action(defn["actions"], "Find_occupancy")["inputs"]["parameters"]
    assert "clt_recordnumber eq" in find["$filter"] and "OccupancyID" in find["$filter"]
    miss = find_action(defn["actions"], "If_occupancy_found")["else"]["actions"]
    assert list(miss) == ["No_occupancy"] and "No occupancy has the ID" in json.dumps(miss)
    # the request: this entry's own, else the open one, else a new one; a closed one keeps its status
    order = list(find_action(defn["actions"], "If_occupancy_found")["actions"])
    assert order.index("Find_request_for_this_entry") < order.index("Find_open_request") < order.index("If_request_found") < order.index("Save_answers") < order.index("Find_insurance_verification")
    received = fi.choice_value("verificationstatus", "Received")
    status = find_action(defn["actions"], "Save_answers")["inputs"]["parameters"]["item/clt_status"]
    assert status.startswith("@if(contains(createArray(") and f", {received}, coalesce(" in status
    # insurance: To review only when proof is attached and no help was asked for; one already closed is left alone
    review, contact = (fi.choice_value("insurancereviewstatus", s) for s in ("To review", "Needs contact"))
    ins = find_action(defn["actions"], "Create_insurance_verification")["inputs"]["parameters"]
    assert ins["item/clt_status"].startswith("@if(and(greater(length(") and ins["item/clt_status"].endswith(f", {review}, {contact})")
    assert "ICantFindThisDocumentPleaseContactMe" in ins["item/clt_status"]
    still_open = find_action(defn["actions"], "If_it_is_still_open")
    assert len(still_open["expression"]["or"]) == 4 and str(fi.choice_value("verificationstatus", "Issue found")) in find_action(defn["actions"], "Find_open_request")["inputs"]["parameters"]["$filter"]
    assert str(fi.choice_value("insurancereviewstatus", "Requested")) in find_action(defn["actions"], "Find_insurance_verification")["inputs"]["parameters"]["$filter"]
    assert list(still_open["actions"]) == ["Update_insurance_verification", "Remember_insurance_verification"] and still_open["else"] == {"actions": {}}
    # asked for mortgage help: one Homeowner request for the occupancy and its home, unless one is already open
    mort = find_action(defn["actions"], "If_asked_for_mortgage_help")
    assert "PleaseContactMeAboutMyMortgage" in json.dumps(mort["expression"]) and list(mort["actions"]) == ["Find_mortgage_request", "If_no_mortgage_request_is_open"]
    req = find_action(defn["actions"], "Create_mortgage_request")["inputs"]["parameters"]
    assert req["item/clt_name"] == "Mortgage help requested" and req["item/clt_requesttype"] == fi.choice_value("requesttype", "Other")
    assert req["item/clt_status"] == fi.choice_value("requeststatus", "Submitted") and "clt_name eq 'Mortgage help requested'" in find_action(defn["actions"], "Find_mortgage_request")["inputs"]["parameters"]["$filter"]
    assert {"occupancy", "property", "details", "requestdate"} <= wrote["homeownerrequest"]
    # the proof of insurance is copied onto the Insurance verification, after everything else is saved; a failed copy leaves a note and nothing else
    copy = defn["actions"]["Copy_insurance_document"]
    assert copy["runAfter"] == {"Process_verification": ["Succeeded"]}
    step = copy["actions"]["If_there_is_a_file_to_copy"]
    assert list(step["actions"]) == ["Get_the_file", "Save_the_file", "If_more_than_one_file"] and step["actions"]["Get_the_file"]["inputs"]["method"] == "GET"
    assert "ProofOfInsurance" in step["actions"]["Get_the_file"]["inputs"]["uri"] and "?['File']" in step["actions"]["Get_the_file"]["inputs"]["uri"]
    save = step["actions"]["Save_the_file"]["inputs"]
    assert save["host"]["operationId"] == "UpdateEntityFileImageFieldContent" and save["parameters"]["fileImageFieldName"] == "clt_document"
    assert {c["name"]: c for c in tables["insuranceverification"]["columns"]}["document"]["kind"] == "file"
    assert save["parameters"]["recordId"] == "@variables('InsuranceId')" and save["parameters"]["item"] == "@body('Get_the_file')"
    more = step["actions"]["If_more_than_one_file"]
    assert more["expression"]["greater"][1] == 1 and "all of them are in the uploaded documents" in json.dumps(more["actions"])
    assert "forms platform" not in json.dumps([a["inputs"]["parameters"] for a in bf._actions(defn) if "item/clt_notes" in a.get("inputs", {}).get("parameters", {})]), "staff are sent to the uploaded documents, not the forms platform"
    assert defn["actions"]["Note_the_copy_failed"]["runAfter"] == {"Copy_insurance_document": ["Failed", "TimedOut"]}
    assert defn["actions"]["If_matched"]["runAfter"] == {"Process_verification": ["Succeeded"], "Copy_insurance_document": ["Succeeded", "Failed", "TimedOut"]}
    assert sample_file(os.path.join(os.path.dirname(__file__), "fixtures", "cognito-annual-verification-entry.json"))
    # where the uploads were saved: the organization's folder, the form's name and the entry's number
    link = ins["item/clt_documentslink"]
    assert "https://example.sharepoint.com/sites/Stewardship/Shared%20Documents/Verification%20Uploads/" in link and "'/Entry_'" in link and "['Number']" in link
    # the sample entry has every path the flow reads
    sample = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "cognito-annual-verification-entry.json")))
    for path in set(re.findall(r"triggerBody\(\)((?:\?\['\w+'\])+)", text)):
        node = sample
        for key in re.findall(r"'(\w+)'", path):
            assert isinstance(node, dict) and key in node, f"sample entry has no {path}"
            node = node[key]
    # every variable and action the flow refers to exists
    names = set()
    for scope in bf._scopes(defn):
        names |= set(scope)
    variables = {a["inputs"]["variables"][0]["name"] for a in bf._actions(defn) if a.get("type") == "InitializeVariable"}
    assert set(re.findall(r"variables\('(\w+)'\)", text)) <= variables
    assert {a["inputs"]["name"] for a in bf._actions(defn) if a.get("type") == "SetVariable"} <= variables
    assert set(re.findall(r"(?:outputs|body|result)\('(\w+)'\)", text)) <= names
    # a form with no occupancy ID question can't be matched, so its mapping is refused
    raw = json.load(open(os.path.join(bf.EXAMPLE, "forms", "annual-verification.json")))
    try:
        form_mapping.Mapping({**raw, "match": {}}, "x")
        raise AssertionError("an annual verification with no occupancy ID question must be refused")
    except form_mapping.MappingError as e:
        assert "match.occupancyId" in str(e)
    # a form that doesn't ask a question leaves that field alone; no uploads folder means no link
    less = json.loads(json.dumps(raw))
    del less["answers"]["peopleInHome"], less["uploadsFolder"]
    small = json.dumps(bf.verification_flow(form_mapping.Mapping(less, "clients/x/forms/annual-verification.json"))["definition"])
    assert "clt_peopleinhome" not in small and "sharepoint.com" not in small and "clt_peopleinhome" in text


def mapping_checks():
    """Form mappings: nothing about a form's wording is in the flow code; each organization maps its own forms."""
    import flows_intake as fi
    # No organization's wording in core: the flow modules name no question of any form.
    for mod in ("flows_intake.py", "flows_full_app.py", "flows_verification.py"):
        src = open(os.path.join(os.path.dirname(__file__), "..", mod)).read()
        assert not re.search(r"""\bq\(\s*['"]|\bq\(\*[A-Z]+\b(?!\.)|\bit\(\w+, ['"]""", src), f"{mod} still names a form question"
    example = form_mapping.mappings(bf.EXAMPLE)
    assert [m.type for m in example] == ["screener", "full-application", "annual-verification"] and all(m.slug == "" for m in example)
    fixtures = os.path.join(os.path.dirname(__file__), "fixtures")
    for m, sample in zip(example, ("cognito-screener-entry.json", "cognito-full-application-entry.json", "cognito-annual-verification-entry.json")):
        assert not m.check_sample(json.load(open(os.path.join(fixtures, sample)))), m.check_sample(
            json.load(open(os.path.join(fixtures, sample))))
    raw = json.load(open(example[0].source))
    # Every screener column can be mapped, and the example maps them all
    assert {c for c, _ in fi.SCREENER_COLUMNS} == set(raw["answers"])
    # A second screener with different questions is its own flow, with its own name, ID and web address
    other = json.loads(json.dumps(raw))
    other["label"] = "Rental"
    del other["answers"]["creditrange"], other["applicant"]["housingStatus"]
    second = bf.screener_flow(form_mapping.Mapping(other, "clients/x/forms/screener-rental.json"))
    first = bf.screener_flow(example[0])
    assert first["name"] == "CLT: Screener intake" and second["name"] == "CLT: Screener intake (Rental)"
    assert first["id"] != second["id"] and first["id"] == bf.FLOWS[3]["id"]
    # A question the form doesn't ask is not written (the field is left as it is), and the flow is still sound
    text = json.dumps(second["definition"])
    assert "clt_creditrange" not in text and "Find_housingstatus" not in text and "clt_statedannualincome" in text
    assert "clt_creditrange" in json.dumps(first["definition"])
    assert not bf.check_spec([second])
    # An answer worded differently from Stu's label is translated by the mapping's "choices"
    fi.use_form(example[0])
    assert fi.choice_maps()["hbeducation"]["Yes, I have completed a course"] == fi.choice_value("hbeducation", "Completed")
    # A mapping without the questions Stu can't work without is refused, by name
    broken = json.loads(json.dumps(raw))
    del broken["applicant"]["email"]
    try:
        form_mapping.Mapping(broken, "x")
        raise AssertionError("a screener with no email question must be refused")
    except form_mapping.MappingError as e:
        assert "applicant.email" in str(e)
    try:
        form_mapping.Mapping({**raw, "answers": {"adults": "How many adults?"}}, "x")
        raise AssertionError("a path with spaces must be refused")
    except form_mapping.MappingError:
        pass
    # Every organization folder on this machine: its mappings build sound flows and match its sample entries
    # (clients/<organization>/samples/<same file name as the mapping>). Only the example is in the repo.
    for folder in form_mapping.client_dirs():
        flows = bf.flows_for(folder)
        assert not bf.check_spec(flows), (folder, bf.check_spec(flows))
        assert len({f["id"] for f in flows}) == len(flows), f"{folder}: two flows share an ID"
        for m in form_mapping.mappings(folder):
            sample = os.path.join(folder, "samples", os.path.basename(m.source))
            if os.path.isfile(sample):
                problems = m.check_sample(json.load(open(sample)))
                assert not problems, (m.source, problems)


def main():
    assert not bf.check_spec(), bf.check_spec()
    mapping_checks()
    assert [f["name"] for f in bf.FLOWS] == ["CLT: Property document folder", "CLT: Household document folder",
                                             "CLT: Occupancy document folder",
                                             "CLT: Screener intake", "CLT: Full application intake",
                                             "CLT: Annual verification intake"]
    folders = bf.FLOWS[:3]
    prop, hh, occ = (f["definition"]["actions"]["If_no_folder_yet"]["actions"]["Folder_name"]["inputs"] for f in folders)
    assert "' - '" in occ and "clt_recordnumber" in occ and "split(" not in occ         # Rivera - 12 Pine St - O-00001
    assert "clt_occupancies(" in json.dumps(bf.FLOWS[2]) and "'/clt_occupancy/'" in json.dumps(bf.FLOWS[2])
    assert {t["name"] for t in schema.TABLES if t.get("documents")} >= {"property", "household", "occupancy"}
    assert "' - '" in prop and "clt_recordnumber" in prop and "split(" not in prop      # address - P-00004
    assert "split(" in hh and "' - '" in hh                                             # Rivera - H-00001
    for f in folders:
        cd = json.loads(bf.clientdata(f))
        refs = cd["properties"]["connectionReferences"]
        assert set(refs) == set(bf.CONNECTION_REFERENCES)
        text = json.dumps(cd)
        for ch in ("*", ":", "#", "%", "?"):
            assert f"'{ch}', ''" in text, ch  # forbidden characters are stripped from folder names
        assert "clt_recordnumber" in text and "uriPath(" in text
        # A parent folder (DEV) is used when the environment has one, and only then
        acts = f["definition"]["actions"]["If_no_folder_yet"]["actions"]
        find = acts["Find_parent_folder"]["inputs"]["parameters"]["$filter"]
        assert "_regardingobjectid_value eq null" in find and "Find_library" in find and "statecode eq 0" in find
        assert acts["Parent_folder"]["inputs"].startswith("@{if(empty(outputs('Find_parent_folder')")
        assert list(acts["If_parent_folder"]["actions"]) == ["Create_parent_folder_in_SharePoint"]
        assert "outputs('Parent_folder'), outputs('Folder_name')" in acts["Folder_request"]["inputs"]["ServerRelativeUrl"]
        link = acts["Link_folder_to_record"]["inputs"]["parameters"]
        bind = link["item/parentsiteorlocation_sharepointdocumentlocation@odata.bind"]
        assert bind.startswith("/sharepointdocumentlocations(@{coalesce(first(outputs('Find_parent_folder')") and "Find_library" in bind
        assert "outputs('Parent_folder')" in json.dumps(acts["Save_folder_link"])
        order = ["Find_site", "Find_library", "Find_parent_folder", "Parent_folder", "Folder_name", "If_parent_folder",
                 "Folder_request", "Create_folder_in_SharePoint", "Link_folder_to_record", "Save_folder_link"]
        assert list(acts) == order and all(list(acts[b_].get("runAfter", {})) == [a] for a, b_ in zip(order, order[1:]))
    screener_checks(bf.FLOWS[3])
    full_app_checks(bf.FLOWS[4])
    verification_checks(bf.FLOWS[5])
    fake = Fake()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "CLTStewardship", session=fake)
    log = b.Log(os.devnull)
    bf.run(dv, log)
    assert len(fake.refs) == 2 and len(fake.flows) == len(bf.FLOWS)
    n = len(fake.writes)
    bf.run(dv, log)
    assert len(fake.writes) == n, "re-run must change nothing"
    bf.run(dv, log, only="document folder")
    assert len(fake.writes) == n
    # A flow that's on and gets a new definition is switched back on after the update.
    wid = bf.FLOWS[0]["id"]
    fake.flows[wid]["statecode"] = 1
    fake.flows[wid]["clientdata"] = "old"
    bf.run(dv, log)
    assert fake.flows[wid]["statecode"] == 1 and fake.flows[wid]["clientdata"] == bf.clientdata(bf.FLOWS[0])
    print("OK: flow definitions are valid, go in the solution, strip bad folder characters, and re-run cleanly.")
    print("OK: screener intake writes only real columns and choice values, reads fields the sample entry has, "
          "and refers only to actions and variables that exist.")
    print("OK: form mappings: no form's wording is in the flow code; a second screener is its own flow; a question "
          "the form doesn't ask is left out; every organization folder's mappings match its sample entries.")
    print("OK: full application intake writes only real columns, never staff review fields, reads fields the "
          "sample entry has, and moves the stage only forward.")
    print("OK: annual verification intake matches on the occupancy ID, writes only real columns, reads fields the sample "
          "entry has, keeps a closed verification's status, starts the insurance verification with a copy of the proof, "
          "opens one request for mortgage help, and never sets the occupancy's dates.")


if __name__ == "__main__":
    main()
