"""Offline test: runs the build against a fake Dataverse twice and checks the results."""
import json
import os
import re
import sys
import tempfile
import uuid
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import build_schema as b
import schema  # noqa: E402
from schema import CHOICES, TABLES, LOOKUPS, KEYS, SEED_LISTS, RETIRED, ENVIRONMENT_VARIABLES  # noqa: E402


class Resp:
    def __init__(self, code, body=None):
        self.status_code = code
        self._body = body
        self.content = b"" if body is None else json.dumps(body).encode()
        self.text = self.content.decode()
        self.headers = {}

    def json(self):
        return self._body


class FakeDataverse:
    VALID_TYPES = {"StringAttributeMetadata", "MemoAttributeMetadata", "IntegerAttributeMetadata",
                   "DecimalAttributeMetadata", "MoneyAttributeMetadata", "DateTimeAttributeMetadata",
                   "BooleanAttributeMetadata", "PicklistAttributeMetadata",
                   "MultiSelectPicklistAttributeMetadata", "FileAttributeMetadata"}

    def __init__(self):
        self.optionsets = {}   # name -> {MetadataId, Options}
        self.entities = {}     # logical -> {attrs: {logical: body}, keys: {}}
        self.rels = {}
        self.calls = []
        self.published = 0
        self.rows = []
        self.deleted = []
        self.sp_sites = []
        self.relabeled = []
        self.renamed_tables = []
        self.org_audit = False
        self.data = {}   # entity -> {id: row}, for the numbering test
        self.seeds = {}
        self.envvars = {}  # id -> definition body
        self.sysforms = {}  # formid -> (table, formxml); only used by the retirement test
        self.sp_locations = []

    def request(self, method, url, headers=None, data=None, timeout=None):
        assert headers["MSCRM.SolutionUniqueName"] == "CLTStewardship"
        path = unquote(url.split("/api/data/v9.2/", 1)[1])
        body = json.loads(data) if data else None
        self.calls.append((method, path))
        if method == "GET" and path.startswith("solutions?"):
            return Resp(200, {"value": [{"solutionid": "sol-1", "friendlyname": "CLT Stewardship",
                     "version": getattr(self, "solution_version", "0.1.0.0"),
                     "publisherid": {"uniquename": "unwindhousing", "customizationprefix": "clt",
                                     "customizationoptionvalueprefix": 72511}}]})
        if method == "PATCH" and path.startswith("solutions("):
            assert re.fullmatch(r"\d+\.\d+\.0\.0", body["version"])
            self.solution_version = body["version"]
            return Resp(204)
        m = re.fullmatch(r"GlobalOptionSetDefinitions\(Name='(\w+)'\)", path)
        if m and method == "GET":
            os_ = self.optionsets.get(m[1])
            return Resp(200, os_) if os_ else Resp(404, {"error": {"message": "Could not find optionset"}})
        if path == "GlobalOptionSetDefinitions" and method == "POST":
            assert body["IsGlobal"] and body["Name"].startswith("clt_")
            vals = [o["Value"] for o in body["Options"]]
            assert len(set(vals)) == len(vals) and all(725110000 <= v < 725120000 for v in vals)
            self.optionsets[body["Name"]] = {"MetadataId": str(uuid.uuid4()), "Options": [
                {"Value": o["Value"], "Label": {"UserLocalizedLabel": o["Label"]["LocalizedLabels"][0]}}
                for o in body["Options"]]}
            return Resp(204)
        if path == "InsertOptionValue":
            os_ = self.optionsets[body["OptionSetName"]]
            os_["Options"].append({"Value": body["Value"],
                                   "Label": {"UserLocalizedLabel": body["Label"]["LocalizedLabels"][0]}})
            return Resp(200, {"NewOptionValue": body["Value"]})
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)\?\$select=LogicalName", path)
        if m:
            return Resp(200, {"LogicalName": m[1]}) if m[1] in self.entities else Resp(404, {"error": {"message": "nf"}})
        if path == "EntityDefinitions" and method == "POST":
            name = body["SchemaName"].lower()
            prim = body["Attributes"][0]
            assert prim["IsPrimaryName"] and body["OwnershipType"] == "UserOwned"
            self.entities[name] = {"attrs": {prim["SchemaName"].lower(): prim, name + "id": {}}, "keys": {},
                                   "labels": (body["DisplayName"]["LocalizedLabels"][0]["Label"],
                                              body["DisplayCollectionName"]["LocalizedLabels"][0]["Label"])}
            return Resp(204)
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)/Attributes\(LogicalName='(\w+)'\)", path)
        if m and method == "DELETE":
            ent = self.entities[m[1]]
            assert m[2] in ent["attrs"], m[2]
            for k in ent["keys"].values():
                assert m[2] not in k["KeyAttributes"], f"{m[2]} still used by a key"
            del ent["attrs"][m[2]]
            self.deleted.append(m[2])
            return Resp(204)
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)/Keys\(LogicalName='(\w+)'\)", path)
        if m and method == "DELETE":
            del self.entities[m[1]]["keys"][m[2]]
            return Resp(204)
        m = re.fullmatch(r"GlobalOptionSetDefinitions\(([\w-]+)\)", path)
        if m and method == "DELETE":
            name = next(n for n, o in self.optionsets.items() if o["MetadataId"] == m[1])
            del self.optionsets[name]
            return Resp(204)
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)\?\$select=EntitySetName", path)
        if m:
            return Resp(200, {"EntitySetName": m[1] + "s"})
        if path.startswith("clt_listitems"):
            if method == "GET":
                val = int(re.search(r"clt_list eq (\d+)", path)[1])
                return Resp(200, {"value": [r for r in self.rows if r["clt_list"] == val][:1]})
            self.rows.append(body)
            return Resp(204)
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)/Attributes\?\$select=LogicalName,DisplayName(,RequiredLevel)?", path)
        if m:
            def label(meta):
                dn = meta.get("DisplayName") or {}
                lab = (dn.get("LocalizedLabels") or [{}])[0].get("Label")
                return {"UserLocalizedLabel": {"Label": lab} if lab else None}
            return Resp(200, {"value": [{"LogicalName": a, "DisplayName": label(meta), "RequiredLevel": meta.get("RequiredLevel")}
                                        for a, meta in self.entities[m[1]]["attrs"].items()]})
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)/Attributes\(LogicalName='(\w+)'\)/Microsoft\.Dynamics\.CRM\.(\w+)", path)
        if m and method == "GET":
            if m[2] not in self.entities[m[1]]["attrs"]:
                return Resp(404, {"error": {"message": "Could not find attribute"}})
            meta = self.entities[m[1]]["attrs"][m[2]]
            assert meta["@odata.type"].endswith(m[3]), (meta["@odata.type"], m[3])
            return Resp(200, dict(meta, **{"@odata.context": "ctx", "MetadataId": "md", "LogicalName": m[2],
                                           "DisplayName@x": "annotation"}))
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)/Attributes\(LogicalName='(\w+)'\)", path)
        if m and method == "PUT":
            assert headers.get("MSCRM.MergeLabels") == "true"
            assert not [k for k in body if "@" in k and k != "@odata.type"], "annotations sent back"
            old = self.entities[m[1]]["attrs"][m[2]]
            assert body["@odata.type"].split(".")[-1] == old["@odata.type"].split(".")[-1]
            assert body["SchemaName"] == old["SchemaName"], "PUT must send the full definition"
            self.entities[m[1]]["attrs"][m[2]] = {k: v for k, v in body.items() if k not in ("MetadataId", "LogicalName")}
            self.relabeled.append(m[2])
            return Resp(204)
        m = re.fullmatch(r"RelationshipDefinitions\(SchemaName='(\w+)'\)\?\$select=SchemaName", path)
        if m and method == "GET":
            return Resp(200, {"SchemaName": m[1]}) if m[1] in self.rels else Resp(404, {"error": {"message": "Could not find"}})
        m = re.fullmatch(r"RelationshipDefinitions\(SchemaName='(\w+)'\)", path)
        if m and method == "DELETE":
            if m[1] == "clt_development_property_development":
                assert not any("indicationOfSubgrid" in f for t, f in self.sysforms.values() if t == "clt_development"), \
                    "the Development form's Properties list still uses this lookup"
            rel = self.rels.pop(m[1])
            del self.entities[rel["ReferencingEntity"]]["attrs"][rel["Lookup"]["SchemaName"].lower()]
            self.deleted.append(m[1])
            return Resp(204)
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)", path)
        if m and method == "DELETE":
            # Like Dataverse: deleting a table deletes its relationships, including lookups to it on other tables
            for r in list(self.rels.values()):
                if r["ReferencedEntity"] == m[1] and r["ReferencingEntity"] != m[1]:
                    self.entities[r["ReferencingEntity"]]["attrs"].pop(r["Lookup"]["SchemaName"].lower(), None)
            del self.entities[m[1]]
            self.rels = {k: v for k, v in self.rels.items() if m[1] not in (v["ReferencingEntity"], v["ReferencedEntity"])}
            self.deleted.append(m[1])
            return Resp(204)
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)/Attributes(\?\$select=LogicalName(,AttributeType)?)?", path)
        if m:
            if m[1] not in self.entities:
                return Resp(404, {"error": {"message": "nf"}})
            ent = self.entities[m[1]]
            if method == "GET":
                def at(meta):
                    t = (meta.get("@odata.type") or "x.Uniqueidentifier").split(".")[-1]
                    return {"LookupAttributeMetadata": "Lookup", "StringAttributeMetadata": "String",
                            "PicklistAttributeMetadata": "Picklist"}.get(t, t.replace("AttributeMetadata", ""))
                return Resp(200, {"value": [{"LogicalName": a, "AttributeType": at(meta)}
                                            for a, meta in ent["attrs"].items()]})
            t = body["@odata.type"].split(".")[-1]
            assert t in self.VALID_TYPES, t
            if "Picklist" in t:
                ref = re.fullmatch(r"/GlobalOptionSetDefinitions\(([0-9a-f-]+)\)", body["GlobalOptionSet@odata.bind"])
                assert ref and any(o["MetadataId"] == ref[1] for o in self.optionsets.values())
            name = body["SchemaName"].lower()
            assert name not in ent["attrs"], f"duplicate {name}"
            if body.get("SourceType") == 3:
                # Like Dataverse: a formula naming a column that doesn't exist yet is refused.
                for own, other in re.findall(r"(?<![\w.'])(clt_\w+)(?:\.(clt_\w+))?", body["FormulaDefinition"]):
                    missing = (own if own not in ent["attrs"] else
                               other if other and not any(other in e["attrs"] for e in self.entities.values()) else None)
                    if missing:
                        return Resp(405, {"error": {"message": f"Name isn't valid. '{missing}' isn't recognized."}})
            ent["attrs"][name] = body
            return Resp(204)
        if path == "RelationshipDefinitions" and method == "POST":
            child = body["ReferencingEntity"]
            parent = body["ReferencedEntity"]
            assert (parent in self.entities or parent == "systemuser") and child in self.entities
            assert body["ReferencedAttribute"] == parent + "id"
            look = body["Lookup"]["SchemaName"].lower()
            assert look not in self.entities[child]["attrs"]
            assert body["SchemaName"] not in self.rels
            self.rels[body["SchemaName"]] = body
            self.entities[child]["attrs"][look] = body["Lookup"]
            return Resp(204)
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)/Keys(\?\$select=LogicalName)?", path)
        if m:
            if m[1] not in self.entities:
                return Resp(404, {"error": {"message": "nf"}})
            ent = self.entities[m[1]]
            if method == "GET":
                return Resp(200, {"value": [{"LogicalName": k} for k in ent["keys"]]})
            assert body["SchemaName"] not in ent["keys"]
            for a in body["KeyAttributes"]:
                assert a in ent["attrs"], a
            ent["keys"][body["SchemaName"]] = body
            return Resp(204)
        if path.startswith("systemforms?") and method == "GET":
            t = re.search(r"objecttypecode eq '(\w+)'", path)[1]
            return Resp(200, {"value": [dict(formid=k, formxml=f) for k, (tt, f) in self.sysforms.items() if tt == t]})
        m = re.fullmatch(r"systemforms\(([\w-]+)\)", path)
        if m and method == "PATCH":
            self.sysforms[m[1]] = (self.sysforms[m[1]][0], body["formxml"])
            return Resp(204)
        if path == "PublishXml":
            return Resp(204)
        m = re.fullmatch(r"(clt_\w+)s\?\$select=\w+&\$orderby=createdon asc", path)
        if m and method == "GET":
            return Resp(200, {"value": [{f"{m[1]}id": rid} for rid in self.data.get(m[1], {})]})
        m = re.fullmatch(r"(clt_\w+)s\?\$select=\w+&\$top=1", path)
        if m and method == "GET":   # seed rows: is the table empty?
            return Resp(200, {"value": [{f"{m[1]}id": rid} for rid in list(self.data.get(m[1], {}))[:1]]})
        m = re.fullmatch(r"(clt_\w+)s", path)
        if m and method == "POST" and m[1] + "s" != "clt_listitems":
            rid = f"row-{len(self.data.get(m[1], {})) + 1}"
            self.data.setdefault(m[1], {})[rid] = body
            return Resp(204)
        m = re.fullmatch(r"(clt_\w+)s\(([\w-]+)\)", path)
        if m and method == "PATCH" and m[1] in self.data:
            self.data[m[1]][m[2]].update(body)
            return Resp(204)
        if path == "SetAutoNumberSeed":
            self.seeds[(body["EntityName"], body["AttributeName"])] = body["Value"]
            return Resp(204)
        if path.startswith("environmentvariabledefinitions"):
            if method == "GET":
                name = re.search(r"schemaname eq '(\w+)'", path)[1]
                return Resp(200, {"value": [{"environmentvariabledefinitionid": i} for i, d in self.envvars.items()
                                            if d["schemaname"] == name]})
            assert body["schemaname"].startswith("clt_") and body["type"] == 100000000 and body["defaultvalue"] == ""
            self.envvars[str(uuid.uuid4())] = body
            return Resp(204)
        if path == "PublishAllXml":
            self.published += 1
            return Resp(204)
        # SharePoint document management (v0.5)
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)\?\$select=DisplayName,DisplayCollectionName", path)
        if m:
            one, many = self.entities[m[1]].get("labels", ("", ""))
            return Resp(200, {"DisplayName": {"UserLocalizedLabel": {"Label": one}},
                              "DisplayCollectionName": {"UserLocalizedLabel": {"Label": many}}})
        if path == "organizations?$select=organizationid,isauditenabled":
            return Resp(200, {"value": [{"organizationid": "org-1", "isauditenabled": self.org_audit}]})
        if path == "organizations(org-1)" and method == "PATCH":
            self.org_audit = body["isauditenabled"]
            return Resp(204)
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)\?\$select=IsAuditEnabled", path)
        if m:
            return Resp(200, {"IsAuditEnabled": {"Value": self.entities[m[1]].get("audit", False), "CanBeChanged": True}})
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)\?\$select=IsDocumentManagementEnabled", path)
        if m:
            return Resp(200, {"IsDocumentManagementEnabled": self.entities[m[1]].get("docmgmt", False)})
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='(\w+)'\)", path)
        if m and method == "GET":
            return Resp(200, {"@odata.context": "ctx", "MetadataId": "md-" + m[1], "LogicalName": m[1],
                              "SchemaName": m[1], "HasNotes": True,
                              "IsDocumentManagementEnabled": self.entities[m[1]].get("docmgmt", False),
                              "IsAuditEnabled": {"Value": self.entities[m[1]].get("audit", False), "CanBeChanged": True},
                              "HasNotes@OData.Community.Display.V1.FormattedValue": "Yes"})
        if m and method == "PUT":
            assert headers.get("MSCRM.MergeLabels") == "true", "metadata PUT must merge labels"
            assert body["@odata.type"] == "Microsoft.Dynamics.CRM.EntityMetadata"
            assert body["LogicalName"] == m[1] and body["HasNotes"] is True, "PUT must send the full definition"
            assert not [k for k in body if "@" in k and k != "@odata.type"], "annotations sent back"
            self.entities[m[1]]["docmgmt"] = body["IsDocumentManagementEnabled"]
            self.entities[m[1]]["audit"] = body["IsAuditEnabled"]["Value"]
            if "DisplayName" in body:
                self.entities[m[1]]["labels"] = (body["DisplayName"]["LocalizedLabels"][0]["Label"],
                                                 body["DisplayCollectionName"]["LocalizedLabels"][0]["Label"])
                self.renamed_tables.append(m[1])
            return Resp(204)
        if path.startswith("sharepointsites"):
            if method == "GET":
                return Resp(200, {"value": self.sp_sites})
            row = dict(body, sharepointsiteid=str(uuid.uuid4()))
            self.sp_sites.append(row)
            r = Resp(204)
            r.headers = {"OData-EntityId": f"https://fake/api/data/v9.2/sharepointsites({row['sharepointsiteid']})"}
            return r
        if path.startswith("sharepointdocumentlocations"):
            if method == "GET":
                parent = re.search(r"_parentsiteorlocation_value eq ([0-9a-f-]+)", path)[1]
                rows = [x for x in self.sp_locations if x["_parent"] == parent]
                rel = re.search(r"relativeurl eq '([^']*)'", path)
                if rel:
                    rows = [x for x in rows if x["relativeurl"] == rel[1]]
                if "_regardingobjectid_value eq null" in path:
                    rows = [x for x in rows if not x.get("_regarding")]
                return Resp(200, {"value": rows})
            bind = body.get("parentsiteorlocation_sharepointsite@odata.bind") or body[
                "parentsiteorlocation_sharepointdocumentlocation@odata.bind"]
            parent = re.fullmatch(r"/sharepoint(?:sites|documentlocations)\(([0-9a-f-]+)\)", bind)[1]
            assert any(x["sharepointsiteid"] == parent for x in self.sp_sites) or any(
                x["sharepointdocumentlocationid"] == parent for x in self.sp_locations)
            row = dict(body, _parent=parent, sharepointdocumentlocationid=str(uuid.uuid4()))
            self.sp_locations.append(row)
            r = Resp(204)
            r.headers = {"OData-EntityId": "https://fake/api/data/v9.2/sharepointdocumentlocations"
                                           f"({row['sharepointdocumentlocationid']})"}
            return r
        raise AssertionError(f"unexpected call {method} {path}")


