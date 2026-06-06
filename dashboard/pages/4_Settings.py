"""Settings page for user preferences and API configuration."""

import streamlit as st
import requests


st.set_page_config(page_title="Settings - AI Job Matcher", page_icon="briefcase", layout="wide")

st.title("Settings")
st.caption("Configure your matching preferences and notification settings.")

# ─── Auth Check ──────────────────────────────────────────────────────────────

if not st.session_state.get("auth_token"):
    st.warning("Please log in from the main page first.")
    st.stop()

api_headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
base = st.session_state.get("api_base_url", "http://localhost:8000")


# ─── Load Current Settings ───────────────────────────────────────────────────

# Note: User profile is managed via Supabase. We'll provide direct forms
# that update the users table through a profile endpoint.
# For now, settings are managed through Streamlit session state and .env.

st.subheader("Notification Settings")

with st.form("discord_settings"):
    discord_url = st.text_input(
        "Discord Webhook URL",
        value=st.session_state.get("discord_webhook_url", ""),
        placeholder="https://discord.com/api/webhooks/...",
        help=(
            "Create a webhook in your Discord server: "
            "Channel Settings > Integrations > Webhooks"
        ),
    )

    if st.form_submit_button("Save Webhook", use_container_width=True):
        st.session_state.discord_webhook_url = discord_url
        st.success("Discord webhook URL saved to session.")
        st.info(
            "Note: To persist this across sessions, set DISCORD_WEBHOOK_URL "
            "in your .env file or update your user profile in the database."
        )


st.divider()


# ─── Matching Preferences ────────────────────────────────────────────────────

st.subheader("Matching Preferences")

with st.form("match_preferences"):
    threshold = st.slider(
        "Match Alert Threshold",
        min_value=0,
        max_value=100,
        value=st.session_state.get("match_threshold", 80),
        step=5,
        help="Only send Discord alerts for matches scoring above this threshold.",
    )

    location = st.text_input(
        "Location Preference",
        value=st.session_state.get("location_preference", ""),
        placeholder="e.g., San Francisco, Remote, New York",
        help="Your preferred job location. 'Remote' will boost remote-friendly roles.",
    )

    if st.form_submit_button("Save Preferences", use_container_width=True):
        st.session_state.match_threshold = threshold
        st.session_state.location_preference = location
        st.success("Preferences saved to session.")


st.divider()


# ─── API Connection Status ───────────────────────────────────────────────────

st.subheader("Connection Status")

col1, col2, col3 = st.columns(3)

# FastAPI Backend
with col1:
    st.write("**Backend API**")
    try:
        r = requests.get(f"{base}/health", timeout=5)
        if r.status_code == 200:
            st.success("Connected")
        else:
            st.error(f"Error: HTTP {r.status_code}")
    except requests.RequestException:
        st.error("Not reachable")

# Auth status
with col2:
    st.write("**Authentication**")
    if st.session_state.get("auth_token"):
        st.success(f"Authenticated as {st.session_state.get('user_email', 'Unknown')}")
    else:
        st.warning("Not authenticated")

# Resume status
with col3:
    st.write("**Resume**")
    try:
        r = requests.get(f"{base}/api/resumes/current", headers=api_headers, timeout=5)
        if r.status_code == 200 and r.json():
            resume = r.json()
            st.success(f"Uploaded: {resume.get('filename', 'Unknown')}")
        else:
            st.warning("Not uploaded")
    except requests.RequestException:
        st.error("Could not check")


st.divider()


# ─── Scrape History ──────────────────────────────────────────────────────────

st.subheader("Recent Scrape Runs")

try:
    r = requests.get(
        f"{base}/api/scraping/history",
        headers=api_headers,
        params={"limit": 10},
        timeout=10,
    )

    if r.status_code == 200:
        runs = r.json()

        if not runs:
            st.info("No scrape runs yet. Trigger one from the Sources page.")
        else:
            for run in runs:
                started = run.get("started_at", "")[:16].replace("T", " ")
                completed = run.get("completed_at")
                status_text = "Completed" if completed else "Running..."
                errors = run.get("errors", [])

                col1, col2, col3, col4, col5 = st.columns(5)
                col1.write(f"**{started}**")
                col2.write(f"Jobs: {run.get('jobs_found', 0)}")
                col3.write(f"New: {run.get('new_jobs', 0)}")
                col4.write(f"Matches: {run.get('matches_found', 0)}")

                if errors:
                    col5.error(f"{len(errors)} errors")
                else:
                    col5.success(status_text)

    else:
        st.error("Failed to load scrape history.")

except requests.RequestException:
    st.error("Could not connect to the API.")


st.divider()


# ─── Danger Zone ─────────────────────────────────────────────────────────────

with st.expander("Danger Zone"):
    st.warning("These actions are irreversible.")

    if st.button("Clear All Session Data"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Session cleared. Refreshing...")
        st.rerun()
