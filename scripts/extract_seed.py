"""Extract the reviewed KRA catalogue + 2026-27 department targets from the original workbook.

Usage: python scripts/extract_seed.py  (writes seed/catalogue_2026-27.json)

Definitions and targets only: achievement columns, evidence links, totals and the
extra research/final-year/M.Tech sections are deliberately not read (plan 2.2).
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "reference" / "workbook" / "original-tracker.xlsx"
MD = ROOT / "reference" / "workbook" / "converted-tracker.md"
OUT = ROOT / "seed" / "catalogue_2026-27.json"
KRA_RE = re.compile(r"\s*KRA\s*(\d+)\s*:")

# Sheet name -> department code. Full names are proposals pending college confirmation (docs/decisions.md D-003).
DEPARTMENTS = {
    "CSE": "Computer Science & Engineering",
    "CSE (AI)": "Computer Science & Engineering (Artificial Intelligence)",
    "CSE (AIML)": "Computer Science & Engineering (AI & ML)",
    "IT": "Information Technology",
    "CS": "Computer Science",
    "CSIT": "Computer Science & Information Technology",
    "EEE": "Electrical & Electronics Engineering",
    "ECE": "Electronics & Communication Engineering",
    "ME": "Mechanical Engineering",
    "KSOM": "KIET School of Management (MBA)",
    "MCA": "Master of Computer Applications",
    "KSOP": "KIET School of Pharmacy",
    "ASH": "Applied Sciences & Humanities",
}


def display(value):
    """Render a cell the way Excel's General format shows it; strings stay byte-for-byte."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def read_catalogue(wb):
    ws = wb["Instructions"]
    kras = {}
    for row in ws.iter_rows(min_row=14, max_row=60):
        activity = row[0].value
        if not (isinstance(activity, str) and KRA_RE.match(activity)):
            continue
        n = int(KRA_RE.match(activity).group(1))
        kras[n] = {
            "number": n,
            "activity_text": activity,
            "nba_ref": display(row[1].value),
            "naac_ref": display(row[2].value),
            # Raw cells of this row only; merged/shared rows are mapped in docs/template-inventory.md.
            "source_report_format": row[3].value or "",
            "source_summary_template": row[4].value or "",
        }
    assert sorted(kras) == list(range(1, 46)), sorted(kras)
    return kras


def read_targets(wb):
    targets = {}
    for code in DEPARTMENTS:
        ws = wb[code]
        found = {}
        for row in ws.iter_rows(min_row=4):
            m = isinstance(row[3].value, str) and KRA_RE.match(row[3].value)
            if m:
                found[int(m.group(1))] = display(row[4].value)
        assert sorted(found) == list(range(1, 46)), (code, sorted(found))
        targets[code] = found
    return targets


def md_targets():
    """Independent read of the Markdown conversion, used only as a cross-check."""
    names = {"MBA": "KSOM"}
    cur, out = None, {}
    for line in MD.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"\|\*\*(.+?) – KRA Achievement Tracker", line)
        if m:
            cur = names.get(m.group(1), m.group(1))
            out[cur] = {}
            continue
        if cur and "|KRA " in line:
            cells = line.split("|")
            for i, c in enumerate(cells):
                mm = re.match(r"KRA (\d+):", c.strip())
                if mm:
                    out[cur][int(mm.group(1))] = cells[i + 1].strip()
    return out


def main():
    wb = openpyxl.load_workbook(XLSX)
    kras, targets = read_catalogue(wb), read_targets(wb)
    norm = lambda s: re.sub(r"\s+", " ", s.replace("\\", "")).strip()
    md = md_targets()
    mismatches = [
        (d, n) for d, t in targets.items() for n, v in t.items() if norm(v) != norm(md[d].get(n, ""))
    ]
    if mismatches:
        sys.exit(f"XLSX/MD target mismatch: {mismatches}")
    seed = {
        "source": {"workbook": str(XLSX.relative_to(ROOT)).replace("\\", "/")},
        "academic_year": "2026-27",
        "departments": [{"code": c, "name": n} for c, n in DEPARTMENTS.items()],
        "kras": [kras[n] for n in range(1, 46)],
        "targets": {d: {str(n): t[n] for n in range(1, 46)} for d, t in targets.items()},
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(seed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(kras)} KRAs x {len(targets)} departments, MD cross-check OK")


if __name__ == "__main__":
    main()
