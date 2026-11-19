"""Offline test for build_app.py: build schema in a fake Dataverse, then the app, twice."""
import json
import os
import re
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import build_schema as b  # noqa: E402
import build_app as a  # noqa: E402
import app_spec as spec  # noqa: E402
from test_offline import FakeDataverse, Resp  # noqa: E402


class FakeApp(FakeDataverse):
    def __init__(self):
        super().__init__()
        self.views, self.forms, self.sitemaps, self.apps = {}, {}, {}, {}
        # SharePoint's own view, present in every environment (marked default so it isn't counted as "added")
        self.views["sp-docs-view"] = {"returnedtypecode": "sharepointdocument", "name": "Document Associated Grid",
                                      "isdefault": True, "fetchxml": "<fetch/>", "layoutxml": "<grid/>"}
        self.app_components, self.sol_components = [], []
        self.webresources = {}  # name -> {id, content}
        self.otc = {}

    def _odata(self, path):
        m = re.search(r"\$filter=(.*)$", path)
        return m[1] if m else ""

    def request(self, method, url, headers=None, data=None, timeout=None):
        path = unquote(url.split("/api/data/v9.2/", 1)[1])
        body = json.loads(data) if data else None
        # schema-stage entity creation: also create default view + main form
        if path == "EntityDefinitions" and method == "POST":
            r = super().request(method, url, headers, data, timeout)
            name = body["SchemaName"].lower()
            self.otc[name] = 10000 + len(self.otc)
            vid = str(uuid.uuid4())
            self.views[vid] = dict(returnedtypecode=name, querytype=0, isdefault=True, name=f"Active {name}",
                                   fetchxml="", layoutxml="")
            fid = str(uuid.uuid4())
            self.forms[fid] = dict(objecttypecode=name, type=2, name="Information",
                                   formxml='<form><tabs><tab name="general"/></tabs><header id="{x}"/>'
                                           '<footer id="{y}"/><Navigation/></form>')
            return r
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(sharepointdocument|sharepointdocumentlocation)'\)\?\$select=MetadataId", path)
        if m:
            return Resp(200, {"MetadataId": "md-" + m[1]})
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)\?\$select=LogicalName,ObjectTypeCode,"
                         r"MetadataId&\$expand=Attributes\(.*\)", path)
        if m:
            if m[1] not in self.entities:
                return Resp(404, {"error": {"message": f"EntityMetadata With Id = LogicalName='{m[1]}' does not exist."}})
            ent = self.entities[m[1]]
            attrs = []
            for ln_, meta in ent["attrs"].items():
                t = (meta.get("@odata.type") or "Microsoft.Dynamics.CRM.UniqueidentifierAttributeMetadata").split(".")[-1]
                at = {"StringAttributeMetadata": "String", "MemoAttributeMetadata": "Memo",
                      "IntegerAttributeMetadata": "Integer", "DecimalAttributeMetadata": "Decimal",
                      "MoneyAttributeMetadata": "Money", "DateTimeAttributeMetadata": "DateTime",
                      "BooleanAttributeMetadata": "Boolean", "PicklistAttributeMetadata": "Picklist",
                      "MultiSelectPicklistAttributeMetadata": "Virtual",
                      "LookupAttributeMetadata": "Lookup"}.get(t, "Uniqueidentifier")
                tn = "MultiSelectPicklistType" if at == "Virtual" else at + "Type"
                label = meta.get("DisplayName", {}).get("LocalizedLabels", [{}])[0].get("Label", ln_)
                attrs.append({"LogicalName": ln_, "AttributeType": at, "AttributeTypeName": {"Value": tn},
                              "DisplayName": {"UserLocalizedLabel": {"Label": label}}})
            return Resp(200, {"LogicalName": m[1], "ObjectTypeCode": self.otc[m[1]],
                              "MetadataId": "md-" + m[1], "Attributes": attrs})
        if path.startswith("savedqueries"):
            if method == "GET":
                f = self._odata(path)
                rt = re.search(r"returnedtypecode eq '(\w+)'", f)[1]
                nm = re.search(r"name eq '([^']+)'", f)
                rows = [{"savedqueryid": k} for k, v in self.views.items() if v["returnedtypecode"] == rt
                        and (v["isdefault"] if "isdefault eq true" in f else (nm and v["name"] == nm[1]))]
                return Resp(200, {"value": rows})
            if method == "PATCH":
                vid = re.fullmatch(r"savedqueries\(([\w-]+)\)", path)[1]
                ET.fromstring(body["fetchxml"]); ET.fromstring(body["layoutxml"])
                self.views[vid].update(body)
                return Resp(204)
            if method == "POST":
                ET.fromstring(body["fetchxml"]); ET.fromstring(body["layoutxml"])
                vid = str(uuid.uuid4())
                self.views[vid] = dict(body)
                r = Resp(204)
                r.headers["OData-EntityId"] = f"https://x/api/data/v9.2/savedqueries({vid})"
                return r
        if path.startswith("systemforms"):
            if method == "GET":
                ot = re.search(r"objecttypecode eq '(\w+)'", path)[1]
                return Resp(200, {"value": [dict(formid=k, **v) for k, v in self.forms.items()
                                            if v["objecttypecode"] == ot]})
            fid = re.fullmatch(r"systemforms\(([\w-]+)\)", path)[1]
            self.forms[fid]["formxml"] = body["formxml"]
            return Resp(204)
        for es, key, store in (("sitemaps", "sitemapnameunique", self.sitemaps),
                               ("appmodules", "uniquename", self.apps)):
            if path.startswith(es):
                idf = "sitemapid" if es == "sitemaps" else "appmoduleid"
                if method == "GET":
                    val = re.search(rf"{key} eq '([^']+)'", path)[1]
                    return Resp(200, {"value": [{idf: k} for k, v in store.items() if v[key] == val]})
                if method == "PATCH":
                    store[re.fullmatch(rf"{es}\(([\w-]+)\)", path)[1]].update(body)
                    return Resp(204)
                nid = str(uuid.uuid4())
                store[nid] = body
                r = Resp(204)
                r.headers["OData-EntityId"] = f"https://x/api/data/v9.2/{es}({nid})"
                return r
        if path == "AddSolutionComponent":
            self.sol_components.append((body["ComponentType"], body["ComponentId"]))
            return Resp(200, {"id": "x"})
        if path.startswith("webresourceset"):
            if method == "GET":
                name = re.search(r"name eq '([^']+)'", path)[1]
                w = self.webresources.get(name)
                return Resp(200, {"value": [{"webresourceid": w["id"], "content": w["content"]}] if w else []})
            if method == "POST":
                assert body["webresourcetype"] == {"js": 3, "html": 1, "css": 2}[body["name"].rsplit(".", 1)[1]]
                assert body["name"].startswith("clt_/")
                wid = str(uuid.uuid4())
                self.webresources[body["name"]] = {"id": wid, "content": body["content"], "patched": 0}
                r = Resp(204)
                r.headers = {"OData-EntityId": f"https://x/api/data/v9.2/webresourceset({wid})"}
                return r
            if method == "PATCH":
                w = next(w for w in self.webresources.values() if path == f"webresourceset({w['id']})")
                w["content"], w["patched"] = body["content"], w["patched"] + 1
                return Resp(204)
        if path == "AddAppComponents":
            for c in body["Components"]:
                key = (body["AppId"], c.get("sitemapid") or c.get("entityid"))
                if key in self.app_components:
                    return Resp(400, {"error": {"message": "Component already exists in app"}})
                self.app_components.append(key)
            return Resp(204)
        if path.startswith("ValidateApp"):
            return Resp(200, {"AppValidationResponse": {"ValidationSuccess": True, "ValidationIssueList": []}})
        if path == "PublishXml":
            ET.fromstring(body["ParameterXml"])
            return Resp(204)
        return super().request(method, url, headers, data, timeout)


