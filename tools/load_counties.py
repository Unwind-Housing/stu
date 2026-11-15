#!/usr/bin/env python3
"""
Load every US county (50 states and DC) into the County list, each linked to its State.

Source: docs/reference/us-counties-2020.csv, from the Census Bureau's 2020 national county file
(https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt). 3,143 counties
and county-equivalents: parishes, boroughs, census areas, independent cities and DC.

Safe to re-run. It never deletes anything and never creates a duplicate:
  - A County value already linked to the right State is left alone (missing form answers are added).
  - A County value with no State is matched by name within --existing-state (for example WA),
    then linked to that State. Without --existing-state, unlinked values are listed and left alone.
  - Everything else is created: name "Jefferson County", form answers "Jefferson County" and "Jefferson".

Needs the State list (build_schema.py v0.5 seeds it) and the List item "State (counties only)" lookup.

Usage:
  python3 tools/load_counties.py --url https://yourorg.crm.dynamics.com --dry-run
  python3 tools/load_counties.py --url https://yourorg.crm.dynamics.com --existing-state WA
"""
import argparse
import csv
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from build_schema import (Dataverse, DataverseError, make_token_provider, ln,  # noqa: E402
                          DEFAULT_CLIENT_ID, SOLUTION)

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "reference", "us-counties-2020.csv")
SUFFIX = re.compile(r"\s+(county|parish|borough|census area|municipality|city and borough)$")