class FakeSharePoint:
    """Fake SharePoint REST for one site: libraries keyed by web address."""

    def __init__(self, fail=False):
        self.libs = {}   # server-relative url -> {Id, Title}
        self.fail = fail

    def request(self, method, url, headers=None, data=None, timeout=None):
        if self.fail:
            return Resp(401, {"odata.error": {"message": {"value": "Unsupported app only token."}}})
        assert headers["Authorization"] == "Bearer sp-token"
        site, path = url.split("/_api/", 1)
        assert site == "https://contoso.sharepoint.com/sites/Stewardship"
        path = unquote(path)
        body = json.loads(data) if data else None
        m = re.fullmatch(r"web/GetList\('([^']+)'\)\?\$select=Id,Title", path)
        if m and method == "GET":
            lib = self.libs.get(m[1])
            return Resp(200, lib) if lib else Resp(404, {"odata.error": {"message": {"value": "not found"}}})
        if path == "web/lists" and method == "POST":
            assert body["BaseTemplate"] == 101 and body["__metadata"]["type"] == "SP.List"
            key = "/sites/Stewardship/" + body["Title"]
            assert key not in self.libs
            self.libs[key] = {"Id": str(uuid.uuid4()), "Title": body["Title"]}
            return Resp(201, self.libs[key])
        m = re.fullmatch(r"web/lists\(guid'([0-9a-f-]+)'\)", path)
        if m and method == "POST":
            assert headers["X-HTTP-Method"] == "MERGE" and headers["IF-MATCH"] == "*"
            lib = next(v for v in self.libs.values() if v["Id"] == m[1])
            lib["Title"] = body["Title"]
            return Resp(204)
        raise AssertionError(f"unexpected SharePoint call {method} {path}")


