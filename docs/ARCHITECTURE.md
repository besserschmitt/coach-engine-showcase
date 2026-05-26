# Coach Engine Architecture (v4.0)

Coach Engine is a modular, event-driven Streamlit application designed for high-concurrency group fitness management, utilizing a Supabase backend.

## 1. Core Principles
- **State Isolation:** Components are scoped to session IDs to prevent leakage.
- **i18n:** Centralized translation via `src/lang.py`.
- **Performance:** Tiered caching separates static lookups (exercises) from operational data.
- **Data Governance:** Audit logging enabled for all CRUD operations via `access_logs`.

## 2. Directory Structure

### `app.py` (Entry Point)
Orchestrates authentication (CookieController), session state, and root-level navigation.

### `src/` (Engine & Logic)
- **`database.py`**: Supabase client configuration and global DB helpers.
- **`engine/`**: Core business logic.
    - `rules.py`: Environmental constants and weather mapping.
    - `architect.py`: Workout generation (EMOM, Tabata, Triplets).
    - `selector.py`: Filters exercises based on constraints.
    - `formatter.py`: JSON packaging of session data.
- **`lang.py`**: Single source of truth for UI strings.
- **`logger.py`**: Asynchronous/Synchronous logging of system events (`audit_log`).
- **`utils.py`**: Shared helpers (time, weather sync).

### `views/` (UI Layer)
- **`login.py`**: Authentication landing page.
- **`home.py`**: Member dashboard.
- **`coach.py`**: Instructor dashboard (Architect, Gear, Bank).
- **`admin.py`**: System admin tools.

## 3. Data Flow
1. **User Request:** Component render triggers logic based on session key.
2. **Context Sync:** `sync_session_weather` attaches environmental state.
3. **Engine Processing:** `architect.py` and `selector.py` build the workout.
4. **Persistence:** JSON blob stored in `workout_sessions` table.
5. **Governance:** Audit logs capture the transaction metadata.