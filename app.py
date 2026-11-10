"""MeetLens — polished Streamlit UI for the existing AI video/meeting pipeline.

Run:
    streamlit run app.py

The existing processing modules and function calls are intentionally preserved.
"""
import html
import os
import re
import tempfile
import time
import traceback

import streamlit as st
from dotenv import load_dotenv

from utils.audio_processor import process_audio_from_youtube
from core.transcriber import transcribe_all
from core.summarize import summarize_chunks, generate_title
from core.extractor import (
    extract_action_items,
    extract_key_decisions,
    extract_questions,
)
from core.rag_engine import build_rag_chain, ask_question

load_dotenv()

# Load Streamlit Cloud secrets into environment variables (safe for local dev)
try:
    for key, value in st.secrets.items():
        if isinstance(value, str):
            os.environ.setdefault(key, value)
except FileNotFoundError:
    pass  # No secrets.toml — running locally with .env

APP_NAME = "MeetLens"
TAGLINE = "Your meetings, understood. Turn long videos into clear summaries, decisions, and next steps."

st.set_page_config(
    page_title="MeetLens — AI meeting intelligence",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────── Design system ─────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

    :root {
      --bg: #080B16;
      --surface: #101629;
      --surface-2: #151D33;
      --surface-3: #1B2540;
      --line: rgba(157, 174, 226, .14);
      --text: #F4F6FF;
      --muted: #9AA7C5;
      --purple: #8B7CFF;
      --cyan: #51D6C5;
      --green: #57D9A3;
      --amber: #FFC36B;
      --pink: #FF83B5;
    }

    html, body, [class*="css"], .stApp {
      font-family: 'DM Sans', sans-serif;
    }
    .stApp {
      color: var(--text);
      background:
        radial-gradient(850px 480px at 82% -12%, rgba(123,105,255,.19), transparent 65%),
        radial-gradient(650px 420px at -12% 18%, rgba(55,205,190,.10), transparent 65%),
        var(--bg);
    }
    [data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer { visibility: hidden; }
    .block-container { max-width: 1320px; padding-top: 2rem; padding-bottom: 4rem; }
    h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: -.035em; color: var(--text) !important; }
    p, li, label, [data-testid="stMarkdownContainer"] { color: var(--text); }
    [data-testid="stCaptionContainer"] { color: var(--muted) !important; }

    [data-testid="stSidebar"] {
      background: linear-gradient(180deg, #0D1325 0%, #0A1020 100%);
      border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] > div { padding-top: 1.4rem; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--muted); }

    .brand {
      display:flex; align-items:center; gap: .72rem;
      font: 700 1.28rem 'Space Grotesk', sans-serif;
      letter-spacing:-.04em; color:var(--text); margin: .2rem 0 1.5rem;
    }
    .brand-mark {
      width:34px;height:34px;border-radius:11px;display:inline-flex;align-items:center;justify-content:center;
      color:#08111C;font-size:18px;font-weight:800;
      background:linear-gradient(135deg,var(--purple),var(--cyan));
      box-shadow:0 7px 24px rgba(139,124,255,.28);
    }
    .eyebrow {
      display:inline-flex;align-items:center;gap:.48rem;
      color:#B9B4FF;background:rgba(139,124,255,.10);
      border:1px solid rgba(139,124,255,.25);border-radius:999px;
      padding:.38rem .72rem;font-size:.76rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
    }
    .eyebrow-dot { width:7px;height:7px;border-radius:50%;background:var(--cyan);box-shadow:0 0 12px var(--cyan); }
    .hero-title {
      font:700 clamp(2.5rem,5vw,4.5rem)/1.04 'Space Grotesk',sans-serif;
      letter-spacing:-.065em;max-width:850px;margin:1.15rem 0 .9rem;color:var(--text);
    }
    .gradient-text {
      background:linear-gradient(100deg,#A69BFF 8%,#65DCCC 90%);
      -webkit-background-clip:text;background-clip:text;color:transparent;
    }
    .hero-copy { color:var(--muted);font-size:1.08rem;line-height:1.75;max-width:650px; }
    .section-kicker { color:#A8B4D2;font-size:.76rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.45rem; }
    .section-title { font:600 1.45rem 'Space Grotesk',sans-serif;color:var(--text);letter-spacing:-.035em; }
    .surface-card {
      background:linear-gradient(145deg,rgba(24,33,57,.92),rgba(14,21,39,.96));
      border:1px solid var(--line);border-radius:20px;padding:1.35rem 1.45rem;
      box-shadow:0 16px 50px rgba(0,0,0,.13);
    }
    .feature-card {
      min-height:150px;background:rgba(17,25,45,.78);border:1px solid var(--line);
      border-radius:17px;padding:1.05rem 1.1rem;transition:all .2s ease;
    }
    .feature-icon {
      width:36px;height:36px;border-radius:11px;display:flex;align-items:center;justify-content:center;
      background:rgba(139,124,255,.14);color:#B9B0FF;font-size:18px;margin-bottom:.8rem;
    }
    .feature-title {font-weight:700;font-size:.98rem;margin-bottom:.35rem;color:var(--text);}
    .feature-copy {font-size:.84rem;line-height:1.55;color:var(--muted);}
    .muted {color:var(--muted);}
    .chip {
      display:inline-block;border:1px solid var(--line);background:rgba(18,27,48,.75);
      border-radius:999px;padding:.36rem .68rem;margin:.2rem .28rem .2rem 0;
      color:#B5C1DD;font-size:.78rem;
    }
    .metric {
      background:linear-gradient(145deg,rgba(24,33,57,.9),rgba(13,20,38,.95));
      border:1px solid var(--line);border-radius:16px;padding:1rem 1.05rem;
      min-height:104px;
    }
    .metric-value {font:700 1.8rem 'Space Grotesk',sans-serif;color:#B7AEFF;letter-spacing:-.05em;}
    .metric-label {font-size:.78rem;color:var(--muted);margin-top:.18rem;}
    .result-heading {font:700 clamp(1.8rem,3vw,2.6rem)/1.1 'Space Grotesk',sans-serif;letter-spacing:-.05em;}
    .result-sub {color:var(--muted);font-size:.9rem;margin-top:.45rem;}
    .item-card {
      padding:.85rem 1rem;margin:.5rem 0;border:1px solid var(--line);
      border-left:3px solid var(--purple);border-radius:12px;background:rgba(17,25,45,.82);
      line-height:1.6;color:#E9EDFA;font-size:.92rem;
    }
    .item-task {border-left-color:var(--green);}
    .item-decision {border-left-color:var(--purple);}
    .item-question {border-left-color:var(--amber);}
    .empty-state {padding:1rem;border:1px dashed var(--line);border-radius:12px;color:var(--muted);font-size:.9rem;}
    .step-wrap {display:flex;gap:.45rem;flex-wrap:wrap;margin:.9rem 0 1.1rem;}
    .step {
      border:1px solid var(--line);background:rgba(17,25,45,.9);color:var(--muted);
      padding:.48rem .72rem;border-radius:999px;font-size:.78rem;display:flex;align-items:center;gap:.42rem;
    }
    .step-dot {width:7px;height:7px;border-radius:50%;background:#46516F;}
    .step.done {color:#7CE4B7;border-color:rgba(87,217,163,.3);background:rgba(87,217,163,.08);}
    .step.done .step-dot {background:var(--green);}
    .step.active {color:#E9E6FF;border-color:rgba(139,124,255,.5);background:rgba(139,124,255,.15);}
    .step.active .step-dot {background:var(--purple);box-shadow:0 0 10px var(--purple);}
    .sidebar-note {font-size:.78rem;color:var(--muted);line-height:1.6;}
    div[data-testid="stVerticalBlockBorderWrapper"] {
      background:rgba(16,22,41,.72);border:1px solid var(--line);border-radius:18px;
    }

    /* Streamlit widgets */
    .stTextInput input,.stTextArea textarea {
      background:#0D1528 !important;color:var(--text) !important;
      border:1px solid rgba(157,174,226,.2) !important;border-radius:12px !important;
    }
    .stTextInput input:focus,.stTextArea textarea:focus {
      border-color:var(--purple) !important;box-shadow:0 0 0 3px rgba(139,124,255,.15) !important;
    }
    [data-baseweb="select"] > div {background:#0D1528 !important;border-color:var(--line) !important;border-radius:11px !important;}
    [data-testid="stFileUploaderDropzone"] {background:#0D1528;border:1px dashed rgba(139,124,255,.45);border-radius:14px;}
    [data-testid="stFileUploaderDropzone"] * {color:#AEB9D5 !important;}
    .stButton > button,.stDownloadButton > button {
      border:1px solid var(--line);border-radius:11px;background:#17213A;color:var(--text);
      font-weight:700;min-height:2.7rem;transition:all .18s ease;
    }
    .stButton > button:hover,.stDownloadButton > button:hover {border-color:var(--purple);color:white;transform:translateY(-1px);}
    .stButton > button[kind="primary"] {
      background:linear-gradient(105deg,#9587FF,#53D7C6);border:0;color:#07121B;
      box-shadow:0 8px 26px rgba(139,124,255,.2);
    }
    .stButton > button[kind="primary"] p {color:#07121B !important;font-weight:800;}
    .stTabs [data-baseweb="tab-list"] {gap:.35rem;border-bottom:1px solid var(--line);}
    .stTabs [data-baseweb="tab"] {color:var(--muted);font-weight:700;padding:.75rem 1rem;}
    .stTabs [aria-selected="true"] {color:#C9C2FF !important;}
    .stTabs [data-baseweb="tab-highlight"] {background:linear-gradient(90deg,var(--purple),var(--cyan));height:3px;}
    [data-testid="stChatMessage"] {background:rgba(17,25,45,.9);border:1px solid var(--line);border-radius:15px;}
    [data-testid="stChatMessage"] * {color:var(--text);}
    [data-testid="stChatInput"] {background:#10182B;border:1px solid var(--line);border-radius:14px;}
    [data-testid="stChatInput"] textarea {color:var(--text) !important;}
    [data-testid="stExpander"] {border:1px solid var(--line);border-radius:12px;background:rgba(16,22,41,.5);}
    hr {border-color:var(--line) !important;}
    @media (max-width: 760px) {
      .block-container {padding:1rem 1rem 3rem;}
      .hero-title {font-size:2.65rem;}
      .surface-card {padding:1rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ───────────────────────────── Helpers ─────────────────────────────
STAGES = [
    "Fetch audio", "Transcribe", "Title & summary",
    "Action items", "Key decisions", "Open questions", "Index for chat",
]


def H(value: str) -> str:
    return "".join(line.strip() for line in value.strip().splitlines())


def stepper(done: int, active: int | None = None) -> str:
    pieces = []
    for i, name in enumerate(STAGES):
        cls = "done" if i < done else "active" if i == active else ""
        pieces.append(
            f'<div class="step {cls}"><span class="step-dot"></span>{html.escape(name)}</div>'
        )
    return f'<div class="step-wrap">{"".join(pieces)}</div>'


def to_items(value) -> list[str]:
    if not value:
        return []
    raw = value if isinstance(value, list) else str(value).splitlines()
    cleaned = [
        re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", str(x)).strip()
        for x in raw
    ]
    return [item for item in cleaned if item and not item.lower().startswith(("none", "n/a"))]


def text_of(value) -> str:
    return value if isinstance(value, str) else "\n".join(map(str, value))


def run_pipeline_ui(source: str, placeholder) -> dict:
    """Run the original pipeline and display real stage transitions."""
    started = time.time()
    result = {}

    def show(done, active=None):
        placeholder.markdown(stepper(done, active), unsafe_allow_html=True)

    show(0, 0)
    chunks = process_audio_from_youtube(source)
    show(1, 1)
    transcript = transcribe_all(chunks)
    show(2, 2)
    result["title"] = generate_title(transcript)
    result["summary"] = summarize_chunks(transcript)
    show(3, 3)
    result["action_items"] = extract_action_items(transcript)
    show(4, 4)
    result["key_decisions"] = extract_key_decisions(transcript)
    show(5, 5)
    result["open_questions"] = extract_questions(transcript)
    show(6, 6)
    result["rag_chain"] = build_rag_chain(transcript)
    show(7)

    result["transcript"] = transcript
    result["seconds"] = time.time() - started
    return result


def render_items(items: list[str], css_class: str, empty_text: str):
    if not items:
        st.markdown(f'<div class="empty-state">{html.escape(empty_text)}</div>', unsafe_allow_html=True)
        return
    for item in items:
        st.markdown(
            f'<div class="item-card {css_class}">{html.escape(item)}</div>',
            unsafe_allow_html=True,
        )


def build_report(result: dict) -> str:
    def bullets(value):
        return "\n".join(f"- {item}" for item in to_items(value)) or "_None_"

    return (
        f"# {result['title']}\n\n## Summary\n{text_of(result['summary'])}\n\n"
        f"## Action items\n{bullets(result['action_items'])}\n\n"
        f"## Key decisions\n{bullets(result['key_decisions'])}\n\n"
        f"## Open questions\n{bullets(result['open_questions'])}\n"
    )


def brand():
    st.markdown(
        '<div class="brand"><span class="brand-mark">M</span>MeetLens</div>',
        unsafe_allow_html=True,
    )


# ───────────────────────────── Sidebar ─────────────────────────────
with st.sidebar:
    brand()
    st.markdown('<div class="section-kicker">Workspace</div>', unsafe_allow_html=True)
    st.markdown("**✦  New analysis**")
    st.caption("Turn a video into useful knowledge.")
    st.divider()

    language = st.selectbox(
        "🎧  Spoken language",
        ["english", "hinglish"],
        help="Choose the primary spoken language in the audio.",
    )
    st.markdown('<div class="sidebar-note">Choose the language that best matches the audio for more accurate transcription.</div>', unsafe_allow_html=True)

    st.divider()
    with st.expander("How MeetLens works"):
        st.markdown(
            "1. Fetches audio from YouTube or your uploaded file.\n"
            "2. Splits audio into chunks and transcribes it.\n"
            "3. Generates a title, summary, tasks and decisions.\n"
            "4. Indexes the transcript so you can ask follow-up questions."
        )
    with st.expander("Technology"):
        st.markdown("Python · Streamlit · Whisper-style ASR · LangChain · LLM · RAG")
    st.divider()
    st.markdown(
        '<div class="sidebar-note">MADE FOR BETTER MEETINGS<br>MeetLens · AI meeting intelligence</div>',
        unsafe_allow_html=True,
    )
    if st.session_state.get("result"):
        if st.button("＋  Start a new analysis", use_container_width=True, type="primary"):
            for key in ("result", "chat", "pending"):
                st.session_state.pop(key, None)
            st.rerun()

# ───────────────────────────── Landing ─────────────────────────────
if "result" not in st.session_state:
    brand()
    st.markdown(
        """
        <div class="hero">
          <span class="eyebrow"><span class="eyebrow-dot"></span> AI-POWERED VIDEO INTELLIGENCE</span>
          <div class="hero-title">Never rewatch a meeting.<br><span class="gradient-text">Get the insights.</span></div>
          <div class="hero-copy">Drop in a video or paste a YouTube link. MeetLens turns hours of conversation into clear summaries, decisions, action items, and answers.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    left, right = st.columns([1.35, 0.85], gap="large")

    with left:
        with st.container(border=True):
            st.markdown('<div class="section-kicker">Start with your source</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-title">What should we analyse?</div>', unsafe_allow_html=True)
            st.caption("Choose a YouTube video or upload an audio/video file.")
            tab_url, tab_file = st.tabs(["▶  YouTube link", "↑  Upload a file"])
            with tab_url:
                url = st.text_input(
                    "YouTube URL",
                    placeholder="https://www.youtube.com/watch?v=...",
                    label_visibility="collapsed",
                    key="youtube_url",
                )
                st.caption("Paste a public YouTube video link.")
                upload = None
            with tab_file:
                upload = st.file_uploader(
                    "Choose an audio or video file",
                    type=["mp3", "wav", "m4a", "mp4", "mkv", "webm"],
                    label_visibility="collapsed",
                    key="media_upload",
                )
                if upload is not None:
                    st.caption(f"Selected: {upload.name} · {upload.size / (1024 * 1024):.1f} MB")

            st.write("")
            go = st.button("✨  Analyse video", type="primary", use_container_width=True)
            progress_slot = st.empty()

        st.markdown(
            '<div style="margin-top:.85rem">'
            '<span class="chip">Whisper transcription</span>'
            '<span class="chip">AI summaries</span>'
            '<span class="chip">Action extraction</span>'
            '<span class="chip">RAG-powered chat</span>'
            '<span class="chip">English + Hinglish</span></div>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            """
            <div class="surface-card">
              <div class="section-kicker">From conversation to clarity</div>
              <div class="section-title" style="margin-bottom:1rem">Everything important, in one place.</div>
              <div class="feature-card" style="margin-bottom:.7rem">
                <div class="feature-icon">✧</div>
                <div class="feature-title">Executive summary</div>
                <div class="feature-copy">Understand the full discussion without replaying the video.</div>
              </div>
              <div class="feature-card" style="margin-bottom:.7rem">
                <div class="feature-icon">✓</div>
                <div class="feature-title">Action items & decisions</div>
                <div class="feature-copy">Know what was decided and what needs to happen next.</div>
              </div>
              <div class="feature-card">
                <div class="feature-icon">⌕</div>
                <div class="feature-title">Ask the meeting</div>
                <div class="feature-copy">Find answers directly from the transcript with AI chat.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown('<div class="section-kicker">A simpler way to stay in sync</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Less watching. More doing.</div>', unsafe_allow_html=True)
    feature_cols = st.columns(3, gap="medium")
    features = [
        ("01", "Understand faster", "Get the context and key takeaways at a glance."),
        ("02", "Stay accountable", "Capture follow-ups and decisions before they get lost."),
        ("03", "Find the answer", "Ask questions and search the conversation naturally."),
    ]
    for col, (number, title, description) in zip(feature_cols, features):
        with col:
            st.markdown(
                f'<div class="feature-card"><div class="section-kicker">{number}</div>'
                f'<div class="feature-title">{title}</div><div class="feature-copy">{description}</div></div>',
                unsafe_allow_html=True,
            )

    if go:
        source = ""
        if upload is not None:
            suffix = os.path.splitext(upload.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(upload.getbuffer())
                source = tmp.name
        elif url.strip():
            source = url.strip()

        if not source:
            st.warning("Paste a YouTube URL or upload a media file to begin.")
        else:
            try:
                st.session_state.result = run_pipeline_ui(source, progress_slot)
                st.session_state.chat = []
                st.session_state.language = language
                st.rerun()
            except Exception as exc:
                traceback.print_exc()
                err_str = str(exc)
                if "403" in err_str or "blocked" in err_str.lower():
                    st.error(
                        "⛔ **YouTube blocked the download from this cloud server.**\n\n"
                        "YouTube restricts downloads from datacenter IPs. "
                        "To work around this:\n\n"
                        "1. Download the video/audio to your device first\n"
                        "2. Use the **↑ Upload a file** tab to upload it here\n\n"
                        "File upload works reliably and supports MP3, WAV, M4A, MP4, MKV, and WebM."
                    )
                else:
                    st.error(
                        f"Analysis could not be completed: {exc}. "
                        "Check the video/file, dependencies, and API keys."
                    )

# ───────────────────────────── Results workspace ─────────────────────────────
else:
    result = st.session_state.result
    actions = to_items(result.get("action_items"))
    decisions = to_items(result.get("key_decisions"))
    questions = to_items(result.get("open_questions"))
    transcript = text_of(result.get("transcript", ""))
    word_count = len(transcript.split())

    brand()
    st.markdown('<div class="section-kicker">Your analysis workspace</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="result-heading">{html.escape(str(result.get("title", "Meeting analysis")))}</div>'
        '<div class="result-sub">Your conversation has been processed. Explore the summary, follow-ups, and transcript below.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    metrics = [
        (f"{word_count:,}", "Words transcribed"),
        (f"{max(1, word_count // 200)} min", "Estimated reading time"),
        (str(len(actions)), "Action items"),
        (str(len(decisions)), "Key decisions"),
        (f"{result.get('seconds', 0):.0f}s", "Processing time"),
    ]
    metric_cols = st.columns(5, gap="small")
    for col, (value, label) in zip(metric_cols, metrics):
        with col:
            st.markdown(
                f'<div class="metric"><div class="metric-value">{value}</div>'
                f'<div class="metric-label">{label}</div></div>',
                unsafe_allow_html=True,
            )

    st.write("")
    tab_overview, tab_chat, tab_transcript = st.tabs(
        ["✦  Overview", "✧  Ask the meeting", "▤  Transcript"]
    )

    with tab_overview:
        st.markdown('<div class="section-kicker">The big picture</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("### Executive summary")
            st.markdown(text_of(result.get("summary", "")))

        st.write("")
        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            st.markdown(f"**✓  Action items**  ·  {len(actions)}")
            render_items(actions, "item-task", "No action items were identified.")
        with c2:
            st.markdown(f"**✦  Key decisions**  ·  {len(decisions)}")
            render_items(decisions, "item-decision", "No key decisions were identified.")
        with c3:
            st.markdown(f"**?  Open questions**  ·  {len(questions)}")
            render_items(questions, "item-question", "No open questions were identified.")

        st.write("")
        st.download_button(
            "↓  Download meeting report",
            build_report(result),
            file_name="meetlens_report.md",
            mime="text/markdown",
            use_container_width=False,
        )

    with tab_chat:
        st.markdown('<div class="section-kicker">Grounded in your transcript</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Ask anything about this meeting.</div>', unsafe_allow_html=True)
        history = st.session_state.setdefault("chat", [])

        if not history:
            st.caption("Not sure where to start? Try a suggested question.")
            suggestions = [
                "What were the main takeaways?",
                "Who owns which task?",
                "What is still undecided?",
            ]
            suggestion_cols = st.columns(3)
            for col, suggestion in zip(suggestion_cols, suggestions):
                with col:
                    if st.button(suggestion, use_container_width=True):
                        st.session_state.pending = suggestion
                        st.rerun()

        for message in history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        question = st.chat_input("Ask a question about the video or meeting…")
        if not question:
            question = st.session_state.pop("pending", None)

        if question:
            history.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Searching the transcript for an answer…"):
                    try:
                        answer = ask_question(result["rag_chain"], question)
                    except Exception as exc:
                        answer = f"I couldn't answer that: {exc}"
                st.markdown(answer)
            history.append({"role": "assistant", "content": answer})

    with tab_transcript:
        st.markdown('<div class="section-kicker">Full conversation text</div>', unsafe_allow_html=True)
        search_term = st.text_input(
            "Search transcript",
            placeholder="Search for a name, topic, or phrase…",
            key="transcript_search",
        )
        lines = transcript.splitlines() or [transcript]
        if search_term:
            lines = [line for line in lines if search_term.lower() in line.lower()]
            st.caption(f"{len(lines)} matching lines")
        st.text_area(
            "Transcript",
            "\n".join(lines),
            height=440,
            label_visibility="collapsed",
        )
        st.download_button(
            "↓  Download transcript",
            transcript,
            file_name="meetlens_transcript.txt",
            mime="text/plain",
        )
