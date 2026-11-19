"""Offline test: tools/apply_branding.py against a fake environment."""
import base64
import json
import os
import re
import sys
import uuid
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_schema as b  # noqa: E402
import apply_branding as ab  # noqa: E402
from schema import ENVIRONMENT_VARIABLES  # noqa: E402
from test_offline import Resp  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class FakeEnv:
    def __init__(self):
        self.defs = {str(uuid.uuid4()): {"schemaname": f"clt_{v['name']}", "defaultvalue": ""} for v in ENVIRONMENT_VARIABLES}
        self.values = {}       # value id -> {def, value}
        self.webresources = {}  # name -> {id, content, type}
        self.appsettings = {}
        self.apps = {"clt_CLTStewardship": "app-1", "clt_CLTIntake": "app-2"}
        self.writes = []
        self.published = 0

    def request(self, method, url, headers=None, data=None, timeout=None):
        assert "MSCRM.SolutionUniqueName" not in headers, "branding must stay out of the solution"
        path = unquote(url.split("/api/data/v9.2/", 1)[1])
        body = json.loads(data) if data else None
        if method != "GET":
            self.writes.append((method, path))
        if path.startswith("environmentvariabledefinitions?"):
            name = re.search(r"schemaname eq '(\w+)'", path)[1]
            return Resp(200, {"value": [{"environmentvariabledefinitionid": i, **d} for i, d in self.defs.items()
                                        if d["schemaname"] == name]})
        if path.startswith("environmentvariablevalues"):
            if method == "GET":
                did = re.search(r"_environmentvariabledefinitionid_value eq ([\w-]+)", path)[1]
                return Resp(200, {"value": [{"environmentvariablevalueid": i, "value": v["value"]}
                                            for i, v in self.values.items() if v["def"] == did]})
            if method == "POST":
                did = re.fullmatch(r"/environmentvariabledefinitions\(([\w-]+)\)",
                                   body["EnvironmentVariableDefinitionId@odata.bind"])[1]
                assert did in self.defs and body["schemaname"] == self.defs[did]["schemaname"] + "_value"
                self.values[str(uuid.uuid4())] = {"def": did, "value": body["value"]}
                return Resp(204)
            vid = re.fullmatch(r"environmentvariablevalues\(([\w-]+)\)", path)[1]
            self.values[vid]["value"] = body["value"]
            return Resp(204)
        if path.startswith("webresourceset"):
            if method == "GET":
                name = re.search(r"name eq '([^']+)'", path)[1]
                w = self.webresources.get(name)
                return Resp(200, {"value": [{"webresourceid": w["id"], "content": w["content"]}] if w else []})
            if method == "POST":
                wid = str(uuid.uuid4())
                self.webresources[body["name"]] = {"id": wid, "content": body["content"], "type": body["webresourcetype"]}
                r = Resp(204)
                r.headers = {"OData-EntityId": f"https://x/api/data/v9.2/webresourceset({wid})"}
                return r
            w = next(w for w in self.webresources.values() if path == f"webresourceset({w['id']})")
            w["content"] = body["content"]
            return Resp(204)
        if path.startswith("appmodules?"):
            name = re.search(r"uniquename eq '([^']+)'", path)[1]
            return Resp(200, {"value": [{"appmoduleid": self.apps[name]}] if name in self.apps else []})
        if path.startswith("settingdefinitions?"):
            assert "CustomThemeDefinition" in path
            return Resp(200, {"value": [{"settingdefinitionid": "sd-1"}]})
        if path.startswith("EntityDefinitions(LogicalName='appsetting')/ManyToOneRelationships"):
            return Resp(200, {"value": [
                {"ReferencingAttribute": "settingdefinitionid", "ReferencingEntityNavigationPropertyName": "SettingDefinitionId"},
                {"ReferencingAttribute": "parentappmoduleid", "ReferencingEntityNavigationPropertyName": "ParentAppModuleId"}]})
        if path.startswith("appsettings"):
            if method == "GET":
                app = re.search(r"_parentappmoduleid_value eq ([\w-]+)", path)[1]
                return Resp(200, {"value": [{"appsettingid": k, "value": v["value"]}
                                            for k, v in self.appsettings.items() if v["app"] == app]})
            if method == "POST":
                assert body["SettingDefinitionId@odata.bind"] == "/settingdefinitions(sd-1)"
                app = re.fullmatch(r"/appmodules\(([\w-]+)\)", body["ParentAppModuleId@odata.bind"])[1]
                assert app in self.apps.values()
                assert body["uniquename"] not in [v["uniquename"] for v in self.appsettings.values()]
                self.appsettings[str(uuid.uuid4())] = {"value": body["value"], "app": app, "uniquename": body["uniquename"]}
                return Resp(204)
            sid = re.fullmatch(r"appsettings\(([\w-]+)\)", path)[1]
            self.appsettings[sid]["value"] = body["value"]
            return Resp(204)
        if path == "PublishXml":
            for a in self.apps.values():
                assert f"<appmodule>{a}</appmodule>" in body["ParameterXml"], "every app is published"
            for w in self.webresources.values():
                assert "{" + w["id"] + "}" in body["ParameterXml"], "every branding web resource is published"
            self.published += 1
            return Resp(204)
        raise AssertionError(f"unexpected {method} {path}")


