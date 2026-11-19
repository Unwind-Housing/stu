"""
Stu: one model-driven app holding both sides, as two areas (the switcher at the bottom left of the sidebar).

    python3 build_app.py --url ...            (Stu is the default)
    python3 build_app.py --app stu --url ...

Nothing is defined here. The Stewardship area is app_spec.py and the Applications and Sales area is
app_spec_intake.py, so a view, form or page is still changed in the spec it belongs to. Those two specs
can still be built as apps of their own (--app core, --app intake) for a client that wants one side only.

Why one app: Power Apps per app passes are counted per person per app, and a household is followed from
screener to occupancy without changing apps. Who sees which side is decided by security roles, not the app.
"""
import app_spec as core
import app_spec_intake as intake
from schema import TABLES

APP = {
    "name": "Stu",
    "uniquename": "clt_Stu",
    "description": "Stewardship, intake and selection for community land trusts.",
}

# (area title, its navigation groups). The first item of the first area is where the app opens.
# A sale is run from one side: in Stu, Resale leaves Stewardship's Activities and sits in a Sales group with
# Applications and Sales, next to the projects that find its buyer. (A Stewardship-only app keeps it under Activities.)
SALES = ("Sales", ["page:resale"])
_stewardship = [(group, [t for t in items if t not in SALES[1]]) for group, items in core.NAVIGATION]
_sales_after = "Projects"
_applications = []
for _group in intake.NAVIGATION:
    _applications.append(_group)
    if _group[0] == _sales_after:
        _applications.append(SALES)
AREAS = [
    ("Stewardship", _stewardship),
    ("Applications and Sales", _applications),
]
NAVIGATION = [group for _, groups in AREAS for group in groups]

APP_TABLES = [t["name"] for t in TABLES]  # every table: both sides, and the ones reached through related lists


def _merged(name):
    """One dict from both specs. The same key in both must mean the same thing."""
    a, b = getattr(core, name), getattr(intake, name)
    clash = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    assert not clash, f"{name}: defined differently in app_spec.py and app_spec_intake.py: {clash}"
    return {**a, **b}


PAGES = _merged("PAGES")
FORMS = _merged("FORMS")
WEB_RESOURCES = _merged("WEB_RESOURCES")
FORM_SCRIPTS = _merged("FORM_SCRIPTS")
SCRIPT_LIBRARIES = _merged("SCRIPT_LIBRARIES")
DEPENDENT_LOOKUPS = _merged("DEPENDENT_LOOKUPS")
VIEWS = core.VIEWS + intake.VIEWS
MANUAL_COLUMNS = core.MANUAL_COLUMNS + intake.MANUAL_COLUMNS

_seen = set()
for _v in VIEWS:
    _key = (_v["table"], _v["name"])
    assert _key not in _seen, f"view defined in both specs: {_key}"
    _seen.add(_key)
