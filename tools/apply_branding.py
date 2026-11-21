#!/usr/bin/env python3
"""
Set a client's settings (environment variables) and brand the app header from them.

1. Writes the values in clients/<client>/client.json "settings" into the environment's variables
   (definitions come from build_schema.py; values belong to the environment, not the solution).
2. Reads the variables back and builds a modern theme (clt_brandtheme) from them: header colors,
   a base palette (buttons, links, selected tabs) from the accent color, and the logo in the header
   (downloaded from BrandLogoUrl into the web resource clt_brandlogo).
3. Points each app's (Stu, and CLT Stewardship or CLT Applications and Sales where built) "Custom theme definition" setting at it,
   and publishes. An app that isn't built yet is skipped; re-run after building it.

Nothing here is added to the solution, so one client's branding never ships to another.
Safe to re-run; change a value in the client file (or in the environment) and run it again.

Usage:
  python3 tools/apply_branding.py --url https://yourorg.crm.dynamics.com --client clients/example/client.json --dry-run
  python3 tools/apply_branding.py --url https://yourorg.crm.dynamics.com --client clients/example/client.json
"""
import argparse
import base64
import json
import os
import re
import sys
from xml.sax.saxutils import escape

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from build_schema import Dataverse, DataverseError, make_token_provider, DEFAULT_CLIENT_ID, PREFIX  # noqa: E402
from schema import ENVIRONMENT_VARIABLES  # noqa: E402
import app_spec  # noqa: E402
import app_spec_intake  # noqa: E402
import app_spec_stu  # noqa: E402

