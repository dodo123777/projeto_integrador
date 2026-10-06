"""Calendários semanais com APIs simuladas; não acessa contas ou banco reais."""
import json
import mimetypes
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2] / 'Programacao_front-end'
ARTIFACTS = Path('/private/tmp/infohelp-weekly-review')
ARTIFACTS.mkdir(exist_ok=True)
ASSETS = Path('/private/tmp/infohelp-map-assets')
ORIGIN = 'http://localhost:5500'
tasks = [
    {'id': 41, 'date': '2026-10-05', 'text': '<img src=x onerror=alert(1)>', 'time': '09:00', 'deadline': '10:00', 'completed': True},
    {'id': 42, 'date': '2026-10-06', 'text': 'Separar o material', 'time': '10:00', 'deadline': '11:00', 'completed': False},
    {'id': 43, 'date': '2026-10-11', 'text': 'Ler uma página', 'time': '14:00', 'deadline': '15:00', 'completed': False},
    {'id': 44, 'date': '2026-10-12', 'text': 'Caminhar', 'time': '08:00', 'deadline': '09:00', 'completed': False},
]
appointments = [
    {'id': 71, 'paciente_id': 12, 'paciente': 'Ana Oliveira', 'inicio': '2026-10-07T02:30:00+00:00', 'tipo': 'Consulta psicológica', 'status': 'agendada'},
    {'id': 72, 'paciente_id': 13, 'paciente': '<img src=x onerror=alert(1)>', 'inicio': '2026-10-07T03:30:00+00:00', 'tipo': 'Retorno', 'status': 'confirmada'},
    {'id': 73, 'paciente_id': 14, 'paciente': 'Marcos Silva', 'inicio': '2026-10-11T14:00:00+00:00', 'tipo': 'Retorno', 'status': 'agendada'},
]
state = {'weekly_status': 200, 'professional_status': 200, 'hold': None, 'role': 'psicologo'}
errors, held, requests = [], [], []
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Authorization, Content-Type',
           'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS'}


def week(value):
    anchor = date.fromisoformat(value)
    start = anchor - timedelta(days=anchor.weekday())
    days = [{'date': (start + timedelta(days=i)).isoformat(), 'tasks': []} for i in range(7)]
    for day in days:
        day['tasks'] = [task for task in tasks if task['date'] == day['date']]
    return {'start': days[0]['date'], 'end': days[-1]['date'], 'days': days}