def main():
    assert not b.check_spec(), b.check_spec()
    fake = FakeDataverse()
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "choice-values.json")

    log1 = b.Log(os.path.join(tmp, "log.txt"))
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "token", "CLTStewardship", session=fake)
    b.run(dv, log1, out)
    ncols = sum(len(t["columns"]) for t in TABLES)
    ndocs = sum(1 for t in TABLES if t.get("documents"))
    naudit = sum(1 for t in TABLES if t.get("audit")) + 1  # + the environment switch
    expected = (len(CHOICES) + len(TABLES) + ncols + len(LOOKUPS) + len(KEYS) + len(SEED_LISTS) + ndocs + naudit
                + len(ENVIRONMENT_VARIABLES) + sum(len(r) for r in b.SEED_ROWS.values()))
    # Starter rows: the organization's eligibility, with choice values mapped from labels
    org = list(fake.data["clt_eligibility"].values())
    assert len(org) == 1 and org[0]["clt_name"] == "Organization eligibility" and org[0]["clt_maxami"] == 80, org
    assert isinstance(org[0]["clt_firsttimebuyer"], int)
    # System-user lookups point at systemuser, not clt_systemuser
    assert fake.rels["clt_systemuser_certification_certifiedby"]["ReferencedEntity"] == "systemuser"
    assert ndocs >= 1 and fake.entities["clt_property"].get("docmgmt") is True
    assert fake.org_audit is True and fake.entities["clt_application"].get("audit") is True
    assert not fake.entities["clt_property"].get("audit")
    assert log1.counts["created"] == expected, (log1.counts, expected)
    assert not fake.sp_sites, "SharePoint setup must only run with --sharepoint-site"
    assert sorted(d["schemaname"] for d in fake.envvars.values()) == sorted(f"clt_{v['name']}" for v in ENVIRONMENT_VARIABLES)

    # Second run: everything already there, nothing created.
    log2 = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log2, out)
    assert log2.counts["created"] == 0, log2.counts

    # Formula columns are created as formulas (after the lookups they read through) ...
    ami = fake.entities["clt_application"]["attrs"]["clt_amipct"]
    assert ami["SourceType"] == 3 and "clt_limit50forsize" in ami["FormulaDefinition"]
    assert "clt_amilimits.clt_size4" in fake.entities["clt_application"]["attrs"]["clt_limit50forsize"]["FormulaDefinition"]
    assert "DefaultValue" not in fake.entities["clt_householdmember"]["attrs"]["clt_isadult"]
    # ... and a formula changed in Dataverse (or in schema.py) is put back to schema.py's on the next build.
    ami["FormulaDefinition"] = "1"
    fake.relabeled.clear()
    log2b = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log2b, out)
    assert log2b.counts["created"] == 1 and fake.relabeled == ["clt_amipct"], (log2b.counts, fake.relabeled)
    assert fake.entities["clt_application"]["attrs"]["clt_amipct"]["FormulaDefinition"] == schema.AMI_PCT
    # Dataverse saves choices as [@global_clt_errrtype].'<value>': that's the same formula, not a change.
    cv = json.load(open(out))
    signed = fake.entities["clt_errrtransaction"]["attrs"]["clt_signedamount"]
    stored = b.stored_formula(signed["FormulaDefinition"], {k[4:]: v for k, v in cv.items()})
    assert "[@global_clt_errrtype].'" in stored and "[@'ERRR" not in stored, stored
    signed["FormulaDefinition"] = stored
    fake.relabeled.clear()
    log2c = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log2c, out)
    assert log2c.counts["created"] == 0 and not fake.relabeled, (log2c.counts, fake.relabeled)
    # The offline check catches a formula that names a column the table doesn't have.
    bad = {"name": "x", "columns": [{"name": "y", "kind": "fx", "result": "int", "formula": "clt_nope + 1"}]}
    assert b.check_formula(bad, bad["columns"][0], {"x": bad}), "unknown column not caught"
    # ... money used outside Decimal(), and formulas over Dataverse's 1,000 characters.
    cash = {"name": "x", "columns": [{"name": "m", "kind": "money"},
                                     {"name": "y", "kind": "fx", "result": "int", "formula": "If(IsBlank(clt_m), 0, 1)"},
                                     {"name": "z", "kind": "fx", "result": "int", "formula": "1" + " + 1" * 400}]}
    assert "Decimal" in " ".join(b.check_formula(cash, cash["columns"][1], {"x": cash}))
    assert "1,000" in " ".join(b.check_formula(cash, cash["columns"][2], {"x": cash}))
    txt = {"name": "x", "columns": [{"name": "n", "kind": "int"},
                                    {"name": "t", "kind": "fx", "result": "text", "formula": "Text(clt_n)"}]}
    assert "format" in " ".join(b.check_formula(txt, txt["columns"][1], {"x": txt}))

    # Spec change: add a choice option, re-run, only that is added.
    CHOICES["feetype"][1].append("HOA dues")
    log3 = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log3, out)
    assert log3.counts["created"] == 1, log3.counts
    CHOICES["feetype"][1].pop()

    vals = json.load(open(out))
    assert vals["clt_errrtype"]["Repair draw"] == 725110003
    assert vals["clt_feetype"]["HOA dues"] == 725110003
    assert sum(1 for r in fake.rows if r["clt_list"] == vals["clt_listname"]["Income type"]) == 18
    rel = next(r for r in fake.rows if r["clt_name"] == "Spouse or partner")
    assert "Domestic partner" in rel["clt_formanswers"]
    assert fake.published == 5  # first run, re-run, formula update, saved-form re-run, choice addition
    assert fake.solution_version == b.VERSION + ".0.0"
    # Defaults resolved to real values
    hh = fake.entities["clt_household"]["attrs"]["clt_status"]
    assert hh["DefaultFormValue"] == vals["clt_householdstatus"]["Applicant"]
    migration_test()
    v05_cleanup_test()
    numbers_and_names_test()
    publish_timeout_test()
    sharepoint_test()
    print(f"OK: {expected} items created on first run, 0 on re-run, choice additions handled.")
    print(f"   {len(fake.entities)} tables, {sum(len(e['attrs']) for e in fake.entities.values())} attributes "
          f"(incl. primary name and id), {len(fake.rels)} relationships.")


