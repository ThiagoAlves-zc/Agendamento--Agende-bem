-- 0002 (PostgreSQL): papel da aplicação com privilégios mínimos e bloqueio da API pública.
--
-- O papel é criado SEM login. A senha nunca fica no Git; o operador habilita o acesso
-- manualmente, no SQL Editor do Supabase:
--     ALTER ROLE agende_bem_app WITH LOGIN PASSWORD '<senha forte gerada fora do Git>';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agende_bem_app') THEN
        CREATE ROLE agende_bem_app NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

ALTER ROLE agende_bem_app SET search_path = agende_bem;
ALTER ROLE agende_bem_app SET statement_timeout = '15s';
ALTER ROLE agende_bem_app SET idle_in_transaction_session_timeout = '30s';

REVOKE ALL ON SCHEMA agende_bem FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA agende_bem FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA agende_bem FROM PUBLIC;

-- Apenas uso do esquema (sem CREATE) e DML nas tabelas da aplicação.
GRANT USAGE ON SCHEMA agende_bem TO agende_bem_app;
GRANT SELECT ON agende_bem.schema_migrations TO agende_bem_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    agende_bem.settings,
    agende_bem.professionals,
    agende_bem.waiting_list,
    agende_bem.appointments,
    agende_bem.audit_events
TO agende_bem_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA agende_bem TO agende_bem_app;
-- Sem TRUNCATE nem posse das sequências: o reset da demonstração usa a função da 0003.

-- Papéis da API do Supabase (anon/authenticated) não acessam nada deste esquema.
DO $$
DECLARE
    api_role text;
BEGIN
    FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
            EXECUTE format('REVOKE ALL ON SCHEMA agende_bem FROM %I', api_role);
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA agende_bem FROM %I', api_role);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA agende_bem FROM %I', api_role);
        END IF;
    END LOOP;
END
$$;

-- Defesa em profundidade: RLS ativo; somente o papel da aplicação tem política.
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['settings', 'professionals', 'waiting_list', 'appointments', 'audit_events'] LOOP
        EXECUTE format('ALTER TABLE agende_bem.%I ENABLE ROW LEVEL SECURITY', tbl);
        EXECUTE format(
            'CREATE POLICY agende_bem_app_all ON agende_bem.%I FOR ALL TO agende_bem_app '
            'USING (true) WITH CHECK (true)', tbl);
    END LOOP;
END
$$;
