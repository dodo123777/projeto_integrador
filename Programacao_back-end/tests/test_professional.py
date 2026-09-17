"""Testes isolados: não acessam o banco configurado nem serviços externos."""
import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import bcrypt
import jwt
import psycopg2

from app import app
from auth import JWTManager
from config import Config
from controllers.professional_controller import professional_model
from models.professional import ProfessionalModel
from auth import user_model as auth_user_model


class ProfessionalRoutesTest(unittest.TestCase):
    def setUp(self):
        self.secret = patch.object(Config, 'SECRET_KEY', 'isolated-tests-only-not-a-production-secret')
        self.secret.start()
        self.addCleanup(self.secret.stop)
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.profile = {'id': 7, 'nome': 'Ana', 'email': 'ana@example.test', 'tipo': 'medico', 'registro': 'CRM teste', 'especialidade': None}
        self.access = {'id': 7, 'nome': 'Ana', 'email': 'ana@example.test', 'role': 'medico', 'ativo': True, 'auth_version': 0}
        self.access_patch = patch.object(auth_user_model, 'get_access_context', return_value=self.access)
        self.access_mock = self.access_patch.start()
        self.addCleanup(self.access_patch.stop)
        self.profile_patch = patch.object(professional_model, 'profile', return_value=self.profile)
        self.profile_mock = self.profile_patch.start()
        self.addCleanup(self.profile_patch.stop)
        self.headers = {'Authorization': 'Bearer ' + JWTManager.encode_token(7, 'ana@example.test')}

    def test_all_routes_require_valid_authentication(self):
        routes = [('GET', '/me'), ('GET', '/dashboard'), ('GET', '/pacientes'), ('GET', '/pacientes/12'), ('GET', '/consultas'), ('POST', '/consultas'), ('PATCH', '/consultas/1/status')]
        for method, route in routes:
            for headers in ({}, {'Authorization': 'Bearer invalid'}):
                with self.subTest(method=method, route=route, headers=headers):
                    response = self.client.open('/profissional' + route, method=method, headers=headers)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.profile_mock.assert_not_called()

    def test_expired_or_malformed_identity_denied(self):
        for payload in ({'id': 7, 'exp': datetime.now(timezone.utc) - timedelta(seconds=5)}, {'id': '7'}, {'id': True}, {'email': 'someone@example.test'}):
            token = jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')
            self.assertEqual(self.client.get('/profissional/me', headers={'Authorization': token}).status_code, 401)

    def test_patient_admin_and_revoked_professional_denied_on_all_routes(self):
        for profile in (None, {**self.profile, 'tipo': 'admin'}, {**self.profile, 'tipo': 'user'}):
            self.profile_mock.return_value = profile
            for method, route in [('GET', '/me'), ('GET', '/dashboard'), ('GET', '/pacientes'), ('GET', '/pacientes/12'), ('GET', '/consultas'), ('POST', '/consultas'), ('PATCH', '/consultas/1/status')]:
                with self.subTest(profile=profile, route=route):
                    self.assertEqual(self.client.open('/profissional' + route, method=method, headers=self.headers).status_code, 403)

    def test_medico_and_psicologo_allowed_without_sensitive_fields(self):
        for role in ('medico', 'psicologo'):
            self.profile_mock.return_value = {**self.profile, 'tipo': role}
            self.access_mock.return_value = {**self.access, 'role': role}
            response = self.client.get('/profissional/me', headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('senha', response.json)
        self.profile_mock.assert_called_with(7)

    def test_authorization_rechecked_when_access_revoked(self):
        self.assertEqual(self.client.get('/profissional/me', headers=self.headers).status_code, 200)
        self.profile_mock.return_value = None
        self.assertEqual(self.client.get('/profissional/me', headers=self.headers).status_code, 403)

    def test_patient_detail_checks_ownership_before_reading_appointments(self):
        with patch.object(professional_model, 'patients', return_value=[]) as patients, patch.object(professional_model, 'appointments') as appointments:
            response = self.client.get('/profissional/pacientes/26?profissional_id=8', headers=self.headers)
            self.assertEqual(response.status_code, 403)
            patients.assert_called_once_with(7, patient_id=26)
            appointments.assert_not_called()

    def test_patient_detail_returns_iso_dates_and_only_scoped_appointments(self):
        start = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
        with patch.object(professional_model, 'patients', return_value=[{'id': 12, 'nome': 'Paciente'}]), patch.object(professional_model, 'appointments', return_value=[{'inicio': start}]) as appointments:
            response = self.client.get('/profissional/pacientes/12', headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['consultas'][0]['inicio'], start.isoformat())
            appointments.assert_called_once_with(7, patient_id=12)

    def test_dashboard_and_search_use_authenticated_id(self):
        with patch.object(professional_model, 'dashboard', return_value={'resumo': {}, 'proximos': []}) as dashboard:
            self.assertEqual(self.client.get('/profissional/dashboard?profissional_id=8', headers=self.headers).status_code, 200)
            dashboard.assert_called_once_with(7)
        with patch.object(professional_model, 'patients', return_value=[]) as patients:
            self.assertEqual(self.client.get('/profissional/pacientes?busca=Ana', headers=self.headers).json, [])
            patients.assert_called_once_with(7, search='Ana')
        self.assertEqual(self.client.get('/profissional/pacientes?busca=' + 'a' * 121, headers=self.headers).status_code, 400)

    def test_date_validation_and_history(self):
        self.assertEqual(self.client.get('/profissional/consultas?data=2026-02-30', headers=self.headers).status_code, 400)
        with patch.object(professional_model, 'appointments', return_value=[]) as appointments:
            self.assertEqual(self.client.get('/profissional/consultas?data=2026-09-20&historico=1', headers=self.headers).status_code, 200)
            appointments.assert_called_once_with(7, day='2026-09-20', history=True)

    def appointment_data(self):
        return {'paciente_id': 12, 'tipo': 'Consulta médica', 'inicio': (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), 'profissional_id': 8}

    def test_create_appointment_ignores_spoofed_professional(self):
        with patch.object(professional_model, 'create_appointment', return_value=15) as create:
            response = self.client.post('/profissional/consultas', headers=self.headers, json=self.appointment_data())
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json, {'id': 15})
            self.assertEqual(create.call_args.args[0:2], (7, 12))

    def test_unlinked_patient_and_duplicate_slot(self):
        with patch.object(professional_model, 'create_appointment', return_value=None):
            self.assertEqual(self.client.post('/profissional/consultas', headers=self.headers, json=self.appointment_data()).status_code, 404)
        with patch.object(professional_model, 'create_appointment', side_effect=psycopg2.errors.UniqueViolation()):
            self.assertEqual(self.client.post('/profissional/consultas', headers=self.headers, json=self.appointment_data()).status_code, 409)

    def test_invalid_appointment_payloads_do_not_write(self):
        base = self.appointment_data()
        payloads = [[], {}, {**base, 'paciente_id': True}, {**base, 'paciente_id': -1}, {**base, 'tipo': 'Consulta psicológica'}, {**base, 'inicio': '2026-01-01'}, {**base, 'inicio': None}, {**base, 'inicio': '2020-01-01T12:00:00Z'}, {**base, 'inicio': '2030-01-01T12:00:00'}]
        with patch.object(professional_model, 'create_appointment') as create:
            for payload in payloads:
                with self.subTest(payload=payload):
                    self.assertEqual(self.client.post('/profissional/consultas', headers=self.headers, json=payload).status_code, 400)
            create.assert_not_called()

    def test_transition_scoped_and_conflicts(self):
        with patch.object(professional_model, 'update_status', return_value=True) as update:
            response = self.client.patch('/profissional/consultas/99/status', headers=self.headers, json={'status': 'finalizada', 'profissional_id': 8})
            self.assertEqual(response.status_code, 204)
            update.assert_called_once_with(7, 99, 'finalizada', ['em_atendimento'])
            update.return_value = False
            self.assertEqual(self.client.patch('/profissional/consultas/99/status', headers=self.headers, json={'status': 'confirmada'}).status_code, 409)
        for value in ('agendada', 'inventado', [], None):
            self.assertEqual(self.client.patch('/profissional/consultas/99/status', headers=self.headers, json={'status': value}).status_code, 400)

    def test_database_unavailable_returns_generic_error(self):
        self.profile_mock.side_effect = psycopg2.OperationalError('sensitive connection details')
        response = self.client.get('/profissional/me', headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('sensitive', response.get_data(as_text=True))

    def test_reset_cannot_take_over_professional_account(self):
        with patch('controllers.user_controller.user_model.update_password') as update:
            response = self.client.post('/esqueci_senha', json={'email': 'ana@example.test', 'nova_senha': 'attacker'})
            self.assertEqual(response.status_code, 403)
            update.assert_not_called()

    def test_registration_ignores_roles_and_legacy_login_still_returns_jwt(self):
        with patch('controllers.user_controller.user_model.create_user', return_value=(True, None)) as create:
            response = self.client.post('/registrar', json={'nome': 'Pessoa', 'email': 'p@example.test', 'senha': 'senha123', 'tipo': 'medico', 'role': 'admin'})
            self.assertEqual(response.status_code, 200)
            create.assert_called_once_with('Pessoa', 'p@example.test', 'senha123')
        password_hash = bcrypt.hashpw(b'senha123', bcrypt.gensalt()).decode()
        with patch('controllers.user_controller.user_model.get_user_by_email', return_value=(7, password_hash, 'paciente', True, 0)):
            response = self.client.post('/login', json={'email': 'p@example.test', 'senha': 'senha123'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(JWTManager.decode_token(response.json['token'])['id'], 7)

    def test_existing_health_tasks_and_chat_authentication(self):
        self.assertEqual(self.client.get('/').json, {'status': 'ok'})
        self.assertEqual(self.client.get('/tarefas').status_code, 401)
        self.assertEqual(self.client.post('/chat', json={'message': 'oi'}).status_code, 401)
        with patch('controllers.task_controller.task_model.list_tasks', return_value=[]) as tasks:
            self.assertEqual(self.client.get('/tarefas', headers=self.headers).json, [])
            tasks.assert_called_once_with(7, None)

    def test_auth_does_not_log_tokens(self):
        capture = io.StringIO()
        with redirect_stdout(capture):
            self.client.get('/profissional/me', headers=self.headers)
        self.assertNotIn(self.headers['Authorization'][7:30], capture.getvalue())


class ProfessionalQueriesTest(unittest.TestCase):
    """Verifica escopo e parametrização SQL; execução PostgreSQL é teste separado."""

    def setUp(self):
        self.model = ProfessionalModel()
        self.model.db = MagicMock()
        self.cursor = self.model.db.get_cursor.return_value.__enter__.return_value
        self.cursor.description = [('id',)]
        self.cursor.fetchall.return_value = []

    def test_queries_bind_professional_and_patient_ids(self):
        self.model.patients(7, patient_id=26, search="' OR TRUE --")
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('v.profissional_id = %s', sql)
        self.assertIn('c.profissional_id = v.profissional_id', sql)
        self.assertNotIn("' OR TRUE --", sql)
        self.assertEqual(params, (7, 26, 26, "' OR TRUE --"))
        self.model.appointments(7, patient_id=26)
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('c.profissional_id = %s', sql)
        self.assertEqual(params[:3], (7, 26, 26))

    def test_insert_requires_relationship_and_rolls_back_conflict(self):
        self.cursor.fetchone.return_value = None
        self.assertIsNone(self.model.create_appointment(7, 26, 'start', 'Retorno'))
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('FROM profissional_pacientes', sql)
        self.assertEqual(params, ('start', 'Retorno', 7, 26))
        self.cursor.execute.side_effect = psycopg2.errors.UniqueViolation()
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self.model.create_appointment(7, 26, 'start', 'Retorno')
        self.model.db.rollback.assert_called_once()

    def test_status_update_has_ownership_transition_and_start_time_checks(self):
        self.cursor.fetchone.return_value = None
        self.assertFalse(self.model.update_status(7, 99, 'em_atendimento', ['confirmada']))
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('profissional_id = %s AND status = ANY(%s)', sql)
        self.assertIn('inicio <= CURRENT_TIMESTAMP', sql)
        self.assertEqual(params, ('em_atendimento', 99, 7, ['confirmada'], 'em_atendimento'))


if __name__ == '__main__':
    unittest.main()
