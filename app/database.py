"""Supabase client initialization.

Provides two clients:
- `get_supabase_client()`: Uses the anon key. Suitable for user-scoped
  operations where a JWT is passed for RLS enforcement.
- `get_service_client()`: Uses the service_role key. Bypasses RLS.
  Used only for background/automated jobs (GitHub Actions scraper).
"""

from functools import lru_cache

from supabase import create_client, Client

from app.config import get_settings


import contextvars

# Context variable to store the request-scoped client authenticated with the user's JWT
_supabase_client_var = contextvars.ContextVar("supabase_client")


def get_supabase_client() -> Client:
    """Return the request-scoped Supabase client, falling back to a default client if unset."""
    try:
        return _supabase_client_var.get()
    except LookupError:
        settings = get_settings()
        return create_client(settings.supabase_url, settings.supabase_key)


@lru_cache()
def get_service_client() -> Client:
    """Return a Supabase client using the service_role key (bypasses RLS)."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
