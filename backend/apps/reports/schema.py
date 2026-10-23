"""Schema-driven payload validation (plan 8.1–8.4). The backend is authoritative.

Payload shape: {"activities": [{<field_id>: value, ...}, ...]}.
Structural checks (types, lengths, row caps, unknown keys) run on every save/preview; required fields,
numeric ranges/decimal places and cross-field rules run only when `strict` (submission/validate), so a
draft with an out-of-range or over-precise number still saves exactly as typed (plan 3.1).

Field types: text, longtext, integer, decimal (kept as the entered string, never rounded), date, select,
multiselect, checklist (item -> Yes/No), ratings (list aligned with items: decimal strings), table (rows of
scalar columns), term (year of study/semester dropdowns, see apps/reports/capabilities.py). Fields with
`auto` set (the Dean's name) are never validated or stored from the client. Table columns may be `auto` (filled by the renderer, never entered) or conditional via
`when: {"field": <column>, "in": [...]}` — required only when applicable, must be blank otherwise.
"""
import datetime
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings

YES_NO = ("Yes", "No")
DECIMAL_RE = re.compile(r"^-?\d+(\.\d+)?$")


def fields_of(schema):
    for section in schema["sections"]:
        yield from section["fields"]


def default_for(f):
    return [] if f["type"] in ("table", "multiselect", "ratings") else {} if f["type"] in ("checklist", "term") else ""


def empty_activity(schema):
    return {f["id"]: default_for(f) for f in fields_of(schema)}


def _blank(v):
    return v is None or v == "" or v == [] or v == {}


def applies(cond, obj):
    """`when` condition: {"field", "in": [...]} (value is one of) or {"field", "contains": x} (multiselect includes x)."""
    if not cond:
        return True
    value = obj.get(cond["field"])
    if "contains" in cond:
        return isinstance(value, list) and cond["contains"] in value
    return value in cond["in"]


def applicable(col, row):
    return applies(col.get("when"), row)


def check_decimal(f, v, strict=True):
    """Return an error message or None. Accepts the entered string (or a JSON number) without rounding.
    Drafts only need a well-formed number; precision and range are enforced at submission."""
    s = str(v).strip()
    if isinstance(v, bool) or not DECIMAL_RE.match(s):
        return "Must be a number."
    if not strict:
        return None
    places = len(s.split(".")[1]) if "." in s else 0
    if places > f.get("decimal_places", 2):
        return f"Use at most {f.get('decimal_places', 2)} decimal places (values are not rounded)."
    d = Decimal(s)
    lo, hi = Decimal(str(f.get("min", -10**12))), Decimal(str(f.get("max", 10**12)))
    if not lo <= d <= hi:
        return f.get("range_message") or f"Must be between {f.get('min')} and {f.get('max')}."
    return None


def _check_scalar(f, v, path, errors, strict=True):
    """Validate one non-container value; appends errors."""
    t = f["type"]
    if _blank(v) or t == "auto":
        return
    if t in ("text", "longtext"):
        if not isinstance(v, str):
            errors[path] = ["Must be text."]
        elif len(v) > f.get("max_length", 2000):
            errors[path] = [f"Maximum {f.get('max_length', 2000)} characters (currently {len(v)})."]
    elif t == "integer":
        if isinstance(v, bool) or not isinstance(v, int):
            errors[path] = ["Must be a whole number."]
        elif strict and not f.get("min", -10**12) <= v <= f.get("max", 10**12):
            errors[path] = [f"Must be between {f.get('min')} and {f.get('max')}."]
    elif t == "decimal":
        msg = check_decimal(f, v, strict)
        if msg:
            errors[path] = [msg]
    elif t == "date":
        try:
            datetime.date.fromisoformat(v)
        except (TypeError, ValueError):
            errors[path] = ["Must be a valid date (YYYY-MM-DD)."]
    elif t == "select":
        if v not in f["options"]:
            errors[path] = ["Choose one of the listed options."]
    elif t == "term":
        _check_term(f, v, path, errors, strict)
    else:
        errors[path] = [f"Unsupported field type {t}."]


def _check_term(f, v, path, errors, strict):
    """Draft: legacy free text or {part: option, "legacy": text}. Submission: every part selected."""
    parts = {p["id"]: p for p in f["parts"]}
    if isinstance(v, str):
        if len(v) > f.get("max_length", 200):
            errors[path] = [f"Maximum {f.get('max_length', 200)} characters (currently {len(v)})."]
        elif strict:
            errors[path] = [f'Select the {" and ".join(p["label"].lower() for p in f["parts"])}; the earlier entry "{v}" could not be matched.']
        return
    if not isinstance(v, dict) or set(v) - set(parts) - {"legacy"} or not isinstance(v.get("legacy", ""), str):
        errors[path] = ["Invalid selection."]
    elif any(v.get(k) not in ("", None, *p["options"]) for k, p in parts.items()):
        errors[path] = ["Choose one of the listed options."]
    elif strict and (f.get("required") or any(v.get(k) for k in parts)) and not all(v.get(k) for k in parts):
        missing = [p["label"] for k, p in parts.items() if not v.get(k)]
        errors[path] = [f"Select the {' and '.join(m.lower() for m in missing)}."]


