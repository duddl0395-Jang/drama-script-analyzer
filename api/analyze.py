"""
씬 분석 API — Vercel Serverless Function
POST /api/analyze
Body: { "scene": {...}, "genre": "오피스 로맨스 코미디", "api_key": "sk-ant-..." }
Returns: scene annotation JSON
"""

import json
import re
import os
from http.server import BaseHTTPRequestHandler
import anthropic

MODEL = "claude-haiku-4-5-20251001"

# ── Prompt templates ───────────────────────────────────────────────────────────

ANALYSIS_RULES = """\
분석 원칙:
1. 반드시 아래 JSON 스키마만 반환하세요. 다른 텍스트 절대 포함 금지.
2. 씬 내용에 근거한 분석만 작성하세요.
3. viral_candidates는 실제로 SNS에서 회자될 가능성이 높은 경우에만. 없으면 빈 배열.
4. 모든 문자열은 한국어로 작성하세요."""

GENRE_DESCRIPTIONS = {
    "오피스 로맨스 코미디": "직장 내 현실적 공감 장면, 남녀 주인공 감정선 변화, 코미디 타이밍과 유머 포인트",
    "로맨스/멜로": "주인공 간 감정선의 단계별 변화 추적, 설레는 순간·갈등·화해·고백 장면 식별",
    "범죄/수사": "사건 전개 흐름, 단서·용의자·반전 포인트, 수사관 캐릭터의 심리 변화",
    "의학/법정": "전문 직업 세계의 긴장감, 환자/의뢰인 사건 중심 서사, 윤리적 딜레마와 갈등",
    "역사/사극": "시대 배경 속 권력 갈등, 역사적 사건과 인물의 재해석, 정치적 긴장과 로맨스",
    "판타지/SF": "세계관 설정과 규칙, 초자연적 능력/기술 요소, 현실 메타포와 감정선",
    "가족/휴먼": "가족 간 갈등과 화해, 세대 간 가치관 충돌, 일상 속 감동과 공감 포인트",
    "코미디": "웃음 포인트와 타이밍, 캐릭터 개그·상황 코미디·언어유희, 반복 개그와 콜백",
    "스릴러/서스펜스": "긴장감 빌드업, 반전 포인트, 떡밥과 복선 회수, 미스터리 요소 추적",
}

SYSTEM_PROMPTS = {}
for genre, desc in GENRE_DESCRIPTIONS.items():
    SYSTEM_PROMPTS[genre] = f"""\
당신은 한국 드라마 대본을 분석하는 전문가입니다.
장르: {genre}
- {desc}
{ANALYSIS_RULES}"""

SCHEMA = {
    "scene_id": "S#12",
    "scene_type": "romance_beat | office_moment | comedy_beat | other",
    "location": "",
    "summary": "씬 내용 요약 (2-3문장)",
    "audience_reaction": "시청자가 느낄 감정 반응",
    "love_line_status": "첫 접점 | 감정 인식 | 밀당 | 갈등 | 화해 | 고백 | 결합 | 해당없음",
    "characters_involved": [],
    "empathy_point": "직장인 공감 포인트 (없으면 null)",
    "viral_candidates": [
        {
            "platform": "instagram | youtube | tiktok",
            "clip_type": "명대사 | 명장면 | 반전 | 공감 | 코미디",
            "line_or_description": "",
            "rationale": "",
            "source": "llm_heuristic",
        }
    ],
    "inflection_point": None,
}


def strip_fences(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def build_user_prompt(scene):
    schema_str = json.dumps(SCHEMA, ensure_ascii=False, indent=2)
    return f"""\
아래 씬을 분석하고, 반드시 다음 JSON 스키마 형식으로만 응답하세요.

=== 씬 정보 ===
씬 ID: {scene['scene_id']}
장소: {scene['location']}

=== 대본 내용 ===
{scene['content']}

=== 반환할 JSON 스키마 ===
{schema_str}

scene_id는 "{scene['scene_id']}"로 고정하세요.
JSON 외 다른 텍스트, 마크다운 코드블록, 설명 일절 포함 금지."""


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        scene = body["scene"]
        genre = body.get("genre", "오피스 로맨스 코미디")
        api_key = body.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")

        if not api_key:
            self._respond(400, {"error": "API 키가 필요합니다."})
            return

        system_prompt = SYSTEM_PROMPTS.get(genre, SYSTEM_PROMPTS["오피스 로맨스 코미디"])
        user_prompt = build_user_prompt(scene)

        client = anthropic.Anthropic(api_key=api_key)

        last_error = None
        for attempt in range(3):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.3,
                )
                raw = strip_fences(response.content[0].text)
                parsed = json.loads(raw)
                parsed["scene_id"] = scene["scene_id"]
                parsed.setdefault("location", scene["location"])
                self._respond(200, parsed)
                return
            except json.JSONDecodeError:
                last_error = f"JSON 파싱 실패 (attempt {attempt+1})"
            except Exception as e:
                last_error = str(e)

        self._respond(200, {
            "scene_id": scene["scene_id"],
            "location": scene["location"],
            "scene_type": "error",
            "summary": f"분석 실패: {last_error}",
            "audience_reaction": "",
            "viral_candidates": [],
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
