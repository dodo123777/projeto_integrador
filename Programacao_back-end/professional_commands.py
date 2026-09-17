"""Operações locais da equipe responsável; não expostas por HTTP."""
import click
from database import db_manager
from models.admin import AdminModel


def register_professional_commands(app):
    def administrator(cursor, email):
        cursor.execute("SELECT id FROM usuarios WHERE email = %s AND role = 'admin' AND ativo", (email,))
        row = cursor.fetchone()
        if not row:
            raise click.ClickException('Informe uma conta administrativa ativa para autorizar e auditar a operação.')
        return row[0]

    @app.cli.command('profissional-autorizar')
    @click.option('--admin-email', required=True)
    @click.option('--email', required=True)
    @click.option('--tipo', type=click.Choice(['medico', 'psicologo']), required=True)
    @click.option('--registro', required=True)
    @click.option('--especialidade', default=None)
    def authorize(admin_email, email, tipo, registro, especialidade):
        """Habilitar uma conta existente após verificar a identidade e o registro."""
        registro = registro.strip()
        if not registro or len(registro) > 60 or (especialidade and len(especialidade) > 120):
            raise click.ClickException('Registro ou especialidade inválidos.')
        with db_manager.get_cursor() as cur:
            admin_id = administrator(cur, admin_email)
            cur.execute("UPDATE usuarios SET role = %s WHERE email = %s AND ativo AND role = 'paciente' RETURNING id", (tipo, email))
            user = cur.fetchone()
            if not user:
                raise click.ClickException('Conta ativa não encontrada. Cadastre a conta antes de habilitá-la.')
            cur.execute('''
                INSERT INTO profissionais (usuario_id, tipo, registro, especialidade)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (usuario_id) DO UPDATE SET tipo = EXCLUDED.tipo,
                    registro = EXCLUDED.registro, especialidade = EXCLUDED.especialidade, ativo = TRUE
                RETURNING usuario_id
            ''', (user[0], tipo, registro, especialidade))
            if not cur.fetchone():
                raise click.ClickException('Conta não encontrada. Cadastre a conta antes de habilitá-la.')
            AdminModel._write_audit(cur, admin_id, f'usuario_promovido_{tipo}', affected=user[0],
                                   details={'origem': 'flask_cli', 'registro': registro})
        db_manager.commit()
        click.echo('Profissional habilitado.')

    @app.cli.command('profissional-revogar')
    @click.option('--admin-email', required=True)
    @click.option('--email', required=True)
    def revoke(admin_email, email):
        """Revogar o acesso profissional, inclusive para JWTs já emitidos."""
        with db_manager.get_cursor() as cur:
            admin_id = administrator(cur, admin_email)
            cur.execute('''UPDATE profissionais p SET ativo = FALSE
                FROM usuarios u WHERE p.usuario_id = u.id AND u.email = %s
                    AND u.role IN ('psicologo', 'medico') RETURNING p.usuario_id''', (email,))
            user = cur.fetchone()
            if not user:
                raise click.ClickException('Profissional não encontrado.')
            cur.execute("UPDATE usuarios SET role = 'paciente' WHERE email = %s", (email,))
            cur.execute('''UPDATE profissional_pacientes SET ativo = FALSE, desvinculado_em = CURRENT_TIMESTAMP
                WHERE profissional_id = (SELECT id FROM usuarios WHERE email = %s) AND ativo''', (email,))
            AdminModel._write_audit(cur, admin_id, 'permissao_profissional_revogada', affected=user[0],
                                   details={'origem': 'flask_cli'})
        db_manager.commit()
        click.echo('Acesso profissional revogado.')

    @app.cli.command('profissional-vincular')
    @click.option('--admin-email', required=True)
    @click.option('--profissional-email', required=True)
    @click.option('--paciente-email', required=True)
    @click.option('--consentimento-confirmado', is_flag=True, required=True,
                  help='Confirma que a equipe verificou a autorização do paciente para o vínculo.')
    def link(admin_email, profissional_email, paciente_email, consentimento_confirmado):
        """Criar um vínculo verificado, sem expor uma lista pública de usuários."""
        if not consentimento_confirmado:
            raise click.ClickException('Confirme a autorização do paciente antes de criar o vínculo.')
        with db_manager.get_cursor() as cur:
            admin_id = administrator(cur, admin_email)
            cur.execute('''
                INSERT INTO profissional_pacientes (profissional_id, paciente_id)
                SELECT p.usuario_id, paciente.id FROM profissionais p
                JOIN usuarios profissional ON profissional.id = p.usuario_id
                CROSS JOIN usuarios paciente
                WHERE profissional.email = %s AND paciente.email = %s
                    AND p.ativo AND profissional.ativo AND profissional.role IN ('psicologo', 'medico')
                    AND paciente.role = 'paciente' AND paciente.ativo AND p.usuario_id <> paciente.id
                ON CONFLICT (profissional_id, paciente_id) DO UPDATE SET ativo = TRUE,
                    vinculado_em = CURRENT_TIMESTAMP, desvinculado_em = NULL
                    WHERE NOT profissional_pacientes.ativo RETURNING profissional_id, paciente_id
            ''', (profissional_email, paciente_email))
            relation = cur.fetchone()
            if not relation:
                raise click.ClickException('Vínculo já existente ou contas inválidas para vinculação.')
            AdminModel._write_audit(cur, admin_id, 'vinculo_criado', affected=relation[1],
                                   professional=relation[0], patient=relation[1], details={'origem': 'flask_cli'})
        db_manager.commit()
        click.echo('Paciente vinculado.')
