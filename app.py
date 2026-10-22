"""Minimal Streamlit interface for TechBrief AI."""
import html
import os
import queue
import threading
import time
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from news_crew import run_newsletter

load_dotenv()
st.set_page_config(page_title="TechBrief AI", page_icon="📰", layout="centered")

TOPICS = [
    ("AI & generative AI", "Models, agents, and AI products"),
    ("Cybersecurity", "Threats, privacy, and security"),
    ("Developer tools", "Programming and engineering"),
    ("Cloud computing", "Platforms and infrastructure"),
    ("Chips & hardware", "Semiconductors and devices"),
    ("Tech business", "Startups and major companies"),
]

st.markdown("""
<style>
header[data-testid="stHeader"]{background:transparent}
[data-testid="stDecoration"]{display:none}
.block-container{max-width:1000px;padding-top:2rem}
[data-testid="stSidebar"]{border-right:1px solid #E5E7EB}
.brand{display:flex;gap:.65rem;align-items:center;margin-bottom:1.2rem}
.logo{background:#172554;color:white;border-radius:10px;width:36px;height:36px;
display:grid;place-items:center;font-weight:700}
.brand-title{font-weight:650}.muted{color:#6B7280;font-size:13px}
.hero{text-align:center;margin:6vh 0 1.5rem}
.hero h1{font-size:30px;letter-spacing:-.03em;font-weight:650}
.hero p{color:#6B7280}
.st-key-topic_cards button{justify-content:flex-start;text-align:left;min-height:4rem;
border:1px solid #E5E7EB;border-radius:12px;background:white}
.newsletter{white-space:pre-wrap;line-height:1.8;font-size:15px}
</style>
""", unsafe_allow_html=True)

for key, default in {
    "topic_input": "", "runs": [], "active": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def choose_topic(topic):
    st.session_state.topic_input = topic


with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="logo">T</div><div>'
        '<div class="brand-title">TechBrief AI</div>'
        '<div class="muted">Daily technology newsletter</div></div></div>',
        unsafe_allow_html=True,
    )
    if st.button("New briefing", icon=":material/edit_square:", use_container_width=True):
        st.session_state.topic_input = ""
        st.session_state.active = None
        st.rerun()
    st.markdown("**CURRENT SESSION**")
    st.caption(f"{len(st.session_state.runs)} briefing(s) generated this session")
    for run in reversed(st.session_state.runs[-5:]):
        with st.expander(f"{run['topic']} · {run['created_at']}"):
            st.write(run["newsletter"])
    st.markdown("**HOW IT WORKS**")
    st.markdown(
        '<div class="muted">1. Choose a topic<br>2. Researcher finds recent stories'
        '<br>3. Writer creates five lines<br>4. Validate and review</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="hero"><h1>What is happening in tech today?</h1>'
    '<p>Choose a topic or enter your own. Get a concise five-line briefing.</p></div>',
    unsafe_allow_html=True,
)
with st.container(key="topic_cards"):
    cols = st.columns(2)
    for i, (topic, subtitle) in enumerate(TOPICS):
        cols[i % 2].button(
            f"**{topic}**  \n{subtitle}", key=f"topic_{i}",
            use_container_width=True, on_click=choose_topic, args=(topic,),
        )

topic = st.text_input(
    "Topic", placeholder="e.g. AI agents in software development",
    key="topic_input",
)
left, right = st.columns([1, 2])
with left:
    generate = st.button("Generate briefing", type="primary",
                         icon=":material/auto_awesome:", use_container_width=True)
with right:
    st.markdown('<div class="muted" style="padding-top:.6rem">Requires OpenAI and Serper API keys in .env.</div>',
                unsafe_allow_html=True)

if generate:
    topic = topic.strip()
    if not topic:
        st.warning("Enter a topic or select a suggestion.")
    elif not os.getenv("OPENAI_API_KEY") or not os.getenv("SERPER_API_KEY"):
        st.error("API keys are missing. Configure OPENAI_API_KEY and SERPER_API_KEY in .env.")
    else:
        events = queue.Queue()
        result_box = {}

        def callback(event):
            role = getattr(getattr(event, "agent", None), "role", None)
            events.put(str(role or event)[:160])

        def worker():
            try:
                result_box["output"] = run_newsletter(topic, callback)
            except Exception as exc:
                result_box["error"] = str(exc)

        st.subheader("Creating your briefing")
        research_status = st.empty()
        writer_status = st.empty()
        validation_status = st.empty()
        activity = st.empty()
        research_status.info("Researcher · Running the research task")
        writer_status.info("Writer · Waiting for research")
        validation_status.info("Validation · Waiting for output")
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        last_activity = ""
        while thread.is_alive():
            try:
                while True:
                    last_activity = events.get_nowait()
            except queue.Empty:
                pass
            if last_activity:
                activity.caption("Latest CrewAI activity: " + last_activity)
            time.sleep(0.25)
        thread.join()
        if "error" in result_box:
            research_status.error("The crew did not complete.")
            st.error(f"Could not generate the briefing: {result_box['error']}")
        else:
            output = result_box["output"]
            research_status.success("Crew execution completed.")
            writer_status.success("Writer returned a newsletter.")
            evaluation = output["evaluation"]
            if evaluation["valid"]:
                validation_status.success("Five-line format check passed.")
            else:
                validation_status.warning(evaluation["message"])
            item = {
                "topic": topic, "newsletter": output["newsletter"],
                "evaluation": evaluation,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            st.session_state.runs.append(item)
            st.session_state.active = item
            st.rerun()

if st.session_state.active:
    item = st.session_state.active
    st.divider()
    st.subheader("Your tech briefing")
    st.caption("Topic: " + item["topic"])
    st.markdown(
        '<div class="newsletter">' + html.escape(item["newsletter"]) + '</div>',
        unsafe_allow_html=True,
    )
    if item["evaluation"]["valid"]:
        st.success("The newsletter passed the five-line format check.")
    else:
        st.warning(item["evaluation"]["message"])
    st.caption("Review the Researcher's source details in the verbose terminal output before relying on a claim.")
