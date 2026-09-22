from flask import Blueprint, request, jsonify
from models.task import TaskModel
from auth import auth_required

task_bp = Blueprint('task', __name__)
task_model = TaskModel()

@task_bp.route('/tarefas', methods=['POST'])
@auth_required
def add_task():
    data = request.get_json()
    texto = data.get('text')
    data_tarefa = data.get('date')
    horario = data.get('time')
    deadline = data.get('deadline')

    try:
        task_id = task_model.add_task(request.user_id, texto, data_tarefa, horario, deadline)
        return jsonify({'id': task_id}), 201
    except Exception:
        return jsonify({'erro': 'Erro ao salvar no banco de dados'}), 500

@task_bp.route('/tarefas', methods=['GET'])
@auth_required
def list_tasks():
    data_tarefa = request.args.get('date')
    tasks = task_model.list_tasks(request.user_id, data_tarefa)
    return jsonify(tasks)

@task_bp.route('/tarefas/estatisticas', methods=['GET'])
@auth_required
def task_stats():
    data_tarefa = request.args.get('date')
    stats = task_model.get_dashboard_stats(request.user_id, data_tarefa)
    return jsonify(stats)

@task_bp.route('/tarefas/<int:task_id>', methods=['DELETE'])
@auth_required
def delete_task(task_id):
    task_model.delete_task(task_id, request.user_id)
    return '', 204

@task_bp.route('/tarefas/<int:task_id>/concluir', methods=['POST'])
@auth_required
def toggle_task(task_id):
    data = request.get_json()
    completed = data.get('completed', False)

    task_model.toggle_task(task_id, request.user_id, completed)
    return '', 204

@task_bp.route('/tarefas_protegidas', methods=['GET'])
@auth_required
def tarefas_protegidas():
    return jsonify({'msg': 'Acesso permitido!'})
