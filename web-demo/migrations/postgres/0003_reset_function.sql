-- 0003 (PostgreSQL): reset controlado dos dados fictícios.
--
-- O papel da aplicação não tem TRUNCATE nem é dono das sequências. Esta função,
-- executada com os privilégios do dono das migrations, esvazia SOMENTE as tabelas
-- do esquema agende_bem e reinicia os identificadores. Nada fora do esquema é tocado.

CREATE FUNCTION agende_bem.reset_demo_data()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = agende_bem, pg_temp
AS $$
BEGIN
    TRUNCATE agende_bem.audit_events,
             agende_bem.appointments,
             agende_bem.waiting_list,
             agende_bem.professionals,
             agende_bem.settings
    RESTART IDENTITY;
END
$$;

REVOKE ALL ON FUNCTION agende_bem.reset_demo_data() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION agende_bem.reset_demo_data() TO agende_bem_app;

DO $$
DECLARE
    api_role text;
BEGIN
    FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
            EXECUTE format('REVOKE ALL ON FUNCTION agende_bem.reset_demo_data() FROM %I', api_role);
        END IF;
    END LOOP;
END
$$;
