import psycopg2
import threading
import logging
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
                    sslmode="require",
                    connect_timeout=8,
                    options='-c statement_timeout=15000',
                )
            except psycopg2.Error as e:
                logging.getLogger(__name__).error('Falha de conexão com banco: %s', type(e).__name__)
                raise

    def get_cursor(self):
        # Uma conexão nova recusada não deve ser tentada duas vezes por requisição.
        self._connect()
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT 1")
            return cursor
        except psycopg2.OperationalError:
            cursor.close()
            self.close()
            self._connect()
            cursor = self.conn.cursor()
            try:
                cursor.execute("SELECT 1")
                return cursor
            except psycopg2.Error:
                cursor.close()
                raise

    def commit(self):
        if self.conn:
            self.conn.commit()

    def rollback(self):
        if self.conn and not self.conn.closed:
            self.conn.rollback()

    def close(self):
        if self.conn:
            if not self.conn.closed:
                self.conn.close()
            self.conn = None

# Instância global
db_manager = DatabaseManager()