# Plain names, no folder path, as in Microsoft's examples. If a theme change ever seems stuck in a
# browser cache, bump the suffix (clt_brandtheme2) and re-run.
THEME = "clt_brandtheme"
LOGO = "clt_brandlogo"
# Stu, and the two single-side apps where built. CLT Stewardship stays first: it owns the setting name with no suffix.
APPS = [app_spec.APP, app_spec_intake.APP, app_spec_stu.APP]
LOGO_TYPES = {"image/png": 5, "image/jpeg": 6, "image/gif": 7, "image/svg+xml": 11}  # web resource types
HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def shade(hex_color, factor):
    """Darken (factor < 1) a #RRGGBB color."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{max(0, min(255, round(c * factor))):02X}" for c in (r, g, b))


def theme_xml(header, text, accent, logo=None, tooltip=""):
    """Modern theme XML. Attribute names are lower camelCase, exactly as in Microsoft's docs
    (XML is case sensitive; Background="..." is silently ignored)."""
    accent = accent or shade(header, 1.25)
    logo_attrs = f' logoWebResource="{logo}" logoTooltip="{escape(tooltip, {chr(34): "&quot;"})}"' if logo else ""
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            f'<CustomTheme basePaletteColor="{accent}"{logo_attrs}>\n'
            f'  <AppHeaderColors background="{header}" foreground="{text}" backgroundHover="{accent}" '
            f'foregroundHover="{text}" backgroundPressed="{shade(header, 0.8)}" foregroundPressed="{text}" '
            f'backgroundSelected="{accent}" foregroundSelected="{text}" />\n</CustomTheme>\n')


def download(url):
    """(bytes, content type) for a logo URL."""
    # Ask for formats Dataverse can store; some CDNs (Squarespace) otherwise send WebP.
    r = requests.get(url, timeout=60, headers={"Accept": "image/png,image/svg+xml,image/jpeg,image/gif;q=0.9"})
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "").split(";")[0].strip().lower()


def check_settings(settings):
    known = {v["name"] for v in ENVIRONMENT_VARIABLES}
    problems = [f"unknown setting {k}" for k in settings if k not in known]
    for k in ("BrandHeaderColor", "BrandHeaderTextColor", "BrandAccentColor"):
        if settings.get(k) and not HEX.fullmatch(settings[k]):
            problems.append(f"{k} should look like #344734, not {settings[k]!r}")
    return problems


def set_variables(dv, log, settings, dry_run):
    for name, value in settings.items():
        schema = f"{PREFIX}_{name}"
        d = dv.call("GET", f"environmentvariabledefinitions?$select=environmentvariabledefinitionid"
                           f"&$filter=schemaname eq '{schema}'").get("value")
        if not d:
            raise DataverseError(f"No environment variable {schema}. Run build_schema.py first.")
        did = d[0]["environmentvariabledefinitionid"]
        cur = dv.call("GET", f"environmentvariablevalues?$select=environmentvariablevalueid,value"
                             f"&$filter=_environmentvariabledefinitionid_value eq {did}").get("value", [])
        if cur and cur[0].get("value") == value:
            log(f"  = {name}: {value}")
            continue
        log(f"  + {name}: {value}" + (" (would set)" if dry_run else ""))
        if dry_run:
            continue
        if cur:
            dv.call("PATCH", f"environmentvariablevalues({cur[0]['environmentvariablevalueid']})", {"value": value})
        else:
            dv.call("POST", "environmentvariablevalues", {
                "schemaname": f"{schema}_value", "value": value,
                "EnvironmentVariableDefinitionId@odata.bind": f"/environmentvariabledefinitions({did})"})


def read_variables(dv):
    """{name: effective value} (the environment's value, else the definition's default)."""
    out = {}
    for v in ENVIRONMENT_VARIABLES:
        schema = f"{PREFIX}_{v['name']}"
        d = dv.call("GET", f"environmentvariabledefinitions?$select=environmentvariabledefinitionid,defaultvalue"
                           f"&$filter=schemaname eq '{schema}'").get("value")
        if not d:
            continue
        cur = dv.call("GET", f"environmentvariablevalues?$select=value&$filter=_environmentvariabledefinitionid_value"
                             f" eq {d[0]['environmentvariabledefinitionid']}").get("value", [])
        out[v["name"]] = (cur[0].get("value") if cur else None) or d[0].get("defaultvalue") or ""
    return out


def upsert_webresource(dv, log, name, data, wtype):
    content = base64.b64encode(data if isinstance(data, bytes) else data.encode("utf-8")).decode()
    r = dv.call("GET", f"webresourceset?$select=webresourceid,content&$filter=name eq '{name}'").get("value", [])
    if r:
        if r[0].get("content") != content:
            dv.call("PATCH", f"webresourceset({r[0]['webresourceid']})", {"content": content})
            log(f"  + {name} updated")
        else:
            log(f"  = {name}")
        return r[0]["webresourceid"]
    res = dv.call("POST", "webresourceset", {"name": name, "displayname": name.split("/")[-1],
                                             "webresourcetype": wtype, "content": content})
    log(f"  + {name} added")
    return res.get("_id")


def apply_logo(dv, log, url, fetch, dry_run):
    """Upload the logo as a web resource; returns its id ("dry-run" in a dry run), or None if there's no usable logo."""
    if not url:
        return None
    try:
        data, ctype = fetch(url)
    except Exception as e:  # a broken logo link shouldn't stop the colors
        log(f"  ! couldn't download the logo ({e}); header shows no logo")
        return None
    if ctype not in LOGO_TYPES:
        log(f"  ! logo isn't a PNG, JPG, GIF or SVG ({ctype or 'unknown type'}); header shows no logo")
        return None
    if dry_run:
        log(f"  (would upload {LOGO}, {len(data):,} bytes)")
        return "dry-run"
    return upsert_webresource(dv, log, LOGO, data, LOGO_TYPES[ctype])


