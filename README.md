# Coach Engine v4.7 — Parametric Group Fitness Architecture

A highly resilient, context-aware group fitness programming platform built to optimize outdoor athletic training sessions in real time. Coach Engine transitions group training from fragile, static spreadsheets into an automated, biomechanically safe routing engine.

Built entirely on a **100% open-source, zero-cost operational stack** utilizing Streamlit Cloud, Python 3.14, and Supabase (PostgreSQL).

---

## 🏗️ System Architecture & Data Flow

The platform utilizes a strictly decoupled 3-tier architecture designed to run seamlessly on mobile networks in unstable outdoor fält (field) environments.
```
[ GitHub Repository ] 
         │
         ▼ (Continuous Deployment Webhook)
[ Streamlit Cloud Runtime ] ◄───────► [ Browser Cookie Gate ]
         │                             (30-Day Session Tokens)
         ▼ (Encrypted SSL Channel)
[ Supabase PostgreSQL DB ] ◄────────► [ Immutable PL/pgSQL Triggers ]
         │                             (Payload Differential Audit Logs)
         ▼
[ Open-Meteo REST API ] ────────────► Live Biomechanical Mutation Loops
```
### Key Components
* **Presentation Layer:** Streamlit runtime optimized with custom CSS for responsive mobile-first grid rendering out in the park.
* **Core Parametric Engine:** A pure Python functional execution pipeline isolated from presentation states.
* **Data & Rule Ledger:** Supabase (PostgreSQL) enforcing relational integrity, Row-Level Security (RLS), and automated immutable state logs.

---

## 🧠 Core Generation Pipeline (The Trestegsraket)

Workout generation avoids naive randomization by routing configuration inputs through an explicit three-stage pipeline inside `src/engine/`:

1. **Rules Layer (`rules.py`):** Establishes baseline limits (e.g., `MAX_EQUIPMENT_TYPES_PER_STATION = 1`), target durations, and structural constraints based on the chosen progression mode (`ses_arch_level` ranging from Level 1 Monostructural to Level 3 "The Gauntlet").
2. **Selector Layer (`selector.py`):** Filters the exercise bank dynamically against environmental metadata arrays.
3. **Architect Layer (`architect.py`):** Combines and balances active exercise triplets/stations, distributes limited equipment to prevent bottlenecks among training groups, and outputs a single synchronized `JSONB` structural payload.

---

## 🌦️ Environmental IQ (Meteorological Adjustments)

The selector module handles live telemetry integration via GPS coordination maps. Real-time WMO weather status codes and wind velocities mutate the workout biomechanics before execution:

* **Rain-Safe Trigger (`wea_trigger_rain_safe`):** Heavy rain codes auto-exclude ground exercises requiring participants to lie down on wet grass, dynamically forcing standing movements or re-routing setups to covered park geography.
* **Wind Safety Cap (`EXTREME_WIND_THRESHOLD = 10.0` m/s):** High winds block lightweight accessories (resistance bands, cones, sheets) that risk blowing away, forcing the use of permanent concrete park structures via structural `ELEVATION_IDS` (e.g., stone walls, steps).
* **Tactical Terrain Priority:** If location infrastructure flags detect a hill asset, the engine automatically swaps out static high-knees for dynamic hill sprints.

---

## 🛠️ Engineering Highlights & Patterns

### 1. Thread-Isolated Observability (`src/logger.py`)
To prevent network logging from degrading mobile UI frame rates, the logging engine offloads actions to background processes via `threading.Thread`. To fix Streamlit’s native Thread-Local Storage isolation (where proxy headers disconnect on new worker threads), the core primary thread harvests client metadata *before* spawning background processes:

```python
def log_event_async(event_type_id, user_id, details):
    # Harvest proxy forwarding tokens on the primary user context thread
    headers = st.context.headers
    client_ip = headers.get("X-Forwarded-For", "0.0.0.0")
    
    # Spin up isolated worker thread with clear context boundaries
    t = threading.Thread(target=log_event_sync, args=(event_type_id, user_id, details, client_ip))
    t.start()
```

2. Immutable PostgreSQL Audit Ledgers (access_logs)
Critical data modifications are protected directly at the database engine schema level using PL/pgSQL database triggers. Even if application layers are completely bypassed, any row mutation automatically extracts the actor's Supabase JWT identity map and computes old vs new states into immutable JSONB diff payloads:

```
CREATE OR REPLACE FUNCTION log_adaptation_changes() RETURNS TRIGGER AS $$
BEGIN
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    INSERT INTO public.audit_log (al_crud_type, al_target_table, al_old_payload, al_new_payload, al_actor_user_id) 
    VALUES ('UPDATE', 'adaptations', to_jsonb(OLD), to_jsonb(NEW), COALESCE(v_actor_id, 0));
    RETURN NEW;
END; $$ LANGUAGE plpgsql SECURITY DEFINER;
```


3. Language Decoupling and Standardization (src/lang.py)
Hardcoded display text is completely eliminated from template render files. UI templates pull display states via defensive lookups: t("string_key", lang). If localization dictionaries are missing assets, the pipeline gracefully degrades to Swedish (sv) to guarantee seamless execution.

All exercise adaptations for scaled groups are cleanly normalized to the uniform architectural term: "förenklad övning".

📁 Repository Structure

```
coachEngine/
├── app.py                     # Root Orchestrator: Authorization Gates & Cookie States
├── scripts/
│   └── cleanup_review.py      # Automated Ruff-validated Code Quality Scanning Utility
├── src/                       # System Core Core Pipelines
│   ├── database.py            # Just-In-Time Client Factories (Prevents stale socket drops)
│   ├── lang.py                # i18n Lookup Matrix Framework
│   ├── logger.py              # Non-blocking Multi-Threaded Logging Hub
│   └── engine/                # Core Parametric Programming Matrix
│       ├── rules.py           # Safety Thresholds & Environmental Constants
│       ├── selector.py        # Biomechanical Exercise Filtration Loops
│       └── architect.py       # Station Matching & Structural JSONB Compiler
└── views/                     # Isolated Render Components (login, home, coach, admin)
```


📈 Architectural Decisions Log (ADR)
Why Supabase/PostgreSQL over SQLite for Production? SQLite was ideal for the 30-hour local prototyping phase on the MacBook M1. However, multi-coach coordination and live user RSVPs required a centralized engine with row locking, strict foreign keys, and Row-Level Security.

Why JSONB Documents for Session Storage? Workouts have dynamic layout counts and structures. Normalizing this into strict multi-table joins introduced performance hits over weak cellular signals. Storing layouts inside indexed JSONB blobs provides maximum structural flexibility with fast retrieval.

Why No Accidental Architecture? The system relies heavily on automated formatting guards, strong typing coercion (_safe_int), and defensive validation wrappers. This ensures that runtime UI states can never force an error loop or crash the platform in the field.
