
from pathlib import Path
import os
import json
import io

def cloud_archive_note() -> str:
    return (
        "Local download always works. Google Drive upload works after service-account credentials "
        "and folder ID are added in deployment secrets."
    )


def upload_to_google_drive_if_configured(local_pdf_path: Path, folder_year: int, subfolder_name: str):
    """
    Returns a dict:
    {
        "status": "uploaded" | "disabled" | "error",
        "file_id": "...",
        "web_link": "...",
        "message": "..."
    }
    """
    local_pdf_path = Path(local_pdf_path)

    try:
        import streamlit as st
        secrets = st.secrets
    except Exception:
        secrets = {}

    if "gdrive_service_account_json" not in secrets or "gdrive_parent_folder_id" not in secrets:
        return {"status": "disabled", "file_id": None, "web_link": None, "message": "Google Drive not configured."}

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except Exception as e:
        return {"status": "error", "file_id": None, "web_link": None, "message": f"Google packages not installed: {e}"}

    try:
        service_info = json.loads(secrets["gdrive_service_account_json"])
        parent_folder_id = secrets["gdrive_parent_folder_id"]

        creds = service_account.Credentials.from_service_account_info(
            service_info,
            scopes=["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        )
        service = build("drive", "v3", credentials=creds)

        year_name = str(folder_year)

        def find_or_create_folder(name, parent_id):
            query = (
                "mimeType='application/vnd.google-apps.folder' and "
                f"name='{name}' and '{parent_id}' in parents and trashed=false"
            )
            results = service.files().list(q=query, fields="files(id, name)").execute().get("files", [])
            if results:
                return results[0]["id"]
            metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }
            created = service.files().create(body=metadata, fields="id").execute()
            return created["id"]

        trust_folder_id = find_or_create_folder(subfolder_name, parent_folder_id)
        year_folder_id = find_or_create_folder(year_name, trust_folder_id)

        metadata = {"name": local_pdf_path.name, "parents": [year_folder_id]}
        media = MediaFileUpload(str(local_pdf_path), mimetype="application/pdf", resumable=False)
        created = service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()

        return {
            "status": "uploaded",
            "file_id": created.get("id"),
            "web_link": created.get("webViewLink"),
            "message": "Uploaded to Google Drive.",
        }

    except Exception as e:
        return {"status": "error", "file_id": None, "web_link": None, "message": str(e)}
