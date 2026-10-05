"""Edição, repetição e recuperação de falhas com APIs simuladas."""
import json
import mimetypes
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2] / 'Programacao_front-end'
ARTIFACTS = Path('/private/tmp/infohelp-task-resilience')
ARTIFACTS.mkdir(exist_ok=True)
ASSETS = Path(os.environ.get('BROWSER_ASSETS_DIR', '/private/tmp/infohelp-map-assets'))
ORIGIN = 'http://localhost:5500'
tasks = [{'id': 33, 'date': '2026-10-05', 'text': 'Ler', 'time': '09:00', 'deadline': '10:00', 'completed': False}]
state = {'listing': 503, 'statistics': 503, 'mutation': 200, 'session': 200, 'abort': None, 'hold_date': None}
held = []
errors = []
requests = []


def fulfill(route):
    url = urlparse(route.request.url)
    if url.port == 5500:
        file = (ROOT / (url.path.lstrip('/') or 'index.html')).resolve()
        if ROOT.resolve() not in file.parents or not file.is_file():
            route.fulfill(status=404)
            return
        route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        return
    if url.port != 5001:
        asset = None
        if 'bootstrap' in url.path:
            asset = ASSETS / 'bootstrap.css'
        elif url.path.endswith('/css/all.min.css'):
            asset = ASSETS / 'fontawesome.css'
        elif '/webfonts/' in url.path:
            asset = ASSETS / Path(url.path).name
        if asset and asset.is_file():
            route.fulfill(body=asset.read_bytes(), content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream')
        else:
            route.abort()
        return
    headers = {'Access-Control-Allow-Origin': '*',
               'Access-Control-Allow-Headers': 'Authorization, Content-Type',
               'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'}
    if route.request.method == 'OPTIONS':
        route.fulfill(status=204, headers=headers)
        return
    method = route.request.method
    payload = route.request.post_data_json
    requests.append((method, url.path, payload))
    if state['abort'] == url.path:
        route.abort()
        return
    day = parse_qs(url.query).get('date', [None])[0]
    if day and day == state['hold_date']:
        held.append((route, headers, url.path, day))
        return
    status, data = 200, {}
    if url.path == '/sessao':
        status = state['session']
        data = {'role': 'paciente', 'destino': 'index.html'}
    elif method != 'GET' and state['mutation'] != 200:
        status = state['mutation']
    elif url.path == '/tarefas/estatisticas':
        status = state['statistics']
        entries = [task for task in tasks if task['date'] == day]
        completed = sum(task['completed'] for task in entries)
        counts = {'total': len(entries), 'completed': completed, 'pending': len(entries) - completed,
                  'completionRate': round(100 * completed / len(entries)) if entries else 0}
        data = {'selectedDate': day, 'day': counts, 'week': [{'date': day, **counts}],
                'periods': [{'label': 'Manhã', **counts}]}
    elif url.path == '/tarefas' and method == 'GET':
        status = state['listing']
        data = [task for task in tasks if task['date'] == day]
    elif url.path == '/tarefas' and method == 'POST':
        repeat = payload.get('repeat')
        start = date.fromisoformat(payload['date'])
        end = date.fromisoformat(repeat['until']) if repeat else start
        step = 7 if repeat and repeat['frequency'] == 'weekly' else 1
        ids = []
        for offset in range(0, (end - start).days + 1, step):
            task_id = max([task['id'] for task in tasks] + [33]) + 1
            tasks.append({**payload, 'id': task_id, 'date': (start + timedelta(days=offset)).isoformat(), 'completed': False})
            ids.append(task_id)
        data, status = {'id': ids[0], 'ids': ids, 'created': len(ids)}, 201
    else:
        task_id = int(url.path.split('/')[2])
        task = next(task for task in tasks if task['id'] == task_id)
        if method == 'PUT':
            task.update(payload)
        elif method == 'DELETE':
            tasks.remove(task)
        else:
            task['completed'] = payload['completed']
        status = 204
    if status >= 400:
        data = {'erro': 'O serviço está temporariamente indisponível.'}
    route.fulfill(status=status, headers=headers, content_type='application/json',
                  body='' if status == 204 else json.dumps(data))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH') or None)
    context = browser.new_context(viewport={'width': 1440, 'height': 1100}, locale='pt-BR')
    context.route('**/*', fulfill)
    context.add_init_script("localStorage.setItem('token', 'Bearer patient-test')")
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(ORIGIN + '/index.html', wait_until='domcontentloaded')
    page.locator('#selectedDate').fill('2026-10-05')
    expect(page.locator('#retryTasksButton')).to_be_visible()
    expect(page.locator('.task-empty-state')).to_have_count(0)
    expect(page.locator('#progressPerc')).to_have_text('—')
    expect(page.locator('#metricTotal')).to_have_text('—')
    assert page.evaluate("localStorage.getItem('token')") == 'Bearer patient-test'
    state['listing'] = state['statistics'] = 200
    page.locator('#retryTasksButton').click()
    expect(page.locator('#taskList .task-item')).to_have_count(1)
    expect(page.locator('#metricTotal')).to_have_text('1')
    expect(page.locator('#cancelEditButton')).to_be_hidden()
    expect(page.locator('#repeatUntilField')).to_be_hidden()

    state['listing'] = state['statistics'] = 503
    page.locator('#selectedDate').dispatch_event('change')
    expect(page.locator('#taskLoadStatus')).to_contain_text('última carregada')
    expect(page.locator('#taskList .task-item')).to_have_count(1)
    expect(page.locator('#metricTotal')).to_have_text('—')
    page.set_viewport_size({'width': 768, 'height': 1100})
    expect(page.locator('#metricTotal')).to_have_text('—')
    page.locator('#selectedDate').fill('2026-10-06')
    expect(page.locator('#taskLoadStatus')).to_contain_text('temporariamente indisponível')
    expect(page.locator('#taskList .task-item')).to_have_count(0)
    page.locator('#selectedDate').fill('2026-10-05')
    expect(page.locator('#taskLoadStatus')).to_contain_text('temporariamente indisponível')
    expect(page.locator('#taskLoadStatus')).not_to_contain_text('última carregada')
    expect(page.locator('.task-empty-state')).to_have_count(0)
    state['listing'] = state['statistics'] = 200
    page.locator('#retryTasksButton').click()
    expect(page.locator('#retryTasksButton')).to_be_hidden()
    expect(page.get_by_role('button', name='Concluir', exact=True)).to_be_enabled()

    state['mutation'] = 503
    for name in ('Remover', 'Concluir'):
        page.get_by_role('button', name=name, exact=True).click()
        expect(page.locator('#statusMessage')).to_contain_text('temporariamente indisponível')
        expect(page.get_by_role('button', name=name, exact=True)).to_be_enabled()
        assert len(tasks) == 1 and not tasks[0]['completed']
        expect(page.locator('#progressPerc')).to_have_text('')
    state['abort'] = '/tarefas/33/concluir'
    page.get_by_role('button', name='Concluir', exact=True).click()
    expect(page.locator('#statusMessage')).to_contain_text('Não foi possível conectar')
    expect(page.get_by_role('button', name='Concluir', exact=True)).to_be_enabled()
    state['abort'] = None
    page.locator('#taskInput').fill('Não perder este texto')
    page.locator('#timeInput').fill('11:00')
    page.locator('#deadlineInput').fill('12:00')
    page.locator('#addTaskButton').click()
    expect(page.locator('#addTaskButton')).to_be_enabled()
    expect(page.locator('#taskInput')).to_have_value('Não perder este texto')
    assert len(tasks) == 1

    state['mutation'] = 200
    page.get_by_role('button', name='Concluir', exact=True).click()
    expect(page.locator('#progressPerc')).to_have_text('100%')
    expect(page.get_by_role('button', name='Editar', exact=True)).to_be_enabled()
    page.get_by_role('button', name='Editar', exact=True).click()
    expect(page.locator('#repeatFields')).to_be_hidden()
    page.locator('#taskInput').fill('<img src=x onerror="window.__xss=true"> Ler mais')
    page.locator('#timeInput').fill('10:00')
    page.locator('#deadlineInput').fill('11:00')
    page.locator('#editTaskDate').fill('2026-10-06')
    state['mutation'] = 503
    page.locator('#addTaskButton').click()
    expect(page.locator('#addTaskButton')).to_be_enabled()
    expect(page.locator('#taskFormTitle')).to_have_text('Editar tarefa')
    assert tasks[0]['date'] == '2026-10-05'
    state['mutation'] = 200
    page.locator('#addTaskButton').click()
    expect(page.locator('#statusMessage')).to_have_text('Tarefa atualizada.')
    expect(page.locator('#selectedDate')).to_have_value('2026-10-06')
    assert tasks[0]['completed']
    assert page.locator('#taskList img').count() == 0
    expect(page.locator('#taskFormTitle')).to_have_text('Adicionar tarefa')

    page.locator('#taskInput').fill('Caminhar')
    page.locator('#timeInput').fill('08:00')
    page.locator('#deadlineInput').fill('08:30')
    page.locator('#repeatFrequency').select_option('weekly')
    expect(page.locator('#repeatUntilField')).to_be_visible()
    page.locator('#repeatUntil').fill('2026-10-20')
    page.locator('#addTaskButton').click()
    expect(page.locator('#statusMessage')).to_contain_text('3 tarefas criadas')
    assert [task['date'] for task in tasks if task['text'] == 'Caminhar'] == ['2026-10-06', '2026-10-13', '2026-10-20']
    page.locator('#selectedDate').fill('2026-10-13')
    expect(page.locator('#taskList .task-item')).to_have_count(1)
    expect(page.get_by_role('button', name='Editar', exact=True)).to_be_enabled()
    page.get_by_role('button', name='Editar', exact=True).click()
    for name, width in [('desktop-edit', 1440), ('tablet-edit', 768), ('mobile-edit', 390), ('mobile-small-edit', 320)]:
        page.set_viewport_size({'width': width, 'height': 1100})
        page.wait_for_function("""() => ['statusChart', 'weeklyChart', 'periodChart'].every(id => {
            const canvas = document.getElementById(id);
            const rect = canvas.getBoundingClientRect();
            return canvas.width === Math.round(rect.width * devicePixelRatio)
                && canvas.height === Math.round(rect.height * devicePixelRatio);
        })""")
        page.screenshot(path=str(ARTIFACTS / (name + '.png')), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
    page.locator('#cancelEditButton').click()
    page.get_by_role('button', name='Remover', exact=True).click()
    expect(page.locator('.task-empty-state')).to_be_visible()
    assert len([task for task in tasks if task['text'] == 'Caminhar']) == 2

    state['hold_date'] = '2026-10-20'
    page.locator('#selectedDate').fill('2026-10-20')
    page.wait_for_function("document.querySelector('#taskLoadStatus').textContent.includes('Carregando')")
    page.wait_for_timeout(100)
    assert len(held) == 2
    # Aguarda as requisições antigas antes de trocar novamente o dia.
    with page.expect_request('**/tarefas?date=2026-10-21'):
        page.locator('#selectedDate').fill('2026-10-21')
    expect(page.locator('.task-empty-state')).to_be_visible()
    expect(page.locator('#metricTotal')).to_have_text('0')
    for route, headers, path, day in held:
        if path == '/tarefas':
            data = [{'id': 999, 'text': 'Resposta antiga', 'time': '09:00', 'deadline': '10:00', 'completed': False}]
        else:
            counts = {'total': 999, 'completed': 0, 'pending': 999, 'completionRate': 0}
            data = {'selectedDate': day, 'day': counts, 'week': [], 'periods': []}
        route.fulfill(headers=headers, json=data)
    state['hold_date'] = None
    page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    expect(page.locator('#taskList')).not_to_contain_text('Resposta antiga')
    expect(page.locator('#metricTotal')).to_have_text('0')
    context.close()

    # Sem reinserir token a cada navegação: verifica preservação real do armazenamento.
    context = browser.new_context(locale='pt-BR')
    context.route('**/*', fulfill)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(ORIGIN + '/login.html')
    page.evaluate("localStorage.setItem('token', 'Bearer patient-test')")
    timeout_message = page.evaluate("""async () => {
        const originalFetch = window.fetch;
        window.fetch = (url, options) => new Promise((resolve, reject) => {
            options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
        });
        try { await apiRequest('/timeout-test', { timeout: 50 }); }
        catch (error) { return error.message; }
        finally { window.fetch = originalFetch; }
    }""")
    assert 'demorou demais' in timeout_message
    assert page.evaluate("localStorage.getItem('token')") == 'Bearer patient-test'
    state['session'] = 503
    page.reload()
    expect(page.locator('#retrySessionButton')).to_be_visible()
    expect(page.locator('#erroLogin')).to_contain_text('Sua sessão foi mantida')
    assert page.evaluate("localStorage.getItem('token')") == 'Bearer patient-test'
    state['abort'] = '/sessao'
    page.locator('#retrySessionButton').click()
    expect(page.locator('#erroLogin')).to_contain_text('Não foi possível conectar')
    expect(page.locator('#retrySessionButton')).to_be_visible()
    assert page.evaluate("localStorage.getItem('token')") == 'Bearer patient-test'
    state['abort'] = None
    state['session'] = 200
    page.locator('#retrySessionButton').click()
    page.wait_for_url('**/index.html')
    state['session'] = 401
    page.goto(ORIGIN + '/login.html')
    expect(page.locator('#erroLogin')).to_have_text('Sua sessão expirou. Entre novamente.')
    assert page.evaluate("localStorage.getItem('token')") is None
    assert not errors, errors
    browser.close()
    print('OK: erros 503/rede, sem falso sucesso, campos preservados, edição/data/conclusão, repetição semanal, exclusão individual, respostas atrasadas, XSS, sessão/retry/401 e 4 larguras.')
    print('Capturas: ' + str(ARTIFACTS))
