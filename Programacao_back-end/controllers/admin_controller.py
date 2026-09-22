from datetime import date, datetime
from functools import wraps

import psycopg2
from flask import Blueprint, current_app, jsonify, request

from auth import auth_required
from models.admin import AdminModel


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
admin_model = AdminModel()
ROLES = ('paciente', 'psicologo', 'admin')


def admin_required(view):
    @wraps(view)
    @auth_required
    def wrapped(*args, **kwargs):
        if request.current_user['role'] != 'admin':
            return jsonify({'erro': 'Acesso exclusivo a administradores.'}), 403
        return view(*args, **kwargs)
    return wrapped


def serialize(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def pagination():
    try:
        page = int(request.args.get('pagina', 1))
        per_page = int(request.args.get('por_pagina', 20))
    except ValueError:
        return None
    if page < 1 or per_page < 1 or per_page > 100:
        return None
    return page, per_page


def confirmed(data):
    return isinstance(data, dict) and data.get('confirmacao') is True


@admin_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Vary'] = 'Authorization, Origin'
    return response


@admin_bp.errorhandler(psycopg2.Error)
def database_error(error):
    admin_model.db.rollback()
    current_app.logger.error('Falha de banco na área administrativa: %s', type(error).__name__)
    return jsonify({'erro': 'A área administrativa está temporariamente indisponível.'}), 503


@admin_bp.get('/me')
@admin_bp.get('')
@admin_bp.get('/')
@admin_required
def me():
    return jsonify({key: request.current_user[key] for key in ('id', 'nome', 'email', 'role')})


@admin_bp.get('/dashboard')
@admin_required
def dashboard():
    return jsonify(serialize(admin_model.dashboard()))


@admin_bp.get('/usuarios')
@admin_required
def users():
    paging = pagination()
    role = request.args.get('role') or None
    search = request.args.get('busca', '').strip()
    if not paging or len(search) > 120 or (role and role not in ROLES):
        return jsonify({'erro': 'Filtros de busca inválidos.'}), 400
    return jsonify(serialize(admin_model.users(search, role, *paging)))


@admin_bp.get('/usuarios/<int:user_id>')
@admin_required
def user(user_id):
    result = admin_model.user(user_id)
    if not result:
        return jsonify({'erro': 'Usuário não encontrado.'}), 404
    return jsonify(serialize(result))


@admin_bp.get('/usuarios/<int:user_id>/vinculos')
@admin_required
def user_links(user_id):
    return jsonify(serialize(admin_model.related_links(user_id)))


@admin_bp.post('/usuarios/<int:user_id>/promover-psicologo')
@admin_required
def promote(user_id):
    data = request.get_json(silent=True)
    registration = data.get('registro') if isinstance(data, dict) else None
    specialty = data.get('especialidade', '') if isinstance(data, dict) else ''
    if not isinstance(registration, str) or not isinstance(specialty, str):
        return jsonify({'erro': 'CRP e especialidade devem ser textos.'}), 400
    registration = registration.strip()
    specialty = specialty.strip() or None
    if not confirmed(data) or not registration or len(registration) > 60 or (specialty and len(specialty) > 120):
        return jsonify({'erro': 'Confirmação, CRP e dados profissionais válidos são obrigatórios.'}), 400
    if not admin_model.promote_psychologist(request.user_id, user_id, registration, specialty):
        return jsonify({'erro': 'Somente pacientes ativos podem ser promovidos.'}), 409
    return jsonify({'msg': 'Usuário transformado em psicólogo com sucesso.'})


@admin_bp.patch('/usuarios/<int:user_id>/status')
@admin_required
def status(user_id):
    data = request.get_json(silent=True)
    active = data.get('ativo') if isinstance(data, dict) else None
    if not confirmed(data) or type(active) is not bool:
        return jsonify({'erro': 'Confirmação e status booleano são obrigatórios.'}), 400
    if user_id == request.user_id:
        return jsonify({'erro': 'Você não pode bloquear ou reativar sua própria conta por esta tela.'}), 409
    if not admin_model.set_user_active(request.user_id, user_id, active):
        return jsonify({'erro': 'Alteração não realizada. Verifique o status e a proteção do último administrador.'}), 409
    return jsonify({'msg': 'Usuário reativado.' if active else 'Usuário bloqueado.'})


@admin_bp.get('/psicologos')
@admin_required
def psychologists():
    paging = pagination()
    search = request.args.get('busca', '').strip()
    if not paging or len(search) > 120:
        return jsonify({'erro': 'Filtros de busca inválidos.'}), 400
    return jsonify(serialize(admin_model.psychologists(search, *paging)))


@admin_bp.get('/psicologos/<int:psychologist_id>')
@admin_required
def psychologist(psychologist_id):
    result = admin_model.psychologist(psychologist_id)
    if not result:
        return jsonify({'erro': 'Psicólogo não encontrado.'}), 404
    return jsonify(serialize(result))


@admin_bp.patch('/psicologos/<int:psychologist_id>/perfil')
@admin_required
def psychologist_profile(psychologist_id):
    data = request.get_json(silent=True)
    if not confirmed(data):
        return jsonify({'erro': 'Confirmação obrigatória.'}), 400
    registration = data.get('registro')
    specialty = data.get('especialidade', '')
    active = data.get('ativo')
    if not isinstance(registration, str) or not isinstance(specialty, str) or type(active) is not bool:
        return jsonify({'erro': 'Dados profissionais inválidos.'}), 400
    registration = registration.strip()
    specialty = specialty.strip() or None
    if not registration or len(registration) > 60 or (specialty and len(specialty) > 120):
        return jsonify({'erro': 'Informe CRP e especialidade válidos.'}), 400
    if not admin_model.update_psychologist(request.user_id, psychologist_id, registration, specialty, active):
        return jsonify({'erro': 'Psicólogo não encontrado.'}), 404
    return jsonify({'msg': 'Perfil profissional atualizado.'})


@admin_bp.get('/vinculos')
@admin_required
def links():
    paging = pagination()
    search = request.args.get('busca', '').strip()
    if not paging or len(search) > 120:
        return jsonify({'erro': 'Filtros de busca inválidos.'}), 400
    return jsonify(serialize(admin_model.links(search, *paging)))


@admin_bp.post('/vinculos')
@admin_required
def create_link():
    data = request.get_json(silent=True)
    psychologist_id = data.get('psicologo_id') if isinstance(data, dict) else None
    patient_id = data.get('paciente_id') if isinstance(data, dict) else None
    if not confirmed(data) or type(psychologist_id) is not int or type(patient_id) is not int:
        return jsonify({'erro': 'Confirmação, psicólogo e paciente válidos são obrigatórios.'}), 400
    if not admin_model.create_link(request.user_id, psychologist_id, patient_id):
        return jsonify({'erro': 'Vínculo já ativo ou usuários incompatíveis.'}), 409
    return jsonify({'msg': 'Vínculo criado com sucesso.'}), 201


@admin_bp.delete('/vinculos/<int:psychologist_id>/<int:patient_id>')
@admin_required
def remove_link(psychologist_id, patient_id):
    data = request.get_json(silent=True)
    if not confirmed(data):
        return jsonify({'erro': 'Confirmação obrigatória.'}), 400
    if not admin_model.remove_link(request.user_id, psychologist_id, patient_id):
        return jsonify({'erro': 'Vínculo ativo não encontrado.'}), 404
    return jsonify({'msg': 'Vínculo removido. O profissional não possui mais acesso ao paciente.'})


@admin_bp.get('/auditoria')
@admin_required
def audit():
    return jsonify(serialize(admin_model.audit(100)))
