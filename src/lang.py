"""
Language module for Coach Engine v4.5.
Fully backward-compatible orchestrator for split UI translations.
"""

import streamlit as st

from src.lang_eng import TEXTS as ENG_TEXTS
from src.lang_swe import TEXTS as SWE_TEXTS

# Central dictionary mapping for available interface locales
LANGUAGES = {"sv": SWE_TEXTS, "en": ENG_TEXTS}


def t(key: str, lang: str | None = None) -> str:
    """
    Retrieves a localized string from translation dictionaries. 100% backward-compatible.

    1. If 'lang' is explicitly passed as a string argument, it takes precedence.
    2. Otherwise, checks st.session_state for the active 'use_lang' attribute.
    3. Falls back to Swedish ('sv') if no active configuration parameters match.
    """
    # 1. Prioritize explicitly provided language parameters, stripping accidental type shifts
    if lang and isinstance(lang, str):
        current_lang = lang.strip().lower()
    else:
        # 2. Extract active locale setting from the current runtime session state context
        current_lang = str(st.session_state.get("use_lang", "sv")).strip().lower()

    # Retrieve the correct localization map, defaulting to Swedish if the code is invalid or missing
    lang_dict = LANGUAGES.get(current_lang, SWE_TEXTS)

    # Return the mapped translation value, or output the key text directly as a layout placeholder fallback
    return lang_dict.get(key, f"[{key}]")
