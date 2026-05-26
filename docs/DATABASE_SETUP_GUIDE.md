# Coach Engine 2.0 — Database Schema and Setup Guide

This document contains the verified database schema and table descriptions based on the system metadata.

## Part 1: Database Initialization Script

Run the following SQL commands to create a fresh, empty database and set up all required tables, constraints, and defaults in the correct dependency order.

```sql
-- 1. Create Roles Table
CREATE TABLE roles (
    rol_id BIGINT PRIMARY KEY,
    rol_name TEXT NOT NULL
);

-- 2. Create Users Table
CREATE TABLE users (
    use_id BIGINT PRIMARY KEY,
    use_name TEXT NOT NULL,
    use_first_name TEXT,
    use_last_name TEXT,
    use_display_name TEXT,
    use_email TEXT,
    use_mobile_phone TEXT,
    use_lang TEXT DEFAULT 'sv',
    use_theme TEXT DEFAULT 'dark',
    use_fitness_level INTEGER DEFAULT 2,
    use_is_active BOOLEAN DEFAULT true,
    use_is_locked BOOLEAN DEFAULT false,
    use_rol_id BIGINT REFERENCES roles(rol_id),
    use_last_login_at TIMESTAMP WITH TIME ZONE,
    use_created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    use_password TEXT,
    use_uuid TEXT
);

-- 3. Create Audit Log Type Table
CREATE TABLE audit_log_type (
    alt_id SMALLINT PRIMARY KEY,
    alt_code VARCHAR NOT NULL,
    alt_description TEXT
);

-- 4. Create Audit Log Table
CREATE TABLE audit_log (
    al_id BIGINT PRIMARY KEY,
    al_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    al_action_type_id SMALLINT NOT NULL REFERENCES audit_log_type(alt_id),
    al_crud_type VARCHAR,
    al_target_table VARCHAR,
    al_target_id TEXT,
    al_old_payload JSONB,
    al_new_payload JSONB,
    al_actor_user_id BIGINT REFERENCES users(use_id)
);

-- 5. Create Access Logs Table
CREATE TABLE access_logs (
    acc_id SERIAL PRIMARY KEY,
    acc_user_id INTEGER REFERENCES users(use_id),
    acc_action TEXT,
    acc_details TEXT,
    acc_timestamp TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- 6. Create Change Log Table
CREATE TABLE change_log (
    cha_id BIGINT PRIMARY KEY,
    cha_timestamp TIMESTAMP WITH TIME ZONE DEFAULT now(),
    cha_user_id BIGINT REFERENCES users(use_id),
    cha_action TEXT,
    cha_action_swe TEXT,
    cha_table_name TEXT,
    cha_column_name TEXT,
    cha_row_id BIGINT,
    cha_old_value TEXT,
    cha_new_value TEXT,
    cha_reason_swe TEXT
);

-- 7. Create Locations Table
CREATE TABLE locations (
    loc_id BIGINT PRIMARY KEY,
    loc_name TEXT NOT NULL,
    loc_name_swe TEXT NOT NULL,
    loc_lat REAL DEFAULT 59.19,
    loc_lon REAL DEFAULT 17.75,
    loc_has_hill BOOLEAN DEFAULT false,
    loc_has_staircase BOOLEAN DEFAULT false,
    loc_is_sheltered BOOLEAN DEFAULT false,
    loc_has_portable_stash BOOLEAN DEFAULT false,
    loc_can_bring_gear BOOLEAN DEFAULT true,
    loc_surface_swe TEXT DEFAULT 'Grus/Gräs',
    loc_notes_swe TEXT
);

-- 8. Create Equipment Table
CREATE TABLE equipment (
    equ_id BIGINT PRIMARY KEY,
    equ_name TEXT NOT NULL,
    equ_name_swe TEXT NOT NULL,
    equ_is_fixed BOOLEAN DEFAULT false,
    loc_id INTEGER DEFAULT -1,
    equ_is_rain_safe BOOLEAN DEFAULT true,
    equ_is_wind_safe BOOLEAN DEFAULT true,
    equ_is_group BOOLEAN DEFAULT true,
    equ_is_stations_only BOOLEAN DEFAULT false
);

-- 9. Create Equipment Inventory Table
CREATE TABLE equipment_inventory (
    iv_id SERIAL PRIMARY KEY,
    equ_id INTEGER REFERENCES equipment(equ_id),
    iv_spec TEXT NOT NULL,
    iv_count INTEGER DEFAULT 0,
    iv_unit TEXT DEFAULT 'st',
    iv_is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- 10. Create Exercises Table
CREATE TABLE exercises (
    exe_id BIGINT PRIMARY KEY,
    exe_name TEXT NOT NULL,
    exe_name_swe TEXT NOT NULL,
    exe_equ_id INTEGER REFERENCES equipment(equ_id),
    exe_level INTEGER,
    exe_is_combo BOOLEAN DEFAULT false,
    exe_is_standing BOOLEAN DEFAULT true,
    exe_is_rain_safe BOOLEAN DEFAULT true,
    exe_hill BOOLEAN DEFAULT false,
    exe_staircase BOOLEAN DEFAULT false,
    is_blacklisted BOOLEAN DEFAULT false,
    exe_author INTEGER REFERENCES users(use_id),
    exe_description TEXT
);

-- 11. Create Adaptations Table
CREATE TABLE adaptations (
    ada_id BIGINT PRIMARY KEY,
    ada_exe_id BIGINT NOT NULL REFERENCES exercises(exe_id),
    ada_name TEXT NOT NULL,
    ada_name_swe TEXT NOT NULL,
    ada_is_standing BOOLEAN DEFAULT true,
    ada_staircase_req BOOLEAN DEFAULT false,
    ada_is_rain_safe BOOLEAN DEFAULT true
);

-- 12. Create Notifications Table
CREATE TABLE notifications (
    not_id SERIAL PRIMARY KEY,
    not_created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    not_user_id INTEGER REFERENCES users(use_id),
    not_message TEXT NOT NULL,
    not_valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
    not_valid_to TIMESTAMP WITH TIME ZONE NOT NULL
);

-- 13. Create Weather Conditions Table
CREATE TABLE weather_conditions (
    wea_id BIGINT PRIMARY KEY,
    wea_name_en TEXT NOT NULL,
    wea_name_swe TEXT NOT NULL,
    wea_is_active BOOLEAN DEFAULT true,
    wea_trigger_standing BOOLEAN DEFAULT false,
    wea_trigger_rain_safe BOOLEAN DEFAULT false,
    wea_trigger_wind_safe BOOLEAN DEFAULT false,
    wea_note_swe TEXT
);

-- 14. Create Workout Sessions Table
CREATE TABLE workout_sessions (
    ses_id BIGINT PRIMARY KEY,
    ses_timestamp TIMESTAMP WITH TIME ZONE DEFAULT now(),
    ses_loc_id BIGINT REFERENCES locations(loc_id),
    ses_coach_id BIGINT,
    ses_arch_level INTEGER,
    ses_weather_eng TEXT,
    ses_weather_swe TEXT,
    ses_temp REAL,
    ses_wind_speed REAL,
    ses_json_blob TEXT,
    ses_is_manual INTEGER DEFAULT 0,
    ses_manual_notes TEXT,
    ses_is_canceled BOOLEAN DEFAULT false,
    ses_weather_fetched_timestamp TIMESTAMP WITH TIME ZONE
);

-- 15. Create Session Participants Table
CREATE TABLE session_participants (
    sep_id BIGINT PRIMARY KEY,
    sep_session_id BIGINT NOT NULL REFERENCES workout_sessions(ses_id),
    sep_user_id BIGINT NOT NULL REFERENCES users(use_id),
    sep_role_id BIGINT DEFAULT 3,
    sep_feedback TEXT,
    sep_effort_score INTEGER,
    sep_created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    sep_is_leader BOOLEAN DEFAULT false,
    sep_status INTEGER DEFAULT 1
);
```

