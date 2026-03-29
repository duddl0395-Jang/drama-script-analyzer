"""
대본 분석 자동화 — Streamlit UI
오피스 로맨스 코미디 / 수사물 / 로맨스
"""

import json
import os
import streamlit as st
from analysis.parser import parse_script
from analysis.analyzer import analyze_all_scenes, available_genres

# .env 파일에서 API 키 자동 로드
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

st.set_page_config(page_title="대본 분석 자동화", page_icon="🎬", layout="wide")

# ── Session state defaults ─────────────────────────────────────────────────────
for k, v in {
    "scenes": [],
    "annotations": {},
    "selected_scene": None,
    "analysis_done": False,
    "run_analysis": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Helpers ────────────────────────────────────────────────────────────────────

def scene_type_icon(t):
    return {
        "romance_beat": "💕", "office_moment": "💼", "comedy_beat": "😄",
        "case_open": "🔍", "investigation": "🔎", "confrontation": "⚡",
        "reveal": "💡", "conflict": "💢", "resolution": "🤝",
        "error": "⚠️", "other": "📝",
    }.get(t, "📝")


def love_line_badge(status):
    colors = {
        "첫 접점": "#FF6B9D", "감정 인식": "#FF8E53", "밀당": "#FFC300",
        "갈등": "#E74C3C", "화해": "#2ECC71", "고백": "#9B59B6",
        "결합": "#E91E63", "해당없음": "#95A5A6",
    }
    c = colors.get(status, "#95A5A6")
    return f'<span style="background:{c};color:white;padding:2px 8px;border-radius:12px;font-size:12px;">{status}</span>'


def viral_badge(platform):
    c = {"instagram": "#E1306C", "youtube": "#FF0000", "tiktok": "#010101"}.get(platform, "#555")
    return f'<span style="background:{c};color:white;padding:1px 7px;border-radius:10px;font-size:11px;">{platform}</span>'


def render_annotation(ann):
    if ann is None:
        st.caption("씬을 선택하면 분석 결과가 표시됩니다.")
        return
    if ann.get("_error"):
        st.error(ann.get("summary", "분석 실패"))
        return

    st.markdown(f"### {scene_type_icon(ann.get('scene_type','other'))} {ann['scene_id']} — {ann.get('location','')}")
    st.markdown("**줄거리**")
    st.write(ann.get("summary", ""))
    st.markdown("**시청자 반응**")
    st.info(ann.get("audience_reaction", ""))

    love = ann.get("love_line_status")
    if love and love != "해당없음":
        st.markdown("**애정 전선**")
        st.markdown(love_line_badge(love), unsafe_allow_html=True)
        chars = ann.get("characters_involved", [])
        if chars:
            st.caption(" · ".join(chars))
        st.markdown("")

    empathy = ann.get("empathy_point")
    if empathy:
        st.markdown("**직장인 공감 포인트**")
        st.success(empathy)

    inflection = ann.get("inflection_point")
    if inflection:
        st.markdown("**캐릭터 변곡점**")
        st.warning(inflection)

    viral = ann.get("viral_candidates", [])
    if viral:
        st.markdown("**바이럴 후보**")
        for v in viral:
            st.markdown(
                f"{viral_badge(v.get('platform',''))} `{v.get('clip_type','')}`  \n"
                f'**"{v.get("line_or_description","")}"**  \n'
                f'<span style="color:#888;font-size:12px;">{v.get("rationale","")}</span>',
                unsafe_allow_html=True,
            )
            st.divider()


def export_json(annotations):
    return json.dumps(list(annotations.values()), ensure_ascii=False, indent=2)


def export_text(scenes, annotations):
    lines = []
    for s in scenes:
        sid = s["scene_id"]
        ann = annotations.get(sid)
        lines.append(f"=== {sid} {s['location']} ===")
        if ann and not ann.get("_error"):
            lines.append(f"[줄거리] {ann.get('summary','')}")
            lines.append(f"[시청자 반응] {ann.get('audience_reaction','')}")
            love = ann.get("love_line_status")
            if love and love != "해당없음":
                lines.append(f"[애정 전선] {love} ({', '.join(ann.get('characters_involved', []))})")
            if ann.get("empathy_point"):
                lines.append(f"[공감 포인트] {ann['empathy_point']}")
            for v in ann.get("viral_candidates", []):
                lines.append(f"[바이럴/{v.get('platform')}] {v.get('clip_type')} — {v.get('line_or_description')}")
        else:
            lines.append("[분석 없음]")
        lines.append("")
    return "\n".join(lines)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎬 대본 분석 자동화")
    st.divider()

    st.subheader("1. API 설정")
    _env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    api_key = st.text_input(
        "Claude API Key",
        type="password",
        value=_env_key,
        placeholder="sk-ant-...",
        help=".env 파일에 ANTHROPIC_API_KEY를 저장하면 자동 입력됩니다.",
    )
    genre = st.selectbox("장르 선택", available_genres())

    st.divider()
    st.subheader("2. 대본 입력")
    upload_type = st.radio("입력 방식", ["PDF 업로드", "텍스트 직접 입력"])

    uploaded_file = None
    pasted_text = ""
    if upload_type == "PDF 업로드":
        uploaded_file = st.file_uploader("PDF 파일", type=["pdf"])
    else:
        pasted_text = st.text_area("대본 텍스트 붙여넣기", height=200)

    if st.button("대본 파싱", use_container_width=True):
        source = None
        if upload_type == "PDF 업로드" and uploaded_file:
            source = uploaded_file.read()
        elif upload_type == "텍스트 직접 입력" and pasted_text.strip():
            source = pasted_text

        if source is None:
            st.warning("파일 또는 텍스트를 입력해주세요.")
        else:
            with st.spinner("파싱 중..."):
                result = parse_script(source)
            st.session_state.scenes = result["scenes"]
            st.session_state.annotations = {}
            st.session_state.analysis_done = False
            st.session_state.run_analysis = False
            st.session_state.selected_scene = (
                result["scenes"][0]["scene_id"] if result["scenes"] else None
            )
            for w in result.get("warnings", []):
                st.warning(w)
            if result["scenes"]:
                st.success(f"✅ 씬 {result['total_scenes']}개 파싱 완료")

    st.divider()
    st.subheader("3. 분석")

    can_run = bool(st.session_state.scenes) and bool(api_key)
    if not api_key:
        st.caption("⚠️ API Key를 먼저 입력해주세요.")
    elif not st.session_state.scenes:
        st.caption("⚠️ 먼저 대본을 파싱해주세요.")

    if st.button("▶ 전체 씬 분석 시작", type="primary", use_container_width=True, disabled=not can_run):
        st.session_state.run_analysis = True
        st.session_state.analysis_done = False
        st.session_state.annotations = {}

    st.divider()
    st.subheader("4. 내보내기")
    if st.session_state.annotations:
        st.download_button(
            "JSON 다운로드",
            data=export_json(st.session_state.annotations),
            file_name="analysis.json",
            mime="application/json",
            use_container_width=True,
        )
    if st.session_state.annotations and st.session_state.scenes:
        st.download_button(
            "텍스트 다운로드",
            data=export_text(st.session_state.scenes, st.session_state.annotations),
            file_name="analysis.txt",
            mime="text/plain",
            use_container_width=True,
        )


# ── Main area ──────────────────────────────────────────────────────────────────
scenes = st.session_state.scenes
annotations = st.session_state.annotations

if not scenes:
    st.markdown("## 🎬 대본 분석 자동화")
    st.markdown(
        "왼쪽 사이드바에서 시작하세요:\n\n"
        "1. **OpenAI API Key** 입력 (sk-...)\n"
        "2. **장르** 선택\n"
        "3. **PDF 업로드** 또는 텍스트 붙여넣기\n"
        "4. **대본 파싱** 버튼 클릭\n"
        "5. **전체 씬 분석 시작** 버튼 클릭"
    )
else:
    col_script, col_annotation = st.columns([2, 1])

    n_done = len(annotations)
    n_total = len(scenes)
    n_viral = sum(1 for a in annotations.values() if a.get("viral_candidates"))

    with col_script:
        st.markdown(f"### 📄 씬 목록 — {n_done}/{n_total}개 완료 · 🔥 {n_viral}씬")

        for scene in scenes:
            sid = scene["scene_id"]
            ann = annotations.get(sid)

            if ann is None:
                status = "⬜"
            elif ann.get("_error"):
                status = "❌"
            else:
                status = scene_type_icon(ann.get("scene_type", "other"))

            flags = ""
            if ann and ann.get("viral_candidates"):
                flags += " 🔥"
            if ann and ann.get("love_line_status", "해당없음") != "해당없음":
                flags += " 💕"

            label = f"{status} {sid}. {scene['location']}{flags}"
            is_selected = (st.session_state.selected_scene == sid)

            if st.button(label, key=f"btn_{sid}", use_container_width=True,
                         type="primary" if is_selected else "secondary"):
                st.session_state.selected_scene = sid
                st.rerun()

    with col_annotation:
        st.markdown("### 🔍 씬 분석 결과")
        ann_placeholder = st.empty()
        with ann_placeholder.container():
            render_annotation(annotations.get(st.session_state.selected_scene))

    # ── Analysis execution ─────────────────────────────────────────────────────
    if st.session_state.run_analysis:
        st.session_state.run_analysis = False  # clear flag before loop

        progress_bar = col_script.progress(0.0)
        status_text = col_script.empty()
        total = len(scenes)

        for i, result in enumerate(analyze_all_scenes(api_key, scenes, genre)):
            st.session_state.annotations[result["scene_id"]] = result
            progress_bar.progress((i + 1) / total)
            status_text.text(
                f"분석 중... {i+1}/{total}  ({result['scene_id']} {result.get('location','')})"
            )
            if i == 0:
                st.session_state.selected_scene = result["scene_id"]
            if result["scene_id"] == st.session_state.selected_scene:
                with ann_placeholder.container():
                    render_annotation(result)

        st.session_state.analysis_done = True
        status_text.text(f"✅ 전체 {total}개 씬 분석 완료!")
        st.rerun()
