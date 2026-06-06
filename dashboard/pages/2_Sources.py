"""Company career source management page."""

import streamlit as st
import requests


st.set_page_config(page_title="Sources - AI Job Matcher", page_icon="briefcase", layout="wide")

st.title("Company Sources")
st.caption("Add company career page URLs to monitor for new job openings.")

from dashboard.components.sidebar import render_sidebar
render_sidebar()

# ─── Auth Check ──────────────────────────────────────────────────────────────

if not st.session_state.get("auth_token"):
    st.warning("Please log in from the main page first.")
    st.stop()

headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
base = st.session_state.api_base_url


# ─── Add New Source ──────────────────────────────────────────────────────────

st.subheader("Add New Source")

with st.form("add_source_form"):
    col1, col2 = st.columns(2)

    with col1:
        company_name = st.text_input(
            "Company Name",
            placeholder="e.g., Stripe",
        )

    with col2:
        career_url = st.text_input(
            "Career Page URL",
            placeholder="e.g., https://stripe.com/jobs",
        )

    submitted = st.form_submit_button("Add Source", type="primary", use_container_width=True)

    if submitted:
        if not company_name or not career_url:
            st.error("Both company name and URL are required.")
        elif not career_url.startswith(("http://", "https://")):
            st.error("URL must start with http:// or https://")
        else:
            try:
                r = requests.post(
                    f"{base}/api/sources",
                    headers=headers,
                    json={
                        "company_name": company_name,
                        "career_url": career_url,
                    },
                    timeout=10,
                )

                if r.status_code == 201:
                    st.success(f"Added {company_name}!")
                    st.rerun()
                elif r.status_code == 409:
                    st.warning("This URL is already being monitored.")
                else:
                    st.error(f"Failed to add source: {r.json().get('detail', '')}")

            except requests.RequestException as e:
                st.error(f"Connection error: {e}")


# ─── Existing Sources ────────────────────────────────────────────────────────

st.divider()
st.subheader("Your Sources")

try:
    r = requests.get(f"{base}/api/sources", headers=headers, timeout=10)

    if r.status_code != 200:
        st.error("Failed to load sources.")
        st.stop()

    sources = r.json()

    if not sources:
        st.info(
            "No sources added yet. Add company career page URLs above to "
            "start monitoring for job openings."
        )
        st.stop()

    for source in sources:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])

            with col1:
                status_icon = "Active" if source["is_active"] else "Paused"
                st.write(f"**{source['company_name']}** ({status_icon})")
                st.caption(source["career_url"])

            with col2:
                last_scraped = source.get("last_scraped_at")
                if last_scraped:
                    st.caption(f"Last scraped: {last_scraped[:16].replace('T', ' ')}")
                else:
                    st.caption("Never scraped")

            with col3:
                # Toggle active/inactive
                is_active = source["is_active"]
                btn_label = "Pause" if is_active else "Resume"
                if st.button(btn_label, key=f"toggle_{source['id']}"):
                    try:
                        requests.patch(
                            f"{base}/api/sources/{source['id']}",
                            headers=headers,
                            json={"is_active": not is_active},
                            timeout=10,
                        )
                        st.rerun()
                    except requests.RequestException:
                        st.error("Failed to update source.")

            with col4:
                if st.button("Delete", key=f"del_{source['id']}", type="secondary"):
                    try:
                        requests.delete(
                            f"{base}/api/sources/{source['id']}",
                            headers=headers,
                            timeout=10,
                        )
                        st.rerun()
                    except requests.RequestException:
                        st.error("Failed to delete source.")

            st.divider()

except requests.RequestException:
    st.error("Could not connect to the API. Check that the backend is running.")


# ─── Trigger Manual Scrape ───────────────────────────────────────────────────

st.subheader("Manual Scrape")
st.caption("Trigger an immediate scrape of all active sources.")

if st.button("Scrape Now", type="primary"):
    with st.spinner("Triggering scrape... This runs in the background."):
        try:
            r = requests.post(
                f"{base}/api/scraping/trigger",
                headers=headers,
                timeout=15,
            )
            if r.status_code == 202:
                st.success(
                    "Scrape triggered successfully! "
                    "Check the Matches page in a few minutes for new results."
                )
            else:
                st.error(f"Failed to trigger scrape: {r.json().get('detail', '')}")
        except requests.RequestException as e:
            st.error(f"Connection error: {e}")
