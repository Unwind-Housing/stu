#!/usr/bin/env python3
"""
Start a TEST environment from scratch, in one go:

  1. Delete every record and every project (tools/reset_records.py). Lists, counties, AMI limits, eligibility
     rules, source forms and message templates stay.
  2. Move the old record folders in SharePoint to the site's recycle bin (only with --sharepoint-site and
     --sharepoint-folder: the folders inside that parent folder in each document library, nothing else).
  3. Load the made-up portfolio of 20 homes (tools/make_test_data.py, tools/import_records.py).
  4. Add made-up history to it: sales, insurance, loans, improvements, requests, follow-ups, notes, ERRR entries
     past verifications and a few staff walk-bys.

NEVER run this on an environment that holds real records. It can't be undone.
Without --confirm it only counts what would go and changes nothing.

Usage:
  python3 tools/start_from_scratch.py --url https://yourtest.crm.dynamics.com
  python3 tools/start_from_scratch.py --url https://yourtest.crm.dynamics.com --confirm yourtest \\
      --sharepoint-site https://yourorg.sharepoint.com/sites/Stewardship --sharepoint-folder DEV
  --confirm        the first part of the environment's address, so a slip can't clear the wrong one
  --keep-projects  leave projects and their priorities, income bands and lottery factors in place
  --no-test-data   stop after clearing: an empty environment
  --email          a test inbox (Gmail): every test household gets it with a dot in a different place, which Gmail
                   delivers to the one inbox. Without it the addresses are at example.com and go nowhere.
"""
import argparse
import os
import sys
import tempfile
from datetime import date
from urllib.parse import quote, unquote, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_schema import (Dataverse, DataverseError, SharePoint, SharePointError, make_token_provider,  # noqa: E402
                          make_sharepoint_token_provider, ln, DEFAULT_CLIENT_ID)
from schema import TABLES, LOOKUPS  # noqa: E402
import import_records as ir  # noqa: E402
import make_test_data as mk  # noqa: E402
import reset_records as rr  # noqa: E402


def clear_folders(sp, folder, delete=False, log=print):
    """Record folders inside <library>/<folder>, for every table with a document library. Recycled, not destroyed."""
    total = 0
    for t in TABLES:
        if not t.get("documents"):
            continue
        parent = f"{sp.path}/{ln(t['name'])}/{folder}"
        r = sp.call("GET", f"web/GetFolderByServerRelativeUrl('{quote(parent)}')/Folders?$select=Name,ServerRelativeUrl",
                    ok404=True)
        subs = [f for f in (r or {}).get("value", []) if f["Name"] != "Forms"]
        if not subs:
            continue
        total += len(subs)
        log(f"  {'-' if delete else ' '} {t['documents']}, {folder}: {len(subs)} folders")
        if delete:
            for f in subs:
                url = quote(f["ServerRelativeUrl"].replace("'", "''"))
                sp.call("POST", f"web/GetFolderByServerRelativeUrl('{url}')/recycle()")
    log(f"{'Moved' if delete else 'Would move'} {total} folders" + (" to the site's recycle bin." if delete else "."))
    return total


# Microsoft's own command line app for Microsoft Graph. In a tenant where the sign-in app for Dataverse tools isn't
# allowed into SharePoint, the folders are cleared through Graph with this one instead (a second sign-in).
GRAPH_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
GRAPH = "https://graph.microsoft.com/v1.0/"


class GraphSite:
    """One SharePoint site through Microsoft Graph: enough to send record folders to the recycle bin."""

    def __init__(self, site_url, get_token, session=None):
        import requests
        self.site = site_url.rstrip("/")
        self.get_token = get_token
        self.s = session or requests.Session()

    def call(self, method, url):
        r = self.s.request(method, url if url.startswith("http") else GRAPH + url,
                           headers={"Authorization": "Bearer " + self.get_token()}, timeout=120)
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise SharePointError(f"{method} {url.split('?')[0][-60:]} -> {r.status_code}: {r.text[:200]}")
        return r.json() if r.content else {}

    def rows(self, url):
        out = []
        while url:
            r = self.call("GET", url) or {}
            out += r.get("value", [])
            url = r.get("@odata.nextLink")
        return out

    def clear(self, folder, delete=False, log=print):
        """As clear_folders(): the record folders inside <library>/<folder> of each document library. Recycled."""
        u = urlparse(self.site)
        site = self.call("GET", f"sites/{u.netloc}:{quote(u.path)}?$select=id,webUrl")
        if not site or site.get("webUrl", "").rstrip("/").lower() != self.site.lower():
            raise SharePointError(f"GET site -> the site {self.site} wasn't found")
        drives = self.rows(f"sites/{site['id']}/drives?$select=id,webUrl")
        total = 0
        for t in TABLES:
            if not t.get("documents"):
                continue
            want = f"{self.site}/{ln(t['name'])}".lower()
            drive = next((x for x in drives if unquote(x.get("webUrl", "")).rstrip("/").lower() == want), None)
            if not drive:
                continue
            subs = [k for k in self.rows(f"drives/{drive['id']}/root:/{quote(folder)}:/children?$select=id,name,folder")
                    if "folder" in k]
            if not subs:
                continue
            total += len(subs)
            log(f"  {'-' if delete else ' '} {t['documents']}, {folder}: {len(subs)} folders")
            if delete:
                for k in subs:
                    self.call("DELETE", f"drives/{drive['id']}/items/{k['id']}")
        log(f"{'Moved' if delete else 'Would move'} {total} folders" + (" to the site's recycle bin." if delete else "."))
        return total


