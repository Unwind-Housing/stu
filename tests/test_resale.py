"""Offline test: the Resale page's rules (webresources/resale.js) and the loan sums (webresources/loan.js) run in Node
on worked examples, and the page is checked against the schema. Skipped with a message if Node isn't installed."""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
const assert = require("assert"); const path = require("path");
const R = require(process.argv[process.argv.length - 1]);
const L = require(path.join(path.dirname(process.argv[process.argv.length - 1]), "loan.js"));
const today = "2026-11-17";

// ---- loans: months, the regular payment, and what is still owed
assert.strictEqual(L.monthsBetween("2026-01-15", "2026-03-14"), 1); assert.strictEqual(L.monthsBetween("2026-01-15", "2026-03-15"), 2);
assert.strictEqual(L.monthsBetween("2026-03-15", "2026-01-15"), 0); assert.strictEqual(L.monthsBetween("", "2026-01-15"), 0);
assert.strictEqual(L.payment(10000, 0, "2024-01-01", "2029-01-01"), 166.67, "no interest: the balance split over 60 months");
assert.strictEqual(L.payment(20000, 3, "2020-06-01", "2030-06-01"), 193.12, "$20,000 at 3% over 10 years");
assert.strictEqual(L.payment(20000, "", "2020-06-01", "2030-06-01"), 166.67, "a blank rate is no interest");
assert.strictEqual(L.payment(0, 3, "2020-06-01", "2030-06-01"), null); assert.strictEqual(L.payment(20000, 3, "2020-06-01", ""), null);
assert.strictEqual(L.payment(20000, 3, "2020-06-01", "2020-06-20"), null, "less than a month");
assert.strictEqual(L.owed({ balance: 10000, rate: 0, start: "2024-01-01", payment: 166.67 }, "2025-01-01"), 7999.96, "12 payments made");
assert.strictEqual(L.owed({ balance: 10000, rate: 0, start: "2024-01-01", payment: 166.67 }, "2023-06-01"), 10000, "before it starts");
assert.strictEqual(L.owed({ balance: 10000, rate: 0, start: "2024-01-01", payment: 166.67 }, "2040-01-01"), 0, "never below zero");
assert.strictEqual(L.owed({ balance: 5000, rate: 0, start: "2020-01-01", payment: 0 }, today), 5000, "a deferred loan with no interest stays level");
assert.strictEqual(L.owed({ balance: 10000, rate: 12, start: "2025-11-17", payment: null }, today), 11268.25, "a deferred loan grows with its interest, added monthly");
const paid = L.owed({ balance: 20000, rate: 3, start: "2020-06-01", payment: 193.12 }, "2030-06-01");
assert.ok(paid < 1, "a loan paid on schedule is paid off at its end date (to within rounding): " + paid);
assert.strictEqual(L.owed({ rate: 3 }, today), null);

// ---- the loans on an occupancy at a resale: paid-off ones are left out
const owed = R.loansOwed([{ name: "Down payment loan", balance: 5000, rate: 0, start: "2020-01-01", payment: 0, status: "Active" },
                          { name: "Repair loan", balance: 10000, rate: 0, start: "2024-01-01", payment: 166.67, status: "Active" },
                          { name: "Old loan", balance: 3000, rate: 0, start: "2015-01-01", payment: 0, status: "Paid off" }], "2025-01-01");
assert.deepStrictEqual(owed, { lines: [{ name: "Down payment loan", owed: 5000 }, { name: "Repair loan", owed: 7999.96 }], total: 12999.96 });
assert.deepStrictEqual(R.loansOwed([], today), { lines: [], total: 0 });

// ---- capital improvements approved for the occupancy flow into the added value
assert.deepStrictEqual(R.improvements([{ name: "New roof", type: "Capital improvement", status: "Completed", credit: 6000 }, { name: "Heat pump", type: "Capital improvement", status: "Approved", credit: "2,500" },
  { name: "Deck", type: "Capital improvement", status: "Denied", credit: 4000 }, { name: "Fence", type: "Capital improvement", status: "Under review", credit: 900 },
  { name: "Gutter repair", type: "ERRR repair draw", status: "Completed", credit: 300 }, { name: "Paint", type: "Capital improvement", status: "Approved", credit: 0 }]),
  { lines: [{ name: "New roof", credit: 6000 }, { name: "Heat pump", credit: 2500 }], total: 8500 }, "only approved capital improvements with a credit");
