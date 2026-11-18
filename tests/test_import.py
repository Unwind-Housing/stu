"""Offline test: tools/import_records.py against a fake Dataverse holding rows."""
import json
import os
import re
import sys
import uuid
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_schema as b  # noqa: E402
import import_records as ir  # noqa: E402
from schema import CHOICES, TABLES  # noqa: E402
from test_offline import Resp  # noqa: E402

TEMPLATES = os.path.join(os.path.dirname(__file__), "..", "docs", "templates")
SETS = {"clt_propertys": "property", "clt_households": "household", "clt_householdmembers": "householdmember",
        "clt_occupancys": "occupancy", "clt_fees": "fee", "clt_listitems": "listitem"}
PREFIXES = {"property": "P", "household": "H", "occupancy": "O"}


def value(choice, label):
    return 725110000 + CHOICES[choice][1].index(label)


class FakeData:
    def __init__(self):
        self.rows = {t: {} for t in SETS.values()}
        self.calls = []

    def add(self, tname, **cols):
        rid = str(uuid.uuid4())
        row = {f"clt_{tname}id": rid, **cols}
        if tname in PREFIXES:
            row["clt_recordnumber"] = f"{PREFIXES[tname]}-{len(self.rows[tname]) + 1:05d}"
        self.rows[tname][rid] = row
        return rid

    def item(self, lst, name, answers="", state=None):
        return self.add("listitem", clt_name=name, clt_list=value("listname", lst), clt_formanswers=answers,
                        _clt_state_value=state)

    def request(self, method, url, headers=None, data=None, timeout=None):
        path = unquote(url.split("/api/data/v9.2/", 1)[1])
        body = json.loads(data) if data else None
        self.calls.append((method, path))
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='clt_(\w+)'\)\?\$select=EntitySetName", path)
        if m:
            return Resp(200, {"EntitySetName": next(k for k, v in SETS.items() if v == m[1])})
        m = re.fullmatch(r"GlobalOptionSetDefinitions\(Name='clt_(\w+)'\)", path)
        if m:
            return Resp(200, {"Options": [{"Value": 725110000 + i, "Label": {"UserLocalizedLabel": {"Label": lab}}}
                                          for i, lab in enumerate(CHOICES[m[1]][1])]})
        m = re.fullmatch(r"(clt_\w+)\?\$select=([\w,]+)(?:&\$filter=clt_list eq (\d+))?", path)
        if m and method == "GET":
            rows = [dict(r) for r in self.rows[SETS[m[1]]].values() if not m[3] or r.get("clt_list") == int(m[3])]
            return Resp(200, {"value": rows})
        if path in SETS and method == "POST":
            tname, cols = SETS[path], {}
            known = {f"clt_{c['name']}" for c in next(t for t in TABLES if t["name"] == tname)["columns"]} | {"clt_name"}
            for k, v in body.items():
                if k.endswith("@odata.bind"):
                    es, rid = re.fullmatch(r"/(clt_\w+)\(([\w-]+)\)", v).groups()
                    assert rid in self.rows[SETS[es]], f"{k} points at a {SETS[es]} that doesn't exist: {rid}"
                    cols[f"_{k[:-len('@odata.bind')]}_value"] = rid
                else:
                    assert k in known, f"{tname} has no column {k}"
                    cols[k] = v
            rid = self.add(tname, **cols)
            return Resp(201, self.rows[tname][rid]) if "return=representation" in headers["Prefer"] else Resp(204)
        m = re.fullmatch(r"(clt_\w+)\(([\w-]+)\)", path)
        if m and method == "PATCH":
            row = self.rows[SETS[m[1]]][m[2]]
            for k, v in body.items():
                if k.endswith("@odata.bind"):
                    row[f"_{k[:-len('@odata.bind')]}_value"] = re.fullmatch(r"/clt_\w+\(([\w-]+)\)", v)[1]
                else:
                    row[k] = v
            return Resp(204)
        raise AssertionError(f"unexpected {method} {path}")


def environment():
    fake = FakeData()
    wa = fake.item("State", "Washington", "WA\nWashington")
    ky = fake.item("State", "Kentucky", "KY\nKentucky")
    fake.item("County", "Jefferson County", "Jefferson County\nJefferson", wa)
    fake.item("County", "Clallam County", "Clallam County\nClallam", wa)
    fake.item("County", "Jefferson County", "Jefferson County\nJefferson", ky)
    for x in ("Townhome", "Single-family detached", "Land only"):
        fake.item("Property type", x, x)
    for x in ("Ground lease", "Other"):
        fake.item("Tenure type", x, x)
    fake.item("Relationship", "Spouse or partner", "Spouse or partner\nSpouse")
    return fake, wa, ky


