"""Offline test: tools/load_counties.py against a fake List item table."""
import json
import os
import re
import sys
import uuid
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_schema as b  # noqa: E402
import load_counties as lc  # noqa: E402
from test_offline import Resp  # noqa: E402

STATE, COUNTY = 725110009, 725110000


class FakeLists:
    def __init__(self):
        self.rows = {}
        self.calls = []

    def add(self, name, lst, answers="", state=None):
        rid = str(uuid.uuid4())
        self.rows[rid] = {"clt_listitemid": rid, "clt_name": name, "clt_list": lst, "clt_formanswers": answers,
                          "_clt_state_value": state}
        return rid

    def request(self, method, url, headers=None, data=None, timeout=None):
        path = unquote(url.split("/api/data/v9.2/", 1)[1])
        body = json.loads(data) if data else None
        self.calls.append((method, path))
        if path == "GlobalOptionSetDefinitions(Name='clt_listname')":
            return Resp(200, {"Options": [{"Value": COUNTY, "Label": {"UserLocalizedLabel": {"Label": "County"}}},
                                          {"Value": STATE, "Label": {"UserLocalizedLabel": {"Label": "State"}}}]})
        if path.startswith("RelationshipDefinitions(SchemaName='clt_listitem_listitem_state')"):
            return Resp(200, {"ReferencingEntityNavigationPropertyName": "clt_state_clt_listitem"})
        if path.startswith("EntityDefinitions(LogicalName='clt_listitem')"):
            return Resp(200, {"EntitySetName": "clt_listitems"})
        m = re.fullmatch(r"clt_listitems\?\$select=[\w,]+&\$filter=clt_list eq (\d+)", path)
        if m and method == "GET":
            vals = [dict(r) for r in self.rows.values() if r["clt_list"] == int(m[1])]
            return Resp(200, {"value": vals})
        if path == "clt_listitems" and method == "POST":
            sid = re.fullmatch(r"/clt_listitems\(([\w-]+)\)", body.pop("clt_state_clt_listitem@odata.bind"))[1]
            assert sid in self.rows and self.rows[sid]["clt_list"] == STATE
            self.add(body["clt_name"], body["clt_list"], body["clt_formanswers"], sid)
            return Resp(204)
        m = re.fullmatch(r"clt_listitems\(([\w-]+)\)", path)
        if m and method == "PATCH":
            row = self.rows[m[1]]
            assert "clt_state@odata.bind" not in body, "self-referencing lookup needs its long navigation name"
            if "clt_state_clt_listitem@odata.bind" in body:
                row["_clt_state_value"] = re.fullmatch(r"/clt_listitems\(([\w-]+)\)",
                                                       body["clt_state_clt_listitem@odata.bind"])[1]
            if "clt_formanswers" in body:
                row["clt_formanswers"] = body["clt_formanswers"]
            return Resp(204)
        raise AssertionError(f"unexpected {method} {path}")


def main():
    rows = lc.read_csv()
    assert len(rows) == 3143, len(rows)
    assert sum(1 for r in rows if r["state"] == "WA") == 39
    fake = FakeLists()
    states = {}
    for st in sorted({r["state"] for r in rows}):
        states[st] = fake.add(f"State {st}", STATE, f"{st}\nState {st}")
    # Someone typed two counties by hand before the State link existed
    jeff = fake.add("Jefferson County", COUNTY, "Jefferson")
    fake.add("Clallam", COUNTY, "")
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "CLTStewardship", session=fake)
    out = []

    # Dry run changes nothing
    c = lc.run(dv, log=out.append, existing_state="WA", dry_run=True)
    assert not [x for x in fake.calls if x[0] in ("POST", "PATCH")]
    assert c["created"] == 3141 and c["linked"] == 2, c

    c = lc.run(dv, log=out.append, existing_state="WA")
    assert c == {"created": 3141, "linked": 2, "answers added": 0, "already there": 0}, c
    counties = [r for r in fake.rows.values() if r["clt_list"] == COUNTY]
    assert len(counties) == 3143
    j = fake.rows[jeff]
    assert j["_clt_state_value"] == states["WA"]
    assert j["clt_formanswers"].splitlines() == ["Jefferson", "Jefferson County"], j["clt_formanswers"]
    ky = [r for r in counties if r["clt_name"] == "Jefferson County" and r["_clt_state_value"] == states["KY"]]
    assert len(ky) == 1 and ky[0]["clt_formanswers"] == "Jefferson County\nJefferson"
    dona = next(r for r in counties if r["clt_name"] == "Doña Ana County")
    assert "Dona Ana" in dona["clt_formanswers"].splitlines()

    # Re-run: nothing created
    c = lc.run(dv, log=out.append, existing_state="WA")
    assert c["created"] == 0 and c["linked"] == 0 and c["already there"] == 3143, c
    assert len([r for r in fake.rows.values() if r["clt_list"] == COUNTY]) == 3143

    # Without --existing-state, unlinked values are reported, not guessed
    fake2 = FakeLists()
    for st in sorted({r["state"] for r in rows}):
        fake2.add(f"State {st}", STATE, st)
    fake2.add("Jefferson County", COUNTY, "Jefferson")
    out2 = []
    c = lc.run(b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "CLTStewardship", session=fake2),
               log=out2.append, dry_run=True)
    assert c["linked"] == 0 and any("have no State" in x for x in out2), out2
    print("OK: 3,143 counties load once, linked to their State; hand-typed counties are linked, not duplicated; "
          "re-run creates nothing; dry run changes nothing.")


if __name__ == "__main__":
    main()
