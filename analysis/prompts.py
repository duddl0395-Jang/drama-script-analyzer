"""
Prompt templates for drama script analysis.
Supports: office_romance_comedy, detective, romance (standalone), office (standalone).
"""

import json

# ── System prompts ─────────────────────────────────────────────────────────────

SYSTEM_OFFICE_ROMANCE_COMEDY = """\
당신은 한국 드라마 대본을 분석하는 전문가입니다.

장르: 오피스 로맨스 코미디
- 직장 내 현실적 공감 장면 (공감 구간)
- 남녀 주인공 간 감정선 변화 (애정 전선)
- 코미디 타이밍과 유머 포인트

분석 원칙:
1. 반드시 아래 JSON 스키마만 반환하세요. 다른 텍스트 절대 포함 금지.
2. 씬 내용에 근거한 분석만 작성하세요.
3. viral_candidates는 실제로 SNS에서 회자될 가능성이 높은 경우에만 포함하세요. 없으면 빈 배열 [].
4. 모든 문자열은 한국어로 작성하세요.
"""

SYSTEM_DETECTIVE = """\
당신은 한국 드라마 대본을 분석하는 전문가입니다.

장르: 옴니버스 수사물
- 매 에피소드 독립된 사건, 반복 등장 형사 캐릭터
- 사건 요약과 반전 포인트 중심 분석

분석 원칙:
1. 반드시 아래 JSON 스키마만 반환하세요. 다른 텍스트 절대 포함 금지.
2. 씬 내용에 근거한 분석만 작성하세요.
3. 모든 문자열은 한국어로 작성하세요.
"""

SYSTEM_ROMANCE = """\
당신은 한국 드라마 대본을 분석하는 전문가입니다.

장르: 로맨스
- 주인공 간 감정선의 단계별 변화 추적
- 설레는 순간, 갈등, 화해, 고백 장면 식별

분석 원칙:
1. 반드시 아래 JSON 스키마만 반환하세요. 다른 텍스트 절대 포함 금지.
2. 씬 내용에 근거한 분석만 작성하세요.
3. 모든 문자열은 한국어로 작성하세요.
"""

# ── JSON schemas (as strings embedded in user prompts) ─────────────────────────

SCHEMA_OFFICE_ROMANCE_COMEDY = {
    "scene_id": "S#12",
    "scene_type": "romance_beat | office_moment | comedy_beat | other",
    "location": "지윤집(밤)",
    "summary": "씬 내용 요약 (2-3문장)",
    "audience_reaction": "시청자가 느낄 감정 반응 (예: 공감, 두근, 웃음, 안타까움)",
    "love_line_status": "첫 접점 | 감정 인식 | 밀당 | 갈등 | 화해 | 고백 | 결합 | 해당없음",
    "characters_involved": ["차지윤", "강시우"],
    "empathy_point": "직장인 공감 포인트 (없으면 null)",
    "viral_candidates": [
        {
            "platform": "instagram | youtube | tiktok",
            "clip_type": "명대사 | 명장면 | 반전 | 공감 | 코미디",
            "line_or_description": "해당 대사 또는 장면 설명",
            "rationale": "왜 이 플랫폼에서 화제될 것인지",
            "source": "llm_heuristic"
        }
    ],
    "inflection_point": "캐릭터 변곡점 설명 (없으면 null)"
}

SCHEMA_DETECTIVE = {
    "scene_id": "S#12",
    "scene_type": "case_open | investigation | confrontation | reveal | other",
    "location": "경찰서(낮)",
    "summary": "씬 내용 요약 (2-3문장)",
    "audience_reaction": "시청자가 느낄 감정 반응",
    "case_status": "사건 시작 | 단서 발견 | 용의자 특정 | 반전 | 해결 | 해당없음",
    "viral_candidates": [
        {
            "platform": "instagram | youtube | tiktok",
            "clip_type": "명대사 | 명장면 | 반전 | 감동",
            "line_or_description": "해당 대사 또는 장면 설명",
            "rationale": "왜 이 플랫폼에서 화제될 것인지",
            "source": "llm_heuristic"
        }
    ],
    "inflection_point": "캐릭터 변곡점 설명 (없으면 null)"
}

SCHEMA_ROMANCE = {
    "scene_id": "S#08",
    "scene_type": "romance_beat | conflict | resolution | other",
    "location": "카페(낮)",
    "summary": "씬 내용 요약 (2-3문장)",
    "audience_reaction": "시청자가 느낄 감정 반응",
    "love_line_status": "첫 접점 | 감정 인식 | 밀당 | 갈등 | 화해 | 고백 | 결합 | 해당없음",
    "characters_involved": ["주인공A", "주인공B"],
    "viral_candidates": [],
    "inflection_point": None
}