def main():
    client = json.load(open(os.path.join(ROOT, "clients", "example", "client.json"), encoding="utf-8"))
    assert not ab.check_settings(client["settings"]), ab.check_settings(client["settings"])
    fake = FakeEnv()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "", session=fake)
    out = []
    png = b"\x89PNG fake logo"
    fetch = lambda url: (png, "image/png")  # noqa: E731

    ab.run(dv, out.append, client, dry_run=True, fetch=fetch)
    assert not fake.writes, fake.writes

    ab.run(dv, out.append, client, fetch=fetch)
    vals = {fake.defs[v["def"]]["schemaname"]: v["value"] for v in fake.values.values()}
    assert vals["clt_BrandHeaderColor"] == "#344734" and vals["clt_OrgName"] == "Example Community Land Trust"
    theme = base64.b64decode(fake.webresources[ab.THEME]["content"]).decode()
    assert fake.webresources[ab.THEME]["type"] == 4
    # Lower camelCase, as in Microsoft's docs; capitalized names are silently ignored.
    assert 'background="#344734"' in theme and 'foreground="#FFFFFF"' in theme and 'backgroundHover="#526B50"' in theme
    assert 'backgroundPressed="#2A392A"' in theme and "Background=" not in theme, theme
    assert 'basePaletteColor="#526B50"' in theme
    assert f'logoWebResource="{ab.LOGO}"' in theme and 'logoTooltip="Example Community Land Trust"' in theme
    assert "/" not in ab.THEME and "/" not in ab.LOGO
    logo = fake.webresources[ab.LOGO]
    assert logo["type"] == 5 and base64.b64decode(logo["content"]) == png
    assert sorted((v["app"], v["value"]) for v in fake.appsettings.values()) == [("app-1", ab.THEME), ("app-2", ab.THEME)]
    assert sorted(v["uniquename"] for v in fake.appsettings.values()) == ["clt_CustomThemeDefinition",
                                                                         "clt_CustomThemeDefinition_CLTIntake"]
    assert fake.published == 1

    # Re-run with the same values: no new values, theme unchanged
    n_values, before = len(fake.values), dict(fake.webresources[ab.THEME])
    ab.run(dv, out.append, client, fetch=fetch)
    assert len(fake.values) == n_values and fake.webresources[ab.THEME] == before and len(fake.appsettings) == 2

    # Change a color: value patched, theme updated
    client2 = json.loads(json.dumps(client))
    client2["settings"]["BrandHeaderColor"] = "#1F4E5F"
    ab.run(dv, out.append, client2, fetch=fetch)
    assert 'background="#1F4E5F"' in base64.b64decode(fake.webresources[ab.THEME]["content"]).decode()
    assert len(fake.values) == n_values

    # A broken logo link still brands the colors, just without a logo.
    def broken(url):
        raise OSError("404")
    fake2 = FakeEnv()
    ab.run(b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "", session=fake2), out.append, client, fetch=broken)
    t2 = base64.b64decode(fake2.webresources[ab.THEME]["content"]).decode()
    assert "logoWebResource" not in t2 and 'background="#344734"' in t2 and ab.LOGO not in fake2.webresources

    # Only the core app built so far: it's themed, the intake app is skipped with a note.
    fake3 = FakeEnv()
    del fake3.apps["clt_CLTIntake"]
    out3 = []
    ab.run(b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "", session=fake3), out3.append, client, fetch=fetch)
    assert [v["app"] for v in fake3.appsettings.values()] == ["app-1"]
    assert any("CLT Applications and Sales isn't there yet" in line for line in out3), out3

    # Stu (both sides in one app) is themed too, under its own setting name.
    fake4 = FakeEnv()
    fake4.apps = {"clt_Stu": "app-3"}
    ab.run(b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "", session=fake4), out.append, client, fetch=fetch)
    assert [(v["app"], v["uniquename"]) for v in fake4.appsettings.values()] == [("app-3", "clt_CustomThemeDefinition_Stu")]

    assert ab.check_settings({"BrandHeaderColor": "green"}) and ab.check_settings({"Nope": "x"})
    print("OK: branding sets the environment variables, builds the theme (camelCase, palette, logo), switches it on in both apps, stays out of "
          "the solution, and re-runs cleanly.")


if __name__ == "__main__":
    main()