def handle(route):
    url = urlparse(route.request.url)
    if url.port == 5500:
        file = (ROOT / url.path.lstrip('/')).resolve()
        if ROOT not in file.parents or not file.is_file():
            route.fulfill(status=404)
        else:
            route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        return
    if url.port != 5001:
        file = ASSETS / ('bootstrap.css' if 'bootstrap' in url.path else 'fontawesome.css' if url.path.endswith('all.min.css') else Path(url.path).name)
        if file.is_file():
            route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        else:
            route.abort()
        return
    if route.request.method == 'OPTIONS':
        route.fulfill(status=204, headers=HEADERS)
        return
    query = parse_qs(url.query)
    day = query.get('date', ['2026-10-06'])[0]
    payload = route.request.post_data_json
    requests.append((url.path, payload))
    data, status = {}, 200
    if url.path == '/sessao':
        data = {'role': 'paciente', 'destino': 'index.html'}
    elif url.path == '/tarefas/semana':
        if state['hold'] == day:
            held.append((route, week(day)))
            return
        status, data = state['weekly_status'], week(day)
    elif url.path == '/tarefas/estatisticas':
        selected = [task for task in tasks if task['date'] == day]
        completed = sum(task['completed'] for task in selected)
        counts = {'total': len(selected), 'completed': completed, 'pending': len(selected) - completed,
                  'completionRate': 100 * completed / len(selected) if selected else 0}
        data = {'selectedDate': day, 'day': counts, 'week': [{'date': day, **counts}], 'periods': [{'label': 'Manhã', **counts}]}
    elif url.path == '/tarefas':
        if route.request.method == 'POST':
            tasks.append({**payload, 'id': 99, 'completed': False})
            status, data = 201, {'id': 99}
        else:
            data = [task for task in tasks if task['date'] == day]
    elif url.path.startswith('/tarefas/'):
        task = next(task for task in tasks if task['id'] == int(url.path.split('/')[2]))
        if route.request.method == 'PUT':
            task.update(payload)
        elif route.request.method == 'DELETE':
            tasks.remove(task)
        else:
            task['completed'] = payload['completed']
        status = 204
    elif url.path == '/profissional/me':
        data = {'id': 7, 'nome': 'Luiza Costa', 'tipo': state['role'], 'registro': 'CRP teste', 'especialidade': 'Psicologia', 'email': 'luiza@example.test'}
    elif url.path == '/admin/me':
        data = {'id': 7, 'nome': 'Luiza Costa', 'role': 'admin', 'email': 'luiza@example.test'}
    elif url.path == '/admin/dashboard':
        data = {'resumo': {}, 'auditoria': []}
    elif url.path == '/profissional/dashboard':
        data = {'resumo': {'hoje': 1, 'proximos': 3, 'pacientes': 3, 'realizados': 0}, 'hoje': appointments[:1], 'proximos': appointments}
    elif url.path.endswith('/status'):
        appointment = next(row for row in appointments if row['id'] == int(url.path.split('/')[3]))
        appointment['status'] = payload['status']
        status = 204
    elif url.path == '/profissional/consultas':
        status = state['professional_status']
        anchor = date.fromisoformat(query.get('semana', ['2026-10-06'])[0])
        start = anchor - timedelta(days=anchor.weekday())
        data = [row for row in appointments if start <= date.fromisoformat(row['inicio'][:10]) <= start + timedelta(days=6)]
        if query.get('historico') == ['1']:
            data = [row for row in data if row['status'] == 'finalizada']
        if query.get('data'):
            data = [row for row in data if row['inicio'][:10] == query['data'][0]]
    elif url.path == '/profissional/pacientes':
        data = [{'id': row['paciente_id'], 'nome': row['paciente'], 'ativo': True,
                 'ultimo_atendimento': None, 'proximo_atendimento': None} for row in appointments]
        data.append({'id': 16, 'nome': 'Paciente sem vínculo', 'ativo': False,
                     'ultimo_atendimento': None, 'proximo_atendimento': None})
    elif url.path.startswith('/profissional/pacientes/'):
        patient_id = int(url.path.rsplit('/', 1)[1])
        rows = [row for row in appointments if row['paciente_id'] == patient_id]
        data = {'paciente': {'nome': rows[0]['paciente']}, 'consultas': rows}
    else:
        raise AssertionError('API inesperada: ' + url.path)
    if status >= 400:
        data = {'erro': 'O serviço está temporariamente indisponível.'}
    route.fulfill(status=status, headers=HEADERS, content_type='application/json', body='' if status == 204 else json.dumps(data))


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH') or None)
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='pt-BR', timezone_id='America/Los_Angeles')
    context.route('**/*', handle)
    context.add_init_script("localStorage.setItem('token', 'Bearer weekly-test')")
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(ORIGIN + '/index.html')
    page.locator('#selectedDate').fill('2026-10-06')
    expect(page.locator('#taskList .task-item')).to_have_count(1)
    page.locator('#weekViewButton').click()
    expect(page.locator('#taskList > .week-day')).to_have_count(7)
    expect(page.locator('#taskWeekRange')).to_contain_text('05')
    expect(page.locator('#taskList .task-item')).to_have_count(3)
    expect(page.locator('#metricTotal')).to_have_text('1')
    assert page.locator('#taskList img').count() == 0
    assert page.evaluate("CalendarDates.week('2028-03-01')") == ['2028-02-28', '2028-02-29', '2028-03-01', '2028-03-02', '2028-03-03', '2028-03-04', '2028-03-05']
    page.locator('.week-day').first.get_by_role('button', name='Editar', exact=True).click()
    expect(page.locator('#editTaskDate')).to_have_value('2026-10-05')
    page.locator('#taskInput').fill('Ler com calma')
    page.locator('#editTaskDate').fill('2026-10-08')
    page.locator('#addTaskButton').click()
    expect(page.locator('#statusMessage')).to_have_text('Tarefa atualizada.')
    assert tasks[0]['date'] == '2026-10-08' and tasks[0]['completed']
    expect(page.locator('#taskList')).to_contain_text('Ler com calma')
    page.get_by_role('button', name='Ver tarefas de quinta-feira', exact=False).click()
    expect(page.locator('#dayViewButton')).to_have_attribute('aria-pressed', 'true')
    expect(page.locator('#taskList .task-item')).to_have_count(1)
    page.locator('#weekViewButton').click()
    expect(page.locator('#taskList > .week-day')).to_have_count(7)
    page.locator('#nextTaskWeek').click()
    expect(page.locator('#taskList')).to_contain_text('Caminhar')
    page.locator('#previousTaskWeek').click()
    expect(page.locator('#taskList')).to_contain_text('Separar o material')
    state['weekly_status'] = 503
    page.locator('#selectedDate').fill('2026-10-05')
    expect(page.locator('#retryTasksButton')).to_be_visible()
    expect(page.locator('#taskList > .week-day')).to_have_count(7)
    expect(page.locator('#taskLoadStatus')).to_contain_text('última carregada')
    expect(page.locator('#progressPerc')).to_have_text('—')
    expect(page.locator('#progressCaption')).to_contain_text('Não foi possível')
    page.locator('#nextTaskWeek').click()
    expect(page.locator('#retryTasksButton')).to_be_visible()
    expect(page.locator('#taskList > .week-day')).to_have_count(0)
    expect(page.locator('.week-empty')).to_have_count(0)
    state['weekly_status'] = 200
    page.locator('#retryTasksButton').click()
    expect(page.locator('#taskList')).to_contain_text('Caminhar')
    state['hold'] = '2026-10-13'
    page.locator('#selectedDate').fill('2026-10-13')
    expect(page.locator('#taskLoadStatus')).to_contain_text('Carregando')
    page.locator('#dayViewButton').click()
    expect(page.locator('.task-empty-state')).to_be_visible()
    assert held
    for route, data in held:
        route.fulfill(headers=HEADERS, json=data)
    state['hold'] = None
    expect(page.locator('#taskList > .week-day')).to_have_count(0)
    page.locator('#selectedDate').fill('2026-10-06')
    page.locator('#weekViewButton').click()
    expect(page.locator('#taskList > .week-day')).to_have_count(7)
    for width in (1440, 768, 390, 320):
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        page.screenshot(path=str(ARTIFACTS / ('patient-week-' + str(width) + '.png')), full_page=True)

    page.set_viewport_size({'width': 1440, 'height': 1000})
    page.goto(ORIGIN + '/profissional.html')
    expect(page.get_by_role('heading', name='Atendimentos de hoje', exact=True)).to_be_visible()
    page.screenshot(path=str(ARTIFACTS / 'professional-home.png'), full_page=True)
    page.get_by_role('link', name='Ver atendimentos da semana', exact=True).click()
    page.locator('#professionalWeekDate').fill('2026-10-06')
    expect(page.locator('.professional-week .week-day')).to_have_count(7)
    expect(page.locator('[data-date="2026-10-06"]')).to_contain_text('23:30')
    expect(page.locator('[data-date="2026-10-07"]')).to_contain_text('00:30')
    assert page.locator('#pageContent img').count() == 0
    page.locator('[data-date="2026-10-06"]').get_by_role('button', name='Confirmar', exact=True).click()
    expect(page.locator('[data-date="2026-10-06"] .status-confirmada')).to_have_count(1)
    page.locator('[data-date="2026-10-06"]').get_by_role('button', name='Ana Oliveira', exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    expect(page.locator('#patientTitle')).to_have_text('Ana Oliveira')
    page.locator('#closePatient').click()
    page.locator('#nextProfessionalWeek').click()
    expect(page.locator('.consultation-card')).to_have_count(0)
    expect(page.locator('.week-empty')).to_have_count(7)
    page.locator('#previousProfessionalWeek').click()
    expect(page.locator('.consultation-card')).to_have_count(3)
    state['professional_status'] = 503
    page.locator('#nextProfessionalWeek').click()
    expect(page.locator('#retryProfessionalPage')).to_be_visible()
    expect(page.locator('.week-empty')).to_have_count(0)
    state['professional_status'] = 200
    page.locator('#retryProfessionalPage').click()
    expect(page.locator('.week-empty')).to_have_count(7)
    page.locator('#professionalWeekDate').fill('2027-01-01')
    expect(page.locator('[data-date="2026-12-28"]')).to_be_visible()
    expect(page.locator('[data-date="2027-01-03"]')).to_be_visible()
    page.locator('#professionalWeekDate').fill('2026-10-06')
    expect(page.locator('.consultation-card')).to_have_count(3)
    for width in (1440, 768, 390, 320):
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        page.screenshot(path=str(ARTIFACTS / ('professional-week-' + str(width) + '.png')), full_page=True)

    # O ADM abre o mesmo espaço com dados globais, mantendo seu perfil e sem ações clínicas.
    state['role'] = 'admin'
    for index, row in enumerate(appointments):
        row['profissional'] = 'Psicóloga Luiza' if index == 0 else 'Psicólogo Rafael'
        row['profissional_id'] = 7 if index == 0 else 8
    appointments[2]['status'] = 'finalizada'
    page.set_viewport_size({'width': 1440, 'height': 1000})
    page.goto(ORIGIN + '/admin.html')
    page.get_by_role('link', name='Todos os atendimentos', exact=True).click()
    expect(page.locator('#backToAdmin')).to_be_visible()
    expect(page.locator('.privacy-note')).to_have_text('Visão de todos os atendimentos. Horários de Brasília.')
    page.get_by_role('link', name='Ver atendimentos da semana', exact=True).click()
    page.locator('#professionalWeekDate').fill('2026-10-06')
    expect(page.get_by_role('heading', name='Semana de todos os atendimentos', exact=True)).to_be_visible()
    expect(page.locator('#pageContent')).to_contain_text('Psicóloga Luiza')
    expect(page.locator('#pageContent')).to_contain_text('Psicólogo Rafael')
    expect(page.locator('[data-appointment]')).to_have_count(0)
    expect(page.get_by_role('link', name='Agendar consulta', exact=True)).to_have_count(0)
    page.get_by_role('button', name='Ana Oliveira', exact=True).click()
    expect(page.get_by_role('dialog')).to_be_visible()
    expect(page.locator('#patientDetails')).to_contain_text('Histórico com todos os profissionais.')
    expect(page.locator('#patientDetails')).to_contain_text('Psicóloga Luiza')
    page.locator('#closePatient').click()
    page.get_by_role('link', name='Agenda / Consultas', exact=True).click()
    expect(page.locator('#newAppointment')).to_have_count(0)
    expect(page.get_by_role('columnheader', name='Psicólogo', exact=True)).to_be_visible()
    page.locator('#appointmentDate').fill('2026-10-11')
    page.get_by_role('button', name='Filtrar', exact=True).click()
    expect(page.locator('#appointmentsResult tbody tr')).to_have_count(1)
    page.get_by_role('link', name='Pacientes', exact=True).click()
    expect(page.locator('#pageContent')).to_contain_text('Paciente sem vínculo')
    expect(page.locator('#pageContent')).to_contain_text('Bloqueada')
    page.get_by_role('link', name='Atendimentos', exact=True).click()
    expect(page.locator('#pageContent')).to_contain_text('Marcos Silva')
    page.get_by_role('link', name='Perfil', exact=True).click()
    expect(page.locator('#pageContent')).to_contain_text('Administrador(a)')
    page.get_by_role('link', name='Semana de atendimentos', exact=True).click()
    expect(page.get_by_role('heading', name='Semana de todos os atendimentos', exact=True)).to_be_visible()
    expect(page.locator('.consultation-card')).to_have_count(3)
    for width in (1440, 768, 390, 320):
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        page.screenshot(path=str(ARTIFACTS / ('admin-professional-week-' + str(width) + '.png')), full_page=True)
    assert not errors, errors
    browser.close()
    print('OK: semana do paciente e psicólogo; ADM acessa todas as consultas, pacientes e histórico; edição, fuso, status, XSS, erro/retry e 1440/768/390/320; sem erros JavaScript.')
    print('Capturas:', ARTIFACTS)
