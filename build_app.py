#!/usr/bin/env python3
"""
Build the CLT Stewardship model-driven app from app_spec.py:
  views (default lists and work queues) -> main forms -> app + navigation -> publish

Run after build_schema.py. Run it again any time: it updates the views, forms and
navigation it manages to match app_spec.py (so make layout changes in app_spec.py),
and places any formula or rollup columns you have added since the last run.

Usage:
  python3 build_app.py --check
  python3 build_app.py --url https://yourorg.crm.dynamics.com
  python3 build_app.py --url ... --only forms        (views, forms or app)
"""
import argparse
import os
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from build_schema import (Dataverse, DataverseError, Log, make_token_provider, label_of, ln, publish_all,
                          DEFAULT_CLIENT_ID, SOLUTION, PREFIX)
from schema import TABLES, LOOKUPS, CHOICES, LIST_LOOKUPS, RETIRED
import importlib
import app_spec as spec

# Each app has its own spec file. --app picks one. Stu (both sides in one app, as two areas) is the default;
# core and intake build one side as an app of its own, for a client that wants only that side.
APP_SPECS = {"stu": "app_spec_stu", "core": "app_spec", "intake": "app_spec_intake"}


def use_app(name):
    """Point this module at another app's spec (app_spec_stu.py, app_spec.py or app_spec_intake.py)."""
    global spec
    spec = importlib.import_module(APP_SPECS[name])
    return spec

LANG = 1033
NS = uuid.UUID("6f1c2a52-6c0e-4c55-9d7e-3c5f0a1b2c3d")  # stable ids across runs

CLASSID = {
    "text": "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}",
    "autonumber": "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}",  # shown as a text box (read-only)
    "email": "{ADA2203E-B4CD-49be-9DDF-234642B43B52}",
    "phone": "{8C10015A-B339-4982-9474-A95FE05631A5}",
    "url": "{71716B6C-711E-476c-8AB8-5D11542BFB47}",
    "memo": "{E0DECE4B-6FC8-4a8f-A065-082708572369}",
    "int": "{C6D124CA-7EDA-4a60-AEA9-7FB8D318B68F}",
    "dec": "{C3EFE0C3-0EC6-42be-8349-CBD9079DFD8E}",
    "double": "{0D2C745A-E5A8-4c8f-BA63-C6D3BB604660}",
    "money": "{533B9E00-756B-4312-95A0-DC888637AC78}",
    "date": "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}",
    "datetime": "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}",  # same calendar control, with time
    "bool": "{67FAC785-CD58-4f9f-ABB3-4B7DDC6ED5ED}",
    "choice": "{3EF39988-22BB-4f0b-BBBE-64B5A3748AEE}",
    "multi": "{4AA28AB7-9C13-4F57-A73D-AD894D048B5F}",
    "lookup": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}",
    "subgrid": "{E7A81278-8635-4d9e-8D4D-59480B391C5B}",
    "page": "{9FDF5F91-88B1-47f4-AD53-C11EFC01A01D}",  # a web resource shown on the form
}
TYPE_TO_KIND = {"String": "text", "Memo": "memo", "Integer": "int", "Decimal": "dec", "Double": "double",
                "Money": "money", "DateTime": "date", "Boolean": "bool", "Picklist": "choice",
                "Lookup": "lookup", "Customer": "lookup", "Owner": "lookup"}
# A formula column shows as its result type (dec, int, text, bool).
SCHEMA_KINDS = {(t["name"], c["name"]): c["result"] if c["kind"] == "fx" else c["kind"]
                for t in TABLES for c in t["columns"]}
SCHEMA_CHOICE = {(t["name"], c["name"]): c["choice"] for t in TABLES for c in t["columns"]
                 if c["kind"] in ("choice", "multi")}
TABLE_LABELS = {t["name"]: (t["label"], t["plural"]) for t in TABLES}
RELATIONSHIPS = {f"{PREFIX}_{p}_{c}_{col}" for c, col, p, *_ in LOOKUPS}
RETIRED_COLUMNS = set(RETIRED["columns"])


def gid(*parts):
    return "{" + str(uuid.uuid5(NS, "/".join(str(p) for p in parts))) + "}"


def opt(name):
    """'?x' -> ('x', True); 'x' -> ('x', False). A leading '!' (read-only on the form) is ignored here."""
    name = name.lstrip("!")
    return (name[1:], True) if name.startswith("?") else (name, False)


