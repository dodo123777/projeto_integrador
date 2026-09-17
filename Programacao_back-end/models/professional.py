from database import db_manager


class ProfessionalModel:
    """Consultas sempre limitadas ao profissional autenticado, nunca ao ID do cliente."""

    def __init__(self):
        self.db = db_manager

    def _rows(self, sql, params):
        with self.db.get_cursor() as cur:
            cur.execute(sql, params)
            keys = [column[0] for column in cur.description]
            return [dict(zip(keys, row)) for row in cur.fetchall()]

    def profile(self, user_id):
        rows = self._rows('''
            SELECT p.usuario_id AS id, u.nome, u.email, p.tipo, p.registro, p.especialidade
            FROM profissionais p JOIN usuarios u ON u.id = p.usuario_id
            WHERE p.usuario_id = %s AND p.ativo AND u.ativo AND u.role IN ('psicologo', 'medico')
        ''', (user_id,))
        return rows[0] if rows else None

    def patients(self, professional_id, patient_id=None, search=''):
        return self._rows('''
            SELECT u.id, u.nome,
                MAX(c.inicio) FILTER (WHERE c.status = 'finalizada') AS ultimo_atendimento,
                MIN(c.inicio) FILTER (WHERE c.inicio >= CURRENT_TIMESTAMP
                    AND c.status IN ('agendada', 'confirmada', 'em_atendimento')) AS proximo_atendimento
            FROM profissional_pacientes v JOIN usuarios u ON u.id = v.paciente_id
            LEFT JOIN consultas c ON c.profissional_id = v.profissional_id AND c.paciente_id = v.paciente_id
            WHERE v.profissional_id = %s AND v.ativo AND u.ativo AND u.role = 'paciente'
                AND (%s IS NULL OR u.id = %s)
                AND strpos(lower(u.nome), lower(%s)) > 0
            GROUP BY u.id, u.nome ORDER BY lower(u.nome), u.id
        ''', (professional_id, patient_id, patient_id, search))

    def appointments(self, professional_id, patient_id=None, day=None, history=False, upcoming=False):
        return self._rows('''
            SELECT c.id, c.paciente_id, u.nome AS paciente, c.inicio, c.tipo, c.status
            FROM consultas c JOIN usuarios u ON u.id = c.paciente_id
            JOIN profissional_pacientes v ON v.profissional_id = c.profissional_id AND v.paciente_id = c.paciente_id
            WHERE c.profissional_id = %s AND v.ativo AND u.ativo AND u.role = 'paciente'
                AND (%s IS NULL OR c.paciente_id = %s)
                AND (%s IS NULL OR (c.inicio AT TIME ZONE 'America/Sao_Paulo')::date = %s::date)
                AND (NOT %s OR c.status = 'finalizada')
                AND (NOT %s OR (c.inicio >= CURRENT_TIMESTAMP AND c.status IN ('agendada', 'confirmada', 'em_atendimento')))
            ORDER BY c.inicio, c.id
        ''', (professional_id, patient_id, patient_id, day, day, history, upcoming))

    def dashboard(self, professional_id):
        summary = self._rows('''
            SELECT COUNT(*) FILTER (WHERE (inicio AT TIME ZONE 'America/Sao_Paulo')::date =
                    (CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date AND status <> 'cancelada') AS hoje,
                COUNT(*) FILTER (WHERE inicio >= CURRENT_TIMESTAMP AND status IN ('agendada', 'confirmada', 'em_atendimento')) AS proximos,
                COUNT(*) FILTER (WHERE status = 'finalizada') AS realizados,
                (SELECT COUNT(*) FROM profissional_pacientes vp JOIN usuarios up ON up.id = vp.paciente_id
                    WHERE vp.profissional_id = %s AND vp.ativo AND up.ativo AND up.role = 'paciente') AS pacientes
            FROM consultas c JOIN profissional_pacientes v
                ON v.profissional_id = c.profissional_id AND v.paciente_id = c.paciente_id
            JOIN usuarios u ON u.id = c.paciente_id
            WHERE c.profissional_id = %s AND v.ativo AND u.ativo AND u.role = 'paciente'
        ''', (professional_id, professional_id))[0]
        return {'resumo': summary, 'proximos': self.appointments(professional_id, upcoming=True)[:6]}

    def create_appointment(self, professional_id, patient_id, start, kind):
        try:
            with self.db.get_cursor() as cur:
                cur.execute('''
                    INSERT INTO consultas (profissional_id, paciente_id, inicio, tipo)
                    SELECT v.profissional_id, v.paciente_id, %s, %s FROM profissional_pacientes v
                    JOIN usuarios u ON u.id = v.paciente_id
                    WHERE v.profissional_id = %s AND v.paciente_id = %s AND v.ativo
                        AND u.ativo AND u.role = 'paciente' RETURNING id
                ''', (start, kind, professional_id, patient_id))
                row = cur.fetchone()
            self.db.commit()
            return row[0] if row else None
        except Exception:
            self.db.rollback()
            raise

    def update_status(self, professional_id, appointment_id, status, previous):
        try:
            with self.db.get_cursor() as cur:
                cur.execute('''
                    UPDATE consultas c SET status = %s
                    WHERE id = %s AND profissional_id = %s AND status = ANY(%s)
                    AND (status <> 'confirmada' OR %s <> 'em_atendimento' OR inicio <= CURRENT_TIMESTAMP)
                    AND EXISTS (SELECT 1 FROM profissional_pacientes v JOIN usuarios u ON u.id = v.paciente_id
                        WHERE v.profissional_id = c.profissional_id AND v.paciente_id = c.paciente_id
                            AND v.ativo AND u.ativo AND u.role = 'paciente')
                    RETURNING id
                ''', (status, appointment_id, professional_id, previous, status))
                row = cur.fetchone()
            self.db.commit()
            return row is not None
        except Exception:
            self.db.rollback()
            raise
