"""Job matches page with filters, detail views, and export."""

import streamlit as st
import requests

from dashboard.components.charts import (
    create_score_radar,
    create_score_distribution,
    create_matches_timeline,
)


st.set_page_config(page_title="Matches - AI Job Matcher", page_icon="briefcase", layout="wide")

st.title("Job Matches")
st.caption("AI-scored matches between your resume and discovered job openings.")

from dashboard.components.sidebar import render_sidebar
render_sidebar()

# ─── Auth Check ──────────────────────────────────────────────────────────────

if not st.session_state.get("auth_token"):
    st.warning("Please log in from the main page first.")
    st.stop()

api_headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
base = st.session_state.api_base_url


# ─── Sidebar Filters ─────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Filters")

    min_score = st.slider("Minimum Score", 0, 100, 0, step=5)
    max_score = st.slider("Maximum Score", 0, 100, 100, step=5)

    status_options = ["All", "new", "applied", "not_interested", "saved"]
    status_filter = st.selectbox("Status", status_options)

    company_filter = st.text_input("Company", placeholder="Filter by company name...")

    date_from = st.date_input("From Date", value=None)
    date_to = st.date_input("To Date", value=None)

    st.divider()

    # Export button
    if st.button("Export to CSV", use_container_width=True):
        try:
            params = {"min_score": min_score}
            if status_filter != "All":
                params["status"] = status_filter

            r = requests.get(
                f"{base}/api/jobs/export/csv",
                headers=api_headers,
                params=params,
                timeout=15,
            )

            if r.status_code == 200:
                st.download_button(
                    "Download CSV",
                    data=r.content,
                    file_name="job_matches.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.error("Export failed.")
        except requests.RequestException:
            st.error("Connection error.")


# ─── Fetch Matches ───────────────────────────────────────────────────────────

params = {
    "min_score": min_score,
    "max_score": max_score,
    "limit": 100,
}

if status_filter != "All":
    params["status"] = status_filter

if company_filter:
    params["company"] = company_filter

if date_from:
    params["date_from"] = date_from.isoformat()

if date_to:
    params["date_to"] = date_to.isoformat()

try:
    r = requests.get(f"{base}/api/jobs", headers=api_headers, params=params, timeout=15)

    if r.status_code != 200:
        st.error("Failed to load matches.")
        st.stop()

    matches = r.json()

except requests.RequestException:
    st.error("Could not connect to the API.")
    st.stop()


if not matches:
    st.info(
        "No matches found. Make sure you have uploaded a resume and added "
        "company sources, then trigger a scrape from the Sources page."
    )
    st.stop()


# ─── Analytics Overview ──────────────────────────────────────────────────────

st.subheader("Overview")

col1, col2, col3, col4 = st.columns(4)
scores = [m["overall_score"] for m in matches]

col1.metric("Total Matches", len(matches))
col2.metric("Avg Score", f"{sum(scores) / len(scores):.0f}%")
col3.metric("Best Match", f"{max(scores)}%")
col4.metric("Above 80%", sum(1 for s in scores if s >= 80))

# Charts
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    fig = create_score_distribution(matches)
    st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    fig = create_matches_timeline(matches)
    st.plotly_chart(fig, use_container_width=True)


# ─── Match List ──────────────────────────────────────────────────────────────

st.divider()
st.subheader("All Matches")

for match in matches:
    score = match["overall_score"]

    # Score badge color
    if score >= 90:
        badge_class = "score-excellent"
    elif score >= 80:
        badge_class = "score-strong"
    elif score >= 60:
        badge_class = "score-moderate"
    else:
        badge_class = "score-low"

    # Card header
    title = match.get("job_title", "Unknown Title")
    company = match.get("company_name", "Unknown Company")
    location = match.get("job_location", "")
    status = match.get("status", "new")
    job_url = match.get("job_url", "")

    with st.container():
        header_col, score_col = st.columns([4, 1])

        with header_col:
            st.markdown(
                f"### {title}\n"
                f"**{company}**"
                f"{f' | {location}' if location else ''}"
                f" | Status: `{status}`"
            )

        with score_col:
            st.markdown(
                f'<div style="text-align:center;padding-top:10px;">'
                f'<span class="{badge_class} score-badge">{score}%</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Summary
        st.write(match.get("summary", ""))

        # Expandable detail
        with st.expander("Score Breakdown"):
            detail_col1, detail_col2 = st.columns([1, 1])

            with detail_col1:
                fig = create_score_radar(
                    match["skills_score"],
                    match["experience_score"],
                    match["title_score"],
                    match["location_score"],
                )
                st.plotly_chart(fig, use_container_width=True)

            with detail_col2:
                st.write(f"**Skills:** {match['skills_score']}%")
                st.write(f"**Experience:** {match['experience_score']}%")
                st.write(f"**Title Fit:** {match['title_score']}%")
                st.write(f"**Location:** {match['location_score']}%")

                matching = match.get("matching_skills", [])
                missing = match.get("missing_skills", [])

                if matching:
                    st.write("**Matching Skills:** " + ", ".join(matching))
                if missing:
                    st.write("**Skills to Develop:** " + ", ".join(missing))

        # Action buttons
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

        with btn_col1:
            if job_url:
                st.link_button("Apply", job_url, use_container_width=True)

        with btn_col2:
            if status != "applied":
                if st.button("Mark Applied", key=f"apply_{match['id']}"):
                    try:
                        requests.patch(
                            f"{base}/api/jobs/{match['id']}/status",
                            headers=api_headers,
                            json={"status": "applied"},
                            timeout=10,
                        )
                        st.rerun()
                    except requests.RequestException:
                        st.error("Failed to update.")

        with btn_col3:
            if status != "saved":
                if st.button("Save", key=f"save_{match['id']}"):
                    try:
                        requests.patch(
                            f"{base}/api/jobs/{match['id']}/status",
                            headers=api_headers,
                            json={"status": "saved"},
                            timeout=10,
                        )
                        st.rerun()
                    except requests.RequestException:
                        st.error("Failed to update.")

        with btn_col4:
            if status != "not_interested":
                if st.button("Not Interested", key=f"skip_{match['id']}"):
                    try:
                        requests.patch(
                            f"{base}/api/jobs/{match['id']}/status",
                            headers=api_headers,
                            json={"status": "not_interested"},
                            timeout=10,
                        )
                        st.rerun()
                    except requests.RequestException:
                        st.error("Failed to update.")

        st.divider()
