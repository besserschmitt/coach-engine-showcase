import logging
import os

import streamlit as st

from src.lang import t


@st.cache_data(show_spinner=False)
def _load_cached_css(css_path: str) -> str:
    """Reads and caches the CSS string in RAM to eliminate downstream layout flickering."""
    with open(css_path, "r", encoding="utf-8") as f:
        return f.read()


def apply_styles():
    """
    Injects the global branding and interface styling into Coach Engine.
    Performance-optimized via RAM cache to guarantee rapid rendering sequences.
    """
    css_path = os.path.join("assets", "style.css")
    lang = st.session_state.get("use_lang", "sv")

    if os.path.exists(css_path):
        try:
            # Fetched instantly from memory cache after the initial read pass
            css_content = _load_cached_css(css_path)

            # Securely inject styles into the active top-level view container
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
        except (IOError, OSError) as file_err:
            # Clean logging to the server console buffer without corrupting user interface views
            logging.error(
                f"File system error encountered while reading style assets: {file_err}"
            )
            st.error(t("err_css_load_failed", lang))
        except Exception as e:
            logging.error(
                f"Unexpected operational error during branding injection sequence: {e}"
            )
            st.error(t("err_css_load_failed", lang))
    else:
        # Log a warning to the server backend console while degrading gracefully to the standard theme
        logging.error(
            "Asset warning: assets/style.css missing from directory tree — falling back to base application theme."
        )