assert.deepStrictEqual(R.improvements([]), { lines: [], total: 0 });
// ---- improvement credits lose value evenly over their depreciation period, and are what the resale adds
assert.strictEqual(R.creditValue({ original: 10000, date: "2021-11-18", years: 10 }, "2026-11-18"), 5000.68, "half way through ten years (by the day)");
assert.strictEqual(R.creditValue({ original: 10000, date: "2016-01-01", years: 10 }, "2026-11-18"), 0, "fully depreciated");
assert.strictEqual(R.creditValue({ original: 10000, date: "2027-01-01", years: 10 }, "2026-11-18"), 10000, "never more than the original");
assert.strictEqual(R.creditValue({ original: 8000, date: "2020-05-01", years: "" }, "2026-11-18"), 8000, "no period: it keeps its value");
assert.strictEqual(R.creditValue({ original: 8000, date: "", years: 5 }, "2026-11-18"), 8000);
assert.strictEqual(R.creditsTotal([], "2026-11-18"), null); assert.strictEqual(R.creditsTotal([{ original: 10000, date: "2021-11-18", years: 10 }, { original: 2000 }], "2026-11-18"), 7000.68);
const both = R.improvements([{ id: "r1", name: "New roof", type: "Capital improvement", status: "Completed", credit: 6000 }, { id: "r2", name: "Heat pump", type: "Capital improvement", status: "Approved", credit: 2500 }],
                            [{ name: "New roof", original: 6000, date: "2023-11-18", years: 20, request: "r1" }, { name: "Deck", original: 3000 }], "2026-11-18");
assert.deepStrictEqual(both.lines.map(l => [l.name, l.credit]), [["New roof", 5099.79], ["Deck", 3000], ["Heat pump", 2500]], "the list at today's value; a request already on the list isn't counted twice");
assert.strictEqual(both.total, 10599.79);

// ---- the project set up to find the buyer, found by the home, and who it has certified
const buyers = [{ id: "h2" }, { id: "h3" }, { id: "h4" }];
let g = R.buyerGroups([{ id: "j2", name: "12 Pine St resale", status: "Selection" }, { id: "j1", name: "Old round", status: "Closed" }],
                      [{ household: "h3", project: "j2" }, { household: "h4", project: "j1" }, { household: "h9", project: "j2" }], buyers);
assert.strictEqual(g.project.id, "j2", "the newest project that isn't closed"); assert.deepStrictEqual([g.fromProject.map(b => b.id), g.others.map(b => b.id)], [["h3"], ["h2", "h4"]]);
g = R.buyerGroups([], [], buyers); assert.deepStrictEqual([g.project, g.fromProject, g.others.length], [null, [], 3]);
assert.strictEqual(R.buyerGroups([{ id: "j1", name: "Old round", status: "Closed" }], [], buyers).project.id, "j1", "a closed project is still shown when it is the only one");

// ---- the Price step: maximum resale price, and what the seller is left with
assert.deepStrictEqual(R.figures({ formula: "212,400", addedValue: "8500", loans: "12999.96", credits: "350", debits: "1,200" }),
                       { maxPrice: 220900, basis: 220900, recapture: 0, net: 207050.04 }, "before a contract, the maximum resale price stands in for the price");
assert.deepStrictEqual(R.figures({ formula: 212400, addedValue: 8500, loans: 12999.96, credits: 350, debits: 1200, price: 218000 }),
                       { maxPrice: 220900, basis: 218000, recapture: 0, net: 204150.04 }, "with a contract, the purchase price is used");
// a price above the maximum is allowed: the seller's side stops at the maximum and the organization recaptures the rest
assert.deepStrictEqual(R.figures({ formula: 212400, addedValue: 8500, loans: 12999.96, credits: 350, debits: 1200, price: 240000 }),
                       { maxPrice: 220900, basis: 220900, recapture: 19100, net: 207050.04 });
assert.deepStrictEqual(R.figures({ formula: 220900, price: "240,000" }).recapture, 19100); assert.strictEqual(R.figures({ formula: 220900, price: 220900 }).recapture, 0);
assert.deepStrictEqual(R.figures({ formula: 200000 }), { maxPrice: 200000, basis: 200000, recapture: 0, net: 200000 }, "blank lines count as 0");
assert.deepStrictEqual(R.figures({ formula: "", addedValue: 5000 }), { maxPrice: null, basis: null, recapture: 0, net: null }, "no formula price, no maximum");

