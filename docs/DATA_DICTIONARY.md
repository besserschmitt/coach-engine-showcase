# 📖 Coach Engine 4.5 — Production Data Dictionary

This data dictionary outlines the comprehensive, column-by-column reference schema for all tables residing in the public schema of the **Coach Engine 4.5** database.

---

## 1. Table: `audit_log` (System Name: `access_logs`)
The system's absolute central modifications and security ledger. It records explicit transactional states before and after mutations occur, along with JIT web-server network metadata headers.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `al_id` | `bigint` | NO | **PK** | `nextval()` | Serial row timeline tracking identifier. Unique sequential auto-increment key. |
| `al_timestamp` | `timestamp with time zone` | NO | | `now()` | Exact system instance execution entry time captured globally in UTC. |
| `al_action_type_id`| `smallint` | NO | **FK** | | Structural classification mapping pointing directly to lookup entry `audit_log_type.alt_id`. |
| `al_crud_type` | `character varying` | YES | | | The processing transaction category class applied (`INSERT`, `UPDATE`, `DELETE`, `OTHER`). |
| `al_target_table` | `character varying` | YES | | | Plaintext physical database target table designation tag indicating where the change processed. |
| `al_target_id` | `text` | YES | | | The precise relational record row identity affected by the execution pipeline. |
| `al_old_payload` | `jsonb` | YES | | | Complete data state snapshot mapping absolute record variables *before* changes processed. |
| `al_new_payload` | `jsonb` | YES | | | Final structural data state payload snapshot mapped *after* transactional pipeline execution. **Contains JIT network metadata (`client_ip`, `user_agent`, `message`)**. |
| `al_actor_user_id` | `bigint` | YES | **FK** | | Tracks operator identity back to `users.use_id` showing who fired the mutation event (0 = System/Anon). |

---

## 2. Table: `audit_log_type`
The lookup directory index describing specific action definitions and priority metadata for the system's central `access_logs` trail.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `alt_id` | `smallint` | NO | **PK** | | Primary operational look-up identity index mapped to security priorities (e.g., `2 = USER_LOGIN`, `15 = AUTH_FAILURE`). |
| `alt_code` | `character varying` | NO | | | Unique system alpha transactional designation string shorthand (e.g., `'USER_LOGIN'`, `'AUTH_FAILURE'`). |
| `alt_description` | `text` | YES | | | Complete scope specification text detailing exactly what the type categorization logs. |

---