# --------------------------------------------------------------------------- spec checks
def check_spec():
    problems = []
    tables = {t["name"]: {c["name"] for c in t["columns"]} | {"name"} for t in TABLES}
    for child, col, *_ in LOOKUPS:
        tables[child].add(col)
    manual = {(t, c) for t, c, *_ in spec.MANUAL_COLUMNS}

    def known(table, field):
        f, optional = opt(field)
        if f in tables.get(table, ()):
            return True
        return optional and (table, f) in manual

    for _, group in spec.NAVIGATION:
        for t in group:
            if t.startswith("page:"):
                if t[5:] not in spec.PAGES:
                    problems.append(f"navigation: unknown page {t}")
                elif spec.PAGES[t[5:]][1] not in spec.WEB_RESOURCES:
                    problems.append(f"navigation: page {t} isn't in WEB_RESOURCES")
            elif t not in tables:
                problems.append(f"navigation: unknown table {t}")
    here = os.path.dirname(os.path.abspath(__file__))
    for name, path in spec.WEB_RESOURCES.items():
        if not os.path.exists(os.path.join(here, path)):
            problems.append(f"web resource {name}: missing file {path}")
        elif os.path.splitext(path)[1] not in WEBRESOURCE_TYPES:
            problems.append(f"web resource {name}: unsupported file type {path}")
    for view in spec.VIEWS:
        t = view["table"]
        for f, _ in view["columns"]:
            if not known(t, f):
                problems.append(f"view {t}/{view['name']}: unknown column {f}")
        for f, op, val in view["filters"]:
            if not known(t, f):
                problems.append(f"view {t}/{view['name']}: unknown filter column {f}")
            fname = opt(f)[0]
            cs = SCHEMA_CHOICE.get((t, fname))
            if cs:
                for label in (val if isinstance(val, list) else [val]):
                    if label not in CHOICES[cs][1]:
                        problems.append(f"view {t}/{view['name']}: '{label}' not an option of {cs}")
    for t, form in spec.FORMS.items():
        if t not in tables:
            problems.append(f"form: unknown table {t}")
            continue
        for f in form["header"]:
            if not known(t, f):
                problems.append(f"form {t} header: unknown {f}")
        if len(form["header"]) > 4:
            problems.append(f"form {t}: header has more than 4 fields")
        for tab_label, columns in form["tabs"]:
            for col in columns:
                for sec_label, items in col:
                    for item in items:
                        if isinstance(item, dict) and item.get("sharepoint"):
                            if not any(x["name"] == t and x.get("documents") for x in TABLES):
                                problems.append(f"form {t}: Documents tab needs documents= on the table in schema.py")
                        elif isinstance(item, dict) and item.get("page"):
                            if item["webresource"] not in spec.WEB_RESOURCES:
                                problems.append(f"form {t}: page {item['webresource']} isn't in WEB_RESOURCES")
                        elif isinstance(item, dict):
                            if item["relationship"] not in RELATIONSHIPS:
                                problems.append(f"form {t}: unknown relationship {item['relationship']}")
                        elif not known(t, item):
                            problems.append(f"form {t} / {tab_label} / {sec_label}: unknown {item}")
    for t, hooks in spec.FORM_SCRIPTS.items():
        if t not in spec.FORMS:
            problems.append(f"form script on {t}: no form for that table")
        for event, field, fn in hooks:
            if event not in ("onload", "onsave", "onchange") or (event == "onchange") != bool(field):
                problems.append(f"form script on {t}: bad event {event} {field}")
            if field and not known(t, field):
                problems.append(f"form script on {t}: unknown field {field}")
            lib = script_library(fn)
            if lib not in spec.WEB_RESOURCES:
                problems.append(f"form script on {t}: no library for {fn} in SCRIPT_LIBRARIES")
                continue
            src = open(os.path.join(here, spec.WEB_RESOURCES[lib])).read()
            if fn.split(".")[-1] + ":" not in src:
                problems.append(f"form script on {t}: {fn} not found in {lib}")
    return problems


