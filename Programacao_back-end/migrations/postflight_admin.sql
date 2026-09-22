-- SOMENTE LEITURA. Usar depois da aplicacao APROVADA de 001 e 002 revisadas.
-- Nao cria administrador, nao modifica usuarios e nao simula logins.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';

SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
    AND table_name IN ('usuarios', 'tarefas', 'profissional_pacientes', 'consultas', 'auditoria_admin')
ORDER BY table_name, ordinal_position;

SELECT role, ativo, COUNT(*) FROM public.usuarios GROUP BY role, ativo ORDER BY role, ativo;
SELECT COUNT(*) AS usuarios,
    COUNT(*) FILTER (WHERE criado_em IS NULL) AS cadastros_sem_data_historica,
    COUNT(*) FILTER (WHERE role = 'psicologo' AND (registro IS NULL OR btrim(registro) = '')) AS psicologos_sem_registro,
    COUNT(*) FILTER (WHERE perfil_profissional_ativo AND role <> 'psicologo') AS perfis_incoerentes
FROM public.usuarios;
SELECT COUNT(*) AS tarefas,
    COUNT(*) FILTER (WHERE u.id IS NULL) AS tarefas_sem_usuario
FROM public.tarefas t LEFT JOIN public.usuarios u ON u.id = t.usuario_id;

SELECT COUNT(*) AS vinculos_com_roles_incorretas
FROM public.profissional_pacientes v
JOIN public.usuarios pro ON pro.id = v.profissional_id
JOIN public.usuarios pac ON pac.id = v.paciente_id
WHERE v.ativo AND (pro.role <> 'psicologo' OR pac.role <> 'paciente');

SELECT c.relname AS tabela, c.relrowsecurity AS rls_habilitada
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
    AND c.relname IN ('usuarios', 'tarefas', 'profissional_pacientes', 'consultas', 'auditoria_admin');
SELECT grantee, table_name, privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public' AND grantee IN ('PUBLIC', 'anon', 'authenticated')
    AND table_name IN ('usuarios', 'tarefas', 'profissional_pacientes', 'consultas', 'auditoria_admin');
SELECT tablename, policyname, roles, cmd
FROM pg_policies WHERE schemaname = 'public';
SELECT rolname, rolbypassrls FROM pg_roles WHERE rolname = current_user;
SELECT to_regclass('public.profissionais') AS tabela_profissionais_nao_deve_existir;
COMMIT;