def migration_test():
    """Turn a v2 fake back into a v1-shaped environment, then upgrade it."""
    fake = FakeDataverse()
    tmp = tempfile.mkdtemp()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "token", "CLTStewardship", session=fake)
    b.run(dv, b.Log(os.path.join(tmp, "log.txt")), os.path.join(tmp, "c.json"))
    lookup_pairs = {(x[0], x[1]) for x in LOOKUPS}
    for table, col in RETIRED["columns"]:
        ent = fake.entities[f"clt_{table}"]
        name = f"clt_{col}"
        if (table, col) in lookup_pairs:  # a lookup in v2: put the v1 non-lookup column back
            fake.rels = {k: v for k, v in fake.rels.items()
                         if not (v["ReferencingEntity"] == f"clt_{table}" and v["Lookup"]["SchemaName"] == name)}
        ent["attrs"][name] = {"@odata.type": "Microsoft.Dynamics.CRM.PicklistAttributeMetadata"}
    for table, key in RETIRED["keys"]:
        fake.entities[f"clt_{table}"]["keys"][f"clt_{table}_{key}"] = {"KeyAttributes": [f"clt_{key}"]}
    for c in RETIRED["choices"]:
        fake.optionsets[f"clt_{c}"] = {"MetadataId": str(uuid.uuid4()), "Options": []}
    try:
        b.run(dv, b.Log(os.path.join(tmp, "log.txt")), os.path.join(tmp, "c.json"))
        raise AssertionError("should have stopped without --remove-retired")
    except b.DataverseError as e:
        assert "--remove-retired" in str(e), e
    log = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"), remove=True)
    for c in RETIRED["choices"]:
        assert f"clt_{c}" not in fake.optionsets
    lookups_back = sum(1 for t, c in RETIRED["columns"] if (t, c) in lookup_pairs)
    expected = len(RETIRED["keys"]) + len(RETIRED["columns"]) + len(RETIRED["choices"]) + lookups_back
    assert log.counts["created"] == expected, (log.counts, expected)
    log = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"))
    assert log.counts["created"] == 0
    print(f"OK: upgrade removed {len(RETIRED['columns'])} columns, {len(RETIRED['keys'])} keys, "
          f"{len(RETIRED['choices'])} choices, and recreated {lookups_back} of them as list lookups.")


