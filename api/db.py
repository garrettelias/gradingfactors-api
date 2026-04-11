import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_url: str = os.environ.get("SUPABASE_URL", "")
_key: str = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not _url or not _key:
    raise RuntimeError(
        "Missing required environment variables: SUPABASE_URL and SUPABASE_SERVICE_KEY "
        "must both be set. Copy .env.example to .env and fill in your Supabase credentials."
    )

supabase: Client = create_client(_url, _key)
