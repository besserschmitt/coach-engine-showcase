Markdown
# Database Triggers & SQL Backup (Coach Engine)

## 📌 1. Active Triggers (Overview)

| table_name           | trigger_name                       | event  | definition                                      |
| -------------------- | ---------------------------------- | ------ | ----------------------------------------------- |
| adaptations          | trigger_audit_adaptations          | UPDATE | EXECUTE FUNCTION log_adaptation_changes()       |
| equipment            | trigger_audit_equipment            | UPDATE | EXECUTE FUNCTION log_equipment_changes()        |
| exercises            | trigger_audit_exercises            | UPDATE | EXECUTE FUNCTION log_exercise_changes()         |
| locations            | trigger_audit_locations            | UPDATE | EXECUTE FUNCTION log_location_changes()         |
| session_participants | trigger_audit_session_participants | INSERT | EXECUTE FUNCTION log_participant_changes()      |
| session_participants | trigger_audit_session_participants | UPDATE | EXECUTE FUNCTION log_participant_changes()      |
| users                | trigger_audit_users                | UPDATE | EXECUTE FUNCTION log_user_changes()             |
| workout_sessions     | trigger_session_json_update        | UPDATE | EXECUTE FUNCTION log_session_json_update()      |
| workout_sessions     | trigger_session_weather_update     | UPDATE | EXECUTE FUNCTION log_session_weather_update()   |
| workout_sessions     | trigger_session_insert             | INSERT | EXECUTE FUNCTION log_session_insert()           |

---

## 🔍 2. Smart Database Queries

### Find All Relevant Columns (Metadata)
Used to quickly retrieve all columns related to users, timestamps, IDs, or statuses.