# --------------------------------------------------------------------------- environment info
class Env:
    """What exists in the environment: attributes, type codes, choice values, default views."""

    def __init__(self, dv, log):
        self.dv, self.log = dv, log
        self.attrs, self.otc, self.metadataid, self.default_view = {}, {}, {}, {}
        self.choice_values = {}
        self.list_view = {}
        self.missing = set()
        for t in TABLES:
            name = ln(t["name"])
            e = dv.call("GET", f"EntityDefinitions(LogicalName='{name}')"
                               "?$select=LogicalName,ObjectTypeCode,MetadataId"
                               "&$expand=Attributes($select=LogicalName,AttributeType,AttributeTypeName,DisplayName)",
                        ok404=True)
            if e is None:  # added in a newer version; build_schema.py hasn't created it yet
                self.missing.add(t["name"])
                self.attrs[t["name"]] = {}
                continue
            self.otc[t["name"]] = e["ObjectTypeCode"]
            self.metadataid[t["name"]] = e["MetadataId"]
            self.attrs[t["name"]] = {
                a["LogicalName"]: {"type": a["AttributeType"],
                                   "typename": (a.get("AttributeTypeName") or {}).get("Value"),
                                   "label": label_of(a.get("DisplayName") and {"Label": a["DisplayName"]} or {})
                                   or a["LogicalName"]}
                for a in e["Attributes"]}
        for key in CHOICES:
            os_ = dv.call("GET", f"GlobalOptionSetDefinitions(Name='{ln(key)}')", ok404=True)
            self.choice_values[key] = {label_of(o): o["Value"] for o in (os_ or {}).get("Options", [])}
        if self.missing:
            log(f"\nNot created yet (run build_schema.py, then this again): "
                + ", ".join(TABLE_LABELS[t][1] for t in sorted(self.missing)))

    def has(self, table, field):
        a = self.attrs.get(table, {}).get(ln(field))
        if a is None:
            return False
        if (table, field) in RETIRED_COLUMNS and a["type"] != "Lookup":
            return False  # old version-1 column waiting to be removed: keep it off forms and views
        return True

    def kind(self, table, field):
        if (table, field) in SCHEMA_KINDS:
            return SCHEMA_KINDS[(table, field)]
        a = self.attrs[table][ln(field)]
        if a["typename"] == "MultiSelectPicklistType":
            return "multi"
        return TYPE_TO_KIND.get(a["type"], "text")

    def label(self, table, field):
        return self.attrs[table][ln(field)]["label"]

    def sharepoint_view_id(self):
        """SharePoint's own 'Document Associated Grid' view, used for Documents tabs."""
        if "sharepointdocument" not in self.default_view:
            r = self.dv.call("GET", "savedqueries?$select=savedqueryid&$filter=returnedtypecode eq 'sharepointdocument'"
                                    " and name eq 'Document Associated Grid'")
            self.default_view["sharepointdocument"] = r["value"][0]["savedqueryid"] if r.get("value") else None
        return self.default_view["sharepointdocument"]

    def default_view_id(self, table):
        if table in self.missing:
            return None
        if table not in self.default_view:
            r = self.dv.call("GET", f"savedqueries?$select=savedqueryid,name&$filter=returnedtypecode eq "
                                    f"'{ln(table)}' and querytype eq 0 and isdefault eq true")
            self.default_view[table] = r["value"][0]["savedqueryid"] if r.get("value") else None
        return self.default_view[table]


def add_to_solution(dv, log, component_id, component_type, what):
    try:
        dv.call("POST", "AddSolutionComponent", {
            "ComponentId": component_id, "ComponentType": component_type,
            "SolutionUniqueName": dv.solution, "AddRequiredComponents": False,
            "DoNotIncludeSubcomponents": False})
    except DataverseError as e:
        log(f"    note: could not add {what} to the solution automatically ({e}). "
            "Add it with Solutions > Add existing.")


# --------------------------------------------------------------------------- views
def fetch_and_layout(env, view):
    t = view["table"]
    cols = [(opt(f)[0], w) for f, w in view["columns"] if env.has(t, opt(f)[0])]
    sorts = view["sort"] if isinstance(view["sort"], list) else [view["sort"]]
    sorts = [(f, d) for f, d in sorts if env.has(t, f)] or [("name", False)]
    conds = ['<condition attribute="statecode" operator="eq" value="0" />']
    for f, op, val in view["filters"]:
        f = opt(f)[0]
        cs = SCHEMA_CHOICE.get((t, f))
        conv = (lambda x: str(env.choice_values[cs].get(x, -1))) if cs else (lambda x: str(x))
        if op == "in":
            values = "".join(f"<value>{escape(conv(x))}</value>" for x in val)
            conds.append(f'<condition attribute="{ln(f)}" operator="in">{values}</condition>')
        elif op in ("null", "not-null"):
            conds.append(f'<condition attribute="{ln(f)}" operator="{op}" />')
        else:
            conds.append(f'<condition attribute="{ln(f)}" operator="{op}" value="{escape(conv(val))}" />')
    pk = ln(t) + "id"
    attrs = "".join(f'<attribute name="{ln(c)}" />' for c, _ in cols)
    fetch = (f'<fetch version="1.0" output-format="xml-platform" mapping="logical" distinct="false">'
             f'<entity name="{ln(t)}"><attribute name="{pk}" />{attrs}'
             + "".join(f'<order attribute="{ln(f)}" descending="{str(d).lower()}" />' for f, d in sorts) +
             f'<filter type="and">{"".join(conds)}</filter></entity></fetch>')
    cells = "".join(f'<cell name="{ln(c)}" width="{w}" />' for c, w in cols)
    layout = (f'<grid name="resultset" object="{env.otc[t]}" jump="{ln("name")}" select="1" icon="1" preview="1">'
              f'<row name="result" id="{pk}">{cells}</row></grid>')
    return fetch, layout


