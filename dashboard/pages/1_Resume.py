"""Resume upload and management page."""

import streamlit as st
import requests


st.set_page_config(page_title="Resume - AI Job Matcher", page_icon="briefcase", layout="wide")

st.title("Resume")
st.caption("Upload your resume to start matching with job openings.")

# ─── Auth Check ──────────────────────────────────────────────────────────────

if not st.session_state.get("auth_token"):
    st.warning("Please log in from the main page first.")
    st.stop()

headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
base = st.session_state.get("api_base_url", "http://localhost:8000")


# ─── Current Resume ──────────────────────────────────────────────────────────

st.subheader("Current Resume")

try:
    r = requests.get(f"{base}/api/resumes/current", headers=headers, timeout=10)

    if r.status_code == 200 and r.json():
        resume = r.json()

        col1, col2 = st.columns([2, 1])

        with col1:
            st.write(f"**File:** {resume.get('filename', 'Unknown')}")
            st.write(f"**Experience:** {resume.get('experience_years', 0)} years")
            st.write(f"**Summary:** {resume.get('summary', 'N/A')}")

            # Skills tags
            skills = resume.get("skills", [])
            if skills:
                st.write("**Skills:**")
                skills_html = " ".join(
                    f'<span style="background:#1a237e;color:#90caf9;padding:4px 10px;'
                    f'border-radius:12px;margin:2px;display:inline-block;font-size:13px;">'
                    f'{skill}</span>'
                    for skill in skills
                )
                st.markdown(skills_html, unsafe_allow_html=True)

            # Job titles
            titles = resume.get("job_titles", [])
            if titles:
                st.write("**Previous Titles:**")
                for i, title in enumerate(titles):
                    st.write(f"  {i + 1}. {title}")

        with col2:
            # Education
            education = resume.get("education", [])
            if education:
                st.write("**Education:**")
                for edu in education:
                    if isinstance(edu, dict):
                        degree = edu.get("degree", "")
                        institution = edu.get("institution", "")
                        year = edu.get("year", "")
                        st.write(f"- {degree}")
                        if institution:
                            st.caption(f"  {institution} {f'({year})' if year else ''}")

            # Delete button
            st.divider()
            if st.button("Delete Resume", type="secondary"):
                dr = requests.delete(
                    f"{base}/api/resumes/{resume['id']}",
                    headers=headers,
                    timeout=10,
                )
                if dr.status_code == 204:
                    st.success("Resume deleted.")
                    st.rerun()
                else:
                    st.error("Failed to delete resume.")

    else:
        st.info("No resume uploaded yet. Upload one below to get started.")

except requests.RequestException:
    st.error("Could not connect to the API. Check that the backend is running.")


# ─── Upload New Resume ───────────────────────────────────────────────────────

st.divider()
st.subheader("Upload Resume")

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"],
    help="Upload your resume as a PDF. Max 10MB.",
)

if uploaded_file is not None:
    st.write(f"Selected: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

    if st.button("Parse and Upload", type="primary", use_container_width=True):
        with st.spinner("Parsing resume with AI... This may take 15-30 seconds."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                r = requests.post(
                    f"{base}/api/resumes/upload",
                    headers=headers,
                    files=files,
                    timeout=60,
                )

                if r.status_code == 201:
                    st.success("Resume parsed and uploaded successfully!")
                    st.rerun()
                elif r.status_code == 422:
                    st.error(f"Parsing error: {r.json().get('detail', 'Unknown error')}")
                else:
                    st.error(f"Upload failed (HTTP {r.status_code}): {r.json().get('detail', '')}")

            except requests.Timeout:
                st.error("Request timed out. The resume may be very large. Please try again.")
            except requests.RequestException as e:
                st.error(f"Connection error: {e}")
