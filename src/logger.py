import logging
import threading
from typing import Any, Dict, Optional

import streamlit as st


def log_event_sync(
    event_type_id: int,
    user_id: int,
    details: str = "",
    target_table: Optional[str] = None,
    extra_payload: Optional[Dict[str, Any]] = None,
    client_ip: str = "Unknown IP",
    user_agent: str = "Unknown Browser",
):
    """
    Synchronous logging execution block for recording critical audit trails.
    Utilizes localized JIT admin client invocation to prevent connection timeouts.
    """
    try:
        # [RESILIENCE FIX]: Lazy import the JIT client factory to isolate connection state
        # and prevent circular dependency locks during runtime hot-reloads.
        from src.database import get_supabase_admin_client

        payload_content = {
            "message": details,
            "client_ip": client_ip,
            "user_agent": user_agent,
        }

        if extra_payload:
            payload_content.update(extra_payload)

        log_payload = {
            "al_action_type_id": event_type_id,
            "al_actor_user_id": user_id,
            "al_new_payload": payload_content,
            "al_crud_type": "OTHER",
        }

        if target_table:
            log_payload["al_target_table"] = target_table

        # Resolve fresh client on this active thread context to bypass stale socket traps
        admin_client = get_supabase_admin_client()
        admin_client.table("audit_log").insert(log_payload).execute()
    except Exception as e:
        logging.error(f"Synchronous logging execution failed: {e}")


def log_event(
    event_type_id: int,
    user_id: int,
    details: str = "",
    target_table: Optional[str] = None,
    extra_payload: Optional[Dict[str, Any]] = None,
):
    """
    Asynchronous logger gate for non-blocking event recording.
    Harvests Streamlit session headers safely on the active UI thread before spawning workers.
    """
    client_ip = "Unknown IP"
    user_agent = "Unknown Browser"

    # [THREAD-SAFETY FIX]: Harvest request metadata on the primary user thread.
    # Spawning a background thread strips Streamlit's Thread-Local Storage context access.
    try:
        headers = st.context.headers
        if headers:
            if "X-Forwarded-For" in headers:
                client_ip = (
                    str(headers.get("X-Forwarded-For", "Unknown IP"))
                    .split(",")[0]
                    .strip()
                )
            elif "Host" in headers:
                client_ip = "127.0.0.1"  # Local host execution assumption

            user_agent = headers.get("User-Agent", "Unknown Browser")
    except Exception:
        # Graceful degradation if called from a disconnected context layout layer
        pass

    # Spin up background worker passing the pre-computed string parameters cleanly
    thread = threading.Thread(
        target=log_event_sync,
        args=(
            event_type_id,
            user_id,
            details,
            target_table,
            extra_payload,
            client_ip,
            user_agent,
        ),
    )
    thread.start()