def upsert_view(dv, env, log, t, name, fetch, layout, desc=""):
    r = dv.call("GET", "savedqueries?$select=savedqueryid&$filter=returnedtypecode eq "
                       f"'{ln(t)}' and querytype eq 0 and name eq '{name}'")
    if r.get("value"):
        vid = r["value"][0]["savedqueryid"]
        dv.call("PATCH", f"savedqueries({vid})", {"fetchxml": fetch, "layoutxml": layout, "description": desc})
        log.created(f"{TABLE_LABELS[t][0]}: {name} updated")
        return vid
    res = dv.call("POST", "savedqueries", {
        "name": name, "description": desc, "returnedtypecode": ln(t),
        "querytype": 0, "fetchxml": fetch, "layoutxml": layout, "isdefault": False})
    vid = res.get("_id")
    if vid:
        add_to_solution(dv, log, vid, 26, f"view {name}")
    log.created(f"{TABLE_LABELS[t][0]}: {name} added")
    return vid


def list_views():
    """One view per editable list, used to filter each list dropdown."""
    return [dict(table="listitem", name=f"List: {name}", columns=[("name", 220), ("sortorder", 80)],
                 sort=[("sortorder", False), ("name", False)], filters=[("list", "eq", name)], default=False,
                 desc=f"Values in the {name} list")
            for name in sorted(set(LIST_LOOKUPS.values()))]


def build_views(dv, env, log):
    log("\nViews")
    for view in ([] if "listitem" in env.missing else list_views()):
        fetch, layout = fetch_and_layout(env, view)
        env.list_view[view["name"][len("List: "):]] = upsert_view(dv, env, log, "listitem", view["name"],
                                                                 fetch, layout, view["desc"])
    for view in spec.VIEWS:
        t = view["table"]
        if t in env.missing:
            continue
        missing = [f for f, *_ in view["filters"] if not env.has(t, opt(f)[0])]
        title = view["name"] or f"Active {TABLE_LABELS[t][1]} (default)"
        if missing:
            log(f"  - {TABLE_LABELS[t][0]}: {title} skipped until {', '.join(opt(m)[0] for m in missing)} exists")
            continue
        fetch, layout = fetch_and_layout(env, view)
        if view["default"]:
            vid = env.default_view_id(t)
            if not vid:
                log(f"  - {title}: no default view found, skipped")
                continue
            dv.call("PATCH", f"savedqueries({vid})", {"fetchxml": fetch, "layoutxml": layout})
            log.created(f"{TABLE_LABELS[t][0]}: {title} updated")
            continue
        upsert_view(dv, env, log, t, view["name"], fetch, layout, view["desc"])


def load_list_views(dv, env):
    """When running --only forms, find the list views made by an earlier run."""
    for name in set(LIST_LOOKUPS.values()):
        if "listitem" in env.missing:
            break
        if name not in env.list_view:
            r = dv.call("GET", "savedqueries?$select=savedqueryid&$filter=returnedtypecode eq "
                               f"'{ln('listitem')}' and querytype eq 0 and name eq 'List: {name}'")
            env.list_view[name] = r["value"][0]["savedqueryid"] if r.get("value") else None


# --------------------------------------------------------------------------- forms
def label_el(parent, text):
    labels = ET.SubElement(parent, "labels")
    ET.SubElement(labels, "label", description=text, languagecode=str(LANG))


def field_cell(row, env, t, field, prefix="", readonly=False):
    cell = ET.SubElement(row, "cell", id=gid(t, prefix, "cell", field), showlabel="true", locklevel="0")
    label_el(cell, env.label(t, field))
    ctl = ET.SubElement(cell, "control", id=prefix + ln(field), classid=CLASSID[env.kind(t, field)],
                        datafieldname=ln(field), disabled="true" if readonly else "false")
    list_name = LIST_LOOKUPS.get((t, field))
    params = None
    if list_name and env.list_view.get(list_name):
        params = ET.SubElement(ctl, "parameters")
        for k, val in [("AutoResolve", "true"), ("DisableMru", "false"), ("DisableQuickFind", "false"),
                       ("DisableViewPicker", "true"), ("DefaultViewId", "{" + env.list_view[list_name].strip("{}") + "}"),
                       ("AllowFilterOff", "false")]:
            ET.SubElement(params, k).text = val
    dep = spec.DEPENDENT_LOOKUPS.get((t, field))
    if dep and env.has(t, dep[0]) and env.kind(t, dep[0]) == "lookup":
        # Related-records filtering: only show targets whose relationship matches the other field's value.
        dep_field, relationship = dep
        target = next(parent for child, col, parent, *_ in LOOKUPS if child == t and col == dep_field)
        if params is None:
            params = ET.SubElement(ctl, "parameters")
        for k, val in [("FilterRelationshipName", relationship), ("DependentAttributeName", ln(dep_field)),
                       ("DependentAttributeType", ln(target))]:
            ET.SubElement(params, k).text = val


