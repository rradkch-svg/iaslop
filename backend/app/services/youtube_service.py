import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from backend.app.config import BASE_DIR, STORAGE_DIR

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

CREDENTIALS_FILE = BASE_DIR / "storage" / "youtube_credentials.json"
CLIENT_SECRET_FILE = BASE_DIR / "storage" / "client_secrets.json"

class YouTubeService:
    def __init__(self):
        self.creds: Optional[Credentials] = None
        self._load_saved_credentials()

    def _load_saved_credentials(self):
        if CREDENTIALS_FILE.exists():
            try:
                self.creds = Credentials.from_authorized_user_file(str(CREDENTIALS_FILE), SCOPES)
            except Exception as e:
                print(f"Error loading saved YouTube credentials: {e}")
                self.creds = None

    def is_authenticated(self) -> bool:
        if not self.creds:
            self._load_saved_credentials()
        if self.creds and self.creds.valid:
            return True
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self._save_credentials()
                return True
            except Exception as e:
                print(f"Failed to refresh YouTube token: {e}")
                return False
        return False

    def _save_credentials(self):
        if self.creds:
            CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
                f.write(self.creds.to_json())

    def save_client_secrets(self, secrets_dict: dict) -> Dict[str, Any]:
        """Saves client_secrets.json uploaded by the user"""
        CLIENT_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CLIENT_SECRET_FILE, "w", encoding="utf-8") as f:
            json.dump(secrets_dict, f, indent=2)
        return {"status": "saved", "message": "Client secrets saved successfully."}

    def get_auth_url(self, redirect_uri: str = "http://localhost:8000/api/youtube/oauth2callback") -> str:
        """Generates the Google OAuth authorization URL"""
        if not CLIENT_SECRET_FILE.exists():
            raise FileNotFoundError("client_secrets.json not found. Please upload it in settings.")

        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE),
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        return auth_url

    def complete_oauth_flow(self, code: str, redirect_uri: str = "http://localhost:8000/api/youtube/oauth2callback") -> Dict[str, Any]:
        """Exchanges auth code for access & refresh tokens"""
        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRET_FILE),
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        self.creds = flow.credentials
        self._save_credentials()

        # Fetch channel name for confirmation
        channel_info = self.get_channel_info()
        return {
            "status": "authenticated",
            "channel_title": channel_info.get("title", "YouTube Channel"),
            "channel_id": channel_info.get("id", "")
        }

    def authenticate_with_desktop_flow(self) -> Dict[str, Any]:
        """Runs interactive desktop browser authorization flow"""
        if not CLIENT_SECRET_FILE.exists():
            raise FileNotFoundError("client_secrets.json not found. Please upload it first.")

        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
        self.creds = flow.run_local_server(port=8088, open_browser=True)
        self._save_credentials()
        return self.get_channel_info()

    def get_channel_info(self) -> Dict[str, Any]:
        """Returns authenticated user's YouTube channel info"""
        if not self.is_authenticated():
            return {"authenticated": False}

        try:
            youtube = build("youtube", "v3", credentials=self.creds)
            res = youtube.channels().list(part="snippet,statistics", mine=True).execute()
            items = res.get("items", [])
            if items:
                ch = items[0]
                return {
                    "authenticated": True,
                    "id": ch["id"],
                    "title": ch["snippet"]["title"],
                    "custom_url": ch["snippet"].get("customUrl", ""),
                    "thumbnail": ch["snippet"]["thumbnails"]["default"]["url"],
                    "subscriber_count": ch["statistics"].get("subscriberCount", "0")
                }
            return {"authenticated": True, "title": "Authenticated Channel"}
        except Exception as e:
            print(f"Error fetching channel info: {e}")
            return {"authenticated": False, "error": str(e)}

    async def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        privacy_status: str = "private",
        category_id: str = "27",  # 27 = Education, 24 = Entertainment, 28 = Science & Tech
        thumbnail_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Uploads final video to YouTube via YouTube Data API v3 (videos.insert).
        Attaches high-CTR thumbnail via thumbnails.set if provided.
        """
        if not self.is_authenticated():
            raise PermissionError("YouTube channel not authenticated. Connect in settings.")

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found at {video_path}")

        loop = asyncio.get_event_loop()

        def _do_upload():
            youtube = build("youtube", "v3", credentials=self.creds)

            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": tags[:30],
                    "categoryId": category_id
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False
                }
            }

            media = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                resumable=True,
                chunksize=1024 * 1024 * 5
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"YouTube Upload Progress: {int(status.progress() * 100)}%")

            video_id = response.get("id")
            video_url = f"https://youtu.be/{video_id}"

            # Attach thumbnail if present
            if thumbnail_path and thumbnail_path.exists() and video_id:
                try:
                    thumb_media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=thumb_media
                    ).execute()
                    print(f"YouTube Thumbnail attached to video {video_id}")
                except Exception as te:
                    print(f"Warning: Failed to set thumbnail: {te}")

            return {
                "success": True,
                "video_id": video_id,
                "video_url": video_url,
                "title": title,
                "privacy_status": privacy_status
            }

        return await loop.run_in_executor(None, _do_upload)

youtube_service = YouTubeService()
