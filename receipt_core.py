from pathlib import Path
from datetime import datetime
import json
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

TRUST_NAME = "PIRANJERI TEMPLES FAMILY TRUST"
REGISTERED_ADDRESS = "26A, Lake View Main Road, Madipakkam, Chennai - 600 091."
EMAIL_LINE = "E-mail : pmk45in@yahoo.co.in / esrivasan@gmail.com"
HELPER_LINE = "Sri Prasanna Venkatachalapathy Sahayam"
PHONE_LINE = "Ph : 044-22471339"

PAGE_W = 842
PAGE_H = 595

BLUE = HexColor("#1c2578")
BLACK = HexColor("#111111")

FONT_REG = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

def ensure_counter(counter_path: Path):
    if counter_path and not counter_path.exists():
        counter_path.write_text(json.dumps({"year": datetime.now().year, "count": 0}, indent=2))

def format_date_dd_mm_yyyy(value):
    if isinstance(value, datetime):
        dt = value
    else:
        dt = None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %m %Y", "%d-%m-%y"):
            try:
                dt = datetime.strptime(str(value), fmt)
                break
            except Exception:
                pass
        if dt is None:
            dt = pd.to_datetime(value).to_pydatetime()
    return dt.strftime("%d %m %Y"), dt

def dotted_line(c, x1, x2, y):
    c.setDash(1, 3)
    c.line(x1, y, x2, y)
    c.setDash()

def fit_text(c, text, x_center, y, max_width, start_size, min_size=10, font_name=FONT_BOLD):
    size = start_size
    while size >= min_size and c.stringWidth(text, font_name, size) > max_width:
        size -= 0.5
    c.setFont(font_name, size)
    c.drawCentredString(x_center, y, text)

def draw_struck_option(c, x, y, text, strike=False, font_name=FONT_REG, size=14):
    c.setFont(font_name, size)
    c.drawString(x, y, text)
    if strike:
        width = c.stringWidth(text, font_name, size)
        c.line(x, y + size * 0.35, x + width, y + size * 0.35)
    return x + c.stringWidth(text, font_name, size)

