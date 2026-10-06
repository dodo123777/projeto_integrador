"""Contratos de tarefas e chat com banco e provedor de IA simulados."""
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import requests
import psycopg2

from app import app
from auth import JWTManager, user_model as auth_user_model
from config import Config
from controllers.task_controller import task_model


class PatientFlowsTest(unittest.TestCase):
    def setUp(self):
        self.config = patch.multiple(
            Config, SECRET_KEY='patient-tests-only',
            GEMINI_API_KEY='test-key', GEMINI_MODEL='test-model',
        )
        self.config.start()
        self.addCleanup(self.config.stop)
        self.access = patch.object(auth_user_model, 'get_access_context', return_value={
            'id': 12, 'nome': 'Paciente', 'email': 'patient@example.test',
            'role': 'paciente', 'ativo': True, 'auth_version': 0,
        })
        self.access.start()
        self.addCleanup(self.access.stop)
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.headers = {'Authorization': 'Bearer ' + JWTManager.encode_token(12, 'patient@example.test')}

    def test_tasks_and_chat_reject_missing_authentication(self):
        for method, path in [
            ('GET', '/tarefas'), ('GET', '/tarefas/semana'), ('POST', '/tarefas'),
            ('DELETE', '/tarefas/1'), ('PUT', '/tarefas/1'), ('POST', '/tarefas/1/concluir'),
            ('GET', '/tarefas/estatisticas'), ('GET', '/tarefas_protegidas'),
            ('POST', '/chat'),
        ]:
            with self.subTest(path=path):
                response = self.client.open(path, method=method, json={})
                self.assertEqual(response.status_code, 401)

    def test_list_and_statistics_scope_to_authenticated_patient(self):
        with patch.object(task_model, 'list_tasks', return_value=[]) as listing:
            response = self.client.get('/tarefas?date=2026-09-17&usuario_id=99', headers=self.headers)
            self.assertEqual(response.status_code, 200)
            listing.assert_called_once_with(12, '2026-09-17')
        with patch.object(task_model, 'get_dashboard_stats', return_value={'summary': {}}) as stats:
            response = self.client.get('/tarefas/estatisticas?date=2026-09-17&usuario_id=99', headers=self.headers)
            self.assertEqual(response.status_code, 200)
            stats.assert_called_once_with(12, '2026-09-17')

    def test_week_is_bounded_to_seven_days_and_authenticated_owner(self):
        rows = [{'id': 33, 'date': '2028-02-29', 'text': 'Ler', 'time': '09:00', 'deadline': '10:00', 'completed': True}]
        with patch.object(task_model, 'list_week', return_value=rows) as listing:
            response = self.client.get('/tarefas/semana?date=2028-03-01&usuario_id=99', headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            listing.assert_called_once_with(12, date(2028, 2, 28), date(2028, 3, 5))
            self.assertEqual((response.json['start'], response.json['end']), ('2028-02-28', '2028-03-05'))
            self.assertEqual(len(response.json['days']), 7)
            self.assertEqual(response.json['days'][1]['tasks'], rows)
            self.assertEqual(response.json['days'][2]['tasks'], [])

    def test_week_rejects_invalid_or_overflowing_dates_without_query(self):
        with patch.object(task_model, 'list_week') as listing:
            for value in ('2026-02-30', '', '2026-1-1', '9999-12-31'):
                self.assertEqual(self.client.get('/tarefas/semana?date=' + value, headers=self.headers).status_code, 400)
            listing.assert_not_called()
        with patch.object(task_model, 'list_week', return_value=[]) as listing:
            response = self.client.get('/tarefas/semana?date=2027-01-01', headers=self.headers)
            self.assertEqual(response.json['start'], '2026-12-28')
            self.assertEqual(response.json['end'], '2027-01-03')

    def test_create_task_ignores_patient_identity_in_payload(self):
        payload = {'text': 'Estudar', 'date': '2026-09-17', 'time': '10:00', 'deadline': '11:00', 'usuario_id': 99}
        with patch.object(task_model, 'add_task', return_value=33) as create:
            response = self.client.post('/tarefas', headers=self.headers, json=payload)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json, {'id': 33})
            create.assert_called_once_with(12, 'Estudar', '2026-09-17', '10:00', '11:00')

    def test_delete_cannot_change_another_patients_task(self):
        with patch.object(task_model, 'delete_task', return_value=False) as delete:
            response = self.client.delete('/tarefas/33?usuario_id=99', headers=self.headers)
            self.assertEqual(response.status_code, 404)
            delete.assert_called_once_with(33, 12)

    def test_toggle_scopes_to_authenticated_patient(self):
        with patch.object(task_model, 'toggle_task', return_value=True) as toggle:
            response = self.client.post('/tarefas/33/concluir', headers=self.headers,
                                        json={'completed': True, 'usuario_id': 99})
            self.assertEqual(response.status_code, 204)
            toggle.assert_called_once_with(33, 12, True)

    def test_task_database_failure_returns_generic_error(self):
        with patch.object(task_model, 'add_task', side_effect=psycopg2.OperationalError('private database detail')):
            response = self.client.post('/tarefas', headers=self.headers, json={
                'text': 'Estudar', 'date': '2026-09-17', 'time': '10:00', 'deadline': '11:00',
            })
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private database detail', response.get_data(as_text=True))

    def test_edit_task_scopes_to_owner_and_preserves_completion(self):
        payload = {'text': ' Ler ', 'date': '2026-10-06', 'time': '09:00', 'deadline': '10:00', 'usuario_id': 99, 'completed': False}
        with patch.object(task_model, 'update_task', return_value=True) as update:
            response = self.client.put('/tarefas/33', headers=self.headers, json=payload)
            self.assertEqual(response.status_code, 204)
            update.assert_called_once_with(33, 12, 'Ler', '2026-10-06', '09:00', '10:00')
            update.return_value = False
            self.assertEqual(self.client.put('/tarefas/33', headers=self.headers, json=payload).status_code, 404)

    def test_repetition_across_month_and_leap_year(self):
        cases = [
            ('2028-02-28', 'daily', '2028-03-01', ['2028-02-28', '2028-02-29', '2028-03-01']),
            ('2026-12-28', 'weekly', '2027-01-12', ['2026-12-28', '2027-01-04', '2027-01-11']),
        ]
        for start, frequency, end, dates in cases:
            with self.subTest(frequency=frequency), patch.object(task_model, 'add_recurring_tasks', return_value=[33, 34, 35]) as create:
                response = self.client.post('/tarefas', headers=self.headers, json={
                    'text': 'Ler', 'date': start, 'time': '09:00', 'deadline': '10:00',
                    'repeat': {'frequency': frequency, 'until': end}, 'usuario_id': 99,
                })
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json, {'id': 33, 'ids': [33, 34, 35], 'created': 3})
                create.assert_called_once_with(12, 'Ler', dates, '09:00', '10:00')

    def test_invalid_tasks_and_repetitions_never_write(self):
        base = {'text': 'Ler', 'date': '2026-10-05', 'time': '09:00', 'deadline': '10:00'}
        payloads = [None, [], {}, {**base, 'text': '  '}, {**base, 'text': 'x' * 501},
                    {**base, 'date': '2026-02-30'}, {**base, 'date': []},
                    {**base, 'time': '24:00'}, {**base, 'deadline': '08:00'}]
        payloads += [{**base, 'repeat': repeat} for repeat in [
            [], {}, {'frequency': 'monthly', 'until': '2026-11-01'},
            {'frequency': 'daily', 'until': '2026-10-04'},
            {'frequency': 'daily', 'until': '2027-01-03'},  # 91 occurrences
            {'frequency': 'weekly', 'until': '2027-10-06'},  # beyond one year
        ]]
        with patch.object(task_model, 'add_task') as create, patch.object(task_model, 'add_recurring_tasks') as repeat, patch.object(task_model, 'update_task') as update:
            for payload in payloads:
                with self.subTest(payload=payload):
                    self.assertEqual(self.client.post('/tarefas', headers=self.headers, json=payload).status_code, 400)
                    self.assertEqual(self.client.put('/tarefas/33', headers=self.headers, json=payload).status_code, 400)
            create.assert_not_called()
            repeat.assert_not_called()
            update.assert_not_called()

    def test_bad_dates_and_completion_payloads_are_rejected(self):
        for path in ('/tarefas', '/tarefas/estatisticas'):
            self.assertEqual(self.client.get(path + '?date=2026-02-30', headers=self.headers).status_code, 400)
        with patch.object(task_model, 'toggle_task') as toggle:
            for payload in ([], {}, {'completed': 'false'}, {'completed': 1}):
                self.assertEqual(self.client.post('/tarefas/33/concluir', headers=self.headers, json=payload).status_code, 400)
            toggle.assert_not_called()
        with patch.object(task_model, 'toggle_task', return_value=False):
            self.assertEqual(self.client.post('/tarefas/33/concluir', headers=self.headers, json={'completed': True}).status_code, 404)

    def test_task_database_outage_is_503_for_all_operations(self):
        operations = [('GET', '/tarefas', 'list_tasks', None),
                      ('GET', '/tarefas/estatisticas', 'get_dashboard_stats', None),
                      ('DELETE', '/tarefas/33', 'delete_task', None),
                      ('PUT', '/tarefas/33', 'update_task', {'text': 'Ler', 'date': '2026-10-05', 'time': '09:00', 'deadline': '10:00'}),
                      ('POST', '/tarefas/33/concluir', 'toggle_task', {'completed': True})]
        for method, path, operation, payload in operations:
            with self.subTest(path=path), patch.object(task_model, operation, side_effect=psycopg2.OperationalError('private detail')):
                response = self.client.open(path, method=method, headers=self.headers, json=payload)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertNotIn('private detail', response.get_data(as_text=True))

    def test_chat_empty_message_does_not_call_provider(self):
        with patch('controllers.chat_controller.requests.post') as provider:
            response = self.client.post('/chat', headers=self.headers, json={'message': '  '})
            self.assertEqual(response.status_code, 400)
            provider.assert_not_called()

    def test_chat_returns_answer_and_omits_thought_parts(self):
        provider_response = MagicMock(ok=True)
        provider_response.json.return_value = {'candidates': [{'content': {'parts': [
            {'thought': True, 'text': 'internal reasoning'}, {'text': 'Organize uma tarefa por vez.'},
        ]}}]}
        with patch('controllers.chat_controller.requests.post', return_value=provider_response):
            response = self.client.post('/chat', headers=self.headers, json={'message': 'Como organizar tarefas?'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {'reply': 'Organize uma tarefa por vez.'})

    def test_chat_timeout_and_network_error(self):
        for error, status in [(requests.Timeout(), 504), (requests.ConnectionError(), 502)]:
            with self.subTest(status=status), patch('controllers.chat_controller.requests.post', side_effect=error):
                response = self.client.post('/chat', headers=self.headers, json={'message': 'Teste'})
                self.assertEqual(response.status_code, status)

    def test_chat_invalid_provider_json_and_empty_reply(self):
        invalid_json = MagicMock(ok=True)
        invalid_json.json.side_effect = ValueError('invalid json')
        empty_reply = MagicMock(ok=True)
        empty_reply.json.return_value = {'candidates': []}
        for provider_response in [invalid_json, empty_reply]:
            with patch('controllers.chat_controller.requests.post', return_value=provider_response):
                response = self.client.post('/chat', headers=self.headers, json={'message': 'Teste'})
                self.assertEqual(response.status_code, 502)

    def test_chat_provider_failure_is_not_success(self):
        provider_response = MagicMock(ok=False)
        provider_response.json.return_value = {'error': {'message': 'Quota exceeded'}}
        with patch('controllers.chat_controller.requests.post', return_value=provider_response):
            response = self.client.post('/chat', headers=self.headers, json={'message': 'Teste'})
            self.assertEqual(response.status_code, 502)

    def test_cors_accepts_local_admin_delete_preflight(self):
        response = self.client.options('/admin/vinculos/7/12', headers={
            'Origin': 'http://localhost:5500',
            'Access-Control-Request-Method': 'DELETE',
            'Access-Control-Request-Headers': 'Authorization, Content-Type',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'http://localhost:5500')
        self.assertIn('DELETE', response.headers['Access-Control-Allow-Methods'])
        response = self.client.options('/tarefas/33', headers={
            'Origin': 'http://localhost:5500',
            'Access-Control-Request-Method': 'PUT',
            'Access-Control-Request-Headers': 'Authorization, Content-Type',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'http://localhost:5500')
        self.assertIn('PUT', response.headers['Access-Control-Allow-Methods'])


if __name__ == '__main__':
    unittest.main()