def v05_cleanup_test():
    """A v0.4-shaped environment: Development and Document tables, Insurance policy's Property lookup,
    State as text, and the old APN label. Upgrade with --remove-retired, then re-run."""
    fake = FakeDataverse()
    tmp = tempfile.mkdtemp()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "token", "CLTStewardship", session=fake)
    b.run(dv, b.Log(os.path.join(tmp, "log.txt")), os.path.join(tmp, "c.json"))

    def lookup(child, col, parent):
        name = f"clt_{parent}_{child}_{col}"
        fake.rels[name] = {"SchemaName": name, "ReferencingEntity": f"clt_{child}", "ReferencedEntity": f"clt_{parent}",
                           "Lookup": {"SchemaName": f"clt_{col}", "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata"}}
        fake.entities[f"clt_{child}"]["attrs"][f"clt_{col}"] = fake.rels[name]["Lookup"]
    for t in RETIRED["tables"]:
        fake.entities[f"clt_{t}"] = {"attrs": {"clt_name": {}, f"clt_{t}id": {}}, "keys": {}}
    lookup("property", "development", "development")
    fake.sysforms["f1"] = ("clt_development", '<form><tabs><tab><columns><column><sections><section><rows><row>'
                           '<cell id="a"><control id="clt_name" datafieldname="clt_name"/></cell></row><row>'
                           '<cell id="b"><control id="sg" indicationOfSubgrid="true"/></cell></row>'
                           '</rows></section></sections></column></columns></tab></tabs></form>')
    lookup("insurancepolicy", "property", "property")
    lookup("document", "property", "property")
    lookup("document", "documenttype", "listitem")
    for child, col in (("property", "state"), ("household", "mailingstate")):
        fake.rels.pop(f"clt_listitem_{child}_{col}")
        fake.entities[f"clt_{child}"]["attrs"][f"clt_{col}"] = {
            "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata", "SchemaName": f"clt_{col}"}
    apn = fake.entities["clt_property"]["attrs"]["clt_apn"]
    apn["DisplayName"] = b.L("APN")
    fake.entities["clt_incomelimitset"]["labels"] = ("Income limit set", "Income limit sets")

    try:
        b.run(dv, b.Log(os.path.join(tmp, "log.txt")), os.path.join(tmp, "c.json"))
        raise AssertionError("should have stopped without --remove-retired")
    except b.DataverseError as e:
        assert "table development" in str(e) and "insurancepolicy.property" in str(e), e
    log = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"), remove=True)
    for t in RETIRED["tables"]:
        assert f"clt_{t}" not in fake.entities
    assert "clt_property" not in fake.entities["clt_insurancepolicy"]["attrs"]
    assert fake.entities["clt_property"]["attrs"]["clt_state"]["@odata.type"].endswith("LookupAttributeMetadata")
    assert fake.relabeled == ["clt_apn"], fake.relabeled
    assert fake.entities["clt_property"]["attrs"]["clt_apn"]["DisplayName"]["LocalizedLabels"][0]["Label"] == "Parcel number"
    assert fake.renamed_tables == ["clt_incomelimitset"], fake.renamed_tables
    assert fake.entities["clt_incomelimitset"]["labels"] == ("HUD AMI Limits", "HUD AMI Limits")
    # 2 State columns removed + 2 lookups + 6 tables (Development, Document, and the 4 from simplifying
    # eligibility) + 2 State lookups recreated + 1 label + 1 table name
    assert log.counts["created"] == 14, log.counts
    assert "clt_development" not in fake.entities["clt_property"]["attrs"]
    log = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"))
    assert log.counts["created"] == 0, log.counts
    print("OK: v0.5 cleanup removes the Development and Document tables and the insurance Property link, "
          "turns State into a list lookup, renames APN, and re-runs clean.")


