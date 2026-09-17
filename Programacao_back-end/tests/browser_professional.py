"""Smoke visual isolado com APIs simuladas; requer Playwright, não usa contas reais.

Executar da raiz: python Programacao_back-end/tests/browser_professional.py
Artefatos temporários: /private/tmp/infohelp-review
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2] / 'Programacao_front-end'
ARTIFACTS = Path('/private/tmp/infohelp-review')
ARTIFACTS.mkdir(exist_ok=True)
ORIGIN = 'http://localhost:5500'
profile = {'id': 7, 'nome': 'Ana Oliveira', 'tipo': 'psicologo', 'registro': 'CRP • exemplo de teste', 'especialidade': 'Psicologia', 'email': 'ana@example.test'}
patients = [{'id': 12, 'nome': 'Carlos Silva', 'ultimo_atendimento': None, 'proximo_atendimento': '2030-09-20T12:00:00+00:00'}, {'id': 13, 'nome': '<img src=x onerror=alert(1)>', 'ultimo_atendimento': None, 'proximo_atendimento': None}]
appointments = [{'id': 1, 'paciente_id': 12, 'paciente': 'Carlos Silva', 'inicio': '2030-09-20T12:00:00+00:00', 'tipo': 'Consulta psicológica', 'status': 'agendada'}]
scenario = {'access': 200, 'empty': False, 'unlinked': False}
errors = []


def handle(route):
    url = urlparse(route.request.url)
    if url.port == 5500:
        relative = url.path.lstrip('/') or 'index.html'
        file = (ROOT / relative).resolve()
        if ROOT.resolve() not in file.parents or not file.is_file():
            route.fulfill(status=404, body='Not found')
        else:
            content_type = {'.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.png': 'image/png'}.get(file.suffix, 'application/octet-stream')
            route.fulfill(body=file.read_bytes(), content_type=content_type)
        return
    if url.port != 5000:
        route.continue_()
        return
    headers = {'Access-Control-Allow-Origin': ORIGIN, 'Access-Control-Allow-Headers': 'Authorization, Content-Type', 'Access-Control-Allow-Methods': 'GET, POST, PATCH, OPTIONS'}
    if route.request.method == 'OPTIONS':
        route.fulfill(status=204, headers=headers)
        return
    status, data = 200, []
    if url.path == '/login':
        data = {'token': 'test-token', 'role': 'psicologo', 'destino': 'profissional.html'}
    elif scenario['access'] != 200:
        status, data = scenario['access'], {'erro': 'Acesso não autorizado.'}
    elif url.path == '/profissional/me':
        data = profile
    elif url.path == '/sessao':
        data = {'id': 7, 'nome': profile['nome'], 'role': 'psicologo', 'destino': 'profissional.html'}
    elif url.path == '/profissional/dashboard':
        data = {'resumo': {'hoje': 0, 'proximos': 0 if scenario['empty'] else len(appointments), 'pacientes': 0 if scenario['empty'] else len(patients), 'realizados': 0}, 'proximos': [] if scenario['empty'] else appointments}
    elif url.path == '/profissional/pacientes':
        search = parse_qs(url.query).get('busca', [''])[0].lower()
        data = [] if scenario['empty'] else [p for p in patients if search in p['nome'].lower()]
    elif url.path == '/profissional/pacientes/12':
        if scenario['unlinked']:
            status, data = 403, {'erro': 'Paciente não está vinculado a este profissional.', 'codigo': 'paciente_nao_vinculado'}
        else:
            data = {'paciente': patients[0], 'consultas': appointments}
    elif url.path.endswith('/status'):
        appointments[0]['status'] = route.request.post_data_json['status']
        status, data = 204, None
    elif url.path == '/profissional/consultas' and route.request.method == 'POST':
        payload = route.request.post_data_json
        assert payload['paciente_id'] == 12
        assert payload['inicio'].endswith('-03:00')
        appointments.append({'id': 2, 'paciente': 'Carlos Silva', 'status': 'agendada', **payload})
        status, data = 201, {'id': 2}
    elif url.path == '/profissional/consultas':
        data = [] if scenario['empty'] or 'historico=1' in url.query else appointments
    route.fulfill(status=status, headers=headers, content_type='application/json', body='' if status == 204 else json.dumps(data))


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        channel=os.environ.get('PLAYWRIGHT_CHANNEL') or None,
        executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH') or None,
    )
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='pt-BR')
    context.route('**/*', handle)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("localStorage.setItem('token', 'Bearer test-token')")
    page.goto(ORIGIN + '/profissional.html')
    page.get_by_role('heading', name='Olá, Ana Oliveira').wait_for()
    page.get_by_role('button', name='Carlos Silva').wait_for()
    page.screenshot(path=str(ARTIFACTS / 'desktop.png'), full_page=True)
    page.get_by_role('link', name='Pacientes', exact=True).click()
    page.locator('#patientSearch').fill('inexistente')
    page.get_by_text('Nenhum paciente encontrado.', exact=False).wait_for()
    page.locator('#patientSearch').fill('')
    page.get_by_role('button', name='<img src=x onerror=alert(1)>', exact=True).wait_for()
    assert page.locator('#pageContent img').count() == 0, 'Nome deve ser renderizado como texto'
    page.get_by_role('button', name='Carlos Silva').click()
    page.get_by_role('dialog').wait_for()
    page.get_by_role('heading', name='Carlos Silva').wait_for()
    page.get_by_role('button', name='Fechar detalhes do paciente').click()
    scenario['unlinked'] = True
    page.get_by_role('button', name='Carlos Silva').click()
    page.get_by_text('Paciente não está vinculado a este profissional.').wait_for()
    assert page.locator('#professionalApp').is_visible()
    page.get_by_role('button', name='Fechar detalhes do paciente').click()
    scenario['unlinked'] = False
    page.get_by_role('link', name='Agenda / Consultas').click()
    page.get_by_role('button', name='Confirmar', exact=True).click()
    page.get_by_text('Status atualizado.', exact=True).wait_for()
    page.get_by_role('button', name='Iniciar', exact=True).wait_for()
    page.get_by_role('button', name='Agendar consulta').click()
    page.locator('#newPatient').select_option('12')
    page.locator('#newStart').fill((datetime.now(timezone.utc) + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'))
    page.get_by_role('button', name='Salvar consulta').click()
    page.get_by_text('Consulta agendada.', exact=True).wait_for()
    assert len(appointments) == 2
    page.get_by_role('link', name='Perfil', exact=True).click()
    page.get_by_text('ana@example.test', exact=True).wait_for()
    page.get_by_role('link', name='Atendimentos', exact=True).click()
    page.get_by_text('Nenhum atendimento para exibir.', exact=True).wait_for()
    for width, name in [(768, 'tablet'), (390, 'mobile'), (320, 'mobile-small')]:
        page.set_viewport_size({'width': width, 'height': 900})
        page.goto(ORIGIN + '/profissional.html')
        page.get_by_role('button', name='Carlos Silva').first.wait_for()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Overflow em {width}px'
        page.screenshot(path=str(ARTIFACTS / f'{name}.png'), full_page=True)
        if width < 768:
            page.locator('#menuToggle').click()
            page.get_by_role('link', name='Agenda / Consultas').click()
            page.get_by_role('button', name='Agendar consulta').wait_for()
            assert page.locator('#menuToggle').get_attribute('aria-expanded') == 'false'
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    scenario['empty'] = True
    page.goto(ORIGIN + '/profissional.html')
    page.get_by_text('Nenhum atendimento para exibir.', exact=True).wait_for()
    scenario['access'] = 403
    page.locator('#refreshProfessional').click()
    page.locator('#accessState').wait_for()
    assert not page.locator('#professionalApp').is_visible()
    assert page.locator('#pageContent').inner_text() == ''
    scenario['access'] = 503
    page.goto(ORIGIN + '/profissional.html')
    page.locator('#retryAccess').wait_for()
    scenario['access'] = 200
    page.locator('#retryAccess').click()
    page.get_by_role('heading', name='Olá, Ana Oliveira').wait_for()
    scenario['access'] = 401
    page.locator('#refreshProfessional').click()
    page.wait_for_url('**/login.html')
    scenario['access'] = 200
    # Sem init_script, valida login e logout reais do frontend contra a API simulada.
    context2 = browser.new_context(viewport={'width': 1280, 'height': 900})
    context2.route('**/*', handle)
    login_page = context2.new_page()
    login_page.on('pageerror', lambda error: errors.append(str(error)))
    login_page.goto(ORIGIN + '/profissional.html')
    login_page.wait_for_url('**/login.html')
    login_page.locator('#loginEmail').fill('ana@example.test')
    login_page.locator('#loginSenha').fill('test-password')
    login_page.locator('#loginBtn').click()
    login_page.wait_for_url('**/profissional.html')
    login_page.locator('#professionalLogout').click()
    login_page.wait_for_url('**/login.html')
    assert login_page.evaluate("localStorage.getItem('token')") is None
    login_page.locator('#openResetBtn').click()
    login_page.get_by_text('A recuperação de senha está temporariamente indisponível.', exact=False).wait_for()
    assert not errors, errors
    browser.close()
    print('OK: navegação, busca, XSS, agendamento, status, perfil, login/logout, 401/403/503, vazio e larguras 1440/768/390/320; sem erros JavaScript.')
    print(f'Screenshots: {ARTIFACTS}')
