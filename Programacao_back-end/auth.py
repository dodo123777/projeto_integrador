import jwt
import datetime
import psycopg2
from functools import wraps
from flask import current_app, request, jsonify
from config import Config
from models.user import UserModel

user_model = UserModel()

class JWTManager:
    @staticmethod
    def encode_token(user_id, email, auth_version=0):
        payload = {
            'id': user_id,
            'email': email,
            'ver': auth_version,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        }
        return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')

    @staticmethod
    def decode_token(token):
        try:
            return jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'], options={'require': ['exp', 'id']})
        except jwt.ExpiredSignatureError:
            print("[auth] Token expirado.")
            return None
        except jwt.InvalidTokenError as e:
            print(f"[auth] Token inválido: {e}")
            return None

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        raw = request.headers.get('Authorization', '')

        # Remove prefixo 'Bearer ' caso algum cliente o envie
        token = raw[7:] if raw.lower().startswith('bearer ') else raw
        token = token.strip()

        if not token:
            return jsonify({'erro': 'Token não fornecido'}), 401

        decoded = JWTManager.decode_token(token)
        if not decoded or type(decoded.get('id')) is not int or type(decoded.get('ver', 0)) is not int:
            return jsonify({'erro': 'Token inválido'}), 401

        try:
            current_user = user_model.get_access_context(decoded['id'])
        except psycopg2.Error as error:
            user_model.db.rollback()
            current_app.logger.error('Falha ao validar sessão: %s', type(error).__name__)
            return jsonify({'erro': 'Não foi possível validar a sessão.'}), 503
        if not current_user or not current_user['ativo'] or current_user['role'] not in ('paciente', 'psicologo', 'medico', 'admin'):
            return jsonify({'erro': 'Conta inexistente ou desativada'}), 401
        if decoded.get('ver', 0) != current_user['auth_version']:
            return jsonify({'erro': 'Sessão revogada. Entre novamente.'}), 401

        request.user_id = current_user['id']
        request.current_user = current_user
        return f(*args, **kwargs)
    return decorated