def numbers_and_names_test():
    """Record numbers start at 1 (existing rows numbered oldest first, once); name optionality follows schema.py."""
    fake = FakeDataverse()
    tmp = tempfile.mkdtemp()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "token", "CLTStewardship", session=fake)
    b.run(dv, b.Log(os.path.join(tmp, "log.txt")), os.path.join(tmp, "c.json"))
    auto = [(t["name"], c) for t in TABLES for c in t["columns"] if c["kind"] == "autonumber"]
    assert {t for t, _ in auto} == {"property", "household", "application", "occupancy", "homeownerrequest", "sale"}
    assert all(fake.seeds[(f"clt_{t}", "clt_recordnumber")] == 1 for t, _ in auto)
    prop = fake.entities["clt_property"]
    assert prop["attrs"]["clt_recordnumber"]["AutoNumberFormat"] == "P-{SEQNUM:5}"
    assert prop["attrs"]["clt_name"]["RequiredLevel"]["Value"] == "None"
    assert fake.entities["clt_fee"]["attrs"]["clt_name"]["RequiredLevel"]["Value"] == "ApplicationRequired"
    # An environment from before v0.5: no record number column, three properties, name required.
    del prop["attrs"]["clt_recordnumber"]
    fake.data["clt_property"] = {"p-old": {}, "p-mid": {}, "p-new": {}}
    prop["attrs"]["clt_name"]["RequiredLevel"] = b.required_level(True)
    log = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"))
    assert [r["clt_recordnumber"] for r in fake.data["clt_property"].values()] == ["P-00001", "P-00002", "P-00003"]
    assert fake.seeds[("clt_property", "clt_recordnumber")] == 4
    assert prop["attrs"]["clt_name"]["RequiredLevel"]["Value"] == "None"
    assert log.counts["created"] == 2, log.counts  # the column, and the name setting
    # Never tightens: a table whose name is optional in the environment stays optional
    fake.entities["clt_fee"]["attrs"]["clt_name"]["RequiredLevel"] = b.required_level(False)
    log = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"))
    assert fake.entities["clt_fee"]["attrs"]["clt_name"]["RequiredLevel"]["Value"] == "None"
    assert log.counts["created"] == 0, log.counts
    log = b.Log(os.path.join(tmp, "log.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"))
    assert log.counts["created"] == 0, log.counts
    print("OK: record numbers start at 1, existing rows numbered once; name optional on Property, Household, Occupancy.")


