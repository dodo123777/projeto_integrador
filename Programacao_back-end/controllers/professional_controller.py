from datetime import date, datetime, timezone
from functools import wraps

import psycopg2
from flask import Blueprint, jsonify, request, current_app

from auth import auth_required
from models.professional import ProfessionalModel


professional_bp = Blueprint('professional', __name__, url_prefix='/profissional')
professional_model = ProfessionalModel()
TRANSITIONS = {
    'confirmada': ['agendada'],
    'em_atendimento': ['confirmada'],
    'finalizada': ['em_atendimento'],
    'cancelada': ['agendada', 'confirmada'],
}


def professional_required(view):
    @wraps(view)
    @auth_required
    def wrapped(*args, **kwargs):
        if request.current_user['role'] not in ('psicologo', 'medico'):
            return jsonify({'erro': 'Acesso exclusivo a profissionais autorizados.', 'codigo': 'acesso_profissional_negado'}), 403
        profile = professional_model.profile(request.user_id)
        if not profile or profile['tipo'] != request.current_user['role']:
            return jsonify({'erro': 'Acesso exclusivo a profissionais autorizados.', 'codigo': 'acesso_profissional_negado'}), 403
        request.professional = profile
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


@professional_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Vary'] = 'Authorization, Origin'
    return response


@professional_bp.errorhandler(psycopg2.Error)
def database_error(error):
    professional_model.db.rollback()
    current_app.logger.error('Falha de banco na área profissional: %s', type(error).__name__)
    return jsonify({'erro': 'A área profissional está temporariamente indisponível.'}), 503


@professional_bp.get('/me')
@professional_required
def me():
    return jsonify(request.professional)


@professional_bp.get('/dashboard')
@professional_required
def dashboard():
    return jsonify(serialize(professional_model.dashboard(request.user_id)))


@professional_bp.get('/pacientes')
@professional_required
def patients():
    search = request.args.get('busca', '').strip()
    if len(search) > 120:
        return jsonify({'erro': 'Busca muito longa.'}), 400
    return jsonify(serialize(professional_model.patients(request.user_id, search=search)))


@professional_bp.get('/pacientes/<int:patient_id>')
@professional_required
def patient(patient_id):
    rows = professional_model.patients(request.user_id, patient_id=patient_id)
    if not rows:
        return jsonify({'erro': 'Paciente não está vinculado a este profissional.', 'codigo': 'paciente_nao_vinculado'}), 403
    return jsonify(serialize({'paciente': rows[0], 'consultas': professional_model.appointments(request.user_id, patient_id=patient_id)}))


@professional_bp.get('/consultas')
@professional_required
def appointments():
    day = request.args.get('data') or None
    if day:
        try:
            day = date.fromisoformat(day).isoformat()
        except ValueError:
            return jsonify({'erro': 'Data inválida.'}), 400
    return jsonify(serialize(professional_model.appointments(request.user_id, day=day, history=request.args.get('historico') == '1')))


@professional_bp.post('/consultas')
@professional_required
def create_appointment():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'erro': 'Envie os dados da consulta.'}), 400
    patient_id = data.get('paciente_id')
    if type(patient_id) is not int or patient_id <= 0:
        return jsonify({'erro': 'Selecione um paciente vinculado.'}), 400
    kind = data.get('tipo')
    allowed = ('Retorno', 'Consulta médica' if request.professional['tipo'] == 'medico' else 'Consulta psicológica')
    if kind not in allowed:
        return jsonify({'erro': 'Tipo de consulta inválido para este profissional.'}), 400
    try:
        start = datetime.fromisoformat(data.get('inicio', ''))
        if start.tzinfo is None or start <= datetime.now(timezone.utc):
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({'erro': 'Informe uma data futura com fuso horário.'}), 400
    try:
        appointment_id = professional_model.create_appointment(request.user_id, patient_id, start, kind)
    except psycopg2.errors.UniqueViolation:
        return jsonify({'erro': 'Já existe uma consulta nesse horário.'}), 409
    if appointment_id is None:
        return jsonify({'erro': 'Paciente não encontrado.'}), 404
    return jsonify({'id': appointment_id}), 201


@professional_bp.patch('/consultas/<int:appointment_id>/status')
@professional_required
def update_status(appointment_id):
    data = request.get_json(silent=True)
    status = data.get('status') if isinstance(data, dict) else None
    if not isinstance(status, str) or status not in TRANSITIONS:
        return jsonify({'erro': 'Status inválido.'}), 400
    if not professional_model.update_status(request.user_id, appointment_id, status, TRANSITIONS[status]):
        return jsonify({'erro': 'Consulta indisponível para esta alteração. Atualize a agenda; o atendimento só pode iniciar no horário marcado.'}), 409
    return '', 204
