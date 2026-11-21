#!/usr/bin/env python3
"""
Write a small made-up portfolio as import files, for testing: 20 homes, every person and address invented.

  - 10 occupied homes. Homes 1 to 5 have been resold along the way (1 to 3 earlier owners each, 9 in all).
    Homes 9 and 10 use the Appraisal share formula; the rest use Fixed annual rate.
  - 10 homes with nobody in them: 4 vacant, 4 for sale, 2 under construction.
  - 19 households (10 homeowners, 9 past homeowners), every last name ending in -Test, every email at example.com.
    With --email you@gmail.com each household gets that address with a dot in a different place (y.ou@, yo.u@):
    Gmail delivers them all to the one inbox, so the emails Stu prepares can really be received.
  - The 10 current occupancies have verification dates set from today, so the Verification hub shows a mix:
    up to date, due soon, overdue and never done.
  - A ground lease fee and an ERRR fee on each occupied home.

  - history() adds what the five files can't carry (tools/start_from_scratch.py loads it): a closed sale for every
    purchase and resale, insurance policies (two under-insured, two renewing soon, two homes with none), loans,
    improvements, homeowner requests, follow-ups (one overdue), notes, ERRR entries and past verifications.

No applicants: those come in through the screener form.

Usage:
  python3 tools/make_test_data.py                      writes export/test-data
  python3 tools/make_test_data.py some/folder --today 2026-11-18 --email you@gmail.com
Then load it with tools/import_records.py (see docs/PLAYBOOK.md, "Start from scratch and load test homes").
"""
import argparse
import csv
import os
from datetime import date, timedelta

P = ["Property ref", "Record number", "Street address", "Unit", "City", "State", "County", "ZIP code", "Parcel number",
     "Property type", "Tenure type", "Neighborhood", "Status", "Bedrooms", "Bathrooms", "Square feet", "Year built",
     "AMI target (%)", "Acquisition date", "Replacement cost", "Replacement cost as of", "Notes"]
H = ["Household ref", "Status", "Primary email", "Phone", "Mailing street address", "Mailing unit", "Mailing city",
     "Mailing state", "Mailing ZIP code", "Notes"]
M = ["Household ref", "First name", "Last name", "Applicant role", "Relationship to primary applicant", "Date of birth",
     "Email", "Phone", "On title"]
O = ["Property ref", "Household ref", "Role", "Status", "Start date", "End date", "Lease or covenant recording number",
     "Agreement version", "Resale formula", "Base price", "Base date", "Annual rate (%)", "Count whole years only",
     "Appraisal at purchase", "Latest appraisal", "Latest appraisal date", "Owner share (%)",
     "Last occupancy verification", "Last insurance verification", "Notes"]
F = ["Property ref", "Fee type", "Monthly amount", "Effective start", "Effective end", "Notes"]

CITY, STATE, COUNTY, ZIP = "Cedar Landing", "WA", "Jefferson County", "98399"
FIRST = ["Ana", "Ben", "Cora", "Dev", "Elena", "Finn", "Grace", "Hugo", "Iris", "Jonah", "Kira", "Leo", "Mina", "Noah",
         "Opal", "Pablo", "Quinn", "Rosa", "Sam"]
LAST = ["Abbott", "Barros", "Calloway", "Dalton", "Eastman", "Farrow", "Gallo", "Hartley", "Ingram", "Jacobs", "Keller",
        "Lindqvist", "Marsh", "Novak", "Okafor", "Pruitt", "Quigley", "Ramos", "Sorensen"]
PARTNER = ["Alex", "Blake", "Casey", "Drew", "Emery"]
RESALES = {1: 2, 2: 1, 3: 3, 4: 1, 5: 2}              # home -> how many times it has been resold
# current occupancy -> days since the last (occupancy, insurance) verification; None = never done
VERIFIED = {1: (30, 30), 2: (200, 200), 3: (355, 355), 4: (362, 90), 5: (400, 400), 6: (500, 100), 7: (None, None),
            8: (None, 360), 9: (100, 380), 10: (340, 20)}