def norm(name):
    """Comparable form of a county name: no accents, lower case, no 'County'-style suffix."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().strip()
    s = re.sub(r"[.']", "", s)
    return SUFFIX.sub("", s)


def answers_for(name, short):
    out = [name, short]
    for a in (name, short):
        plain = unicodedata.normalize("NFKD", a).encode("ascii", "ignore").decode()
        if plain != a:
            out.append(plain)
    seen, result = set(), []
    for a in out:
        if a and a.lower() not in seen:
            seen.add(a.lower())
            result.append(a)
    return result


def read_csv(path=CSV_PATH):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_all(dv, path):
    """GET a collection, following @odata.nextLink pages."""
    rows, nxt = [], path
    while nxt:
        r = dv.call("GET", nxt)
        rows.extend(r.get("value", []))
        link = r.get("@odata.nextLink")
        nxt = link.split("/api/data/v9.2/", 1)[1] if link else None
    return rows


def list_values(dv):
    """{list name: option value} for the List name choice."""
    os_ = dv.call("GET", f"GlobalOptionSetDefinitions(Name='{ln('listname')}')")
    out = {}
    for o in os_["Options"]:
        label = (o.get("Label") or {}).get("UserLocalizedLabel") or {}
        out[label.get("Label")] = o["Value"]
    return out


def run(dv, log=print, existing_state=None, dry_run=False, rows=None):
    rows = rows if rows is not None else read_csv()
    lists = list_values(dv)
    for needed in ("State", "County"):
        if needed not in lists:
            raise DataverseError(f"The List name choice has no '{needed}' option. Run build_schema.py first.")
    es = dv.call("GET", f"EntityDefinitions(LogicalName='{ln('listitem')}')?$select=EntitySetName")["EntitySetName"]
    sel = f"$select={ln('listitemid')},{ln('name')},{ln('formanswers')},_{ln('state')}_value"
    # A lookup to its own table gets a longer navigation name (clt_state_clt_listitem), so ask for it.
    rel = dv.call("GET", f"RelationshipDefinitions(SchemaName='{ln('listitem')}_listitem_state')"
                         "/Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata?$select=ReferencingEntityNavigationPropertyName")
    nav = rel["ReferencingEntityNavigationPropertyName"]

    states = get_all(dv, f"{es}?{sel}&$filter={ln('list')} eq {lists['State']}")
    state_id = {}
    for s in states:
        for a in (s.get(ln("formanswers")) or "").splitlines():
            if re.fullmatch(r"[A-Z]{2}", a.strip()):
                state_id[a.strip()] = s[ln("listitemid")]
    missing = sorted({r["state"] for r in rows} - set(state_id))
    if missing:
        raise DataverseError(f"These states aren't in the State list (by their two-letter form answer): "
                             f"{', '.join(missing)}. Run build_schema.py, or add them under Settings > Lists.")

    counties = get_all(dv, f"{es}?{sel}&$filter={ln('list')} eq {lists['County']}")
    linked = {}      # (state id, normalized name) -> row
    unlinked = {}    # normalized name -> [rows]
    for c in counties:
        sid = c.get(f"_{ln('state')}_value")
        if sid:
            linked[(sid, norm(c[ln("name")]))] = c
        else:
            unlinked.setdefault(norm(c[ln("name")]), []).append(c)

    counts = {"created": 0, "linked": 0, "answers added": 0, "already there": 0}
    for i, r in enumerate(rows, 1):
        sid = state_id[r["state"]]
        key = (sid, norm(r["name"]))
        want = answers_for(r["name"], r["shortname"])
        row = linked.get(key)
        if row is None and existing_state == r["state"] and unlinked.get(key[1]):
            row = unlinked[key[1]].pop(0)
            have = (row.get(ln("formanswers")) or "").splitlines()
            merged = have + [a for a in want if a.lower() not in {h.lower() for h in have}]
            if not dry_run:
                dv.call("PATCH", f"{es}({row[ln('listitemid')]})", {
                    f"{nav}@odata.bind": f"/{es}({sid})", ln("formanswers"): "\n".join(merged)})
            log(f"  + linked existing '{row[ln('name')]}' to {r['state']}")
            counts["linked"] += 1
            linked[key] = row
            continue
        if row is not None:
            have = (row.get(ln("formanswers")) or "").splitlines()
            add = [a for a in want if a.lower() not in {h.lower() for h in have}]
            if add:
                if not dry_run:
                    dv.call("PATCH", f"{es}({row[ln('listitemid')]})", {ln("formanswers"): "\n".join(have + add)})
                counts["answers added"] += 1
            else:
                counts["already there"] += 1
            continue
        if not dry_run:
            dv.call("POST", es, {ln("name"): r["name"], ln("list"): lists["County"],
                                 ln("formanswers"): "\n".join(want),
                                 f"{nav}@odata.bind": f"/{es}({sid})"})
        counts["created"] += 1
        linked[key] = {ln("name"): r["name"]}
        if i % 250 == 0:
            log(f"  ... {i} of {len(rows)}")

    left = [c[ln("name")] for cs in unlinked.values() for c in cs]
    if left:
        log(f"\n  ! {len(left)} County values have no State and weren't matched: {', '.join(sorted(left)[:20])}"
            + (" ..." if len(left) > 20 else "")
            + ("\n    Re-run with --existing-state XX to link them by name within that state, or set their State"
               " under Settings > Lists." if not existing_state else
               f"\n    No county with that name in {existing_state}. Set their State under Settings > Lists."))
    log(("\nDry run, nothing changed. Would do: " if dry_run else "\nDone. ")
        + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="Environment URL, e.g. https://yourorg.crm.dynamics.com")
    ap.add_argument("--existing-state", help="Two-letter state for County values that have no State yet, e.g. WA")
    ap.add_argument("--dry-run", action="store_true", help="Report what would change, change nothing")
    ap.add_argument("--tenant", default="organizations")
    ap.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    ap.add_argument("--device-code", action="store_true")
    args = ap.parse_args()
    dv = Dataverse(args.url, make_token_provider(args.url, args.client_id, args.tenant, args.device_code), SOLUTION)
    try:
        run(dv, existing_state=(args.existing_state or "").upper() or None, dry_run=args.dry_run)
    except DataverseError as e:
        sys.exit(f"\nSTOPPED: {e}")


if __name__ == "__main__":
    main()
