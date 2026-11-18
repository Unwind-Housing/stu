# Pre-screen plan

Drafted and built 2026-11-14. Implements FUNCTIONAL-SPEC E-4 and E-5 and the E-flow-1 row in `v0.5-plan.md`, as a page (Projects > Pre-screen), not a flow: see "How it's built".

## Where it sits

Screener, add to a project, close applications and Unique IDs, **pre-screen**, lock the lists and draw, invite the top households on each list, full application, certify, offer.

The pre-screen uses only what the screener says (self-reported). It decides who goes into the lottery. Certification checks the same rules again later against verified figures.

## Decided

- **Monthly housing cost comes from the project, by home size** (2026-11-14). It gives the front-end and back-end ratios.
- Rules come from the project; where the project leaves one blank, the organization's rule applies.
- Every test is saved as an Eligibility check (stage Pre-screen) with its value, its limit and how it was worked out.
- **Every home of the same size costs the same in a project**, so the cost is one number per home size on the project: five fields, studio to 4+ bedrooms.
- **Income over the limit but inside the buffer passes, with a note**.
- **A household that fails stays at stage Pre-screened** with result Not eligible, so staff can still override until the lists lock.

## The tests

Monthly income = stated annual income / 12.

| Test | Passes when | Source of the limit |
|---|---|---|
| Income limit | Stated income is no more than the limit for the household size at the project's max % of AMI, plus the income buffer (a percent over the limit; blank is 10, so 80% becomes 88%) | Project max AMI, AMI limits used, income buffer |
| Minimum income | Stated income is at least the project's min % of AMI. Skipped if blank. | Project min AMI |
| Housing ratio (front-end) | Monthly housing cost / monthly income is no more than the housing ratio max plus the housing ratio buffer | Housing ratio max (for example 35%) |
| Total debt ratio (back-end) | (Monthly housing cost + stated monthly debt) / monthly income is no more than the debt ratio max plus the debt ratio buffer | Total debt ratio max (for example 44%), buffer in points |
| Credit | Credit range is at or above the project's minimum. "I don't know" is Needs review. Skipped if blank. | Minimum credit range |
| Bankruptcy | No bankruptcy in the look-back period. Skipped if blank. | Bankruptcy look-back (years) |
| First-time buyer | First-time buyer, or an exception applies, when required | First-time buyer rule |
| Local tie | Lived or worked locally a year, when required. **New test value: add "Local tie" to the Check choice.** | Lives or works locally rule |
| Asset limit | Stated non-retirement assets are within the limit. Skipped if blank. | Asset limit |
| Household size fits | The household's size has a priority row for at least one home size it asked for | Project priorities |
| Primary residence | Will live in the home as a primary residence | Always |

Homebuyer education is a certification test, not a pre-screen test.

### Ratios are per home size

A household asks for one or more home sizes. The two ratio tests run once for each size it asked for that also fits its household size, using that size's monthly cost. One Eligibility check row per size, for example "3 bedrooms: $2,150 / $5,708 = 37.7%, limit 35%".

A household can pass for one size and fail for another. So the pre-screen also records **Home sizes eligible for** on the application (new multi-select field, same choices as Home sizes of interest). The lottery builds one list entry per size from that field.

The ratio tests are skipped when **Check minimum affordability** is off on the project.

### Income bands (added 2026-11-15)

A project can have income bands: bands of buyers by income, each with its own interest rate and, optionally, its own sale prices. Each band holds a monthly housing cost per home size. A project with one band ("All buyers") behaves as before.

- The band is picked from the household's stated % of AMI: the first band whose top it doesn't exceed, or the last band (everyone above).
- The two ratio tests use that band's monthly cost. The check's notes name the band.
- **Near the line:** a household that fails at its band's cost, whose stated income is within the income buffer of the band below (65% with a 10% buffer is 71.5%), and that would pass both ratios at the lower band's cost, is **Needs review**, not Not eligible. Screener income is rough, and certification decides which loan they qualify for.
- No % of AMI worked out: tested at the highest band; if that fails and the lowest band would pass, Needs review.

## The result

- Any test fails for every size asked for, or a non-ratio test fails: **Not eligible**, with the reasons in Pre-screen notes.
- An answer a test needs is missing or can't be matched: **Needs review**.
- Otherwise: **Eligible for selection**.

Stage moves from Screener submitted to **Pre-screened**. It never moves a stage backwards.

A staff override (for example Needs review to Eligible): staff change the result, tick **Pre-screen overridden**, and write who, when and why in Pre-screen notes. A later run then leaves that application alone.

## When it runs

Staff run it: **Projects > Pre-screen**, pick the project, look at the results, **Save results**. It can be run again any time; each save replaces that application's earlier Pre-screen checks. Applications with **Pre-screen overridden** ticked are left alone, and so are ones past the pre-screen that already have a saved result.

It doesn't run by itself when a screener arrives. A CLT that pre-screens after applications close wants a button. A rolling first come, first served list would want it automatic: that would be a small flow later.

## How it's built

- `webresources/prescreen.js`: the rules as one plain function, `CLTPrescreen.run(app, rules, priorities)`. No Dataverse calls, so `tests/test_prescreen.py` runs it in Node on worked examples.
- `webresources/prescreen.html`: loads the project, the organization's rules, the priorities and the applications; calls the function; shows the results; saves on request.
- Schema: "Local tie" on the Check choice; **Home sizes eligible for**, **Pre-screened on** and **Pre-screen overridden** on Application; five **Monthly housing cost** fields on Project.

Why a page and not a flow: the rules are arithmetic with a lot of branches. In a flow they can't be run offline, and every fix means a redeploy as the service account. As plain JavaScript they're tested on real numbers before they reach an environment, and staff see every result before anything is saved.

## Not done yet

- The **+ New** button is still on the application's Pre-screen checks list (roadmap request 19).
- Overrides aren't closed automatically when the lists lock, because the lock isn't built.
- No automatic run when a screener arrives.