## 3. Table: `adaptations`
The structural alternative fallback motions mapping to master movements when outdoor parameters, weather rules, or skill scaling demand simplified variations.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ada_id` | `bigint` | NO | **PK** | `nextval()` | Core adaptation entry database reference identifier key. |
| `ada_exe_id` | `bigint` | NO | **FK** | | Foreign key routing directly back to the original movement profile anchor in `exercises.exe_id`. |
| `ada_name` | `text` | NO | | | Technical designation mapping the regression profile variation in English. |
| `ada_name_swe` | `text` | NO | | | Swedish title representation. **Nomenclature rule: Must consistently map to "förenklad övning"**. |
| `ada_is_standing` | `boolean` | YES | | `true` | Ground-contact avoidance switch identifying if the movement sequence bypasses mud constraints. |
| `ada_staircase_req`| `boolean` | YES | | `false` | Explicit architectural flag requiring structural step infrastructure at the session node. |
| `ada_is_rain_safe` | `boolean` | YES | | `true` | Validation flag protecting athletes from tracking slips or structural friction losses during wet events. |

---

## 4. Table: `equipment`
Abstract apparatus metadata classifications enforcing configuration boundaries, environmental logic dependencies, and physical group configurations.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `equ_id` | `bigint` | NO | **PK** | `nextval()` | Core physical equipment abstract category master key. |
| `equ_name` | `text` | NO | | | Universal code categorization name token parameter in English. |
| `equ_name_swe` | `text` | NO | | | Localized apparatus description rendered straight to the application layout interface. |
| `equ_is_fixed` | `boolean` | YES | | `false` | Distinguishes static, structural installations (e.g., park walls/pull-up rigs) from mobile items. Prefer walls over trees for pushups. |
| `loc_id` | `integer` | YES | | `-1` | Binds fixed structural gear arrays straight back to an individual designated geographical park node. |
| `equ_is_rain_safe` | `boolean` | YES | | `true` | Material flag indicating structural resilience or grip safety thresholds during wet routines. |
| `equ_is_wind_safe` | `boolean` | YES | | `true` | Isolation logic variable stripping lightweight tools vulnerable to flying away during heavy gusts (Extreme Wind logic). |
| `equ_is_group` | `boolean` | YES | | `true` | Declares if the item setup accommodates group sharing pools during a concurrent triplet or interval block. |
| `equ_is_stations_only` | `boolean` | YES | | `false` | Core architecture rule locking specific hardware exclusively within circuit/station configuration modules. Enforced at session initialization. |

---

## 5. Table: `equipment_inventory`
The actual item tracking parameters mapping unit distributions, hardware weight matrices, and physical container counts.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `iv_id` | `integer` | NO | **PK** | `nextval()` | Unique inventory tracking serial key instance parameter. |
| `equ_id` | `integer` | YES | **FK** | | Relational pointer mapping row details directly back to abstract `equipment.equ_id`. |
| `iv_spec` | `text` | NO | | | Sizing and sizing specification text configurations (e.g., `'8kg'`, `'12kg'`, `'Large'`). |
| `iv_count` | `integer` | YES | | `0` | Absolute count integer tracking quantities physically residing in the training arsenal. Enforces station constraints. |
| `iv_unit` | `text` | YES | | `'st'` | Tracking units standard variable label (e.g., pieces, units). |
| `iv_is_active` | `boolean` | YES | | `true` | Verifies structural unit status, filtering out damaged hardware from current generation pools. |
| `created_at` | `timestamp with time zone` | YES | | `now()` | Log entry system trace mapping when hardware profile records were established. |

---

## 6. Table: `exercises`
The master movement repository framework storing physical taxonomy mechanics, biomechanical parameters, and environmental selector overrides.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `exe_id` | `bigint` | NO | **PK** | `nextval()` | Core exercise movement identifier master reference key. |
| `exe_name` | `text` | NO | | | Global backend system identification reference code. |
| `exe_name_swe` | `text` | NO | | | Localized movement nomenclature visible to active members inside the UI dashboards. |
| `exe_equ_id` | `integer` | YES | **FK** | | Core dependency tracking link mapping hardware constraints back to `equipment.equ_id`. Max one type per station. |
| `exe_level` | `integer` | YES | | | Workout session taxonomy segment tier level (Level 1: Monostructural, Level 2: Hybrid, Level 3: Gauntlet). |
| `exe_is_combo` | `boolean` | YES | | `false` | Flags compound biomechanical muscle chains (e.g., combining horse stance into shadow boxing). |
| `exe_is_standing` | `boolean` | YES | | `true` | Biomechanical orientation attribute isolating vertical positions to bypass muddy/wet field configurations. |
| `exe_is_rain_safe` | `boolean` | YES | | `true` | Safety override token checking friction or platform slip thresholds under wet conditions. |
| `exe_hill` | `boolean` | YES | | `false` | Geographic requirement logic parameter testing slope/hill reliance criteria. Prioritizes hill intervals over stationary work. |
| `exe_staircase` | `boolean` | YES | | `false` | Geographic requirement logic parameter testing staircase structure requirements. |
| `is_blacklisted` | `boolean` | YES | | `false` | Emergency soft-delete toggle immediately dropping movements from generation visibility. |
| `exe_author` | `integer` | YES | **FK** | | Tracks specific coaching profile record ownership via reference to `users.use_id`. |
| `exe_description` | `text` | YES | | | Complete execution tutorial notes, tactical setup guides, and coaching parameter summaries. |

---

## 7. Table: `locations`
Geographic coordinates, topographical parameters, surface states, and fixed installation metadata available across outdoor training hubs.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `loc_id` | `bigint` | NO | **PK** | `nextval()` | Unique geographical park station reference identifier key. |
| `loc_name` | `text` | NO | | | System backend alphanumeric identification location tag. |
| `loc_name_swe` | `text` | NO | | | Localized geographical address name string rendered inside the UI view layout. |
| `loc_lat` | `real` | YES | | `59.19` | Precision geographic latitude coordinate variable passed to live meteorological API blocks. |
| `loc_lon` | `real` | YES | | `17.75` | Precision geographic longitude coordinate variable passed to live meteorological API blocks. |
| `loc_has_hill` | `boolean` | YES | | `false` | Environment flag confirming native hill terrain availability for interval modules. |
| `loc_has_staircase` | `boolean` | YES | | `false` | Environment flag confirming structural step/stair availability for step modules. |
| `loc_is_sheltered` | `boolean` | YES | | `false` | Identifies covered alternative microclimates resilient during downpour constraints. |
| `loc_has_portable_stash`| `boolean`| YES | | `false` | Confirms lockable storage boxes are locally present at the workout location. |
| `loc_can_bring_gear` | `boolean` | YES | | `true` | Assesses if mobile vehicular deployment can add additional supply bags to the session. |
| `loc_surface_swe` | `text` | YES | | `'Grus/Gräs'`| Surface profile structural analysis mapping string (e.g., grass, concrete, gravel). |
| `loc_notes_swe` | `text` | YES | | | Field notes and descriptions tracking environmental updates or logistical conditions. |

---

## 8. Table: `notifications`
Application system message dashboard tracking alerts, live bulletins, scheduling boundaries, and localized targeting criteria.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `not_id` | `integer` | NO | **PK** | `nextval()` | Core broadcast event target identification master reference key. |
| `not_created_at` | `timestamp with time zone` | YES | | `now()` | Exact transaction entry trace time capturing notice posting events. |
| `not_user_id` | `integer` | YES | **FK** | | Targeted member filter index pointing back to `users.use_id` (NULL = Broadcast to all profiles). |
| `not_message` | `text` | NO | | | Communication alert payload body string displayed directly on the screen layout. |
| `not_valid_from` | `timestamp with time zone` | NO | | | Precise scheduling anchor initializing notice visibility inside client views. |
| `not_valid_to` | `timestamp with time zone` | NO | | | Expiration timestamp criterion executing auto-dismiss routines from dashboard interfaces. |

---

## 9. Table: `roles`
System access tiers managing role clearance loops, dashboard boundaries, and authorization checkpoints.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `rol_id` | `bigint` | NO | **PK** | | Core authorization permission sequence index level identification number (1 = Admin, 2 = Coach, 3 = Member). |
| `rol_name` | `text` | NO | | | Access role categorization label descriptor strings (`Admin`, `Coach`, `Member`). |

---

## 10. Table: `session_participants`
The relational junction database managing attendance vectors, effort grading matrices, tracking states, and performance flags.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `sep_id` | `bigint` | NO | **PK** | `nextval()` | Core registration database sequence identifier row index key. |
| `sep_session_id` | `bigint` | NO | **FK** | | Connecting trace pointing directly to active target event in `workout_sessions.ses_id`. |
| `sep_user_id` | `bigint` | NO | **FK** | | Connecting trace pointing directly to active target athlete profile in `users.use_id`. Maps under 'job tracker' context for specific tasks. |
| `sep_role_id` | `bigint` | YES | | `3` | Specific functional role assigned during the timeframe (e.g., participant, co-instructor). |
| `sep_feedback` | `text` | YES | | | Qualitative notes, workout summaries, or performance reviews collected post-event. |
| `sep_effort_score` | `integer` | YES | | | Rating integer measuring baseline perceived workout intensity from the user. |
| `sep_created_at` | `timestamp with time zone` | YES | | `now()` | Log audit recording entry timestamp tracking when the member logged into the group queue. |
| `sep_is_leader` | `boolean` | YES | | `false` | Explicit high-performance performance indicator tracking top performance rankings. |
| `sep_status` | `integer` | YES | | `1` | Core registration flag state parameters (`1 = Coming`, `2 = Can't attend / Declined`). |

