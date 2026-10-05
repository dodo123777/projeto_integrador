"""Mapa e agenda no navegador, com dados fictícios e sem consultar mapas públicos.

Opcional: BROWSER_ASSETS_DIR aponta para um cache de Leaflet/Bootstrap/Font Awesome.
"""
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2] / 'Programacao_front-end'
ARTIFACTS = Path('/private/tmp/infohelp-clinics-review')
ARTIFACTS.mkdir(exist_ok=True)
ASSETS = Path(os.environ['BROWSER_ASSETS_DIR']) if os.environ.get('BROWSER_ASSETS_DIR') else None
ORIGIN = 'http://localhost:5500'
state = {'places': 'success', 'leaflet_failure': True, 'geocoder_calls': 0, 'places_calls': 0}
tasks = []
errors = []
malicious_name = '<img src=x onerror="window.__xss=true"> Clínica de teste'


def fulfill(route):
    url = urlparse(route.request.url)
    headers = {'Access-Control-Allow-Origin': '*'}
    if url.port == 5500:
        file = (ROOT / (url.path.lstrip('/') or 'index.html')).resolve()
        if ROOT.resolve() not in file.parents or not file.is_file():
            route.fulfill(status=404)
            return
        route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        return
    if url.port == 5001:
        headers.update({'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                        'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS'})
        data, status = {}, 200
        if route.request.method == 'OPTIONS':
            status = 204
        elif url.path == '/sessao':
            data = {'role': 'paciente'}
        elif url.path == '/tarefas/estatisticas':
            date = parse_qs(url.query)['date'][0]
            completed = sum(task['completed'] for task in tasks)
            counts = {'total': len(tasks), 'completed': completed, 'pending': len(tasks) - completed,
                      'completionRate': 100 if completed else 0}
            data = {'selectedDate': date, 'day': counts,
                    'week': [{'date': date, 'total': len(tasks), 'completed': completed}],
                    'periods': [{'label': 'Manhã', 'total': len(tasks), 'completed': completed}]}
        elif url.path == '/tarefas' and route.request.method == 'POST':
            tasks.append({**route.request.post_data_json, 'id': 1, 'completed': False})
            data, status = {'id': 1}, 201
        elif url.path == '/tarefas':
            data = tasks
        elif url.path == '/tarefas/1/concluir':
            tasks[0]['completed'] = route.request.post_data_json['completed']
            status = 204
        elif url.path == '/tarefas/1' and route.request.method == 'DELETE':
            tasks.clear()
            status = 204
        route.fulfill(status=status, headers=headers, content_type='application/json',
                      body='' if status == 204 else json.dumps(data))
        return
    if url.hostname == 'photon.komoot.io' and url.path == '/api/':
        state['geocoder_calls'] += 1
        query = parse_qs(url.query)['q'][0]
        features = [{'geometry': {'coordinates': [-47.06, -22.90]},
                     'properties': {'name': query, 'city': 'Campinas', 'state': 'São Paulo'}}]
        if query == 'Não existe':
            features = []
        elif query == 'Ambíguo':
            features.append({'geometry': {'coordinates': [-46.63, -23.55]},
                             'properties': {'name': 'Outro local', 'city': 'São Paulo'}})
        route.fulfill(headers=headers, json={'features': features})
        return
    if url.hostname == 'photon.komoot.io' and url.path == '/reverse':
        state['places_calls'] += 1
        if state['places'] == 'error':
            route.fulfill(status=503, headers=headers, json={})
            return
        features = [
            {'geometry': {'coordinates': [-47.07, -22.91]},
             'properties': {'name': 'Clínica mais distante', 'street': 'Rua Teste', 'housenumber': '100'}},
            {'geometry': {'coordinates': [-47.061, -22.901]}, 'properties': {'name': malicious_name}},
            {'geometry': {'coordinates': [-47.10, -22.95]}, 'properties': {'name': 'Clínica fora do raio'}},
        ]
        if state['places'] == 'empty':
            features = []
        data = {'features': features}
        if state['places'] == 'partial':
            data = {'error': 'Resposta incompleta'}
        route.fulfill(headers=headers, json=data)
        return
    if url.hostname == 'tile.openstreetmap.org':
        # Não baixar tiles públicos durante testes automatizados.
        route.fulfill(content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><path fill="#e5edf4" d="M0 0h256v256H0z"/><path stroke="#d0dde6" fill="none" d="M0 128h256M128 0v256"/></svg>')
        return
    if url.hostname == 'unpkg.com' and url.path.endswith('leaflet.js') and state['leaflet_failure']:
        route.abort()
        return
    if ASSETS:
        name = Path(url.path).name
        if name == 'bootstrap.min.css':
            name = 'bootstrap.css'
        elif name == 'all.min.css':
            name = 'fontawesome.css'
        file = ASSETS / name
        if file.is_file():
            route.fulfill(headers=headers, body=file.read_bytes(),
                          content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
            return
        route.abort()
        return
    route.continue_()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True,
                                executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH') or None,
                                channel=os.environ.get('PLAYWRIGHT_CHANNEL') or None)
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='pt-BR',
                                  geolocation={'latitude': -22.90, 'longitude': -47.06},
                                  permissions=['geolocation'])
    context.route('**/*', fulfill)
    context.add_init_script("localStorage.setItem('token', 'Bearer browser-test')")
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(ORIGIN + '/index.html', wait_until='networkidle')
    expect(page.locator('.task-empty-state')).to_be_visible()
    assert not state['geocoder_calls'] and not state['places_calls']
    assert page.locator('script[src*="leaflet"]').count() == 0
    page.locator('#focusToggle').click()
    page.locator('#taskInput').fill('Estudar por 5 minutos')
    page.locator('#timeInput').fill('10:00')
    page.locator('#deadlineInput').fill('11:00')
    page.locator('#addTaskButton').click()
    expect(page.locator('#taskList .task-item')).to_have_count(1)
    page.get_by_role('button', name='Concluir', exact=True).click()
    expect(page.locator('#metricCompleted')).to_have_text('1')
    page.get_by_role('button', name='Desfazer', exact=True).click()
    expect(page.locator('#metricCompleted')).to_have_text('0')
    page.locator('#focusToggle').click()

    for width in [1920, 1440, 1024, 768, 390, 320]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.wait_for_timeout(200)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
        if width >= 1024:
            assert page.locator('.layout').bounding_box()['width'] >= width * 0.9
            planner = page.locator('.task-planner').bounding_box()
            daily = page.locator('.daily-tasks').bounding_box()
            assert abs(planner['y'] - daily['y']) < 2
        page.screenshot(path=str(ARTIFACTS / f'agenda-{width}.png'), full_page=True)

    page.set_viewport_size({'width': 1440, 'height': 1000})
    page.locator('#agendaTab').focus()
    page.keyboard.press('ArrowRight')
    expect(page.locator('#clinicsTab')).to_be_focused()
    expect(page.locator('#agendaPanel')).to_be_hidden()
    expect(page.locator('#clinicStatus')).to_contain_text('Não foi possível carregar o mapa')
    state['leaflet_failure'] = False
    page.locator('#clinicAddress').fill('Campinas')
    page.locator('#searchClinicsButton').click()
    expect(page.locator('#clinicList .clinic-item')).to_have_count(2)
    assert page.locator('#clinicList .clinic-item').first.locator('h4').inner_text() == malicious_name
    assert not page.locator('#clinicList img').count()
    assert not page.evaluate('Boolean(window.__xss)')
    assert page.locator('#clinicList a').first.get_attribute('href').startswith('https://www.google.com/maps/dir/?api=1&destination=')
    page.locator('#clinicList button').first.click()
    expect(page.locator('.leaflet-popup-content')).to_contain_text(malicious_name)
    assert page.locator('.leaflet-popup-content img').count() == 0
    expect(page.locator('.leaflet-control-attribution')).to_contain_text('OpenStreetMap')
    # Repetir a busca usa os caches, sem novas consultas públicas.
    before = (state['geocoder_calls'], state['places_calls'])
    page.locator('#searchClinicsButton').click()
    expect(page.locator('#searchClinicsButton')).to_be_enabled()
    assert (state['geocoder_calls'], state['places_calls']) == before

    for width in [1920, 1440, 1024, 768, 390, 320]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.wait_for_timeout(200)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
        page.screenshot(path=str(ARTIFACTS / f'clinics-{width}.png'), full_page=True)

    page.locator('#clinicAddress').fill('Ambíguo')
    page.locator('#searchClinicsButton').click()
    expect(page.locator('#clinicLocationChoices button')).to_have_count(2)
    page.locator('#clinicLocationChoices button').first.click()
    expect(page.locator('#clinicList .clinic-item')).to_have_count(2)
    page.locator('#clinicAddress').fill('Não existe')
    page.locator('#searchClinicsButton').click()
    expect(page.locator('#clinicStatus')).to_contain_text('Local não encontrado')
    expect(page.locator('#clinicList .clinic-item')).to_have_count(0)
    page.locator('#locateClinicsButton').click()
    expect(page.locator('#clinicStatus')).to_contain_text('Clínicas próximas de Sua localização')
    context.clear_permissions()
    page.evaluate("() => { navigator.geolocation.getCurrentPosition = (_, reject) => reject({code: 1}); }")
    page.locator('#locateClinicsButton').click()
    expect(page.locator('#clinicStatus')).to_contain_text('Permissão de localização negada')
    # Buscar por endereço continua funcionando sem a permissão de localização.
    page.locator('#clinicAddress').fill('Campinas')
    page.locator('#searchClinicsButton').click()
    expect(page.locator('#clinicList .clinic-item')).to_have_count(2)
    state['places'] = 'empty'
    page.locator('#clinicRadius').select_option('2000')
    expect(page.locator('#clinicStatus')).to_contain_text('Nenhuma clínica cadastrada')
    state['places'] = 'partial'
    page.locator('#clinicRadius').select_option('10000')
    expect(page.locator('#clinicStatus')).to_contain_text('Não foi possível concluir a consulta')
    state['places'] = 'error'
    page.locator('#searchClinicsButton').click()
    expect(page.locator('#clinicStatus')).to_contain_text('Serviço de mapas indisponível')
    expect(page.locator('#searchClinicsButton')).to_be_enabled()
    state['places'] = 'success'
    page.locator('#searchClinicsButton').click()
    expect(page.locator('#clinicList .clinic-item')).to_have_count(3)
    page.locator('#agendaTab').click()
    expect(page.locator('#agendaPanel')).to_be_visible()
    expect(page.locator('#clinicsPanel')).to_be_hidden()
    page.get_by_role('button', name='Remover', exact=True).click()
    expect(page.locator('.task-empty-state')).to_be_visible()
    assert not errors, errors
    browser.close()
    print('OK: agenda, largura total, 6 tamanhos de tela, abas por teclado, mapa, falha e recuperação do CDN, busca, seleção de local, distância, cache, localização permitida/negada, erros, consulta parcial, XSS e rotas.')
    print('Capturas: ' + str(ARTIFACTS))