def publish_timeout_test():
    """A publish that outlasts the wait is reported, not a crash (Dataverse keeps publishing)."""
    import requests

    class SlowPublish(FakeDataverse):
        def request(self, method, url, headers=None, data=None, timeout=None):
            if url.endswith("/PublishAllXml"):
                assert timeout == 1800
                raise requests.exceptions.ReadTimeout("Read timed out.")
            return super().request(method, url, headers, data, timeout)
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "log.txt")
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "token", "CLTStewardship", session=SlowPublish())
    b.run(dv, b.Log(path), os.path.join(tmp, "c.json"))
    assert "Still publishing after 30 minutes" in open(path).read()
    print("OK: a slow publish is reported and the run finishes.")


def sharepoint_test():
    """--sharepoint-site: site record, library (created then retitled), document location; idempotent;
    falls back to manual instructions when SharePoint refuses; refuses to fight another default site."""
    site = "https://contoso.sharepoint.com/sites/Stewardship"
    docs = [t for t in TABLES if t.get("documents")]
    tmp = tempfile.mkdtemp()

    fake, sp_fake = FakeDataverse(), FakeSharePoint()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "token", "CLTStewardship", session=fake)
    sp = b.SharePoint(site + "/", lambda: "sp-token", session=sp_fake)
    b.run(dv, b.Log(os.path.join(tmp, "l.txt")), os.path.join(tmp, "c.json"))
    log = b.Log(os.path.join(tmp, "l.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"), sharepoint_site=site + "/", sp=sp)
    assert log.counts["created"] == 1 + 2 * len(docs), log.counts
    assert fake.sp_sites == [dict(fake.sp_sites[0], name="Stewardship", absoluteurl=site, isdefault=True)]
    lib = sp_fake.libs["/sites/Stewardship/clt_property"]
    assert lib["Title"] == "Property Documents", lib
    loc = fake.sp_locations[0]
    assert loc["relativeurl"] == "clt_property" and loc["name"] == "Property Documents"
    assert loc["_parent"] == fake.sp_sites[0]["sharepointsiteid"]
    log = b.Log(os.path.join(tmp, "l.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"), sharepoint_site=site, sp=sp)
    assert log.counts["created"] == 0, log.counts
    assert len(fake.sp_sites) == 1 and len(fake.sp_locations) == len(docs)

    # --sharepoint-folder DEV: one parent folder location under each library, once; a different name is refused.
    log = b.Log(os.path.join(tmp, "l.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"), sharepoint_site=site, sp=sp, sharepoint_folder="DEV")
    assert log.counts["created"] == len(docs), log.counts
    devs = [x for x in fake.sp_locations if x["relativeurl"] == "DEV"]
    libs = {x["sharepointdocumentlocationid"] for x in fake.sp_locations if x["_parent"] == fake.sp_sites[0]["sharepointsiteid"]}
    assert len(devs) == len(docs) and {x["_parent"] for x in devs} == libs
    assert not any(k.startswith("regardingobjectid") for x in devs for k in x), "a parent folder isn't tied to a record"
    log = b.Log(os.path.join(tmp, "l.txt"))
    b.run(dv, log, os.path.join(tmp, "c.json"), sharepoint_site=site, sp=sp, sharepoint_folder="DEV")
    assert log.counts["created"] == 0 and len(fake.sp_locations) == 2 * len(docs)
    try:
        b.run(dv, b.Log(os.path.join(tmp, "l.txt")), os.path.join(tmp, "c.json"), sharepoint_site=site, sp=sp,
              sharepoint_folder="TEST")
        raise AssertionError("should refuse a second parent folder")
    except b.DataverseError as e:
        assert "different parent folder (DEV)" in str(e), e
    path = os.path.join(tmp, "warn.txt")
    b.run(dv, b.Log(path), os.path.join(tmp, "c.json"), sharepoint_site=site, sp=sp)
    assert "has a parent folder (DEV)" in open(path).read()

    # SharePoint refuses the sign-in or the call: Dataverse side still done, manual steps printed.
    fake = FakeDataverse()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "token", "CLTStewardship", session=fake)
    path = os.path.join(tmp, "fail.txt")
    log = b.Log(path)
    b.run(dv, log, os.path.join(tmp, "c.json"), sharepoint_site=site,
          sp=b.SharePoint(site, lambda: "sp-token", session=FakeSharePoint(fail=True)))
    text = open(path).read()
    assert "To finish by hand" in text and "'clt_property'" in text and "'Property Documents'" in text, text
    assert len(fake.sp_sites) == 1 and len(fake.sp_locations) == len(docs)

    def no_token():
        raise b.SharePointError("SharePoint sign-in failed: AADSTS65001 consent required")
    fake = FakeDataverse()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "token", "CLTStewardship", session=fake)
    path = os.path.join(tmp, "fail2.txt")
    b.run(dv, b.Log(path), os.path.join(tmp, "c.json"), sharepoint_site=site,
          sp=b.SharePoint(site, no_token, session=FakeSharePoint()))
    assert "AADSTS65001" in open(path).read()

    # A different default site already exists: stop rather than take over.
    fake = FakeDataverse()
    fake.sp_sites.append({"sharepointsiteid": str(uuid.uuid4()), "absoluteurl": "https://contoso.sharepoint.com/sites/Other",
                          "isdefault": True})
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "token", "CLTStewardship", session=fake)
    try:
        b.run(dv, b.Log(os.path.join(tmp, "l.txt")), os.path.join(tmp, "c.json"),
              sharepoint_site=site, sp=b.SharePoint(site, lambda: "sp-token", session=FakeSharePoint()))
        raise AssertionError("should stop when another default site exists")
    except b.DataverseError as e:
        assert "default SharePoint site" in str(e), e
    print(f"OK: SharePoint setup creates site, {len(docs)} library and location; re-run creates nothing; "
          f"falls back to manual steps; won't replace another default site.")


if __name__ == "__main__":
    main()
