"""
Claude API calls with retry logic and JSON validation.
"""

import json
import time
import re
import anthropic
from .prompts import get_prompts_for_scene, GENRE_CONFIG, SYSTEM_EPISODE_SUMMARY, build_episode_summary_prompt

MAX_RETRIES = 3
RETRY_DELAY = 1.5
MODEL = "claude-haiku-4-5-20251001"


def _strip_markdown_fences(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_response(text):
    text = _strip_markdown_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def analyze_scene(client, scene, genre):
    system_prompt, user_prompt = get_prompts_for_scene(scene, genre)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.3,
            )
            raw = response.content[0].text
            parsed = _parse_json_response(raw)

            if parsed is not None:
                parsed["scene_id"] = scene["scene_id"]
                parsed.setdefault("location", scene["location"])
                return parsed

            last_error = f"JSON 파싱 실패 (attempt {attempt+1}): {raw[:200]}"

        except Exception as e:
            last_error = str(e)

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)

    return {
        "scene_id": scene["scene_id"],
        "location": scene["location"],
        "scene_type": "error",
        "summary": f"분석 실패: {last_error}",
        "audience_reaction": "",
        "love_line_status": "해당없음",
        "characters_involved": [],
        "empathy_point": None,
        "viral_candidates": [],
        "inflection_point": None,
        "_error": True,
    }


def analyze_all_scenes(api_key, scenes, genre):
    client = anthropic.Anthropic(api_key=api_key)
    for scene in scenes:
        yield analyze_scene(client, scene, genre)


def summarize_episode(api_key, episode_label, annotations):
    """
    annotations: list of scene annotation dicts for one episode.
    Returns episode summary dict.
    """
    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = build_episode_summary_prompt(episode_label, annotations)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_EPISODE_SUMMARY,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.3,
            )
            raw = response.content[0].text
            parsed = _parse_json_response(raw)
            if parsed is not None:
                parsed["episode"] = episode_label
                return parsed

            last_error = f"JSON 파싱 실패: {raw[:200]}"
        except Exception as e:
            last_error = str(e)

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)

    return {
        "episode": episode_label,
        "character_events": f"요약 실패: {last_error}",
        "romance": "",
        "expected_reactions": [],
        "_error": True,
    }


def available_genres():
    return list(GENRE_CONFIG.keys())
