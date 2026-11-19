"""Offline test: tools/make_test_data.py (the made-up portfolio loads cleanly) and tools/reset_records.py
(clears records in an order the links allow, keeps the setup, deletes nothing unless told to)."""
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import date
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_schema as b  # noqa: E402
import import_records as ir  # noqa: E402
import make_test_data as mk  # noqa: E402
import reset_records as rr  # noqa: E402
import start_from_scratch as sfs  # noqa: E402
import test_import as ti  # noqa: E402
from schema import LOOKUPS, TABLES  # noqa: E402
from test_offline import Resp  # noqa: E402


class FakeEnv:
    """Rows per table. A delete is refused, as Dataverse would, while a row that must go first still points at it."""
    def __init__(self):
        self.rows = {t["name"]: {} for t in TABLES}
        self.deleted = []

    def add(self, table, **links):
        rid = str(uuid.uuid4())
        self.rows[table][rid] = links
        return rid

    def request(self, method, url, headers=None, data=None, timeout=None):
        path = unquote(url.split("/api/data/v9.2/", 1)[1])
        m = re.fullmatch(r"EntityDefinitions\(LogicalName='clt_(\w+)'\)\?\$select=EntitySetName", path)
        if m:
            return Resp(200, {"EntitySetName": f"clt_{m[1]}s"})
        m = re.fullmatch(r"clt_(\w+)s\?\$select=clt_\w+id", path)
        if m and method == "GET":
            return Resp(200, {"value": [{f"clt_{m[1]}id": rid} for rid in self.rows[m[1]]]})
        m = re.fullmatch(r"clt_(\w+)s\(([\w-]+)\)", path)
        if m and method == "DELETE":
            table, rid = m[1], m[2]
            for child, col, parent, _, behavior in (l[:5] for l in LOOKUPS):
                if parent != table:
                    continue
                for cid, row in list(self.rows[child].items()):
                    if row.get(col) != rid:
                        continue
                    if behavior == "Restrict":
                        return Resp(400, {"error": {"message": f"{table} is still used by a {child}"}})
                    if behavior == "Cascade":
                        del self.rows[child][cid]
                    else:
                        row[col] = None
            del self.rows[table][rid]
            self.deleted.append(table)
            return Resp(204)
        raise AssertionError(f"unexpected {method} {path}")


def check(out, ok, label):
    out.append(("PASS " if ok else "FAIL ") + label)
    return ok


