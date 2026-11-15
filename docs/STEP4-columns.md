# Step 4: rollup columns (by hand)

**Formula columns are now built by `build_schema.py`** from `fx(...)` columns in `schema.py` (since 2026-11-10: the Web API accepts Power Fx formulas). That covers Raw formula price, Formula price, Maximum resale price, Age, Is adult, Annualized income, Total dwelling coverage, Coverage check, Coverage gap, Signed amount, Difference and Stated income (% of AMI). To change one, edit its formula in `schema.py` and run the schema build; it updates the formula in place.

What's left by hand: the **rollup** columns, and the two formulas that add them up (a formula can only be built once the rollups it reads exist).

Create these in **Solutions → CLT Stewardship → Tables → (table) → Columns → + New column**.

- Open **Advanced options** and type the **schema name** shown here (Power Apps adds the `clt_` prefix). The app build looks for these names to place the columns on forms and views.
- If the editor rejects a currency column inside a formula, wrap it like this: `Decimal('Base price')`.

After adding columns, run `build_app.py` again to put them on the forms and views.

## Property

| Display name | Schema name | Type |
|---|---|---|
| ERRR increases | errrincreases | Rollup |
| ERRR decreases | errrdecreases | Rollup |
| ERRR balance | errrbalance | Formula |

**ERRR increases** (rollup)

- Related table: ERRR transactions (Property)
- Filter: Type equals Opening balance, Contribution, Adjustment increase
- Aggregation: Sum of Amount

**ERRR decreases** (rollup)

- Related table: same
- Filter: Type equals Returned contribution, Repair draw, Adjustment decrease
- Aggregation: Sum of Amount

**ERRR balance**

```
If(IsBlank('ERRR increases'), 0, 'ERRR increases') - If(IsBlank('ERRR decreases'), 0, 'ERRR decreases')
```

## Application

| Display name | Schema name | Type |
|---|---|---|
| Verified annual income | verifiedannualincome | Rollup |
| Verified assets | verifiedassets | Rollup |
| Verified monthly debt | verifiedmonthlydebt | Rollup |
| Income as % of AMI | incomepctami | Formula |

**Verified annual income** (rollup)

- Related table: Income sources (Application)
- Filter: Review status equals Accepted, Adjusted
- Aggregation: Sum of Verified annual amount

**Verified assets** (rollup)

- Related table: Assets (Application)
- Filter: Review status equals Accepted, Adjusted
- Aggregation: Sum of Verified value

**Verified monthly debt** (rollup)

- Related table: Debts (Application)
- Filter: Review status equals Accepted, Adjusted
- Aggregation: Sum of Verified monthly payment

**Income as % of AMI**

```
If(IsBlank('100% AMI for household size') || IsBlank('Verified annual income'), Blank(),
   Round('Verified annual income' / '100% AMI for household size' * 100, 1))
```

## How rollups update

Rollups recalculate on a schedule, about every hour. To update one immediately, click the refresh icon next to its value on the form.
