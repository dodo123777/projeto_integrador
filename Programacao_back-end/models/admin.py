import json

from database import db_manager


class AdminModel:
    def __init__(self):
        self.db = db_manager

    @staticmethod
    def _dicts(cursor):
        keys = [column[0] for column in cursor.description]
        return [dict(zip(keys, row)) for row in cursor.fetchall()]

    def dashboard(self):
        with self.db.get_cursor() as cur:
            cur.execute('''
                SELECT COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE role = 'paciente') AS pacientes,
                    COUNT(*) FILTER (WHERE role = 'psicologo') AS psicologos,
                    COUNT(*) FILTER (WHERE role = 'admin') AS administradores,
                    COUNT(*) FILTER (WHERE ativo) AS ativos,
                    COUNT(*) FILTER (WHERE NOT ativo) AS bloqueados,
                    (SELECT COUNT(*) FROM profissional_pacientes WHERE ativo) AS vinculos,
                    (SELECT COUNT(*) FROM consultas WHERE
                        (inicio AT TIME ZONE 'America/Sao_Paulo')::date =
                        (CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date
                        AND status <> 'cancelada') AS consultas_hoje,
                    (SELECT COUNT(*) FROM consultas WHERE status IN ('agendada', 'confirmada')) AS consultas_agendadas,
                    (SELECT COUNT(*) FROM consultas WHERE status = 'finalizada') AS consultas_realizadas
                FROM usuarios
            ''')
            keys = [column[0] for column in cur.description]
            summary = dict(zip(keys, cur.fetchone()))
        return {'resumo': summary, 'auditoria': self.audit(8)}

    def users(self, search='', role=None, page=1, per_page=20):
        offset = (page - 1) * per_page
        params = (search, search, role, role)
        condition = '''WHERE (strpos(lower(nome), lower(%s)) > 0 OR strpos(lower(email), lower(%s)) > 0)
            AND (%s IS NULL OR role = %s)'''
        with self.db.get_cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM usuarios {condition}', params)
            total = cur.fetchone()[0]
            cur.execute(f'''
                SELECT id, nome, email, role, ativo, criado_em
                FROM usuarios {condition}
                ORDER BY lower(nome), id LIMIT %s OFFSET %s
            ''', params + (per_page, offset))
            rows = self._dicts(cur)
        return {'itens': rows, 'pagina': page, 'por_pagina': per_page, 'total': total,
                'paginas': (total + per_page - 1) // per_page}

    def user(self, user_id):
        with self.db.get_cursor() as cur:
            cur.execute('''
                SELECT u.id, u.nome, u.email, u.role, u.ativo, u.criado_em,
                    u.registro, u.especialidade, u.perfil_profissional_ativo
                FROM usuarios u
                WHERE u.id = %s
            ''', (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            keys = [column[0] for column in cur.description]
            return dict(zip(keys, row))

    def psychologists(self, search='', page=1, per_page=20):
        offset = (page - 1) * per_page
        params = (search, search)
        condition = '''WHERE u.role = 'psicologo'
            AND (strpos(lower(u.nome), lower(%s)) > 0 OR strpos(lower(u.email), lower(%s)) > 0)'''
        with self.db.get_cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM usuarios u {condition}', params)
            total = cur.fetchone()[0]
            cur.execute(f'''
                SELECT u.id, u.nome, u.email, u.ativo, u.criado_em, u.registro, u.especialidade,
                    u.perfil_profissional_ativo,
                    COUNT(v.paciente_id) FILTER (WHERE v.ativo) AS pacientes
                FROM usuarios u
                LEFT JOIN profissional_pacientes v ON v.profissional_id = u.id
                {condition} GROUP BY u.id
                ORDER BY lower(u.nome), u.id LIMIT %s OFFSET %s
            ''', params + (per_page, offset))
            rows = self._dicts(cur)
        return {'itens': rows, 'pagina': page, 'por_pagina': per_page, 'total': total,
                'paginas': (total + per_page - 1) // per_page}

    def psychologist(self, psychologist_id):
        user = self.user(psychologist_id)
        if not user or user['role'] != 'psicologo':
            return None
        with self.db.get_cursor() as cur:
            cur.execute('''
                SELECT u.id, u.nome, u.email, u.ativo AS paciente_ativo,
                    v.ativo AS vinculo_ativo, v.vinculado_em, v.desvinculado_em
                FROM profissional_pacientes v JOIN usuarios u ON u.id = v.paciente_id
                WHERE v.profissional_id = %s
                ORDER BY v.ativo DESC, lower(u.nome), u.id
            ''', (psychologist_id,))
            links = self._dicts(cur)
        return {'psicologo': user, 'vinculos': links}

    def related_links(self, user_id):
        with self.db.get_cursor() as cur:
            cur.execute('''
                SELECT v.profissional_id, pro.nome AS psicologo, v.paciente_id, pac.nome AS paciente,
                    v.ativo, v.vinculado_em, v.desvinculado_em
                FROM profissional_pacientes v
                JOIN usuarios pro ON pro.id = v.profissional_id
                JOIN usuarios pac ON pac.id = v.paciente_id
                WHERE v.profissional_id = %s OR v.paciente_id = %s
                ORDER BY v.ativo DESC, v.vinculado_em DESC
            ''', (user_id, user_id))
            return self._dicts(cur)

    def links(self, search='', page=1, per_page=20):
        offset = (page - 1) * per_page
        params = (search, search)
        condition = '''WHERE strpos(lower(pro.nome), lower(%s)) > 0
            OR strpos(lower(pac.nome), lower(%s)) > 0'''
        with self.db.get_cursor() as cur:
            cur.execute(f'''SELECT COUNT(*) FROM profissional_pacientes v
                JOIN usuarios pro ON pro.id = v.profissional_id
                JOIN usuarios pac ON pac.id = v.paciente_id {condition}''', params)
            total = cur.fetchone()[0]
            cur.execute(f'''
                SELECT v.profissional_id, pro.nome AS psicologo, v.paciente_id, pac.nome AS paciente,
                    v.ativo, v.vinculado_em, v.desvinculado_em
                FROM profissional_pacientes v
                JOIN usuarios pro ON pro.id = v.profissional_id
                JOIN usuarios pac ON pac.id = v.paciente_id
                {condition} ORDER BY v.ativo DESC, lower(pro.nome), lower(pac.nome)
                LIMIT %s OFFSET %s
            ''', params + (per_page, offset))
            rows = self._dicts(cur)
        return {'itens': rows, 'pagina': page, 'por_pagina': per_page, 'total': total,
                'paginas': (total + per_page - 1) // per_page}

    def audit(self, limit=50):
        with self.db.get_cursor() as cur:
            cur.execute('''
                SELECT a.id, a.acao, a.criado_em, a.detalhes,
                    administrador.nome AS administrador, afetado.nome AS usuario_afetado
                FROM auditoria_admin a
                LEFT JOIN usuarios administrador ON administrador.id = a.administrador_id
                LEFT JOIN usuarios afetado ON afetado.id = a.usuario_afetado_id
                ORDER BY a.criado_em DESC, a.id DESC LIMIT %s
            ''', (limit,))
            return self._dicts(cur)

    @staticmethod
    def _write_audit(cur, admin_id, action, affected=None, professional=None, patient=None, details=None):
        cur.execute('''
            INSERT INTO auditoria_admin
                (administrador_id, acao, usuario_afetado_id, profissional_id, paciente_id, detalhes)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        ''', (admin_id, action, affected, professional, patient, json.dumps(details or {})))

    def promote_psychologist(self, admin_id, user_id, registration, specialty=None):
        try:
            with self.db.get_cursor() as cur:
                cur.execute('''
                    UPDATE usuarios SET role = 'psicologo', registro = %s,
                        especialidade = %s, perfil_profissional_ativo = TRUE
                    WHERE id = %s AND role = 'paciente' AND ativo RETURNING id
                ''', (registration, specialty, user_id))
                if not cur.fetchone():
                    self.db.rollback()
                    return False
                self._write_audit(cur, admin_id, 'usuario_promovido_psicologo', affected=user_id,
                                  details={'registro': registration, 'especialidade': specialty})
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def set_user_active(self, admin_id, user_id, active):
        if admin_id == user_id:
            return False
        try:
            with self.db.get_cursor() as cur:
                # Serializa bloqueios de administradores para não desativar os últimos dois em paralelo.
                cur.execute("SELECT id FROM usuarios WHERE role = 'admin' AND ativo ORDER BY id FOR UPDATE")
                cur.execute('''
                    UPDATE usuarios SET ativo = %s,
                        auth_version = auth_version + CASE WHEN %s THEN 0 ELSE 1 END
                    WHERE id = %s AND ativo <> %s
                    AND (role <> 'admin' OR %s OR
                        (SELECT COUNT(*) FROM usuarios WHERE role = 'admin' AND ativo) > 1)
                    RETURNING id
                ''', (active, active, user_id, active, active))
                if not cur.fetchone():
                    self.db.rollback()
                    return False
                self._write_audit(cur, admin_id, 'usuario_reativado' if active else 'usuario_bloqueado', affected=user_id)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def update_psychologist(self, admin_id, user_id, registration, specialty, active):
        try:
            with self.db.get_cursor() as cur:
                cur.execute('''
                    UPDATE usuarios SET registro = %s, especialidade = %s,
                        perfil_profissional_ativo = %s
                    WHERE id = %s AND role = 'psicologo' RETURNING id
                ''', (registration, specialty, active, user_id))
                if not cur.fetchone():
                    self.db.rollback()
                    return False
                self._write_audit(cur, admin_id, 'perfil_psicologo_atualizado', affected=user_id,
                                  details={'registro': registration, 'especialidade': specialty, 'ativo': active})
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def create_link(self, admin_id, psychologist_id, patient_id):
        if psychologist_id == patient_id:
            return False
        try:
            with self.db.get_cursor() as cur:
                cur.execute('''
                    INSERT INTO profissional_pacientes
                        (profissional_id, paciente_id, ativo, vinculado_em, desvinculado_em)
                    SELECT psi.id, pac.id, TRUE, CURRENT_TIMESTAMP, NULL
                    FROM usuarios psi CROSS JOIN usuarios pac
                    WHERE psi.id = %s AND psi.role = 'psicologo' AND psi.ativo AND psi.perfil_profissional_ativo
                        AND pac.id = %s AND pac.role = 'paciente' AND pac.ativo
                    ON CONFLICT (profissional_id, paciente_id) DO UPDATE
                        SET ativo = TRUE, vinculado_em = CURRENT_TIMESTAMP, desvinculado_em = NULL
                        WHERE NOT profissional_pacientes.ativo
                    RETURNING paciente_id
                ''', (psychologist_id, patient_id))
                if not cur.fetchone():
                    self.db.rollback()
                    return False
                self._write_audit(cur, admin_id, 'vinculo_criado', affected=patient_id,
                                  professional=psychologist_id, patient=patient_id)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise

    def remove_link(self, admin_id, psychologist_id, patient_id):
        try:
            with self.db.get_cursor() as cur:
                cur.execute('''
                    UPDATE profissional_pacientes SET ativo = FALSE, desvinculado_em = CURRENT_TIMESTAMP
                    WHERE profissional_id = %s AND paciente_id = %s AND ativo RETURNING paciente_id
                ''', (psychologist_id, patient_id))
                if not cur.fetchone():
                    self.db.rollback()
                    return False
                self._write_audit(cur, admin_id, 'vinculo_removido', affected=patient_id,
                                  professional=psychologist_id, patient=patient_id)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise
