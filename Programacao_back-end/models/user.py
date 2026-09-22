import bcrypt
import psycopg2
from database import db_manager

class UserModel:
    def __init__(self):
        self.db = db_manager

    def create_user(self, nome, email, senha):
        senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur = self.db.get_cursor()
        try:
            cur.execute("INSERT INTO usuarios (nome, email, senha, role, ativo) VALUES (%s, %s, %s, 'paciente', TRUE)",
                       (nome, email, senha_hash))
            self.db.commit()
            return True, None
        except psycopg2.errors.UniqueViolation:
            self.db.rollback()
            return False, 'E-mail já cadastrado!'
        except Exception as e:
            self.db.rollback()
            return False, 'Não foi possível registrar a conta.'

    def get_user_by_email(self, email):
        cur = self.db.get_cursor()
        cur.execute('SELECT id, senha, role, ativo, auth_version FROM usuarios WHERE email = %s', (email,))
        return cur.fetchone()

    def get_access_context(self, user_id):
        cur = self.db.get_cursor()
        cur.execute('SELECT id, nome, email, role, ativo, auth_version FROM usuarios WHERE id = %s', (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {'id': row[0], 'nome': row[1], 'email': row[2], 'role': row[3], 'ativo': row[4], 'auth_version': row[5]}

    def update_password(self, email, nova_senha):
        senha_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur = self.db.get_cursor()
        cur.execute("UPDATE usuarios SET senha = %s WHERE email = %s", (senha_hash, email))
        if cur.rowcount == 0:
            return False
        self.db.commit()
        return True

    @staticmethod
    def verify_password(senha, senha_hash):
        return bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8'))
