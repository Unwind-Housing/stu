#!/usr/bin/env python3
"""
Point every screener's "AMI limits used" at its county's newest HUD AMI Limits record, and its
"Eligibility rules used" at the organization's eligibility rules.

Stated income (% of AMI) is a formula column over that link (schema.py AMI_PCT), so it recalculates by
itself when the income, household size or limits change. The screener intake flow sets the link for
new screeners. Run this after loading a new year's limits, so applications that came in earlier move
to the new year too (and any that had no limits for their county pick them up).

  Newest = the highest Year among active records with Source = HUD for the application's county.
  An application whose county has no HUD limits is left as it is.
  Organization eligibility is a formula over Eligibility rules used, so linking it is all that's needed.

Usage:
  python3 tools/recalc_ami.py --url https://yourorg.crm.dynamics.com --dry-run
  python3 tools/recalc_ami.py --url https://yourorg.crm.dynamics.com
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from build_schema import Dataverse, DataverseError, make_token_provider, DEFAULT_CLIENT_ID, SOLUTION  # noqa: E402


def get_all(dv, path):
    rows, page = [], dv.call("GET", path)
    rows += page.get("value", [])
    while page.get("@odata.nextLink"):
        page = dv.call("GET", page["@odata.nextLink"].split("/api/data/v9.2/", 1)[1])
        rows += page.get("value", [])
    return rows


def hud_value(dv):
    """The Source choice's value for HUD, read from the environment (it depends on the publisher's prefix)."""
    os_ = dv.call("GET", "GlobalOptionSetDefinitions(Name='clt_limitsource')")
    for o in os_["Options"]:
        if ((o.get("Label") or {}).get("UserLocalizedLabel") or {}).get("Label") == "HUD":
            return o["Value"]
    raise DataverseError("The AMI limit source choice has no HUD option. Run build_schema.py first.")


def newest_limits(dv):
    """{county id: newest HUD AMI Limits record id}"""
    rows = get_all(dv, "clt_incomelimitsets?$select=clt_incomelimitsetid,_clt_county_value,clt_year"
                       f"&$filter=statecode eq 0 and clt_limitsource eq {hud_value(dv)}&$orderby=clt_year desc")
    newest = {}
    for r in rows:  # newest first, so the first row per county wins
        if r.get("_clt_county_value"):
            newest.setdefault(r["_clt_county_value"], r["clt_incomelimitsetid"])
    return newest


def org_rules(dv):
    """The organization's eligibility record (the oldest active one), or None."""
    rows = dv.call("GET", "clt_eligibilities?$select=clt_eligibilityid&$filter=statecode eq 0&$orderby=createdon asc&$top=1")
    return rows["value"][0]["clt_eligibilityid"] if rows.get("value") else None


def run(dv, log=print, dry_run=False):
    newest = newest_limits(dv)
    rules = org_rules(dv)
    apps = get_all(dv, "clt_applications?$select=clt_applicationid,clt_name,_clt_county_value,_clt_amilimits_value,"
                       "_clt_eligibilityrules_value"
                       "&$filter=statecode eq 0 and clt_screenerentryid ne null")
    changed = missing = 0
    for a in apps:
        body = {}
        want = newest.get(a.get("_clt_county_value"))
        if not want:
            missing += 1
        elif want != a.get("_clt_amilimits_value"):
            body["clt_amilimits@odata.bind"] = f"/clt_incomelimitsets({want})"
        if rules and rules != a.get("_clt_eligibilityrules_value"):
            body["clt_eligibilityrules@odata.bind"] = f"/clt_eligibilities({rules})"
        if not body:
            continue
        changed += 1
        what = " and ".join(x for x, k in (("AMI limits", "clt_amilimits@odata.bind"),
                                           ("eligibility rules", "clt_eligibilityrules@odata.bind")) if k in body)
        log(f"  {a.get('clt_name')}: {what} linked")
        if not dry_run:
            dv.call("PATCH", f"clt_applications({a['clt_applicationid']})", body)
    if not rules:
        log("  ! No Organization eligibility record: add one under Settings > Organization eligibility.")
    log(f"\n{len(apps)} screeners, {len(newest)} counties with HUD limits, {changed} "
        f"{'would change' if dry_run else 'updated'}, {missing} with no HUD limits for their county.")
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="Environment URL, e.g. https://yourorg.crm.dynamics.com")
    ap.add_argument("--dry-run", action="store_true", help="Report what would change, change nothing")
    ap.add_argument("--tenant", default="organizations")
    ap.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    ap.add_argument("--device-code", action="store_true")
    args = ap.parse_args()
    dv = Dataverse(args.url, make_token_provider(args.url, args.client_id, args.tenant, args.device_code), SOLUTION)
    try:
        run(dv, dry_run=args.dry_run)
    except DataverseError as e:
        sys.exit(f"\nSTOPPED: {e}")


if __name__ == "__main__":
    main()
