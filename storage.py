from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
import streamlit as st

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def upload_to_drive(file_path, file_name):
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
    service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name": file_name,
        "parents": [st.secrets["google_drive"]["folder_id"]],
    }

    media = MediaFileUpload(file_path, mimetype="application/pdf")

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    return uploaded["id"], uploaded.get("webViewLink", "")