def subgrid_rows(rows, env, t, item, n):
    cell = ET.SubElement(ET.SubElement(rows, "row"), "cell", id=gid(t, "sg", n), showlabel="false",
                         rowspan=str(item["rows"]), colspan="1", auto="false")
    label_el(cell, item["label"])
    ctl = ET.SubElement(cell, "control", id=f"sg_{item['child']}_{n}", classid=CLASSID["subgrid"],
                        indicationOfSubgrid="true")
    params = ET.SubElement(ctl, "parameters")
    sp = item.get("sharepoint")
    view_id = (env.sharepoint_view_id() if sp else env.default_view_id(item["child"])) or ""
    for k, val in [("ViewId", view_id), ("IsUserView", "false"), ("RelationshipName", item["relationship"]),
                   ("TargetEntityType", item["child"] if sp else ln(item["child"])), ("AutoExpand", "Fixed"),
                   ("EnableQuickFind", "false"), ("EnableViewPicker", "false"), ("ViewIds", None),
                   ("EnableJumpBar", "false"), ("ChartGridMode", "Grid"), ("VisualizationId", None),
                   ("IsUserChart", "false"), ("EnableChartPicker", "false"), ("RecordsPerPage", "10")]:
        el = ET.SubElement(params, k)
        if val is not None:
            el.text = val
    for _ in range(item["rows"] - 1):
        ET.SubElement(rows, "row")


def page_rows(rows, t, item, n):
    """A page (web resource) shown on the form. It is handed the record's id and table name (?id=...&typename=...)."""
    cell = ET.SubElement(ET.SubElement(rows, "row"), "cell", id=gid(t, "page", n), showlabel="false",
                         rowspan=str(item["rows"]), colspan="1", auto="false")
    label_el(cell, item["label"])
    name = re.sub(r"\W", "_", item["webresource"].rsplit("/", 1)[-1].rsplit(".", 1)[0])
    ctl = ET.SubElement(cell, "control", id=f"WebResource_{name}_{n}", classid=CLASSID["page"])
    params = ET.SubElement(ctl, "parameters")
    for k, val in [("Url", item["webresource"]), ("PassParameters", "true"), ("Security", "false"), ("Scrolling", "auto"),
                   ("Border", "false"), ("ShowOnMobileClient", "true")]:
        ET.SubElement(params, k).text = val
    for _ in range(item["rows"] - 1):
        ET.SubElement(rows, "row")


def build_tabs(env, t, form, kept=None):
    """kept: cells from the current form for fields this script can't place itself (file columns)."""
    kept = kept or {}
    tabs = ET.Element("tabs")
    placed, skipped, n = [], [], 0
    for ti, (tab_label, columns) in enumerate(form["tabs"]):
        tab = ET.SubElement(tabs, "tab", name=f"tab_{ti}", id=gid(t, "tab", ti), IsUserDefined="0",
                            locklevel="0", showlabel="true", expanded="true", verticallayout="true")
        label_el(tab, tab_label)
        cols_el = ET.SubElement(tab, "columns")
        width = f"{100 // len(columns)}%"
        for ci, col in enumerate(columns):
            sections = ET.SubElement(ET.SubElement(cols_el, "column", width=width), "sections")
            for si, (sec_label, items) in enumerate(col):
                sec = ET.SubElement(sections, "section", name=f"tab_{ti}_c{ci}_s{si}", id=gid(t, "sec", ti, ci, si),
                                    IsUserDefined="0", locklevel="0", showlabel="true", showbar="false",
                                    columns="1", labelwidth="115", celllabelalignment="Left",
                                    celllabelposition="Left")
                label_el(sec, sec_label)
                rows = ET.SubElement(sec, "rows")
                for item in items:
                    if isinstance(item, dict):
                        n += 1
                        if item.get("page"):
                            page_rows(rows, t, item, n)
                            continue
                        if item.get("sharepoint"):
                            if not env.sharepoint_view_id():
                                skipped.append("Documents (SharePoint document management isn't set up)")
                                continue
                            subgrid_rows(rows, env, t, item, n)
                            continue
                        if not env.has(item["child"], item["lookup"]):
                            skipped.append(f"{item['label']} list")
                            continue
                        subgrid_rows(rows, env, t, item, n)
                        continue
                    field, _ = opt(item)
                    if not env.has(t, field):
                        skipped.append(field)
                        continue
                    if field in placed:
                        continue
                    if env.kind(t, field) not in CLASSID:
                        if ln(field) in kept:
                            ET.SubElement(rows, "row").append(kept[ln(field)])
                            placed.append(field)
                        else:
                            skipped.append(f"{field} (drag it onto the form once in the form designer)")
                        continue
                    placed.append(field)
                    field_cell(ET.SubElement(rows, "row"), env, t, field, readonly=item.startswith("!"))
                if not len(rows):
                    sections.remove(sec)
    return tabs, skipped


