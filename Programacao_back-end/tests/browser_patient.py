"""Fluxos do paciente com APIs interceptadas e dados fictícios."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2] / 'Programacao_front-end'
ARTIFACTS = Path('/private/tmp/infohelp-patient-review')
ARTIFACTS.mkdir(exist_ok=True)
ORIGIN = 'http://localhost:5500'
tasks = []
errors = []
state = {'expired': False}


def fulfill(route):
    url = urlparse(route.request.url)
    if url.port == 5500:
        file = (ROOT / (url.path.lstrip('/') or 'index.html')).resolve()
        if ROOT.resolve() not in file.parents or not file.is_file():
            route.fulfill(status=404)
            return
        mime = {'.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css'}.get(file.suffix, 'application/octet-stream')
        route.fulfill(body=file.read_bytes(), content_type=mime)
        return
    if url.port != 5000:
        route.continue_()
        return
    headers = {
        'Access-Control-Allow-Origin': ORIGIN,
        'Access-Control-Allow-Headers': 'Authorization, Content-Type',
        'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
    }
    if route.request.method == 'OPTIONS':
        route.fulfill(status=204, headers=headers)
        return
    if state['expired']:
        route.fulfill(status=401, headers=headers, content_type='application/json', body='{}')
        return
    data, status = {}, 200
    if url.path == '/sessao':
        data = {'id': 12, 'role': 'paciente', 'destino': 'index.html'}
    elif url.path == '/tarefas/estatisticas':
        date = parse_qs(url.query)['date'][0]
        completed = sum(t['completed'] for t in tasks)
        counts = {'total': len(tasks), 'completed': completed, 'pending': len(tasks) - completed,
                  'completionRate': round(100 * completed / len(tasks)) if tasks else 0}
        data = {'selectedDate': date, 'summary': counts, 'day': counts,
                'week': [{'date': date, 'total': len(tasks), 'completed': completed}],
                'periods': [{'label': 'Manha', 'total': len(tasks), 'completed': completed}]}
    elif url.path == '/tarefas' and route.request.method == 'POST':
        payload = route.request.post_data_json
        tasks.append({'id': 33, 'text': payload['text'], 'time': payload['time'],
                      'deadline': payload['deadline'], 'completed': False})
        data, status = {'id': 33}, 201
    elif url.path == '/tarefas':
        data = tasks
    elif url.path == '/tarefas/33/concluir':
        tasks[0]['completed'] = route.request.post_data_json['completed']
        status = 204
    elif url.path == '/tarefas/33' and route.request.method == 'DELETE':
        tasks.clear()
        status = 204
    route.fulfill(status=status, headers=headers, content_type='application/json',
                  body='' if status == 204 else json.dumps(data))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True,
                                executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH') or None,
                                channel=os.environ.get('PLAYWRIGHT_CHANNEL') or None)
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='pt-BR')
    context.route('**/*', fulfill)
    context.add_init_script("if (!sessionStorage.getItem('initialized')) { localStorage.setItem('token', 'Bearer patient-test'); sessionStorage.setItem('initialized', '1'); }")
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(ORIGIN + '/index.html', wait_until='domcontentloaded')
    page.wait_for_function("document.querySelector('#refreshDashboard').disabled === false")
    expect(page.locator('#adminLink')).to_be_hidden()
    expect(page.locator('#professionalLink')).to_be_hidden()
    page.locator('#focusToggle').click()
    assert page.evaluate("document.body.classList.contains('focus-mode')")
    text = '<img src=x onerror="window.__xss=true"> Estudar'
    page.locator('#taskInput').fill(text)
    page.locator('#timeInput').fill('10:00')
    page.locator('#deadlineInput').fill('11:00')
    page.locator('#addTaskButton').click()
    expect(page.locator('#taskList .task-item')).to_have_count(1)
    assert page.locator('#taskList img').count() == 0
    page.get_by_role('button', name='Concluir', exact=True).click()
    expect(page.locator('#progressPerc')).to_have_text('100%')
    expect(page.locator('#metricCompleted')).to_have_text('1')
    page.get_by_role('button', name='Desfazer', exact=True).click()
    expect(page.locator('#progressPerc')).to_have_text('')
    for name, width in [('desktop', 1440), ('tablet', 768), ('mobile', 390), ('mobile-small', 320)]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.screenshot(path=str(ARTIFACTS / (name + '.png')), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
    page.get_by_role('button', name='Remover', exact=True).click()
    expect(page.locator('#taskList .task-item')).to_have_count(0)
    state['expired'] = True
    page.locator('#selectedDate').fill('2026-09-18')
    page.locator('#selectedDate').dispatch_event('change')
    page.wait_for_url('**/login.html', wait_until='domcontentloaded')
    assert page.evaluate("localStorage.getItem('token')") is None
    assert not errors, errors
    browser.close()
    print('OK: criar/concluir/reabrir/remover tarefas, progresso/gráficos, modo foco, XSS, links por role, sessão expirada e larguras 1440/768/390/320.')
    print('Screenshots: ' + str(ARTIFACTS))
