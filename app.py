
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st

from receipt_core import generate_receipt_pdf

st.set_page_config(page_title="Piranjeri Temple Receipt Generator", layout="centered")

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "donors.csv"
OUT_DIR = BASE_DIR / "generated_receipts"
COUNTER_PATH = BASE_DIR / "serial_counter.json"
OM_PATH = BASE_DIR / "om_saffron.png"
OUT_DIR.mkdir(exist_ok=True)

PURPOSES = [
    "Nithya Pooja",
    "Garuda Seva",
    "Pradhosham",
    "Sagabhishekam",
    "Panguni uthiram",
    "Annadhanam",
    "Kumbhabhishekam",
    "Varushabhishekam",
    "Temple Renovation",
]

st.title("Piranjeri Temple Receipt Generator")
st.caption("Search donor by first 3 letters of name or by mobile number, then generate the receipt PDF.")

@st.cache_data
def load_donors():
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]
    df["NAME"] = df["NAME"].astype(str).str.strip()
    df["Mobile Number"] = df["Mobile Number"].astype(str).str.strip()
    return df

donors = load_donors()

query = st.text_input("Type donor name or mobile number")
matches = donors.copy()
if query.strip():
    q = query.strip().lower()
    matches = donors[
        donors["NAME"].str.lower().str.contains(q, na=False)
        | donors["Mobile Number"].str.contains(q, na=False)
    ]

if len(matches) == 0:
    st.warning("No donor found.")
    st.stop()

display_options = [
    f"{row['NAME']} — {row['Mobile Number']}"
    for _, row in matches.head(20).iterrows()
]
selected = st.selectbox("Matching donors", display_options)
selected_row = matches.head(20).iloc[display_options.index(selected)]

donor_name = selected_row["NAME"]
donor_mobile = str(selected_row["Mobile Number"])

col1, col2 = st.columns(2)
with col1:
    amount = st.number_input("Amount received (Rs.)", min_value=1.0, step=1.0, format="%.2f")
    credit_date = st.date_input("Date of credit into trust bank account", value=datetime.today())
    payment_method = st.selectbox("Payment method", ["cash", "cheque", "bank_transfer"])

with col2:
    issue_date = st.date_input("Receipt issue date", value=datetime.today())
    purpose = st.selectbox("Towards", PURPOSES)
    optional_note = st.text_input("Optional note")

cheque_number = ""
if payment_method == "cheque":
    cheque_number = st.text_input("Cheque number")

if st.button("Generate receipt PDF", type="primary"):
    safe_name = "".join(ch for ch in donor_name if ch.isalnum() or ch in (" ", "_", "-")).strip().replace(" ", "_")
    out_file = OUT_DIR / f"receipt_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    full_purpose = purpose if not optional_note.strip() else f"{purpose} - {optional_note.strip()}"

    meta = generate_receipt_pdf(
        output_path=out_file,
        donor_name=donor_name,
        donor_mobile=donor_mobile,
        amount=float(amount),
        credit_date=credit_date.strftime("%Y-%m-%d"),
        issue_date=issue_date.strftime("%Y-%m-%d"),
        receipt_for=full_purpose,
        counter_path=COUNTER_PATH,
        om_image_path=OM_PATH,
        payment_method=payment_method,
        cheque_number=cheque_number,
    )

    st.success(f"Receipt generated. Receipt No: {meta['receipt_number']}")
    with open(out_file, "rb") as f:
        st.download_button(
            "Download PDF receipt",
            data=f.read(),
            file_name=out_file.name,
            mime="application/pdf",
        )

    clean_phone = "".join(ch for ch in donor_mobile if ch.isdigit())
    msg = (
        f"Vanakkam {donor_name}, your donation receipt from Piranjeri Temples Family Trust "
        f"(Receipt No. {meta['receipt_number']}) is ready. Please find the PDF attached."
    )
    whatsapp_url = f"https://wa.me/{clean_phone}?text=" + msg.replace(" ", "%20")
    st.markdown(f"[Open WhatsApp chat with message]({whatsapp_url})")

    st.info("Automatic WhatsApp attachment sending needs WhatsApp Business API setup.")