def writes(fake):
    return [c for c in fake.calls if c[0] in ("POST", "PATCH")]


def data():
    P = ["Property ref", "Record number", "Street address", "Unit", "City", "State", "County", "ZIP code",
         "Property type", "Tenure type", "Status", "Bedrooms", "Bathrooms", "Square feet", "Notes"]
    H = ["Household ref", "Status", "Primary email", "Phone", "Mailing street address", "Mailing state", "Notes"]
    M = ["Household ref", "First name", "Last name", "Applicant role", "Relationship to primary applicant", "On title"]
    O = ["Property ref", "Household ref", "Role", "Status", "Start date", "End date", "Resale formula", "Base price",
         "Base date", "Annual rate (%)", "Count whole years only"]
    F = ["Property ref", "Fee type", "Monthly amount", "Effective start"]
    rows = lambda head, *vals: [dict(zip(head, v)) for v in vals]  # noqa: E731
    return {
        "property": rows(P,
            ["P1", "", "12 Pine St", "", "Port Angeles", "WA", "Clallam", "98363", "Single-family detached",
             "Ground lease", "Owner-occupied", "3", "1.5", "1,432", ""],
            ["P2", "", "40 Hill Rd", "2", "Port Townsend", "WA", "Jefferson County", "98368", "Townhome",
             "Ground lease", "For sale", "2", "1", "898", "made up"],
            ["P3", "", "Hill Rd common lot", "", "Port Townsend", "WA", "Jefferson County", "98368", "Common area",
             "Other", "", "", "", "", ""]),
        "household": rows(H,
            ["H1", "Homeowner", "a@example.com", "(360) 555-0100", "PO Box 1", "WA", ""],
            ["H2", "Past homeowner", "", "", "", "", "sold in 2022"]),
        "householdmember": rows(M,
            ["H1", "Jo", "Rivera", "Primary applicant", "", "Yes"],
            ["H1", "Sam", "Rivera", "Co-applicant", "Spouse", "Yes"],
            ["H2", "Lee", "Rivera", "Primary applicant", "", "Yes"]),
        "occupancy": rows(O,
            ["P1", "H1", "Owner", "Current", "2022-11-22", "", "Fixed annual rate", "122400", "2022-11-22", "1.5", "No"],
            ["P1", "H2", "Owner", "Past", "2014-05-20", "2022-11-15", "Fixed annual rate", "$105,896.00", "2014-05-20",
             "1.5", "No"]),
        "fee": rows(F, ["P1", "Ground lease fee", "45", "2022-11-22"], ["P1", "ERRR", "65", "2022-11-22"]),
    }


