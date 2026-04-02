import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from receipt_core import generate_receipt_pdf
from storage import (
    load_history, save_history, cancel_receipt, get_serial,
    load_donors_from_sheets, save_donor_to_sheets, update_donor_in_sheets,
    reset_serial_counter
)

# ---------------- LOGIN CONFIG ----------------
USERS = {
    "esrivasan": "Password1",
    "pmk45in": "Password2",
    "admin3": "Password3"
}

SESSION_TIMEOUT = 15  # minutes

# ---------------- FILES ----------------
BASE_DIR = Path(__file__).resolve().parent
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
COUNTRY_CODES = {
    "India (+91)": "91",
    "Singapore (+65)": "65",
    "Malaysia (+60)": "60",
    "UAE (+971)": "971",
    "Oman (+968)": "968",
    "UK (+44)": "44",
    "USA (+1)": "1"
}

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

def normalize_mobile(mobile: str) -> str:
    return "".join(ch for ch in str(mobile) if ch.isdigit())

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

# ---------------- LOAD DONORS ----------------
@st.cache_data(ttl=60)
def get_donors():
    rows = load_donors_from_sheets()
    if not rows:
        return pd.DataFrame(columns=["NAME", "Mobile Number"])
    df = pd.DataFrame(rows)
    if "NAME" not in df.columns:
        df["NAME"] = ""
    if "Mobile Number" not in df.columns:
        df["Mobile Number"] = ""
    df["NAME"] = df["NAME"].astype(str).str.strip()
    df["Mobile Number"] = df["Mobile Number"].astype(str).str.strip()
    return df.sort_values("NAME").reset_index(drop=True)

donors = get_donors()

# ---------------- SELECT DONOR ----------------
if donors.empty:
    st.warning("No donor found. You can add a new donor below.")
    selected = None
    selected_index = None
else:
    donor_options = [
        f"{row['NAME']} - {row['Mobile Number']}"
        for _, row in donors.iterrows()
    ]
    selected = st.selectbox("Select donor", donor_options)
    selected_index = donors.index[donor_options.index(selected)]

# ---------------- ADD DONOR ----------------
with st.expander("Add New Donor"):
    new_name = st.text_input("New donor name")
    new_country = st.selectbox("Country code", list(COUNTRY_CODES.keys()), key="add_country")
    new_mobile = st.text_input("New donor mobile number (without country code)")

    if st.button("Save New Donor"):
        nm = new_name.strip()
        raw_mobile = normalize_mobile(new_mobile)
        mm = COUNTRY_CODES[new_country] + raw_mobile

        if not nm or not raw_mobile:
            st.error("Enter both donor name and mobile number.")
        else:
            duplicate = donors[
                (donors["NAME"].str.lower() == nm.lower()) &
                (donors["Mobile Number"].astype(str) == mm)
            ]
            if not duplicate.empty:
                st.warning("This donor already exists.")
            else:
                save_donor_to_sheets(nm, mm)
                st.success("New donor added.")
                st.cache_data.clear()
                st.rerun()

# ---------------- EDIT DONOR ----------------
if selected is not None:
    with st.expander("Edit Selected Donor"):
        current_name = donors.loc[selected_index, "NAME"]
        current_mobile = str(donors.loc[selected_index, "Mobile Number"])

        default_country = "India (+91)"
        default_local = current_mobile

        for label, code in COUNTRY_CODES.items():
            if current_mobile.startswith(code):
                default_country = label
                default_local = current_mobile[len(code):]
                break

        edit_name = st.text_input("Edit donor name", value=current_name)
        edit_country = st.selectbox(
            "Edit country code",
            list(COUNTRY_CODES.keys()),
            index=list(COUNTRY_CODES.keys()).index(default_country),
            key="edit_country"
        )
        edit_mobile = st.text_input("Edit donor mobile number (without country code)", value=default_local)

        if st.button("Update Donor"):
            en = edit_name.strip()
            raw_mobile = normalize_mobile(edit_mobile)
            em = COUNTRY_CODES[edit_country] + raw_mobile

            if not en or not raw_mobile:
                st.error("Name and mobile number cannot be empty.")
            else:
                update_donor_in_sheets(current_name, current_mobile, en, em)
                st.success("Donor updated successfully.")
                st.cache_data.clear()
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
        optional_note = st.text_input("Optional note")

    cheque_number = ""
    if payment_method == "cheque":
        cheque_number = st.text_input("Cheque number")

    if st.button("Generate Receipt", type="primary"):
        final_purpose = purpose
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
            counter_path=None,
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
            "cheque_number": cheque_number,
            "issue_date": issue_date.strftime("%Y-%m-%d"),
            "credit_date": credit_date.strftime("%Y-%m-%d"),
            "user": st.session_state["user"],
            "pdf_file": str(out_file.name),
            "status": "ACTIVE",
            "cancelled_by": "",
            "cancelled_at": "",
            "cancel_reason": "",
        }
        save_history(record)

        st.success(f"Receipt generated: {receipt_number}")
        st.success("✅ Receipt saved to Google Sheets.")

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
        full_mobile = normalize_mobile(donor_mobile)
        whatsapp_url = f"https://wa.me/{full_mobile}?text={whatsapp_text.replace(' ', '%20')}"
        st.markdown(f"[Open WhatsApp chat]({whatsapp_url})")

