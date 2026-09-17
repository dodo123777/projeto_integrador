-- Requer 001_area_profissional.sql. Revisar em homologação antes de produção.
BEGIN;

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS role VARCHAR(20);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- Somente roles ausentes são preenchidas; uma execução repetida não desfaz decisões administrativas.
UPDATE usuarios u SET role = COALESCE(
    (SELECT p.tipo FROM profissionais p WHERE p.usuario_id = u.id AND p.tipo IN ('psicologo', 'medico')),
    'paciente'
) WHERE u.role IS NULL;

ALTER TABLE usuarios ALTER COLUMN role SET DEFAULT 'paciente';
ALTER TABLE usuarios ALTER COLUMN role SET NOT NULL;

DO $$ BEGIN
    ALTER TABLE usuarios ADD CONSTRAINT usuarios_role_check
        CHECK (role IN ('paciente', 'psicologo', 'medico', 'admin'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE profissional_pacientes ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE profissional_pacientes ADD COLUMN IF NOT EXISTS desvinculado_em TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS auditoria_admin (
    id BIGSERIAL PRIMARY KEY,
    administrador_id BIGINT REFERENCES usuarios(id),
    acao VARCHAR(60) NOT NULL,
    usuario_afetado_id BIGINT REFERENCES usuarios(id),
    profissional_id BIGINT REFERENCES usuarios(id),
    paciente_id BIGINT REFERENCES usuarios(id),
    detalhes JSONB NOT NULL DEFAULT '{}'::jsonb,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS auditoria_admin_criado_em ON auditoria_admin(criado_em DESC);
CREATE INDEX IF NOT EXISTS auditoria_admin_administrador ON auditoria_admin(administrador_id, criado_em DESC);

-- O JWT do Flask não é um JWT do Supabase. Sem policies públicas, estas tabelas
-- ficam inacessíveis pela Data API; a autorização por usuário continua no Flask.
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria_admin ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON usuarios, profissionais, profissional_pacientes, consultas, auditoria_admin FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON usuarios, profissionais, profissional_pacientes, consultas, auditoria_admin FROM authenticated;
    END IF;
END $$;

COMMIT;
