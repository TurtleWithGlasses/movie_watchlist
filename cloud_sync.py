"""
Google Drive sync for watchlist.db.

Setup (one-time):
  1. Go to https://console.cloud.google.com
  2. Create a project → Enable "Google Drive API"
  3. OAuth consent screen → External → Testing → add your Gmail as test user
  4. Credentials → Create → OAuth client ID → Desktop app → Download JSON
  5. Rename the downloaded file to  credentials.json  and put it next to the exe
  6. First run: a browser tab opens → sign in → grant access → token.json is saved
  7. From then on the app syncs silently with no browser prompt.
"""

import io
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

DRIVE_FILE_ID = "1GOlrITdRU87fWTSPPIj5MrEEJuQ9Rgyn"
_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _credentials_path():
    return os.path.join(_app_dir(), "credentials.json")


def _token_path():
    return os.path.join(_app_dir(), "token.json")


def is_configured():
    """Return True if credentials.json or token.json is present."""
    return os.path.exists(_credentials_path()) or os.path.exists(_token_path())


def _get_service():
    creds = None
    token_path = _token_path()
    creds_path = _credentials_path()

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, _SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def download_db(local_path):
    """Overwrite local_path with the file from Google Drive."""
    service = _get_service()
    request = service.files().get_media(fileId=DRIVE_FILE_ID)
    with io.FileIO(local_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def upload_db(local_path):
    """Replace the Google Drive file with the current local_path."""
    service = _get_service()
    media = MediaFileUpload(local_path, mimetype="application/x-sqlite3", resumable=False)
    service.files().update(fileId=DRIVE_FILE_ID, media_body=media).execute()
