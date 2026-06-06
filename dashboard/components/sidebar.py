"""Shared sidebar component for Streamlit dashboard.

Renders branding, login status, and API configuration consistently across all pages.
"""

import streamlit as st
import requests
import os
from pathlib import Path

def detect_api_url() -> str:
    """Detect if the backend is running on 8080, 8000 or defined in environment/env files."""
    # 1. Check if custom env var is set
    env_url = os.getenv("API_BASE_URL")
    if env_url:
        return env_url

    # 2. Check port 8080 and 8000 dynamically (fast ping)
    for url in ["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:8000", "http://127.0.0.1:8000"]:
        try:
            r = requests.get(f"{url}/health", timeout=0.15)
            if r.status_code == 200:
                return url
        except requests.RequestException:
            continue

    # 3. Fallback to reading from .env file
    try:
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith("API_BASE_URL="):
                        val = line.split("=", 1)[1].strip()
                        if val.startswith(('"', "'")) and val.endswith(('"', "'")):
                            val = val[1:-1]
                        return val
    except Exception:
        pass

    return "http://localhost:8000"


def render_sidebar():
    """Render consistent sidebar branding, auth state, and developer settings across all pages."""
    # Ensure api_base_url is initialized in session state
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = detect_api_url()

    with st.sidebar:
        st.title("AI Resume-Job Matcher")
        st.caption("Find your perfect role, automatically.")

        st.divider()

        if st.session_state.get("auth_token"):
            st.success(f"Logged in as {st.session_state.get('user_email')}")
            if st.button("Log out", use_container_width=True):
                st.session_state.auth_token = None
                st.session_state.user_email = None
                st.rerun()
        else:
            st.info("Please log in using the main page.")

        st.divider()

        # API base URL config (for development)
        with st.expander("Developer Settings", expanded=False):
            api_url = st.text_input(
                "API Base URL",
                value=st.session_state.api_base_url,
                help="URL of the FastAPI backend",
            )
            if api_url != st.session_state.api_base_url:
                st.session_state.api_base_url = api_url
                st.rerun()
