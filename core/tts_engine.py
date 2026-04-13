"""
TTS engine - randomly picks a Microsoft Edge neural voice per video.
Retries with fallback voices if a voice fails.
Runs in a thread to avoid asyncio conflicts with Playwright.
"""

import os
import asyncio
import logging
import random
import json
import concurrent.futures
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

AB_LOG_FILE = Path("logs/ab_voice_log.json")

VOICE_POOL = [
    ("en-US-GuyNeural",         "Guy",         "+5%",  "-5Hz"),
    ("en-US-ChristopherNeural", "Christopher", "+8%",  "+0Hz"),
    ("en-US-EricNeural",        "Eric",        "+5%",  "-3Hz"),
    ("en-US-RogerNeural",       "Roger",       "+10%", "+0Hz"),
    ("en-US-SteffanNeural",     "Steffan",     "+8%",  "+0Hz"),
    ("en-GB-RyanNeural",        "Ryan (UK)",   "+5%",  "-2Hz"),
    ("en-GB-ThomasNeural",      "Thomas (UK)", "+5%",  "-2Hz"),
    ("en-AU-WilliamNeural",     "William (AU)","10%",  "+0Hz"),
    ("en-US-JennyNeural",       "Jenny",       "+10%", "+2Hz"),
    ("en-US-AriaNeural",        "Aria",        "+8%",  "+0Hz"),
    ("en-US-NancyNeural",       "Nancy",       "+5%",  "+0Hz"),
    ("en-GB-SoniaNeural",       "Sonia (UK)",  "+8%",  "+0Hz"),
    ("en-AU-NatashaNeural",     "Natasha (AU)","10%",  "+2Hz"),
]

# Always-reliable fallbacks
SAFE_VOICES = [
    ("en-US-GuyNeural",         "Guy",         "+5%",  "-5Hz"),
    ("en-US-ChristopherNeural", "Christopher", "+8%",  "+0Hz"),
    ("en-US-AriaNeural",        "Aria",        "+8%",  "+0Hz"),
]


class TTSEngine:
    def __init__(self):
        forced = os.getenv("TTS_VOICE")
        if forced:
            self.voice      = forced
            self.voice_name = forced
            self.rate       = os.getenv("TTS_RATE", "+5%")
            self.pitch      = os.getenv("TTS_PITCH", "+0Hz")
            self.is_random  = False
        else:
            voice_id, name, rate, pitch = random.choice(VOICE_POOL)
            self.voice      = voice_id
            self.voice_name = name
            self.rate       = rate
            self.pitch      = pitch
            self.is_random  = True

    def generate(self, text: str, output_path: Path, content_type: str = None, topic: dict = None) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        log.info(f"TTS voice: {self.voice_name} ({self.voice}) rate={self.rate} pitch={self.pitch}")
        clean_text = self._clean_text(text)

        # Try selected voice then safe fallbacks
        voices_to_try = [(self.voice, self.voice_name, self.rate, self.pitch)]
        for v in SAFE_VOICES:
            if v[0] != self.voice:
                voices_to_try.append(v)

        last_error = None
        for voice_id, voice_name, rate, pitch in voices_to_try:
            try:
                self._run_tts(clean_text, output_path, voice_id, rate, pitch)
                if voice_id != self.voice:
                    log.warning(f"Used fallback voice: {voice_name}")
                    self.voice      = voice_id
                    self.voice_name = voice_name
                break
            except Exception as e:
                last_error = e
                log.warning(f"Voice {voice_name} failed: {e} — trying next")
                continue
        else:
            raise RuntimeError(f"All TTS voices failed. Last error: {last_error}")

        self._log_voice(topic, content_type, output_path)
        log.info(f"Audio saved: {output_path} ({output_path.stat().st_size // 1024}KB)")
        return output_path

    def _run_tts(self, text: str, output_path: Path, voice: str, rate: str, pitch: str):
        """Run edge-tts in a thread to avoid asyncio event loop conflicts."""
        async def _generate():
            import edge_tts
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
            await communicate.save(str(output_path))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _generate())
            future.result()

    def _clean_text(self, text: str) -> str:
        import re
        text = re.sub(r'#\w+', '', text)
        text = re.sub(r'http\S+', '', text)
        text = text.replace('&', 'and')
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('...', '... ')
        return text.strip()

    def _log_voice(self, topic: dict, content_type: str, audio_path: Path):
        AB_LOG_FILE.parent.mkdir(exist_ok=True)
        entry = {
            "timestamp":    datetime.now().isoformat(),
            "voice_id":     self.voice,
            "voice_name":   self.voice_name,
            "rate":         self.rate,
            "pitch":        self.pitch,
            "random_pick":  self.is_random,
            "content_type": content_type,
            "category":     topic.get("category", "") if topic else "",
            "title":        topic.get("title", "") if topic else "",
            "audio_file":   str(audio_path),
            "views":        None,
            "likes":        None,
        }
        history = []
        if AB_LOG_FILE.exists():
            try:
                with open(AB_LOG_FILE) as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append(entry)
        with open(AB_LOG_FILE, "w") as f:
            json.dump(history, f, indent=2)

    def get_current_voice(self) -> dict:
        return {"voice_id": self.voice, "voice_name": self.voice_name,
                "rate": self.rate, "pitch": self.pitch}
