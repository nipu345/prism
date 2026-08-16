"""Shared Supabase client.

Split out of main.py so routers can `from db import supabase` directly
instead of `from main import supabase`, which previously created a
fragile circular import (main.py imported the routers, which imported
main.py back) that only worked because of import ordering.
"""

from supabase import create_client, Client
import config

supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