## Part 2: Table Functions & Data Type Documentation

Here is the comprehensive description of the verified tables and their underlying schemas.

### 1. `roles`
Stores the system authorization roles for controlling user capabilities.
* **`rol_id`** (`BIGINT`, PK): Unique role identifier.
* **`rol_name`** (`TEXT`): Name of the role (e.g., Admin, Coach, Member).

### 2. `users`
Manages core user profiles, localizations, application preferences, and references permissions.
* **`use_id`** (`BIGINT`, PK): Internal sequential user identifier.
* **`use_name`** / **`use_display_name`** (`TEXT`): Identifiers and names exposed on leaderboards.
* **`use_lang`** (`TEXT`): User interface language configuration (default is 'sv').
* **`use_rol_id`** (`BIGINT`, FK): Links to `roles`.

### 3. `audit_log_type` & `audit_log`
Provides structural activity tracking across database records for administrative visibility.
* **`al_crud_type`** (`VARCHAR`): Records the operation category (`INSERT`, `UPDATE`, `DELETE`).
* **`al_new_payload`** / **`al_old_payload`** (`JSONB`): Stores structured operational payloads for record differentials.

### 4. `access_logs` & `change_log`
Tracks granular platform actions and localized administrative context on mutations.
* **`acc_action`** / **`cha_action`** (`TEXT`): User actions tracked in log outputs.

### 5. `locations`
Geographic definitions for tactical outdoor workout session configurations.
* **`loc_has_hill`** / **`loc_has_staircase`** (`BOOLEAN`): Infrastructure triggers that enable specific workout paradigms.

### 6. `equipment` & `equipment_inventory`
Material lists and localized inventory parameters for active session orchestration.
* **`equ_is_stations_only`** (`BOOLEAN`): Restricts equipment strictly to station environments.

### 7. `exercises` & `adaptations`
The motion bank and tactical alternative motions.
* **`exe_is_combo`** / **`exe_is_standing`** (`BOOLEAN`): Biomechanical modifiers used by the execution matrix.
* **`ada_name`** (`TEXT`): Alternative motions strictly normalized as **"förenklad övning"** for scaling.

### 8. `weather_conditions`
Weather states influencing execution logic.
* **`wea_trigger_wind_safe`** / **`wea_trigger_rain_safe`** (`BOOLEAN`): Triggers modifying available exercise vectors under stress.

### 9. `workout_sessions` & `session_participants`
Core historical and live tracking records for all generated functional routines.