"""Offline tests: % of AMI. The formula (schema.py AMI_PCT) and tools/recalc_ami.py against a fake Dataverse."""
import json
import os
import re
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_schema as b  # noqa: E402
import recalc_ami as ra  # noqa: E402
import schema  # noqa: E402
from test_offline import Resp  # noqa: E402

HUD, OTHER = 768270000, 768270001


def eligibility_formula_test():
    """Organization eligibility: reads the rules through the lookup, using helper columns for choices and money."""
    f, g, o = schema.ELIGIBILITY_FAILS, schema.ELIGIBILITY_GAPS, schema.ORG_ELIGIBILITY
    for x in ("clt_eligibilityrules.clt_maxami", "clt_eligibilityrules.clt_requiresftb",
              "clt_eligibilityrules.clt_requireslocal", "clt_eligibilityrules.clt_assetlimitwhole"):
        assert x in f, x
    assert "clt_eligibilityrules.clt_assetlimit " not in f and "clt_eligibilityrules.clt_firsttimebuyer" not in f
    assert "IsBlank(clt_amipct)" in g and '"Eligible"' in o and "Not eligible: " in o and "Needs review: " in o
    assert all(len(x) <= 1000 for x in (f, g, o))
    cols = {c["name"]: c for t in schema.TABLES if t["name"] == "application" for c in t["columns"]}
    assert cols["iseligible"]["result"] == "bool" and cols["orgeligibility"]["max"] >= 500


def formula_test():
    """The formula reads the household size's 50% limit through AMI limits used, with HUD's rule over 8."""
    lim, f = schema.LIMIT50_FOR_SIZE, schema.AMI_PCT
    for n in range(1, 9):
        assert f"{n}, clt_amilimits.clt_size{n}" in lim
    assert "clt_size4 * (1.32 + 0.08 * ((clt_adults + clt_children) - 8))" in lim
    assert lim.startswith("If(IsBlank(clt_amilimits)")
    assert "Decimal(clt_statedannualincome) * 50 / clt_limit50forsize" in f   # % = income x 100 / (2 x limit)
    assert len(lim) <= 1000 and len(f) <= 1000
    col = next(c for t in schema.TABLES if t["name"] == "application" for c in t["columns"] if c["name"] == "amipct")
    assert col["kind"] == "fx" and col["result"] == "int"
    body = b.column_body(col, {}, {})
    assert body["SourceType"] == 3 and body["FormulaDefinition"] == col["formula"]
    assert body["@odata.type"] == "Microsoft.Dynamics.CRM.IntegerAttributeMetadata"
    assert ("application", "amilimits", "incomelimitset") in [(c, n, p) for c, n, p, *_ in schema.LOOKUPS]


class Fake:
    def __init__(self):
        self.sets = [
            {"clt_incomelimitsetid": "jeff26", "_clt_county_value": "jeff", "clt_year": 2026, "clt_limitsource": HUD},
            {"clt_incomelimitsetid": "jeff25", "_clt_county_value": "jeff", "clt_year": 2025, "clt_limitsource": HUD},
            {"clt_incomelimitsetid": "clal27", "_clt_county_value": "clal", "clt_year": 2027, "clt_limitsource": OTHER},
        ]
        self.apps = {
            "a1": dict(clt_name="On last year", _clt_county_value="jeff", _clt_amilimits_value="jeff25",
                       _clt_eligibilityrules_value="org"),
            "a2": dict(clt_name="No link yet", _clt_county_value="jeff", _clt_amilimits_value=None,
                       _clt_eligibilityrules_value=None),
            "a3": dict(clt_name="Already current", _clt_county_value="jeff", _clt_amilimits_value="jeff26",
                       _clt_eligibilityrules_value="org"),
            "a4": dict(clt_name="Clallam, only Other", _clt_county_value="clal", _clt_amilimits_value=None,
                       _clt_eligibilityrules_value="org"),
        }
        self.patches = []

    def request(self, method, url, headers=None, data=None, timeout=None):
        path = unquote(url.split("/api/data/v9.2/", 1)[1])
        if path == "GlobalOptionSetDefinitions(Name='clt_limitsource')":
            return Resp(200, {"Options": [{"Value": HUD, "Label": {"UserLocalizedLabel": {"Label": "HUD"}}},
                                          {"Value": OTHER, "Label": {"UserLocalizedLabel": {"Label": "Other"}}}]})
        if path.startswith("clt_incomelimitsets?"):
            src = int(re.search(r"clt_limitsource eq (\d+)", path)[1])
            assert "$orderby=clt_year desc" in path
            return Resp(200, {"value": sorted([s for s in self.sets if s["clt_limitsource"] == src],
                                              key=lambda s: -s["clt_year"])})
        if path.startswith("clt_eligibilities?"):
            assert "$orderby=createdon asc" in path
            return Resp(200, {"value": [{"clt_eligibilityid": "org"}]})
        if path.startswith("clt_applications?"):
            return Resp(200, {"value": [{"clt_applicationid": k, **v} for k, v in self.apps.items()]})
        m = re.fullmatch(r"clt_applications\((\w+)\)", path)
        if m and method == "PATCH":
            body = json.loads(data)
            self.patches.append(m[1])
            if "clt_amilimits@odata.bind" in body:
                self.apps[m[1]]["_clt_amilimits_value"] = re.fullmatch(r"/clt_incomelimitsets\((\w+)\)",
                                                                        body["clt_amilimits@odata.bind"])[1]
            if "clt_eligibilityrules@odata.bind" in body:
                self.apps[m[1]]["_clt_eligibilityrules_value"] = re.fullmatch(r"/clt_eligibilities\((\w+)\)",
                                                                              body["clt_eligibilityrules@odata.bind"])[1]
            return Resp(204)
        raise AssertionError(f"unexpected {method} {path}")


def tool_test():
    fake = Fake()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "", session=fake)
    out = []
    assert ra.run(dv, out.append, dry_run=True) == 2 and not fake.patches
    ra.run(dv, out.append)
    a = fake.apps
    assert a["a1"]["_clt_amilimits_value"] == "jeff26" and a["a2"]["_clt_amilimits_value"] == "jeff26"
    assert sorted(fake.patches) == ["a1", "a2"]               # already current: untouched
    assert a["a4"]["_clt_amilimits_value"] is None            # only an Other record for Clallam
    assert all(x["_clt_eligibilityrules_value"] == "org" for x in a.values())  # everyone linked to the org's rules
    fake.patches.clear()
    assert ra.run(dv, out.append) == 0 and not fake.patches   # re-run changes nothing


def main():
    formula_test()
    eligibility_formula_test()
    tool_test()
    print("OK: % of AMI formula reads the size's 50% limit (HUD's rule over 8); the tool links each screener to its "
          "county's newest HUD limits, ignores Other, skips current ones, re-runs clean.")


if __name__ == "__main__":
    main()
