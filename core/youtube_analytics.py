"""
YouTube Analytics puller - fetches views, likes, comments, watch time
for every uploaded video after each pipeline run.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

log = logging.getLogger(__name__)

ANALYTICS_FILE = Path("logs/analytics.json")


class YouTubeAnalytics:
    def __init__(self):
        self.youtube = self._build_youtube_client()

    def pull_all(self) -> list:
        """Fetch latest stats for every video we've uploaded."""
        videos = self._load_video_registry()
        if not videos:
            log.info("No videos in registry yet.")
            return []

        log.info(f"Pulling analytics for {len(videos)} videos...")
        updated = []

        for video in videos:
            video_id = video.get("video_id")
            if not video_id:
                continue
            stats = self._fetch_stats(video_id)
            if stats:
                video.update(stats)
                video["last_updated"] = datetime.now(timezone.utc).isoformat()
                log.info(f"  {video.get('title','')[:40]} | views={stats.get('views',0):,} likes={stats.get('likes',0):,}")
            updated.append(video)

        self._save_analytics(updated)
        return updated

    def register_video(self, video_id: str, metadata: dict, voice_info: dict, topic: dict):
        """Called after upload to register a new video in the analytics registry."""
        videos = self._load_video_registry()

        entry = {
            "video_id":           video_id,
            "title":              metadata.get("youtube", {}).get("title", ""),
            "uploaded_at":        datetime.now(timezone.utc).isoformat(),
            "url":                f"https://youtube.com/shorts/{video_id}",
            "voice_id":           voice_info.get("voice_id", ""),
            "voice_name":         voice_info.get("voice_name", ""),
            "content_type":       topic.get("type", ""),
            "category":           topic.get("category", ""),
            "views":              0,
            "likes":              0,
            "comments":           0,
            "watch_time_minutes": 0,
            "last_updated":       datetime.now(timezone.utc).isoformat(),
        }

        videos.append(entry)
        self._save_analytics(videos)
        log.info(f"Registered video: {video_id}")

    def _fetch_stats(self, video_id: str) -> dict:
        try:
            resp = self.youtube.videos().list(
                part="statistics,contentDetails",
                id=video_id,
            ).execute()

            items = resp.get("items", [])
            if not items:
                return {}

            stats   = items[0].get("statistics", {})
            details = items[0].get("contentDetails", {})

            return {
                "views":    int(stats.get("viewCount",   0)),
                "likes":    int(stats.get("likeCount",   0)),
                "comments": int(stats.get("commentCount", 0)),
                "duration": details.get("duration", ""),
            }
        except Exception as e:
            log.warning(f"Failed to fetch stats for {video_id}: {e}")
            return {}

    def _build_youtube_client(self):
        token_json = os.environ.get("YOUTUBE_TOKEN_JSON")
        if not token_json:
            raise ValueError("YOUTUBE_TOKEN_JSON not set")
        token_data = json.loads(token_json)
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["YOUTUBE_CLIENT_ID"],
            client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        )
        return build("youtube", "v3", credentials=creds)

    def _load_video_registry(self) -> list:
        ANALYTICS_FILE.parent.mkdir(exist_ok=True)
        if ANALYTICS_FILE.exists():
            try:
                with open(ANALYTICS_FILE) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_analytics(self, videos: list):
        with open(ANALYTICS_FILE, "w") as f:
            json.dump(videos, f, indent=2)