// ---- what stops each step
assert.deepStrictEqual(R.check("start", { occupancy: "o1", noticeDate: today }, today), []);
assert.strictEqual(R.check("start", { occupancy: "", noticeDate: "" }, today).length, 2); assert.ok(R.check("start", { occupancy: "o1", noticeDate: "2026-11-18" }, today)[0].includes("future"));
assert.deepStrictEqual(R.check("price", { formula: "212400", addedValue: "", loans: "", credits: "", debits: "" }, today), []);
assert.ok(R.check("price", { formula: "" }, today)[0].includes("formula price")); assert.ok(R.check("price", { formula: "abc" }, today)[0].includes("number"));
assert.ok(R.check("price", { formula: 1, loans: -5 }, today)[0].includes("loans owed"));
assert.ok(R.check("price", { formula: 1, credits: 350, creditsNote: " " }, today)[0].includes("credits")); assert.deepStrictEqual(R.check("price", { formula: 1, credits: 350, creditsNote: "Tax proration" }, today), []);
assert.ok(R.check("price", { formula: 1, debits: 10 }, today)[0].includes("debits"));
assert.ok(R.check("buyer", { household: "" }, today)[0].includes("buyer")); assert.ok(R.check("buyer", { household: "h1", sameAsSeller: true }, today)[0].includes("selling"));
assert.deepStrictEqual(R.check("buyer", { household: "h2" }, today), []);
assert.ok(R.warnings("buyer", { household: "h2", certificationExpires: "2026-10-01" }, today)[0].includes("expired")); assert.deepStrictEqual(R.warnings("buyer", { household: "h2" }, today), [], "certified with no expiry date: the certification doesn't run out, so nothing to warn about");
assert.deepStrictEqual(R.warnings("buyer", { household: "h2", certificationExpires: "2027-03-01" }, today), []);
assert.deepStrictEqual(R.check("contract", { price: "218,000", maxPrice: 220900, contractDate: today }, today), []);
assert.deepStrictEqual(R.check("contract", { price: "220900", maxPrice: 220900, contractDate: today }, today), [], "at the maximum is fine");
assert.deepStrictEqual(R.check("contract", { price: "240000", maxPrice: 220900, contractDate: today }, today), [], "above the maximum is allowed");
assert.ok(R.warnings("contract", { price: "240000", maxPrice: 220900 }, today)[0].includes("$19,100 above the maximum resale price") && R.warnings("contract", { price: "240000", maxPrice: 220900 }, today)[0].includes("recaptured"));
assert.deepStrictEqual(R.warnings("contract", { price: 220900, maxPrice: 220900 }, today), []);
assert.strictEqual(R.check("contract", { price: "", maxPrice: 220900, contractDate: "" }, today).length, 2);
assert.ok(R.warnings("contract", { price: 218000, maxPrice: 220900 }, today)[0].includes("below"));
assert.deepStrictEqual(R.check("closing", { closingDate: today, contractDate: "2026-10-01" }, today), []);
assert.ok(R.check("closing", { closingDate: "2026-09-30", contractDate: "2026-10-01" }, today)[0].includes("before the purchase and sale agreement"));
assert.ok(R.check("closing", { closingDate: "2026-12-01", contractDate: "2026-10-01" }, today)[0].includes("future")); assert.ok(R.check("closing", { closingDate: "" }, today)[0].includes("closing date"));

// ---- where a resale stands
assert.deepStrictEqual(R.progress(null).next, "start");
assert.strictEqual(R.progress({ noticeDate: today, status: "Pending" }).next, "price");
assert.strictEqual(R.progress({ maxPrice: 220900, status: "Pending" }).next, "offer"); assert.strictEqual(R.progress({ maxPrice: 0, status: "Pending" }).next, "offer", "a price of 0 is still a price");
assert.strictEqual(R.progress({ maxPrice: 220900, offered: true, status: "Pending" }).next, "buyer", "an offer is out: the next thing is the household's answer");
assert.deepStrictEqual([R.progress({ maxPrice: 1, buyer: "h2", status: "Pending" }).done.offer, R.progress({ maxPrice: 1, buyer: "h2", status: "Pending" }).done.buyer], [true, true],
                       "a sale with a buyer has been through both steps, including one from before offers were kept");
assert.strictEqual(R.progress({ maxPrice: 220900, buyer: "h2", status: "Pending" }).next, "contract");
assert.strictEqual(R.progress({ maxPrice: 220900, buyer: "h2", contractDate: today, price: 218000, status: "Pending" }).next, "closing");
const end = R.progress({ maxPrice: 220900, buyer: "h2", contractDate: today, price: 218000, status: "Closed" });
assert.ok(end.closed && end.next === "" && !end.cancelled); assert.ok(R.progress({ status: "Cancelled" }).cancelled);
assert.deepStrictEqual(R.STEPS.map(s => s.key), ["start", "price", "offer", "buyer", "contract", "closing"]);
assert.deepStrictEqual(R.STEPS.map(s => s.title).slice(2, 5), ["Offer the home", "The household's answer", "Purchase and sale agreement"]);

// ---- offering the home: one household at a time, 7 days to answer unless the project says otherwise
assert.strictEqual(R.offerDue("2026-11-19"), "2026-11-26"); assert.strictEqual(R.offerDue("2026-11-19", 10), "2026-11-29"); assert.strictEqual(R.offerDue("2026-12-28", ""), "2027-01-04");
assert.strictEqual(R.offerDue("2026-11-19", 0), "2026-11-26", "0 or nonsense falls back to 7"); assert.strictEqual(R.OFFER_DAYS, 7);
assert.deepStrictEqual(R.check("offer", { household: "h2", due: "2026-11-26" }, today), []);
assert.ok(R.check("offer", { household: "", due: "2026-11-26" }, today)[0].includes("Choose the household")); assert.ok(R.check("offer", { household: "h1", sameAsSeller: true, due: "2026-11-26" }, today)[0].includes("selling"));
assert.ok(R.check("offer", { household: "h2", due: "" }, today)[0].includes("answer by")); assert.ok(R.check("offer", { household: "h2", due: "2026-01-01" }, today)[0].includes("past"));
assert.ok(R.warnings("offer", { household: "h4", ahead: "Rivera (rank 1, tier 1)" }, today)[0].startsWith("Rivera"), "the list order warning applies to an offer");
assert.deepStrictEqual(R.check("answer", { answer: "Accepted", date: today }, today), []); assert.deepStrictEqual(R.check("answer", { answer: "No response", date: today }, today), []);
assert.ok(R.check("answer", { answer: "", date: today }, today)[0].includes("what the household said")); assert.ok(R.check("answer", { answer: "Declined", date: "" }, today)[0].includes("date"));
assert.ok(R.check("answer", { answer: "Declined", date: "2099-01-01" }, today)[0].includes("future"));
assert.deepStrictEqual(R.ANSWERS, ["Accepted", "Declined", "No response"]);
// where a sale's offers stand: one open at most; the ones who said no, or nothing, are out
const os = R.offers([{ id: "o1", household: "h2", status: "Declined", offeredOn: "2026-11-01", respondedOn: "2026-11-05", reason: "Bought elsewhere" },
                     { id: "o2", household: "h1", status: "No response", offeredOn: "2026-11-06" }, { id: "o3", household: "h4", status: "Offered", offeredOn: "2026-11-14", due: "2026-11-21" },
                     { id: "o4", household: "h9", status: "Withdrawn", offeredOn: "2026-11-13" }]);
