"""
Korean drama script parser.
Handles PDF and plain text input, splits by scene markers.
Scene format: S#1.  지윤집(밤)
"""

import re
from typing import Union
import fitz  # PyMuPDF


SCENE_PATTERN = re.compile(r"^(S#\d+)[.\s]+(.*)", re.MULTILINE)
KOREAN_CHAR_PATTERN = re.compile(r"[\uAC00-\uD7A3]")
MULTI_EPISODE_THRESHOLD = 80  # warn if more scenes than this


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def validate_korean_text(text: str) -> bool:
    return bool(KOREAN_CHAR_PATTERN.search(text))


def parse_scenes(text: str) -> list[dict]:
    """
    Split script text into scenes.
    Returns list of {"scene_id": "S#1", "location": "지윤집(밤)", "content": "..."}.
    Falls back to page-chunked mode if no scene markers found.
    """
    matches = list(SCENE_PATTERN.finditer(text))

    if not matches:
        return _chunk_fallback(text)

    if len(matches) > MULTI_EPISODE_THRESHOLD:
        # caller should surface this warning
        pass

    scenes = []
    for i, match in enumerate(matches):
        scene_id = match.group(1)          # e.g. "S#12"
        location = match.group(2).strip()  # e.g. "지윤집(밤)"

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


def _chunk_fallback(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[dict]:
    """
    No scene markers found — split by character chunks with overlap.
    Produces fake scene IDs so downstream code still works.
    """
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


def parse_script(source: Union[bytes, str], filename: str = "") -> dict:
    """
    Main entry point.
    source: bytes (PDF) or str (plain text).
    Returns {"scenes": [...], "warnings": [...], "raw_text": str}.
    """
    warnings = []

    if isinstance(source, bytes):
        raw_text = extract_text_from_pdf(source)
    else:
        raw_text = source

    if not validate_korean_text(raw_text):
        warnings.append("한국어 텍스트를 감지하지 못했습니다. 파일을 확인해주세요.")

    scenes = parse_scenes(raw_text)

    if not scenes:
        warnings.append("씬을 분리하지 못했습니다. 텍스트 형식을 확인해주세요.")
    elif len(scenes) > MULTI_EPISODE_THRESHOLD:
        warnings.append(
            f"씬이 {len(scenes)}개 감지됐습니다 ({MULTI_EPISODE_THRESHOLD}개 초과). "
            "복수 에피소드가 합쳐진 파일일 수 있습니다."
        )

    return {
        "scenes": scenes,
        "warnings": warnings,
        "raw_text": raw_text,
        "total_scenes": len(scenes),
    }
