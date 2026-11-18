"""
Form mappings: which question on an organization's online form feeds which Stu field.

Every organization has its own forms, so nothing about a form's wording lives in the flow code. Each form
has one mapping file:

    clients/<organization>/forms/screener.json            the screener (type "screener")
    clients/<organization>/forms/screener-<name>.json     another screener with different questions
    clients/<organization>/forms/full-application.json    the full application (type "full-application")
    clients/<organization>/forms/annual-verification.json the yearly occupancy verification (type "annual-verification")

Forms that are copies of each other (same question names) share one mapping and one flow. A form with
different questions gets its own mapping file, and the build makes it its own flow.

A mapping is JSON. Values are the path to the answer in the entry the forms platform posts, with dots
between levels: "PrimaryApplicant.Name.First". Inside a repeating section (income, debts, assets, other
household members) "list" is the path to the section and the other paths are inside one line of it.
A question the form doesn't ask is simply left out: Stu leaves that field blank.

clients/example/forms/ has a complete pair to copy. Check a mapping against a real entry with:

    python3 form_mapping.py clients/<organization>/forms/screener.json sample-entry.json
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENTS = os.path.join(HERE, "clients")
TYPES = ("screener", "full-application", "annual-verification")
NOT_ASKED = ("NotOnThisForm",)   # a path no entry has: the flow reads it as blank
# Keys that aren't paths
META = ("type", "label", "provider", "choices", "firstLetterChoices", "notes", "uploadsFolder", "uploadsPath")
REQUIRED = {
    "screener": ["entry.id", "entry.formId", "applicant.firstName", "applicant.lastName", "applicant.email"],
    "full-application": ["entry.id", "entry.formId", "applicant.firstName", "applicant.lastName"],
    "annual-verification": ["entry.id", "entry.formId", "match.occupancyId"],
}
LISTS = ("otherMembers", "income", "debts", "assets")


class MappingError(Exception):
    pass


class Mapping:
    def __init__(self, data, source="(mapping)"):
        self.source = source
        self.type = data.get("type")
        if self.type not in TYPES:
            raise MappingError(f"{source}: \"type\" must be one of {', '.join(TYPES)}")
        self.provider = data.get("provider") or "Cognito Forms"
        self.label = data.get("label") or ""
        self._choices = data.get("choices") or {}
        self._first_letter = set(data.get("firstLetterChoices") or [])
        # Annual verification: the folder the forms platform saves uploads in (a web address), and the folder it makes
        # inside it for each entry, with {formName} and {number} where the form's name and the entry's number go.
        self.uploads_folder = (data.get("uploadsFolder") or "").strip()
        self.uploads_path = (data.get("uploadsPath") or "{formName}/Entry_{number}").strip()
        if re.sub(r"\{(formName|number)\}", "", self.uploads_path).count("{"):
            raise MappingError(f"{source}: uploadsPath can only use {{formName}} and {{number}}")
        self.paths = {}
        self._flatten("", {k: v for k, v in data.items() if k not in META})
        missing = [k for k in REQUIRED[self.type] if k not in self.paths]
        if self.type == "full-application" and not (self.has("applicant.applicationNumber") or self.has("applicant.email")):
            missing.append("applicant.applicationNumber or applicant.email")
        if missing:
            raise MappingError(f"{source}: missing {', '.join(missing)}")

    def _flatten(self, prefix, node):
        for k, v in node.items():
            if isinstance(v, dict):
                self._flatten(f"{prefix}{k}.", v)
            elif isinstance(v, str) and v.strip():
                if not re.fullmatch(r"\w+(\.\w+)*", v.strip()):
                    raise MappingError(f"{self.source}: {prefix}{k}: \"{v}\" isn't a path like Section.Question")
                self.paths[f"{prefix}{k}"] = tuple(v.strip().split("."))
            elif v not in (None, ""):
                raise MappingError(f"{self.source}: {prefix}{k} must be a path (text)")

    def has(self, key):
        return key in self.paths

    def path(self, key):
        """The path for a key, or one that no entry has (read as blank) when the form doesn't ask it."""
        return self.paths.get(key, NOT_ASKED)

    def choices(self, name):
        """Form answer -> Stu label for a choice, or None when the form uses Stu's labels word for word."""
        return self._choices.get(name)

    def first_letter(self, name):
        """True when a choice is matched on the first letter of the answer ("a) As a single parent...")."""
        return name in self._first_letter

    @property
    def slug(self):
        """"" for the main form of its type (screener.json), else the rest of the file name."""
        base = os.path.splitext(os.path.basename(self.source))[0].lower()
        rest = base[len(self.type):] if base.startswith(self.type) else base
        return re.sub(r"[^a-z0-9]+", "-", rest).strip("-")

    # ---- checking against a real entry
    def check_sample(self, sample):
        """Problems found comparing the mapping with one posted entry: mapped paths the entry doesn't have."""
        problems = []

        def get(node, path):
            for key in path:
                if not isinstance(node, dict) or key not in node:
                    return KeyError
                node = node[key]
            return node
        for key, path in sorted(self.paths.items()):
            section = key.split(".")[0]
            if key == "entry.lineId":
                continue  # read inside each line of a repeating section
            if section in LISTS and not key.endswith(".list"):
                lines = get(sample, self.path(f"{section}.list"))
                if lines is KeyError or not isinstance(lines, list):
                    continue  # reported on the list itself
                for i, line in enumerate(lines):
                    if get(line, path) is KeyError:
                        problems.append(f"{key}: line {i + 1} of {'.'.join(self.path(section + '.list'))} "
                                        f"has no {'.'.join(path)}")
                        break
            elif get(sample, path) is KeyError:
                problems.append(f"{key}: the entry has no {'.'.join(path)}")
        return problems

    def unmapped(self, sample):
        """Questions in the entry that no mapping path reads (for a person to review)."""
        used = set(self.paths.values())
        prefixes = {p[:i] for p in used for i in range(1, len(p))}
        out = []

        def walk(node, path):
            for k, v in node.items():
                p = path + (k,)
                if p in used:
                    continue
                if isinstance(v, dict) and p in prefixes:
                    walk(v, p)
                else:
                    out.append(".".join(p))
        walk(sample, ())
        return out


