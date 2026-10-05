from datetime import date, timedelta
import re

from flask import Blueprint, request, jsonify
from models.task import TaskModel
from auth import auth_required

task_bp = Blueprint('task', __name__)
task_model = TaskModel()


@task_bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def parse_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Informe uma data válida.')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('Informe uma data válida.') from None


def validate_task(data):
    if not isinstance(data, dict):
        raise ValueError('Dados inválidos.')
    text = data.get('text')
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > 500:
        raise ValueError('A tarefa deve ter entre 1 e 500 caracteres.')
    parse_date(data.get('date'))
    for key in ('time', 'deadline'):
        if not isinstance(data.get(key), str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', data[key]):
            raise ValueError('Informe horários válidos no formato HH:MM.')
    if data['deadline'] < data['time']:
        raise ValueError('O prazo deve ser igual ou posterior ao horário de início.')
    return text.strip(), data['date'], data['time'], data['deadline']


def recurrence_dates(start_value, repeat):
    start = parse_date(start_value)
    if not isinstance(repeat, dict) or repeat.get('frequency') not in ('daily', 'weekly'):
        raise ValueError('Escolha repetição diária ou semanal.')
    end = parse_date(repeat.get('until'))
    if end < start or (end - start).days > 365:
        raise ValueError('A repetição deve terminar entre o dia inicial e os próximos 365 dias.')
    interval = 1 if repeat['frequency'] == 'daily' else 7
    count = (end - start).days // interval + 1
    if count > 90:
        raise ValueError('Cada cadastro pode criar até 90 ocorrências. Escolha uma data final mais próxima.')
    return [(start + timedelta(days=offset * interval)).isoformat() for offset in range(count)]


@task_bp.route('/tarefas', methods=['POST'])
@auth_required
def add_task():
    data = request.get_json(silent=True)
    try:
        text, task_date, time, deadline = validate_task(data)
        dates = recurrence_dates(task_date, data['repeat']) if data.get('repeat') is not None else None
    except ValueError as error:
        return jsonify({'erro': str(error)}), 400
    if dates is not None:
        ids = task_model.add_recurring_tasks(request.user_id, text, dates, time, deadline)
        return jsonify({'id': ids[0], 'ids': ids, 'created': len(ids)}), 201
    task_id = task_model.add_task(request.user_id, text, task_date, time, deadline)
    return jsonify({'id': task_id}), 201


@task_bp.route('/tarefas/<int:task_id>', methods=['PUT'])
@auth_required
def edit_task(task_id):
    data = request.get_json(silent=True)
    try:
        values = validate_task(data)
        if data.get('repeat') is not None:
            raise ValueError('A repetição pode ser definida ao adicionar uma tarefa. Edite cada ocorrência separadamente.')
    except ValueError as error:
        return jsonify({'erro': str(error)}), 400
    if not task_model.update_task(task_id, request.user_id, *values):
        return jsonify({'erro': 'Tarefa não encontrada. Atualize a agenda.'}), 404
    return '', 204


def requested_date():
    value = request.args.get('date')
    if value is not None:
        parse_date(value)
    return value


@task_bp.route('/tarefas', methods=['GET'])
@auth_required
def list_tasks():
    try:
        task_date = requested_date()
    except ValueError as error:
        return jsonify({'erro': str(error)}), 400
    return jsonify(task_model.list_tasks(request.user_id, task_date))


@task_bp.route('/tarefas/estatisticas', methods=['GET'])
@auth_required
def task_stats():
    try:
        task_date = requested_date()
    except ValueError as error:
        return jsonify({'erro': str(error)}), 400
    return jsonify(task_model.get_dashboard_stats(request.user_id, task_date))


@task_bp.route('/tarefas/<int:task_id>', methods=['DELETE'])
@auth_required
def delete_task(task_id):
    if not task_model.delete_task(task_id, request.user_id):
        return jsonify({'erro': 'Tarefa não encontrada. Atualize a agenda.'}), 404
    return '', 204


@task_bp.route('/tarefas/<int:task_id>/concluir', methods=['POST'])
@auth_required
def toggle_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or type(data.get('completed')) is not bool:
        return jsonify({'erro': 'Informe se a tarefa foi concluída.'}), 400
    if not task_model.toggle_task(task_id, request.user_id, data['completed']):
        return jsonify({'erro': 'Tarefa não encontrada. Atualize a agenda.'}), 404
    return '', 204


@task_bp.route('/tarefas_protegidas', methods=['GET'])
@auth_required
def tarefas_protegidas():
    return jsonify({'msg': 'Acesso permitido!'})
