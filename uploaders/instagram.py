"""
Instagram Reels uploader — uploads video using the Meta Graph API.
Requires a Facebook App with instagram_content_publish permission.
Video must be hosted at a public URL, so we upload to a temp host first.
"""

import os
import time
import logging
import requests
from pathlib import Path

log = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v19.0"


class InstagramUploader:
    def __init__(self):
        self.access_token = os.environ["INSTAGRAM_ACCESS_TOKEN"]
        self.ig_user_id = os.environ["INSTAGRAM_USER_ID"]
        self.cdn_upload_url = os.getenv("CDN_UPLOAD_URL")  # Your file host endpoint

    def upload(self, video_path: Path, metadata: dict) -> dict:
        video_path = Path(video_path)
        caption = metadata.get("instagram", {}).get("caption", "#Pokemon")

        # Step 1: Upload video to a publicly accessible URL
        video_url = self._upload_to_cdn(video_path)
        log.info(f"Video hosted at: {video_url}")

        # Step 2: Create media container
        container_id = self._create_container(video_url, caption)
        log.info(f"Instagram container created: {container_id}")

        # Step 3: Wait for container to be ready
        self._wait_for_container(container_id)

        # Step 4: Publish container
        media_id = self._publish_container(container_id)
        log.info(f"Instagram published: media_id={media_id}")

        return {"success": True, "media_id": media_id}

    def _upload_to_cdn(self, video_path: Path) -> str:
        """Upload video to a CDN/file host and return the public URL."""
        if not self.cdn_upload_url:
            raise ValueError(
                "CDN_UPLOAD_URL not set. Instagram requires a public video URL. "
                "Set up a simple file host (e.g. Cloudflare R2, S3, or Backblaze B2) "
                "and set CDN_UPLOAD_URL to your upload endpoint."
            )

        with open(video_path, "rb") as f:
            response = requests.post(
                self.cdn_upload_url,
                files={"file": (video_path.name, f, "video/mp4")},
                headers={"Authorization": f"Bearer {os.getenv('CDN_API_KEY', '')}"},
                timeout=120,
            )
        response.raise_for_status()
        return response.json()["url"]

    def _create_container(self, video_url: str, caption: str) -> str:
        url = f"{GRAPH_API}/{self.ig_user_id}/media"
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": self.access_token,
        }
        response = requests.post(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()["id"]

    def _wait_for_container(self, container_id: str, max_wait: int = 300):
        url = f"{GRAPH_API}/{container_id}"
        params = {"fields": "status_code,status", "access_token": self.access_token}
        elapsed = 0
        while elapsed < max_wait:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            status = data.get("status_code", "IN_PROGRESS")
            log.info(f"Instagram container status: {status}")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise RuntimeError(f"Instagram container failed: {data}")
            time.sleep(15)
            elapsed += 15
        raise TimeoutError("Instagram container processing timed out")

    def _publish_container(self, container_id: str) -> str:
        url = f"{GRAPH_API}/{self.ig_user_id}/media_publish"
        params = {
            "creation_id": container_id,
            "access_token": self.access_token,
        }
        response = requests.post(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()["id"]
