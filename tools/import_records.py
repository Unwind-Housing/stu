#!/usr/bin/env python3
"""
Load properties, households, their members, occupancies and monthly fees from spreadsheets (CSV).

Reads a folder holding any of these files (templates and rules: docs/templates/README.md):
  properties.csv   one row per home or parcel
  households.csv   one row per household
  members.csv      one row per person, linked by Household ref
  occupancies.csv  who owns or rents which home, with the resale formula terms
  fees.csv         monthly fees per property (ground lease fee, ERRR)

Everything is checked first: if any row has a problem (an unknown status, a county that isn't in the
list, a ref that points nowhere), nothing is written and every problem is listed.

Safe to re-run. It never deletes anything and never creates a duplicate:
  - A property with the same name (street, plus unit) is left alone, unless the row gives its Record
    number (P-00002): then the filled-in columns are updated and blank cells are left alone.
  - A household whose primary applicant has the same first and last name is left alone, unless its
    Household ref is its record number (H-00003): then the filled-in columns are updated.
  - Members, occupancies and fees that are already there are left alone.

Usage:
  python3 tools/import_records.py "export/load" --url https://yourorg.crm.dynamics.com --dry-run
  python3 tools/import_records.py "export/load" --url https://yourorg.crm.dynamics.com
  Add --add-list-values to add Property type, Tenure type, Neighborhood or Relationship values the files use
  that aren't under Settings > Lists yet.
"""
import argparse
import csv
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from build_schema import (Dataverse, DataverseError, make_token_provider, ln,  # noqa: E402
                          DEFAULT_CLIENT_ID, SOLUTION)
from schema import TABLES  # noqa: E402

FILES = [("properties.csv", "property"), ("households.csv", "household"), ("members.csv", "householdmember"),
         ("occupancies.csv", "occupancy"), ("fees.csv", "fee")]
# Columns that aren't plain fields: links to other rows in the files, or to a list value.
REFS = {"property ref", "household ref", "record number"}
LIST_COLUMNS = {  # header -> (lookup column, list name)
    "property": {"state": ("state", "State"), "county": ("county", "County"),
                 "property type": ("propertytype", "Property type"), "tenure type": ("tenuretype", "Tenure type"),
                 "neighborhood": ("neighborhood", "Neighborhood")},
    "household": {"mailing state": ("mailingstate", "State")},
    "householdmember": {"relationship to primary applicant": ("relationship", "Relationship")},
}
ADDABLE_LISTS = {"Property type", "Tenure type", "Relationship", "Neighborhood"}
RETURN = {"Prefer": 'return=representation,odata.include-annotations="*"'}


def table(name):
    return next(t for t in TABLES if t["name"] == name)


def fields(name):
    """{header in lower case: column} for the columns a file may fill in."""
    return {c["label"].lower(): c for c in table(name)["columns"] if c["kind"] not in ("fx", "autonumber", "file")}


def read_folder(folder):
    out = {}
    for fname, tname in FILES:
        path = os.path.join(folder, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
        out[tname] = [r for r in rows if any(r.values())]
    return out


def get_all(dv, path):
    rows, nxt = [], path
    while nxt:
        r = dv.call("GET", nxt)
        rows.extend(r.get("value", []))
        link = r.get("@odata.nextLink")
        nxt = link.split("/api/data/v9.2/", 1)[1] if link else None
    return rows


def options(dv, choice):
    """{label in lower case: value} for a global choice."""
    os_ = dv.call("GET", f"GlobalOptionSetDefinitions(Name='{ln(choice)}')")
    return {((o.get("Label") or {}).get("UserLocalizedLabel") or {}).get("Label", "").lower(): o["Value"]
            for o in os_["Options"]}


def convert(col, raw, choices):
    """A cell as the value Dataverse wants. Raises ValueError with a plain message."""
    kind = col["kind"]
    if kind in ("text", "email", "phone", "url", "memo"):
        if col.get("max") and len(raw) > col["max"]:
            raise ValueError(f"is {len(raw)} characters; the limit is {col['max']}")
        return raw
    if kind in ("int", "dec", "money"):
        try:
            n = float(raw.replace("$", "").replace(",", "").replace("%", ""))
        except ValueError:
            raise ValueError(f"'{raw}' is not a number")
        if kind == "int":
            if n != int(n):
                raise ValueError(f"'{raw}' should be a whole number")
            return int(n)
        return n
    if kind in ("date", "datetime"):
        try:
            datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"'{raw}' is not a date like 2026-03-31")
        return raw
    if kind == "bool":
        if raw.lower() in ("yes", "y", "true", "1"):
            return True
        if raw.lower() in ("no", "n", "false", "0"):
            return False
        raise ValueError(f"'{raw}' should be Yes or No")
    if kind == "choice":
        opts = choices[col["choice"]]
        if raw.lower() not in opts:
            raise ValueError(f"'{raw}' isn't one of: {', '.join(k for k in opts)}")
        return opts[raw.lower()]
    raise ValueError(f"column type {kind} can't be imported")


