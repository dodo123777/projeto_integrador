from flask import Flask, jsonify
import psycopg2
from flask_cors import CORS
from config import Config
from controllers.user_controller import user_bp
from controllers.task_controller import task_bp
from controllers.chat_controller import chat_bp
from controllers.professional_controller import professional_bp
from controllers.admin_controller import admin_bp
from database import db_manager
from professional_commands import register_professional_commands
from admin_commands import register_admin_commands


ALLOWED_ORIGINS = [
    "https://receba777.netlify.app",
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]

app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": ALLOWED_ORIGINS}},
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type", "Authorization"],
)

app.config.from_object(Config)

# Registrar blueprints (APIs)
app.register_blueprint(user_bp)
app.register_blueprint(task_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(professional_bp)
app.register_blueprint(admin_bp)
register_professional_commands(app)
register_admin_commands(app)


@app.teardown_appcontext
def close_database(error=None):
    db_manager.close()


@app.errorhandler(psycopg2.Error)
def database_unavailable(error):
    db_manager.rollback()
    app.logger.error('Falha de banco: %s', type(error).__name__)
    return jsonify({'erro': 'O serviço está temporariamente indisponível.'}), 503

# Rota raiz só pra health check / teste
@app.route("/")
def health():
    return jsonify({"status": "ok"}), 200


@app.route('/health/ready')
def readiness():
    try:
        with db_manager.get_cursor() as cursor:
            cursor.fetchone()  # SELECT 1 executado pelo gerenciador de conexões.
        payload, status = {'status': 'ok', 'api': 'ok', 'database': 'ok'}, 200
    except psycopg2.Error as error:
        db_manager.rollback()
        app.logger.error('Banco indisponível no diagnóstico: %s', type(error).__name__)
        payload, status = {'status': 'unavailable', 'api': 'ok', 'database': 'unavailable'}, 503
    response = jsonify(payload)
    response.headers['Cache-Control'] = 'no-store'
    return response, status

if __name__ == "__main__":
    app.run(debug=True, port=5001)
