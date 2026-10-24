-- 0005 (PostgreSQL): identidade e papel operacional resolvidos no servidor.
-- Não há FK para auth.users: auth é schema gerenciado pelo Supabase e não deve
-- receber alterações por migrations da aplicação.

CREATE TABLE agende_bem.app_users (
    user_id uuid PRIMARY KEY,
    email text NOT NULL CHECK (char_length(email) BETWEEN 3 AND 320),
    role text NOT NULL CHECK (role IN ('administrador', 'recepcao', 'leitura')),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX app_users_email_ci_key ON agende_bem.app_users (lower(email));
CREATE TRIGGER app_users_set_updated_at BEFORE UPDATE ON agende_bem.app_users
    FOR EACH ROW EXECUTE FUNCTION agende_bem.set_updated_at();

GRANT SELECT, INSERT, UPDATE, DELETE ON agende_bem.app_users TO agende_bem_app;
ALTER TABLE agende_bem.app_users ENABLE ROW LEVEL SECURITY;
CREATE POLICY agende_bem_app_all ON agende_bem.app_users
    FOR ALL TO agende_bem_app USING (true) WITH CHECK (true);
