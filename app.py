import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# ---------------- LOGIN CONFIG ----------------
USERS = {
    "esrivasan": "Password1",
    "pmk45in": "Password2",
    "admin3": "Password3"
}

SESSION_TIMEOUT = 15  # minutes

# ---------------- FILES ----------------
BASE_DIR = os.path.dirname(__file__)
DONOR_FILE = os.path.join(BASE_DIR, "donors.csv")
COUNTER_FILE = os.path.join(BASE_DIR, "serial_counter.json")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")

# ---------------- INIT FILES ----------------
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w") as f:
        json.dump([], f)

# ---------------- LOGIN ----------------
def login():
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in USERS and USERS[username] == password:
            st.session_state["user"] = username
            st.session_state["login_time"] = datetime.now()
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

def check_session():
    if "login_time" in st.session_state:
        if datetime.now() - st.session_state["login_time"] > timedelta(minutes=SESSION_TIMEOUT):
            st.session_state.clear()
            st.warning("Session expired. Login again.")
            st.rerun()

# ---------------- SERIAL ----------------
def get_serial():
    year = datetime.now().year

    if not os.path.exists(COUNTER_FILE):
        data = {"year": year, "count": 1}
    else:
        with open(COUNTER_FILE) as f:
            data = json.load(f)

        if data["year"] != year:
            data = {"year": year, "count": 1}
        else:
            data["count"] += 1

    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f)

    return f"{data['count']:03d}/{year}"

# ---------------- DONORS ----------------
def load_donors():
    return pd.read_csv(DONOR_FILE)

def save_donors(df):
    df.to_csv(DONOR_FILE, index=False)

# ---------------- HISTORY ----------------
def save_history(record):
    with open(HISTORY_FILE, "r") as f:
        data = json.load(f)

    data.append(record)

    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f)

def load_history():
    with open(HISTORY_FILE) as f:
        return json.load(f)

# ---------------- MAIN APP ----------------
if "user" not in st.session_state:
    login()
    st.stop()

check_session()

st.title("Piranjeri Temple Receipt Generator")

# ---------------- DONOR SEARCH ----------------
donors = load_donors()

query = st.text_input("Search donor")

filtered = donors[
    donors["NAME"].str.contains(query, case=False, na=False) |
    donors["Mobile Number"].astype(str).str.contains(query, na=False)
]

selected = st.selectbox(
    "Select donor",
    filtered.apply(lambda x: f"{x['NAME']} - {x['Mobile Number']}", axis=1)
)

name, mobile = selected.split(" - ")

# ---------------- ADD DONOR ----------------
with st.expander("➕ Add New Donor"):
    new_name = st.text_input("New donor name")
    new_mobile = st.text_input("Mobile number")

    if st.button("Add donor"):
        if new_name and new_mobile:
            donors.loc[len(donors)] = [new_name, new_mobile]
            save_donors(donors)
            st.success("Donor added. Refresh page.")
        else:
            st.error("Enter both fields")

# ---------------- FORM ----------------
amount = st.number_input("Amount", min_value=1.0)

purpose = st.selectbox("Purpose", [
    "Nithya Pooja",
    "Garuda Seva",
    "Pradhosham",
    "Sagabhishekam",
    "Panguni uthiram",
    "Annadhanam",
    "Kumbhabhishekam",
    "Varushabhishekam",
    "Temple Renovation"
])

payment = st.selectbox("Payment method", ["cash", "cheque", "bank transfer"])

note = st.text_input("Optional note")

# ---------------- GENERATE ----------------
if st.button("Generate Receipt"):
    serial = get_serial()

    record = {
        "serial": serial,
        "name": name,
        "mobile": mobile,
        "amount": amount,
        "purpose": purpose,
        "payment": payment,
        "date": str(datetime.now())
    }

    save_history(record)

    st.success(f"Receipt Generated: {serial}")

# ---------------- HISTORY ----------------
st.subheader("📜 Receipt History")

history = load_history()

for h in history[::-1]:
    st.write(f"{h['serial']} | {h['name']} | Rs.{h['amount']} | {h['purpose']}")
