-- Aplicar no mesmo PostgreSQL de usuarios e tarefas. Não concede acesso automaticamente.
BEGIN;
CREATE TABLE IF NOT EXISTS profissionais (
    usuario_id BIGINT PRIMARY KEY REFERENCES usuarios(id),
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('medico', 'psicologo')),
    registro VARCHAR(60) NOT NULL CHECK (length(trim(registro)) > 0),
    especialidade VARCHAR(120),
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS profissional_pacientes (
    profissional_id BIGINT NOT NULL REFERENCES profissionais(usuario_id),
    paciente_id BIGINT NOT NULL REFERENCES usuarios(id),
    vinculado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profissional_id, paciente_id),
    CHECK (profissional_id <> paciente_id)
);
CREATE TABLE IF NOT EXISTS consultas (
    id BIGSERIAL PRIMARY KEY,
    profissional_id BIGINT NOT NULL,
    paciente_id BIGINT NOT NULL,
    inicio TIMESTAMPTZ NOT NULL,
    tipo VARCHAR(40) NOT NULL CHECK (tipo IN ('Consulta médica', 'Consulta psicológica', 'Retorno')),
    status VARCHAR(20) NOT NULL DEFAULT 'agendada'
        CHECK (status IN ('agendada', 'confirmada', 'em_atendimento', 'finalizada', 'cancelada')),
    FOREIGN KEY (profissional_id, paciente_id)
        REFERENCES profissional_pacientes(profissional_id, paciente_id)
);
CREATE INDEX IF NOT EXISTS consultas_profissional_inicio ON consultas(profissional_id, inicio);
CREATE INDEX IF NOT EXISTS consultas_paciente ON consultas(profissional_id, paciente_id, inicio);
CREATE UNIQUE INDEX IF NOT EXISTS consultas_horario_ativo ON consultas(profissional_id, inicio)
    WHERE status <> 'cancelada';
-- Supabase pode expor o schema public pela Data API. Sem políticas públicas,
-- os papéis anon/authenticated não acessam estas tabelas diretamente.
-- Aplicar como o papel confiável usado pelo backend (proprietário das tabelas).
ALTER TABLE profissionais ENABLE ROW LEVEL SECURITY;
ALTER TABLE profissional_pacientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE consultas ENABLE ROW LEVEL SECURITY;
COMMIT;