assert.deepStrictEqual([os.open.id, os.accepted, os.past.map(o => o.id), Object.keys(os.out).sort()], ["o3", null, ["o2", "o1"], ["h1", "h2"]], "a withdrawn offer isn't a no");
assert.deepStrictEqual(R.offers([]), { open: null, accepted: null, past: [], out: {} });
assert.strictEqual(R.offers([{ id: "o5", household: "h4", status: "Accepted", offeredOn: "2026-11-14" }]).accepted.id, "o5");
assert.strictEqual(R.nextToOffer([{ id: "h2" }, { id: "h1" }, { id: "h4" }], os.out).id, "h4", "the first in list order that hasn't said no");
assert.strictEqual(R.nextToOffer([{ id: "h2" }], os.out), null); assert.strictEqual(R.nextToOffer([], {}), null);
assert.strictEqual(R.offerName("Rivera, Maria", "12 Pine St"), "Rivera, 12 Pine St");
// a household's place on the project's lists follows its offer; it declines once for the whole project
assert.deepStrictEqual(["Offered", "Accepted", "Declined", "No response", "Withdrawn"].map(R.entryStatus), ["Offered", "Accepted", "Declined", "Unresponsive", "Approved"]);
// the email and the flyer
const om = R.offerEmail({ email: "maria@example.com", firstName: "Maria", household: "Rivera", home: "12 Pine St", price: 227160.94, due: "2026-11-26", organization: "Pine Valley CLT" });
assert.deepStrictEqual([om.to, om.subject], ["maria@example.com", "A home for you: 12 Pine St"]);
assert.ok(om.body.startsWith("Hello Maria,") && om.body.includes("The sale price is $227,160.94.") && om.body.includes("by November 26, 2026") && om.body.endsWith("Thank you,\nPine Valley CLT"));
assert.ok(!/[{}]/.test(om.body), "every field is filled in");
assert.ok(R.offerEmail({ household: "Rivera", home: "12 Pine St", price: 250000, due: "2026-11-26", organization: "X" }).body.includes("Hello Rivera,") , "no first name on file: the household's name");
assert.ok(R.offerEmail({ household: "Rivera", home: "12 Pine St", price: 250000, due: "2026-11-26", organization: "X" }).body.includes("$250,000."), "a whole-dollar price has no cents");
assert.strictEqual(R.offerEmail({ household: "Rivera", home: "12 Pine St", due: "2026-11-26" }, { subject: "", body: "Dear {Household}, by {respond  by}." }).body, "Dear Rivera, by November 26, 2026.");
const fl = R.flyer({ home: "12 Pine St", address: "12 Pine St, Port Townsend, 98368", bedrooms: 2, bathrooms: 1.5, squareFeet: 1040, yearBuilt: 2019, price: 227000, due: "2026-11-26",
                     organization: "Pine Valley CLT", monthly: { principalInterest: 1100, taxes: 150, hoa: 0, leaseFee: 50 } });
assert.strictEqual(fl.title, "12 Pine St"); const text = JSON.stringify(fl.blocks);
for (const piece of ["12 Pine St, Port Townsend, 98368", "2 bedrooms, 1.5 bathrooms, 1,040 square feet, built 2019.", "Sale price: $227,000", "Principal and interest", "$1,100", "Ground lease fee",
                     "Estimated monthly housing cost", "$1,300", "Let us know by November 26, 2026", "Pine Valley CLT"]) assert.ok(text.includes(piece), piece);
assert.ok(!text.includes("HOA dues"), "a cost of 0 is left off");
assert.ok(!JSON.stringify(R.flyer({ home: "4 Oak Ave", price: 200000 }).blocks).includes("each month"), "no monthly costs known: no table");
assert.strictEqual(JSON.stringify(R.flyer({ home: "1 Elm", bedrooms: 0 }).blocks).includes("Studio"), true);

