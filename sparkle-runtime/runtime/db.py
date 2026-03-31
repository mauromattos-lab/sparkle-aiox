from supabase import create_client, Client
from runtime.config import settings


def get_supabase() -> Client:
    """Returns a Supabase client using the service key (bypasses RLS)."""
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
    return create_client(settings.supabase_url, settings.supabase_key)


# Module-level singleton — reused across requests
supabase: Client = get_supabase()