EMPTY = {11: "Vacant", 12: "Vacant", 13: "Vacant", 14: "Vacant", 15: "For sale", 16: "For sale", 17: "For sale",
         18: "For sale", 19: "Under construction", 20: "Under construction"}
TOWNHOMES = [7, 8, 9, 10, 15, 16, 17, 18]             # 40 Harbor Row, Units 1 to 8; the rest are houses on Maple Ct


def address(email, n, fallback):
    """The nth household's address: the test inbox with a dot in the nth place (a +n tag once the places run out)."""
    if not email:
        return fallback
    local, domain = email.strip().rsplit("@", 1)
    gaps = [i for i in range(1, len(local)) if "." not in local[i - 1:i + 1]]
    return (f"{local[:gaps[n - 1]]}.{local[gaps[n - 1]:]}" if n <= len(gaps) else f"{local}+{n}") + "@" + domain


def build(today, email=None):
    props, hhs, mems, occs, fees = [], [], [], [], []
    ago = lambda days: "" if days is None else (today - timedelta(days=days)).isoformat()   # noqa: E731
    people = iter(zip(FIRST, LAST))
    for i in range(1, 21):
        town = i in TOWNHOMES
        street, unit = ("40 Harbor Row", str(TOWNHOMES.index(i) + 1)) if town else (f"{99 + 2 * i} Maple Ct", "")
        beds = 2 + i % 3
        built = "" if EMPTY.get(i) == "Under construction" else 2024 if i in EMPTY else 2007 if i in RESALES else 2018
        props.append([f"P{i}", "", street, unit, CITY, STATE, COUNTY, ZIP, f"TEST-{9000 + i}",
                      "Townhome" if town else "Single-family detached", "Ground lease",
                      "Harbor Row (test)" if town else "Maple Court (test)", EMPTY.get(i, "Owner-occupied"), beds,
                      1 if beds == 2 else 1.5 if beds == 3 else 2, 780 + 190 * beds + 11 * i, built,
                      (60, 80, 80, 120)[i % 4], f"{(built or 2026) - 1}-06-01", 240000 + 9000 * i, f"{today.year - 1}-01-15",
                      "Made-up test home."])
        if i in EMPTY:
            continue
        owners = RESALES.get(i, 0) + 1
        start = date(2008 + i % 4, 1 + i, 15) if i in RESALES else date(2013 + i, 2 + i % 9, 10)
        price, appraisal = 148000 + 6500 * i, i in (9, 10)
        for n in range(owners):
            current = n == owners - 1
            years = 3 + (i + n) % 3
            end = None if current else date(start.year + years, 1 + (start.month + 4) % 12, 20)
            first, last = next(people)
            ref, phone = f"H{len(hhs) + 1}", f"(360) 555-01{len(hhs) + 10}"
            mail = address(email, len(hhs) + 1, f"{first}.{last}-test@example.com".lower())
            hhs.append([ref, "Homeowner" if current else "Past homeowner", mail, phone] + (
                [street, unit, CITY, STATE, ZIP] if current else ["", "", "", "", ""]) + ["Made-up test household."])
            mems.append([ref, first, f"{last}-Test", "Primary applicant", "", "", mail, phone, "Yes"])
            if current and i % 2 == 0:
                mems.append([ref, PARTNER[i // 2 - 1], f"{last}-Test", "Co-applicant", "Spouse or partner", "", "", "", "Yes"])
            if current and i % 3 == 0:
                mems.append([ref, "Robin", f"{last}-Test", "Other household member", "Child",
                             f"{today.year - 4 - i}-03-0{i}", "", "", "No"])
            occ_days, ins_days = VERIFIED[i] if current else (None, None)
            occs.append([f"P{i}", ref, "Owner", "Current" if current else "Past", start.isoformat(),
                         end.isoformat() if end else "", f"TEST-{start.year}-{1000 + i * 10 + n}", "Test ground lease",
                         "Appraisal share" if appraisal else "Fixed annual rate", price, start.isoformat(),
                         "" if appraisal else 1.5, "No", price + 60000 if appraisal else "",
                         price + 60000 + 14000 * i if appraisal else "", f"{today.year - 1}-09-01" if appraisal else "",
                         25 if appraisal else "", ago(occ_days), ago(ins_days),
                         "Made-up test occupancy." + ("" if current else " Sold to the next owner.")])
            if end:   # the next owner buys at the fixed rate price on the day of the sale
                price = round(price * (1 + 0.015 * (end - start).days / 365.25))
                start = end
        first_start = next(o[4] for o in occs if o[0] == f"P{i}")
        fees.append([f"P{i}", "Ground lease fee", 50, first_start, "", ""])
        fees.append([f"P{i}", "ERRR", 40 + i, first_start, "", ""])
    return {"properties.csv": (P, props), "households.csv": (H, hhs), "members.csv": (M, mems),
            "occupancies.csv": (O, occs), "fees.csv": (F, fees)}


def history(today):
    """The made-up history that hangs off the homes, as rows for tools/start_from_scratch.py to create:
    {table, place (the property's name), name, values {column label: value}, links {lookup: which}}.
    A link is True (the home), a number (that owner in the home's chain, 0 = first; for a household, that owner's
    household) or the name of a homeowner request made earlier for the same home."""
    files = build(today)
    rows = lambda k: [dict(zip(files[k][0], r)) for r in files[k][1]]   # noqa: E731
    props = {p["Property ref"]: p for p in rows("properties.csv")}
    last = {m["Household ref"]: m["Last name"] for m in rows("members.csv") if m["Applicant role"] == "Primary applicant"}
    chains = {}
    for o in rows("occupancies.csv"):
        chains.setdefault(int(o["Property ref"][1:]), []).append(o)
    ago = lambda days: (today - timedelta(days=days)).isoformat()       # noqa: E731
    shift = lambda iso, days: (date.fromisoformat(iso) + timedelta(days=days)).isoformat()   # noqa: E731
    out = []

    for i, chain in sorted(chains.items()):
        p = props[f"P{i}"]
        place = p["Street address"] + (f", Unit {p['Unit']}" if p["Unit"] else "")
        cur = len(chain) - 1
        who = f"{last[chain[cur]['Household ref']]} - {place}"
        cost = p["Replacement cost"]

        def add(table, name, values, **links):
            out.append({"table": table, "place": place, "name": name, "values": values, "links": links})

        # every purchase is a closed sale: the first one, then each resale at the formula price
        for n, o in enumerate(chain):
            day, common = o["Start date"], {"Status": "Closed", "Lender": "Test Credit Union",
                                            "Title or escrow company": "Test Title & Escrow", "Notes": "Made-up test sale."}
            if n == 0:
                add("sale", f"{place} initial sale {day[:4]}", {
                    "Sale type": "Initial sale", "Purchase and sale agreement signed": shift(day, -45), "Closing date": day,
                    "Purchase price": o["Base price"], **common}, property=True, buyerhousehold=0, buyeroccupancy=0)
            else:
                add("sale", f"{place} resale {day[:4]}", {
                    "Sale type": "Resale", "Notice of intent to sell": shift(day, -120), "Purchase and sale agreement signed": shift(day, -45),
                    "Closing date": day, "Formula price at sale": o["Base price"], "Added value at sale": 0,
                    "Maximum resale price at sale": o["Base price"], "Purchase price": o["Base price"], **common},
                    property=True, selleroccupancy=n - 1, buyerhousehold=n, buyeroccupancy=n)

        occ_days, ins_days = VERIFIED[i]
        if occ_days is not None:
            add("annualverification", f"{ago(occ_days)[:4]}, {place}", {
                "Year": int(ago(occ_days)[:4]), "Status": "Approved", "How": "Paper" if i % 2 else "Online form",
                "Sent date": ago(occ_days + 14), "Received date": ago(occ_days), "Signed on": ago(occ_days),
                "Primary residence confirmed": "Yes", "Rental status": "Not renting", "People living in the home": 1 + i % 4,
                "Notes": "Made-up test verification."}, occupancy=cur)
        if i <= 8:   # homes 9 and 10 have no policy on file
            under = i in (4, 5)
            add("insurancepolicy", f"Test Mutual {today.year}-{str(today.year + 1)[2:]}", {
                "Carrier": "Test Mutual", "Policy number": f"TEST-HO-{5000 + i}", "Dwelling coverage (A)": round(cost * (0.7 if under else 1)),
                "Extended dwelling (%)": 0 if under else 25, "Liability coverage": 300000, "Deductible": 2500 if i % 2 else 1000,
                "Annual premium": 900 + 35 * i, "Effective date": ago(365 - (12 if i == 3 else 25 if i == 6 else 40 * i)),
                "Renewal date": ago(-(12 if i == 3 else 25 if i == 6 else 40 * i)), "CLT listed as additional insured": "No" if i == 5 else "Yes",
                "Verified date": "" if ins_days is None else ago(ins_days), "Replacement cost": cost,
                "Notes": "Made-up test policy."}, occupancy=cur)
        if ins_days is not None:
            add("insuranceverification", f"{ago(ins_days)}, {who}", {
                "Started": ago(ins_days + 10), "Status": "Approved", "How": "Paper", "Sent date": ago(ins_days + 10),
                "Reviewed on": ago(ins_days), "Replacement coverage limit": round(cost * (0.7 if i in (4, 5) else 1.25)),
                "Notes": "Made-up test insurance verification."}, occupancy=cur)

        # the ERRR: an opening balance two years ago and the last six months' contributions
        add("errrtransaction", f"Opening balance {ago(730)[:7]}", {"Date": ago(730), "Type": "Opening balance",
                                                                 "Amount": 1500 + 100 * i}, property=True, occupancy=cur)
        month = today.replace(day=1)
        for _ in range(6):
            add("errrtransaction", f"Contribution {month.isoformat()[:7]}", {
                "Date": month.isoformat(), "Type": "Contribution", "Amount": 40 + i}, property=True, occupancy=cur)
            month = (month - timedelta(days=1)).replace(day=1)

        note = lambda days, how, text: add("relationshipnote", f"{ago(days)}, {who}", {   # noqa: E731
            "Date": ago(days), "How": how, "Notes": text}, occupancy=cur)
        todo = lambda name, days, done=None: add("followup", name, {                      # noqa: E731
            "Due date": ago(days), "Status": "Done" if done else "Open", "Done on": ago(done) if done else ""}, occupancy=cur, property=True)
        walk = lambda days, text: add("walkby", f"{ago(days)}, {place}", {                # noqa: E731
            "Date": ago(days), "Status": "Submitted", "Notes": text}, property=True, occupancy=cur)
        if i in (1, 2, 4):   # two walked within the year (green on the Stu in the wild page), one longer ago (red again)
            walk({1: 40, 2: 200, 4: 420}[i], "Made-up test walk-by: yard tidy, nothing to follow up.")
        if i == 1:
            add("homeownerrequest", "Roof replacement", {
                "Request type": "Capital improvement", "Request date": ago(1170), "Status": "Completed",
                "Details": "Made-up test request: replace the roof.", "Decision date": ago(1150), "Estimated cost": 19000,
                "Approved resale credit": 18000, "Completed date": ago(1095)}, occupancy=cur, property=True)
            add("improvementcredit", "New roof", {"Original value": 18000, "Value as of": ago(1095),
                                                  "Depreciation period (years)": 20}, occupancy=cur, homeownerrequest="Roof replacement")
            todo("Check the roof warranty was filed", 320, done=300)
            note(45, "Phone", "Made-up test note: called to say hello, all well.")
        if i == 2:
            add("loan", "Down payment loan", {"Status": "Active", "Starting balance": 15000, "Interest rate (%)": 0,
                                              "Start date": chain[cur]["Start date"]}, occupancy=cur)
            add("homeownerrequest", "Refinance with Test Credit Union", {
                "Request type": "Refinance", "Request date": ago(12), "Status": "Under review",
                "Details": "Made-up test request: refinance to a lower rate."}, occupancy=cur, property=True)
            todo("Call about the refinance paperwork", -5)
            note(12, "Email", "Made-up test note: asked about refinancing.")
        if i == 3:
            add("improvementcredit", "Kitchen remodel", {"Original value": 12000, "Value as of": ago(1100),
                                                         "Depreciation period (years)": 10}, occupancy=cur)
            add("improvementcredit", "Heat pump", {"Original value": 9000, "Value as of": ago(365),
                                                   "Depreciation period (years)": 15}, occupancy=cur)
        if i == 4:
            add("loan", "Down payment loan", {"Status": "Paid off", "Starting balance": 10000, "Interest rate (%)": 0,
                                              "Start date": chain[cur]["Start date"], "End date": ago(900)}, occupancy=cur)
            todo("Ask for the insurance declarations page", -20)
            note(150, "In person", "Made-up test note: stopped by at the block party.")
        if i == 5:
            add("homeownerrequest", "Water heater", {
                "Request type": "ERRR repair draw", "Request date": ago(40), "Status": "Approved",
                "Details": "Made-up test request: the water heater failed.", "Decision date": ago(35),
                "Estimated cost": 1500, "Approved ERRR draw": 1400}, occupancy=cur, property=True)
            add("errrtransaction", f"Repair draw {ago(30)[:7]}", {"Date": ago(30), "Type": "Repair draw", "Amount": 1400,
                                                               "Notes": "Water heater."},
                property=True, occupancy=cur, homeownerrequest="Water heater")
            todo("Confirm the water heater is installed", 4)
            note(40, "Phone", "Made-up test note: water heater failed, sent the request form.")
        if i == 6:
            add("loan", "Roof repair loan", {"Status": "Active", "Starting balance": 12000, "Interest rate (%)": 1.5,
                                             "Start date": ago(700), "End date": ago(700 - 3650), "Regular payment": 107.75},
                occupancy=cur)
            note(400, "Mail", "Made-up test note: sent the annual letter.")
        if i == 7:
            add("homeownerrequest", "Rent a room", {
                "Request type": "Rent or sublet", "Request date": ago(3), "Status": "Submitted",
                "Details": "Made-up test request: rent a room to a relative."}, occupancy=cur, property=True)
            todo("Send a verification reminder", 0)
        if i == 8:
            add("improvementcredit", "Fence", {"Original value": 4000, "Value as of": ago(2200),
                                               "Depreciation period (years)": 5}, occupancy=cur)
        if i == 9:
            add("homeownerrequest", "Deck", {
                "Request type": "Capital improvement", "Request date": ago(200), "Status": "Denied",
                "Details": "Made-up test request: add a deck.", "Decision date": ago(180), "Estimated cost": 8000},
                occupancy=cur, property=True)
            note(90, "Text", "Made-up test note: asked about the deck decision.")
    return out


def write(folder, today=None, email=None):
    files = build(today or date.today(), email)
    os.makedirs(folder, exist_ok=True)
    for name, (head, rows) in files.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(head)
            w.writerows(rows)
    return {name: len(rows) for name, (_, rows) in files.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default=os.path.join("export", "test-data"))
    ap.add_argument("--today", help="Work the verification dates out from this day (YYYY-MM-DD) instead of today")
    ap.add_argument("--email", help="A test inbox (Gmail): every household gets it with a dot in a different place")
    args = ap.parse_args()
    counts = write(args.folder, date.fromisoformat(args.today) if args.today else None, args.email)
    print(f"Wrote {args.folder}: " + ", ".join(f"{n} {k[:-4]}" for k, n in counts.items()))


if __name__ == "__main__":
    main()
