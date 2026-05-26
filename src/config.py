import os

import streamlit as st

# ====================================================================
# 🎯 CENTRAL CONFIGURATION FILE — SECURED FOR MOCK & CLOUD
# ====================================================================

VERSION = "4.7"
ARCHITECTURE_STRATEGY = "cherry picker architect"

# Cache the environmental evaluation flag globally to minimize filesystem I/O operations
IS_DEMO = True

# 1. First, check if running live in the cloud environment via Streamlit Secrets
try:
    # Explicit identity comparison to satisfy strict linter guidelines
    if st.secrets.get("IS_PROD") is True:
        IS_DEMO = False
    else:
        IS_DEMO = True
except Exception:
    # 2. Fallback: If st.secrets is unavailable (local development context)
    # Cache the lowercased workspace string directly to maximize execution speed
    current_workspace = os.path.basename(os.getcwd()).lower()
    if "coach-engine-prod" in current_workspace:
        IS_DEMO = False
    else:
        IS_DEMO = True

# 🏷️ DYNAMIC UI STRINGS
PAGE_TITLE = f"Coach Engine {VERSION} DEMO" if IS_DEMO else f"Coach Engine {VERSION}"
APP_TITLE = f"Coach Engine {VERSION} DEMO" if IS_DEMO else f"Coach Engine {VERSION}"
