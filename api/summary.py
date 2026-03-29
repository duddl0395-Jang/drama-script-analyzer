"""
회차 요약 API — Vercel Serverless Function
POST /api/summary
Body: { "episode": "1화", "annotations": [...], "api_key": "sk-ant-..." }
Returns: episode summary JSON
"""

import json
import re
import os
from http.server import BaseHTTPRequestHandler
import anthropic

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
당신은 한국 드라마 회차 전체를 요약하는 전문가입니다.
제공된 씬별 분석 결과를 종합해 회차 전체 요약을 작성하세요.
반드시 지정된 JSON 스키마만 반환하며, 다른 텍스트는 포함하지 마세요."""

SUMMARY_SCHEMA = {
    "episode": "1화",
    "character_events": "주요 캐릭터 사건 요약. **키워드** 형식 강조. 2-3문장.",
    "romance": "로맨스 전개 요약. 감정선 변화 중심. 2-3문장.",
    "expected_reactions": ['"시청자 반응1"', '"시청자 반응2"', '"시청자 반응3"'],
}


def build_summary_prompt(episode, annotations):
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

    schema_str = json.dumps(SUMMARY_SCHEMA, ensure_ascii=False, indent=2)
    return f"""\
아래는 {episode} 전체 씬 분석 결과입니다.
이를 종합해 회차 요약을 작성하고, 반드시 아래 JSON 스키마 형식으로만 응답하세요.

=== 씬별 분석 ===
{scenes_text}

=== 반환할 JSON 스키마 ===
{schema_str}

episode 값은 "{episode}"로 고정하세요.
expected_reactions는 실제 시청자가 댓글로 쓸 법한 말투로 3개 작성하세요.
JSON 외 다른 텍스트, 마크다운 코드블록, 설명 일절 포함 금지."""


def strip_fences(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        episode = body["episode"]
        annotations = body["annotations"]
        api_key = body.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")

        if not api_key:
            self._respond(400, {"error": "API 키가 필요합니다."})
            return

        client = anthropic.Anthropic(api_key=api_key)
        user_prompt = build_summary_prompt(episode, annotations)

        last_error = None
        for attempt in range(3):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.3,
                )
                raw = strip_fences(response.content[0].text)
                parsed = json.loads(raw)
                parsed["episode"] = episode
                self._respond(200, parsed)
                return
            except json.JSONDecodeError:
                last_error = f"JSON 파싱 실패 (attempt {attempt+1})"
            except Exception as e:
                last_error = str(e)

        self._respond(200, {
            "episode": episode,
            "character_events": f"요약 실패: {last_error}",
            "romance": "",
            "expected_reactions": [],
            "_error": True,
        })

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