def build_header(env, t, form):
    header = ET.Element("header", id=gid(t, "header"), celllabelposition="Top", columns="1111",
                        labelwidth="115", celllabelalignment="Left")
    row = ET.SubElement(ET.SubElement(header, "rows"), "row")
    fields = [opt(f)[0] for f in form["header"] if env.has(t, opt(f)[0])]
    for f in fields:
        field_cell(row, env, t, f, prefix="header_")
    for i in range(4 - len(fields)):
        cell = ET.SubElement(row, "cell", id=gid(t, "header", "empty", i), showlabel="false")
        label_el(cell, "")
    return header


WEBRESOURCE_TYPES = {".html": 1, ".css": 2, ".js": 3, ".xml": 4, ".png": 5, ".svg": 11}


def script_library(fn):
    """Web resource holding a form script function: CLT.Names.property -> clt_/scripts/names.js."""
    return spec.SCRIPT_LIBRARIES.get(fn.rsplit(".", 1)[0])


def deploy_web_resources(dv, env, log):
    """Upload the form scripts and pages (web resources). Re-run safe: only changed content is uploaded."""
    import base64
    log("\nScripts and pages")
    env.scripts = set()
    for name, path in spec.WEB_RESOURCES.items():
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), path), "rb").read()
        content = base64.b64encode(src).decode()
        r = dv.call("GET", f"webresourceset?$select=webresourceid,content&$filter=name eq '{name}'")
        if r.get("value"):
            wr = r["value"][0]
            if wr.get("content") != content:
                dv.call("PATCH", f"webresourceset({wr['webresourceid']})", {"content": content})
                log.created(f"{name} updated")
            else:
                log.skipped(name)
        else:
            wtype = WEBRESOURCE_TYPES[os.path.splitext(path)[1]]
            res = dv.call("POST", "webresourceset", {"name": name, "displayname": name.split("/")[-1],
                                                     "webresourcetype": wtype, "content": content})
            wid = res.get("_id")
            if wid:
                add_to_solution(dv, log, wid, 61, name)
            log.created(f"{name} added")
        env.scripts.add(name)


def form_events(t):
    """formLibraries and events elements for a table's scripts (stable ids, so re-runs don't churn)."""
    hooks = spec.FORM_SCRIPTS.get(t)
    if not hooks:
        return None, None
    libs = ET.Element("formLibraries")
    for lib in dict.fromkeys(script_library(fn) for _, _, fn in hooks):
        ET.SubElement(libs, "Library", name=lib,
                      libraryUniqueId="{" + str(uuid.uuid5(uuid.NAMESPACE_URL, lib)) + "}")
    events = ET.Element("events")
    for event, field, fn in hooks:
        lib = script_library(fn)
        attrs = {"name": event, "application": "false", "active": "false"}
        if field:
            attrs["attribute"] = ln(field)
        ev = next((e for e in events if e.attrib == attrs), None) or ET.SubElement(events, "event", attrs)
        handlers = ev.find("Handlers") if ev.find("Handlers") is not None else ET.SubElement(ev, "Handlers")
        ET.SubElement(handlers, "Handler", functionName=fn, libraryName=lib, parameters="", enabled="true",
                      passExecutionContext="true",
                      handlerUniqueId="{" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"{t}/{event}/{field}/{fn}")) + "}")
    return libs, events


def build_forms(dv, env, log):
    log("\nForms")
    load_list_views(dv, env)
    for t, form in spec.FORMS.items():
        if t in env.missing:
            continue
        r = dv.call("GET", "systemforms?$select=formid,name,formxml&$filter=objecttypecode eq "
                           f"'{ln(t)}' and type eq 2")
        forms = r.get("value", [])
        if not forms:
            log(f"  - {TABLE_LABELS[t][0]}: no main form found, skipped")
            continue
        target = next((f for f in forms if f["name"] == "Information"), forms[0])
        root = ET.fromstring(target["formxml"])
        kept = {}
        for cell in root.iter("cell"):
            ctl = cell.find("control")
            if ctl is not None and ctl.get("datafieldname") and ctl.get("classid") not in CLASSID.values():
                kept[ctl.get("datafieldname")] = cell
        tabs, skipped = build_tabs(env, t, form, kept)
        header = build_header(env, t, form)
        children = list(root)
        old_tabs = root.find("tabs")
        idx = children.index(old_tabs) if old_tabs is not None else 0
        if old_tabs is not None:
            root.remove(old_tabs)
        root.insert(idx, tabs)
        old_header = root.find("header")
        if old_header is not None:
            hidx = list(root).index(old_header)
            root.remove(old_header)
            root.insert(hidx, header)
        else:
            root.insert(idx + 1, header)
        libs, events = form_events(t)
        if libs is not None and all(lib.get("name") in getattr(env, "scripts", set()) for lib in libs):
            for tag, new in (("formLibraries", libs), ("events", events)):
                old = root.find(tag)
                if old is not None:
                    root.remove(old)
                root.append(new)
        dv.call("PATCH", f"systemforms({target['formid']})", {"formxml": ET.tostring(root, encoding="unicode")})
        note = f" (waiting for: {', '.join(sorted(set(skipped)))})" if skipped else ""
        log.created(f"{TABLE_LABELS[t][0]} form{note}")


