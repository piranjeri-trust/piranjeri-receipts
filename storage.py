import json
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_sheets_client():
    creds_info = json.loads(st.secrets["google_service_account_json"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)

def log_to_sheets(record: dict):
    client = get_sheets_client()
    spreadsheet_id = st.secrets["google_sheets"]["spreadsheet_id"]

    st.write("DEBUG spreadsheet_id:", spreadsheet_id)
    st.write("DEBUG client_email:", json.loads(st.secrets["google_service_account_json"])["client_email"])

    sheet = client.open_by_key(spreadsheet_id).get_worksheet(0)

    existing = sheet.get_all_values()
    if not existing:
        sheet.append_row(list(record.keys()))

    sheet.append_row(list(record.values()))