class Importer:
    def __init__(self, dv, data, log=print, add_list_values=False):
        self.dv, self.data, self.log, self.add = dv, data, log, add_list_values
        self.problems, self.actions = [], []
        self.counts = {"created": 0, "updated": 0, "already there": 0, "list values added": 0}

    # ---- what the environment has -------------------------------------------------
    def load_environment(self):
        dv = self.dv
        self.es = {t: dv.call("GET", f"EntityDefinitions(LogicalName='{ln(t)}')?$select=EntitySetName")["EntitySetName"]
                   for t in ("property", "household", "householdmember", "occupancy", "fee", "listitem")}
        used = {c["choice"] for t in self.data for c in table(t)["columns"] if c["kind"] == "choice"}
        self.choices = {c: options(dv, c) for c in sorted(used)}
        self.listvalue = {k: v for k, v in options(dv, "listname").items()}
        self.lists = {}  # list name -> [{id, name, answers, state}]
        for lname in sorted({l for t in self.data for _, l in LIST_COLUMNS.get(t, {}).values()}):
            val = self.listvalue.get(lname.lower())
            if val is None:
                raise DataverseError(f"The List name choice has no '{lname}' option. Run build_schema.py first.")
            rows = get_all(dv, f"{self.es['listitem']}?$select={ln('listitemid')},{ln('name')},{ln('formanswers')},"
                               f"_{ln('state')}_value&$filter={ln('list')} eq {val}")
            self.lists[lname] = [{"id": r[ln("listitemid")], "name": r[ln("name")],
                                  "answers": [a.strip().lower() for a in (r.get(ln("formanswers")) or "").splitlines()],
                                  "state": r.get(f"_{ln('state')}_value")} for r in rows]
        e = self.es
        self.props = get_all(dv, f"{e['property']}?$select={ln('propertyid')},{ln('name')},{ln('recordnumber')}")
        self.hhs = get_all(dv, f"{e['household']}?$select={ln('householdid')},{ln('name')},{ln('recordnumber')}")
        self.members = get_all(dv, f"{e['householdmember']}?$select={ln('firstname')},{ln('lastname')},"
                                   f"{ln('applicantrole')},_{ln('household')}_value")
        self.occs = get_all(dv, f"{e['occupancy']}?$select={ln('startdate')},_{ln('property')}_value,"
                                f"_{ln('household')}_value") if "occupancy" in self.data else []
        self.fees = get_all(dv, f"{e['fee']}?$select={ln('feetype')},{ln('effectivestart')},"
                                f"_{ln('property')}_value") if "fee" in self.data else []

    # ---- helpers ------------------------------------------------------------------
    def bad(self, fname, n, msg):
        self.problems.append(f"{fname}, row {n}: {msg}")

    def list_item(self, lname, raw, state=None):
        """Id of a list value by name or form answer (a County within its State). None if not found."""
        want = raw.strip().lower()
        hits = [i for i in self.lists[lname] if want == i["name"].lower() or want in i["answers"]]
        if lname == "County":
            hits = [i for i in hits if i["state"] == state]
        return hits[0]["id"] if hits else None

    def body_for(self, tname, fname, n, row):
        """(plain field values, list lookups) from a row. Records problems; never raises."""
        cols, lists = fields(tname), LIST_COLUMNS.get(tname, {})
        body, binds, state = {}, {}, None
        for header, raw in row.items():
            h = header.lower()
            if h in REFS or not header:
                continue
            if h not in cols and h not in lists:
                if n == 2:
                    self.bad(fname, 1, f"column '{header}' isn't a field on {table(tname)['label']}")
                continue
            if raw == "" or h in lists:
                continue
            try:
                body[ln(cols[h]["name"])] = convert(cols[h], raw, self.choices)
            except ValueError as e:
                self.bad(fname, n, f"{header} {e}")
        for h in sorted(lists, key=lambda x: x != "state" and x != "mailing state"):  # State before County
            raw = next((v for k, v in row.items() if k.lower() == h), "")
            if not raw:
                continue
            col, lname = lists[h]
            item = self.list_item(lname, raw, state)
            if lname == "State":
                state = item
            if item is None and lname in ADDABLE_LISTS and self.add:
                item = ("new", lname, raw)
            if item is None:
                hint = (" in that State" if lname == "County" else "") + (
                    ". Re-run with --add-list-values to add it" if lname in ADDABLE_LISTS else "")
                self.bad(fname, n, f"{h.capitalize()} '{raw}' isn't under Settings > Lists{hint}")
                continue
            binds[ln(col)] = item
        return body, binds

    def act(self, kind, tname, label, body=None, binds=None, ref=None, target=None):
        self.actions.append({"kind": kind, "table": tname, "label": label, "body": body or {}, "binds": binds or {},
                             "ref": ref, "target": target})

    # ---- the plan -----------------------------------------------------------------
    def plan(self):
        self.prop_ref, self.hh_ref, self.hh_name = {}, {}, {}
        self.plan_properties()
        self.plan_households()
        self.plan_occupancies()
        self.plan_fees()

    def plan_properties(self):
        by_name = {(p.get(ln("name")) or "").lower(): p for p in self.props}
        by_number = {(p.get(ln("recordnumber")) or "").upper(): p for p in self.props}
        self.prop_name = {p[ln("propertyid")]: p.get(ln("name")) or "" for p in self.props}
        for p in self.props:
            if p.get(ln("recordnumber")):
                self.prop_ref[p[ln("recordnumber")].upper()] = p[ln("propertyid")]
        for n, row in enumerate(self.data.get("property", []), 2):
            f = "properties.csv"
            body, binds = self.body_for("property", f, n, row)
            street, unit = row.get("Street address", ""), row.get("Unit", "")
            name = f"{street}, Unit {unit}" if unit else street
            ref, number = row.get("Property ref", "").upper(), row.get("Record number", "").upper()
            if number:
                if number not in by_number:
                    self.bad(f, n, f"Record number {number} isn't a property in this environment")
                    continue
                pid = by_number[number][ln("propertyid")]
                if name:
                    body[ln("name")] = name
                self.act("update", "property", f"{number} {by_number[number].get(ln('name')) or ''}", body, binds, target=pid)
                self.prop_ref[ref or number] = pid
                continue
            if not street:
                self.bad(f, n, "Street address is blank")
                continue
            key = ref or name.upper()
            if key in self.prop_ref and ref:
                self.bad(f, n, f"Property ref {ref} is used twice")
                continue
            if name.lower() in by_name:
                pid = by_name[name.lower()][ln("propertyid")]
                self.act("same", "property", name)
                self.prop_ref[key] = pid
                continue
            body[ln("name")] = name
            self.act("create", "property", name, body, binds, ref=("property", key))
            self.prop_ref[key] = ("property", key)
            self.prop_name[("property", key)] = name
            by_name[name.lower()] = {ln("propertyid"): ("property", key)}

    def plan_households(self):
        primary = self.choices.get("applicantrole", {}).get("primary applicant")
        people = {}   # household id -> {(first, last)}
        prim = {}     # (first, last) of a primary applicant -> household id
        for m in self.members:
            hid = m.get(f"_{ln('household')}_value")
            who = ((m.get(ln("firstname")) or "").strip().lower(), (m.get(ln("lastname")) or "").strip().lower())
            people.setdefault(hid, set()).add(who)
            if m.get(ln("applicantrole")) == primary:
                prim.setdefault(who, hid)
        by_number = {(h.get(ln("recordnumber")) or "").upper(): h for h in self.hhs}
        names = {(h.get(ln("name")) or "").lower() for h in self.hhs}
        for h in self.hhs:
            self.hh_name[h[ln("householdid")]] = h.get(ln("name")) or ""
            if h.get(ln("recordnumber")):
                self.hh_ref[h[ln("recordnumber")].upper()] = h[ln("householdid")]
        members = {}
        for n, row in enumerate(self.data.get("householdmember", []), 2):
            members.setdefault(row.get("Household ref", "").upper(), []).append((n, row))
        seen = set()
        for n, row in enumerate(self.data.get("household", []), 2):
            f = "households.csv"
            ref = row.get("Household ref", "").upper()
            body, binds = self.body_for("household", f, n, row)
            if not ref:
                self.bad(f, n, "Household ref is blank")
                continue
            if ref in seen:
                self.bad(f, n, f"Household ref {ref} is used twice")
                continue
            seen.add(ref)
            mine = members.get(ref, [])
            prims = [r for _, r in mine if r.get("Applicant role", "").lower() == "primary applicant"]
            if ref in by_number:
                hid = by_number[ref][ln("householdid")]
                self.act("update", "household", f"{ref} {by_number[ref].get(ln('name')) or ''}", body, binds, target=hid)
            else:
                if len(prims) != 1:
                    self.bad(f, n, f"household {ref} needs exactly one Primary applicant in members.csv (it has {len(prims)})")
                    continue
                first, last = prims[0].get("First name", ""), prims[0].get("Last name", "")
                if not last:
                    self.bad(f, n, f"household {ref}: the primary applicant has no Last name")
                    continue
                hid = prim.get((first.lower(), last.lower()))
                if hid:
                    self.act("same", "household", self.hh_name.get(hid) or last)
                else:
                    name = next(c for c in [last] + [f"{last}, {first}" + (f" {i}" if i > 1 else "") for i in range(1, 50)]
                                if c.lower() not in names)
                    names.add(name.lower())
                    body[ln("name")] = name
                    hid = ("household", ref)
                    self.act("create", "household", name, body, binds, ref=hid)
                    self.hh_name[hid] = name
            self.hh_ref[ref] = hid
            for mn, m in mine:
                mbody, mbinds = self.body_for("householdmember", "members.csv", mn, m)
                first, last = m.get("First name", ""), m.get("Last name", "")
                if not (first or last):
                    self.bad("members.csv", mn, "First name and Last name are both blank")
                    continue
                full = f"{first} {last}".strip()
                if (first.lower(), last.lower()) in people.get(hid, set()):
                    self.act("same", "householdmember", f"{full} ({self.hh_name.get(hid, ref)})")
                    continue
                mbody[ln("name")] = full
                mbinds[ln("household")] = hid
                self.act("create", "householdmember", f"{full} ({self.hh_name.get(hid, ref)})", mbody, mbinds)
        for ref, rows in members.items():
            if ref not in seen:
                for mn, _ in rows:
                    self.bad("members.csv", mn, f"Household ref '{ref}' isn't in households.csv")

    def parents(self, fname, n, row, need_household=True):
        pref, href = row.get("Property ref", "").upper(), row.get("Household ref", "").upper()
        pid, hid = self.prop_ref.get(pref), self.hh_ref.get(href)
        if pid is None:
            self.bad(fname, n, f"Property ref '{pref}' isn't in properties.csv and isn't a record number here")
        if need_household and hid is None:
            self.bad(fname, n, f"Household ref '{href}' isn't in households.csv and isn't a record number here")
        return pid, hid

    def plan_occupancies(self):
        have = {(o.get(f"_{ln('property')}_value"), o.get(f"_{ln('household')}_value"), (o.get(ln("startdate")) or "")[:10])
                for o in self.occs}
        current = self.choices.get("occupancystatus", {}).get("current")
        for n, row in enumerate(self.data.get("occupancy", []), 2):
            f = "occupancies.csv"
            body, binds = self.body_for("occupancy", f, n, row)
            pid, hid = self.parents(f, n, row)
            if pid is None or hid is None:
                continue
            name = f"{self.hh_name.get(hid, '').split(',')[0].strip()} - {self.prop_name.get(pid, '')}"
            if (pid, hid, row.get("Start date", "")) in have:
                self.act("same", "occupancy", name)
                continue
            body[ln("name")] = name
            binds.update({ln("property"): pid, ln("household"): hid})
            self.act("create", "occupancy", name, body, binds,
                     ref=("current", pid) if body.get(ln("status")) == current else None)

    def plan_fees(self):
        have = {(x.get(f"_{ln('property')}_value"), x.get(ln("feetype")), (x.get(ln("effectivestart")) or "")[:10])
                for x in self.fees}
        for n, row in enumerate(self.data.get("fee", []), 2):
            f = "fees.csv"
            body, binds = self.body_for("fee", f, n, row)
            pid, _ = self.parents(f, n, row, need_household=False)
            if pid is None:
                continue
            ftype, start = row.get("Fee type", ""), row.get("Effective start", "")
            if not ftype or ln("amount") not in body:
                self.bad(f, n, "Fee type and Monthly amount are both needed")
                continue
            when = f" from {datetime.strptime(start, '%Y-%m-%d'):%b %Y}" if ln("effectivestart") in body else ""
            name = f"{ftype}{when}"
            label = f"{name}, ${body[ln('amount')]:,.2f} ({self.prop_name.get(pid, '')})"
            if (pid, body.get(ln("feetype")), start) in have:
                self.act("same", "fee", label)
                continue
            body[ln("name")] = name
            binds[ln("property")] = pid
            self.act("create", "fee", label, body, binds)

    # ---- writing ------------------------------------------------------------------
    def apply(self, dry_run):
        ids, new_items = {}, {}
        target_table = {ln("property"): "property", ln("household"): "household"}

        def resolve(col, v):
            if isinstance(v, tuple) and v[0] == "new":
                _, lname, raw = v
                if (lname, raw.lower()) not in new_items:
                    self.log(f"  + list value: {lname} '{raw}'")
                    self.counts["list values added"] += 1
                    made = {} if dry_run else self.dv.call("POST", self.es["listitem"], {
                        ln("name"): raw, ln("list"): self.listvalue[lname.lower()], ln("formanswers"): raw},
                        extra_headers=RETURN)
                    new_items[(lname, raw.lower())] = made.get(ln("listitemid")) or made.get("_id") or "(new)"
                return "listitem", new_items[(lname, raw.lower())]
            if isinstance(v, tuple):
                return v[0], ids.get(v, "(new)")
            return target_table.get(col, "listitem"), v

        marks = {"create": "+", "update": "~", "same": "="}
        for a in self.actions:
            t = table(a["table"])["label"].lower()
            if a["kind"] == "same":
                self.counts["already there"] += 1
                self.log(f"  = {t}: {a['label']} (already there, left alone)")
                continue
            body = dict(a["body"])
            for col, v in a["binds"].items():
                tname, rid = resolve(col, v)
                body[f"{col}@odata.bind"] = f"/{self.es[tname]}({rid})"
            if a["kind"] == "update":
                if not body:
                    self.counts["already there"] += 1
                    self.log(f"  = {t}: {a['label']} (nothing to change)")
                    continue
                self.counts["updated"] += 1
                self.log(f"  ~ {t}: {a['label']} ({len(body)} fields)")
                if not dry_run:
                    self.dv.call("PATCH", f"{self.es[a['table']]}({a['target']})", body)
                continue
            self.counts["created"] += 1
            made = {} if dry_run else self.dv.call("POST", self.es[a["table"]], body, extra_headers=RETURN)
            rid = made.get(ln(a["table"]) + "id") or made.get("_id")
            number = made.get(ln("recordnumber"))
            self.log(f"  {marks['create']} {t}: {a['label']}" + (f"  [{number}]" if number else ""))
            ref = a["ref"]
            if ref and ref[0] == "current":      # a current occupancy: point its property at it
                tname, pid = resolve(ln("property"), ref[1])
                if not dry_run:
                    self.dv.call("PATCH", f"{self.es['property']}({pid})",
                                 {f"{ln('currentoccupancy')}@odata.bind": f"/{self.es['occupancy']}({rid})"})
            elif ref and not dry_run:
                ids[ref] = rid