---

## 11. Table: `users`
The centralized identity profile master engine processing preference structures, internationalization variables, encrypted states, and secure cryptographic anchors.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `use_id` | `bigint` | NO | **PK** | `nextval()` | Unique internal master serial index tracking identifier key. |
| `use_name` | `text` | NO | | | Core fallback text string identification parameter username. |
| `use_first_name` | `text` | YES | | | First name attribute explicitly targeted by client text-to-speech engine rules. |
| `use_last_name` | `text` | YES | | | Last name / family surname classification text data. |
| `use_display_name` | `text` | YES | | | Full naming taxonomy strings rendered across community scoreboard leaderboards. |
| `use_email` | `text` | YES | | | Primary communication e-post address and account recovery location trace. |
| `use_mobile_phone` | `text` | YES | | | Cellular telephone contact number details mapping. |
| `use_lang` | `text` | YES | | `'sv'` | Interface local language token setup flag (`'sv'` or `'en'`). Hydrates core i18n blocks. |
| `use_theme` | `text` | YES | | `'dark'` | UI configuration palette toggle choice setting (`dark` or `light` rules). |
| `use_fitness_level`| `integer` | YES | | `2` | Physical capability variable matrix coefficient passed to sizing templates. |
| `use_is_active` | `boolean` | YES | | `true` | System account state checking current subscription status parameters. |
| `use_is_locked` | `boolean` | YES | | `false` | Security throttle indicating lockout bounds from login rate limitations. |
| `use_rol_id` | `bigint` | YES | **FK** | | System security clearance link mapping user groups directly back to `roles.rol_id`. |
| `use_last_login_at`| `timestamp with time zone` | YES | | | Logging timeline trace showing exactly when credentials were last authenticated. |
| `use_created_at` | `timestamp with time zone` | YES | | `now()` | Internal calendar logging system trace tracking account activation date. |
| `use_password` | `text` | YES | | | Secure internal localized encrypted password string parameters. |
| `use_uuid` | `text` | YES | | | Unique external security UUID reference mapping directly to backend identity platforms. **Used alongside SESSION_SALT for secure cookie hashing**. |