def check_forms(fake):
    rels = set(fake.rels)
    for fid, f in fake.forms.items():
        root = ET.fromstring(f["formxml"])
        ent = f["objecttypecode"]
        ids = [c.get("id") for c in root.iter("control")]
        assert len(ids) == len(set(ids)), f"duplicate control ids on {ent}"
        for c in root.iter("control"):
            if c.get("datafieldname"):
                assert c.get("datafieldname") in fake.entities[ent]["attrs"], (ent, c.get("datafieldname"))
            if c.get("indicationOfSubgrid"):
                rel = c.find("parameters/RelationshipName").text
                if c.find("parameters/TargetEntityType").text == "sharepointdocument":
                    assert rel == f"{ent}_SharePointDocuments", rel
                    assert c.find("parameters/ViewId").text == "sp-docs-view"
                    continue
                assert rel in rels, rel
                assert c.find("parameters/ViewId").text
        assert root.find("footer") is not None and root.find("Navigation") is not None
        assert len(root.findall("tabs")) == 1 and len(root.findall("header")) == 1


def main():
    assert not a.check_spec(), a.check_spec()
    fake = FakeApp()
    tmp = tempfile.mkdtemp()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "CLTStewardship", session=fake)
    b.run(dv, b.Log(os.path.join(tmp, "l.txt")), os.path.join(tmp, "c.json"))

    log1 = b.Log(os.path.join(tmp, "a.txt"))
    a.run(dv, log1)
    check_forms(fake)
    n_custom = sum(1 for vw in spec.VIEWS if not vw["default"])
    # views filtering on a ?column that doesn't exist (rollups made by hand) are skipped; formula columns exist
    skipped = sum(1 for vw in spec.VIEWS if any(f.startswith("?") and f"clt_{f[1:]}" not in
                                                fake.entities[f"clt_{vw['table']}"]["attrs"]
                                                for f, *_ in vw["filters"]))
    added = [v for v in fake.views.values() if not v.get("isdefault")]
    n_lists = len(set(a.LIST_LOOKUPS.values()))
    assert len(added) == n_custom - skipped + n_lists, (len(added), n_custom, skipped, n_lists)
    # sitemap + our tables + the two SharePoint tables (so Related shows Documents)
    core = core_components(fake)
    assert len(core) == expected_core_components(fake), (len(core), expected_core_components(fake))
    assert "md-sharepointdocument" in core and "md-sharepointdocumentlocation" in core
    assert "md-clt_project" not in core, "intake tables stay out of the core app"
    # list lookups are filtered to their list's view
    prop_form = next(f for f in fake.forms.values() if f["objecttypecode"] == "clt_property")
    root = ET.fromstring(prop_form["formxml"])
    county = next(c for c in root.iter("control") if c.get("id") == "clt_county")
    county_view = next(k for k, v in fake.views.items() if v.get("name") == "List: County")
    assert county.find("parameters/DefaultViewId").text == "{" + county_view + "}"
    assert county.find("parameters/DisableViewPicker").text == "true"
    # County only shows counties in the property's State (related-records filtering)
    assert county.find("parameters/FilterRelationshipName").text == "clt_listitem_listitem_state"
    assert county.find("parameters/DependentAttributeName").text == "clt_state"
    assert county.find("parameters/DependentAttributeType").text == "clt_listitem"
    assert "Development" not in str(fake.sitemaps) and not re.search(r"clt_document(?!sfolder)", str(fake.sitemaps))
    # Start here comes first: the Dashboard (where the app opens), the Verification hub and the guides; then Activities: Occupancy verification, Insurance verification, Resale
    smx = ET.fromstring(next(iter(fake.sitemaps.values()))["sitemapxml"])
    urls = [sa.get("Url") or sa.get("Entity") for sa in smx.iter("SubArea")]
    assert urls[:7] == ["$webresource:clt_/pages/overview.html", "$webresource:clt_/pages/stewardship.html", "$webresource:clt_/pages/field.html",
                        "$webresource:clt_/pages/guides.html",
                        "$webresource:clt_/pages/verify.html", "$webresource:clt_/pages/insurance.html", "$webresource:clt_/pages/resale.html"], urls[:8]
    assert [g.get("Title") or g.find("Titles/Title").get("Title") for g in smx.iter("Group")][:2] == ["Start here", "Activities"]
    import app_spec
    assert app_spec.PAGES["overview"][0] == "Stewardship Dashboard"
    for page in ("overview.html", "guides.html", "pages.css", "pages.js"):
        assert f"clt_/pages/{page}" in fake.webresources, page
    # Overview figures: every tile runs a view the build makes; properties by status (Left program has a view
    # but no tile; a common area has no status, so no status view counts it); households in four groups
    names = {(v["returnedtypecode"], v.get("name")) for v in fake.views.values()}
    page = open(os.path.join(os.path.dirname(__file__), "..", "webresources", "overview.html")).read()
    tiles = re.findall(r'e: "(clt_\w+)", v: "([^"]+)"', page)
    assert len(tiles) >= 13 and not [t for t in tiles if t not in names], [t for t in tiles if t not in names]
    assert ("clt_property", "Properties that left the program") in names and "left the program\"" not in page
    seen = set()
    for status, view in spec.PROPERTY_STATUS_VIEWS.items():
        fetch = next(v for v in fake.views.values() if v.get("name") == view)["fetchxml"]
        m = re.search(r'attribute="clt_status" operator="eq" value="(\d+)"', fetch)
        assert m and m[1] not in seen, view   # a real option value, a different one per status
        seen.add(m[1])
    assert set(spec.PROPERTY_STATUS_VIEWS) == set(b.CHOICES["propertystatus"][1])
    hh = {v["name"]: v["fetchxml"] for v in fake.views.values() if v["returnedtypecode"] == "clt_household"}
    assert {"Homeowners", "Former homeowners", "Applicants", "Potential purchasers"} <= set(hh)
    assert hh["Potential purchasers"].count("<value>") == 2 and 'operator="in"' in hh["Potential purchasers"]
    # Neighborhood: on the property form, filtered to its own list, and a column in the property views
    assert 'datafieldname="clt_neighborhood"' in prop_form["formxml"]
    # a page on a form: the web resource control, handed the record's id
    pages = [c for c in ET.fromstring(prop_form["formxml"]).iter("control") if c.get("classid") == "{9FDF5F91-88B1-47f4-AD53-C11EFC01A01D}"]
    assert len(pages) == 1 and pages[0].get("id").startswith("WebResource_") and pages[0].get("datafieldname") is None
    assert pages[0].find("parameters/Url").text == "clt_/pages/walkbys.html" and pages[0].find("parameters/PassParameters").text == "true"
    assert any(v.get("name") == "List: Neighborhood" for v in fake.views.values())
    assert 'name="clt_neighborhood"' in next(v for v in fake.views.values() if v.get("name") == "Properties by neighborhood")["layoutxml"]
    # Documents tab shows the SharePoint folder on Property, Household and Occupancy
    for ent in ("clt_property", "clt_household", "clt_occupancy"):
        fx = next(f for f in fake.forms.values() if f["objecttypecode"] == ent)["formxml"]
        assert f"{ent}_SharePointDocuments" in fx and ">sharepointdocument<" in fx, ent
    assert 'datafieldname="clt_development"' not in prop_form["formxml"]
    assert "clt_insurancepolicy_property" not in prop_form["formxml"]
    # file columns are not placed by the script; simulate a hand-made File column dragged onto a form
    fake.entities["clt_property"]["attrs"]["clt_photo"] = {
        "@odata.type": "Microsoft.Dynamics.CRM.FileAttributeMetadata",
        "DisplayName": {"LocalizedLabels": [{"Label": "Photo"}]}}
    spec.FORMS["property"]["tabs"][0][1][0][0][1].append("photo")  # as if app_spec listed it
    doc_id = next(k for k, f in fake.forms.items() if f["objecttypecode"] == "clt_property")
    droot = ET.fromstring(fake.forms[doc_id]["formxml"])
    rows = droot.find("tabs/tab/columns/column/sections/section/rows")
    cell = ET.SubElement(ET.SubElement(rows, "row"), "cell", id="{hand}")
    ET.SubElement(cell, "control", id="clt_photo", classid="{FILE-CONTROL}", datafieldname="clt_photo")
    fake.forms[doc_id]["formxml"] = ET.tostring(droot, encoding="unicode")
    assert len(fake.apps) == 1 and len(fake.sitemaps) == 1
    ET.fromstring(next(iter(fake.sitemaps.values()))["sitemapxml"])
    assert {c for c, _ in fake.sol_components} == {26, 61, 62, 80}
    # the names script is uploaded once and hooked to the forms; names are read-only and lower on the form
    import base64
    w = fake.webresources["clt_/scripts/names.js"]
    assert base64.b64decode(w["content"]).decode().startswith("// CLT Stewardship")
    for ent, needles in (("clt_property", ['attribute="clt_street"', 'attribute="clt_unit"', 'name="onsave"']),
                         ("clt_occupancy", ['attribute="clt_household"', 'attribute="clt_property"']),
                         ("clt_householdmember", ["CLT.Names.member"]), ("clt_household", ['name="onload"'])):
        fx = next(f for f in fake.forms.values() if f["objecttypecode"] == ent)["formxml"]
        froot = ET.fromstring(fx)
        assert froot.find("formLibraries/Library").get("name") == "clt_/scripts/names.js", ent
        tips = 'CLT.Tips.documents' in fx
        assert tips == (ent in ("clt_property", "clt_household", "clt_occupancy")), ent
        assert len(froot.findall("formLibraries/Library")) == (2 if tips else 1), ent
        for n in needles:
            assert n in fx, (ent, n)
    pfx = next(f for f in fake.forms.values() if f["objecttypecode"] == "clt_property")["formxml"]
    proot = ET.fromstring(pfx)
    name_ctl = next(c for c in proot.iter("control") if c.get("datafieldname") == "clt_name")
    assert name_ctl.get("disabled") == "true"
    order = [c.get("datafieldname") for c in proot.iter("control") if c.get("datafieldname")]
    assert order.index("clt_name") > order.index("clt_zip") and order[0] == "clt_recordnumber", order[:10]

    # Formula columns come from the schema build, so they're placed on the first run.
    occ_form = next(f for f in fake.forms.values() if f["objecttypecode"] == "clt_occupancy")
    assert 'datafieldname="clt_maximumresaleprice"' in occ_form["formxml"]
    assert any(v.get("name") == "Underinsured policies" for v in fake.views.values()), "view over Coverage check"
    # Add a column by hand (a formula over rollups), re-run: it gets placed, nothing duplicated.
    fake.entities["clt_property"]["attrs"]["clt_errrbalance"] = {
        "@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata",
        "DisplayName": {"LocalizedLabels": [{"Label": "ERRR balance"}]}}
    log2 = b.Log(os.path.join(tmp, "a.txt"))
    a.run(dv, log2)
    check_forms(fake)
    added2 = [v for v in fake.views.values() if not v.get("isdefault")]
    assert len(added2) == len(added)
    doc_form = fake.forms[doc_id]["formxml"]
    assert doc_form.count('datafieldname="clt_photo"') == 1, "hand-placed file field must survive a re-run"
    assert fake.webresources["clt_/scripts/names.js"]["patched"] == 0, "unchanged script must not be re-uploaded"
    assert doc_form.count("<Library ") == 2, "re-run must not duplicate form libraries (names.js and tips.js)"
    assert len(core_components(fake)) == expected_core_components(fake)
    prop_form2 = next(f for f in fake.forms.values() if f["objecttypecode"] == "clt_property")
    assert prop_form2["formxml"].count('datafieldname="clt_errrbalance"') >= 1
    assert len(fake.apps) == 1 and len(fake.sitemaps) == 1
    uv = next(v for v in added2 if v["name"] == "Underinsured policies")
    assert 'value="Underinsured"' in uv["fetchxml"]
    vv = next(v for v in added2 if v["name"] == "Verifications to do")
    assert "<value>768270000</value>" not in vv["fetchxml"]  # fake prefix is 72511
    assert "<value>725110000</value>" in vv["fetchxml"]
    # Upgrade order: app build on a v1-shaped environment keeps retired columns off forms and views
    fake.entities["clt_property"]["attrs"]["clt_county"] = {
        "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
        "DisplayName": {"LocalizedLabels": [{"Label": "County"}]}}
    a.run(dv, b.Log(os.path.join(tmp, "a.txt")), {"views", "forms"})
    prop_form = next(f for f in fake.forms.values() if f["objecttypecode"] == "clt_property")
    assert 'datafieldname="clt_county"' not in prop_form["formxml"]
    intake_app_test(fake, dv, tmp)
    stu_app_test(fake, dv, tmp)
    print(f"OK: {len(fake.forms)} forms, {len(added2)} added views, two apps + navigation; list lookups filtered; "
          "re-run places new formula columns, keeps the hand-placed file field, no duplicates.")


