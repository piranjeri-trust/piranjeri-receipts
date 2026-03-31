import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

def get_sheets_client():
    creds_info = {
        "type": st.secrets["google_drive"]["type"],
        "project_id": st.secrets["google_drive"]["project_id"],
        "private_key_id": st.secrets["google_drive"]["private_key_id"],
        "private_key": st.secrets["google_drive"]["private_key"],
        "client_email": st.secrets["google_drive"]["client_email"],
        "client_id": st.secrets["google_drive"]["client_id"],
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)

def log_to_sheets(record: dict):
    """Append one receipt record as a row in Google Sheet."""
    client = get_sheets_client()
    spreadsheet_id = st.secrets["google_drive"]["spreadsheet_id"]
    sheet = client.open_by_key(spreadsheet_id).sheet1

    # Write headers if sheet is empty
    existing = sheet.get_all_values()
    if not existing:
        sheet.append_row(list(record.keys()))

    sheet.append_row(list(record.values()))
```

---

### 3. Add to `requirements.txt`
```
gspread