# ---------------- RECEIPT HISTORY ----------------
st.subheader("Receipt History")

history = load_history()

if not history:
    st.info("No receipts generated yet.")
else:
    from collections import defaultdict
    grouped = defaultdict(list)
    for h in history:
        try:
            dt = datetime.strptime(h["issue_date"], "%Y-%m-%d")
            key = dt.strftime("%B %Y")
        except:
            key = "Unknown"
        grouped[key].append(h)

    for month_label in sorted(grouped.keys(), reverse=True):
        entries = grouped[month_label]
        with st.expander(f"📁 {month_label}  ({len(entries)} receipts)"):
            for h in sorted(entries, key=lambda x: x["serial"], reverse=True):
                status = h.get("status", "ACTIVE")
                if status == "CANCELLED":
                    st.markdown(
                        f"~~{h['serial']}~~ | {h['name']} | Rs.{h['amount']} | "
                        f"{h['purpose']} | {h['payment']} | "
                        f"❌ CANCELLED by {h.get('cancelled_by','')} — {h.get('cancel_reason','')}"
                    )
                else:
                    st.write(
                        f"{h['serial']} | {h['name']} | Rs.{h['amount']} | "
                        f"{h['purpose']} | {h['payment']} | {h.get('user', '')}"
                    )

# ---------------- REPRINT & CANCEL ----------------
st.subheader("Reprint / Cancel Receipt")

search_col1, search_col2, search_col3 = st.columns(3)

with search_col1:
    search_receipt_no = st.text_input("Search by Receipt Number")

with search_col2:
    search_mobile = st.text_input("Search by Mobile Number")

with search_col3:
    search_issue_date_enabled = st.checkbox("Filter by Issue Date")
    search_issue_date = None
    if search_issue_date_enabled:
        search_issue_date = st.date_input("Select Issue Date", value=datetime.today())

filtered_history = history

if search_receipt_no.strip():
    filtered_history = [
        h for h in filtered_history
        if search_receipt_no.strip().lower() in str(h.get("serial", "")).lower()
    ]

if search_mobile.strip():
    mobile_q = normalize_mobile(search_mobile)
    filtered_history = [
        h for h in filtered_history
        if mobile_q in normalize_mobile(str(h.get("mobile", "")))
    ]

if search_issue_date:
    issue_q = search_issue_date.strftime("%Y-%m-%d")
    filtered_history = [
        h for h in filtered_history
        if str(h.get("issue_date", "")) == issue_q
    ]

