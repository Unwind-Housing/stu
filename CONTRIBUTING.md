# Contributing to Stu

Stu is run by more than one community land trust. The aim is that every CLT can pull new versions safely, and that an improvement made at one CLT reaches the others.

## How changes flow

1. **Fork** this repository (or clone it, if you are a maintainer) and install from your copy.
2. Make a change on a **branch based on `main`**.
3. Run the checks and tests (below). They run offline, with no Dataverse environment.
4. Try it in a **Dev or sandbox environment**, not production.
5. Open a **pull request** to `main` here. The same tests run automatically. Say what the change is for and how you tried it.
6. Once it's merged, other CLTs get it by pulling `main` and running the build scripts again. The scripts add and update; they never delete anything unless someone runs `--remove-retired` on purpose.

## Rules that keep every installation compatible

- **Don't change the publisher or prefix.** Every installation uses publisher `unwindhousing`, prefix `clt` and choice value prefix `76827`. That is what lets a table or column mean the same thing everywhere.
- **Nothing specific to one CLT in core code.** No organization names, tenant addresses or account names in `schema.py`, the app specs, flows, pages or tools. Your own settings and form mappings go in your folder, `clients/<yourname>/`, which git ignores.
- **Need something different? Make it a setting.** If your CLT needs a different rule, add a field, a list value or a setting that any CLT could use, and send that back. A private edit of `schema.py` will collide with the next version.
- **Never rename or remove a table, column or choice value in place.** Add the new one and list the old one under `RETIRED` in `schema.py`, so existing installations can move over.
- **No real data.** Tests and examples use made-up people at `example.com`. See `SECURITY.md`.
- **Change a rule, add an example.** Rules such as the pre-screen live in plain functions with worked examples in `tests/`. A changed rule comes with a changed or new example.
- **Describe the real screens.** When a form or workflow changes, update the in-app guides (`webresources/guides.html`, `webresources/intake-guide.html`) and `docs/PLAYBOOK.md`.

## Checks and tests

From the repo folder, with the virtual environment active:

```
python3 build_schema.py --check && python3 build_app.py --check && python3 build_app.py --check --app core && python3 build_app.py --check --app intake && python3 build_flows.py --check
for t in tests/test_*.py; do python3 "$t" || break; done
```

`tests/test_prescreen.py` needs Node.js; it is skipped with a message if Node isn't installed.

## Asking for a feature

Open an issue describing what you need and why. Maintainers log accepted requests in the Feature requests table at the bottom of `docs/ROADMAP.md`.

## Working with Claude

`CLAUDE.md` is the brief Claude Code reads when it opens this repo. If you use Claude to make a change, it will follow the rules above. Keep your own environment details in `CLAUDE.local.md`, which git ignores.