def main():
    out = []

    # ---- the made-up portfolio ----------------------------------------------------------
    files = mk.build(date(2026, 11, 18))
    rows = {k: [dict(zip(h, r)) for r in v] for k, (h, v) in files.items()}
    props, occs = rows["properties.csv"], rows["occupancies.csv"]
    current = [o for o in occs if o["Status"] == "Current"]
    check(out, len(props) == 20, "20 homes")
    check(out, sum(p["Status"] == "Owner-occupied" for p in props) == 10 and len(current) == 10, "10 of them occupied")
    check(out, all(p["Bedrooms"] and p["Square feet"] for p in props), "every one has a home on it")
    first = {}
    for o in occs:
        first.setdefault(o["Property ref"], o["Start date"])
    check(out, all(str(p["Year built"]) < first[p["Property ref"]] for p in props if p["Property ref"] in first),
          "no home was sold before it was built")
    resold = {o["Property ref"] for o in occs if o["Status"] == "Past"}
    check(out, len(resold) == 5 and len(occs) == 19, "5 occupied homes have earlier owners (9 past occupancies)")
    chains_ok = all(a["End date"] == b_["Start date"] and float(b_["Base price"]) > float(a["Base price"])
                    for a, b_ in zip(occs, occs[1:]) if a["Property ref"] == b_["Property ref"])
    check(out, chains_ok, "each resale starts the day the last owner left, at a higher price")
    check(out, all(o["End date"] < "2026-11-18" for o in occs if o["Status"] == "Past"), "no sale is in the future")
    check(out, {o["Resale formula"] for o in current} == {"Fixed annual rate", "Appraisal share"}, "both resale formulas")
    never = sum(not o["Last occupancy verification"] for o in current)
    check(out, 0 < never < 10, "verification dates are a mix, some never done")
    people = rows["members.csv"]
    check(out, all(m["Last name"].endswith("-Test") for m in people)
          and all(h["Primary email"].endswith("@example.com") for h in rows["households.csv"]),
          "every person is marked as a test (last name -Test, email at example.com)")

    with tempfile.TemporaryDirectory() as tmp:
        mk.write(tmp, date(2026, 11, 18))
        fake, _, _ = ti.environment()
        dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "CLTStewardship", session=fake)
        counts = ir.run(dv, tmp, log=lambda s: None, add_list_values=True)
        made = {k: len(v) for k, v in fake.rows.items() if k != "listitem"}
        check(out, made == {"property": 20, "household": 19, "householdmember": len(people), "occupancy": 19, "fee": 20},
              f"the import tool loads it: {made}")
        linked = sum(1 for p in fake.rows["property"].values() if p.get("_clt_currentoccupancy_value"))
        check(out, linked == 10, "the 10 occupied homes point at their current occupancy")
        again = ir.run(dv, tmp, log=lambda s: None, add_list_values=True)
        check(out, again["created"] == 0, "loading it twice adds nothing")

    # ---- the made-up history, on top of the loaded portfolio ---------------------------------
    hist = mk.history(date(2026, 11, 18))
    extra = sorted({r["table"] for r in hist})
    ti.SETS.update({f"clt_{t}s": t for t in extra})
    with tempfile.TemporaryDirectory() as tmp:
        mk.write(tmp, date(2026, 11, 18))
        fake, _, _ = ti.environment()
        fake.rows.update({t: {} for t in extra})
        dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", "CLTStewardship", session=fake)
        ir.run(dv, tmp, log=lambda s: None, add_list_values=True)
        made = sfs.load_history(dv, date(2026, 11, 18), log=lambda s: None)
        check(out, made == {t: sum(r["table"] == t for r in hist) for t in extra}, f"the history loads: {made}")
        sales = list(fake.rows["sale"].values())
        resales = [x for x in sales if x.get("_clt_selleroccupancy_value")]
        check(out, len(sales) == 19 and len(resales) == 9, "a closed sale for each of the 10 first purchases and 9 resales")
        occ = fake.rows["occupancy"]
        good = all(occ[x["_clt_selleroccupancy_value"]]["clt_enddate"] == x["clt_closingdate"]
                   == occ[x["_clt_buyeroccupancy_value"]]["clt_startdate"]
                   and x["clt_purchaseprice"] == occ[x["_clt_buyeroccupancy_value"]]["clt_baseprice"]
                   and x["_clt_buyerhousehold_value"] == occ[x["_clt_buyeroccupancy_value"]]["_clt_household_value"]
                   for x in resales)
        check(out, good, "each resale links the seller's and buyer's occupancies, on the closing date, at the buyer's base price")
        cur = {p["_clt_currentoccupancy_value"] for p in fake.rows["property"].values() if p.get("_clt_currentoccupancy_value")}
        kids = [x for t in extra if t not in ("sale", "errrtransaction") for x in fake.rows[t].values()]
        check(out, all(x["_clt_occupancy_value"] in cur for x in kids), "everything else sits on a current occupancy")
        ver = {x["_clt_occupancy_value"]: x["clt_receiveddate"] for x in fake.rows["annualverification"].values()}
        check(out, all(occ[o].get("clt_lastoccupancyverified") == d for o, d in ver.items()) and len(ver) == 8,
              "past verifications match the occupancies' last verification dates")
        draw = next(x for x in fake.rows["errrtransaction"].values() if x.get("_clt_homeownerrequest_value"))
        check(out, fake.rows["homeownerrequest"][draw["_clt_homeownerrequest_value"]]["clt_name"] == "Water heater",
              "the repair draw is linked to its request")
        again = sfs.load_history(dv, date(2026, 11, 18), log=lambda s: None)
        check(out, again == {}, "adding the history twice adds nothing")

    # ---- old SharePoint folders ----------------------------------------------------------------
    class FakeSite:
        def __init__(self):
            self.folders = {"/sites/S/clt_property/DEV": ["12 Pine St - P-00001", "O'Brien Rd - P-00002"],
                            "/sites/S/clt_household/DEV": ["Rivera - H-00001"], "/sites/S/clt_property": ["DEV", "Forms"]}
            self.recycled = []

        def request(self, method, url, headers=None, data=None, timeout=None):
            path = unquote(url.split("/_api/", 1)[1])
            m = re.fullmatch(r"web/GetFolderByServerRelativeUrl\('(.+?)'\)/Folders\?\$select=Name,ServerRelativeUrl", path)
            if m and method == "GET":
                if m[1] not in self.folders:
                    return Resp(404, {})
                return Resp(200, {"value": [{"Name": n, "ServerRelativeUrl": f"{m[1]}/{n}"} for n in self.folders[m[1]]]})
            m = re.fullmatch(r"web/GetFolderByServerRelativeUrl\('(.+)'\)/recycle\(\)", path)
            if m and method == "POST":
                self.recycled.append(m[1].replace("''", "'"))
                return Resp(200, {"value": "x"})
            raise AssertionError(f"unexpected {method} {path}")

    site = FakeSite()
    sp = b.SharePoint("https://x.sharepoint.com/sites/S", lambda: "t", session=site)
    n = sfs.clear_folders(sp, "DEV", delete=False, log=lambda s: None)
    check(out, n == 3 and not site.recycled, "old record folders: counted, not touched, without the go-ahead")
    sfs.clear_folders(sp, "DEV", delete=True, log=lambda s: None)
    check(out, sorted(site.recycled) == ["/sites/S/clt_household/DEV/Rivera - H-00001",
                                         "/sites/S/clt_property/DEV/12 Pine St - P-00001",
                                         "/sites/S/clt_property/DEV/O'Brien Rd - P-00002"],
          "only the folders inside the environment's parent folder go to the recycle bin")

    # ---- the reset --------------------------------------------------------------------------
    def env():
        f = FakeEnv()
        item = f.add("listitem")
        proj = f.add("project")
        f.add("projectband", project=proj)
        f.add("sourceform", project=proj)
        p = f.add("property", state=item)
        h = f.add("household")
        f.add("householdmember", household=h)
        o = f.add("occupancy", property=p, household=h)
        f.rows["property"][p]["currentoccupancy"] = o
        v = f.add("annualverification", occupancy=o)
        f.add("insuranceverification", occupancy=o, annualverification=v)
        req = f.add("homeownerrequest", occupancy=o, property=p)
        f.add("errrtransaction", property=p, occupancy=o, homeownerrequest=req)
        f.add("sale", property=p, selleroccupancy=o, buyerhousehold=h)
        f.add("fee", property=p)
        f.add("projecthome", project=proj, property=p)
        a = f.add("application", household=h, project=proj)
        f.add("incomesource", application=a)
        c = f.add("certification", household=h, application=a)
        f.add("checklistitem", certification=c)
        rnd = f.add("selectionround", project=proj)
        f.add("selectionentry", round=rnd, application=a)
        f.add("formsubmission", household=h, application=a)
        return f

    def left(f):
        return sorted(k for k, v in f.rows.items() if v)

    f = env()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", None, session=f)
    counted = rr.run(dv, log=lambda s: None)
    check(out, not f.deleted and sum(counted.values()) == 18, "without --delete it only counts (18 records)")
    rr.run(dv, delete=True, log=lambda s: None)
    check(out, left(f) == ["listitem", "project", "projectband", "sourceform"],
          f"a reset clears the records and keeps the setup: {left(f)}")
    f = env()
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", None, session=f)
    rr.run(dv, delete=True, with_projects=True, log=lambda s: None)
    check(out, left(f) == ["listitem", "sourceform"], "--with-projects takes the projects too")
    class NoEntry:
        def request(self, method, url, headers=None, data=None, timeout=None):
            return Resp(401, {"error": "invalid_request"})

    f, said = env(), []
    dv = b.Dataverse("https://fake.crm.dynamics.com", lambda: "t", None, session=f)
    sfs.run(dv, b.SharePoint("https://x.sharepoint.com/sites/S", lambda: "t", session=NoEntry()), "DEV", delete=True,
            log=said.append)
    check(out, left(f) == ["listitem", "sourceform"] and "by hand" in said[0] and "run this again" in said[-1].replace("\n", " "),
          "when SharePoint can't be reached: the records are cleared, it says to empty the folders by hand, and it loads nothing")
    names = {t["name"] for t in TABLES}
    check(out, set(rr.SETUP + rr.PROJECT_SETUP) <= names, "every table the reset keeps is a real table")

    print("\n".join(out))
    if any(line.startswith("FAIL") for line in out):
        sys.exit(1)
    print(f"\nAll {len(out)} checks passed.")


if __name__ == "__main__":
    main()
