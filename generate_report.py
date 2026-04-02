from pathlib import Path
from datetime import datetime
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BLUE = "1C2578"
LIGHT_BLUE = "DCE6F1"
SAFFRON = "FF6B00"
WHITE = "FFFFFF"
LIGHT_GREY = "F2F2F2"

def thin_border():
    s = Side(style='thin')
    return Border(left=s, right=s, top=s, bottom=s)

def header_style(cell, bg=BLUE, fg=WHITE, size=11, bold=True):
    cell.font = Font(name="Arial", bold=bold, color=fg, size=size)
    cell.fill = PatternFill("solid", start_color=bg)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = thin_border()

def data_style(cell, bold=False, bg=WHITE, align="left", num_fmt=None):
    cell.font = Font(name="Arial", bold=bold, size=10)
    cell.fill = PatternFill("solid", start_color=bg)
    cell.alignment = Alignment(horizontal=align, vertical="center")
    cell.border = thin_border()
    if num_fmt:
        cell.number_format = num_fmt

def generate_collections_report(history: list, month_label: str, output_path: Path):
    active = [h for h in history if h.get("status", "ACTIVE") != "CANCELLED"]

    wb = Workbook()

    # ── Sheet 1: Collections by Date ──────────────────────────
    ws1 = wb.active
    ws1.title = "By Date"

    ws1.merge_cells("A1:G1")
    title = ws1["A1"]
    title.value = f"PIRANJERI TEMPLES FAMILY TRUST — Collections Report ({month_label})"
    title.font = Font(name="Arial", bold=True, size=13, color=WHITE)
    title.fill = PatternFill("solid", start_color=BLUE)
    title.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 30

    headers = ["Receipt No.", "Date", "Donor Name", "Purpose", "Payment", "Amount (Rs.)", "Issued By"]
    for col, h in enumerate(headers, 1):
        cell = ws1.cell(row=2, column=col, value=h)
        header_style(cell, bg=SAFFRON)

    sorted_data = sorted(active, key=lambda x: x.get("issue_date", ""))
    total = 0
    for row_idx, h in enumerate(sorted_data, 3):
        bg = LIGHT_GREY if row_idx % 2 == 0 else WHITE
        values = [
            h.get("serial", ""),
            h.get("issue_date", ""),
            h.get("name", ""),
            h.get("purpose", ""),
            h.get("payment", ""),
            float(h.get("amount", 0)),
            h.get("user", ""),
        ]
        for col, val in enumerate(values, 1):
            cell = ws1.cell(row=row_idx, column=col, value=val)
            align = "right" if col == 6 else "left"
            num_fmt = "#,##0.00" if col == 6 else None
            data_style(cell, bg=bg, align=align, num_fmt=num_fmt)
        total += float(h.get("amount", 0))

    total_row = len(sorted_data) + 3
    ws1.merge_cells(f"A{total_row}:E{total_row}")
    tc = ws1.cell(row=total_row, column=1, value="TOTAL COLLECTIONS")
    header_style(tc, bg=BLUE)
    ws1.merge_cells(f"A{total_row}:E{total_row}")
    amt = ws1.cell(row=total_row, column=6, value=f"=SUM(F3:F{total_row-1})")
    header_style(amt, bg=BLUE)
    amt.number_format = "#,##0.00"
    ws1.cell(row=total_row, column=7).fill = PatternFill("solid", start_color=BLUE)

    col_widths = [14, 14, 28, 30, 16, 16, 14]
    for i, w in enumerate(col_widths, 1):
        ws1.column_dimensions[get_column_letter(i)].width = w

    # ── Sheet 2: By Donor ──────────────────────────────────────
    ws2 = wb.create_sheet("By Donor")
    ws2.merge_cells("A1:C1")
    t2 = ws2["A1"]
    t2.value = f"Collections by Donor — {month_label}"
    t2.font = Font(name="Arial", bold=True, size=13, color=WHITE)
    t2.fill = PatternFill("solid", start_color=BLUE)
    t2.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 30

    for col, h in enumerate(["Donor Name", "No. of Receipts", "Total Amount (Rs.)"], 1):
        cell = ws2.cell(row=2, column=col, value=h)
        header_style(cell, bg=SAFFRON)

    donor_totals = {}
    for h in active:
        name = h.get("name", "Unknown")
        donor_totals[name] = donor_totals.get(name, {"count": 0, "total": 0})
        donor_totals[name]["count"] += 1
        donor_totals[name]["total"] += float(h.get("amount", 0))

    for row_idx, (name, vals) in enumerate(sorted(donor_totals.items()), 3):
        bg = LIGHT_GREY if row_idx % 2 == 0 else WHITE
        for col, val in enumerate([name, vals["count"], vals["total"]], 1):
            cell = ws2.cell(row=row_idx, column=col, value=val)
            align = "right" if col in (2, 3) else "left"
            num_fmt = "#,##0.00" if col == 3 else None
            data_style(cell, bg=bg, align=align, num_fmt=num_fmt)

    tr2 = len(donor_totals) + 3
    ws2.cell(row=tr2, column=1, value="TOTAL").font = Font(name="Arial", bold=True)
    header_style(ws2.cell(row=tr2, column=1, value="TOTAL"), bg=BLUE)
    c2 = ws2.cell(row=tr2, column=2, value=f"=SUM(B3:B{tr2-1})")
    header_style(c2, bg=BLUE)
    a2 = ws2.cell(row=tr2, column=3, value=f"=SUM(C3:C{tr2-1})")
    header_style(a2, bg=BLUE)
    a2.number_format = "#,##0.00"

    for i, w in enumerate([30, 18, 22], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # ── Sheet 3: By Purpose ────────────────────────────────────
    ws3 = wb.create_sheet("By Purpose")
    ws3.merge_cells("A1:C1")
    t3 = ws3["A1"]
    t3.value = f"Collections by Purpose — {month_label}"
    t3.font = Font(name="Arial", bold=True, size=13, color=WHITE)
    t3.fill = PatternFill("solid", start_color=BLUE)
    t3.alignment = Alignment(horizontal="center", vertical="center")
    ws3.row_dimensions[1].height = 30

    for col, h in enumerate(["Purpose", "No. of Receipts", "Total Amount (Rs.)"], 1):
        cell = ws3.cell(row=2, column=col, value=h)
        header_style(cell, bg=SAFFRON)

    purpose_totals = {}
    for h in active:
        purpose = h.get("purpose", "Unknown")
        purpose_totals[purpose] = purpose_totals.get(purpose, {"count": 0, "total": 0})
        purpose_totals[purpose]["count"] += 1
        purpose_totals[purpose]["total"] += float(h.get("amount", 0))

    for row_idx, (purpose, vals) in enumerate(sorted(purpose_totals.items()), 3):
        bg = LIGHT_GREY if row_idx % 2 == 0 else WHITE
        for col, val in enumerate([purpose, vals["count"], vals["total"]], 1):
            cell = ws3.cell(row=row_idx, column=col, value=val)
            align = "right" if col in (2, 3) else "left"
            num_fmt = "#,##0.00" if col == 3 else None
            data_style(cell, bg=bg, align=align, num_fmt=num_fmt)

    tr3 = len(purpose_totals) + 3
    header_style(ws3.cell(row=tr3, column=1, value="TOTAL"), bg=BLUE)
    c3 = ws3.cell(row=tr3, column=2, value=f"=SUM(B3:B{tr3-1})")
    header_style(c3, bg=BLUE)
    a3 = ws3.cell(row=tr3, column=3, value=f"=SUM(C3:C{tr3-1})")
    header_style(a3, bg=BLUE)
    a3.number_format = "#,##0.00"

    for i, w in enumerate([35, 18, 22], 1):
        ws3.column_dimensions[get_column_letter(i)].width = w

    wb.save(str(output_path))
    return output_path