def core_components(fake):
    core_id = next(k for k, v in fake.apps.items() if v["uniquename"] == spec.APP["uniquename"])
    return [k for app, k in fake.app_components if app == core_id]


def expected_core_components(fake):
    from schema import TABLES
    core = [t["name"] for t in TABLES if t.get("solution", "core") == "core"] + spec.APP_EXTRA_TABLES
    return 1 + len(set(core)) + 2  # navigation + tables + the two SharePoint tables


def intake_app_test(fake, dv, tmp):
    """The second app: its own app, navigation and views; selection lists show Unique IDs only."""
    intake = a.use_app("intake")
    try:
        a.run(dv, b.Log(os.path.join(tmp, "i.txt")))
        apps = {v["uniquename"]: k for k, v in fake.apps.items()}
        assert set(apps) == {spec.APP["uniquename"], intake.APP["uniquename"]}
        smaps = [ET.fromstring(v["sitemapxml"]) for v in fake.sitemaps.values()]
        isite = next(x for x in smaps if "clt_project" in [sa.get("Entity") for sa in x.iter("SubArea")])
        assert "clt_property" not in [sa.get("Entity") for sa in isite.iter("SubArea")]
        mine = [k for app, k in fake.app_components if app == apps[intake.APP["uniquename"]]]
        assert "md-clt_selectionentry" in mine and "md-clt_occupancy" not in mine
        # Blind lottery: the entry views never show the application or household
        for vw in fake.views.values():
            if vw.get("returnedtypecode") == "clt_selectionentry":
                assert not re.search(r'attribute name="clt_(application|household)"', vw["fetchxml"]), vw["name"]
        n = len(fake.app_components)
        a.run(dv, b.Log(os.path.join(tmp, "i2.txt")))
        assert len(fake.app_components) == n and len(fake.apps) == 2, "re-run must not duplicate"
    finally:
        a.use_app("core")


