"""Server-side report HTML (preview + PDF) from retained snapshots (plan section 8).

Status/verification is always derived here from the database, never from the client (8.11).
Branding is inlined as data: URIs so the renderer needs no network/file access (C12).
"""
import base64
import datetime
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import escape

from apps.submissions.models import ReviewDecision, Status
from apps.submissions.services import snapshot_of

ASSETS = Path(__file__).resolve().parent / "assets"
PAGES = {
    "Letter": {"width": "8.5in", "height": "11in"},
    "A4": {"width": "210mm", "height": "297mm"},
}
# Matches the source header: logo top ~8.6pt, rule ~94pt, body from ~120pt; footer "Page N | M" (D-014).
MARGINS = {"top": "1.6in", "bottom": "1.25in", "left": "1in", "right": "1in"}


def _data_uri(name, mime):
    return f"data:{mime};base64," + base64.b64encode((ASSETS / name).read_bytes()).decode()


@lru_cache(maxsize=1)
def assets():
    faces = []
    for weight, style in (("400", "normal"), ("700", "normal"), ("400", "italic"), ("700", "italic")):
        uri = _data_uri(f"tinos-latin-{weight}-{style}.woff2", "font/woff2")
        faces.append(f'@font-face{{font-family:"Tinos";font-weight:{weight};font-style:{style};'
                     f'src:url({uri}) format("woff2");}}')
    return {"font_css": "\n".join(faces), "logo_uri": _data_uri("kiet-logo.png", "image/png")}


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


def _prepare_activity(schema, act):
    """Derive display values by field type: <id>_display (dates), <id>_list (multiselect/longtext lines),
    <id>_items (checklist pairs). Raw values stay available under their ids."""
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
    return out


def build_context(submission, revision=None, draft=None):
    """draft = unsaved {payload, is_nil, nil_reason, achievement_text} for preview only."""
    tv = submission.assignment.template_version
    schema = tv.schema
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
    page = dict(PAGES[schema["page"]["format"]])
    if schema["page"].get("landscape"):
        page["width"], page["height"] = page["height"], page["width"]
    page["css_size"] = f'{page["width"]} {page["height"]}'
    table = next(f for s in schema["sections"] for f in s["fields"] if f["type"] == "table")
    return {
        **assets(),
        "snap": snap,
        "schema": schema,
        "template_name": "reports/nil.html" if src["is_nil"] else tv.renderer_template,
        "is_nil": src["is_nil"],
        "nil_reason": src["nil_reason"],
        "achievement": src["achievement_text"],
        "activities": [_prepare_activity(schema, a) for a in (src["payload"] or {}).get("activities", [])],
        "engagement_columns": table["columns"],
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
    # Chromium offsets header content by ~14.6pt; the negative margin restores the source geometry
    # (logo 8.6-82.1pt drawn at 241x73.5pt, 0.7pt blue rule at 94pt, "Page N | M" at ~719pt).
    header = (
        '<div style="width:100%;margin:-6pt 0 0;padding:0;font-size:8pt;-webkit-print-color-adjust:exact;">'
        f'<div style="text-align:center;height:73.5pt"><img src="{a["logo_uri"]}" style="width:241pt;height:73.5pt"></div>'
        '<div style="border-top:0.75pt solid #4a86c5;margin:12pt 3.75pt 0;"></div></div>'
    )
    regular = a["font_css"].splitlines()[0]  # header/footer templates do not inherit page fonts
    footer = (
        f'<style>{regular}</style>'
        '<div style="width:100%;font-family:Tinos,serif;font-size:10.5pt;color:#8496b0;padding:0 1.18in 46pt 1in;'
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
        "margin": MARGINS,
    }


def content_hash(parts):
    blob = json.dumps({**parts, "renderer": settings.RENDERER_VERSION}, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()