def run(dv, folder, log=print, dry_run=False, add_list_values=False, data=None):
    data = data if data is not None else read_folder(folder)
    if not data:
        raise DataverseError(f"No import files in '{folder}'. Expected any of: {', '.join(f for f, _ in FILES)}")
    if "householdmember" in data and "household" not in data:
        raise DataverseError("members.csv needs households.csv next to it.")
    imp = Importer(dv, data, log, add_list_values)
    imp.load_environment()
    imp.plan()
    if imp.problems:
        raise DataverseError(f"{len(imp.problems)} problem(s). Nothing was changed.\n  - " + "\n  - ".join(imp.problems))
    log("Dry run: nothing will be changed.\n" if dry_run else "Loading...\n")
    imp.apply(dry_run)
    log(("\nDry run, nothing changed. Would do: " if dry_run else "\nDone. ")
        + ", ".join(f"{v} {k}" for k, v in imp.counts.items()))
    return imp.counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="Folder holding properties.csv, households.csv, members.csv, occupancies.csv, fees.csv")
    ap.add_argument("--url", required=True, help="Environment URL, e.g. https://yourorg.crm.dynamics.com")
    ap.add_argument("--dry-run", action="store_true", help="Report what would change, change nothing")
    ap.add_argument("--add-list-values", action="store_true",
                    help="Add Property type, Tenure type, Neighborhood and Relationship values that aren't in the lists yet")
    ap.add_argument("--tenant", default="organizations")
    ap.add_argument("--client-id", default=DEFAULT_CLIENT_ID)
    ap.add_argument("--device-code", action="store_true")
    args = ap.parse_args()
    dv = Dataverse(args.url, make_token_provider(args.url, args.client_id, args.tenant, args.device_code), SOLUTION)
    try:
        run(dv, args.folder, dry_run=args.dry_run, add_list_values=args.add_list_values)
    except DataverseError as e:
        sys.exit(f"\nSTOPPED: {e}")


if __name__ == "__main__":
    main()
