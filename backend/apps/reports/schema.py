"""Schema-driven payload validation (plan 8.1–8.4). The backend is authoritative.

Payload shape: {"activities": [{<field_id>: value, ...}, ...]}.
Structural checks (types, lengths, row caps, unknown keys) run on every save/preview;
required-field checks run only when `strict` (submission/validate).
"""
import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings

YES_NO = ("Yes", "No")


def fields_of(schema):
    for section in schema["sections"]:
        yield from section["fields"]


def empty_activity(schema):
    out = {}
    for f in fields_of(schema):
        out[f["id"]] = [] if f["type"] in ("table", "multiselect") else {} if f["type"] == "checklist" else ""
    return out


def _blank(v):
    return v is None or v == "" or v == [] or v == {}


def _check_scalar(f, v, path, errors):
    """Validate one non-container value; returns nothing, appends errors."""
    t = f["type"]
    if _blank(v):
        return
    if t in ("text", "longtext"):
        if not isinstance(v, str):
            errors[path] = ["Must be text."]
        elif len(v) > f.get("max_length", 2000):
            errors[path] = [f"Maximum {f.get('max_length', 2000)} characters (currently {len(v)})."]
    elif t == "integer":
        if isinstance(v, bool) or not isinstance(v, int):
            errors[path] = ["Must be a whole number."]
        elif not f.get("min", -10**12) <= v <= f.get("max", 10**12):
            errors[path] = [f"Must be between {f.get('min')} and {f.get('max')}."]
    elif t == "decimal":
        try:
            d = Decimal(str(v))
        except InvalidOperation:
            errors[path] = ["Must be a number."]
            return
        if not Decimal(str(f.get("min", -10**12))) <= d <= Decimal(str(f.get("max", 10**12))):
            errors[path] = [f"Must be between {f.get('min')} and {f.get('max')}."]
    elif t == "date":
        try:
            datetime.date.fromisoformat(v)
        except (TypeError, ValueError):
            errors[path] = ["Must be a valid date (YYYY-MM-DD)."]
    elif t == "select":
        if v not in f["options"]:
            errors[path] = ["Choose one of the listed options."]
    else:
        errors[path] = [f"Unsupported field type {t}."]


def _check_field(f, v, path, strict, errors):
    t = f["type"]
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
        cols = {c["id"]: c for c in f["columns"]}
        for i, row in enumerate(v):
            for k in row:
                if k not in cols:
                    errors[f"{path}.{i}.{k}"] = ["Unknown column."]
            for c in f["columns"]:
                cv, cp = row.get(c["id"], ""), f"{path}.{i}.{c['id']}"
                _check_scalar(c, cv, cp, errors)
                if strict and c.get("required") and _blank(cv) and cp not in errors:
                    errors[cp] = ["Required."]
    else:
        _check_scalar(f, v, path, errors)
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
        return {"activities": [f"At most {max_acts} {spec['label'].lower()}s per report."]}
    if strict and len(activities) < spec.get("min", 1):
        errors["activities"] = [f"Add at least {spec.get('min', 1)} {spec['label'].lower()}."]
    fields = {f["id"]: f for f in fields_of(schema)}
    for i, act in enumerate(activities):
        for k in act:
            if k not in fields:
                errors[f"activities.{i}.{k}"] = ["Unknown field."]
        for fid, f in fields.items():
            default = [] if f["type"] in ("table", "multiselect") else {} if f["type"] == "checklist" else ""
            _check_field(f, act.get(fid, default), f"activities.{i}.{fid}", strict, errors)
    return errors
