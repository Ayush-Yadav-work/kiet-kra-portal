"""Shared field capabilities layered onto stored template schemas at read time (D-079).

Stored TemplateVersion schemas stay immutable (plan 7); `apply` returns a copy in which
- year/semester fields become `term` fields: labelled dropdowns (year of study limited to the department's programme
  length, semester Odd/Even as the templates' own examples use) whose value is {"year", "semester"[, "legacy"]};
- Head-of-Department/Dean name fields become `auto: dean_name`: read-only, filled from the submitting Dean's profile and
  snapshotted on each revision, never taken from the client.
Old free-text values stay valid in drafts and render unchanged in historical revisions.
"""
import copy
import re

YEARS = ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year"]
SEMESTERS = ["Odd Semester", "Even Semester"]
# Programme length (years) per department; departments not listed run four-year programmes (B.Tech, B.Pharm).
PROGRAMME_YEARS = {"KSOM": 2, "MCA": 2}
# Template key -> {field id or "table.column": capability}. Only fields that mean year of study/semester or the reporting
# department's own Head/Dean are listed; calendar years, batches, coordinators and external heads are not (docs/api.md).
FIELDS = {
    **{k: {"year_semester": "year_semester", "hod": "dean_name"} for k in ("kra1", "kra2", "kra3", "kra11", "kra23")},
    "kra19": {"year_semester": "year_semester", "hod": "dean_name", "courses.year_semester": "year_semester"},
    "kra44": {"semester": "year_semester", "hod_name": "dean_name"},
    "kra7": {"semester": "semester"},
}


def years_for(department_code):
    return YEARS[:PROGRAMME_YEARS.get(department_code, 4)] if department_code else YEARS[:4]


def _upgrade(f, cap, department_code):
    if cap == "dean_name":
        f.update(auto="dean_name", help="Filled automatically from your account profile (full name).")
        return
    parts = [{"id": "semester", "label": "Semester", "options": SEMESTERS}]
    if cap == "year_semester":
        parts.insert(0, {"id": "year", "label": "Year of study", "options": years_for(department_code)})
    f.pop("placeholder", None)
    f.update(type="term", parts=parts)


def apply(schema, department_code=None):
    out = copy.deepcopy(schema)
    caps = FIELDS.get(out.get("key"), {})
    for section in out["sections"]:
        for f in section["fields"]:
            if f["id"] in caps:
                _upgrade(f, caps[f["id"]], department_code)
            for c in f.get("columns", []):
                if f"{f['id']}.{c['id']}" in caps:
                    _upgrade(c, caps[f"{f['id']}.{c['id']}"], department_code)
    return out


def schema_for(submission):
    a = submission.assignment
    return apply(a.template_version.schema, a.department.code)


def term_display(v):
    """Composed text for a term value; legacy free text (str, or kept under "legacy") is shown as entered."""
    if isinstance(v, dict):
        picked = [v.get(k) for k in ("year", "semester") if v.get(k)]
        return " / ".join(picked) if picked else str(v.get("legacy") or "")
    return "" if v is None else str(v)


ORD = {"1": 0, "first": 0, "i": 0, "2": 1, "second": 1, "ii": 1, "3": 2, "third": 2, "iii": 2,
       "4": 3, "fourth": 3, "iv": 3, "5": 4, "fifth": 4, "v": 4}
YEAR_RE = re.compile(r"\b(?:(1|2|3|4|5|first|second|third|fourth|fifth|i{1,3}|iv|v)\s*(?:st|nd|rd|th)?\s*(?:year|yr)"
                     r"|(?:year|yr)\s*[-:]?\s*(1|2|3|4|5|i{1,3}|iv|v))\b", re.I)
SEM_RE = re.compile(r"\b(?:sem(?:ester)?\s*[-:]?\s*(10|[1-9]|i{1,3}|iv|v|vi{1,3}|ix|x)|(10|[1-9])\s*(?:st|nd|rd|th)?\s*sem(?:ester)?)\b", re.I)
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}


def map_legacy(text, f):
    """Free text -> term value when it names exactly one year/semester consistent with the options; else kept as
    {"legacy": text} for the Dean to correct (never guessed, never discarded)."""
    text = (text or "").strip()
    if not text:
        return {}
    keep = {"legacy": text}
    parts = {p["id"]: p["options"] for p in f["parts"]}
    years = {ORD[(a or b).lower()] for a, b in YEAR_RE.findall(text)}
    nums = {int(a or b) if (a or b).isdigit() else ROMAN[(a or b).lower()] for a, b in SEM_RE.findall(text)}
    odd, even = bool(re.search(r"\bodd\b", text, re.I)), bool(re.search(r"\beven\b", text, re.I))
    if len(years) > 1 or len(nums) > 1 or (odd and even):
        return keep
    n = next(iter(nums), None)
    if n and ((odd and n % 2 == 0) or (even and n % 2)):
        return keep
    semester = SEMESTERS[0] if odd or (n and n % 2) else SEMESTERS[1] if even or n else ""
    if not semester:
        return keep
    out = {"semester": semester}
    if "year" in parts:
        y = next(iter(years), None)
        if n and y is not None and (n + 1) // 2 != y + 1:
            return keep  # e.g. "2nd year / semester 7"
        y = (n + 1) // 2 - 1 if y is None and n else y
        if y is None or y >= len(parts["year"]):
            return keep
        out["year"] = parts["year"][y]
    elif years:
        return keep  # a year where only the semester is asked: keep for review
    return out


def _each_term(schema, act):
    """(container, key, field) for every term value in one activity, including table cells."""
    for s in schema["sections"]:
        for f in s["fields"]:
            if f["type"] == "term":
                yield act, f["id"], f
            for c in f.get("columns", []):
                if c["type"] == "term":
                    for row in act.get(f["id"]) or []:
                        if isinstance(row, dict):
                            yield row, c["id"], c


def editable_payload(schema, payload):
    """The Dean's working copy as the editor expects it: legacy term strings mapped or kept under "legacy"."""
    out = copy.deepcopy(payload or {})
    for act in out.get("activities") or []:
        if isinstance(act, dict):
            for obj, key, f in list(_each_term(schema, act)):
                if not isinstance(obj.get(key), dict):
                    obj[key] = map_legacy(obj.get(key), f)
    return out


def strip_auto(schema, payload):
    """Client-supplied values of auto fields are never stored: the name comes from the profile snapshot."""
    auto = [f["id"] for s in schema["sections"] for f in s["fields"] if f.get("auto")]
    for act in (payload or {}).get("activities") or []:
        if isinstance(act, dict):
            for k in auto:
                if k in act:
                    act[k] = ""
    return payload


def needs_dean_name(schema, is_nil):
    return is_nil or any(f.get("auto") == "dean_name" and f.get("required") for s in schema["sections"] for f in s["fields"])
