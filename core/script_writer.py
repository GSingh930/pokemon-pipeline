"""
Script writer - generates a full 45-60s narration script with pacing,
emphasis markers, and B-roll cues for video assembly.
"""

import os
import json
import re
from anthropic import Anthropic


class ScriptWriter:
    def __init__(self):
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def write(self, topic: dict) -> dict:
        prompt = self._build_prompt(topic)

        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            system="You are a JSON API. You only ever respond with valid RFC8259 JSON. No markdown, no code fences, no explanation, no apostrophes inside string values. Always use double quotes.",
            messages=[{"role": "user", "content": prompt}, {"role": "assistant", "content": "{"}],
        )

        raw = response.content[0].text.strip()

        # Prepend the { used as prefill (Claude continues from after it)
        if not raw.startswith("{"):
            raw = "{" + raw

        # Strip any trailing content after the JSON closes
        # Find the last } that closes the root object
        depth = 0
        end = 0
        for i, ch in enumerate(raw):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end:
            raw = raw[:end]

        try:
            script = json.loads(raw)
        except json.JSONDecodeError:
            script = self._build_fallback_script(topic, raw)

        # Ensure required keys exist
        if "lines" not in script:
            script["lines"] = [{"id": 1, "text": raw[:500], "duration_hint": 5, "emphasis": "normal", "broll": "Pokemon gameplay footage"}]
        if "broll_cues" not in script:
            script["broll_cues"] = [{"at_line": 1, "search_query": "Pokemon gameplay", "duration": 5}]

        # Build flat narration string for TTS
        script["narration"] = " ".join(
            line["text"] for line in script["lines"]
        )
        script["estimated_duration"] = self._estimate_duration(script["narration"])

        return script

    def _build_prompt(self, topic: dict) -> str:
        type_styles = {
            "top10": "Count down from 10 to 1. Each entry gets 1-2 sentences. Build to the most shocking entry at #1.",
            "fan_theory": "Present the theory like you're revealing a secret. Build evidence gradually. End with 'and that changes everything.'",
            "did_you_know": "Lead with the surprising fact, then explain details, then give 2-3 more related facts.",
            "hidden_secret": "Feel like insider knowledge. Reveal cut content, beta designs, or developer secrets.",
            "lore_deep_dive": "Start dark. Reference specific Pokedex entries or game events.",
        }

        style = type_styles.get(topic["type"], type_styles["did_you_know"])

        category = topic.get('category', 'pokemon').replace('_', ' ')
        return f"""You are writing a script for a faceless {category} YouTube Short.

Topic: {topic['title']}
Hook (first line): {topic['hook']}
Content type: {topic['type']}
Style: {style}

Rules:
- Total script: 45-60 seconds when read aloud (120-150 words)
- Short punchy sentences only
- No "Hey guys" or calls to subscribe
- End on a mind-bending final line

Respond with ONLY a raw JSON object. No markdown, no code fences, no explanation before or after. Start your response with {{ and end with }}.

{{
  "lines": [
    {{
      "id": 1,
      "text": "narration text for this line",
      "duration_hint": 3,
      "emphasis": "normal",
      "broll": "description of footage to show"
    }}
  ],
  "broll_cues": [
    {{
      "at_line": 1,
      "search_query": "specific search query for footage",
      "duration": 3
    }}
  ],
  "outro_line": "final punchy sentence"
}}

emphasis options: normal, slow, dramatic"""

    def _build_fallback_script(self, topic: dict, raw_text: str) -> dict:
        """Build a basic script structure if JSON parsing fails completely."""
        sentences = [s.strip() for s in raw_text.replace("\n", " ").split(".") if s.strip()][:10]
        lines = []
        for i, sentence in enumerate(sentences):
            lines.append({
                "id": i + 1,
                "text": sentence + ".",
                "duration_hint": 4,
                "emphasis": "normal",
                "broll": f"Pokemon gameplay footage related to {topic.get('title', 'Pokemon')}",
            })
        return {
            "lines": lines,
            "broll_cues": [{"at_line": 1, "search_query": "Pokemon gameplay footage", "duration": 5}],
            "outro_line": sentences[-1] if sentences else "And that changes everything.",
        }

    def _estimate_duration(self, narration: str) -> int:
        words = len(narration.split())
        return round(words / 2.5)
