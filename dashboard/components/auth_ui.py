"""Authentication UI component for Streamlit.

Provides login and registration forms that authenticate against
the Supabase Auth backend via the FastAPI API.
"""

import streamlit as st
from supabase import create_client


def render_auth_page():
    """Render the login/register page."""

    st.title("Welcome")
    st.write("Sign in to start matching your resume with job openings.")

    # Supabase direct auth (no need to go through FastAPI for login)
    supabase_url = st.secrets.get("SUPABASE_URL", "")
    supabase_key = st.secrets.get("SUPABASE_KEY", "")

    is_placeholder = (
        not supabase_url 
        or not supabase_key
        or "your-project" in supabase_url
        or "your-anon-public-key" in supabase_key
    )

    if is_placeholder:
        st.warning(
            "Supabase credentials not configured. "
            "Please add your actual SUPABASE_URL and SUPABASE_KEY to your Streamlit secrets "
            "file (.streamlit/secrets.toml) and your backend configuration (.env)."
        )
        _render_manual_token_input()
        return

    tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

    with tab_login:
        _render_login_form(supabase_url, supabase_key)

    with tab_register:
        _render_register_form(supabase_url, supabase_key)


def _render_login_form(supabase_url: str, supabase_key: str):
    """Render the login form."""
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
                return

            try:
                client = create_client(supabase_url, supabase_key)
                response = client.auth.sign_in_with_password({
                    "email": email,
                    "password": password,
                })

                st.session_state.auth_token = response.session.access_token
                st.session_state.user_email = response.user.email
                st.success("Logged in successfully!")
                st.rerun()

            except Exception as e:
                error_msg = str(e)
                if "Invalid login" in error_msg or "invalid" in error_msg.lower():
                    st.error("Invalid email or password.")
                else:
                    st.error(f"Login failed: {error_msg}")


def _render_register_form(supabase_url: str, supabase_key: str):
    """Render the registration form."""
    with st.form("register_form"):
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_password")
        confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")
        full_name = st.text_input("Full Name (optional)", key="reg_name")
        submitted = st.form_submit_button("Create Account", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
                return

            if password != confirm:
                st.error("Passwords do not match.")
                return

            if len(password) < 6:
                st.error("Password must be at least 6 characters.")
                return

            try:
                client = create_client(supabase_url, supabase_key)
                response = client.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {"full_name": full_name},
                    },
                })

                if response.user:
                    st.success(
                        "Account created! Check your email for a confirmation link, "
                        "then sign in."
                    )
                else:
                    st.error("Registration failed. Please try again.")

            except Exception as e:
                st.error(f"Registration failed: {e}")


def _render_manual_token_input():
    """Fallback: manual JWT token input for development."""
    st.divider()
    st.subheader("Developer Login")
    st.caption("Paste a valid Supabase JWT token to authenticate.")

    with st.form("token_form"):
        token = st.text_input("JWT Token", type="password")
        email = st.text_input("Email (for display)")
        submitted = st.form_submit_button("Authenticate", use_container_width=True)

        if submitted and token:
            st.session_state.auth_token = token
            st.session_state.user_email = email or "developer"
            st.rerun()
