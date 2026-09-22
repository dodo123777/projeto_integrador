-- Diagnóstico somente leitura. Não cria tabelas, não modifica registros nem permissões.
-- Executar no PostgreSQL/Supabase de desenvolvimento ANTES de aplicar migrations.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';

SELECT current_user AS papel_conexao, session_user AS papel_sessao, version();

SELECT table_name, column_name, data_type, is_nullable, column_default, is_identity, identity_generation
FROM information_schema.columns
WHERE table_schema = 'public'
    AND table_name IN ('usuarios', 'tarefas', 'profissionais', 'profissional_pacientes', 'consultas', 'auditoria_admin')
ORDER BY table_name, ordinal_position;

SELECT c.relname AS tabela, pg_get_userbyid(c.relowner) AS proprietario,
    c.relrowsecurity AS rls_habilitada, c.relforcerowsecurity AS rls_forcada
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
    AND c.relname IN ('usuarios', 'tarefas', 'profissionais', 'profissional_pacientes', 'consultas', 'auditoria_admin');

SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies
WHERE schemaname = 'public'
    AND tablename IN ('usuarios', 'tarefas', 'profissionais', 'profissional_pacientes', 'consultas', 'auditoria_admin');

SELECT grantee, table_name, privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public'
    AND table_name IN ('usuarios', 'tarefas', 'profissionais', 'profissional_pacientes', 'consultas', 'auditoria_admin')
ORDER BY table_name, grantee, privilege_type;

SELECT rolname, rolsuper, rolbypassrls
FROM pg_roles
WHERE rolname IN (current_user, 'anon', 'authenticated', 'service_role');

SELECT conrelid::regclass AS tabela, conname, pg_get_constraintdef(oid) AS definicao
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
    AND conrelid::regclass::text IN ('usuarios', 'tarefas', 'profissionais', 'profissional_pacientes', 'consultas', 'auditoria_admin');

-- Os campos opcionais são lidos como JSON: funciona antes e depois da migration 001 revisada.
SELECT COALESCE(to_jsonb(u)->>'role', '(sem role)') AS role_atual,
    COALESCE(to_jsonb(u)->>'ativo', '(sem campo ativo)') AS status_atual, COUNT(*) AS quantidade
FROM usuarios u GROUP BY 1, 2 ORDER BY 1, 2;

SELECT COUNT(*) AS grupos_email_duplicado_sem_diferenciar_maiusculas
FROM (SELECT lower(email) FROM usuarios GROUP BY lower(email) HAVING COUNT(*) > 1) duplicados;

-- Apenas contagens; nao retorna nomes, emails ou hashes de senha.
SELECT COUNT(*) AS usuarios,
    COUNT(*) FILTER (WHERE nome IS NULL OR btrim(nome) = '') AS nomes_ausentes,
    COUNT(*) FILTER (WHERE senha IS NULL OR senha = '') AS senhas_ausentes,
    COUNT(*) FILTER (WHERE senha ~ '^\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}$') AS hashes_bcrypt_compativeis
FROM public.usuarios;

SELECT COUNT(*) AS tarefas,
    COUNT(*) FILTER (WHERE u.id IS NULL) AS tarefas_sem_usuario
FROM public.tarefas t LEFT JOIN public.usuarios u ON u.id = t.usuario_id;

COMMIT;
