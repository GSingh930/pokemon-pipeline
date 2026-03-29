"""
Topic engine - generates viral short-form video topics across
Pokemon, anime, video games, and all nerd/geek culture.
"""

import os
import json
import re
import random
from pathlib import Path
from anthropic import Anthropic

CONTENT_TYPES = ["top10", "fan_theory", "did_you_know", "hidden_secret", "lore_deep_dive"]

CATEGORIES = ["pokemon"]

TOPIC_HISTORY_FILE = Path("logs/topic_history.json")


class TopicEngine:
    def __init__(self):
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.history = self._load_history()

    def generate(self) -> dict:
        content_type = self._pick_type()
        category = self._pick_category()
        used_titles = [h.get("title", "") for h in self.history]
        prompt = self._build_prompt(content_type, category, used_titles)

        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=600,
            system="You are a JSON API. You only ever respond with valid RFC8259 JSON. No markdown, no code fences, no apostrophes inside string values. Always use double quotes.",
            messages=[{"role": "user", "content": prompt}, {"role": "assistant", "content": "{"}],
        )

        raw = response.content[0].text.strip()
        # Prepend the { used as prefill (Claude continues from after it)
        if not raw.startswith("{"):
            raw = "{" + raw

        # Trim any trailing content after JSON closes
        depth, end = 0, 0
        for i, ch in enumerate(raw):
            if ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end:
            raw = raw[:end]


        try:
            topic = json.loads(raw)
        except Exception:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            topic = json.loads(match.group()) if match else {
                "title": "Top 10 Most Shocking Anime Moments Ever",
                "hook": "These anime moments broke the internet.",
                "angle": "Ranked by cultural impact and shock value",
                "subjects": ["Naruto", "Dragon Ball Z", "Attack on Titan"],
                "virality_score": 9,
            }

        topic["type"] = content_type
        topic["category"] = category
        self._save_to_history(topic)
        return topic

    def _pick_type(self) -> str:
        recent = self.history[-3:] if len(self.history) >= 3 else self.history
        recent_types = [h.get("type", "") for h in recent]
        available = [t for t in CONTENT_TYPES if t not in recent_types]
        if not available:
            available = CONTENT_TYPES
        return random.choice(available)

    def _pick_category(self) -> str:
        return "pokemon"

    def _build_prompt(self, content_type: str, category: str, used_titles: list) -> str:
        type_instructions = {
            "top10":         "Generate a Top 10 countdown topic. Surprising, emotional, or controversial ranking.",
            "fan_theory":    "Generate a compelling fan theory. Should feel like a revelation that reframes everything.",
            "did_you_know":  "Generate a fascinating hidden fact. Insider knowledge most fans don't know.",
            "hidden_secret": "Generate a hidden secret, cut content, or developer/creator secret.",
            "lore_deep_dive":"Generate a dark, complex, or surprisingly deep lore topic.",
        }

        category_context = {
            "pokemon": "Pokemon games, anime, manga, cards, and lore across all generations (Gen 1 through Gen 9)",
        }

        used_block = ""
        if used_titles:
            recent_used = used_titles[-40:]
            used_block = f"""
ALREADY USED — do NOT repeat or closely resemble:
{chr(10).join(f'- {t}' for t in recent_used if t)}
"""

        return f"""You are a viral nerd culture YouTube Shorts content strategist.

Category: {category_context.get(category, category)}
Content type: {type_instructions[content_type]}
{used_block}
Rules:
- Must be genuinely surprising or emotional to stop scrolling
- Accessible to casual fans, not just hardcore nerds
- Title must create curiosity or controversy
- Hook must grab attention in 3 seconds

Respond ONLY with raw JSON, no markdown, start with {{ end with }}:
{{
  "title": "Punchy title 60 chars max",
  "hook": "First spoken sentence — grabs in 3 seconds",
  "angle": "One sentence on what makes this uniquely shareable",
  "subjects": ["main", "characters", "or", "franchises", "featured"],
  "search_terms": ["3-5 image search terms for visuals"],
  "virality_score": 9
}}"""

    def _load_history(self) -> list:
        TOPIC_HISTORY_FILE.parent.mkdir(exist_ok=True)
        if TOPIC_HISTORY_FILE.exists():
            try:
                with open(TOPIC_HISTORY_FILE) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_to_history(self, topic: dict):
        self.history.append(topic)
        self.history = self.history[-200:]
        with open(TOPIC_HISTORY_FILE, "w") as f:
            json.dump(self.history, f, indent=2)
