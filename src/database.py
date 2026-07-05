import logging
from typing import Any, Dict, List, Optional, cast

import streamlit as st
from supabase import Client, ClientOptions, create_client

# --- CLIENT FACTORIES (RLS & TOKEN COMPLIANT) ---


def get_supabase_client() -> Client:
    """
    Initializes a user-bound Supabase client using the ANONYMOUS public key.
    If a valid user session is active, it injects the JWT token to enforce RLS boundaries.
    """
    url = st.secrets["SUPABASE_URL"]
    anon_key = st.secrets.get("SUPABASE_ANON_KEY", st.secrets.get("SUPABASE_KEY"))

    opts = ClientOptions(postgrest_client_timeout=15)
    client = create_client(url, anon_key, options=opts)

    # If a specific user session was stored during login, bind it to the client
    if "supabase_session" in st.session_state and st.session_state.supabase_session:
        access_token = st.session_state.supabase_session.access_token
        client.postgrest.auth(access_token)

    return client


def get_supabase() -> Client:
    """
    JIT-retrieval for the user-specific, RLS-enforced Supabase client.
    Defends against dead sockets and dynamically handles authorization contexts.
    """
    try:
        return get_supabase_client()
    except Exception as e:
        st.error("Database connection dropped. Retrying...")
        logging.error(f"Connection retry log: {e}")
        return get_supabase_client()


@st.cache_resource(
    ttl=3600
)  # Cache the administrative client since the static key does not change
def get_supabase_admin_client() -> Client:
    """
    Initializes the administrative client bypassing RLS via the private SUPABASE_KEY.
    Retains administrative powers for system tables like audit_log and GDPR routines.
    """
    try:
        url = st.secrets["SUPABASE_URL"]
        # Mapped directly to SUPABASE_KEY as established in secrets.toml configuration
        key = st.secrets["SUPABASE_KEY"]
        opts = ClientOptions(postgrest_client_timeout=15)
        return create_client(url, key, options=opts)
    except Exception as e:
        logging.error(f"Admin client allocation failure: {e}")
        return get_supabase()


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

        is_uuid = False
        if isinstance(user_id_or_uuid, str):
            if "-" in user_id_or_uuid or not user_id_or_uuid.isdigit():
                is_uuid = True

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
    """
    try:
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
