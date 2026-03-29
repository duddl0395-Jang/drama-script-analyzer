"""
대본 분석 자동화 — Streamlit UI
멀티 에피소드 + 회차별 요약 장표
"""

import json
import os
import re
import streamlit as st
from analysis.parser import parse_script
from analysis.analyzer import analyze_all_scenes, summarize_episode, available_genres

st.set_page_config(page_title="대본 분석 자동화", page_icon="🎬", layout="wide")

# .env 자동 로드
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ── Session state ──────────────────────────────────────────────────────────────
# episodes: {"1화": {"scenes": [], "annotations": {}, "done": False}}
# episode_summaries: {"1화": {"character_events": ..., "romance": ..., "expected_reactions": [...]}}
for k, v in {
    "episodes": {},
    "episode_summaries": {},
    "current_episode": None,
    "selected_scene": None,
    "run_analysis": False,
    "run_summary": False,
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


def bold_to_html(text):
    """**키워드** → <b>키워드</b>"""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def render_summary_table(episode_summaries):
    """이미지처럼 회차별 요약 장표 렌더링."""
    if not episode_summaries:
        st.info("분석된 에피소드가 없습니다. 먼저 씬 분석 후 요약을 생성하세요.")
        return

    episodes = sorted(episode_summaries.keys())

    # 헤더
    header_cols = st.columns([1] + [1] * len(episodes))
    header_cols[0].markdown("")
    for i, ep in enumerate(episodes):
        header_cols[i + 1].markdown(
            f'<div style="background:#333;color:white;text-align:center;padding:8px;border-radius:4px;font-weight:bold;">{ep}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # 주요 캐릭터 사건
    row1 = st.columns([1] + [1] * len(episodes))
    row1[0].markdown(
        '<div style="background:#555;color:white;text-align:center;padding:40px 8px;border-radius:4px;font-size:13px;font-weight:bold;">주요<br>캐릭터<br>사건</div>',
        unsafe_allow_html=True,
    )
    for i, ep in enumerate(episodes):
        data = episode_summaries.get(ep, {})
        text = bold_to_html(data.get("character_events", "—"))
        row1[i + 1].markdown(
            f'<div style="background:#f9f9f9;padding:12px;border-radius:4px;font-size:13px;line-height:1.6;min-height:80px;">{text}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # 로맨스 전개
    row2 = st.columns([1] + [1] * len(episodes))
    row2[0].markdown(
        '<div style="background:#C0392B;color:white;text-align:center;padding:40px 8px;border-radius:4px;font-size:13px;font-weight:bold;">로맨스<br>전개</div>',
        unsafe_allow_html=True,
    )
    for i, ep in enumerate(episodes):
        data = episode_summaries.get(ep, {})
        text = bold_to_html(data.get("romance", "—"))
        row2[i + 1].markdown(
            f'<div style="background:#fff5f5;padding:12px;border-radius:4px;font-size:13px;line-height:1.6;min-height:80px;">{text}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # 예상 반응
    row3 = st.columns([1] + [1] * len(episodes))
    row3[0].markdown(
        '<div style="background:#555;color:white;text-align:center;padding:40px 8px;border-radius:4px;font-size:13px;font-weight:bold;">예상<br>반응</div>',
        unsafe_allow_html=True,
    )
    for i, ep in enumerate(episodes):
        data = episode_summaries.get(ep, {})
        reactions = data.get("expected_reactions", [])
        lines = "".join(
            f'<div style="margin-bottom:6px;font-size:12px;color:#444;">"{r}"</div>'
            for r in reactions
        ) if reactions else "<div style='color:#aaa;font-size:12px;'>—</div>"
        row3[i + 1].markdown(
            f'<div style="background:#f9f9f9;padding:12px;border-radius:4px;min-height:80px;">{lines}</div>',
            unsafe_allow_html=True,
        )


def export_summary_json(episode_summaries):
    return json.dumps(episode_summaries, ensure_ascii=False, indent=2)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎬 대본 분석 자동화")
    st.divider()

    st.subheader("1. API 설정")
    _env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    api_key = st.text_input("Claude API Key", type="password", value=_env_key, placeholder="sk-ant-...")
    genre = st.selectbox("장르 선택", available_genres())

    st.divider()
    st.subheader("2. 에피소드 업로드")

    uploaded_files = st.file_uploader(
        "PDF 파일 (여러 개 가능)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.caption("에피소드 번호를 입력하세요:")
        episode_labels = {}
        for f in uploaded_files:
            default_label = f.name.replace(".pdf", "")
            label = st.text_input(f.name, value=default_label, key=f"label_{f.name}")
            episode_labels[f.name] = label

    if st.button("대본 파싱", use_container_width=True, disabled=not uploaded_files):
        for f in uploaded_files:
            label = episode_labels[f.name]
            f.seek(0)
            with st.spinner(f"{label} 파싱 중..."):
                result = parse_script(f.read())
            st.session_state.episodes[label] = {
                "scenes": result["scenes"],
                "annotations": {},
                "done": False,
            }
            for w in result.get("warnings", []):
                st.warning(f"[{label}] {w}")
            if result["scenes"]:
                st.success(f"✅ {label}: 씬 {result['total_scenes']}개")

        if st.session_state.episodes:
            first = sorted(st.session_state.episodes.keys())[0]
            st.session_state.current_episode = first
            scenes = st.session_state.episodes[first]["scenes"]
            st.session_state.selected_scene = scenes[0]["scene_id"] if scenes else None

    st.divider()
    st.subheader("3. 분석")

    ep_keys = sorted(st.session_state.episodes.keys())
    if ep_keys:
        selected_ep = st.selectbox("분석할 에피소드", ep_keys, key="ep_selector")
        st.session_state.current_episode = selected_ep

    can_run = bool(st.session_state.episodes) and bool(api_key)
    if not api_key:
        st.caption("⚠️ API Key를 입력해주세요.")
    elif not st.session_state.episodes:
        st.caption("⚠️ 먼저 대본을 파싱해주세요.")

    if st.button("▶ 씬 분석 시작", type="primary", use_container_width=True, disabled=not can_run):
        ep = st.session_state.current_episode
        st.session_state.episodes[ep]["annotations"] = {}
        st.session_state.episodes[ep]["done"] = False
        st.session_state.run_analysis = True

    st.divider()
    st.subheader("4. 회차 요약 생성")

    analyzed_eps = [ep for ep, d in st.session_state.episodes.items() if d.get("done")]
    can_summarize = bool(analyzed_eps) and bool(api_key)

    if st.button("📊 요약 장표 생성", use_container_width=True, disabled=not can_summarize):
        st.session_state.run_summary = True

    if not analyzed_eps:
        st.caption("씬 분석 완료된 에피소드가 없습니다.")

    st.divider()
    st.subheader("5. 내보내기")
    if st.session_state.episode_summaries:
        st.download_button(
            "요약 JSON 다운로드",
            data=export_summary_json(st.session_state.episode_summaries),
            file_name="episode_summaries.json",
            mime="application/json",
            use_container_width=True,
        )


# ── Main area ──────────────────────────────────────────────────────────────────
if not st.session_state.episodes:
    st.markdown("## 🎬 대본 분석 자동화")
    st.markdown(
        "왼쪽 사이드바에서 시작하세요:\n\n"
        "1. **Claude API Key** 입력\n"
        "2. **장르** 선택\n"
        "3. **PDF 파일** 업로드 (여러 화 동시 가능)\n"
        "4. 에피소드 이름 입력 후 **대본 파싱**\n"
        "5. **씬 분석 시작** → 완료 후 **요약 장표 생성**"
    )
else:
    tab_scene, tab_summary = st.tabs(["📄 씬 분석", "📊 회차별 요약"])

    # ── Tab 1: 씬 분석 ─────────────────────────────────────────────────────────
    with tab_scene:
        ep = st.session_state.current_episode
        if ep and ep in st.session_state.episodes:
            ep_data = st.session_state.episodes[ep]
            scenes = ep_data["scenes"]
            annotations = ep_data["annotations"]

            col_script, col_annotation = st.columns([2, 1])

            n_done = len(annotations)
            n_total = len(scenes)
            n_viral = sum(1 for a in annotations.values() if a.get("viral_candidates"))

            with col_script:
                st.markdown(f"### {ep} — {n_done}/{n_total}개 완료 · 🔥 {n_viral}씬")

                for scene in scenes:
                    sid = scene["scene_id"]
                    ann = annotations.get(sid)
                    status = "⬜" if ann is None else ("❌" if ann.get("_error") else scene_type_icon(ann.get("scene_type", "other")))
                    flags = ""
                    if ann and ann.get("viral_candidates"):
                        flags += " 🔥"
                    if ann and ann.get("love_line_status", "해당없음") != "해당없음":
                        flags += " 💕"

                    is_selected = (st.session_state.selected_scene == sid)
                    if st.button(
                        f"{status} {sid}. {scene['location']}{flags}",
                        key=f"btn_{ep}_{sid}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                    ):
                        st.session_state.selected_scene = sid
                        st.rerun()

            with col_annotation:
                st.markdown("### 🔍 씬 분석 결과")
                ann_placeholder = st.empty()
                with ann_placeholder.container():
                    render_annotation(annotations.get(st.session_state.selected_scene))

            # 분석 실행
            if st.session_state.run_analysis:
                st.session_state.run_analysis = False
                progress_bar = col_script.progress(0.0)
                status_text = col_script.empty()
                total = len(scenes)

                for i, result in enumerate(analyze_all_scenes(api_key, scenes, genre)):
                    st.session_state.episodes[ep]["annotations"][result["scene_id"]] = result
                    progress_bar.progress((i + 1) / total)
                    status_text.text(f"분석 중... {i+1}/{total} ({result['scene_id']} {result.get('location','')})")
                    if i == 0:
                        st.session_state.selected_scene = result["scene_id"]
                    if result["scene_id"] == st.session_state.selected_scene:
                        with ann_placeholder.container():
                            render_annotation(result)

                st.session_state.episodes[ep]["done"] = True
                status_text.text(f"✅ {ep} 전체 {total}개 씬 분석 완료!")
                st.rerun()

    # ── Tab 2: 회차별 요약 ────────────────────────────────────────────────────
    with tab_summary:
        st.markdown("### 📊 회차별 요약")

        # 요약 생성 실행
        if st.session_state.run_summary:
            st.session_state.run_summary = False
            analyzed_eps = sorted([ep for ep, d in st.session_state.episodes.items() if d.get("done")])
            prog = st.progress(0.0)
            msg = st.empty()
            for i, ep in enumerate(analyzed_eps):
                msg.text(f"요약 생성 중... {ep}")
                annotations = list(st.session_state.episodes[ep]["annotations"].values())
                summary = summarize_episode(api_key, ep, annotations)
                st.session_state.episode_summaries[ep] = summary
                prog.progress((i + 1) / len(analyzed_eps))
            msg.text("✅ 요약 장표 생성 완료!")

        render_summary_table(st.session_state.episode_summaries)