def _check_rules(rules, obj, path, errors):
    """Cross-field rules on an activity or a table row. Only checked when both values are present and valid."""
    for rule in rules or []:
        if not applies(rule.get("when"), obj):
            continue
        if rule["type"] == "ref_in":  # each table row's reference must name a row of another table in the same record
            keys = {r.get(rule["key"]) for r in obj.get(rule["source"]) or [] if isinstance(r, dict) and not _blank(r.get(rule["key"]))}
            for i, r in enumerate(obj.get(rule["table"]) or []):
                p = f"{path}{rule['table']}.{i}.{rule['column']}"
                if isinstance(r, dict) and not _blank(r.get(rule["column"])) and p not in errors and r[rule["column"]] not in keys:
                    errors[p] = [rule["message"]]
            continue
        a, b = obj.get(rule["a"]), obj.get(rule["b"])
        if _blank(a) or _blank(b) or f"{path}{rule['a']}" in errors or f"{path}{rule['b']}" in errors:
            continue
        if rule["type"] == "date_order" and datetime.date.fromisoformat(b) < datetime.date.fromisoformat(a):
            errors[f"{path}{rule['b']}"] = [rule["message"]]
        elif rule["type"] == "lte" and Decimal(str(a)) > Decimal(str(b)):
            errors[f"{path}{rule['a']}"] = [rule["message"]]


def _check_field(f, v, path, strict, errors):
    t = f["type"]
    if f.get("auto"):
        return  # derived on the server (the Dean's profile name); any client value is discarded
    if t == "multiselect":
        if not isinstance(v, list) or any(x not in f["options"] for x in v) or len(set(v)) != len(v):
            errors[path] = ["Choose from the listed options."]
        elif strict and f.get("required") and not v:
            errors[path] = ["Select at least one."]
    elif t == "checklist":
        if not isinstance(v, dict) or any(k not in f["items"] or x not in YES_NO + ("", None) for k, x in v.items()):
            errors[path] = ["Answer Yes or No for listed items only."]
        elif strict and f.get("required") and any(v.get(i) not in YES_NO for i in f["items"]):
            errors[path] = ["Answer Yes or No for every item."]
    elif t == "ratings":
        if not isinstance(v, list) or len(v) > len(f["items"]):
            errors[path] = ["Invalid ratings."]
            return
        scale = {"min": f["scale"][0], "max": f["scale"][-1], "decimal_places": f.get("decimal_places", 2)}
        for n in range(len(f["items"])):
            x = v[n] if n < len(v) else ""
            if _blank(x):
                if strict and f.get("required"):
                    errors[f"{path}.{n}"] = ["Enter the consolidated average."]
                continue
            msg = check_decimal(scale, x, strict)
            if msg:
                errors[f"{path}.{n}"] = [msg]
    elif t == "table":
        max_rows = min(f.get("max_rows", settings.MAX_TABLE_ROWS), settings.MAX_TABLE_ROWS)
        if not isinstance(v, list) or any(not isinstance(r, dict) for r in v):
            errors[path] = ["Invalid table."]
            return
        if len(v) > max_rows:
            errors[path] = [f"At most {max_rows} rows."]
            return
        if strict and f.get("required") and len(v) < f.get("min_rows", 1):
            errors[path] = [f"Add at least {f.get('min_rows', 1)} row(s)."]
        cols = {c["id"]: c for c in f["columns"] if c["type"] != "auto"}
        for i, row in enumerate(v):
            for k in row:
                if k not in cols:
                    errors[f"{path}.{i}.{k}"] = ["Unknown column."]
            for c in cols.values():
                cv, cp = row.get(c["id"], ""), f"{path}.{i}.{c['id']}"
                if not applicable(c, row):
                    if not _blank(cv) and strict and not c.get("keep_inactive"):  # keep_inactive: kept in draft, ignored
                        errors[cp] = [f"Not applicable for this {cols[c['when']['field']]['label'].lower()}; leave blank."]
                    continue
                _check_scalar(c, cv, cp, errors, strict)
                if strict and c.get("required") and _blank(cv) and cp not in errors:
                    errors[cp] = ["Required."]
            if strict:  # cross-field rules never block saving a draft (plan 3.1)
                _check_rules(f.get("row_rules"), row, f"{path}.{i}.", errors)
    else:
        _check_scalar(f, v, path, errors, strict)
        if strict and f.get("required") and _blank(v) and path not in errors:
            errors[path] = ["Required."]


def validate_payload(schema, payload, strict=False):
    errors = {}
    if not isinstance(payload, dict) or set(payload) - {"activities"}:
        return {"payload": ["Invalid report structure."]}
    activities = payload.get("activities", [])
    spec = schema["activity"]
    max_acts = min(spec.get("max", settings.MAX_ACTIVITIES), settings.MAX_ACTIVITIES)
    if not isinstance(activities, list) or any(not isinstance(a, dict) for a in activities):
        return {"activities": ["Invalid activity list."]}
    if len(activities) > max_acts:
        return {"activities": [f"At most {max_acts} {spec['label'].lower()}(s) per report."]}
    if strict and len(activities) < spec.get("min", 1):
        errors["activities"] = [f"Add at least {spec.get('min', 1)} {spec['label'].lower()}."]
    fields = {f["id"]: f for f in fields_of(schema)}
    for i, act in enumerate(activities):
        for k in act:
            if k not in fields:
                errors[f"activities.{i}.{k}"] = ["Unknown field."]
        for fid, f in fields.items():
            if strict and not applies(f.get("when"), act):
                continue  # e.g. a deselected KRA 9 variant: kept in the draft, ignored at submission
            _check_field(f, act.get(fid, default_for(f)), f"activities.{i}.{fid}", strict, errors)
        if strict:
            _check_rules(schema.get("rules"), act, f"activities.{i}.", errors)
    return errors
