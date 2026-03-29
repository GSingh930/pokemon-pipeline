"""
Pokemon Shorts Pipeline - main orchestrator
Runs the full pipeline: topic -> script -> TTS -> video -> music -> upload
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Auto-create required directories
Path("logs").mkdir(exist_ok=True)
Path("output").mkdir(exist_ok=True)
Path("footage/library").mkdir(parents=True, exist_ok=True)
Path("music").mkdir(exist_ok=True)

from core.topic_engine import TopicEngine
from core.script_writer import ScriptWriter
from core.tts_engine import TTSEngine
from core.video_assembler import VideoAssembler
from core.music_mixer import MusicMixer
from core.metadata_writer import MetadataWriter
from uploaders.youtube import YouTubeUploader
from uploaders.tiktok import TikTokUploader
from uploaders.instagram import InstagramUploader
from core.asset_manager import AssetManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"logs/pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def run_pipeline():
    log.info("=== Pokemon Shorts Pipeline Starting ===")

    # Sync assets from R2 if configured
    if os.getenv("R2_PUBLIC_URL"):
        log.info("Syncing assets from R2...")
        try:
            assets = AssetManager()
            assets.sync_footage()
            assets.sync_music()
        except Exception as e:
            log.warning(f"Asset sync failed (non-fatal): {e}")

    # Clean up old output runs to free disk space (keep last 2)
    output_root = Path("output")
    if output_root.exists():
        old_runs = sorted(output_root.iterdir())
        for old_run in old_runs[:-2]:
            import shutil
            try:
                shutil.rmtree(old_run)
                log.info(f"Cleaned up old run: {old_run.name}")
            except Exception:
                pass

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"output/{run_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Stage 1: Pick topic
        log.info("[1/7] Generating topic...")
        topic_engine = TopicEngine()
        topic = topic_engine.generate()
        log.info(f"Topic: {topic['title']} ({topic['type']})")
        _save_json(output_dir / "topic.json", topic)

        # Stage 2: Write script
        log.info("[2/7] Writing script...")
        script_writer = ScriptWriter()
        script = script_writer.write(topic)
        script["type"] = topic["type"]
        script["category"] = topic.get("category", "pokemon")
        script["_topic"] = topic
        log.info(f"Script: {len(script['lines'])} lines, ~{script['estimated_duration']}s")
        _save_json(output_dir / "script.json", script)

        # Stage 3: Generate voiceover
        log.info("[3/7] Generating voiceover (Edge TTS)...")
        tts = TTSEngine()
        audio_path = tts.generate(
            script["narration"],
            output_dir / "voiceover.mp3",
            content_type=topic["type"],
            topic=topic,
        )
        voice_info = tts.get_current_voice()
        log.info(f"Voice selected: {voice_info['voice_name']}")
        _save_json(output_dir / "voice.json", voice_info)
        log.info(f"Audio saved: {audio_path}")

        # Stage 4: Assemble video with images
        log.info("[4/7] Fetching images and assembling video...")
        assembler = VideoAssembler()
        raw_video_path = assembler.assemble(
            audio_path=audio_path,
            broll_cues=script["broll_cues"],
            output_path=output_dir / "raw_video.mp4",
            script=script,
        )
        log.info(f"Raw video: {raw_video_path}")

        # Stage 5: Burn captions
        log.info("[5/7] Burning captions...")
        captioned_path = assembler.burn_captions(
            video_path=raw_video_path,
            script=script,
            output_path=output_dir / "captioned_video.mp4",
            audio_path=audio_path,
        )
        log.info(f"Captioned video: {captioned_path}")

        # Stage 6: Mix in background music
        log.info("[6/7] HAHA Mixing background music...")
        mixer = MusicMixer()
        final_video_path = mixer.mix(
            video_path=captioned_path,
            content_type=topic["type"],
            output_path=output_dir / "final_video.mp4",
        )
        log.info(f"Final video: {final_video_path}")

        # Stage 7: Write metadata + upload
        log.info("[7/7] Writing metadata and uploading...")
        metadata_writer = MetadataWriter()
        metadata = metadata_writer.generate(topic, script)
        _save_json(output_dir / "metadata.json", metadata)

        results = {}

        if os.getenv("YOUTUBE_ENABLED", "true").lower() == "true":
            log.info("Uploading to YouTube Shorts...")
            yt = YouTubeUploader()
            yt_result = yt.upload(final_video_path, metadata)
            results["youtube"] = yt_result

        if os.getenv("TIKTOK_ENABLED", "false").lower() == "true":
            log.info("Uploading to TikTok...")
            tt = TikTokUploader()
            results["tiktok"] = tt.upload(final_video_path, metadata)

        if os.getenv("INSTAGRAM_ENABLED", "false").lower() == "true":
            log.info("Uploading to Instagram Reels...")
            ig = InstagramUploader()
            results["instagram"] = ig.upload(final_video_path, metadata)

        _save_json(output_dir / "upload_results.json", results)

        log.info("=== Pipeline Complete ===")
        log.info(f"Results: {json.dumps(results, indent=2)}")
        return True

    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)
        return False


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
