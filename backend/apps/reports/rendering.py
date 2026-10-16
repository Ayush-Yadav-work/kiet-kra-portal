"""Server-side report HTML (preview + PDF) from retained snapshots (plan section 8).

Status/verification is always derived here from the database, never from the client (8.11).
Branding is inlined as data: URIs so the renderer needs no network/file access (C12).
"""
import base64
import copy
import datetime
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.reports.families import PREPARERS
from apps.submissions.models import ReviewDecision, Status
from apps.submissions.services import snapshot_of

ASSETS = Path(__file__).resolve().parent / "assets"
PAGES = {
    "Letter": {"width": "8.5in", "height": "11in"},
    "A4": {"width": "210mm", "height": "297mm"},
}
CHROMIUM_HEADER_OFFSET = 15  # pt: Chromium places header-template content ~15pt below the page top

# Header styles measured from the source PDFs (D-014, D-027). y = top of each element in pt.
STYLES = {
    # Word report family (KRA 33 etc.): logo 8.6-82.1pt drawn 241x73.5pt, 0.75pt blue rule at 94pt.
    "report": {"margins": {"top": "1.6in", "bottom": "1.25in", "left": "1in", "right": "1in"},
               "logo": (241, 73.5, 8.6), "caption": None, "rule": ("0.75pt solid #4a86c5", 12, "3.75pt")},
    # Survey family (KRA 7-10): logo 36.9-105.9pt (187.6x69), bold institute caption, 3pt maroon rule at ~120pt.
    "survey": {"margins": {"top": "1.95in", "bottom": "1.1in", "left": "1in", "right": "1in"},
               "logo": (187.6, 69, 36.9), "caption": "Krishna Institute of Engineering &amp; Technology (KIET) (Deemed to be university)",
               "rule": ("3pt solid #62231f", 2, "1in")},
    # Spreadsheet family (KRA 20, 32...): logo only, repaired onto one landscape table.
    "sheet": {"margins": {"top": "1.7in", "bottom": "0.9in", "left": "0.5in", "right": "0.5in"},
              "logo": (248, 92, 20), "caption": None, "rule": None},
}


def header_html(style, logo_uri, for_pdf):
    st = STYLES[style]
    w, h, y = st["logo"]
    top = y - CHROMIUM_HEADER_OFFSET if for_pdf else y
    out = (f'<div style="width:100%;margin:{top}pt 0 0;padding:0;font-family:Tinos,serif;-webkit-print-color-adjust:exact;">'
           f'<div style="text-align:center;height:{h}pt"><img src="{logo_uri}" alt="KIET Deemed to be University" '
           f'style="width:{w}pt;height:{h}pt"></div>')
    if st["caption"]:
        out += f'<div style="text-align:center;font-weight:bold;font-size:8.5pt;margin-top:2pt">{st["caption"]}</div>'
    if st["rule"]:
        border, gap, inset = st["rule"]
        out += f'<div style="border-top:{border};margin:{gap}pt {inset} 0;"></div>'
    return out + "</div>"


def _data_uri(name, mime):
    return f"data:{mime};base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


LATIN = ("U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,"
         "U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD")
LATIN_EXT = ("U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,"
             "U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF")  # accented names and the ₹ sign


def _face(subset, weight, style, rng):
    uri = _data_uri(f"tinos-{subset}-{weight}-{style}.woff2", "font/woff2")
    return (f'@font-face{{font-family:"Tinos";font-weight:{weight};font-style:{style};'
            f'src:url({uri}) format("woff2");unicode-range:{rng};}}')


@lru_cache(maxsize=1)
def assets():
    """Line 1 = regular, line 2 = bold (both with Latin-Extended); header/footer templates reuse them."""
    regular = _face("latin", "400", "normal", LATIN) + _face("latin-ext", "400", "normal", LATIN_EXT)
    bold = _face("latin", "700", "normal", LATIN) + _face("latin-ext", "700", "normal", LATIN_EXT)
    italics = [_face("latin", w, "italic", LATIN) for w in ("400", "700")]  # shortcut: no extended italics (rarely used)
    return {"font_css": "\n".join([regular, bold, *italics]), "logo_uri": _data_uri("kiet-logo.png", "image/png")}