# ── Genre config registry ──────────────────────────────────────────────────────

GENRE_CONFIG = {
    "오피스 로맨스 코미디": {
        "system_prompt": SYSTEM_OFFICE_ROMANCE_COMEDY,
        "schema": SCHEMA_OFFICE_ROMANCE_COMEDY,
        "label": "오피스 로맨스 코미디",
    },
    "수사물": {
        "system_prompt": SYSTEM_DETECTIVE,
        "schema": SCHEMA_DETECTIVE,
        "label": "수사물",
    },
    "로맨스": {
        "system_prompt": SYSTEM_ROMANCE,
        "schema": SCHEMA_ROMANCE,
        "label": "로맨스",
    },
}


def build_user_prompt(scene: dict, schema: dict) -> str:
    schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
    return f"""\
아래 씬을 분석하고, 반드시 다음 JSON 스키마 형식으로만 응답하세요.

=== 씬 정보 ===
씬 ID: {scene['scene_id']}
장소: {scene['location']}

=== 대본 내용 ===
{scene['content']}

=== 반환할 JSON 스키마 ===
{schema_str}

위 스키마의 key 이름을 그대로 유지하고, 실제 분석 결과로 value를 채워 반환하세요.
scene_id는 "{scene['scene_id']}"로 고정하세요.
JSON 외 다른 텍스트, 마크다운 코드블록(```), 설명 일절 포함 금지.
"""


def get_prompts_for_scene(scene: dict, genre: str) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for a scene given genre."""
    config = GENRE_CONFIG.get(genre, GENRE_CONFIG["오피스 로맨스 코미디"])
    system = config["system_prompt"]
    user = build_user_prompt(scene, config["schema"])
    return system, user


# ── Episode summary prompt ─────────────────────────────────────────────────────

SYSTEM_EPISODE_SUMMARY = """\
당신은 한국 드라마 회차 전체를 요약하는 전문가입니다.
제공된 씬별 분석 결과를 종합해 회차 전체 요약을 작성하세요.
반드시 지정된 JSON 스키마만 반환하며, 다른 텍스트는 포함하지 마세요.
"""

EPISODE_SUMMARY_SCHEMA = {
    "episode": "1화",
    "character_events": "주요 캐릭터 사건 요약. 굵게 강조할 핵심 키워드는 **키워드** 형식으로 표시. 2~3문장.",
    "romance": "로맨스 전개 요약. 감정선 변화 중심. 2~3문장.",
    "expected_reactions": [
        '"시청자 댓글 스타일 반응 1 (공감/설렘/웃음 등)"',
        '"시청자 댓글 스타일 반응 2"',
        '"시청자 댓글 스타일 반응 3"',
    ],
}


def build_episode_summary_prompt(episode_label: str, annotations: list[dict]) -> str:
    scenes_text = ""
    for ann in annotations:
        if ann.get("_error"):
            continue
        scenes_text += f"\n[{ann.get('scene_id')} {ann.get('location','')}]\n"
        scenes_text += f"- 줄거리: {ann.get('summary','')}\n"
        scenes_text += f"- 시청자 반응: {ann.get('audience_reaction','')}\n"
        love = ann.get("love_line_status")
        if love and love != "해당없음":
            chars = ", ".join(ann.get("characters_involved", []))
            scenes_text += f"- 애정 전선: {love} ({chars})\n"
        empathy = ann.get("empathy_point")
        if empathy:
            scenes_text += f"- 공감 포인트: {empathy}\n"

    schema_str = json.dumps(EPISODE_SUMMARY_SCHEMA, ensure_ascii=False, indent=2)

    return f"""\
아래는 {episode_label} 전체 씬 분석 결과입니다.
이를 종합해 회차 요약을 작성하고, 반드시 아래 JSON 스키마 형식으로만 응답하세요.

=== 씬별 분석 ===
{scenes_text}

=== 반환할 JSON 스키마 ===
{schema_str}

episode 값은 "{episode_label}"로 고정하세요.
expected_reactions는 실제 시청자가 댓글로 쓸 법한 말투로 3개 작성하세요.
JSON 외 다른 텍스트, 마크다운 코드블록(```), 설명 일절 포함 금지.
"""