def graph_site(site_url, tenant="organizations"):
    """Sign in to Microsoft Graph (the browser opens) and return the site. Raises SharePointError if it is refused."""
    import msal
    app = msal.PublicClientApplication(GRAPH_CLIENT_ID, authority=f"https://login.microsoftonline.com/{tenant}")
    print("Opening your browser to sign in again, this time for SharePoint through Microsoft Graph.")
    r = app.acquire_token_interactive(scopes=["https://graph.microsoft.com/Sites.ReadWrite.All"], prompt="select_account")
    if "access_token" not in r:
        raise SharePointError("Graph sign-in -> " + str(r.get("error_description", r)).splitlines()[0])
    return GraphSite(site_url, lambda: r["access_token"])


def load_history(dv, today, log=print):
    """Create the rows of make_test_data.history() on the loaded portfolio. Rows that are already there are left alone."""
    rows = mk.history(today)
    tables = sorted({r["table"] for r in rows})
    es = {t: dv.call("GET", f"EntityDefinitions(LogicalName='{ln(t)}')?$select=EntitySetName")["EntitySetName"]
          for t in tables + ["property", "occupancy", "household"]}
    cols = {t: ir.fields(t) for t in tables}
    choices = {c["choice"]: None for t in tables for c in cols[t].values() if c["kind"] == "choice"}
    choices = {c: ir.options(dv, c) for c in sorted(choices)}
    links = {t: {l[1]: l[2] for l in LOOKUPS if l[0] == t} for t in tables}
    pid = {(p.get(ln("name")) or "").lower(): p[ln("propertyid")]
           for p in ir.get_all(dv, f"{es['property']}?$select={ln('propertyid')},{ln('name')}")}
    chain = {}
    for o in ir.get_all(dv, f"{es['occupancy']}?$select={ln('occupancyid')},{ln('startdate')},"
                            f"_{ln('property')}_value,_{ln('household')}_value"):
        chain.setdefault(o[f"_{ln('property')}_value"], []).append(o)
    for c in chain.values():
        c.sort(key=lambda o: o.get(ln("startdate")) or "")

    def parent(t):   # the link a row is told apart by
        return "occupancy" if t not in ("sale", "errrtransaction", "walkby") else "property"

    have = {}
    for t in tables:
        for r in ir.get_all(dv, f"{es[t]}?$select={ln(t)}id,{ln('name')},_{ln(parent(t))}_value"):
            have[(t, r.get(ln("name")), r.get(f"_{ln(parent(t))}_value"))] = r[ln(t) + "id"]
    made = {}
    for r in rows:
        t, home = r["table"], pid.get(r["place"].lower())
        if home is None or home not in chain:
            raise DataverseError(f"The test home '{r['place']}' isn't loaded. Load the test portfolio first.")

        def target(lookup, which):
            kind = links[t][lookup]
            if kind == "property":
                return "property", home
            if kind == "occupancy":
                return "occupancy", chain[home][which][ln("occupancyid")]
            if kind == "household":
                return "household", chain[home][which][f"_{ln('household')}_value"]
            return kind, have[(kind, which, chain[home][-1][ln("occupancyid")])]

        key = (t, r["name"], target(parent(t), r["links"][parent(t)])[1])
        if key in have:
            continue
        body = {ln("name"): r["name"]}
        for label, v in r["values"].items():
            if v != "":
                body[ln(cols[t][label.lower()]["name"])] = ir.convert(cols[t][label.lower()], str(v), choices)
        for lookup, which in r["links"].items():
            kind, rid = target(lookup, which)
            body[f"{ln(lookup)}@odata.bind"] = f"/{es[kind]}({rid})"
        new = dv.call("POST", es[t], body, extra_headers=ir.RETURN)
        have[key] = new.get(ln(t) + "id") or new.get("_id")
        made[t] = made.get(t, 0) + 1
    labels = {t["name"]: t["label"] for t in TABLES}
    log("History added: " + (", ".join(f"{n} {labels[t].lower()}" for t, n in made.items()) or "nothing new"))
    return made


