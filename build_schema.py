#!/usr/bin/env python3
"""
Build the CLT Stewardship schema in a Dataverse environment.

Creates, inside the CLTStewardship solution:
  global choices -> tables -> columns -> lookups -> alternate keys
then publishes, and writes choice-values.json (choice label -> number) for the flows.

Safe to re-run. Anything that already exists is skipped, and nothing is ever
changed or deleted. Deliberate exceptions: --remove-retired deletes retired
items; tables marked documents= in schema.py get SharePoint document
management switched on (never off); formula columns get their formula updated to
match schema.py; and table and column display names are updated to
match schema.py (labels only, no data). If a run stops partway, fix the problem and
run it again.

With --sharepoint-site, it also sets up SharePoint document storage: the site
record, one document library per documents= table (created in SharePoint if
missing), and the document location that points Dataverse at that library.

Usage:
  python3 build_schema.py --check
  python3 build_schema.py --url https://yourorg.crm.dynamics.com
  python3 build_schema.py --url https://yourorg.crm.dynamics.com \
      --sharepoint-site https://yourorg.sharepoint.com/sites/Stewardship
"""
import argparse
import json
import re
import sys
import time
import warnings
from datetime import datetime
from urllib.parse import urlparse, quote

# macOS's built-in Python uses LibreSSL; urllib3 warns about it on every run. It's harmless.
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

from schema import CHOICES, TABLES, LOOKUPS, KEYS, SEED_LISTS, RETIRED, ENVIRONMENT_VARIABLES, SEED_ROWS

# Dataverse's own tables a lookup may point at (no clt_ prefix).
SYSTEM_TABLES = {"systemuser"}
# Which solution a table belongs to (a table's solution= in schema.py). Dev builds everything into SOLUTION for now;
# the split into installable solutions happens at deployment (docs/DESIGN.md, Two apps).
SOLUTION_TAGS = {"core", "intake"}

PREFIX = "clt"
VERSION = "0.5"  # main.sub; also stamped on the solution as 0.5.0.0
SOLUTION = "CLTStewardship"
API = "/api/data/v9.2/"
LANG = 1033
# Microsoft's app registration for Dataverse development and samples.
DEFAULT_CLIENT_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d"


# --------------------------------------------------------------------------- helpers
def L(text):
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [{
            "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
            "Label": text, "LanguageCode": LANG}],
    }


def required_level(required):
    return {"Value": "ApplicationRequired" if required else "None", "CanBeChanged": True,
            "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"}


def ln(name):
    """Logical name with publisher prefix."""
    return f"{PREFIX}_{name}"


def label_of(option):
    lbl = option.get("Label") or {}
    if lbl.get("UserLocalizedLabel"):
        return lbl["UserLocalizedLabel"]["Label"]
    for loc in lbl.get("LocalizedLabels", []):
        if loc.get("LanguageCode") == LANG:
            return loc["Label"]
    return None


class DataverseError(Exception):
    pass


class SharePointError(Exception):
    pass