def apply_theme(dv, log, values, dry_run, fetch=download):
    header = values.get("BrandHeaderColor")
    if not header:
        log("  - no header color set; the app keeps the Dataverse default header")
        return
    lid = apply_logo(dv, log, values.get("BrandLogoUrl"), fetch, dry_run)
    xml = theme_xml(header, values.get("BrandHeaderTextColor") or "#FFFFFF", values.get("BrandAccentColor"),
                    LOGO if lid else None, values.get("OrgName", ""))
    if dry_run:
        log("  (would upload)\n" + xml)
        return
    wid = upsert_webresource(dv, log, THEME, xml, 4)  # 4 = XML
    sd = dv.call("GET", "settingdefinitions?$select=settingdefinitionid&$filter=uniquename eq 'CustomThemeDefinition'")["value"]
    if not sd:
        raise DataverseError("This environment has no 'Custom theme definition' app setting.")
    sd_id = sd[0]["settingdefinitionid"]
    # Navigation names for appsetting's two lookups, read from metadata rather than assumed.
    rels = dv.call("GET", "EntityDefinitions(LogicalName='appsetting')/ManyToOneRelationships"
                          "?$select=ReferencingAttribute,ReferencingEntityNavigationPropertyName")["value"]
    nav = {r["ReferencingAttribute"]: r["ReferencingEntityNavigationPropertyName"] for r in rels}
    app_ids = []
    for spec in APPS:  # every app gets the same theme, so they all look alike
        app = dv.call("GET", f"appmodules?$select=appmoduleid&$filter=uniquename eq '{spec['uniquename']}'")["value"]
        if not app:
            log(f"  - {spec['name']} isn't there yet (build_app.py builds it); skipped")
            continue
        app_id = app[0]["appmoduleid"]
        app_ids.append(app_id)
        cur = dv.call("GET", f"appsettings?$select=appsettingid,value&$filter=_parentappmoduleid_value eq {app_id}"
                             f" and _settingdefinitionid_value eq {sd_id}").get("value", [])
        if cur and cur[0].get("value") == THEME:
            log(f"  = {spec['name']} uses the custom theme")
        elif cur:
            dv.call("PATCH", f"appsettings({cur[0]['appsettingid']})", {"value": THEME})
            log(f"  + {spec['name']} now uses the custom theme")
        else:
            # The first app keeps the setting name it has always had.
            suffix = "" if spec is APPS[0] else "_" + spec["uniquename"].split("_", 1)[1]
            dv.call("POST", "appsettings", {
                "value": THEME, "uniquename": f"{PREFIX}_CustomThemeDefinition{suffix}",
                f"{nav['settingdefinitionid']}@odata.bind": f"/settingdefinitions({sd_id})",
                f"{nav['parentappmoduleid']}@odata.bind": f"/appmodules({app_id})"})
            log(f"  + {spec['name']} now uses the custom theme")
    if not app_ids:
        raise DataverseError("No app is there yet. Run build_app.py first.")
    dv.call("POST", "PublishXml", {"ParameterXml":
            "<importexportxml><webresources>"
            + "".join(f"<webresource>{{{i}}}</webresource>" for i in (wid, lid) if i and i != "dry-run")
            + "</webresources><appmodules>"
            + "".join(f"<appmodule>{a}</appmodule>" for a in app_ids)
            + "</appmodules></importexportxml>"}, timeout=1200)
    log("  + published")


def run(dv, log, client, dry_run=False, fetch=download):
    settings = client.get("settings", {})
    problems = check_settings(settings)
    if problems:
        raise DataverseError("Client file problems: " + "; ".join(problems))
    log(f"Settings for {client.get('client', 'client')}")
    set_variables(dv, log, settings, dry_run)
    values = settings if dry_run else read_variables(dv)
    log("\nApp header")
    apply_theme(dv, log, values, dry_run, fetch)
    log("\nDry run, nothing changed." if dry_run else "\nDone. Refresh the app (Cmd+Shift+R) to see it.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True)
    ap.add_argument("--client", required=True, help="Client settings file, e.g. clients/example/client.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tenant", default="organizations")
    ap.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    ap.add_argument("--device-code", action="store_true")
    args = ap.parse_args()
    client = json.load(open(args.client, encoding="utf-8"))
    # No solution header: values, the theme file and the app setting belong to this environment only.
    dv = Dataverse(args.url, make_token_provider(args.url, args.client_id, args.tenant, args.device_code), "")
    try:
        run(dv, print, client, args.dry_run)
    except DataverseError as e:
        sys.exit(f"\nSTOPPED: {e}")


if __name__ == "__main__":
    main()
