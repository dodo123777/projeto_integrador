"""Bootstrap do primeiro administrador usando a autenticação existente."""
import click

from database import db_manager


def register_admin_commands(app):
    @app.cli.command('admin-criar-primeiro')
    @click.option('--email', required=True)
    @click.option('--confirmacao', required=True,
                  help='Digite exatamente: CRIAR PRIMEIRO ADMIN')
    def create_first_admin(email, confirmacao):
        """Promove uma conta existente somente quando ainda não há administrador."""
        if confirmacao != 'CRIAR PRIMEIRO ADMIN':
            raise click.ClickException('Confirmação inválida.')
        try:
            with db_manager.get_cursor() as cur:
                cur.execute('SELECT pg_advisory_xact_lock(72016001)')
                cur.execute("SELECT COUNT(*) FROM usuarios WHERE role = 'admin'")
                if cur.fetchone()[0] != 0:
                    raise click.ClickException('Já existe administrador. O bootstrap só cria o primeiro.')
                cur.execute('''
                    UPDATE usuarios SET role = 'admin'
                    WHERE lower(email) = lower(%s) AND ativo AND role = 'paciente'
                    RETURNING id
                ''', (email,))
                row = cur.fetchone()
                if not row or cur.rowcount != 1:
                    raise click.ClickException('Conta paciente ativa não encontrada.')
                cur.execute('''
                    INSERT INTO auditoria_admin (administrador_id, acao, usuario_afetado_id, detalhes)
                    VALUES (%s, 'primeiro_admin_criado_cli', %s, '{"origem":"flask_cli"}'::jsonb)
                ''', (row[0], row[0]))
            db_manager.commit()
        except click.ClickException:
            db_manager.rollback()
            raise
        except Exception:
            db_manager.rollback()
            raise
        click.echo('Primeiro administrador criado. Use o login normal da plataforma.')
