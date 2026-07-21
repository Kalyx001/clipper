"""OAuth2 (web flow) against a user's YouTube channel, and video upload via
the YouTube Data API v3. Token is persisted to disk so re-auth isn't needed
every run (single-user app -- for multi-user, key the token file by user id).
"""
import json
from pathlib import Path

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REDIRECT_URI, STORAGE_DIR

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = STORAGE_DIR / "youtube_token.json"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [YOUTUBE_REDIRECT_URI],
        }
    }


def _new_flow() -> Flow:
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
        raise RuntimeError("YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET are not configured")
    return Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=YOUTUBE_REDIRECT_URI)


def get_auth_url() -> str:
    flow = _new_flow()
    auth_url, _state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )
    return auth_url


def handle_oauth_callback(full_callback_url: str) -> None:
    flow = _new_flow()
    flow.fetch_token(authorization_response=full_callback_url)
    creds = flow.credentials
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")


def is_connected() -> bool:
    return TOKEN_PATH.exists()


def _get_credentials() -> Credentials:
    if not TOKEN_PATH.exists():
        raise RuntimeError("YouTube is not connected yet")
    creds = Credentials.from_authorized_user_info(json.loads(TOKEN_PATH.read_text()), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str = "private",
) -> str:
    """Uploads a clip as a YouTube Short. Returns the new video's ID."""
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": "22",
        },
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _status, response = request.next_chunk()
    return response["id"]