// ---- names, the buyer's terms, and the closing
assert.strictEqual(R.saleName("12 Pine St", "2026-11-17"), "12 Pine St resale 2026"); assert.strictEqual(R.occupancyName("Okafor, Ada", "12 Pine St"), "Okafor - 12 Pine St");
const seller = { clt_occupancyid: "o1", clt_resaleformula: 768270000, clt_annualrate: 1.5, clt_wholeyearsonly: false, clt_ownershare: null, clt_floorbaseprice: true, clt_pricecap: null,
                 clt_roundto: 100, clt_agreementversion: "2019 lease", clt_baseprice: 180000, clt_basedate: "2019-05-01", clt_improvementcredits: 8500, clt_notes: "seller's notes" };
assert.deepStrictEqual(R.newTerms(seller, 218000, "2026-11-17", 310000), { clt_resaleformula: 768270000, clt_annualrate: 1.5, clt_wholeyearsonly: false, clt_floorbaseprice: true, clt_roundto: 100,
  clt_agreementversion: "2019 lease", clt_baseprice: 218000, clt_basedate: "2026-11-17", clt_appraisalatpurchase: 310000 }, "the formula and limits carry over; the price, date and credits start again");
const d = { saleId: "s1", closingDate: "2026-11-17", price: 218000, appraised: null, seller, sellerHouseholdId: "h1", sellerHasOtherHome: false, buyerHouseholdId: "h2", buyerHouseholdName: "Okafor, Ada",
  propertyId: "p1", propertyName: "12 Pine St", sets: { clt_sale: "clt_sales", clt_occupancy: "clt_occupancies", clt_property: "clt_properties", clt_household: "clt_households" },
  values: { current: 1, past: 2, owner: 10, closed: 21, homeowner: 33, pastHomeowner: 35, ownerOccupied: 45 } };
const ops = R.closing(d);
assert.deepStrictEqual(ops.map(o => o.method + " " + o.path), ["POST clt_occupancies", "PATCH clt_sales(s1)", "PATCH clt_occupancies(o1)", "PATCH clt_properties(p1)", "PATCH clt_households(h2)", "PATCH clt_households(h1)"]);
assert.deepStrictEqual(ops[0].body, { clt_resaleformula: 768270000, clt_annualrate: 1.5, clt_wholeyearsonly: false, clt_floorbaseprice: true, clt_roundto: 100, clt_agreementversion: "2019 lease",
  clt_baseprice: 218000, clt_basedate: "2026-11-17", clt_name: "Okafor - 12 Pine St", clt_role: 10, clt_status: 1, clt_startdate: "2026-11-17",
  "clt_property@odata.bind": "/clt_properties(p1)", "clt_household@odata.bind": "/clt_households(h2)" });
assert.deepStrictEqual(ops[1].body, { clt_status: 21, clt_closingdate: "2026-11-17", "clt_buyeroccupancy@odata.bind": "$1" }, "the sale points at the occupancy the first change made");
assert.deepStrictEqual(ops[2].body, { clt_status: 2, clt_enddate: "2026-11-17" }); assert.deepStrictEqual(ops[3].body, { clt_status: 45, "clt_currentoccupancy@odata.bind": "$1" });
assert.deepStrictEqual(ops[4].body, { clt_status: 33 }); assert.deepStrictEqual(ops[5].body, { clt_status: 35 });
assert.strictEqual(R.closing({ ...d, sellerHasOtherHome: true }).length, 5, "a seller who owns another home here stays a homeowner");

// ---- how the purchase price is made up
const typed = [{ type: "Loan", amount: "$180,000", rate: "6.5", notes: "Test Credit Union first mortgage" }, { type: "Buyer cash", amount: "20,000.00", rate: "9", notes: "" },
               { type: "Subsidy", amount: "18000", rate: "", notes: "Down payment assistance" }, { type: "", amount: "", rate: "", notes: " " }];
assert.deepStrictEqual(R.fundingLines(typed), [{ id: "", type: "Loan", amount: 180000, rate: 6.5, notes: "Test Credit Union first mortgage" }, { id: "", type: "Buyer cash", amount: 20000, rate: null, notes: "" },
                                               { id: "", type: "Subsidy", amount: 18000, rate: null, notes: "Down payment assistance" }], "a blank line is dropped; a rate is kept only for a loan");
