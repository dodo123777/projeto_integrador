import psycopg2
import threading
from config import Config

class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._local = threading.local()
        return cls._instance

    @property
    def conn(self):
        return getattr(self._local, 'conn', None)

    @conn.setter
    def conn(self, value):
        self._local.conn = value

    def _connect(self):
        if self.conn is None or self.conn.closed:
            try:
                self.conn = psycopg2.connect(
                    dbname=Config.DB_NAME,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    host=Config.DB_HOST,
                    port=Config.DB_PORT,
                    sslmode="require"  # ← ESSENCIAL pro Supabase
                )
            except psycopg2.Error as e:
                print(f"Erro ao conectar: {e}")
                raise

    def get_cursor(self):
        try:
            self._connect()
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            return cursor
        except psycopg2.OperationalError:
            self.conn = None
            self._connect()
            return self.conn.cursor()

    def commit(self):
        if self.conn:
            self.conn.commit()

    def rollback(self):
        if self.conn:
            self.conn.rollback()

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None

# Instância global
db_manager = DatabaseManager()