def load(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise MappingError(f"{path}: {e}")
    return Mapping(data, path)


def client_dirs():
    """Every organization folder under clients/ (the example first)."""
    if not os.path.isdir(CLIENTS):
        return []
    names = [n for n in os.listdir(CLIENTS) if os.path.isdir(os.path.join(CLIENTS, n)) and not n.startswith(".")]
    return [os.path.join(CLIENTS, n) for n in sorted(names, key=lambda n: (n != "example", n))]


def client_file(folder):
    return os.path.join(folder, "client.json")


def client_for(url):
    """The organization folder whose client.json lists this environment address, or None."""
    for folder in client_dirs():
        try:
            c = json.load(open(client_file(folder), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if url.rstrip("/").lower() in [u.rstrip("/").lower() for u in c.get("environments", {}).values()]:
            return folder
    return None


def mappings(folder):
    """The form mappings in an organization's folder: screeners first, then full applications."""
    forms = os.path.join(folder, "forms")
    if not os.path.isdir(forms):
        return []
    out = [load(os.path.join(forms, n)) for n in sorted(os.listdir(forms)) if n.endswith(".json")]
    return sorted(out, key=lambda m: (TYPES.index(m.type), m.slug))


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    try:
        m = load(sys.argv[1])
    except MappingError as e:
        sys.exit(str(e))
    print(f"{sys.argv[1]}: {m.type}, {len(m.paths)} questions mapped.")
    if len(sys.argv) == 3:
        sample = json.load(open(sys.argv[2], encoding="utf-8"))
        problems = m.check_sample(sample)
        for p in problems:
            print("  ! " + p)
        extra = m.unmapped(sample)
        if extra:
            print("  In the entry but not mapped (fine if Stu has no use for them):")
            for p in extra:
                print("    " + p)
        if problems:
            sys.exit(1)
        print("  Every mapped question is in the entry.")


if __name__ == "__main__":
    main()
