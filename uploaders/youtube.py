"""
YouTube uploader — uploads video as a YouTube Short using the YouTube Data API v3.
Uses OAuth2 credentials stored as environment variables.
"""

import os
import json
import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploader:
    def __init__(self):
        self.credentials = self._load_credentials()

    def upload(self, video_path: Path, metadata: dict) -> dict:
        youtube = build("youtube", "v3", credentials=self.credentials)

        yt_meta = metadata.get("youtube", {})
        title = yt_meta.get("title", "Pokemon Facts")
        description = yt_meta.get("description", "")
        tags = yt_meta.get("tags", ["Pokemon"])

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "20",  # Gaming
                "defaultLanguage": "en",
            },
            "status": {
                "privacyStatus": os.getenv("YOUTUBE_PRIVACY", "public"),
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=5 * 1024 * 1024,  # 5MB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        log.info("Starting YouTube upload...")
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info(f"YouTube upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        url = f"https://youtube.com/shorts/{video_id}"
        log.info(f"YouTube upload complete: {url}")

        return {"success": True, "video_id": video_id, "url": url}

    def _load_credentials(self) -> Credentials:
        token_json = os.environ.get("YOUTUBE_TOKEN_JSON")
        if token_json:
            token_data = json.loads(token_json)
            return Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.environ["YOUTUBE_CLIENT_ID"],
                client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                scopes=SCOPES,
            )
        raise ValueError("YOUTUBE_TOKEN_JSON environment variable not set. Run auth/youtube_auth.py first.")