def _fmt_date(value):
    try:
        return datetime.date.fromisoformat(value).strftime("%d %B %Y")
    except (TypeError, ValueError):
        return ""


def _lines(text):
    return [ln.strip(" \t-•●") for ln in (text or "").splitlines() if ln.strip(" \t-•●")]


def _approval(revision):
    if not revision:
        return None
    return revision.decisions.filter(decision=ReviewDecision.Decision.APPROVE).order_by("-created_at").first()


def verification(submission, revision=None):
    """(label, verified, verified_at) from server state (plan 4, 8.11).

    Current export: Verified only while the submission is Approved, else Pending approval.
    Explicit revision export: an approval the revision received is shown as historical once the
    submission is no longer Approved on that revision (returned or superseded)."""
    fmt = lambda d: timezone.localtime(d.created_at).strftime("%d %b %Y %H:%M IST")
    rev = revision or submission.current_revision
    approval = _approval(rev)
    live = submission.status == Status.APPROVED and rev is not None and rev.id == submission.current_revision_id
    if live and approval:
        return f"Verified by VC - {approval.reviewer_name}", True, fmt(approval)
    if revision is None:
        return "Pending approval", False, ""
    if approval:
        return (f"Historical revision {revision.sequence}: Verified by VC - {approval.reviewer_name}"
                f" (later returned/superseded)", True, fmt(approval))
    if revision.id == submission.current_revision_id:
        return "Pending approval", False, ""
    return f"Historical revision {revision.sequence}: not approved", False, ""


def _cell(col, row, snap):
    if col["type"] == "auto":
        return {"year": snap["year"], "department": snap["department"]["code"]}[col["source"]]
    cond = col.get("when")
    if cond and row.get(cond["field"]) not in cond["in"]:
        return "NA"
    v = row.get(col["id"])
    if v is None:
        return ""
    if col["type"] == "date":
        try:
            return datetime.date.fromisoformat(v).strftime("%d %b %Y")
        except (TypeError, ValueError):
            return ""
    return str(v)


def _prepare_activity(schema, act, snap):
    """Derive display values by field type. Raw values stay available under their ids:
    <id>_display (dates), <id>_list (multiselect/longtext lines), <id>_items (checklist pairs;
    ratings triples (n, item, value)), <id>_rows (table rows as lists of display cells), <id>_records (same cells keyed by column id)."""
    out = {k: ("" if v is None else v) for k, v in act.items()}
    for f in (f for s in schema["sections"] for f in s["fields"]):
        v = act.get(f["id"])
        if f["type"] == "date":
            out[f["id"] + "_display"] = _fmt_date(v)
        elif f["type"] == "multiselect":
            out[f["id"] + "_list"] = [o for o in f["options"] if o in (v or [])]
        elif f["type"] == "longtext":
            out[f["id"] + "_list"] = _lines(v)
        elif f["type"] == "checklist":
            out[f["id"] + "_items"] = [(item, (v or {}).get(item, "")) for item in f["items"]]
        elif f["type"] == "ratings":
            vals = v if isinstance(v, list) else []
            out[f["id"] + "_items"] = [(n + 1, item, (vals[n] if n < len(vals) and vals[n] is not None else ""))
                                       for n, item in enumerate(f["items"])]
        elif f["type"] == "table":
            out[f["id"] + "_rows"] = [[_cell(c, row, snap) for c in f["columns"]] for row in (v or [])]
            out[f["id"] + "_records"] = [{c["id"]: cell for c, cell in zip(f["columns"], r)} for r in out[f["id"] + "_rows"]]
    if "detail_columns" in schema.get("family", {}):  # course family prints a configurable one-row details table
        out["detail_cells"] = ["" if act.get(c["id"]) is None else act.get(c["id"], "")
                               for c in schema["family"]["detail_columns"]]
    prepare = PREPARERS.get(schema.get("family", {}).get("name"))
    if prepare:  # family-specific display data (e.g. survey parts) lives with the family definition
        out.update(prepare(schema, act, snap))
    return out


