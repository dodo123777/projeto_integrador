from datetime import date, datetime, timedelta

from database import db_manager

class TaskModel:
    def __init__(self):
        self.db = db_manager

    def add_task(self, user_id, texto, data_tarefa, horario, deadline):
        cur = self.db.get_cursor()
        try:
            cur.execute(
                "INSERT INTO tarefas (usuario_id, data, texto, horario, deadline, concluida) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (user_id, data_tarefa, texto, horario, deadline, False)
            )
            task_id = cur.fetchone()[0]
            self.db.commit()
            return task_id
        except Exception as e:
            print(f"[task_model.py] Erro ao adicionar tarefa: {e}")
            self.db.rollback()
            raise e

    def list_tasks(self, user_id, data_tarefa=None):
        cur = self.db.get_cursor()
        if data_tarefa:
            cur.execute("SELECT id, texto, horario, deadline, concluida FROM tarefas WHERE usuario_id = %s AND data = %s", 
                       (user_id, data_tarefa))
        else:
            cur.execute("SELECT id, texto, horario, deadline, concluida, data FROM tarefas WHERE usuario_id = %s", 
                       (user_id,))
        
        tasks = []
        for row in cur.fetchall():
            task = {
                'id': row[0],
                'text': row[1],
                'time': str(row[2]),
                'deadline': str(row[3]),
                'completed': row[4]
            }
            tasks.append(task)
        return tasks

    def delete_task(self, task_id, user_id):
        cur = self.db.get_cursor()
        cur.execute("DELETE FROM tarefas WHERE id = %s AND usuario_id = %s", (task_id, user_id))
        self.db.commit()
        return cur.rowcount > 0

    def toggle_task(self, task_id, user_id, completed):
        cur = self.db.get_cursor()
        cur.execute("UPDATE tarefas SET concluida = %s WHERE id = %s AND usuario_id = %s", 
                   (completed, task_id, user_id))
        self.db.commit()
        return cur.rowcount > 0

    def get_dashboard_stats(self, user_id, selected_date=None):
        base_date = self._parse_date(selected_date) or date.today()
        start_date = base_date - timedelta(days=6)
        cur = self.db.get_cursor()

        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE concluida) AS completed,
                COUNT(*) FILTER (WHERE NOT concluida) AS pending
            FROM tarefas
            WHERE usuario_id = %s
            """,
            (user_id,)
        )
        total, completed, pending = cur.fetchone()

        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE concluida) AS completed,
                COUNT(*) FILTER (WHERE NOT concluida) AS pending
            FROM tarefas
            WHERE usuario_id = %s AND data = %s
            """,
            (user_id, base_date)
        )
        day_total, day_completed, day_pending = cur.fetchone()

        cur.execute(
            """
            SELECT data::date, COUNT(*) AS total, COUNT(*) FILTER (WHERE concluida) AS completed
            FROM tarefas
            WHERE usuario_id = %s AND data BETWEEN %s AND %s
            GROUP BY data::date
            ORDER BY data::date
            """,
            (user_id, start_date, base_date)
        )
        week_rows = {
            row[0].isoformat(): {
                "date": row[0].isoformat(),
                "total": int(row[1] or 0),
                "completed": int(row[2] or 0),
            }
            for row in cur.fetchall()
        }
        week = []
        for offset in range(7):
            current = start_date + timedelta(days=offset)
            key = current.isoformat()
            week.append(week_rows.get(key, {"date": key, "total": 0, "completed": 0}))

        cur.execute(
            """
            SELECT
                CASE
                    WHEN horario::time < TIME '12:00' THEN 'Manha'
                    WHEN horario::time < TIME '18:00' THEN 'Tarde'
                    ELSE 'Noite'
                END AS period,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE concluida) AS completed
            FROM tarefas
            WHERE usuario_id = %s AND data = %s
            GROUP BY period
            """,
            (user_id, base_date)
        )
        period_rows = {
            row[0]: {"label": self._period_label(row[0]), "total": int(row[1] or 0), "completed": int(row[2] or 0)}
            for row in cur.fetchall()
        }
        periods = [
            period_rows.get("Manha", {"label": "Manha", "total": 0, "completed": 0}),
            period_rows.get("Tarde", {"label": "Tarde", "total": 0, "completed": 0}),
            period_rows.get("Noite", {"label": "Noite", "total": 0, "completed": 0}),
        ]

        completion_rate = round((completed / total) * 100) if total else 0
        day_completion_rate = round((day_completed / day_total) * 100) if day_total else 0

        return {
            "selectedDate": base_date.isoformat(),
            "summary": {
                "total": int(total or 0),
                "completed": int(completed or 0),
                "pending": int(pending or 0),
                "completionRate": completion_rate,
            },
            "day": {
                "total": int(day_total or 0),
                "completed": int(day_completed or 0),
                "pending": int(day_pending or 0),
                "completionRate": day_completion_rate,
            },
            "week": week,
            "periods": periods,
        }

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _period_label(period):
        labels = {
            "Manha": "Manha",
            "Tarde": "Tarde",
            "Noite": "Noite",
        }
        return labels.get(period, period)
