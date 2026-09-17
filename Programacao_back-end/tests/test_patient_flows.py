"""Contratos de tarefas e chat com banco e provedor de IA simulados."""
import unittest
from unittest.mock import MagicMock, patch

import requests

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
            ('GET', '/tarefas'), ('POST', '/tarefas'),
            ('DELETE', '/tarefas/1'), ('POST', '/tarefas/1/concluir'),
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
            self.assertEqual(response.status_code, 204)
            delete.assert_called_once_with(33, 12)

    def test_toggle_scopes_to_authenticated_patient(self):
        with patch.object(task_model, 'toggle_task', return_value=True) as toggle:
            response = self.client.post('/tarefas/33/concluir', headers=self.headers,
                                        json={'completed': True, 'usuario_id': 99})
            self.assertEqual(response.status_code, 204)
            toggle.assert_called_once_with(33, 12, True)

    def test_task_database_failure_returns_generic_error(self):
        with patch.object(task_model, 'add_task', side_effect=RuntimeError('private database detail')):
            response = self.client.post('/tarefas', headers=self.headers, json={'text': 'Estudar'})
            self.assertEqual(response.status_code, 500)
            self.assertNotIn('private database detail', response.get_data(as_text=True))

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


if __name__ == '__main__':
    unittest.main()
