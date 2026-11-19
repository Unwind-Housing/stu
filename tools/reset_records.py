#!/usr/bin/env python3
"""
Clear a TEST environment's records, so testing can start from scratch.

Deletes every property, household, member, application (with its income, debts and assets), occupancy and
everything recorded on one (verifications, insurance, follow-ups, loans, requests), sale, fee, ERRR entry,
certification, selection round, notice and form submission.

Keeps the setup: Settings > Lists (with the counties), HUD AMI Limits, eligibility rules, source forms,
message templates, and projects with their priorities, income bands and lottery factors. A project's homes
go, because they point at properties. Add --with-projects to delete the projects too.

Not touched: SharePoint (old record folders stay where they are), the forms platform, flows, settings.
Record numbers don't start over: the next property after P-00019 is P-00020.

NEVER run this on an environment that holds real records. It can't be undone. Without --delete it only counts.

Usage:
  python3 tools/reset_records.py --url https://yourtest.crm.dynamics.com                       (counts, deletes nothing)
  python3 tools/reset_records.py --url https://yourtest.crm.dynamics.com --delete --confirm yourtest
  --confirm must be the first part of the environment's address, so a slip of the hand can't clear the wrong one.
"""
import argparse
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from build_schema import (Dataverse, DataverseError, make_token_provider, ln,  # noqa: E402
                          DEFAULT_CLIENT_ID)
from schema import TABLES, LOOKUPS  # noqa: E402

SETUP = ["listitem", "incomelimitset", "eligibility", "sourceform", "messagetemplate"]
PROJECT_SETUP = ["project", "projectpriority", "projectband", "lotteryfactor"]


def order(with_projects=False):
    """The tables to clear, each one before any table it hangs off (an occupancy before its property)."""
    keep = set(SETUP) | (set() if with_projects else set(PROJECT_SETUP))
    todo = [t["name"] for t in TABLES if t["name"] not in keep]
    # table -> the tables hanging off it, which go first. A link that is simply removed on delete holds nothing up.
    waits = {t: {l[0] for l in LOOKUPS if l[2] == t and l[0] in todo and l[0] != t and l[4] != "RemoveLink"} for t in todo}
    out = []
    while todo:
        ready = [t for t in todo if not (waits[t] - set(out))]
        if not ready:
            raise DataverseError("The tables link to each other in a circle: " + ", ".join(todo))
        out.append(ready[0])
        todo.remove(ready[0])
    return out


def get_ids(dv, es, idcol):
    ids, nxt = [], f"{es}?$select={idcol}"
    while nxt:
        r = dv.call("GET", nxt)
        ids.extend(x[idcol] for x in r.get("value", []))
        link = r.get("@odata.nextLink")
        nxt = link.split("/api/data/v9.2/", 1)[1] if link else None
    return ids


def run(dv, delete=False, with_projects=False, log=print):
    labels = {t["name"]: t["label"] for t in TABLES}
    counts = {}
    log(("Deleting" if delete else "Counting only, nothing will be deleted") + ":\n")
    for name in order(with_projects):
        d = dv.call("GET", f"EntityDefinitions(LogicalName='{ln(name)}')?$select=EntitySetName", ok404=True)
        if not d:
            continue
        ids = get_ids(dv, d["EntitySetName"], ln(name) + "id")   # read now: an earlier delete may have taken some along
        if not ids:
            continue
        counts[labels[name]] = len(ids)
        log(f"  {'-' if delete else ' '} {labels[name]}: {len(ids)}")
        if delete:
            for rid in ids:
                dv.call("DELETE", f"{d['EntitySetName']}({rid})", ok404=True)
    total = sum(counts.values())
    log(f"\n{'Deleted' if delete else 'Would delete'} {total} records." + ("" if delete or not total else
        " To delete them, run again with --delete --confirm <first part of the address>."))
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="Environment URL, e.g. https://yourtest.crm.dynamics.com")
    ap.add_argument("--delete", action="store_true", help="Really delete. Without it, only counts.")
    ap.add_argument("--confirm", help="With --delete: the first part of the environment's address (yourtest)")
    ap.add_argument("--with-projects", action="store_true", help="Also delete projects and their priorities, bands and factors")
    ap.add_argument("--tenant", default="organizations")
    ap.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    ap.add_argument("--device-code", action="store_true")
    args = ap.parse_args()
    host = (urlparse(args.url).hostname or "").split(".")[0]
    if args.delete and (args.confirm or "").lower() != host.lower():
        sys.exit(f"STOPPED: to delete, add --confirm {host} (the first part of the address). Nothing was deleted.")
    dv = Dataverse(args.url, make_token_provider(args.url, args.client_id, args.tenant, args.device_code), None)
    try:
        run(dv, delete=args.delete, with_projects=args.with_projects)
    except DataverseError as e:
        sys.exit(f"\nSTOPPED: {e}")


if __name__ == "__main__":
    main()
