import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

from receipt_core import generate_receipt_pdf

# ---------------- LOGIN CONFIG ----------------
USERS = {
    "esrivasan": "Password1",
    "pmk45in": "Password2",
    "admin3": "Password3"
}

SESSION_TIMEOUT = 15  # minutes

# ---------------- FILES ----------------
BASE_DIR = Path(__file__).resolve().parent
DONOR_FILE = BASE_DIR / "donors.csv"
COUNTER_FILE = BASE_DIR / "serial_counter.json"
HISTORY_FILE = BASE_DIR / "history.json"
OUT_DIR = BASE_DIR / "generated_receipts"
OM_PATH = BASE_DIR / "om_saffron.png"
OUT_DIR.mkdir(exist_ok=True)

PURPOSES = [
    "Nithya Pooja",
    "Garuda Seva",
    "Pradhosham",
    "Sangabhishekam",
    "Panguni uthiram",
    "Annadhanam",
    "Kumbhabhishekam",
    "Varushabhishekam",
    "Temple Renovation",
    "General Donation"
]

# ---------------- INIT FILES ----------------
if not HISTORY_FILE.exists():
    HISTORY_FILE.write_text("[]", encoding="utf-8")

if not COUNTER_FILE.exists():
    COUNTER_FILE.write_text(json.dumps({"year": datetime.now().year, "count": 0}), encoding="utf-8")

# ---------------- LOGIN ----------------
def login():
    st.title("Piranjeri Temple Receipt Generator")
    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login", type="primary"):
        if username in USERS and USERS[username] == password:
            st.session_state["user"] = username
            st.session_state["login_time"] = datetime.now().isoformat()
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

def check_session():
    if "login_time" in st.session_state:
        login_time = datetime.fromisoformat(st.session_state["login_time"])
        if datetime.now() - login_time > timedelta(minutes=SESSION_TIMEOUT):
            st.session_state.clear()
            st.warning("Session expired. Login again.")
            st.rerun()