def generate_receipt_pdf(
    output_path: Path,
    donor_name: str,
    donor_mobile: str,
    amount: float,
    credit_date,
    issue_date=None,
    receipt_for="Temple Development / Daily Poojas / Festivities",
    counter_path: Path = None,
    om_image_path: Path | None = None,
    payment_method: str = "bank_transfer",
    cheque_number: str = "",
    receipt_number_override: str | None = None,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if issue_date is None:
        issue_date = datetime.now()

    issue_date_str, _ = format_date_dd_mm_yyyy(issue_date)
    credit_date_str, _ = format_date_dd_mm_yyyy(credit_date)
    receipt_number = receipt_number_override or "001/2026"

    payment_method = payment_method.lower().strip()
    if payment_method not in {"cash", "cheque", "bank_transfer"}:
        payment_method = "bank_transfer"

    c = canvas.Canvas(str(output_path), pagesize=(PAGE_W, PAGE_H))

    left = 32
    right = PAGE_W - 32
    bottom = 28
    top = PAGE_H - 28
    mid = PAGE_W / 2

    c.setStrokeColor(BLUE)
    c.setLineWidth(1)
    c.rect(left, bottom, right - left, top - bottom)

    if om_image_path and Path(om_image_path).exists():
        from reportlab.lib.utils import ImageReader
        om = ImageReader(str(om_image_path))
        iw, ih = 52, 52
        c.drawImage(om, mid - iw/2, top - ih + 8, width=iw, height=ih,
                    mask='auto', preserveAspectRatio=True)
    else:
        c.setFillColor(HexColor("#FF6B00"))
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(mid, top - 38, "OM")
        c.setFillColor(BLUE)
    c.setFillColor(BLUE)
    c.setFont(FONT_REG, 10)
    c.drawCentredString(mid, top - 48, HELPER_LINE)
    c.setFont(FONT_BOLD, 10)
    c.drawRightString(right - 12, top - 48, PHONE_LINE)

    fit_text(c, TRUST_NAME, mid, top - 76, (right - left) - 120, 24, 16, FONT_BOLD)
    c.setFont(FONT_REG, 11)
    c.drawCentredString(mid, top - 98, REGISTERED_ADDRESS)
    c.drawCentredString(mid, top - 116, EMAIL_LINE)

    row_y = top - 152
    c.setFont(FONT_REG, 12)
    c.drawString(left + 24, row_y, "No.")
    c.drawString(left + 58, row_y, receipt_number)

    c.drawString(right - 170, row_y, "Date :")
    dotted_line(c, right - 118, right - 20, row_y - 2)
    c.setFillColor(BLACK)
    c.drawString(right - 114, row_y, issue_date_str)
    c.setFillColor(BLUE)

    box_w, box_h = 100, 32
    box_x = mid - box_w / 2
    box_y = row_y - 48
    c.roundRect(box_x, box_y, box_w, box_h, 8, stroke=1, fill=0)
    c.setFont(FONT_BOLD, 16)
    c.drawCentredString(mid, box_y + 10, "RECEIPT")

    label_x = left + 62
    y1 = box_y - 28
    y2 = y1 - 38
    y3 = y2 - 38
    y4 = y3 - 38

    c.setFont(FONT_REG, 14)
    label_1 = "Received from  Shri.  /  Smt."
    c.drawString(label_x, y1, label_1)
    donor_x = label_x + c.stringWidth(label_1, FONT_REG, 14) + 18
    line_x2 = right - 38
    dotted_line(c, donor_x, line_x2, y1 - 3)
    c.setFillColor(BLACK)
    c.setFont(FONT_REG, 13)
    c.drawString(donor_x + 4, y1 + 1, donor_name.upper())
    c.setFillColor(BLUE)

    c.setFont(FONT_REG, 14)
    label_2 = "the sum of Rupees"
    c.drawString(label_x, y2, label_2)
    amount_x = label_x + c.stringWidth(label_2, FONT_REG, 14) + 22
    dotted_line(c, amount_x, line_x2, y2 - 3)
    c.setFillColor(BLACK)
    c.setFont(FONT_REG, 13)
    amount_words = f"{amount:,.2f} only" if float(amount) % 1 else f"{int(amount):,} only"
    c.drawString(amount_x + 4, y2 + 1, amount_words)
    c.setFillColor(BLUE)

    c.setFont(FONT_REG, 14)
    c.drawString(label_x, y3, "by")
    x = label_x + c.stringWidth("by", FONT_REG, 14) + 12
    x = draw_struck_option(c, x, y3, "Cash", strike=(payment_method != "cash"))
    c.drawString(x + 8, y3, "/")
    x += 18
    x = draw_struck_option(c, x, y3, "Cheque", strike=(payment_method != "cheque"))
    c.drawString(x + 8, y3, "/")
    x += 18
    x = draw_struck_option(c, x, y3, "Bank Transfer", strike=(payment_method != "bank_transfer"))

    if payment_method == "cheque":
        ref_label_x = left + 500
        c.setFont(FONT_REG, 14)
        c.drawString(ref_label_x, y3, "Cheque No.")
        ref_line_x1 = ref_label_x + c.stringWidth("Cheque No.", FONT_REG, 14) + 12
        ref_line_x2 = right - 38
        dotted_line(c, ref_line_x1, ref_line_x2, y3 - 3)
        c.setFillColor(BLACK)
        c.setFont(FONT_REG, 13)
        c.drawString(ref_line_x1 + 4, y3 + 1, cheque_number.strip())
        c.setFillColor(BLUE)
    elif payment_method == "bank_transfer":
        ref_label_x = left + 500
        c.setFont(FONT_REG, 14)
        c.drawString(ref_label_x, y3, "Date of credit")
        ref_line_x1 = ref_label_x + c.stringWidth("Date of credit", FONT_REG, 14) + 12
        ref_line_x2 = right - 38
        dotted_line(c, ref_line_x1, ref_line_x2, y3 - 3)
        c.setFillColor(BLACK)
        c.setFont(FONT_REG, 13)
        c.drawString(ref_line_x1 + 4, y3 + 1, credit_date_str)
        c.setFillColor(BLUE)

    c.setFont(FONT_REG, 14)
    c.drawString(label_x, y4, "towards")
    purpose_x = left + 120
    dotted_line(c, purpose_x, line_x2, y4 - 3)
    c.setFillColor(BLACK)
    c.setFont(FONT_REG, 12)
    text = receipt_for.strip()
    max_width = line_x2 - purpose_x - 6
    while c.stringWidth(text, FONT_REG, 12) > max_width and len(text) > 10:
        text = text[:-1]
    c.drawString(purpose_x + 4, y4 + 1, text)
    c.setFillColor(BLUE)

    rs_y = bottom + 58
    c.setFont(FONT_BOLD, 14)
    c.drawString(left + 24, rs_y, "Rs.")
    dotted_line(c, left + 54, left + 170, rs_y - 3)
    c.setFillColor(BLACK)
    c.setFont(FONT_REG, 13)
    c.drawString(left + 58, rs_y + 1, f"{amount:,.2f}")
    c.setFillColor(BLUE)

    c.setFont(FONT_BOLD, 14)
    c.drawRightString(right - 38, rs_y, f"For {TRUST_NAME}")

    c.setFont(FONT_REG, 12)
    c.drawCentredString(mid, bottom + 24, "Received by")
    c.drawRightString(right - 60, bottom + 24, "Signatory")

    c.setFillColor(BLACK)
    c.setFont(FONT_REG, 9)
    c.drawCentredString(mid, bottom + 5, "Computer generated receipt. No signature required.")

    c.save()
    return {"receipt_number": receipt_number}