def stu_app_test(fake, dv, tmp):
    """Stu: both sides in one app, as two areas, built from the same two specs."""
    stu = a.use_app("stu")
    try:
        assert set(stu.FORMS) == set(spec.FORMS) | set(a.importlib.import_module("app_spec_intake").FORMS)
        before = len(fake.apps)
        a.run(dv, b.Log(os.path.join(tmp, "s.txt")))
        apps = {v["uniquename"]: k for k, v in fake.apps.items()}
        assert "clt_Stu" in apps and len(fake.apps) == before + 1
        site = next(x for x in (ET.fromstring(v["sitemapxml"]) for v in fake.sitemaps.values())
                    if len(x.findall("Area")) == 2)
        titles = [ar.find("Titles/Title").get("Title") for ar in site.findall("Area")]
        assert titles == ["Stewardship", "Applications and Sales"], titles
        ids = [e.get("Id") for e in site.iter() if e.get("Id")]
        assert len(ids) == len(set(ids)), "navigation ids must be unique across the two areas"
        first, second = site.findall("Area")
        assert next(first.iter("SubArea")).get("Url") == "$webresource:clt_/pages/overview.html", "opens on the Overview"
        ents = lambda ar: [sa.get("Entity") for sa in ar.iter("SubArea")]
        assert "clt_property" in ents(first) and "clt_project" not in ents(first)
        assert "clt_project" in ents(second) and "clt_household" in ents(first) and "clt_household" in ents(second)
        mine = [k for app, k in fake.app_components if app == apps["clt_Stu"]]
        assert "md-clt_selectionentry" in mine and "md-clt_occupancy" in mine and len(mine) == len(set(mine))
        n = len(fake.app_components)
        a.run(dv, b.Log(os.path.join(tmp, "s2.txt")))
        assert len(fake.app_components) == n and len(fake.apps) == before + 1, "re-run must not duplicate"
    finally:
        a.use_app("core")