# ---------------- SERIAL ----------------
def get_serial(issue_date: datetime):
    year = issue_date.year

    if not COUNTER_FILE.exists():
        data = {"year": year, "count": 0}
    else:
        with open(COUNTER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    if data.get("year") != year:
        data = {"year": year, "count": 0}

    data["count"] += 1

    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

    return f"{data['count']:03d}/{year}"

# ---------------- DONORS ----------------
def ensure_donor_file():
    if not DONOR_FILE.exists():
        df = pd.DataFrame(columns=["NAME", "Mobile Number"])
        df.to_csv(DONOR_FILE, index=False)

def load_donors():
    ensure_donor_file()
    df = pd.read_csv(DONOR_FILE)
    df.columns = [c.strip() for c in df.columns]
    if "NAME" not in df.columns:
        df["NAME"] = ""
    if "Mobile Number" not in df.columns:
        df["Mobile Number"] = ""
    df["NAME"] = df["NAME"].astype(str).fillna("").str.strip()
    df["Mobile Number"] = df["Mobile Number"].astype(str).fillna("").str.strip()
    return df

def save_donors(df):
    df.to_csv(DONOR_FILE, index=False)

def normalize_mobile(mobile: str) -> str:
    return "".join(ch for ch in str(mobile) if ch.isdigit())

# ---------------- HISTORY ----------------
def save_history(record):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.append(record)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_history():
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------------- APP ----------------
if "user" not in st.session_state:
    login()
    st.stop()

check_session()

st.title("Piranjeri Temple Receipt Generator")
st.caption(f"Logged in as: {st.session_state['user']}")

if st.button("Logout"):
    st.session_state.clear()
    st.rerun()

donors = load_donors()

# ---------------- SEARCH / SELECT DONOR ----------------
search = st.text_input("Search donor by name or mobile number")

filtered = donors.copy()
if search.strip():
    q = search.strip().lower()
    q_mobile = normalize_mobile(search)
    filtered = donors[
        donors["NAME"].str.lower().str.contains(q, na=False) |
        donors["Mobile Number"].astype(str).str.contains(q_mobile, na=False)
    ]

if filtered.empty:
    st.warning("No donor found. You can add a new donor below.")
    selected = None
    selected_index = None
else:
    donor_options = [
        f"{row['NAME']} - {row['Mobile Number']}"
        for _, row in filtered.iterrows()
    ]
    selected = st.selectbox("Select donor", donor_options)
    selected_index = filtered.index[donor_options.index(selected)]

# ---------------- ADD DONOR ----------------
with st.expander("Add New Donor"):
    new_name = st.text_input("New donor name")
    new_mobile = st.text_input("New donor mobile number")

    if st.button("Save New Donor"):
        nm = new_name.strip()
        mm = normalize_mobile(new_mobile)

        if not nm or not mm:
            st.error("Enter both donor name and mobile number.")
        else:
            duplicate = donors[
                (donors["NAME"].str.lower() == nm.lower()) &
                (donors["Mobile Number"].astype(str) == mm)
            ]
            if not duplicate.empty:
                st.warning("This donor already exists.")
            else:
                donors.loc[len(donors)] = [nm, mm]
                save_donors(donors)
                st.success("New donor added. Refresh search if needed.")
                st.rerun()

# ---------------- EDIT DONOR ----------------
if selected is not None:
    with st.expander("Edit Selected Donor"):
        current_name = donors.loc[selected_index, "NAME"]
        current_mobile = donors.loc[selected_index, "Mobile Number"]

        edit_name = st.text_input("Edit donor name", value=current_name)
        edit_mobile = st.text_input("Edit donor mobile number", value=current_mobile)

        if st.button("Update Donor"):
            en = edit_name.strip()
            em = normalize_mobile(edit_mobile)

            if not en or not em:
                st.error("Name and mobile number cannot be empty.")
            else:
                donors.loc[selected_index, "NAME"] = en
                donors.loc[selected_index, "Mobile Number"] = em
                save_donors(donors)
                st.success("Donor updated successfully.")
                st.rerun()

# ---------------- RECEIPT FORM ----------------
if selected is not None:
    donor_name = donors.loc[selected_index, "NAME"]
    donor_mobile = str(donors.loc[selected_index, "Mobile Number"])

    col1, col2 = st.columns(2)

    with col1:
        amount = st.number_input("Amount received (Rs.)", min_value=1.0, step=1.0, format="%.2f")
        payment_method = st.selectbox("Payment method", ["cash", "cheque", "bank_transfer"])
        credit_date = st.date_input("Date of credit into trust bank account", value=datetime.today())

    with col2:
        issue_date = st.date_input("Receipt issue date", value=datetime.today())
        purpose = st.selectbox("Purpose", PURPOSES)
        custom_purpose = st.text_input("Custom purpose (optional)")
        optional_note = st.text_input("Optional note")

    cheque_number = ""
    if payment_method == "cheque":
        cheque_number = st.text_input("Cheque number")

    if st.button("Generate Receipt", type="primary"):
        final_purpose = custom_purpose.strip() if custom_purpose.strip() else purpose
        if optional_note.strip():
            final_purpose = f"{final_purpose} - {optional_note.strip()}"

        receipt_number = get_serial(issue_date)
        safe_name = "".join(ch for ch in donor_name if ch.isalnum() or ch in (" ", "_", "-")).strip().replace(" ", "_")
        out_file = OUT_DIR / f"{receipt_number.replace('/','_')}_{safe_name}.pdf"

        meta = generate_receipt_pdf(
            output_path=out_file,
            donor_name=donor_name,
            donor_mobile=donor_mobile,
            amount=float(amount),
            credit_date=credit_date.strftime("%Y-%m-%d"),
            issue_date=issue_date.strftime("%Y-%m-%d"),
            receipt_for=final_purpose,
            counter_path=COUNTER_FILE,
            om_image_path=OM_PATH,
            payment_method=payment_method,
            cheque_number=cheque_number,
            receipt_number_override=receipt_number,
        )

        record = {
            "serial": receipt_number,
            "name": donor_name,
            "mobile": donor_mobile,
            "amount": float(amount),
            "purpose": final_purpose,
            "payment": payment_method,
            "issue_date": issue_date.strftime("%Y-%m-%d"),
            "credit_date": credit_date.strftime("%Y-%m-%d"),
            "user": st.session_state["user"],
            "pdf_file": str(out_file.name),
            "created_at": datetime.now().isoformat()
        }
        save_history(record)

        st.success(f"Receipt generated: {receipt_number}")

        with open(out_file, "rb") as f:
            st.download_button(
                "Download PDF",
                f.read(),
                file_name=out_file.name,
                mime="application/pdf"
            )

        whatsapp_text = (
            f"Vanakkam {donor_name}, your donation receipt "
            f"({receipt_number}) from Piranjeri Temples Family Trust is ready."
        )
        whatsapp_url = f"https://wa.me/{normalize_mobile(donor_mobile)}?text={whatsapp_text.replace(' ', '%20')}"
        st.markdown(f"[Open WhatsApp chat]({whatsapp_url})")

# ---------------- HISTORY ----------------
st.subheader("Receipt History")

history = load_history()
if history:
    for h in history[::-1]:
        st.write(
            f"{h['serial']} | {h['name']} | Rs.{h['amount']:.2f} | "
            f"{h['purpose']} | {h['payment']} | {h.get('user', '')}"
        )
else:
    st.info("No receipts generated yet.")