```sql
SELECT 
    table_name AS table_name,
    column_name AS column_name,
    data_type AS data_type,
    is_nullable AS is_nullable
FROM 
    information_schema.columns
WHERE 
    table_schema = 'public'
    AND table_name NOT IN ('schema_migrations', 'spatial_ref_sys') 
    AND (
        column_name LIKE '%user%'      
        OR column_name LIKE '%id%'     
        OR column_name LIKE '%uuid%'   
        OR column_name LIKE '%time%'   
        OR column_name LIKE '%creat%'  
        OR column_name LIKE '%stat%'   
    )
ORDER BY 
    table_name, 
    ordinal_position;
⚙️ 3. Configuration: Audit Log Types
These codes must exist in the audit_log_type table for the triggers to map onto the correct event category type.

SQL
INSERT INTO public.audit_log_type (alt_id, alt_code, alt_description) VALUES
(6, 'PARTICIPANT_UPDATED', 'Participant change (RSVP/Leader)'),
(7, 'USER_ROLE_UPDATED', 'User or role assignment change'),
(8, 'EQUIPMENT_UPDATED', 'Equipment structural update (Station Lockout)'),
(9, 'EXERCISE_UPDATED', 'Exercise record updated in repository bank'),
(10, 'ADAPTATION_UPDATED', 'Adaptation entry modified (Simplified exercise)'),
(11, 'LOCATION_UPDATED', 'Location geography metadata update'),
(12, 'SESSION_CREATED', 'Workout session scheduled (INSERT)'),
(13, 'SESSION_WEATHER_SYNCED', 'Weather snapshot synchronized to session'),
(14, 'SESSION_PROGRAM_UPDATED', 'Workout architecture program generated/modified')
ON CONFLICT (alt_id) DO UPDATE 
SET alt_code = EXCLUDED.alt_code, alt_description = EXCLUDED.alt_description;
🚀 4. System Triggers & SQL Functions (Latest Master Code)
4.1 Participants (session_participants) - INSERT & UPDATE
SQL
CREATE OR REPLACE FUNCTION public.log_participant_changes()
RETURNS TRIGGER AS $$
DECLARE
    v_actor_id BIGINT;
    v_action_type INT;
    v_crud_type TEXT;
    v_old_payload JSONB := NULL;
    v_new_payload JSONB;
BEGIN
    -- Determine the current context user executing the action
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    IF v_actor_id IS NULL THEN v_actor_id := NEW.sep_user_id; END IF;
    IF v_actor_id IS NULL THEN v_actor_id := 0; END IF;

    IF TG_OP = 'INSERT' THEN
        v_action_type := 3; -- DATA_CREATED
        v_crud_type := 'INSERT';
        v_new_payload := jsonb_build_object('sep_session_id', NEW.sep_session_id, 'sep_user_id', NEW.sep_user_id, 'sep_status', NEW.sep_status, 'sep_is_leader', NEW.sep_is_leader);
    ELSE
        -- Safeguard: short-circuit execution if core transactional metrics are unchanged
        IF (OLD.sep_status IS NOT DISTINCT FROM NEW.sep_status AND OLD.sep_is_leader IS NOT DISTINCT FROM NEW.sep_is_leader) THEN
            RETURN NEW;
        END IF;
        v_action_type := 6; -- PARTICIPANT_UPDATED
        v_crud_type := 'UPDATE';
        v_old_payload := jsonb_build_object('sep_status', OLD.sep_status, 'sep_is_leader', OLD.sep_is_leader);
        v_new_payload := jsonb_build_object('sep_status', NEW.sep_status, 'sep_is_leader', NEW.sep_is_leader);
    END IF;

    INSERT INTO public.audit_log (al_action_type_id, al_crud_type, al_target_table, al_target_id, al_old_payload, al_new_payload, al_actor_user_id) 
    VALUES (v_action_type, v_crud_type, 'session_participants', NEW.sep_id::text, v_old_payload, v_new_payload, v_actor_id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_audit_session_participants ON public.session_participants;
CREATE TRIGGER trigger_audit_session_participants
AFTER INSERT OR UPDATE ON public.session_participants
FOR EACH ROW
EXECUTE FUNCTION public.log_participant_changes();
4.2 Users & Roles (users)
SQL
CREATE OR REPLACE FUNCTION public.log_user_changes()
RETURNS TRIGGER AS $$
DECLARE v_actor_id BIGINT;
BEGIN
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    IF v_actor_id IS NULL THEN v_actor_id := 0; END IF;

    INSERT INTO public.audit_log (al_action_type_id, al_crud_type, al_target_table, al_target_id, al_old_payload, al_new_payload, al_actor_user_id) 
    VALUES (7, 'UPDATE', 'users', OLD.use_id::text, jsonb_build_object('use_display_name', OLD.use_display_name, 'use_rol_id', OLD.use_rol_id), jsonb_build_object('use_display_name', NEW.use_display_name, 'use_rol_id', NEW.use_rol_id), v_actor_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_audit_users ON public.users;
CREATE OR REPLACE TRIGGER trigger_audit_users
AFTER UPDATE OF use_rol_id, use_display_name ON public.users
FOR EACH ROW
WHEN (OLD.use_rol_id IS DISTINCT FROM NEW.use_rol_id OR OLD.use_display_name IS DISTINCT FROM NEW.use_display_name)
EXECUTE FUNCTION public.log_user_changes();
4.3 Workout Sessions (workout_sessions) - INSERT
SQL
CREATE OR REPLACE FUNCTION public.log_session_insert()
RETURNS TRIGGER AS $$
DECLARE v_actor_id BIGINT;
BEGIN
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    IF v_actor_id IS NULL THEN v_actor_id := 0; END IF;

    -- Log initial metadata properties while keeping large structural program blobs out of the log stream
    INSERT INTO public.audit_log (al_action_type_id, al_crud_type, al_target_table, al_target_id, al_new_payload, al_actor_user_id) 
    VALUES (12, 'INSERT', 'workout_sessions', NEW.ses_id::text, to_jsonb(NEW) - 'ses_json_blob', v_actor_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_session_insert ON public.workout_sessions;
CREATE TRIGGER trigger_session_insert
AFTER INSERT ON public.workout_sessions
FOR EACH ROW
EXECUTE FUNCTION public.log_session_insert();
4.4 Workout Sessions (workout_sessions) - Weather Sync
SQL
CREATE OR REPLACE FUNCTION public.log_session_weather_update()
RETURNS TRIGGER AS $$
DECLARE v_actor_id BIGINT;
BEGIN
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    IF v_actor_id IS NULL THEN v_actor_id := 0; END IF;

    INSERT INTO public.audit_log (al_action_type_id, al_crud_type, al_target_table, al_target_id, al_old_payload, al_new_payload, al_actor_user_id) 
    VALUES (13, 'UPDATE', 'workout_sessions', OLD.ses_id::text, jsonb_build_object('ses_wea_id', OLD.ses_wea_id, 'ses_temp', OLD.ses_temp, 'ses_weather_swe', OLD.ses_weather_swe), jsonb_build_object('ses_wea_id', NEW.ses_wea_id, 'ses_temp', NEW.ses_temp, 'ses_weather_swe', NEW.ses_weather_swe), v_actor_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_session_weather_update ON public.workout_sessions;
CREATE TRIGGER trigger_session_weather_update
AFTER UPDATE OF ses_weather_fetched_timestamp ON public.workout_sessions
FOR EACH ROW
WHEN (OLD.ses_weather_fetched_timestamp IS DISTINCT FROM NEW.ses_weather_fetched_timestamp)
EXECUTE FUNCTION public.log_session_weather_update();
4.5 Workout Sessions (workout_sessions) - Program/JSON Blob Update
SQL
CREATE OR REPLACE FUNCTION public.log_session_json_update()
RETURNS TRIGGER AS $$
DECLARE v_actor_id BIGINT;
BEGIN
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    IF v_actor_id IS NULL THEN v_actor_id := 0; END IF;

    INSERT INTO public.audit_log (al_action_type_id, al_crud_type, al_target_table, al_target_id, al_old_payload, al_new_payload, al_actor_user_id) 
    VALUES (14, 'UPDATE', 'workout_sessions', OLD.ses_id::text, jsonb_build_object('ses_manual_notes', OLD.ses_manual_notes, 'ses_arch_level', OLD.ses_arch_level), jsonb_build_object('ses_manual_notes', NEW.ses_manual_notes, 'ses_arch_level', NEW.ses_arch_level), v_actor_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_session_json_update ON public.workout_sessions;
CREATE TRIGGER trigger_session_json_update
AFTER UPDATE OF ses_json_blob ON public.workout_sessions
FOR EACH ROW
WHEN (OLD.ses_json_blob IS DISTINCT FROM NEW.ses_json_blob)
EXECUTE FUNCTION public.log_session_json_update();
4.6 Equipment (equipment)
SQL
CREATE OR REPLACE FUNCTION public.log_equipment_changes()
RETURNS TRIGGER AS $$
DECLARE v_actor_id BIGINT;
BEGIN
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    IF v_actor_id IS NULL THEN v_actor_id := 0; END IF;

    INSERT INTO public.audit_log (al_action_type_id, al_crud_type, al_target_table, al_target_id, al_old_payload, al_new_payload, al_actor_user_id) 
    VALUES (8, 'UPDATE', 'equipment', OLD.equ_id::text, jsonb_build_object('equ_is_stations_only', OLD.equ_is_stations_only), jsonb_build_object('equ_is_stations_only', NEW.equ_is_stations_only), v_actor_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_audit_equipment ON public.equipment;
CREATE OR REPLACE TRIGGER trigger_audit_equipment
AFTER UPDATE OF equ_is_stations_only ON public.equipment
FOR EACH ROW
WHEN (OLD.equ_is_stations_only IS DISTINCT FROM NEW.equ_is_stations_only)
EXECUTE FUNCTION public.log_equipment_changes();
4.7 Exercise Repository Bank (exercises)
SQL
CREATE OR REPLACE FUNCTION public.log_exercise_changes()
RETURNS TRIGGER AS $$
DECLARE v_actor_id BIGINT; v_old_payload JSONB; v_new_payload JSONB;
BEGIN
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    IF v_actor_id IS NULL THEN v_actor_id := 0; END IF;

    v_old_payload := to_jsonb(OLD) - 'exe_id';
    v_new_payload := to_jsonb(NEW) - 'exe_id';

    INSERT INTO public.audit_log (al_action_type_id, al_crud_type, al_target_table, al_target_id, al_old_payload, al_new_payload, al_actor_user_id) 
    VALUES (9, 'UPDATE', 'exercises', OLD.exe_id::text, v_old_payload, v_new_payload, v_actor_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_audit_exercises ON public.exercises;
CREATE OR REPLACE TRIGGER trigger_audit_exercises
AFTER UPDATE ON public.exercises
FOR EACH ROW
WHEN (OLD IS DISTINCT FROM NEW)
EXECUTE FUNCTION public.log_exercise_changes();
4.8 Adaptations / Simplified Exercises (adaptations)
SQL
CREATE OR REPLACE FUNCTION public.log_adaptation_changes()
RETURNS TRIGGER AS $$
DECLARE v_actor_id BIGINT; v_old_payload JSONB; v_new_payload JSONB;
BEGIN
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    IF v_actor_id IS NULL THEN v_actor_id := 0; END IF;

    v_old_payload := to_jsonb(OLD) - 'ada_id';
    v_new_payload := to_jsonb(NEW) - 'ada_id';

    INSERT INTO public.audit_log (al_action_type_id, al_crud_type, al_target_table, al_target_id, al_old_payload, al_new_payload, al_actor_user_id) 
    VALUES (10, 'UPDATE', 'adaptations', OLD.ada_id::text, v_old_payload, v_new_payload, v_actor_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_audit_adaptations ON public.adaptations;
CREATE OR REPLACE TRIGGER trigger_audit_adaptations
AFTER UPDATE ON public.adaptations
FOR EACH ROW
WHEN (OLD IS DISTINCT FROM NEW)
EXECUTE FUNCTION public.log_adaptation_changes();
4.9 Locations (locations)
SQL
CREATE OR REPLACE FUNCTION public.log_location_changes()
RETURNS TRIGGER AS $$
DECLARE v_actor_id BIGINT; v_old_payload JSONB; v_new_payload JSONB;
BEGIN
    SELECT use_id INTO v_actor_id FROM public.users WHERE use_uuid = auth.uid()::text;
    IF v_actor_id IS NULL THEN v_actor_id := 0; END IF;

    v_old_payload := to_jsonb(OLD) - 'loc_id';
    v_new_payload := to_jsonb(NEW) - 'loc_id';

    INSERT INTO public.audit_log (al_action_type_id, al_crud_type, al_target_table, al_target_id, al_old_payload, al_new_payload, al_actor_user_id) 
    VALUES (11, 'UPDATE', 'locations', OLD.loc_id::text, v_old_payload, v_new_payload, v_actor_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_audit_locations ON public.locations;
CREATE OR REPLACE TRIGGER trigger_audit_locations
AFTER UPDATE ON public.locations
FOR EACH ROW
WHEN (OLD IS DISTINCT FROM NEW)
EXECUTE FUNCTION public.log_location_changes();