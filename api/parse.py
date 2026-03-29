"""
PDF/텍스트 파싱 API — Vercel Serverless Function
POST /api/parse
  - multipart/form-data (file field: "pdf") → PDF 파싱
  - application/json { "text": "대본 텍스트" } → 텍스트 직접 파싱
"""

import json
import re
from http.server import BaseHTTPRequestHandler

SCENE_PATTERN = re.compile(r"^(S#\d+)[.\s]+(.*)", re.MULTILINE)
KOREAN_CHAR_PATTERN = re.compile(r"[\uAC00-\uD7A3]")


def extract_text_from_pdf(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def parse_scenes(text):
    matches = list(SCENE_PATTERN.finditer(text))
    if not matches:
        return chunk_fallback(text)

    scenes = []
    for i, match in enumerate(matches):
        scene_id = match.group(1)
        location = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        scenes.append({
            "scene_id": scene_id,
            "location": location,
            "content": content,
            "scene_number": int(scene_id.replace("S#", "")),
        })
    return scenes


def chunk_fallback(text, chunk_size=2000, overlap=200):
    chunks = []
    start = 0
    idx = 1
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append({
            "scene_id": f"S#{idx}",
            "location": f"구간 {idx}",
            "content": chunk,
            "scene_number": idx,
        })
        start += chunk_size - overlap
        idx += 1
    return chunks


def parse_multipart(body_bytes, content_type):
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part.split("=", 1)[1].strip('"')
            break
    if not boundary:
        return body_bytes

    boundary_bytes = boundary.encode()
    parts = body_bytes.split(b"--" + boundary_bytes)

    for part in parts:
        if b"filename=" in part:
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                header_end = part.find(b"\n\n")
                if header_end == -1:
                    continue
                file_data = part[header_end + 2:]
            else:
                file_data = part[header_end + 4:]

            # strip trailing boundary
            end_marker = file_data.rfind(b"\r\n")
            if end_marker > 0:
                file_data = file_data[:end_marker]

            return file_data

    return body_bytes


def build_response(raw_text):
    warnings = []
    if not KOREAN_CHAR_PATTERN.search(raw_text):
        warnings.append("한국어 텍스트를 감지하지 못했습니다.")

    scenes = parse_scenes(raw_text)
    if len(scenes) > 80:
        warnings.append(f"씬이 {len(scenes)}개 — 복수 에피소드 파일일 수 있습니다.")

    return {
        "scenes": scenes,
        "warnings": warnings,
        "total_scenes": len(scenes),
    }


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_type = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            if "application/json" in content_type:
                # 텍스트 붙여넣기 모드
                data = json.loads(body)
                raw_text = data.get("text", "")
                if not raw_text.strip():
                    self._respond(400, {"error": "텍스트가 비어있습니다."})
                    return
                result = build_response(raw_text)

            elif "multipart/form-data" in content_type:
                # PDF 업로드 모드
                pdf_bytes = parse_multipart(body, content_type)
                raw_text = extract_text_from_pdf(pdf_bytes)
                result = build_response(raw_text)

            else:
                # raw PDF bytes
                raw_text = extract_text_from_pdf(body)
                result = build_response(raw_text)

            self._respond(200, result)

        except Exception as e:
            self._respond(500, {"error": str(e)})

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