# --------------------------------------------------------------------------- app
def sitemap_xml(missing=()):
    """Navigation. A spec with AREAS (Stu) gets one area per entry, each with its own groups; ids carry the
    area number because the same table can sit in two areas. A spec without AREAS is one area."""
    def title(text):
        return f'<Titles><Title LCID="{LANG}" Title="{escape(text, {chr(34): "&quot;"})}" /></Titles>'
    def subarea(t, pre):
        if t.startswith("page:"):
            label, wr = spec.PAGES[t[5:]]
            return (f'<SubArea Id="sub_{pre}page_{t[5:]}" Url="$webresource:{wr}" AvailableOffline="false" '
                    f'PassParams="false">{title(label)}</SubArea>')
        return (f'<SubArea Id="sub_{pre}{t}" Entity="{ln(t)}" AvailableOffline="true" PassParams="false">'
                f'{title(TABLE_LABELS[t][1])}</SubArea>')
    areas = getattr(spec, "AREAS", None)
    single = areas is None
    if single:
        areas = [(spec.APP["name"], spec.NAVIGATION)]
    out = []
    for ai, (area, navigation) in enumerate(areas):
        pre = "" if single else f"{ai}_"
        groups = []
        for gi, (group, tables) in enumerate(navigation):
            subs = "".join(subarea(t, pre) for t in tables if t not in missing)
            if subs:
                groups.append(f'<Group Id="grp_{pre}{gi}" IsProfile="false">{title(group)}{subs}</Group>')
        if groups:
            out.append(f'<Area Id="{"area_main" if single else f"area_{ai}"}" ShowGroups="true">'
                       f'{title(area)}{"".join(groups)}</Area>')
    return f'<SiteMap IntroducedVersion="7.0.0.0">{"".join(out)}</SiteMap>'


def find_one(dv, entityset, field, value, idfield):
    for path in (f"{entityset}?$select={idfield}&$filter={field} eq '{value}'",
                 f"{entityset}/Microsoft.Dynamics.CRM.RetrieveUnpublishedMultiple()"
                 f"?$select={idfield}&$filter={field} eq '{value}'"):
        try:
            r = dv.call("GET", path)
        except DataverseError:
            continue
        if r.get("value"):
            return r["value"][0][idfield]
    return None


def build_app(dv, env, log):
    log("\nApp and navigation")
    uname = spec.APP["uniquename"]
    smap = sitemap_xml(env.missing)
    sitemap_id = find_one(dv, "sitemaps", "sitemapnameunique", uname, "sitemapid")
    if sitemap_id:
        dv.call("PATCH", f"sitemaps({sitemap_id})", {"sitemapxml": smap})
        log.created("Navigation updated")
    else:
        res = dv.call("POST", "sitemaps", {"sitemapname": spec.APP["name"], "sitemapnameunique": uname,
                                           "isappaware": True, "sitemapxml": smap})
        sitemap_id = res.get("_id") or find_one(dv, "sitemaps", "sitemapnameunique", uname, "sitemapid")
        add_to_solution(dv, log, sitemap_id, 62, "navigation (site map)")
        log.created("Navigation created")

    app_id = find_one(dv, "appmodules", "uniquename", uname, "appmoduleid")
    if app_id:
        log.skipped(f"App '{spec.APP['name']}'")
    else:
        res = dv.call("POST", "appmodules", {
            "name": spec.APP["name"], "uniquename": uname, "description": spec.APP["description"],
            "webresourceid": "953b9fac-1e5e-e611-80d6-00155ded156f", "clienttype": 4})
        app_id = res.get("_id") or find_one(dv, "appmodules", "uniquename", uname, "appmoduleid")
        add_to_solution(dv, log, app_id, 80, "app")
        log.created(f"App '{spec.APP['name']}' created")

    nav_tables = [t for _, ts in spec.NAVIGATION for t in ts if t not in env.missing and not t.startswith("page:")]
    # Tables the app needs besides its navigation (related lists, lookups): the spec's APP_TABLES, or for the
    # core app every table tagged core in schema.py.
    extra = getattr(spec, "APP_TABLES", None)
    if extra is None:
        extra = [t["name"] for t in TABLES if t.get("solution", "core") == "core"] + getattr(spec, "APP_EXTRA_TABLES", [])
    others = [t for t in dict.fromkeys(extra) if t not in nav_tables and t not in env.missing]
    components = [("navigation", {"@odata.type": "Microsoft.Dynamics.CRM.sitemap", "sitemapid": sitemap_id})]
    components += [(TABLE_LABELS[t][1], {"@odata.type": "Microsoft.Dynamics.CRM.entity",
                                         "entityid": env.metadataid[t]}) for t in nav_tables + others]
    if any(t.get("documents") for t in TABLES if t["name"] not in env.missing):
        # The Related menu only lists tables that are in the app. SharePoint's Documents link needs these two.
        for sp in ("sharepointdocument", "sharepointdocumentlocation"):
            e = dv.call("GET", f"EntityDefinitions(LogicalName='{sp}')?$select=MetadataId", ok404=True)
            if e:
                components.append((sp, {"@odata.type": "Microsoft.Dynamics.CRM.entity", "entityid": e["MetadataId"]}))
    added = 0
    for what, comp in components:
        try:
            dv.call("POST", "AddAppComponents", {"AppId": app_id, "Components": [comp]})
            added += 1
        except DataverseError as e:
            if "already" not in str(e).lower():  # only "already in the app" is fine; anything else is a real error
                raise
    if added:
        log.created(f"App components: {added} added")
    else:
        log.skipped("App components")

    try:
        v = dv.call("GET", f"ValidateApp(AppModuleId={app_id})")
        issues = (v.get("AppValidationResponse") or {}).get("ValidationIssueList") or []
        for i in issues:
            log(f"    app check: {i.get('ErrorType', '')} {i.get('Message', i)}")
        if not issues:
            log("  App check passed")
    except DataverseError as e:
        log(f"    note: app check unavailable ({e})")
    return app_id


