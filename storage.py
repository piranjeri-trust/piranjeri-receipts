import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import json

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_sheets_client():
    creds_info = json.loads(st.secrets["google_service_account_json"])
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)

def load_donors_from_sheets():
    client = get_sheets_client()
    sheet = client.open_by_key(st.secrets["google_sheets"]["spreadsheet_id"]).worksheet("Donors")
    rows = sheet.get_all_records()
    return rows

def log_to_sheets(record: dict):
    client = get_sheets_client()
    sheet = client.open_by_key(st.secrets["google_sheets"]["spreadsheet_id"]).worksheet("Receipts")
    existing = sheet.get_all_values()
    if not existing:
        sheet.append_row(list(record.keys()))
    sheet.append_row(list(record.values()))
