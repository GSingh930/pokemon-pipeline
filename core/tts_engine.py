"""
TTS engine - randomly picks a Microsoft Edge neural voice per video.
Logs the voice used so you can A/B test performance across uploads.
"""

import os
import asyncio
import logging
import random
import json
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

AB_LOG_FILE = Path("logs/ab_voice_log.json")

# All voices available for A/B testing
# Format: (voice_id, display_name, style_notes)
VOICE_POOL = [
    # Male voices
    ("en-US-GuyNeural",         "Guy",         "deep, dramatic — great for dark lore"),
    ("en-US-ChristopherNeural", "Christopher", "clear, confident — great for top 10s"),
    ("en-US-EricNeural",        "Eric",        "authoritative, serious"),
    ("en-US-RogerNeural",       "Roger",       "warm, engaging"),
    ("en-US-SteffanNeural",     "Steffan",     "neutral, professional"),
    ("en-GB-RyanNeural",        "Ryan (UK)",   "British accent, distinct and cool"),
    ("en-GB-ThomasNeural",      "Thomas (UK)", "British, calm and measured"),
    ("en-AU-WilliamNeural",     "William (AU)","Australian accent, energetic"),

    # Female voices
    ("en-US-JennyNeural",       "Jenny",       "upbeat, friendly"),
    ("en-US-AriaNeural",        "Aria",        "clear, versatile"),
    ("en-US-SaraNeural",        "Sara",        "warm, natural"),
    ("en-US-NancyNeural",       "Nancy",       "calm, articulate"),
    ("en-GB-SoniaNeural",       "Sonia (UK)",  "British female, polished"),
    ("en-AU-NatashaNeural",     "Natasha (AU)","Australian female, bright"),
]

# Rate and pitch tuning per voice for best results
VOICE_TUNING = {
    "en-US-GuyNeural":         {"rate": "+5%",  "pitch": "-5Hz"},
    "en-US-ChristopherNeural": {"rate": "+8%",  "pitch": "+0Hz"},
    "en-US-EricNeural":        {"rate": "+5%",  "pitch": "-3Hz"},
    "en-US-RogerNeural":       {"rate": "+10%", "pitch": "+0Hz"},
    "en-US-SteffanNeural":     {"rate": "+8%",  "pitch": "+0Hz"},
    "en-GB-RyanNeural":        {"rate": "+5%",  "pitch": "-2Hz"},
    "en-GB-ThomasNeural":      {"rate": "+5%",  "pitch": "-2Hz"},
    "en-AU-WilliamNeural":     {"rate": "+10%", "pitch": "+0Hz"},
    "en-US-JennyNeural":       {"rate": "+10%", "pitch": "+2Hz"},
    "en-US-AriaNeural":        {"rate": "+8%",  "pitch": "+0Hz"},
    "en-US-SaraNeural":        {"rate": "+8%",  "pitch": "+0Hz"},
    "en-US-NancyNeural":       {"rate": "+5%",  "pitch": "+0Hz"},
    "en-GB-SoniaNeural":       {"rate": "+8%",  "pitch": "+0Hz"},
    "en-AU-NatashaNeural":     {"rate": "+10%", "pitch": "+2Hz"},
}


class TTSEngine:
    def __init__(self):
        # Allow manual override via env var, otherwise random
        forced = os.getenv("TTS_VOICE")
        if forced:
            self.voice = forced
            self.voice_name = forced
            self.is_random = False
        else:
            voice_id, name, _ = random.choice(VOICE_POOL)
            self.voice = voice_id
            self.voice_name = name
            self.is_random = True

        tuning = VOICE_TUNING.get(self.voice, {"rate": "+5%", "pitch": "+0Hz"})
        self.rate = os.getenv("TTS_RATE", tuning["rate"])
        self.pitch = os.getenv("TTS_PITCH", tuning["pitch"])

    def generate(self, text: str, output_path: Path, content_type: str = None, topic: dict = None) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        log.info(f"TTS voice: {self.voice_name} ({self.voice}) rate={self.rate} pitch={self.pitch}")
        clean_text = self._clean_text(text)

        asyncio.run(self._generate_async(clean_text, output_path))

        # Log for A/B tracking
        self._log_voice(topic, content_type, output_path)

        log.info(f"Audio saved: {output_path} ({output_path.stat().st_size // 1024}KB)")
        return output_path

    async def _generate_async(self, text: str, output_path: Path):
        try:
            import edge_tts
        except ImportError:
            raise ImportError("Run: pip install edge-tts")

        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )
        await communicate.save(str(output_path))

    def _clean_text(self, text: str) -> str:
        import re
        text = re.sub(r'#\w+', '', text)
        text = re.sub(r'http\S+', '', text)
        text = text.replace('&', 'and')
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('...', '... ')
        return text.strip()

    def _log_voice(self, topic: dict, content_type: str, audio_path: Path):
        """Log which voice was used for this video for A/B analysis."""
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
            "views":        None,   # filled in later by analytics
            "likes":        None,
            "comments":     None,
            "watch_time":   None,
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

        log.info(f"A/B log updated: {AB_LOG_FILE}")

    def get_current_voice(self) -> dict:
        return {
            "voice_id":   self.voice,
            "voice_name": self.voice_name,
            "rate":       self.rate,
            "pitch":      self.pitch,
        }