---

## 12. Table: `weather_conditions`
Environmental safety boundary matrices mapped to lookup configurations to toggle automated selector constraints.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `wea_id` | `bigint` | NO | **PK** | | Core constraint threshold mapping reference index identifier key. |
| `wea_name_en` | `text` | NO | | | Global conditions classification text label specified in English. |
| `wea_name_swe` | `text` | NO | | | Localized condition description tag specified in Swedish (e.g., Extrem vind, Regn, Halka). Extreme wind forces standing-only blocks. |
| `wea_is_active` | `boolean` | YES | | `true` | Activates or silences checking rules within generation modules. Bypassable via `IS_DEMO` mock engine layer. |
| `wea_trigger_standing`| `boolean`| YES | | `false` | Enforces 100% standing-only templates when activated, skipping mud/ground positions. |
| `wea_trigger_rain_safe`| `boolean`| YES | | `false` | Purges sliding movements or low-friction handling tasks during rainfall events. |
| `wea_trigger_wind_safe`| `boolean`| YES | | `false` | Blocks lightweight loose gear parameters from structural pass selection models. |
| `wea_note_swe` | `text` | YES | | | Localized coaching documentation outlining safety reasoning for weather restrictions. |

---

## 13. Table: `workout_sessions`
Core entity tracking records compiling parameters, metrics blueprints, structured timing setups, and historical logs of scheduled programs.

| Column Name | Data Type | Nullable | Key | Default / Sequence | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ses_id` | `bigint` | NO | **PK** | `nextval()` | Unique workout session entity primary identification database reference key. |
| `ses_timestamp` | `timestamp with time zone` | YES | | `now()` | Set schedule date and launch time parameters mapped locally for event dispatch. |
| `ses_loc_id` | `bigint` | YES | **FK** | | Connects geographic parameters back to an individual site tracking record in `locations.loc_id`. |
| `ses_coach_id` | `bigint` | YES | | | Target pointer identification tracking the supervising instructor or head coach profile. |
| `ses_arch_level` | `integer` | YES | | | The programmatic segmentation model tier enforced (Level 1: Monostructural, Level 2: Hybrid, Level 3: Gauntlet). |
| `ses_weather_eng` | `text` | YES | | | Real-time weather provider information string logged in English. |
| `ses_weather_swe` | `text` | YES | | | Localized weather condition telemetry strings logged in Swedish. |
| `ses_temp` | `real` | YES | | | Outdoor temperature coordinate float captured at event generation times. |
| `ses_wind_speed` | `real` | YES | | | Measured wind velocity tracking speed data evaluated for safety restriction filters. |
| `ses_json_blob` | `text` | YES | | | Structured JSON layout configuration compiling station triplets, timing intervals, and target assets (e.g., 3-minute block series structures). |
| `ses_is_manual` | `integer` | YES | | `0` | Audit switch checking if generating engine templates were manually overridden. |
| `ses_manual_notes` | `text` | YES | | | Documented manual structural updates, alternate setups, or field changes. |
| `ses_is_canceled` | `boolean` | YES | | `false` | System cancel check flag. `true` removes session parameters from member calendar panels. |
| `ses_weather_fetched_timestamp`| `timestamp with time zone`| YES| | | Tracking verification time confirming when external meteorology APIs synced. Bypassed under `IS_DEMO` mocks. |