class Log:
    def __init__(self, path):
        self.f = open(path, "a", encoding="utf-8")
        self.f.write(f"\n=== Run started {datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
        self.counts = {"created": 0, "skipped": 0}

    def __call__(self, msg):
        print(msg)
        self.f.write(msg + "\n")
        self.f.flush()

    def created(self, what):
        self.counts["created"] += 1
        self("  + " + what)

    def skipped(self, what):
        self.counts["skipped"] += 1
        self("  = " + what + " (already there)")


# --------------------------------------------------------------------------- spec checks
def check_formula(t, c, tables):
    """Offline checks for a formula column: result type, and that every clt_ name it uses exists
    (a name after a dot is checked on the table the lookup points to)."""
    where = f"{t['name']}.{c['name']}"
    if c["result"] not in ("dec", "int", "text", "bool"):
        return [f"{where}: formula result must be dec, int, text or bool"]
    def names(table):
        return ({x["name"] for x in tables[table]["columns"]} | {"name"}
                | {col for child, col, *_ in LOOKUPS if child == table}) if table in tables else None
    problems = []
    targets = {col: parent for child, col, parent, *_ in LOOKUPS if child == t["name"]}
    for m in re.finditer(r"(?<![\w.'])clt_(\w+)(?:\.clt_(\w+))?", c["formula"]):
        first, second = m[1], m[2]
        if first == c["name"] or first not in names(t["name"]):
            problems.append(f"{where}: formula uses clt_{first}, which isn't a column or lookup of {t['name']}")
        elif second:
            other = names(targets.get(first, ""))
            if other is None or second not in other:
                problems.append(f"{where}: formula uses clt_{first}.clt_{second}, which isn't on the looked-up table")
    # Dataverse rules: money only inside Decimal(...), and at most 1,000 characters.
    for m in re.finditer(r"(?<![\w.'])clt_(\w+)(?:\.clt_(\w+))?", c["formula"]):
        table, col = (targets.get(m[1]), m[2]) if m[2] else (t["name"], m[1])
        kinds = {x["name"]: x["kind"] for x in tables[table]["columns"]} if table in tables else {}
        if kinds.get(col) == "money" and m[2]:
            problems.append(f"{where}: {m[0]} is money on a linked table; formulas can't calculate with that "
                            "(store it as a whole number or decimal)")
        elif kinds.get(col) == "money" and not c["formula"][:m.start()].endswith("Decimal("):
            problems.append(f"{where}: wrap money column {m[0]} in Decimal(...)")
    if "IsBlank(Decimal(" in c["formula"]:
        problems.append(f"{where}: IsBlank(Decimal(x)) is never true (a blank money value reads as 0): "
                        "use Decimal(x) = 0")
    if re.search(r"\bText\([^,()]*\)", c["formula"]):
        problems.append(f"{where}: Text() of a number needs a format, for example Text(x, \"0\")")
    if len(c["formula"]) > 1000:
        problems.append(f"{where}: formula is {len(c['formula'])} characters; Dataverse allows 1,000")
    if c["formula"].count("(") != c["formula"].count(")"):
        problems.append(f"{where}: formula brackets don't match")
    return problems


def check_spec():
    problems = []
    name_ok = re.compile(r"^[a-z][a-z0-9]*$")
    for key, (label, options) in CHOICES.items():
        if not name_ok.match(key):
            problems.append(f"choice '{key}': name must be lowercase letters and digits")
        if len(set(options)) != len(options):
            problems.append(f"choice '{key}': duplicate labels")
    tables = {t["name"]: t for t in TABLES}
    if len(tables) != len(TABLES):
        problems.append("duplicate table names")
    for t in TABLES:
        if not name_ok.match(t["name"]) or len(ln(t["name"])) > 40:
            problems.append(f"table '{t['name']}': bad or too long name")
        if "documents" in t and not (isinstance(t["documents"], str) and t["documents"].strip()
                                     and not re.search(r'[~"#%&*:<>?/\\{|}]', t["documents"])):
            problems.append(f"table '{t['name']}': documents= must be a SharePoint library title "
                            f"without ~ \" # % & * : < > ? / \\ {{ | }}")
        seen = {"name"}
        for c in t["columns"]:
            n = c["name"]
            if not name_ok.match(n) or len(ln(n)) > 40:
                problems.append(f"{t['name']}.{n}: bad or too long name")
            if n in seen:
                problems.append(f"{t['name']}.{n}: duplicate column")
            seen.add(n)
            if c["kind"] == "fx":
                problems += check_formula(t, c, tables)
            if c["kind"] in ("choice", "multi"):
                cs = c["choice"]
                if cs not in CHOICES:
                    problems.append(f"{t['name']}.{n}: unknown choice '{cs}'")
                elif c.get("default") and c["default"] not in CHOICES[cs][1]:
                    problems.append(f"{t['name']}.{n}: default '{c['default']}' not in choice '{cs}'")
    for t in TABLES:
        if t.get("solution", "core") not in SOLUTION_TAGS:
            problems.append(f"table '{t['name']}': solution must be one of {sorted(SOLUTION_TAGS)}")
    for child, col, parent, label, ondelete, req in LOOKUPS:
        if child not in tables or (parent not in tables and parent not in SYSTEM_TABLES):
            problems.append(f"lookup {child}.{col}: unknown table")
            continue
        if any(c["name"] == col for c in tables[child]["columns"]):
            problems.append(f"lookup {child}.{col}: clashes with a column of the same name")
        if ondelete not in ("Cascade", "RemoveLink", "Restrict"):
            problems.append(f"lookup {child}.{col}: bad on-delete '{ondelete}'")
    cascades = [l[0] for l in LOOKUPS if l[4] == "Cascade"]
    for child in sorted({c for c in cascades if cascades.count(c) > 1}):
        problems.append(f"table '{child}': only one lookup can be Cascade (Dataverse allows one parent)")
    lookup_names = [(c, n) for c, n, *_ in LOOKUPS]
    if len(set(lookup_names)) != len(lookup_names):
        problems.append("duplicate lookup")
    for table, keyname, cols in KEYS:
        if table not in tables:
            problems.append(f"key {table}.{keyname}: unknown table")
            continue
        names = {c["name"]: c for c in tables[table]["columns"]}
        lookups = {col for child, col, *_ in LOOKUPS if child == table}
        for c in cols:
            if c not in lookups and (c not in names or names[c]["kind"] not in ("text", "email", "int", "dec", "date")):
                problems.append(f"key {table}.{keyname}: column '{c}' missing or wrong type")
    for table, rows in SEED_ROWS.items():
        if table not in tables:
            problems.append(f"seed rows: unknown table {table}")
            continue
        cols = {c["name"]: c for c in tables[table]["columns"]} | {"name": {"kind": "text"}}
        for row in rows:
            for k, v in row.items():
                c = cols.get(k)
                if not c:
                    problems.append(f"seed rows {table}: unknown column {k}")
                elif c["kind"] in ("choice", "multi"):
                    for label in (v if isinstance(v, list) else [v]):
                        if label not in CHOICES[c["choice"]][1]:
                            problems.append(f"seed rows {table}.{k}: '{label}' not in choice {c['choice']}")
    return problems


def summary():
    ncols = sum(len(t["columns"]) for t in TABLES)
    lines = [f"{len(CHOICES)} global choices, {len(TABLES)} tables, {ncols} columns, "
             f"{len(LOOKUPS)} lookups, {len(KEYS)} alternate keys", ""]
    for t in TABLES:
        lk = [f"{c} -> {p}" for ch, c, p, *_ in LOOKUPS if ch == t["name"]]
        lines.append(f"  {t['label']:<22} {len(t['columns']):>3} columns"
                     + (f"   lookups: {', '.join(lk)}" if lk else ""))
    return "\n".join(lines)


# --------------------------------------------------------------------------- auth
_MSAL_APPS = {}


def _msal_app(client_id, tenant):
    """One sign-in per run: Dataverse and SharePoint tokens share this app and its account."""
    try:
        import msal
    except ImportError:
        sys.exit("Missing package. Run:  pip install msal requests")
    key = (client_id, tenant)
    if key not in _MSAL_APPS:
        _MSAL_APPS[key] = msal.PublicClientApplication(
            client_id, authority=f"https://login.microsoftonline.com/{tenant}")
    return _MSAL_APPS[key]


def _acquire(app, scopes, device_code, account=None):
    """account: a username (automation@...) to sign in as; cached sign-ins for anyone else are ignored."""
    accounts = app.get_accounts()
    if account:
        accounts = [a for a in accounts if (a.get("username") or "").lower() == account.lower()]
    if accounts:
        r = app.acquire_token_silent(scopes, account=accounts[0])
        if r and "access_token" in r:
            return r
    if device_code:
        flow = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            return {"error_description": "Could not start device sign-in: " + json.dumps(flow)}
        print(flow["message"])
        return app.acquire_token_by_device_flow(flow)
    if account:
        print(f"Opening your browser to sign in. Sign in as {account}.")
        return app.acquire_token_interactive(scopes=scopes, prompt="login", login_hint=account)
    print("Opening your browser to sign in. Use the account that belongs to this environment.")
    return app.acquire_token_interactive(scopes=scopes, prompt="select_account")


def make_token_provider(url, client_id, tenant, device_code, account=None):
    app = _msal_app(client_id, tenant)
    scopes = [url.rstrip("/") + "/.default"]

    def get_token():
        r = _acquire(app, scopes, device_code, account)
        if "access_token" not in r:
            sys.exit("Sign-in failed: " + r.get("error_description", json.dumps(r)))
        return r["access_token"]

    return get_token


def make_sharepoint_token_provider(site_url, client_id, tenant, device_code):
    """Like make_token_provider, but raises SharePointError instead of exiting, so the
    build can fall back to telling you to create the library by hand."""
    app = _msal_app(client_id, tenant)
    u = urlparse(site_url)
    scopes = [f"{u.scheme}://{u.netloc}/.default"]
    cache = {}

    def get_token():
        if "token" not in cache:
            r = _acquire(app, scopes, device_code)
            if "access_token" not in r:
                raise SharePointError("SharePoint sign-in failed: "
                                      + r.get("error_description", json.dumps(r)).splitlines()[0])
            cache["token"] = r["access_token"]
        return cache["token"]

    return get_token


# --------------------------------------------------------------------------- web api client
class Dataverse:
    def __init__(self, base_url, get_token, solution, session=None):
        import requests
        self.base = base_url.rstrip("/")
        self.get_token = get_token
        self.solution = solution
        self.s = session or requests.Session()

    def call(self, method, path, body=None, ok404=False, extra_headers=None, timeout=600):
        headers = {
            "Authorization": "Bearer " + self.get_token(),
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            **({"MSCRM.SolutionUniqueName": self.solution} if self.solution else {}),
            "Prefer": "odata.include-annotations=\"*\"",
            **(extra_headers or {}),
        }
        data = json.dumps(body) if body is not None else None
        for attempt in range(8):
            r = self.s.request(method, self.base + API + path, headers=headers, data=data, timeout=timeout)
            if ok404 and (r.status_code == 404 or (r.status_code == 400 and any(
                    s in r.text.lower() for s in ("could not find", "does not exist", "not found")))):
                return None
            busy = r.status_code >= 500 and ("previous" in r.text.lower() or "lock" in r.text.lower())
            if r.status_code in (429, 502, 503, 504) or busy:
                wait = int(r.headers.get("Retry-After") or 0) or min(60, 5 * 2 ** attempt)
                print(f"    (Dataverse busy, waiting {wait}s)")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                try:
                    msg = r.json().get("error", {}).get("message", r.text)
                except ValueError:
                    msg = r.text
                raise DataverseError(f"{method} {path} -> {r.status_code}: {msg}")
            if r.content:
                return r.json()
            m = re.search(r"\(([0-9a-fA-F-]{36})\)\s*$", r.headers.get("OData-EntityId", ""))
            return {"_id": m[1]} if m else {}
        raise DataverseError(f"{method} {path}: gave up after repeated busy responses")


class SharePoint:
    """Minimal SharePoint REST client for one site. Only used to create document libraries."""

    def __init__(self, site_url, get_token, session=None):
        import requests
        self.site = site_url.rstrip("/")
        self.path = urlparse(self.site).path.rstrip("/")   # e.g. /sites/Stewardship
        self.get_token = get_token
        self.s = session or requests.Session()

    def call(self, method, path, body=None, ok404=False, extra_headers=None):
        headers = {
            "Authorization": "Bearer " + self.get_token(),
            "Accept": "application/json;odata=nometadata",
            "Content-Type": "application/json;odata=verbose",
            **(extra_headers or {}),
        }
        data = json.dumps(body) if body is not None else None
        r = self.s.request(method, self.site + "/_api/" + path, headers=headers, data=data, timeout=120)
        if ok404 and r.status_code == 404:
            return None
        if r.status_code >= 400:
            try:
                msg = r.json().get("odata.error", {}).get("message", {}).get("value", r.text)
            except ValueError:
                msg = r.text
            raise SharePointError(f"{method} {path} -> {r.status_code}: {msg}")
        return r.json() if r.content else {}


# --------------------------------------------------------------------------- builders
def column_body(c, choice_ids, choice_values):
    kind = c["kind"]
    if kind == "fx":  # a formula column: the result type's definition, plus the formula
        body = column_body({**c, "kind": c["result"], "default": None}, choice_ids, choice_values)
        body.pop("DefaultValue", None)
        return {**body, "SourceType": 3, "FormulaDefinition": c["formula"]}
    base = {
        "SchemaName": ln(c["name"]),
        "DisplayName": L(c["label"]),
        "Description": L(c.get("desc", "")),
        "RequiredLevel": required_level(c.get("required", False)),
    }
    if kind == "autonumber":
        return {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                **base, "MaxLength": c["max"], "FormatName": {"Value": "Text"}, "AutoNumberFormat": c["format"]}
    if kind in ("text", "email", "phone", "url"):
        fmt = {"text": "Text", "email": "Email", "phone": "Phone", "url": "Url"}[kind]
        return {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                **base, "MaxLength": c["max"], "FormatName": {"Value": fmt}}
    if kind == "memo":
        return {"@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata",
                **base, "Format": "TextArea", "MaxLength": c["max"]}
    if kind == "int":
        return {"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
                **base, "Format": "None", "MinValue": -2147483648, "MaxValue": 2147483647}
    if kind == "dec":
        return {"@odata.type": "Microsoft.Dynamics.CRM.DecimalAttributeMetadata",
                **base, "Precision": c["precision"], "MinValue": -100000000000, "MaxValue": 100000000000}
    if kind == "money":
        return {"@odata.type": "Microsoft.Dynamics.CRM.MoneyAttributeMetadata",
                **base, "Precision": 2, "PrecisionSource": 2,
                "MinValue": -1000000000, "MaxValue": 1000000000}
    if kind == "date":
        return {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
                **base, "Format": "DateOnly", "DateTimeBehavior": {"Value": "DateOnly"}}
    if kind == "datetime":
        return {"@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
                **base, "Format": "DateAndTime", "DateTimeBehavior": {"Value": "UserLocal"}}
    if kind == "bool":
        return {"@odata.type": "Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
                **base, "DefaultValue": bool(c.get("default")),
                "OptionSet": {
                    "@odata.type": "Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                    "OptionSetType": "Boolean",
                    "TrueOption": {"Value": 1, "Label": L("Yes")},
                    "FalseOption": {"Value": 0, "Label": L("No")}}}
    if kind == "file":
        return {"@odata.type": "Microsoft.Dynamics.CRM.FileAttributeMetadata",
                **base, "MaxSizeInKB": c["max_kb"]}
    if kind in ("choice", "multi"):
        t = "PicklistAttributeMetadata" if kind == "choice" else "MultiSelectPicklistAttributeMetadata"
        body = {"@odata.type": f"Microsoft.Dynamics.CRM.{t}", **base,
                "GlobalOptionSet@odata.bind": f"/GlobalOptionSetDefinitions({choice_ids[c['choice']]})"}
        if kind == "choice" and c.get("default"):
            body["DefaultFormValue"] = choice_values[c["choice"]][c["default"]]
        return body
    raise ValueError(f"unknown column kind {kind}")


def ensure_choices(dv, log, option_prefix):
    log("\nGlobal choices")
    ids, values = {}, {}
    for key, (label, options) in CHOICES.items():
        name = ln(key)
        existing = dv.call("GET", f"GlobalOptionSetDefinitions(Name='{name}')", ok404=True)
        if existing is None:
            base = option_prefix * 10000
            dv.call("POST", "GlobalOptionSetDefinitions", {
                "@odata.type": "Microsoft.Dynamics.CRM.OptionSetMetadata",
                "Name": name, "DisplayName": L(label), "Description": L(""),
                "OptionSetType": "Picklist", "IsGlobal": True,
                "Options": [{"Value": base + i, "Label": L(o)} for i, o in enumerate(options)],
            })
            log.created(f"{label} ({len(options)} options)")
            existing = dv.call("GET", f"GlobalOptionSetDefinitions(Name='{name}')")
        else:
            have = {label_of(o): o["Value"] for o in existing.get("Options", [])}
            missing = [o for o in options if o not in have]
            if not missing:
                log.skipped(label)
            nxt = max(have.values(), default=option_prefix * 10000 - 1) + 1
            for o in missing:
                dv.call("POST", "InsertOptionValue", {
                    "OptionSetName": name, "Value": nxt, "Label": L(o),
                    "SolutionUniqueName": dv.solution})
                log.created(f"{label}: added option '{o}'")
                nxt += 1
            if missing:
                existing = dv.call("GET", f"GlobalOptionSetDefinitions(Name='{name}')")
        ids[key] = existing["MetadataId"]
        values[key] = {label_of(o): o["Value"] for o in existing.get("Options", [])}
    return ids, values


def ensure_tables(dv, log):
    log("\nTables")
    for t in TABLES:
        name = ln(t["name"])
        if dv.call("GET", f"EntityDefinitions(LogicalName='{name}')?$select=LogicalName", ok404=True):
            log.skipped(t["label"])
            continue
        pname, pdesc = t["primary"]
        dv.call("POST", "EntityDefinitions", {
            "@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata",
            "SchemaName": name,
            "DisplayName": L(t["label"]),
            "DisplayCollectionName": L(t["plural"]),
            "Description": L(t.get("desc", "")),
            "OwnershipType": "UserOwned",
            "IsActivity": False,
            "HasActivities": False,
            "HasNotes": bool(t.get("notes")),
            "Attributes": [{
                "@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata",
                "SchemaName": ln("name"),
                "IsPrimaryName": True,
                "MaxLength": 200,
                "FormatName": {"Value": "Text"},
                "DisplayName": L(pname),
                "Description": L(pdesc),
                "RequiredLevel": required_level(t.get("primary_required", True)),
            }],
        })
        log.created(f"{t['label']}")


def existing_attributes(dv, table):
    """{logical name: attribute type} for a table."""
    r = dv.call("GET", f"EntityDefinitions(LogicalName='{ln(table)}')/Attributes?$select=LogicalName,AttributeType")
    return {a["LogicalName"]: a.get("AttributeType") for a in r.get("value", [])}


ATTR_TYPE = {"autonumber": "String", "text": "String", "email": "String", "phone": "String", "url": "String", "memo": "Memo",
             "int": "Integer", "dec": "Decimal", "money": "Money", "date": "DateTime", "datetime": "DateTime", "bool": "Boolean",
             "choice": "Picklist", "multi": "MultiSelectPicklist", "file": "File"}


def attr_type(c):
    """Metadata type name for a column (a formula column's is its result type's)."""
    return ATTR_TYPE[c["result"] if c["kind"] == "fx" else c["kind"]]


def ensure_labels(dv, log):
    """Update table and column display names that differ from schema.py, and whether each table's name is required.
    Settings only; no data changes. This is how a column gets renamed (its schema name never changes)."""
    log("\nTable and column labels")
    changed = 0
    for t in TABLES:
        # Table names (singular and plural), the same way: full definition back, labels merged.
        tpath = f"EntityDefinitions(LogicalName='{ln(t['name'])}')"
        names = dv.call("GET", f"{tpath}?$select=DisplayName,DisplayCollectionName")
        lab = lambda k: ((names.get(k) or {}).get("UserLocalizedLabel") or {}).get("Label")  # noqa: E731
        if (lab("DisplayName"), lab("DisplayCollectionName")) != (t["label"], t["plural"]):
            full = dv.call("GET", tpath)
            body = {k: v for k, v in full.items() if "@" not in k}
            body["@odata.type"] = "Microsoft.Dynamics.CRM.EntityMetadata"
            body["DisplayName"], body["DisplayCollectionName"] = L(t["label"]), L(t["plural"])
            dv.call("PUT", tpath, body, extra_headers={"MSCRM.MergeLabels": "true"})
            log.created(f"table '{lab('DisplayName')}' renamed to '{t['label']}' ('{t['plural']}')")
            changed += 1
        r = dv.call("GET", f"EntityDefinitions(LogicalName='{ln(t['name'])}')/Attributes"
                           f"?$select=LogicalName,DisplayName,RequiredLevel")
        prim = next((a for a in r.get("value", []) if a["LogicalName"] == ln("name")), None)
        # Only ever loosen: make the name optional where schema.py says so. Never tighten an existing table
        # (Dataverse can leave primary names optional regardless of what was asked at creation).
        want = "None"
        current = (prim.get("RequiredLevel") or {}).get("Value") if prim else None
        if prim and t.get("primary_required", True) is False and current not in (None, "None"):
            path = f"EntityDefinitions(LogicalName='{ln(t['name'])}')/Attributes(LogicalName='{ln('name')}')"
            typ = "Microsoft.Dynamics.CRM.StringAttributeMetadata"
            full = dv.call("GET", f"{path}/{typ}")
            body = {k: v for k, v in full.items() if "@" not in k}
            body["@odata.type"] = typ
            body["RequiredLevel"] = required_level(False)
            dv.call("PUT", path, body, extra_headers={"MSCRM.MergeLabels": "true"})
            log.created(f"{t['label']}: name is now optional")
            changed += 1
        current = {}
        for a in r.get("value", []):
            dn = (a.get("DisplayName") or {}).get("UserLocalizedLabel") or {}
            current[a["LogicalName"]] = dn.get("Label")
        for c in t["columns"]:
            name = ln(c["name"])
            if name not in current or current[name] == c["label"]:
                continue
            path = f"EntityDefinitions(LogicalName='{ln(t['name'])}')/Attributes(LogicalName='{name}')"
            typ = f"Microsoft.Dynamics.CRM.{attr_type(c)}AttributeMetadata"
            full = dv.call("GET", f"{path}/{typ}")
            body = {k: v for k, v in full.items() if "@" not in k}
            body["@odata.type"] = typ
            body["DisplayName"] = L(c["label"])
            dv.call("PUT", path, body, extra_headers={"MSCRM.MergeLabels": "true"})
            log.created(f"{t['label']}: '{current[name]}' renamed to '{c['label']}'")
            changed += 1
    if not changed:
        log("  = all table and column labels and name settings match schema.py")


def ensure_columns(dv, log, choice_ids, choice_values):
    log("\nColumns")
    for t in TABLES:
        have = existing_attributes(dv, t["name"])
        todo = [c for c in t["columns"] if ln(c["name"]) not in have and c["kind"] != "fx"]  # formulas: ensure_formulas
        n = len([c for c in t["columns"] if c["kind"] != "fx"])
        log(f" {t['label']}: {n - len(todo)} already there, {len(todo)} to add")
        log.counts["skipped"] += n - len(todo)
        for c in todo:
            dv.call("POST", f"EntityDefinitions(LogicalName='{ln(t['name'])}')/Attributes",
                    column_body(c, choice_ids, choice_values))
            log.created(f"{t['label']}.{c['label']}")
            if c["kind"] == "autonumber":
                start_numbering(dv, log, t, c)


def stored_formula(formula, choice_values):
    """A formula as Dataverse saves it: [@'Pay frequency'].'Weekly' becomes [@global_clt_payfrequency].'768270000'.
    Used to tell a real change from a different spelling of the same formula."""
    by_label = {label: key for key, (label, _) in CHOICES.items()}
    def swap(m):
        key = by_label.get(m[1])
        value = (choice_values.get(key) or {}).get(m[2]) if key else None
        return f"[@global_{ln(key)}].'{value}'" if value is not None else m[0]
    return re.sub(r"\[@'([^']+)'\]\.'([^']+)'", swap, " ".join(formula.split()))


def ensure_formulas(dv, log, choice_values=None):
    """Formula columns, after the lookups they may read through. A missing one is created; one whose formula
    changed in schema.py is updated (settings only: Dataverse works the values out when they're read).
    A formula Dataverse won't accept is reported and skipped, so the rest of the build still runs."""
    cols = [(t, c) for t in TABLES for c in t["columns"] if c["kind"] == "fx"]
    if not cols:
        return
    log("\nFormula columns")
    # A formula can read another formula column (on its own table or through a lookup), so one may name a
    # column that isn't there yet. Keep going round while each pass creates something; then report the rest.
    pending, errors = cols, {}
    while pending:
        retry = []
        for t, c in pending:
            try:
                ensure_formula(dv, log, t, c, choice_values)
            except DataverseError as e:
                errors[(t["name"], c["name"])] = (t, c, e)
                if "isn't recognized" in str(e):
                    retry.append((t, c))
                continue
            errors.pop((t["name"], c["name"]), None)
        if len(retry) == len(pending):
            break
        pending = retry
    for t, c, e in errors.values():
        log(f"  ! {t['label']}.{c['label']}: Dataverse didn't accept the formula ({e}). Fix it in schema.py.")
    if errors:
        log(f"  {len(errors)} formula column(s) not created: {', '.join(f'{a}.{b}' for a, b in errors)}")


def ensure_formula(dv, log, t, c, choice_values):
    path = f"EntityDefinitions(LogicalName='{ln(t['name'])}')/Attributes(LogicalName='{ln(c['name'])}')"
    typ = f"Microsoft.Dynamics.CRM.{attr_type(c)}AttributeMetadata"
    have = dv.call("GET", f"{path}/{typ}", ok404=True)
    if not have:
        dv.call("POST", f"EntityDefinitions(LogicalName='{ln(t['name'])}')/Attributes", column_body(c, {}, {}))
        log.created(f"{t['label']}.{c['label']}")
    elif " ".join((have.get("FormulaDefinition") or "").split()) not in (
            c["formula"], stored_formula(c["formula"], choice_values or {})):
        body = {k: v for k, v in have.items() if "@" not in k}
        body["@odata.type"] = typ
        body["FormulaDefinition"] = c["formula"]
        dv.call("PUT", path, body, extra_headers={"MSCRM.MergeLabels": "true"})
        log.created(f"{t['label']}.{c['label']}: formula updated")
    else:
        log.skipped(f"{t['label']}.{c['label']}")


def start_numbering(dv, log, t, c):
    """A new autonumber column: number existing rows oldest first (P-00001...), then start the sequence after them.
    Runs once, when the column is created. Dataverse only numbers rows created after the column exists."""
    es = dv.call("GET", f"EntityDefinitions(LogicalName='{ln(t['name'])}')?$select=EntitySetName")["EntitySetName"]
    rows, nxt = [], f"{es}?$select={ln(t['name'])}id&$orderby=createdon asc"
    while nxt:
        r = dv.call("GET", nxt)
        rows.extend(r.get("value", []))
        link = r.get("@odata.nextLink")
        nxt = link.split(API, 1)[1] if link else None
    width = int(re.search(r"\{SEQNUM:(\d+)\}", c["format"]).group(1))
    for i, row in enumerate(rows, 1):
        number = re.sub(r"\{SEQNUM:\d+\}", str(i).zfill(width), c["format"])
        dv.call("PATCH", f"{es}({row[ln(t['name']) + 'id']})", {ln(c["name"]): number})
    dv.call("POST", "SetAutoNumberSeed", {"EntityName": ln(t["name"]), "AttributeName": ln(c["name"]),
                                          "Value": len(rows) + 1})
    if rows:
        log(f"    numbered {len(rows)} existing {t['plural'].lower()}; new ones start at {len(rows) + 1}")


def ensure_lookups(dv, log):
    log("\nLookups")
    cache = {}
    for child, col, parent, label, ondelete, req in LOOKUPS:
        if child not in cache:
            cache[child] = existing_attributes(dv, child)
        what = f"{child}.{col} -> {parent} ({ondelete})"
        if ln(col) in cache[child]:
            if cache[child][ln(col)] not in (None, "Lookup"):
                raise DataverseError(f"{child}.{col} exists but is not a lookup. Run with --remove-retired first "
                                     "(see README: upgrading).")
            log.skipped(what)
            continue
        dv.call("POST", "RelationshipDefinitions", {
            "@odata.type": "Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
            "SchemaName": f"{PREFIX}_{parent}_{child}_{col}",
            "ReferencedEntity": parent if parent in SYSTEM_TABLES else ln(parent),
            "ReferencedAttribute": (parent if parent in SYSTEM_TABLES else ln(parent)) + "id",
            "ReferencingEntity": ln(child),
            "CascadeConfiguration": {
                "Assign": "NoCascade", "Delete": ondelete, "Merge": "NoCascade",
                "Reparent": "NoCascade", "Share": "NoCascade", "Unshare": "NoCascade",
                "RollupView": "NoCascade"},
            "AssociatedMenuConfiguration": {
                "Behavior": "UseCollectionName", "Group": "Details", "Label": L(""), "Order": 10000},
            "Lookup": {
                "@odata.type": "Microsoft.Dynamics.CRM.LookupAttributeMetadata",
                "SchemaName": ln(col),
                "DisplayName": L(label),
                "Description": L(""),
                "RequiredLevel": required_level(req)},
        })
        cache[child][ln(col)] = "Lookup"
        log.created(what)


def ensure_keys(dv, log):
    log("\nAlternate keys")
    for table, keyname, cols in KEYS:
        schema = f"{PREFIX}_{table}_{keyname}"
        r = dv.call("GET", f"EntityDefinitions(LogicalName='{ln(table)}')/Keys?$select=LogicalName")
        if any(k["LogicalName"] == schema for k in r.get("value", [])):
            log.skipped(schema)
            continue
        dv.call("POST", f"EntityDefinitions(LogicalName='{ln(table)}')/Keys", {
            "SchemaName": schema,
            "DisplayName": L(keyname),
            "KeyAttributes": [ln(c) for c in cols],
        })
        log.created(schema)


def find_retired(dv):
    """What from RETIRED still exists."""
    found = {"keys": [], "columns": [], "lookups": [], "tables": [], "choices": []}
    attrs = {}
    for table, key in RETIRED["keys"]:
        r = dv.call("GET", f"EntityDefinitions(LogicalName='{ln(table)}')/Keys?$select=LogicalName", ok404=True)
        if r and any(k["LogicalName"] == f"{PREFIX}_{table}_{key}" for k in r.get("value", [])):
            found["keys"].append((table, key))
    for table, col in RETIRED["columns"]:
        if table not in attrs:
            exists = dv.call("GET", f"EntityDefinitions(LogicalName='{ln(table)}')?$select=LogicalName", ok404=True)
            attrs[table] = existing_attributes(dv, table) if exists else {}
        if ln(col) in attrs[table] and attrs[table][ln(col)] != "Lookup":
            found["columns"].append((table, col))
    for child, col, parent in RETIRED.get("lookups", []):
        if child not in attrs:
            exists = dv.call("GET", f"EntityDefinitions(LogicalName='{ln(child)}')?$select=LogicalName", ok404=True)
            attrs[child] = existing_attributes(dv, child) if exists else {}
        if attrs[child].get(ln(col)) == "Lookup":
            found["lookups"].append((child, col, parent))
    for table in RETIRED.get("tables", []):
        if dv.call("GET", f"EntityDefinitions(LogicalName='{ln(table)}')?$select=LogicalName", ok404=True):
            found["tables"].append(table)
    for key in RETIRED["choices"]:
        if dv.call("GET", f"GlobalOptionSetDefinitions(Name='{ln(key)}')", ok404=True):
            found["choices"].append(key)
    return found


def strip_subgrids(dv, log, table):
    """Remove related-record lists (subgrids) from a table's main forms, then publish the table."""
    import xml.etree.ElementTree as ET
    r = dv.call("GET", f"systemforms?$select=formid,formxml&$filter=objecttypecode eq '{ln(table)}' and type eq 2")
    changed = False
    for f in r.get("value", []):
        root = ET.fromstring(f["formxml"])
        removed = 0
        for parent in root.iter():
            for cell in list(parent):
                if cell.tag == "cell" and any(c.get("indicationOfSubgrid") == "true" for c in cell.iter("control")):
                    parent.remove(cell)
                    removed += 1
        if removed:
            dv.call("PATCH", f"systemforms({f['formid']})", {"formxml": ET.tostring(root, encoding="unicode")})
            changed = True
    if changed:
        dv.call("POST", "PublishXml", {"ParameterXml": f"<importexportxml><entities><entity>{ln(table)}</entity>"
                                                         f"</entities></importexportxml>"})
        log(f"  - removed related lists from the {table} form so its links can be deleted")


def remove_retired(dv, log, found):
    log("\nRemoving retired items")
    for table, key in found["keys"]:
        dv.call("DELETE", f"EntityDefinitions(LogicalName='{ln(table)}')/Keys(LogicalName='{PREFIX}_{table}_{key}')")
        log.created(f"removed key {table}.{key}")
    for table, col in found["columns"]:
        try:
            dv.call("DELETE", f"EntityDefinitions(LogicalName='{ln(table)}')/Attributes(LogicalName='{ln(col)}')")
            log.created(f"removed column {table}.{col}")
        except DataverseError as e:
            raise DataverseError(f"Could not remove {table}.{col}. Something still uses it, usually a form, "
                                 f"view or formula column. Run build_app.py first, then try again. ({e})")
    # A retired table's own forms can hold related-record lists that use the lookups we're about to remove
    # (and those lookups block deleting the table). Strip the lists first, then lookups, then tables.
    for table in found["tables"]:
        strip_subgrids(dv, log, table)
    for child, col, parent in found["lookups"]:
        schema = f"{PREFIX}_{parent}_{child}_{col}"
        if not dv.call("GET", f"RelationshipDefinitions(SchemaName='{schema}')?$select=SchemaName", ok404=True):
            log(f"  - lookup {child}.{col} already removed")
            continue
        try:
            dv.call("DELETE", f"RelationshipDefinitions(SchemaName='{schema}')")
            log.created(f"removed lookup {child}.{col}")
        except DataverseError as e:
            raise DataverseError(f"Could not remove lookup {child}.{col}. Something still uses it, usually a form "
                                 f"or view. Run build_app.py first, then try again. ({e})")
    for table in found["tables"]:
        try:
            dv.call("DELETE", f"EntityDefinitions(LogicalName='{ln(table)}')")
            log.created(f"removed table {table}")
        except DataverseError as e:
            raise DataverseError(f"Could not remove table {table}. Something still uses it, usually the app's "
                                 f"navigation or a form on another table. Run build_app.py first, then try again. ({e})")
    for key in found["choices"]:
        os_ = dv.call("GET", f"GlobalOptionSetDefinitions(Name='{ln(key)}')")
        dv.call("DELETE", f"GlobalOptionSetDefinitions({os_['MetadataId']})")
        log.created(f"removed choice {key}")


def ensure_document_management(dv, log):
    """Switch on SharePoint document management for tables marked documents= in schema.py.
    This is table metadata, so it travels with the solution. It is only ever switched on."""
    tables = [t for t in TABLES if t.get("documents")]
    if not tables:
        return
    log("\nDocument management (SharePoint)")
    for t in tables:
        name = ln(t["name"])
        cur = dv.call("GET", f"EntityDefinitions(LogicalName='{name}')?$select=IsDocumentManagementEnabled")
        if cur.get("IsDocumentManagementEnabled"):
            log.skipped(f"{t['label']}: document management on")
            continue
        # Table metadata can only be updated with a full PUT, so read it all, flip the switch, write it back.
        full = dv.call("GET", f"EntityDefinitions(LogicalName='{name}')")
        body = {k: v for k, v in full.items() if "@" not in k or k == "@odata.type"}
        body.setdefault("@odata.type", "Microsoft.Dynamics.CRM.EntityMetadata")
        body["IsDocumentManagementEnabled"] = True
        dv.call("PUT", f"EntityDefinitions(LogicalName='{name}')", body,
                extra_headers={"MSCRM.MergeLabels": "true"})
        log.created(f"{t['label']}: document management switched on")


def ensure_auditing(dv, log):
    """Audit history (who changed what, old and new value) for tables marked audit=True in schema.py.
    The table switch is metadata and travels with the solution; auditing must also be on for the whole
    environment, which is a setting of each environment, so the build switches that on too. Only ever on."""
    tables = [t for t in TABLES if t.get("audit")]
    if not tables:
        return
    log("\nAuditing")
    org = dv.call("GET", "organizations?$select=organizationid,isauditenabled")["value"][0]
    if org.get("isauditenabled"):
        log.skipped("environment auditing on")
    else:
        dv.call("PATCH", f"organizations({org['organizationid']})", {"isauditenabled": True})
        log.created("environment auditing switched on")
    for t in tables:
        name = ln(t["name"])
        cur = dv.call("GET", f"EntityDefinitions(LogicalName='{name}')?$select=IsAuditEnabled")
        if (cur.get("IsAuditEnabled") or {}).get("Value"):
            log.skipped(f"{t['label']}: auditing on")
            continue
        full = dv.call("GET", f"EntityDefinitions(LogicalName='{name}')")
        body = {k: v for k, v in full.items() if "@" not in k or k == "@odata.type"}
        body.setdefault("@odata.type", "Microsoft.Dynamics.CRM.EntityMetadata")
        body["IsAuditEnabled"] = {**(full.get("IsAuditEnabled") or {}), "Value": True}
        dv.call("PUT", f"EntityDefinitions(LogicalName='{name}')", body, extra_headers={"MSCRM.MergeLabels": "true"})
        log.created(f"{t['label']}: auditing switched on (Related > Audit history on each record)")


def odata_str(v):
    return v.replace("'", "''")


def ensure_sharepoint(dv, log, site_url, sp, folder=None):
    """Point Dataverse at a SharePoint site, with one library per documents= table.

    Dataverse looks for a table's records under a library whose URL name is the
    table's logical name (for example clt_property), so each library is created with
    that URL and then given the friendly title from schema.py ("Property Documents").
    The site record and document locations are data, so each environment gets its own.

    folder: a parent folder inside every library (for example DEV), for an environment that shares the
    site with another one. It's a document location under the library that isn't tied to a record; the
    folder flows put new record folders inside it, and create the SharePoint folder the first time."""
    tables = [t for t in TABLES if t.get("documents")]
    site_url = site_url.rstrip("/")
    log(f"\nSharePoint document storage: {site_url}")

    # 1. Site record, marked as the default site.
    r = dv.call("GET", "sharepointsites?$select=sharepointsiteid,name,absoluteurl,isdefault")
    sites = r.get("value", [])
    site = next((x for x in sites if (x.get("absoluteurl") or "").rstrip("/").lower() == site_url.lower()), None)
    if site:
        site_id = site["sharepointsiteid"]
        log.skipped(f"site record {site_url}")
        if not site.get("isdefault"):
            log("  ! This site record isn't the default site. Set it as default under Advanced Settings, "
                "Document Management, SharePoint Sites, or document folders will go to the other site.")
    else:
        others = [x for x in sites if x.get("isdefault")]
        if others:
            raise DataverseError(f"This environment already has a different default SharePoint site "
                                 f"({others[0].get('absoluteurl')}). Change it by hand, or run without "
                                 f"--sharepoint-site.")
        res = dv.call("POST", "sharepointsites", {
            "name": urlparse(site_url).path.rstrip("/").split("/")[-1] or "SharePoint",
            "absoluteurl": site_url, "isdefault": True,
        })
        site_id = res.get("_id") or res.get("sharepointsiteid")
        log.created(f"site record {site_url} (default site)")

    manual = []
    for t in tables:
        lib_url, title = ln(t["name"]), t["documents"]

        # 2. The library in SharePoint.
        try:
            lib = sp.call("GET", f"web/GetList('{quote(sp.path + '/' + lib_url)}')?$select=Id,Title", ok404=True)
            if lib:
                log.skipped(f"library {title} ({sp.path}/{lib_url})")
            else:
                new = sp.call("POST", "web/lists", {
                    "__metadata": {"type": "SP.List"}, "BaseTemplate": 101, "Title": lib_url,
                    "Description": f"{t['label']} folders, created by Dataverse. One folder per record.",
                })
                sp.call("POST", f"web/lists(guid'{new['Id']}')", {"__metadata": {"type": "SP.List"}, "Title": title},
                        extra_headers={"X-HTTP-Method": "MERGE", "IF-MATCH": "*"})
                log.created(f"library {title} ({sp.path}/{lib_url})")
        except SharePointError as e:
            manual.append((t, e))
            log(f"  ! Could not check or create library {title} in SharePoint: {e}")

        # 3. Document location: tells Dataverse which library holds this table's folders.
        q = (f"sharepointdocumentlocations?$select=sharepointdocumentlocationid&$filter=relativeurl eq "
             f"'{odata_str(lib_url)}' and _parentsiteorlocation_value eq {site_id}")
        found = dv.call("GET", q).get("value")
        if found:
            loc_id = found[0]["sharepointdocumentlocationid"]
            log.skipped(f"document location {title}")
        else:
            res = dv.call("POST", "sharepointdocumentlocations", {
                "name": title, "relativeurl": lib_url,
                "parentsiteorlocation_sharepointsite@odata.bind": f"/sharepointsites({site_id})",
            })
            loc_id = res.get("_id") or res.get("sharepointdocumentlocationid")
            log.created(f"document location {title} -> {site_url}/{lib_url}")

        # 4. Optional parent folder inside the library (see the docstring).
        r = dv.call("GET", "sharepointdocumentlocations?$select=sharepointdocumentlocationid,relativeurl&$filter="
                           f"_parentsiteorlocation_value eq {loc_id} and _regardingobjectid_value eq null "
                           "and statecode eq 0").get("value", [])
        if folder and any(x.get("relativeurl") == folder for x in r):
            log.skipped(f"parent folder {folder} in {title}")
        elif folder and r:
            raise DataverseError(f"{title} already has a different parent folder ({r[0].get('relativeurl')}). "
                                 "Deactivate that document location by hand first, or use the same name.")
        elif folder:
            dv.call("POST", "sharepointdocumentlocations", {
                "name": f"{title}: {folder}", "relativeurl": folder,
                "parentsiteorlocation_sharepointdocumentlocation@odata.bind": f"/sharepointdocumentlocations({loc_id})",
            })
            log.created(f"parent folder {folder} in {title}: new record folders go in {site_url}/{lib_url}/{folder}")
        elif r:
            log(f"  ! {title} has a parent folder ({r[0].get('relativeurl')}): new record folders go inside it. "
                "Pass --sharepoint-folder to keep it, or deactivate that document location to stop.")

    for t, _ in manual:
        log(f"\n  To finish by hand: in SharePoint, open {site_url}, click New, Document library, and name it "
            f"exactly '{ln(t['name'])}' (that sets its web address). Then open the library, click the gear "
            f"icon, Library settings, List name, description and navigation, and rename it to "
            f"'{t['documents']}'. Re-run this script afterwards to confirm.")


def publish_all(dv, log):
    """Publish all customizations. Dataverse keeps publishing even if we stop waiting, so a timeout
    is reported, not treated as a failure."""
    import requests
    log("\nPublishing customizations (can take a few minutes)")
    try:
        dv.call("POST", "PublishAllXml", {}, timeout=1800)
    except requests.exceptions.Timeout:
        log("  ! Still publishing after 30 minutes. Dataverse carries on by itself; check again shortly. If the "
            "changes don't show, use Publish all customizations in the maker portal.")


def ensure_environment_variables(dv, log):
    """Create the per-client setting definitions (in the solution, blank defaults). Values are per environment."""
    if not ENVIRONMENT_VARIABLES:
        return
    log("\nEnvironment variables")
    for v in ENVIRONMENT_VARIABLES:
        schema = f"{PREFIX}_{v['name']}"
        r = dv.call("GET", f"environmentvariabledefinitions?$select=environmentvariabledefinitionid"
                           f"&$filter=schemaname eq '{schema}'")
        if r.get("value"):
            log.skipped(v["label"])
            continue
        dv.call("POST", "environmentvariabledefinitions", {
            "schemaname": schema, "displayname": v["label"], "description": v.get("desc", ""),
            "type": 100000000, "defaultvalue": v.get("default", "")})  # 100000000 = Text
        log.created(v["label"])


def seed_lists(dv, log, choice_values):
    """Load starting values into any editable list that has no values yet."""
    log("\nEditable lists")
    e = dv.call("GET", f"EntityDefinitions(LogicalName='{ln('listitem')}')?$select=EntitySetName")
    es = e["EntitySetName"]
    for list_name, items in SEED_LISTS.items():
        val = choice_values["listname"][list_name]
        r = dv.call("GET", f"{es}?$select={ln('name')}&$filter={ln('list')} eq {val}&$top=1")
        if r.get("value"):
            log.skipped(f"{list_name} list (has values; staff own it now)")
            continue
        for i, (name, answers) in enumerate(items):
            dv.call("POST", es, {ln("name"): name, ln("list"): val, ln("sortorder"): (i + 1) * 10,
                                 ln("formanswers"): "\n".join(answers)})
        log.created(f"{list_name} list: {len(items)} values")


# --------------------------------------------------------------------------- main
def seed_rows(dv, log, choice_values):
    """Starter rows (SEED_ROWS in schema.py), only for tables that are still empty. Never changes existing rows."""
    if not SEED_ROWS:
        return
    log("\nStarter rows")
    tables = {t["name"]: t for t in TABLES}
    for table, rows in SEED_ROWS.items():
        cols = {c["name"]: c for c in tables[table]["columns"]}
        es = dv.call("GET", f"EntityDefinitions(LogicalName='{ln(table)}')?$select=EntitySetName")["EntitySetName"]
        if dv.call("GET", f"{es}?$select={ln(table)}id&$top=1").get("value"):
            log.skipped(f"{tables[table]['label']} (has rows)")
            continue
        for row in rows:
            body = {}
            for k, v in row.items():
                c = cols.get(k, {"kind": "text"})
                if c["kind"] == "choice":
                    v = choice_values[c["choice"]][v]
                elif c["kind"] == "multi":
                    v = ",".join(str(choice_values[c["choice"]][x]) for x in v)
                body[ln(k)] = v
            dv.call("POST", es, body)
            log.created(f"{tables[table]['label']}: {row.get('name', '')}")


def run(dv, log, out_path="choice-values.json", remove=False, sharepoint_site=None, sp=None, sharepoint_folder=None):
    log(f"Build scripts v{VERSION}. Environment: {dv.base}")
    sol = dv.call("GET", "solutions?$filter=uniquename eq '" + dv.solution + "'"
                  "&$select=solutionid,friendlyname,version"
                  "&$expand=publisherid($select=uniquename,customizationprefix,customizationoptionvalueprefix)")
    if not sol.get("value"):
        raise DataverseError(f"Solution '{dv.solution}' not found. Create it first (step 4).")
    pub = sol["value"][0]["publisherid"]
    if pub["customizationprefix"] != PREFIX:
        raise DataverseError(f"Publisher prefix is '{pub['customizationprefix']}', expected '{PREFIX}'.")
    option_prefix = int(pub["customizationoptionvalueprefix"])
    log(f"Solution: {sol['value'][0]['friendlyname']} {sol['value'][0]['version']}, "
        f"publisher {pub['uniquename']}, choice value prefix {option_prefix}")

    found = find_retired(dv)
    if any(found.values()):
        if not remove:
            items = ([f"{t}.{c}" for t, c in found["columns"]] + [f"{t}.{c}" for t, c, _ in found["lookups"]]
                     + [f"table {t}" for t in found["tables"]] + found["choices"])
            raise DataverseError("This environment still has retired items ("
                                 + ", ".join(items) + "). See README: upgrading. Run build_app.py, then this "
                                 "script with --remove-retired.")
        remove_retired(dv, log, found)

    choice_ids, choice_values = ensure_choices(dv, log, option_prefix)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({ln(k): v for k, v in choice_values.items()}, f, indent=2)
    ensure_tables(dv, log)
    ensure_columns(dv, log, choice_ids, choice_values)
    ensure_labels(dv, log)
    ensure_lookups(dv, log)
    ensure_formulas(dv, log, choice_values)
    ensure_keys(dv, log)
    ensure_document_management(dv, log)
    ensure_auditing(dv, log)
    ensure_environment_variables(dv, log)
    seed_lists(dv, log, choice_values)
    seed_rows(dv, log, choice_values)
    if sharepoint_site:
        ensure_sharepoint(dv, log, sharepoint_site, sp, sharepoint_folder)
    elif any(t.get("documents") for t in TABLES):
        log("\nSharePoint document storage: skipped (add --sharepoint-site to set it up)")
    target = VERSION + ".0.0"
    current = sol["value"][0]["version"]
    if tuple(int(x) for x in current.split(".")) < tuple(int(x) for x in target.split(".")):
        dv.call("PATCH", f"solutions({sol['value'][0]['solutionid']})", {"version": target})
        log(f"\nSolution version set to {target} (was {current})")
    publish_all(dv, log)
    log(f"\nDone. {log.counts['created']} created, {log.counts['skipped']} already there.")
    log(f"Choice values written to {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="Environment URL, e.g. https://yourorg.crm.dynamics.com")
    ap.add_argument("--check", action="store_true", help="Check the spec and print a summary. No sign-in.")
    ap.add_argument("--solution", default=SOLUTION)
    ap.add_argument("--tenant", default="organizations", help="Tenant ID or domain, if sign-in needs it")
    ap.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    ap.add_argument("--device-code", action="store_true", help="Sign in with a code instead of a browser pop-up")
    ap.add_argument("--remove-retired", action="store_true",
                    help="Delete retired columns, lookups, tables and choices (any data in them is lost)")
    ap.add_argument("--sharepoint-site",
                    help="SharePoint site for document folders, e.g. https://contoso.sharepoint.com/sites/Stewardship")
    ap.add_argument("--sharepoint-folder",
                    help="With --sharepoint-site: a parent folder inside every library that new record folders go into, "
                         "for example DEV. For an environment that shares the site with another one.")
    args = ap.parse_args()
    if args.sharepoint_folder and not args.sharepoint_site:
        sys.exit("--sharepoint-folder needs --sharepoint-site.")
    if args.sharepoint_folder and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.sharepoint_folder):
        sys.exit("--sharepoint-folder should be letters, digits, hyphens or underscores, for example DEV.")
    if args.sharepoint_site and not re.fullmatch(r"https://[\w.-]+\.sharepoint\.com/(sites|teams)/[^/?#]+/?",
                                                 args.sharepoint_site):
        sys.exit("--sharepoint-site should look like https://<tenant>.sharepoint.com/sites/<SiteName>")

    problems = check_spec()
    if problems:
        print("Spec problems:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print(summary())
    if args.check:
        print("\nSpec looks good.")
        return
    if not args.url:
        sys.exit("\nAdd --url with your environment URL.")

    log = Log("build-log.txt")
    dv = Dataverse(args.url, make_token_provider(args.url, args.client_id, args.tenant, args.device_code),
                   args.solution)
    try:
        sp = None
        if args.sharepoint_site:
            sp = SharePoint(args.sharepoint_site, make_sharepoint_token_provider(
                args.sharepoint_site, args.client_id, args.tenant, args.device_code))
        run(dv, log, remove=args.remove_retired, sharepoint_site=args.sharepoint_site, sp=sp,
            sharepoint_folder=args.sharepoint_folder)
    except DataverseError as e:
        log(f"\nSTOPPED: {e}")
        log("Nothing already created is affected. Fix the issue (or send this message to Claude) and run again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
