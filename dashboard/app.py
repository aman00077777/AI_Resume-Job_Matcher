"""Streamlit dashboard entry point.

Multi-page app for managing resumes, company sources, and viewing
job matches. Communicates with the FastAPI backend via REST API.
"""

import streamlit as st

# ─── Page Configuration ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Resume-Job Matcher",
    page_icon="briefcase",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Dark theme overrides */
    .stApp {
        background-color: #0e1117;
    }

    /* Score badge styles */
    .score-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 16px;
        font-weight: 700;
        font-size: 14px;
        color: white;
    }
    .score-excellent { background: linear-gradient(135deg, #00c853, #00e676); }
    .score-strong { background: linear-gradient(135deg, #ff8f00, #ffab00); }
    .score-moderate { background: linear-gradient(135deg, #2962ff, #2979ff); }
    .score-low { background: linear-gradient(135deg, #616161, #9e9e9e); }

    /* Card style */
    .match-card {
        background: #1a1d23;
        border: 1px solid #2d2f36;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        transition: border-color 0.2s;
    }
    .match-card:hover {
        border-color: #4a4d56;
    }

    /* Sidebar branding */
    [data-testid="stSidebar"] {
        background-color: #0a0d12;
    }

    /* Hide default streamlit footer */
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─── Session State Initialization ────────────────────────────────────────────

if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None

from dashboard.components.sidebar import render_sidebar
render_sidebar()


# ─── Main Page (Auth Gate) ───────────────────────────────────────────────────

if not st.session_state.auth_token:
    from dashboard.components.auth_ui import render_auth_page
    render_auth_page()
else:
    st.title("Dashboard")
    st.write("Use the sidebar to navigate between pages.")

    # Quick stats
    import requests

    headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
    base = st.session_state.api_base_url

    col1, col2, col3 = st.columns(3)

    # Sources count
    try:
        r = requests.get(f"{base}/api/sources", headers=headers, timeout=5)
        sources = r.json() if r.status_code == 200 else []
        active = sum(1 for s in sources if s.get("is_active"))
        col1.metric("Active Sources", active, f"{len(sources)} total")
    except Exception:
        col1.metric("Active Sources", "N/A")

    # Resume status
    try:
        r = requests.get(f"{base}/api/resumes/current", headers=headers, timeout=5)
        if r.status_code == 200 and r.json():
            resume = r.json()
            col2.metric("Resume Skills", len(resume.get("skills", [])))
        else:
            col2.metric("Resume", "Not uploaded")
    except Exception:
        col2.metric("Resume", "N/A")

    # Recent matches
    try:
        r = requests.get(
            f"{base}/api/jobs",
            headers=headers,
            params={"min_score": 80, "limit": 100},
            timeout=5,
        )
        matches = r.json() if r.status_code == 200 else []
        col3.metric("Strong Matches", len(matches))
    except Exception:
        col3.metric("Strong Matches", "N/A")