# --------------------------------------------------------------------------- main
def run(dv, log, only=None):
    stages = only or {"views", "forms", "app"}
    log(f"Environment: {dv.base}")
    env = Env(dv, log)
    manual_missing = [(t, c, lbl) for t, c, lbl, _ in spec.MANUAL_COLUMNS if not env.has(t, c)]
    if manual_missing:
        log(f"\n{len(manual_missing)} formula/rollup columns not created yet; their places are left empty:")
        for t, c, lbl in manual_missing:
            log(f"    {TABLE_LABELS[t][0]}: {lbl} (schema name clt_{c})")
    if "views" in stages:
        build_views(dv, env, log)
    if stages & {"forms", "app"}:
        deploy_web_resources(dv, env, log)  # forms use the scripts; navigation links to the pages
    if "forms" in stages:
        build_forms(dv, env, log)
    app_id = build_app(dv, env, log) if "app" in stages else None
    publish_all(dv, log)
    if app_id:
        try:
            dv.call("POST", "PublishXml", {"ParameterXml":
                    f"<importexportxml><appmodules><appmodule>{app_id}</appmodule></appmodules></importexportxml>"})
        except DataverseError as e:
            log(f"    note: publish the app from the app designer if it doesn't appear ({e})")
    log(f"\nDone. {log.counts['created']} items built or updated.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url")
    ap.add_argument("--check", action="store_true", help="Check the app spec. No sign-in.")
    ap.add_argument("--app", choices=sorted(APP_SPECS), default="stu",
                    help="Which app: stu (both sides in one app, the default), core (CLT Stewardship only) "
                         "or intake (CLT Applications and Sales only)")
    ap.add_argument("--only", help="Comma list of stages: views, forms, app")
    ap.add_argument("--solution", default=SOLUTION)
    ap.add_argument("--tenant", default="organizations")
    ap.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    ap.add_argument("--device-code", action="store_true")
    args = ap.parse_args()
    use_app(args.app)

    problems = check_spec()
    if problems:
        print("App spec problems:\n  " + "\n  ".join(problems))
        sys.exit(1)
    nforms = len(spec.FORMS)
    print(f"{spec.APP['name']}: {len(spec.VIEWS)} views, {nforms} forms, {sum(len(g) for _, g in spec.NAVIGATION)} navigation pages "
          f"in {len(spec.NAVIGATION)} groups")
    if args.check:
        print("App spec looks good.")
        return
    if not args.url:
        sys.exit("Add --url with your environment URL.")
    only = set(s.strip() for s in args.only.split(",")) if args.only else None
    log = Log("app-build-log.txt")
    dv = Dataverse(args.url, make_token_provider(args.url, args.client_id, args.tenant, args.device_code),
                   args.solution)
    try:
        run(dv, log, only)
    except DataverseError as e:
        log(f"\nSTOPPED: {e}")
        log("Run again after fixing, or send this message to Claude.")
        sys.exit(1)


if __name__ == "__main__":
    main()