def main():
    fake, wa, ky = environment()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "CLTStewardship", session=fake)
    out = []

    # A value missing from a list stops everything, with a plain message, before any write
    try:
        ir.run(dv, None, log=out.append, data=data())
        raise AssertionError("should have stopped")
    except b.DataverseError as e:
        assert "Property type 'Common area' isn't under Settings > Lists" in str(e) and "--add-list-values" in str(e), e
    assert not writes(fake)

    # Dry run changes nothing and counts what it would do
    c = ir.run(dv, None, log=out.append, dry_run=True, add_list_values=True, data=data())
    assert not writes(fake)
    assert c == {"created": 12, "updated": 0, "already there": 0, "list values added": 1}, c

    c = ir.run(dv, None, log=out.append, add_list_values=True, data=data())
    assert c == {"created": 12, "updated": 0, "already there": 0, "list values added": 1}, c
    props = {p["clt_name"]: p for p in fake.rows["property"].values()}
    assert set(props) == {"12 Pine St", "40 Hill Rd, Unit 2", "Hill Rd common lot"}
    pine = props["12 Pine St"]
    items = fake.rows["listitem"]
    assert pine["clt_squarefeet"] == 1432 and pine["clt_bathrooms"] == 1.5 and pine["clt_bedrooms"] == 3
    assert pine["clt_status"] == value("propertystatus", "Owner-occupied")
    assert items[pine["_clt_county_value"]]["clt_name"] == "Clallam County"
    hill = props["40 Hill Rd, Unit 2"]
    assert items[hill["_clt_county_value"]]["_clt_state_value"] == wa, "Jefferson County must be Washington's"
    assert items[props["Hill Rd common lot"]["_clt_propertytype_value"]]["clt_name"] == "Common area"
    assert "clt_status" not in props["Hill Rd common lot"]
    # Two households with the same last name: Rivera, then Rivera, Lee
    hh = {h["clt_name"]: h for h in fake.rows["household"].values()}
    assert set(hh) == {"Rivera", "Rivera, Lee"}, set(hh)
    assert hh["Rivera"]["_clt_mailingstate_value"] == wa and hh["Rivera"]["clt_status"] == value("householdstatus", "Homeowner")
    mem = {m["clt_name"]: m for m in fake.rows["householdmember"].values()}
    assert mem["Sam Rivera"]["_clt_household_value"] == hh["Rivera"]["clt_householdid"]
    assert items[mem["Sam Rivera"]["_clt_relationship_value"]]["clt_name"] == "Spouse or partner"
    assert mem["Jo Rivera"]["clt_ontitle"] is True
    occ = {o["clt_name"]: o for o in fake.rows["occupancy"].values()}
    assert set(occ) == {"Rivera - 12 Pine St"}, "both occupancies are named from the household's last name"
    occs = list(fake.rows["occupancy"].values())
    cur = next(o for o in occs if o["clt_status"] == value("occupancystatus", "Current"))
    past = next(o for o in occs if o["clt_status"] == value("occupancystatus", "Past"))
    assert cur["clt_baseprice"] == 122400 and cur["clt_wholeyearsonly"] is False and cur["clt_annualrate"] == 1.5
    assert past["clt_baseprice"] == 105896 and past["clt_enddate"] == "2022-11-15"
    assert pine["_clt_currentoccupancy_value"] == cur["clt_occupancyid"], "the property points at its current occupancy"
    fees = {f["clt_name"]: f for f in fake.rows["fee"].values()}
    assert set(fees) == {"Ground lease fee from Nov 2022", "ERRR from Nov 2022"}
    assert fees["ERRR from Nov 2022"]["clt_amount"] == 65 and fees["ERRR from Nov 2022"]["_clt_property_value"] == pine["clt_propertyid"]

    # Running it again changes nothing
    before = len(writes(fake))
    c = ir.run(dv, None, log=out.append, add_list_values=True, data=data())
    assert c == {"created": 0, "updated": 0, "already there": 12, "list values added": 0}, c
    assert len(writes(fake)) == before

    # A record number updates that record: filled cells only
    d = {"property": [{"Record number": pine["clt_recordnumber"], "Street address": "", "Bedrooms": "4", "Notes": "new roof 2026"}],
         "fee": [{"Property ref": pine["clt_recordnumber"], "Fee type": "ERRR", "Monthly amount": "70", "Effective start": "2027-01-01"}]}
    c = ir.run(dv, None, log=out.append, data=d)
    assert c["updated"] == 1 and c["created"] == 1, c
    assert pine["clt_bedrooms"] == 4 and pine["clt_notes"] == "new roof 2026" and pine["clt_name"] == "12 Pine St"
    assert pine["clt_squarefeet"] == 1432, "blank cells are left alone"

    # Problems are all listed, with file and row, and nothing is written
    before = len(writes(fake))
    bad = data()
    bad["property"][0].update({"Street address": "99 New St", "Status": "Sold", "Bedrooms": "three", "County": "King"})
    bad["householdmember"][2]["Applicant role"] = "Co-applicant"
    bad["occupancy"][0]["Property ref"] = "P9"
    bad["fee"][0]["Effective start"] = "11/22/2022"
    try:
        ir.run(dv, None, log=out.append, add_list_values=True, data=bad)
        raise AssertionError("should have stopped")
    except b.DataverseError as e:
        msg = str(e)
    for want in ("properties.csv, row 2: Status 'Sold' isn't one of", "properties.csv, row 2: Bedrooms 'three' is not a number",
                 "properties.csv, row 2: County 'King' isn't under Settings > Lists in that State",
                 "households.csv, row 3: household H2 needs exactly one Primary applicant",
                 "occupancies.csv, row 2: Property ref 'P9'", "fees.csv, row 2: Effective start '11/22/2022' is not a date"):
        assert want in msg, (want, msg)
    assert len(writes(fake)) == before

    # The templates in docs/templates load as they are
    fake2, _, _ = environment()
    for name in ("1 Old Rd", "2 Old Rd", "3 Old Rd"):   # the templates update P-00002 and H-00003 as examples
        fake2.add("property", clt_name=name)
        fake2.add("household", clt_name=name)
    dv2 = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "CLTStewardship", session=fake2)
    c = ir.run(dv2, TEMPLATES, log=out.append, add_list_values=True)
    assert c["created"] >= 5 and c["already there"] == 0, c
    assert not any("\u2014" in line for line in out)
    print("OK: import creates properties, households, members, occupancies and fees; re-runs change nothing; "
          "record numbers update; problems stop the run before any write.")


if __name__ == "__main__":
    main()
