import logging
from typing import Any, Dict, List, Optional, cast

import streamlit as st
from supabase import Client, ClientOptions, create_client

# --- CLIENT FACTORIES (CONNECTION RESILIENT) ---


@st.cache_resource
def get_supabase_client() -> Client:
    """
    Initializes the primary Supabase client.
    Uses cached resource with a strict 15s timeout to mitigate cloud connection drops.
    """
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    # Timeout limits prevent hanging the Streamlit container during brief network hiccups
    opts = ClientOptions(postgrest_client_timeout=15)
    return create_client(url, key, options=opts)


def get_supabase() -> Client:
    """
    JIT-retrieval for the primary Supabase client.
    Ensures that runtime operations do not rely blindly on a stale global instance.
    """
    try:
        return get_supabase_client()
    except Exception as e:
        st.error("Database connection dropped. Retrying...")
        logging.error(f"Connection retry log: {e}")
        st.cache_resource.clear()  # Forces a complete handshake renewal on hard drop failures
        return get_supabase_client()


def get_supabase_admin_client() -> Client:
    """
    Initializes the administrative client bypassing RLS via service_role_key.
    Falls back to user-client gracefully if context demands it.
    """
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", st.secrets["SUPABASE_KEY"])
        opts = ClientOptions(postgrest_client_timeout=15)
        return create_client(url, key, options=opts)
    except Exception as e:
        logging.error(f"Admin client allocation fallback triggered: {e}")
        return get_supabase()


# Module-level definitions retain backwards compatibility for static legacy imports
supabase = get_supabase()
supabase_admin = get_supabase_admin_client()


# --- JIT EQUIPMENT RESOLVER ---


@st.cache_data(ttl=86400)
def get_equipment_name_swe(equ_id: Optional[int]) -> str:
    """
    Fetches and caches an equipment's Swedish name to prevent redundant database hits.
    Exposed for UI architecture and view filtering components.
    """
    if not equ_id:
        return ""
    try:
        client = get_supabase()
        res = (
            client.table("equipment")
            .select("equ_name_swe")
            .eq("equ_id", equ_id)
            .maybe_single()
            .execute()
        )

        # Confirm dictionary type context explicitly for Pylance validation compliance
        if res and res.data and isinstance(res.data, dict):
            data_dict = cast(Dict[str, Any], res.data)
            return str(data_dict.get("equ_name_swe", ""))
    except Exception as e:
        logging.error(f"Error fetching equipment localized name metadata: {e}")
    return ""


# --- DATA FETCHING LAYER ---


@st.cache_data(ttl=3600)
def get_static_data(table_name: str):
    """Retrieves static table data with table-specific sorting and graceful error fallbacks."""
    try:
        # Resolve client dynamically to defend against dead sockets during long idle states
        client = get_supabase()
        query = client.table(table_name).select("*")

        if table_name == "exercises":
            return query.order("exe_id").execute()

        if table_name == "locations":
            lang = st.session_state.get("use_lang", "sv")
            suffix = "swe" if lang == "sv" else "en"
            return query.order(f"loc_name_{suffix}").execute()

        return query.execute()
    except Exception as e:
        st.warning(f"Failed to fetch static data for {table_name}. Retrying session...")
        logging.error(
            f"Static retrieval exception tracing data for table '{table_name}': {e}"
        )
        return None


@st.cache_data(ttl=86400)
def fetch_all_locations(lang: str) -> List[Dict[str, Any]]:
    """Retrieves all physical training locations sorted by active user interface localization parameters."""
    try:
        client = get_supabase()
        suffix = "swe" if lang == "sv" else "en"
        order_col = f"loc_name_{suffix}"

        res = client.table("locations").select("*").order(order_col).execute()

        return cast(List[Dict[str, Any]], res.data) if res and res.data else []
    except Exception as e:
        logging.error(f"Error fetching aggregated location lists: {e}")
        return []


# --- COMPLIANCE & GDPR LAYERS ---


def get_user_gdpr_data(user_id_or_uuid) -> dict:
    """
    Gathers compiled personal profiles and history rows for structural GDPR compliance exports.
    Returns structured operational error codes to the interface layer for clean handling.
    """
    try:
        if not user_id_or_uuid:
            return {
                "profile": {},
                "history": [],
                "logs": [],
                "error": "user_id_or_uuid missing completely from execution payload.",
            }

        client = get_supabase()

        # 1. Evaluate identification parameter type dynamically (UUID or sequential internal ID)
        is_uuid = False
        if isinstance(user_id_or_uuid, str):
            if "-" in user_id_or_uuid or not user_id_or_uuid.isdigit():
                is_uuid = True

        # 2. Build the primary base evaluation query
        query = client.table("users").select(
            "use_id, use_uuid, use_display_name, use_rol_id"
        )

        if is_uuid:
            user_res = (
                query.eq("use_uuid", str(user_id_or_uuid)).maybe_single().execute()
            )
        else:
            user_res = query.eq("use_id", int(user_id_or_uuid)).maybe_single().execute()

        user_data = {}
        if user_res is not None and user_res.data:
            user_data = cast(Dict[str, Any], user_res.data)

        if not user_data:
            return {
                "profile": {},
                "history": [],
                "logs": [],
                "error": f"No active user match located for parameter: '{user_id_or_uuid}'",
            }

        actual_user_id = int(user_data["use_id"])

        # 3. Retrieve historical attendance details (RSVP / Session Architecture)
        history_res = (
            client.table("session_participants")
            .select(
                "sep_id, sep_session_id, sep_status, sep_is_leader, workout_sessions(ses_timestamp, locations(loc_name_swe))"
            )
            .eq("sep_user_id", actual_user_id)
            .execute()
        )
        history_data = (
            cast(List[Dict[str, Any]], history_res.data)
            if (history_res is not None and history_res.data)
            else []
        )

        # 4. Extract Access Logs (Crucial for compliance transparency verification maps)
        admin_client = get_supabase_admin_client()
        logs_res = (
            admin_client.table("audit_log")
            .select("al_id, al_timestamp, al_crud_type, al_target_table, al_target_id")
            .eq("al_actor_user_id", actual_user_id)
            .order("al_timestamp", desc=True)
            .execute()
        )
        logs_data = (
            cast(List[Dict[str, Any]], logs_res.data)
            if (logs_res is not None and logs_res.data)
            else []
        )

        return {
            "profile": user_data,
            "history": history_data,
            "logs": logs_data,
            "error": None,
        }
    except Exception as e:
        return {
            "profile": {},
            "history": [],
            "logs": [],
            "error": f"Database transactional exception caught: {str(e)}",
        }


def get_recent_access_logs(limit: int = 30):
    """
    Retrieves the latest entries from the audit_log table without heavy payloads,
    utilizing an explicit join with audit_log_type (v4.5).

    This function is centralized to keep database logic separated from the UI views.
    It uses a Just-In-Time (JIT) admin client to guarantee read permissions (RLS)
    and prevent stale sockets.
    """
    try:
        # Utilize the JIT admin factory instead of the module-level variable proxy.
        # Secures execution against stale sockets while satisfying RLS context criteria.
        client = get_supabase_admin_client()

        return (
            client.table("audit_log")
            .select(
                "al_id, al_timestamp, al_crud_type, al_target_table, al_target_id, al_actor_user_id, al_new_payload, al_action_type_id, audit_log_type!al_action_type_id(alt_code, alt_description)"
            )
            .order("al_timestamp", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        logging.error(f"Exception encountered during access_logs extraction: {e}")
        return None
