"""Transações de repetição, escopo de edição e diagnóstico sem banco real."""
import threading
import unittest
from datetime import date, time
from unittest.mock import MagicMock, patch

import psycopg2

from app import app
from database import DatabaseManager, db_manager
from models.task import TaskModel


class TaskStorageTest(unittest.TestCase):
    def setUp(self):
        self.model = TaskModel()
        self.model.db = MagicMock()
        self.cursor = self.model.db.get_cursor.return_value.__enter__.return_value

    def test_repetition_commits_all_occurrences_once(self):
        self.cursor.fetchone.side_effect = [(41,), (42,), (43,)]
        dates = ['2026-10-05', '2026-10-06', '2026-10-07']
        self.assertEqual(self.model.add_recurring_tasks(12, 'Ler', dates, '09:00', '10:00'), [41, 42, 43])
        self.assertEqual([call.args[1] for call in self.cursor.execute.call_args_list], [
            (12, day, 'Ler', '09:00', '10:00', False) for day in dates
        ])
        self.model.db.commit.assert_called_once()
        self.model.db.rollback.assert_not_called()

    def test_week_query_is_bounded_scoped_and_serializes_dates(self):
        self.cursor.fetchall.return_value = [(41, 'Ler', time(9), time(10), False, date(2026, 10, 6))]
        tasks = self.model.list_week(12, date(2026, 10, 5), date(2026, 10, 11))
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('usuario_id = %s AND data BETWEEN %s AND %s', sql)
        self.assertEqual(params, (12, date(2026, 10, 5), date(2026, 10, 11)))
        self.assertEqual(tasks[0]['date'], '2026-10-06')
        self.assertEqual(tasks[0]['time'], '09:00:00')

    def test_failure_in_later_occurrence_rolls_back_everything(self):
        self.cursor.execute.side_effect = [None, psycopg2.OperationalError()]
        self.cursor.fetchone.return_value = (41,)
        with self.assertRaises(psycopg2.OperationalError):
            self.model.add_recurring_tasks(12, 'Ler', ['2026-10-05', '2026-10-06'], '09:00', '10:00')
        self.model.db.commit.assert_not_called()
        self.model.db.rollback.assert_called_once()

    def test_edit_is_scoped_and_does_not_reset_completion(self):
        self.cursor.rowcount = 1
        self.assertTrue(self.model.update_task(41, 12, 'Novo texto', '2026-10-07', '09:00', '10:00'))
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('WHERE id = %s AND usuario_id = %s', sql)
        self.assertNotIn('concluida', sql)
        self.assertEqual(params, ('Novo texto', '2026-10-07', '09:00', '10:00', 41, 12))
        self.cursor.rowcount = 0
        self.assertFalse(self.model.update_task(41, 99, 'Outro usuário', '2026-10-07', '09:00', '10:00'))


class DatabaseHealthTest(unittest.TestCase):
    def setUp(self):
        self.manager = object.__new__(DatabaseManager)
        self.manager._local = threading.local()
        self.client = app.test_client()

    def test_new_connection_failure_is_bounded_and_not_retried(self):
        with patch('database.psycopg2.connect', side_effect=psycopg2.OperationalError('private credentials')) as connect:
            with self.assertLogs('database', level='ERROR') as logs, self.assertRaises(psycopg2.OperationalError):
                self.manager.get_cursor()
            connect.assert_called_once()
            self.assertEqual(connect.call_args.kwargs['connect_timeout'], 8)
            self.assertNotIn('private credentials', ' '.join(logs.output))

    def test_stale_connection_is_closed_and_reconnected_once(self):
        stale, fresh = MagicMock(closed=False), MagicMock(closed=False)
        stale.cursor.return_value.execute.side_effect = psycopg2.OperationalError()
        self.manager.conn = stale
        with patch('database.psycopg2.connect', return_value=fresh) as connect:
            self.assertIs(self.manager.get_cursor(), fresh.cursor.return_value)
            stale.cursor.return_value.close.assert_called_once()
            stale.close.assert_called_once()
            connect.assert_called_once()
            fresh.cursor.return_value.execute.assert_called_once_with('SELECT 1')
        self.manager.close()

    def test_ready_reports_database_health_without_credentials(self):
        with patch.object(db_manager, 'get_cursor') as cursor:
            cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
            response = self.client.get('/health/ready')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {'status': 'ok', 'api': 'ok', 'database': 'ok'})
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        with patch.object(db_manager, 'get_cursor', side_effect=psycopg2.OperationalError('private credentials')):
            response = self.client.get('/health/ready')
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json['api'], 'ok')
            self.assertEqual(response.json['database'], 'unavailable')
            self.assertNotIn('private credentials', response.get_data(as_text=True))
        self.assertEqual(self.client.get('/').json, {'status': 'ok'})


if __name__ == '__main__':
    unittest.main()