if search_receipt_no.strip() or search_mobile.strip() or search_issue_date_enabled:
    if filtered_history:
        for i, h in enumerate(filtered_history[::-1]):
            status = h.get("status", "ACTIVE")
            st.divider()

            if status == "CANCELLED":
                st.markdown(
                    f"~~{h['serial']}~~ | {h['name']} | Rs.{h['amount']} | "
                    f"{h['purpose']} | ❌ **CANCELLED** by {h.get('cancelled_by','')} — _{h.get('cancel_reason','')}_"
                )
            else:
                st.write(
                    f"{h['serial']} | {h['name']} | Rs.{h['amount']} | "
                    f"{h['purpose']} | {h['payment']}"
                )
                btn1, btn2 = st.columns(2)
                with btn1:
                    if st.button("🖨️ Reprint", key=f"reprint_{i}_{h['serial']}"):
                        out_file = OUT_DIR / h["pdf_file"]
                        generate_receipt_pdf(
                            output_path=out_file,
                            donor_name=h["name"],
                            donor_mobile=h["mobile"],
                            amount=float(h["amount"]),
                            credit_date=h["credit_date"],
                            issue_date=h["issue_date"],
                            receipt_for=h["purpose"],
                            counter_path=None,
                            om_image_path=OM_PATH,
                            payment_method=h["payment"],
                            cheque_number=h.get("cheque_number", ""),
                            receipt_number_override=h["serial"],
                        )
                        st.success(f"Reprinted receipt {h['serial']}")
                        with open(out_file, "rb") as f:
                            st.download_button(
                                f"Download {h['serial']}",
                                f.read(),
                                file_name=out_file.name,
                                mime="application/pdf",
                                key=f"download_reprint_{i}_{h['serial']}"
                            )
                with btn2:
                    if st.button("❌ Cancel", key=f"cancel_{i}_{h['serial']}"):
                        st.session_state[f"confirm_cancel_{h['serial']}"] = True

            if st.session_state.get(f"confirm_cancel_{h['serial']}", False):
                st.warning(f"Cancel receipt {h['serial']} — {h['name']} — Rs.{h['amount']}?")
                cancel_reason = st.text_input("Reason for cancellation (required)", key=f"reason_{h['serial']}")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("Confirm Cancel", key=f"confirm_{h['serial']}"):
                        if not cancel_reason.strip():
                            st.error("Please enter a reason.")
                        else:
                            cancel_receipt(h["serial"], st.session_state["user"], cancel_reason.strip())
                            from receipt_core import generate_cancelled_pdf
                            orig_file = OUT_DIR / h["pdf_file"]
                            cancelled_file = OUT_DIR / f"CANCELLED_{h['pdf_file']}"
                            generate_cancelled_pdf(
                                original_path=orig_file,
                                output_path=cancelled_file,
                                cancelled_by=st.session_state["user"],
                                reason=cancel_reason.strip(),
                                cancelled_at=datetime.now().isoformat()
                            )
                            st.session_state[f"cancelled_file_{h['serial']}"] = str(cancelled_file)
                            st.session_state.pop(f"confirm_cancel_{h['serial']}", None)
                            st.rerun()
                with col_no:
                    if st.button("No, go back", key=f"abort_{h['serial']}"):
                        st.session_state.pop(f"confirm_cancel_{h['serial']}", None)
                        st.rerun()

            cancelled_key = f"cancelled_file_{h['serial']}"
            if st.session_state.get(cancelled_key):
                cancelled_file = Path(st.session_state[cancelled_key])
                if cancelled_file.exists():
                    with open(cancelled_file, "rb") as cf:
                        st.download_button(
                            "⬇️ Download Cancelled Receipt",
                            cf.read(),
                            file_name=cancelled_file.name,
                            mime="application/pdf",
                            key=f"dl_cancelled_{h['serial']}"
                        )
    else:
        st.warning("No matching receipt found.")

# ---------------- COLLECTIONS REPORT ----------------
st.subheader("📊 Collections Report")

if not history:
    st.info("No receipts yet to generate a report.")
else:
    from collections import defaultdict
    from generate_report import generate_collections_report

    active_history = [h for h in history if h.get("status", "ACTIVE") != "CANCELLED"]

    months_available = sorted(set(
        datetime.strptime(h["issue_date"], "%Y-%m-%d").strftime("%B %Y")
        for h in active_history
        if h.get("issue_date")
    ), reverse=True)

    if months_available:
        selected_month = st.selectbox("Select month to generate report", months_available)

        if st.button("📥 Generate & Download Excel Report", type="primary"):
            month_data = [
                h for h in active_history
                if datetime.strptime(h["issue_date"], "%Y-%m-%d").strftime("%B %Y") == selected_month
            ]

            REPORTS_DIR = BASE_DIR / "reports"
            REPORTS_DIR.mkdir(exist_ok=True)
            safe_month = selected_month.replace(" ", "_")
            report_file = REPORTS_DIR / f"Collections_{safe_month}.xlsx"

            generate_collections_report(month_data, selected_month, report_file)

            with open(report_file, "rb") as f:
                st.session_state["report_bytes"] = f.read()
            st.session_state["report_filename"] = report_file.name
            st.session_state["report_month"] = selected_month
            st.session_state["report_count"] = len(month_data)

        if st.session_state.get("report_bytes"):
            st.download_button(
                f"⬇️ Download {st.session_state['report_month']} Report",
                st.session_state["report_bytes"],
                file_name=st.session_state["report_filename"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="report_download"
            )
            st.success(
                f"✅ Report generated for {st.session_state['report_month']} "
                f"— {st.session_state['report_count']} receipts."
            )

# ---------------- ADMIN PANEL ----------------
if st.session_state.get("user") == "admin3":
    st.subheader("🔧 Admin Panel")
    with st.expander("Reset Serial Counter"):
        st.warning("⚠️ Only reset at start of new financial year or if counter is wrong.")
        reset_year = st.number_input("Financial Year", value=datetime.now().year, step=1, format="%d")
        reset_count = st.number_input("Start from (next receipt will be this + 1)", value=0, step=1, format="%d")
        if st.button("Reset Counter", type="primary"):
            reset_serial_counter(int(reset_year), int(reset_count))
            st.success(f"Counter reset. Next receipt will be {int(reset_count)+1:03d}/{int(reset_year)}")
