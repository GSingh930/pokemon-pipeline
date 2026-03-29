"""
TikTok uploader — uploads video using the TikTok Content Posting API v2.
Requires a TikTok Developer account and approved app with video.publish scope.
"""

import os
import logging
import requests
from pathlib import Path

log = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokUploader:
    def __init__(self):
        self.access_token = os.environ["TIKTOK_ACCESS_TOKEN"]

    def upload(self, video_path: Path, metadata: dict) -> dict:
        video_path = Path(video_path)
        file_size = video_path.stat().st_size

        caption = metadata.get("tiktok", {}).get("caption", "Pokemon facts #Pokemon")

        # Step 1: Initialize upload
        init_response = self._init_upload(file_size, caption)
        upload_url = init_response["data"]["video"]["upload_url"]
        publish_id = init_response["data"]["publish_id"]

        # Step 2: Upload video bytes
        self._upload_video(upload_url, video_path, file_size)

        # Step 3: Poll for completion
        result = self._poll_publish_status(publish_id)

        log.info(f"TikTok upload complete: {result}")
        return {"success": True, "publish_id": publish_id, "status": result}

    def _init_upload(self, file_size: int, caption: str) -> dict:
        url = f"{TIKTOK_API_BASE}/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        body = {
            "post_info": {
                "title": caption[:150],
                "privacy_level": os.getenv("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE"),
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        return response.json()

    def _upload_video(self, upload_url: str, video_path: Path, file_size: int):
        with open(video_path, "rb") as f:
            video_bytes = f.read()

        headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            "Content-Length": str(file_size),
        }
        response = requests.put(upload_url, headers=headers, data=video_bytes, timeout=300)
        response.raise_for_status()
        log.info("TikTok video bytes uploaded successfully")

    def _poll_publish_status(self, publish_id: str, max_attempts: int = 20) -> str:
        import time
        url = f"{TIKTOK_API_BASE}/post/publish/status/fetch/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        for attempt in range(max_attempts):
            response = requests.post(
                url,
                headers=headers,
                json={"publish_id": publish_id},
                timeout=30,
            )
            data = response.json()
            status = data.get("data", {}).get("status", "PROCESSING")
            log.info(f"TikTok publish status: {status} (attempt {attempt + 1})")
            if status in ("PUBLISH_COMPLETE", "SUCCESS"):
                return status
            if status in ("FAILED", "ERROR"):
                raise RuntimeError(f"TikTok publish failed: {data}")
            time.sleep(10)
        return "TIMEOUT"