assert.strictEqual(R.fundingTotal(typed), 218000); assert.deepStrictEqual(R.fundingProblems(typed), []); assert.deepStrictEqual(R.fundingWarnings(typed, "$218,000.00"), []);
assert.ok(R.fundingProblems([{ type: "Loan", amount: "100", rate: "" }])[0].includes("interest rate"), "a loan needs its interest rate");
assert.deepStrictEqual(R.fundingProblems([{ type: "Loan", amount: "100", rate: "0" }]), [], "0 is a rate: a loan with no interest");
assert.ok(R.fundingProblems([{ type: "Loan", amount: "100", rate: "lots" }])[0].includes("0 to 100")); assert.deepStrictEqual(R.fundingProblems([{ type: "Subsidy", amount: "100", rate: "" }]), []);
assert.ok(R.fundingProblems([{ type: "", amount: "100" }])[0].includes("choose the type")); assert.ok(R.fundingProblems([{ type: "Other", amount: "" }])[0].includes("enter the amount"));
assert.ok(R.fundingProblems([{ type: "Other", amount: "0" }])[0].includes("above 0")); assert.deepStrictEqual(R.fundingProblems([]), []);
assert.deepStrictEqual(R.fundingWarnings(typed, 220000), ["The funding adds up to $218,000.00, $2,000.00 less than the purchase price."]);
assert.ok(R.fundingWarnings(typed, 210000)[0].includes("$8,000.00 more")); assert.deepStrictEqual(R.fundingWarnings([], 210000), [], "no lines yet is fine");
assert.strictEqual(R.fundingName({ type: "Loan", notes: "Test Credit Union first mortgage" }), "Loan, Test Credit Union first mortgage"); assert.strictEqual(R.fundingName({ type: "Buyer cash", notes: "" }), "Buyer cash");
assert.strictEqual(R.fundingSummary(typed), "Loan $180,000.00 at 6.5%, Buyer cash $20,000.00, Subsidy $18,000.00");
// ---- the closing: closing costs are optional, and the settlement statement is a PDF or a photo
assert.deepStrictEqual(R.check("closing", { closingDate: today, contractDate: "2026-10-01", closingCosts: "" }, today), []); assert.deepStrictEqual(R.check("closing", { closingDate: today, closingCosts: "$4,250.10" }, today), []);
assert.ok(R.check("closing", { closingDate: today, closingCosts: "some" }, today)[0].includes("closing costs"));
assert.strictEqual(R.statementProblem(null), ""); assert.strictEqual(R.statementProblem({ name: "Final ALTA.pdf", size: 400000 }), "");
assert.ok(R.statementProblem({ name: "statement.docx", size: 10 }).includes("PDF")); assert.ok(R.statementProblem({ name: "scan.PNG", size: 30 * 1024 * 1024 }).includes("25 MB"));
// ---- the buyer step shows each of the project's certified households with its priority on the project's list
const list = [{ household: "h1", bedrooms: 2, tier: 1, rank: 3, status: "Approved" }, { household: "h2", bedrooms: 2, tier: 1, rank: 1, status: "Approved" },
              { household: "h2", bedrooms: 3, tier: 2, rank: 1 }, { household: "h3", bedrooms: 3, tier: 1, rank: 2 }, { household: "h4", bedrooms: 2, tier: 2, rank: 1 },
              { household: "h5", bedrooms: 2, tier: 1, rank: null }, { household: "", bedrooms: 2, tier: 1, rank: 9 }];
const prio = R.priorities(list, 2);
assert.deepStrictEqual(Object.keys(prio).sort(), ["h1", "h2", "h3", "h4"], "an entry with no rank (not drawn yet) gives no priority");
assert.deepStrictEqual([prio.h2.rank, prio.h2.tier, prio.h2.thisSize], [1, 1, true], "its place on this home's list, not its place on another size's");
assert.strictEqual(R.priorityText(prio.h2), "rank 1, tier 1"); assert.strictEqual(R.priorityText(prio.h3), "rank 2, tier 1 on the 3 bedroom list"); assert.strictEqual(R.priorityText(undefined), "not on the list");
const cert = [{ id: "h1", clt_name: "Chen" }, { id: "h9", clt_name: "Nobody" }, { id: "h4", clt_name: "Lee" }, { id: "h3", clt_name: "Okafor" }, { id: "h2", clt_name: "Rivera" }];
assert.deepStrictEqual(R.byPriority(cert, prio).map(b => b.id), ["h2", "h1", "h4", "h3", "h9"], "this home's list by tier then rank, then other lists, then anyone not on a list");
assert.strictEqual(R.ahead("h2", R.byPriority(cert, prio), prio), null, "the first on the list has nobody ahead");
assert.strictEqual(R.ahead("h4", R.byPriority(cert, prio), prio).clt_name, "Rivera");
assert.strictEqual(R.ahead("h2", R.byPriority(cert, {}), {}), null, "no lists: nobody is ahead of anybody"); assert.strictEqual(R.ahead("zz", R.byPriority(cert, prio), prio), null);
const prio2 = R.priorities(list.map(e => e.household === "h2" ? { ...e, status: "Declined" } : e), 2);
assert.strictEqual(R.ahead("h4", R.byPriority(cert, prio2), prio2).clt_name, "Chen", "a household that declined isn't ahead of anyone: the next one is named");
assert.strictEqual(R.ahead("h1", R.byPriority(cert, prio2), prio2), null);
assert.deepStrictEqual(R.priorities([], 2), {}); assert.strictEqual(R.priorities([{ household: "h1", bedrooms: 2, rank: 1 }], null).h1.thisSize, false);
assert.ok(R.warnings("buyer", { household: "h4", ahead: "Rivera (rank 1, tier 1)" }, today)[0].startsWith("Rivera (rank 1, tier 1) comes before this household"));
assert.deepStrictEqual(R.warnings("buyer", { household: "h2", ahead: "" }, today), []);

