from flask import Blueprint, request, jsonify
from models.user import UserModel
from auth import JWTManager, auth_required

user_bp = Blueprint('user', __name__)
user_model = UserModel()


@user_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    return response

@user_bp.route('/registrar', methods=['POST'])
def registrar():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'erro': 'Dados inválidos.'}), 400
    nome = data.get('nome')
    email = data.get('email')
    senha = data.get('senha')

    if not all(isinstance(value, str) and value.strip() for value in (nome, email, senha)):
        return jsonify({'erro': 'Preencha todos os campos!'}), 400
    if len(nome) > 120 or len(email) > 254 or len(senha) < 6 or len(senha.encode('utf-8')) > 72:
        return jsonify({'erro': 'Nome, e-mail ou senha fora dos limites permitidos.'}), 400

    success, message = user_model.create_user(nome, email, senha)
    if success:
        return jsonify({'msg': 'Usuário registrado com sucesso!'})
    elif message == 'E-mail já cadastrado!':
        return jsonify({'erro': message}), 409
    else:
        return jsonify({'erro': message}), 500

@user_bp.route('/esqueci_senha', methods=['POST'])
def esqueci_senha():
    # Não alterar credenciais sem comprovar a posse da conta.
    return jsonify({'erro': 'A recuperação de senha está indisponível. Entre em contato com o suporte da plataforma.'}), 403

@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'erro': 'Dados inválidos.'}), 400
    email = data.get('email')
    senha = data.get('senha')
    if not isinstance(email, str) or not isinstance(senha, str) or not email or not senha:
        return jsonify({'erro': 'Informe e-mail e senha.'}), 400
    if len(email) > 254 or len(senha.encode('utf-8')) > 72:
        return jsonify({'erro': 'Credenciais inválidas'}), 401
    
    user = user_model.get_user_by_email(email)
    if user:
        user_id, senha_hash, role, ativo, auth_version = user
        if ativo and UserModel.verify_password(senha, senha_hash):
            token = JWTManager.encode_token(user_id, email, auth_version)
            return jsonify({'token': token, 'role': role, 'destino': destination_for(role)})
    
    return jsonify({'erro': 'Credenciais inválidas'}), 401


def destination_for(role):
    if role == 'admin':
        return 'admin.html'
    if role == 'psicologo':
        return 'profissional.html'
    return 'index.html'


@user_bp.route('/sessao', methods=['GET'])
@auth_required
def session():
    return jsonify({
        'id': request.current_user['id'],
        'nome': request.current_user['nome'],
        'role': request.current_user['role'],
        'destino': destination_for(request.current_user['role']),
    })