def upgrade_from_v02_test():
    """A real case: a v0.2 environment (old columns, no new tables), old keys already removed."""
    from schema import RETIRED, LOOKUPS
    fake = FakeApp()
    tmp = tempfile.mkdtemp()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "CLTStewardship", session=fake)
    b.run(dv, b.Log(os.path.join(tmp, "l.txt")), os.path.join(tmp, "c.json"))
    a.run(dv, b.Log(os.path.join(tmp, "a.txt")))
    new_tables = {"clt_listitem", "clt_formsubmission"}  # Development and Document were added in v0.3 and retired in v0.5
    # roll back to v0.2: drop new tables and every lookup that involves them
    for name in new_tables:
        del fake.entities[name]
    fake.forms = {k: f for k, f in fake.forms.items() if f["objecttypecode"] not in new_tables}
    fake.views = {k: v for k, v in fake.views.items() if v["returnedtypecode"] not in new_tables}
    fake.app_components = []
    fake.rels = {k: v for k, v in fake.rels.items()
                 if v["ReferencedEntity"] not in new_tables and v["ReferencingEntity"] not in new_tables}
    for v in fake.rels.values():
        pass
    lookup_pairs = {(x[0], x[1]) for x in LOOKUPS}
    for table, col in RETIRED["columns"]:
        ent = fake.entities[f"clt_{table}"]
        name = f"clt_{col}"
        if (table, col) in lookup_pairs:
            fake.rels = {k: v for k, v in fake.rels.items()
                         if not (v["ReferencingEntity"] == f"clt_{table}" and v["Lookup"]["SchemaName"] == name)}
        ent["attrs"][name] = {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                              "DisplayName": {"LocalizedLabels": [{"Label": col}]}}
    # v0.2 had no lookups to the new tables (they were all dropped above)
    fake.rels = {k: v for k, v in fake.rels.items() if v["ReferencedEntity"] not in new_tables}
    for t, e in fake.entities.items():
        for attr in list(e["attrs"]):
            meta = e["attrs"][attr]
            if meta.get("@odata.type", "").endswith("LookupAttributeMetadata") and not any(
                    r["ReferencingEntity"] == t and r["Lookup"]["SchemaName"] == attr for r in fake.rels.values()):
                del e["attrs"][attr]
    # put the old county field back on the property form, like v0.2 had it
    pid, pform = next((k, f) for k, f in fake.forms.items() if f["objecttypecode"] == "clt_property")
    fake.forms[pid]["formxml"] = pform["formxml"].replace("</rows>",
        '<row><cell id="{c}"><control id="clt_county" classid="{x}" datafieldname="clt_county"/></cell></row></rows>', 1)
    for c in RETIRED["choices"]:
        fake.optionsets[f"clt_{c}"] = {"MetadataId": str(uuid.uuid4()), "Options": []}
    for k in ["clt_listname", "clt_formtype", "clt_submissionstatus"]:
        fake.optionsets.pop(k, None)

    # Step 1: app build on the v0.2 environment must run and take clt_county off the form
    a.run(dv, b.Log(os.path.join(tmp, "a.txt")))
    pform = next(f for f in fake.forms.values() if f["objecttypecode"] == "clt_property")
    assert 'datafieldname="clt_county"' not in pform["formxml"]
    check_forms(fake)
    # Step 2: schema with --remove-retired
    b.run(dv, b.Log(os.path.join(tmp, "l.txt")), os.path.join(tmp, "c.json"), remove=True)
    assert all(n in fake.entities for n in new_tables)
    # Step 3: app build places everything
    a.run(dv, b.Log(os.path.join(tmp, "a.txt")))
    check_forms(fake)
    pform = next(f for f in fake.forms.values() if f["objecttypecode"] == "clt_property")
    assert 'datafieldname="clt_county"' in pform["formxml"] and 'DefaultViewId' in pform["formxml"]
    assert not re.search(r"clt_document(?!sfolder)", pform["formxml"]), "retired Document table still on the form"
    assert 'datafieldname="clt_state"' in pform["formxml"] and "FilterRelationshipName" in pform["formxml"]
    print("OK: upgrade from a v0.2 environment works in the README order (app, schema --remove-retired, app).")


if __name__ == "__main__":
    main()
    upgrade_from_v02_test()