def build_context(submission, revision=None, draft=None):
    """draft = unsaved {payload, is_nil, nil_reason, achievement_text} for preview only."""
    tv = submission.assignment.template_version
    schema = copy.deepcopy(tv.schema)  # display-only annotations must never touch the stored schema
    if revision is not None:
        src = {"payload": revision.payload, "is_nil": revision.is_nil, "nil_reason": revision.nil_reason,
               "achievement_text": revision.achievement_text}
        snap = revision.snapshot
    else:
        src = {"payload": submission.payload, "is_nil": submission.is_nil, "nil_reason": submission.nil_reason,
               "achievement_text": submission.achievement_text}
        if draft:
            src.update({k: v for k, v in draft.items() if k in src})
        snap = snapshot_of(submission)
    label, verified, verified_at = verification(submission, revision)
    style = schema["page"].get("style", "report")
    page = dict(PAGES[schema["page"]["format"]], style=style, margins=STYLES[style]["margins"])
    if schema["page"].get("landscape"):
        page["width"], page["height"] = page["height"], page["width"]
    page["css_size"] = f'{page["width"]} {page["height"]}'
    fields = {f["id"]: f for s in schema["sections"] for f in s["fields"]}
    for f in fields.values():
        for c in f.get("columns", []):  # allow header line breaks after "/" instead of mid-word
            c["label_html"] = mark_safe(escape(c["label"]).replace("/", "/<wbr>"))
    activities = [_prepare_activity(schema, a, snap) for a in (src["payload"] or {}).get("activities", [])]
    if schema["activity"].get("max", 1) > 1:
        count = (f'{schema["activity"]["label"]}s in this report', len(activities))
    else:
        table = next((f for f in fields.values() if f["type"] == "table"), None)
        count = ("Records in this report", sum(len(a.get(table["id"] + "_rows", [])) for a in activities)) if table else None
    return {
        **assets(),
        "snap": snap,
        "schema": schema,
        "template_name": "reports/nil.html" if src["is_nil"] else tv.renderer_template,
        "is_nil": src["is_nil"],
        "nil_reason": src["nil_reason"],
        "achievement": src["achievement_text"],
        "activities": activities,
        "count": count,
        "fields": fields,
        "screen_header": header_html(style, assets()["logo_uri"], for_pdf=False),
        "verification_label": label,
        "verified": verified,
        "verified_at": verified_at,
        "page": page,
        "doc_title": f'KRA {snap["kra"]["number"]} — {snap["department"]["code"]} — {snap["period"]["label"]}',
    }


def render_html(ctx, mode):
    """mode 'preview' draws the header on screen; 'pdf' leaves it to the Chromium header template."""
    return render_to_string(ctx["template_name"], {**ctx, "mode": mode})


def pdf_parts(ctx):
    a = assets()
    style = ctx["page"]["style"]
    regular = a["font_css"].splitlines()[0]  # header/footer templates do not inherit page fonts
    bold = a["font_css"].splitlines()[1]  # survey caption is bold; avoid a synthesised Type3 face
    header = f'<style>{regular}{bold}</style>' + header_html(style, a["logo_uri"], for_pdf=True)
    m = ctx["page"]["margins"]
    pad_l, pad_r = m["left"], f'{float(m["right"].rstrip("in")) + 0.18:.2f}in'
    pad_b = round(float(m["bottom"].rstrip("in")) * 72 - 44)  # keeps "Page N | M" ~73pt above the edge (KRA 33)
    footer = (
        f'<style>{regular}</style>'
        f'<div style="width:100%;font-family:Tinos,serif;font-size:10.5pt;color:#8496b0;padding:0 {pad_r} {pad_b}pt {pad_l};'
        'display:flex;justify-content:space-between;-webkit-print-color-adjust:exact;">'
        f'<span style="color:#333;font-size:9pt">{escape(ctx["verification_label"])}</span>'
        '<span>Page <span class="pageNumber"></span> | <span class="totalPages"></span></span></div>'
    )
    return {
        "html": render_html(ctx, "pdf"),
        "header": header,
        "footer": footer,
        "format": ctx["schema"]["page"]["format"],
        "landscape": bool(ctx["schema"]["page"].get("landscape")),
        "margin": ctx["page"]["margins"],
    }


def content_hash(parts):
    blob = json.dumps({**parts, "renderer": settings.RENDERER_VERSION}, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()
