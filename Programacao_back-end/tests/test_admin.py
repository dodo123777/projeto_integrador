"""Autorização administrativa isolada, sem banco local ou Supabase."""
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import psycopg2
import bcrypt
import jwt
from datetime import timedelta

from app import app
from auth import JWTManager, user_model as auth_user_model
from config import Config
from controllers.admin_controller import admin_model
from controllers.professional_controller import professional_model
from models.admin import AdminModel


class AdminRoutesTest(unittest.TestCase):
    def setUp(self):
        self.secret = patch.object(Config, 'SECRET_KEY', 'admin-tests-only-not-production')
        self.secret.start()
        self.addCleanup(self.secret.stop)
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.users = {
            1: {'id': 1, 'nome': 'Admin', 'email': 'admin@example.test', 'role': 'admin', 'ativo': True},
            7: {'id': 7, 'nome': 'Psi', 'email': 'psi@example.test', 'role': 'psicologo', 'ativo': True},
            12: {'id': 12, 'nome': 'Paciente', 'email': 'pac@example.test', 'role': 'paciente', 'ativo': True},
            13: {'id': 13, 'nome': 'Bloqueado', 'email': 'off@example.test', 'role': 'paciente', 'ativo': False},
        }
        for user in self.users.values():
            user['auth_version'] = 0
        self.access_patch = patch.object(auth_user_model, 'get_access_context', side_effect=lambda user_id: self.users.get(user_id))
        self.access_patch.start()
        self.addCleanup(self.access_patch.stop)
        self.tokens = {user_id: {'Authorization': 'Bearer ' + JWTManager.encode_token(user_id, user['email'])}
                       for user_id, user in self.users.items()}

    def test_patient_and_psychologist_denied_on_every_admin_route(self):
        routes = [
            ('GET', '/admin', None), ('GET', '/admin/me', None), ('GET', '/admin/dashboard', None),
            ('GET', '/admin/usuarios', None), ('GET', '/admin/usuarios/12', None),
            ('GET', '/admin/usuarios/12/vinculos', None),
            ('POST', '/admin/usuarios/12/promover-psicologo', {'role': 'admin', 'confirmacao': True}),
            ('PATCH', '/admin/usuarios/12/status', {'ativo': False, 'confirmacao': True}),
            ('GET', '/admin/psicologos', None), ('GET', '/admin/psicologos/7', None),
            ('PATCH', '/admin/psicologos/7/perfil', {'registro': 'CRP 1', 'ativo': True, 'confirmacao': True}),
            ('GET', '/admin/vinculos', None),
            ('POST', '/admin/vinculos', {'psicologo_id': 7, 'paciente_id': 12, 'confirmacao': True}),
            ('DELETE', '/admin/vinculos/7/12', {'confirmacao': True}), ('GET', '/admin/auditoria', None),
        ]
        for user_id in (7, 12):
            for method, route, data in routes:
                with self.subTest(user=user_id, route=route):
                    response = self.client.open(route, method=method, headers=self.tokens[user_id], json=data)
                    self.assertEqual(response.status_code, 403)

    def test_invalid_or_blocked_session_denied_before_admin_model(self):
        with patch.object(admin_model, 'dashboard') as dashboard:
            self.assertEqual(self.client.get('/admin/dashboard').status_code, 401)
            self.assertEqual(self.client.get('/admin/dashboard', headers=self.tokens[13]).status_code, 401)
            dashboard.assert_not_called()

    def test_admin_can_read_dashboard_users_search_and_details(self):
        self.assertEqual(self.client.get('/admin', headers=self.tokens[1]).status_code, 200)
        with patch.object(admin_model, 'dashboard', return_value={'resumo': {}, 'auditoria': []}) as dashboard:
            self.assertEqual(self.client.get('/admin/dashboard', headers=self.tokens[1]).status_code, 200)
            dashboard.assert_called_once_with()
        result = {'itens': [], 'pagina': 2, 'por_pagina': 10, 'total': 0, 'paginas': 0}
        with patch.object(admin_model, 'users', return_value=result) as users:
            response = self.client.get('/admin/usuarios?busca=ana&pagina=2&por_pagina=10', headers=self.tokens[1])
            self.assertEqual(response.status_code, 200)
            users.assert_called_once_with('ana', None, 2, 10)
        with patch.object(admin_model, 'user', return_value={**self.users[12], 'criado_em': datetime.now(timezone.utc)}) as user:
            self.assertEqual(self.client.get('/admin/usuarios/12', headers=self.tokens[1]).status_code, 200)
            user.assert_called_once_with(12)

    def test_admin_promotes_blocks_reactivates_and_manages_links(self):
        with patch.object(admin_model, 'promote_psychologist', return_value=True) as promote:
            response = self.client.post('/admin/usuarios/12/promover-psicologo', headers=self.tokens[1],
                                        json={'registro': 'CRP 123', 'especialidade': 'Clínica', 'confirmacao': True,
                                              'role': 'admin', 'user_type': 'admin'})
            self.assertEqual(response.status_code, 200)
            promote.assert_called_once_with(1, 12, 'CRP 123', 'Clínica')
        with patch.object(admin_model, 'set_user_active', return_value=True) as set_active:
            self.assertEqual(self.client.patch('/admin/usuarios/12/status', headers=self.tokens[1],
                                               json={'ativo': False, 'confirmacao': True, 'role': 'admin'}).status_code, 200)
            set_active.assert_called_once_with(1, 12, False)
        with patch.object(admin_model, 'create_link', return_value=True) as create:
            self.assertEqual(self.client.post('/admin/vinculos', headers=self.tokens[1],
                                              json={'psicologo_id': 7, 'paciente_id': 12, 'confirmacao': True,
                                                    'role': 'admin'}).status_code, 201)
            create.assert_called_once_with(1, 7, 12)
        with patch.object(admin_model, 'remove_link', return_value=True) as remove:
            self.assertEqual(self.client.delete('/admin/vinculos/7/12', headers=self.tokens[1],
                                                json={'confirmacao': True}).status_code, 200)
            remove.assert_called_once_with(1, 7, 12)

    def test_sensitive_operations_require_explicit_confirmation(self):
        cases = [
            ('POST', '/admin/usuarios/12/promover-psicologo', {'registro': 'CRP 1'}),
            ('PATCH', '/admin/usuarios/12/status', {'ativo': False}),
            ('POST', '/admin/vinculos', {'psicologo_id': 7, 'paciente_id': 12}),
            ('DELETE', '/admin/vinculos/7/12', {}),
        ]
        for method, route, data in cases:
            with self.subTest(route=route):
                self.assertEqual(self.client.open(route, method=method, headers=self.tokens[1], json=data).status_code, 400)

    def test_admin_cannot_block_self_and_last_admin_is_protected(self):
        with patch.object(admin_model, 'set_user_active') as status:
            self.assertEqual(self.client.patch('/admin/usuarios/1/status', headers=self.tokens[1],
                                               json={'ativo': False, 'confirmacao': True}).status_code, 409)
            status.assert_not_called()
        with patch.object(admin_model, 'set_user_active', return_value=False):
            self.assertEqual(self.client.patch('/admin/usuarios/99/status', headers=self.tokens[1],
                                               json={'ativo': False, 'confirmacao': True}).status_code, 409)

    def test_role_and_user_type_fields_never_grant_privileges(self):
        with patch('controllers.user_controller.user_model.create_user', return_value=(True, None)) as create:
            response = self.client.post('/registrar', json={'nome': 'X', 'email': 'x@example.test', 'senha': '123456',
                                                            'role': 'admin', 'user_type': 'admin', 'tipo': 'psicologo'})
            self.assertEqual(response.status_code, 200)
            create.assert_called_once_with('X', 'x@example.test', '123456')
        self.assertEqual(self.client.post('/admin/vinculos', headers=self.tokens[12],
                                          json={'role': 'admin', 'psicologo_id': 7, 'paciente_id': 12,
                                                'confirmacao': True}).status_code, 403)

    def test_link_removal_revokes_same_psychologist_token_immediately(self):
        link = {'active': True}
        profile = {'id': 7, 'nome': 'Psi', 'email': 'psi@example.test', 'tipo': 'psicologo',
                   'registro': 'CRP 1', 'especialidade': None}
        patient = {'id': 12, 'nome': 'Paciente', 'ultimo_atendimento': None, 'proximo_atendimento': None}
        with patch.object(professional_model, 'profile', return_value=profile), \
             patch.object(professional_model, 'patients', side_effect=lambda professional_id, patient_id=None, search='': [patient] if link['active'] and patient_id == 12 else []), \
             patch.object(professional_model, 'appointments', return_value=[]), \
             patch.object(professional_model, 'update_status', side_effect=lambda *args: link['active']), \
             patch.object(admin_model, 'remove_link', side_effect=lambda admin_id, psychologist_id, patient_id: link.update(active=False) is None):
            self.assertEqual(self.client.get('/profissional/pacientes/12', headers=self.tokens[7]).status_code, 200)
            self.assertEqual(self.client.delete('/admin/vinculos/7/12', headers=self.tokens[1],
                                                json={'confirmacao': True}).status_code, 200)
            self.assertEqual(self.client.get('/profissional/pacientes/12', headers=self.tokens[7]).status_code, 403)
            self.assertEqual(self.client.patch('/profissional/consultas/5/status', headers=self.tokens[7], json={'status': 'confirmada'}).status_code, 409)

    def test_database_errors_are_generic(self):
        with patch.object(admin_model, 'dashboard', side_effect=psycopg2.OperationalError('secret host')):
            response = self.client.get('/admin/dashboard', headers=self.tokens[1])
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('secret host', response.get_data(as_text=True))

    def test_login_uses_one_authentication_and_database_destination_for_every_role(self):
        password_hash = bcrypt.hashpw(b'test-password', bcrypt.gensalt()).decode()
        for role, destination in [('paciente', 'index.html'), ('psicologo', 'profissional.html'), ('admin', 'admin.html')]:
            with self.subTest(role=role), patch('controllers.user_controller.user_model.get_user_by_email', return_value=(12, password_hash, role, True, 3)):
                response = self.client.post('/login', json={'email': 'x@example.test', 'senha': 'test-password', 'role': 'admin'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['destino'], destination)
                payload = JWTManager.decode_token(response.json['token'])
                self.assertNotIn('role', payload)
                self.assertNotIn('pacientes', payload)
                self.assertEqual(payload['ver'], 3)
        with patch('controllers.user_controller.user_model.get_user_by_email', return_value=(12, password_hash, 'admin', False, 3)):
            self.assertEqual(self.client.post('/login', json={'email': 'x@example.test', 'senha': 'test-password'}).status_code, 401)

    def test_block_and_reactivate_does_not_restore_old_tokens(self):
        def set_active(admin_id, user_id, active):
            self.users[user_id]['ativo'] = active
            if not active:
                self.users[user_id]['auth_version'] += 1
            return True
        with patch.object(admin_model, 'set_user_active', side_effect=set_active):
            self.assertEqual(self.client.get('/sessao', headers=self.tokens[12]).status_code, 200)
            self.assertEqual(self.client.patch('/admin/usuarios/12/status', headers=self.tokens[1], json={'ativo': False, 'confirmacao': True}).status_code, 200)
            for method, route in [('GET', '/sessao'), ('GET', '/tarefas'), ('GET', '/tarefas/estatisticas'), ('POST', '/chat'), ('GET', '/profissional/me')]:
                with self.subTest(route=route):
                    self.assertEqual(self.client.open(route, method=method, headers=self.tokens[12]).status_code, 401)
            self.assertEqual(self.client.patch('/admin/usuarios/12/status', headers=self.tokens[1], json={'ativo': True, 'confirmacao': True}).status_code, 200)
            self.assertEqual(self.client.get('/sessao', headers=self.tokens[12]).status_code, 401)
            fresh = {'Authorization': JWTManager.encode_token(12, self.users[12]['email'], 1)}
            self.assertEqual(self.client.get('/sessao', headers=fresh).status_code, 200)

    def test_current_database_role_overrides_any_token_role_claim(self):
        token = jwt.encode({'id': 12, 'role': 'admin', 'ver': 0, 'exp': datetime.now(timezone.utc) + timedelta(hours=1)}, Config.SECRET_KEY, algorithm='HS256')
        self.assertEqual(self.client.get('/admin/me', headers={'Authorization': token}).status_code, 403)
        self.assertEqual(self.client.get('/admin/me', headers=self.tokens[1]).status_code, 200)
        self.users[1]['role'] = 'paciente'
        self.assertEqual(self.client.get('/admin/me', headers=self.tokens[1]).status_code, 403)

    def test_malformed_inputs_and_pagination_rejected(self):
        for query in ('pagina=0', 'por_pagina=101', 'pagina=x', 'role=superadmin'):
            self.assertEqual(self.client.get('/admin/usuarios?' + query, headers=self.tokens[1]).status_code, 400)
        for data in ([], {'registro': [], 'confirmacao': True}, {'registro': 'CRP 1', 'especialidade': None, 'confirmacao': True}):
            self.assertEqual(self.client.post('/admin/usuarios/12/promover-psicologo', headers=self.tokens[1], json=data).status_code, 400)
        for route in ('/login', '/registrar'):
            self.assertEqual(self.client.post(route, json=['invalid']).status_code, 400)

    def test_admin_reads_related_links_and_updates_existing_professional_profile(self):
        with patch.object(admin_model, 'related_links', return_value=[]) as links:
            self.assertEqual(self.client.get('/admin/usuarios/12/vinculos', headers=self.tokens[1]).status_code, 200)
            links.assert_called_once_with(12)
        with patch.object(admin_model, 'update_psychologist', return_value=True) as update:
            response = self.client.patch('/admin/psicologos/7/perfil', headers=self.tokens[1],
                                         json={'registro': 'CRP 2', 'especialidade': 'Clínica', 'ativo': False, 'confirmacao': True})
            self.assertEqual(response.status_code, 200)
            update.assert_called_once_with(1, 7, 'CRP 2', 'Clínica', False)


class AdminQueriesTest(unittest.TestCase):
    def setUp(self):
        self.model = AdminModel()
        self.model.db = MagicMock()
        self.cursor = self.model.db.get_cursor.return_value.__enter__.return_value

    def test_link_is_soft_deleted_and_audited_in_same_transaction(self):
        self.cursor.fetchone.return_value = (12,)
        self.assertTrue(self.model.remove_link(1, 7, 12))
        calls = self.cursor.execute.call_args_list
        self.assertIn('SET ativo = FALSE', calls[0].args[0])
        self.assertEqual(calls[0].args[1], (7, 12))
        self.assertIn('INSERT INTO auditoria_admin', calls[1].args[0])
        self.model.db.commit.assert_called_once()

    def test_link_creation_checks_current_roles_and_active_status(self):
        self.cursor.fetchone.return_value = (12,)
        self.assertTrue(self.model.create_link(1, 7, 12))
        sql, params = self.cursor.execute.call_args_list[0].args
        self.assertIn("psi.role = 'psicologo'", sql)
        self.assertIn("pac.role = 'paciente'", sql)
        self.assertIn('psi.ativo', sql)
        self.assertIn('pac.ativo', sql)
        self.assertEqual(params, (7, 12))

    def test_promotion_updates_same_user_and_writes_audit(self):
        self.cursor.fetchone.return_value = (12,)
        self.assertTrue(self.model.promote_psychologist(1, 12, 'CRP 1', 'Clínica'))
        calls = self.cursor.execute.call_args_list
        self.assertIn("UPDATE usuarios SET role = 'psicologo'", calls[0].args[0])
        self.assertEqual(calls[0].args[1], ('CRP 1', 'Clínica', 12))
        self.assertIn('perfil_profissional_ativo = TRUE', calls[0].args[0])
        self.assertIn('INSERT INTO auditoria_admin', calls[1].args[0])
        self.assertEqual(len(calls), 2)

    def test_profile_edit_updates_existing_user_and_audits_together(self):
        self.cursor.fetchone.return_value = (7,)
        self.assertTrue(self.model.update_psychologist(1, 7, 'CRP 7', 'Clínica', False))
        calls = self.cursor.execute.call_args_list
        self.assertIn('UPDATE usuarios SET registro', calls[0].args[0])
        self.assertIn("role = 'psicologo'", calls[0].args[0])
        self.assertEqual(calls[0].args[1], ('CRP 7', 'Clínica', False, 7))
        self.assertIn('INSERT INTO auditoria_admin', calls[1].args[0])
        self.assertEqual(len(calls), 2)
        self.model.db.commit.assert_called_once()

    def test_audit_failure_rolls_back_administrative_change(self):
        self.cursor.fetchone.return_value = (12,)
        self.cursor.execute.side_effect = [None, psycopg2.OperationalError('audit unavailable')]
        with self.assertRaises(psycopg2.OperationalError):
            self.model.remove_link(1, 7, 12)
        self.model.db.rollback.assert_called_once()
        self.model.db.commit.assert_not_called()

    def test_block_serializes_admin_protection_and_invalidates_sessions(self):
        self.cursor.fetchone.return_value = (12,)
        self.assertTrue(self.model.set_user_active(1, 12, False))
        calls = self.cursor.execute.call_args_list
        self.assertIn('FOR UPDATE', calls[0].args[0])
        self.assertIn('auth_version = auth_version +', calls[1].args[0])
        self.assertIn("COUNT(*) FROM usuarios WHERE role = 'admin' AND ativo", calls[1].args[0])


class AdminBootstrapTest(unittest.TestCase):
    def test_first_admin_uses_existing_user_and_records_audit(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(0,), (12,)]
        cursor.rowcount = 1
        with patch('admin_commands.db_manager.get_cursor') as get_cursor, patch('admin_commands.db_manager.commit') as commit:
            get_cursor.return_value.__enter__.return_value = cursor
            result = app.test_cli_runner().invoke(args=['admin-criar-primeiro', '--email', 'x@example.test', '--confirmacao', 'CRIAR PRIMEIRO ADMIN'])
            self.assertEqual(result.exit_code, 0, result.output)
            sqls = [call.args[0] for call in cursor.execute.call_args_list]
            self.assertTrue(any('UPDATE usuarios SET role' in sql for sql in sqls))
            self.assertTrue(any('INSERT INTO auditoria_admin' in sql for sql in sqls))
            commit.assert_called_once()

    def test_bootstrap_refuses_when_an_admin_already_exists(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        with patch('admin_commands.db_manager.get_cursor') as get_cursor, patch('admin_commands.db_manager.commit') as commit:
            get_cursor.return_value.__enter__.return_value = cursor
            result = app.test_cli_runner().invoke(args=['admin-criar-primeiro', '--email', 'x@example.test', '--confirmacao', 'CRIAR PRIMEIRO ADMIN'])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn('Já existe administrador', result.output)
            commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
