"""
TikTok uploader - uses tiktok-uploader with session cookies.

Setup:
    1. Go to tiktok.com in Chrome, log in
    2. F12 -> Application -> Cookies -> tiktok.com
    3. Copy the value of the "sessionid" cookie
    4. railway variables set TIKTOK_SESSION_ID=your_session_id
    5. railway variables set TIKTOK_ENABLED=true
"""

import os
import json
import logging
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


class TikTokUploader:
    def __init__(self):
        self.session_id = os.environ.get("TIKTOK_SESSION_ID", "")

    def upload(self, video_path: Path, metadata: dict) -> dict:
        try:
            from tiktok_uploader.upload import upload_video
        except ImportError:
            raise ImportError("Run: pip install tiktok-uploader")

        if not self.session_id:
            raise ValueError(
                "TIKTOK_SESSION_ID not set. Get it from:\n"
                "tiktok.com -> F12 -> Application -> Cookies -> sessionid"
            )

        video_path = Path(video_path)
        caption    = metadata.get("tiktok", {}).get("caption", "#Pokemon #PokemonFacts")[:150]

        # Write cookies as a proper JSON file with domain set
        cookies = [
            {
                "name":   "sessionid",
                "value":  self.session_id,
                "domain": ".tiktok.com",
                "path":   "/",
                "secure": True,
                "httpOnly": True,
            }
        ]
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(json.dumps(cookies))

        log.info(f"Uploading to TikTok: {video_path.name}")

        try:
            result = upload_video(
                filename=str(video_path),
                description=caption,
                cookies=str(tmp),
                headless=True,
                browser="chromium",
            )
            log.info(f"TikTok upload complete: {result}")
            return {"success": True, "result": str(result)}
        finally:
            tmp.unlink(missing_ok=True)