// ---- the page's opening list: every sale in progress with the step it waits on; another kind of sale opens as its own record
assert.deepStrictEqual(R.pending([{ id: "a", resale: true, noticeDate: "2026-10-01", status: "Pending" }, { id: "b", resale: true, noticeDate: "2026-10-01", maxPrice: 250000, buyer: "h1", status: "Pending" },
                                  { id: "c", resale: false }]).map(r => [r.id, r.resale, r.next]),
                       [["a", true, "Price and what the seller owes"], ["b", true, "Purchase and sale agreement"], ["c", false, "Open the sale to carry on"]]);
assert.deepStrictEqual(R.pending([]), []);
process.stdout.write(JSON.stringify({ offer: R.OFFER_DEFAULT, copied: R.COPIED, funding: R.FUNDING_TYPES }));
"""


def main():
    node = shutil.which("node")
    if not node:
        print("SKIPPED: Node isn't installed, so the Resale rules weren't run. Install Node to run this test.")
        return
    web = os.path.join(HERE, "..", "webresources")
    r = subprocess.run([node, "-e", JS, os.path.join(web, "resale.js")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Resale rules failed:\n" + r.stdout + r.stderr)
    out = json.loads(r.stdout.strip().splitlines()[-1])

    import app_spec as core
    import app_spec_stu as stu
    from schema import TABLES, LOOKUPS, CHOICES
    PREFIX = "clt"
    tables = {t["name"]: t for t in TABLES}
    cols = {t: {c["name"]: c for c in tables[t]["columns"]} for t in tables}
    rules = open(os.path.join(web, "resale.js")).read()
    loan = open(os.path.join(web, "loan.js")).read()
    page = open(os.path.join(web, "resale.html")).read()
    # how the purchase price is made up: the types are the choice's, and the lines, closing costs and statement have a home
    assert out["funding"] == CHOICES["purchasefundingtype"][1] and ("salefunding", "sale", "sale", "Sale", "Cascade", True) in LOOKUPS
    assert {"type", "amount", "interestrate", "notes"} <= set(cols["salefunding"]) and cols["sale"]["settlementstatement"]["kind"] == "file" and cols["sale"]["closingcosts"]["kind"] == "money"
    for piece in ('id="f-rows"', 'id="f-add"', "R.fundingProblems(", "R.fundingWarnings(", 'box("x-costs"', 'id="x-file"', 'id="addstatement"', "Purchase and sale agreement signed", "dollars(", "sale price to the selling homeowner"):
        assert piece in page, piece
    assert page.index("return P.batch(R.closing({") < page.index("clt_closingcosts: n(input.closingCosts)"), "the closing's own changes stay first: the new occupancy is referred to by its place in the list"
    # the terms copied to the buyer are real occupancy columns, and none of them is a price, a date or a credit
    for c in out["copied"]:
        assert c[len(PREFIX) + 1:] in cols["occupancy"], c
    assert not {"clt_baseprice", "clt_basedate", "clt_improvementcredits", "clt_latestappraisal"} & set(out["copied"])
    # a loan: on an occupancy, with the fields the sums and the form script use
    assert {"status", "startingbalance", "interestrate", "startdate", "enddate", "payment"} <= set(cols["loan"])
    assert ("loan", "occupancy", "occupancy") in {(c, n, p) for c, n, p, *_ in LOOKUPS} and "solution" not in tables["loan"]
    assert "Paid off" in CHOICES["loanstatus"][1] and '"Paid off"' in rules
    assert all(f"clt_{c}" in loan for c in ("startingbalance", "interestrate", "startdate", "enddate", "payment"))
    assert core.SCRIPT_LIBRARIES["CLT.Loans"] == "clt_/pages/loan.js" and all(h[2] == "CLT.Loans.fill" for h in core.FORM_SCRIPTS["loan"])
    assert "loan" in str(core.FORMS["occupancy"]) and "loan" in core.FORMS
    # the sale keeps the figures from the Price step
    for c in ("noticedate", "subsidyrecapture", "formulapriceatsale", "creditsatsale", "maxpriceatsale", "appraisedvalue", "loanpayoff", "othercredits", "othercreditsnote", "otherdebits", "otherdebitsnote"):
        assert c in cols["sale"] and f"clt_{c}" in page and c in str(core.FORMS["sale"]), c
    # in the app: the page under Activities, loans under Portfolio, in the core app and Stu
    assert core.PAGES["resale"] == ("Resale", "clt_/pages/resale.html") and "page:resale" in dict(core.NAVIGATION)["Activities"] and "loan" in dict(core.NAVIGATION)["Portfolio"]
    for res in ("clt_/pages/resale.html", "clt_/pages/resale.js", "clt_/pages/loan.js"):
        assert res in core.WEB_RESOURCES and res in stu.WEB_RESOURCES, res
    assert page.index('src="pages.js"') < page.index('src="loan.js"') < page.index('src="resale.js"') < page.index("CLTResale")
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    for src in (script, rules, loan):
        p = subprocess.run([node, "-e", "new Function('require', require('fs').readFileSync(0, 'utf8'))"], input=src, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr[-600:]
    # every clt_ name is real
    used_tables = ("sale", "occupancy", "property", "household", "loan", "homeownerrequest", "project", "projecthome", "certification", "improvementcredit", "salefunding", "selectionround", "selectionentry", "application", "saleoffer", "householdmember", "messagetemplate")
    known = {f"{PREFIX}_name"} | {f"{PREFIX}_{c}" for c in ("saletype", "salestatus", "occupancystatus", "occupancyrole", "householdstatus", "propertystatus", "purchasefundingtype", "settlementstatement_name", "offerstatus", "entrystatus", "applicantrole", "noticetype")}
    for t in used_tables:
        known |= {f"{PREFIX}_{c}" for c in cols[t]} | {f"{PREFIX}_{t}", f"{PREFIX}_{t}id"}
    known |= {f"{PREFIX}_{col}" for child, col, *_ in LOOKUPS if child in used_tables}
    used = (set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", script)) | set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", rules)) | set(re.findall(rf"\b{PREFIX}_[a-z0-9_]+", loan))) - {f"{PREFIX}_"}
    assert used <= known, sorted(used - known)
    for name, labels in (("saletype", ["Resale"]), ("salestatus", ["Pending", "Closed", "Cancelled"]), ("occupancystatus", ["Current", "Past"]), ("occupancyrole", ["Owner"]),
                         ("householdstatus", ["Eligible", "Homeowner", "Past homeowner"]), ("propertystatus", ["Sale pending", "Owner-occupied"]),
                         ("requesttype", ["Capital improvement"]), ("requeststatus", ["Approved", "Approved with conditions", "Completed"]), ("certificationstatus", ["Certified"]),
                         ("projectstatus", ["Closed"])):
        for label in labels:
            assert label in CHOICES[name][1] and label in script + rules, (name, label)
    # opens on the sales in progress; the Dashboard's Pending sales tile comes here; What for sits beside its amount;
    # a project started from a resale gets the home and its maximum resale price
    for piece in ("R.priorities(", "R.byPriority(", "R.priorityText(", "R.ahead(", "clt_rank", 'id="landing"', 'id="pending"', "R.pending(", "data-pick=", "data-record=", 'class="whatfor"', '"&price=" + D.sale.clt_maxpriceatsale'):
        assert piece in page, piece
    # the home is offered to one household at a time: an offer record, an email to copy, a flyer to attach, then their answer
    from schema import CHOICES as CH, SEED_ROWS, TABLES as TB
    assert CH["offerstatus"][1] == ["Offered", "Accepted", "Declined", "No response", "Withdrawn"] and "Offer" in CH["noticetype"][1]
    assert {"Offered", "Accepted", "Declined", "Unresponsive", "Approved"} <= set(CH["entrystatus"][1])
    assert ("saleoffer", "sale", "sale", "Sale", "Cascade", True) in LOOKUPS and ("saleoffer", "household", "household", "Household", "Restrict", True) in LOOKUPS
    assert "saleoffer" in core.FORMS and "saleoffer" in str(core.FORMS["sale"]) and "offerdays" in {c["name"] for c in {t["name"]: t for t in TB}["project"]["columns"]}
    start = [t for t in SEED_ROWS["messagetemplate"] if t["noticetype"] == "Offer"]
    mail = json.loads(r.stdout.strip().splitlines()[-1])["offer"]
    assert len(start) == 1 and start[0]["subject"] == mail["subject"] and start[0]["body"] == mail["body"], "the seeded offer email and the page's fallback say the same thing"
    for piece in ('R.check("offer"', 'R.check("answer"', "R.offers(", "R.nextToOffer(", "R.offerEmail(", "R.flyer(", "CLTPdf.make(", "entryOps(", 'id="o-mail"', 'id="o-flyer"', 'id="m-sent"',
                  'id="a-answer"', 'id="b-due"', "clt_buyerhousehold/$ref", "R.offerDue(today(), D.offerDays)"):
        assert piece in page, piece
    assert page.index('src="resale.js"') < page.index('src="pdf.js"') and "sendEmail" not in page
    # opened from a project's workflow page on its sale; starts a project in the same window, which remembers the sale; leads back
    for piece in ("sale=([0-9a-f-]+)", "project=([0-9a-f-]+)", "loadSales(wantSale)", '"&sale=" + D.sale.clt_saleid', 'id="overview"', 'id="b-workflow"', 'webresourceName: "clt_/pages/project.html"'):
        assert piece in page, piece
    assert "window.open(url" not in page and 'body["clt_sale@odata.bind"]' in open(os.path.join(web, "newproject.html")).read()
    assert "pending.length === 1" not in page and 'line("What for"' not in page
    dash = open(os.path.join(web, "overview.html")).read()
    assert 'page: "clt_/pages/resale.html"' in dash and "if (cfg.page) CLTPage.go(" in dash
    new = open(os.path.join(web, "newproject.html")).read()
    assert "price=([0-9.]+)" in new and "c.price = resale.price" in new
    assert "—" not in page and "—" not in rules and "—" not in loan
    assert 'id="regular"' in open(os.path.join(web, "guides.html")).read() and "Resale" in open(os.path.join(web, "guides.html")).read()
    print("OK: loan payments and balances, the resale price figures, each step's checks and the closing's changes match the worked examples; "
          "the page is in the app and uses only real columns and choices.")


if __name__ == "__main__":
    main()