def run(dv, sp=None, folder=None, delete=False, keep_projects=False, test_data=True, today=None, email=None, log=print,
        graph=None):
    """graph: a function that signs in to Microsoft Graph and returns a GraphSite, tried when sp can't get in."""
    today = today or date.today()
    reach, clear = True, lambda **kw: clear_folders(sp, folder, **kw)
    if sp and folder:   # find out before anything is deleted whether this sign-in can reach SharePoint
        try:
            clear(delete=False, log=lambda s: None)
        except SharePointError as e:
            reach, why = False, str(e).split(" -> ")[-1][:60]
            if graph:
                try:
                    site = graph()
                    site.clear(folder, delete=False, log=lambda s: None)
                    reach, clear = True, lambda **kw: site.clear(folder, **kw)
                    log(f"This sign-in can't reach SharePoint ({why}); Microsoft Graph can, so the folders go that way.\n")
                except SharePointError as e2:
                    why += "; Microsoft Graph: " + str(e2).split(" -> ")[-1][:60]
            if not reach:
                log(f"This sign-in can't reach SharePoint ({why}), so the old record folders "
                    "have to be deleted by hand.\n")
    rr.run(dv, delete=delete, with_projects=not keep_projects, log=log)
    if sp and folder and reach:
        log("\nOld record folders in SharePoint:")
        clear(delete=delete, log=log)
    if not delete:
        log("\nNothing was changed. To do it, add --confirm <first part of the address>.")
        return
    if not reach and test_data:
        log(f"\nThe records are cleared and nothing is loaded yet. Now, while every folder there is an old one: in "
            f"SharePoint, open each document library's {folder} folder, select everything in it and delete. Then run "
            "this again without the --sharepoint options to load the test homes.")
        return
    if not test_data:
        return
    log("\nLoading the test portfolio:")
    with tempfile.TemporaryDirectory() as tmp:
        mk.write(tmp, today, email)
        counts = ir.run(dv, tmp, log=lambda s: None, add_list_values=True)
    log("  " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    load_history(dv, today, log=lambda s: log("  " + s))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="Environment URL, e.g. https://yourtest.crm.dynamics.com")
    ap.add_argument("--confirm", help="The first part of the environment's address. Without it, nothing is changed.")
    ap.add_argument("--keep-projects", action="store_true")
    ap.add_argument("--no-test-data", action="store_true")
    ap.add_argument("--email", help="A test inbox (Gmail) for every test household, with a dot in a different place each")
    ap.add_argument("--sharepoint-site", help="Also clear the old record folders in this site's document libraries")
    ap.add_argument("--sharepoint-folder", help="The parent folder this environment's record folders are in (DEV)")
    ap.add_argument("--tenant", default="organizations")
    ap.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    ap.add_argument("--device-code", action="store_true")
    args = ap.parse_args()
    host = (urlparse(args.url).hostname or "").split(".")[0]
    if args.confirm and args.confirm.lower() != host.lower():
        sys.exit(f"STOPPED: --confirm must be {host} (the first part of the address). Nothing was changed.")
    if bool(args.sharepoint_site) != bool(args.sharepoint_folder):
        sys.exit("STOPPED: --sharepoint-site and --sharepoint-folder go together. Only folders inside that parent "
                 "folder are cleared, so an environment that shares a site can't touch another one's folders.")
    dv = Dataverse(args.url, make_token_provider(args.url, args.client_id, args.tenant, args.device_code), None)
    sp = SharePoint(args.sharepoint_site, make_sharepoint_token_provider(
        args.sharepoint_site, args.client_id, args.tenant, args.device_code)) if args.sharepoint_site else None
    try:
        run(dv, sp, args.sharepoint_folder, delete=bool(args.confirm), keep_projects=args.keep_projects,
            test_data=not args.no_test_data, email=args.email,
            graph=(lambda: graph_site(args.sharepoint_site, args.tenant)) if sp and not args.device_code else None)
    except (DataverseError, SharePointError) as e:
        sys.exit(f"\nSTOPPED: {e}")


if __name__ == "__main__":
    main()
