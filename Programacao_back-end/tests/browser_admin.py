"""Smoke visual da administração com API interceptada; não usa banco real."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2] / 'Programacao_front-end'
ARTIFACTS = Path('/private/tmp/infohelp-admin-review')
ARTIFACTS.mkdir(exist_ok=True)
ORIGIN = 'http://localhost:5500'
errors = []
state = {'access': 200, 'linked': True, 'promoted': False, 'patient_active': True}
admin = {'id': 1, 'nome': 'Administrador Teste', 'email': 'admin@example.test', 'role': 'admin'}
patient = {'id': 12, 'nome': '<img src=x onerror=alert(1)>', 'email': 'paciente@example.test', 'role': 'paciente', 'ativo': True, 'criado_em': '2026-01-01T12:00:00+00:00', 'registro': None}
psychologist = {'id': 7, 'nome': 'Mariana Souza', 'email': 'mariana@example.test', 'role': 'psicologo', 'ativo': True, 'criado_em': '2026-01-01T12:00:00+00:00', 'registro': 'CRP 123', 'especialidade': 'Clínica', 'pacientes': 1}


def paged(items):
    return {'itens': items, 'pagina': 1, 'por_pagina': 20, 'total': len(items), 'paginas': 1}


def fulfill(route):
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
    headers = {'Access-Control-Allow-Origin': ORIGIN, 'Access-Control-Allow-Headers': 'Authorization, Content-Type', 'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS'}
    if route.request.method == 'OPTIONS':
        route.fulfill(status=204, headers=headers)
        return
    status, data = 200, {}
    if url.path == '/login':
        data = {'token': 'admin-token', 'role': 'admin', 'destino': 'admin.html'}
    elif url.path == '/sessao':
        if state['access'] == 401:
            status, data = 401, {'erro': 'Sessão expirada.'}
        else:
            data = {**admin, 'destino': 'admin.html'}
    elif state['access'] != 200:
        status, data = state['access'], {'erro': 'Acesso exclusivo a administradores.'}
    elif url.path == '/admin/me':
        data = admin
    elif url.path == '/admin/dashboard':
        data = {'resumo': {'total': 3, 'pacientes': 1, 'psicologos': 1, 'ativos': 3, 'bloqueados': 0, 'vinculos': 1, 'consultas_hoje': 1, 'consultas_agendadas': 1, 'consultas_realizadas': 2}, 'auditoria': [{'id': 1, 'acao': 'vinculo_criado', 'administrador': admin['nome'], 'usuario_afetado': 'Paciente', 'criado_em': '2026-09-15T12:00:00+00:00', 'detalhes': {}}]}
    elif url.path == '/admin/usuarios/12/promover-psicologo':
        assert route.request.post_data_json.get('confirmacao') is True
        state['promoted'] = True
        data = {'msg': 'Usuário transformado em psicólogo com sucesso.'}
    elif url.path == '/admin/usuarios/12/status':
        assert route.request.post_data_json.get('confirmacao') is True
        state['patient_active'] = route.request.post_data_json['ativo']
        data = {'msg': 'Usuário bloqueado.' if not state['patient_active'] else 'Usuário reativado.'}
    elif url.path == '/admin/usuarios/12':
        data = {**patient, 'ativo': state['patient_active']}
    elif url.path == '/admin/usuarios/12/vinculos':
        data = []
    elif url.path == '/admin/usuarios':
        query = parse_qs(url.query)
        if query.get('busca', [''])[0] == 'inexistente':
            data = paged([])
        else:
            data = paged([{**patient, 'ativo': state['patient_active']}])
            if query.get('role') != ['paciente']:
                data.update(pagina=int(query.get('pagina', ['1'])[0]), total=40, paginas=2)
    elif url.path == '/admin/psicologos/7':
        data = {'psicologo': psychologist, 'vinculos': ([{'id': 12, 'nome': 'Carlos Silva', 'email': patient['email'], 'paciente_ativo': True, 'vinculo_ativo': True, 'vinculado_em': '2026-01-01T12:00:00+00:00', 'desvinculado_em': None}] if state['linked'] else [])}
    elif url.path == '/admin/psicologos/7/perfil':
        assert route.request.post_data_json.get('confirmacao') is True
        data = {'msg': 'Perfil profissional atualizado.'}
    elif url.path == '/admin/psicologos':
        data = paged([psychologist])
    elif url.path == '/admin/vinculos/7/12':
        assert route.request.post_data_json.get('confirmacao') is True
        state['linked'] = False
        data = {'msg': 'Vínculo removido. O profissional não possui mais acesso ao paciente.'}
    elif url.path == '/admin/vinculos' and route.request.method == 'POST':
        assert route.request.post_data_json.get('confirmacao') is True
        state['linked'] = True
        status, data = 201, {'msg': 'Vínculo criado com sucesso.'}
    elif url.path == '/admin/vinculos':
        data = paged([{'profissional_id': 7, 'psicologo': psychologist['nome'], 'paciente_id': 12, 'paciente': 'Carlos Silva', 'ativo': state['linked'], 'vinculado_em': '2026-01-01T12:00:00+00:00', 'desvinculado_em': None}])
    elif url.path == '/chat':
        data = {'reply': '**Seguro** <img src=x onerror="window.__xss=true"> <script>window.__xss=true</script> [link](javascript:alert(1))'}
    route.fulfill(status=status, headers=headers, content_type='application/json', body=json.dumps(data))


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        channel=os.environ.get('PLAYWRIGHT_CHANNEL') or None,
        executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH') or None,
    )
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='pt-BR')
    context.route('**/*', fulfill)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("localStorage.setItem('token', 'Bearer admin-token')")
    page.goto(ORIGIN + '/admin.html', wait_until='domcontentloaded')
    page.get_by_role('heading', name='Dashboard').wait_for()
    page.get_by_text('Total de usuários').wait_for()
    page.screenshot(path=str(ARTIFACTS / 'desktop.png'), full_page=True)

    page.get_by_role('link', name='Usuários', exact=True).click()
    page.locator('#adminSearch').fill('inexistente')
    page.get_by_role('button', name='Buscar', exact=True).click()
    page.get_by_text('Nenhum usuário encontrado.').wait_for()
    page.locator('#adminSearch').fill('')
    page.get_by_role('button', name='Buscar', exact=True).click()
    page.get_by_role('button', name='Próxima', exact=True).click()
    page.get_by_text('Página 2 de 2', exact=False).wait_for()
    page.get_by_role('button', name='Anterior', exact=True).click()
    page.get_by_role('button', name='Visualizar').click()
    page.get_by_role('heading', name='<img src=x onerror=alert(1)>').wait_for()
    assert page.locator('#adminDialogBody img').count() == 0
    page.locator('#promotionRegistration').fill('CRP 456')
    page.get_by_role('button', name='Promover', exact=True).click()
    page.get_by_role('button', name='Promover', exact=True).last.click()
    page.get_by_text('Usuário transformado em psicólogo com sucesso.').wait_for()
    assert state['promoted']
    page.get_by_role('button', name='Visualizar').click()
    page.get_by_role('button', name='Bloquear usuário').click()
    page.locator('#acceptConfirm').click()
    page.get_by_text('Usuário bloqueado.', exact=True).wait_for()
    assert not state['patient_active']
    page.get_by_role('button', name='Visualizar').click()
    page.get_by_role('button', name='Reativar usuário').click()
    page.locator('#acceptConfirm').click()
    page.get_by_text('Usuário reativado.', exact=True).wait_for()
    assert state['patient_active']

    page.get_by_role('link', name='Psicólogos', exact=True).click()
    page.get_by_role('button', name='Visualizar').click()
    page.get_by_role('heading', name='Mariana Souza').wait_for()
    page.get_by_role('button', name='Remover').click()
    page.get_by_role('button', name='Remover vínculo').click()
    page.get_by_text('O profissional não possui mais acesso ao paciente.', exact=False).wait_for()
    assert not state['linked']

    page.get_by_role('link', name='Vínculos', exact=True).click()
    page.get_by_text('Encerrado').wait_for()
    page.get_by_role('link', name='Psicólogos', exact=True).click()
    page.get_by_role('button', name='Visualizar').click()
    page.locator('#linkPatient').select_option('12')
    page.get_by_role('button', name='Criar vínculo', exact=True).click()
    page.locator('#acceptConfirm').click()
    page.get_by_text('Vínculo criado com sucesso.').wait_for()
    assert state['linked']
    page.get_by_role('button', name='Visualizar').click()
    page.locator('#editRegistration').fill('CRP 789')
    page.get_by_role('button', name='Salvar perfil', exact=True).click()
    page.locator('#acceptConfirm').click()
    page.locator('#adminFeedback').filter(has_text='Perfil profissional atualizado.').wait_for()
    page.get_by_role('link', name='Perfil', exact=True).click()
    page.get_by_text('mesmo login dos demais usuários', exact=False).wait_for()

    page.goto(ORIGIN + '/chat.html', wait_until='domcontentloaded')
    page.locator('#messageInput').fill('Teste de segurança')
    page.locator('#sendButton').click()
    page.locator('.message.assistant strong').filter(has_text='Seguro').wait_for()
    assert page.locator('.message [onerror], .message [onload], .message a[href^="javascript:"]').count() == 0
    assert page.evaluate('window.__xss') is None

    for width, name in [(768, 'tablet'), (390, 'mobile'), (320, 'mobile-small')]:
        page.set_viewport_size({'width': width, 'height': 900})
        page.goto(ORIGIN + '/admin.html', wait_until='domcontentloaded')
        page.get_by_text('Total de usuários').wait_for()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(ARTIFACTS / f'{name}.png'), full_page=True)
        if width < 768:
            page.locator('#adminMenuToggle').click()
            page.get_by_role('link', name='Usuários', exact=True).click()
            page.get_by_role('heading', name='Usuários').wait_for()
            assert page.locator('#adminMenuToggle').get_attribute('aria-expanded') == 'false'

    state['access'] = 403
    page.goto(ORIGIN + '/admin.html', wait_until='domcontentloaded')
    page.get_by_text('Acesso exclusivo a administradores autorizados.').wait_for()
    assert not page.locator('#adminApp').is_visible()
    state['access'] = 401
    page.goto(ORIGIN + '/admin.html', wait_until='domcontentloaded')
    page.wait_for_url('**/login.html', wait_until='domcontentloaded')

    state['access'] = 200
    context2 = browser.new_context(viewport={'width': 1280, 'height': 900})
    context2.route('**/*', fulfill)
    login = context2.new_page()
    login.on('pageerror', lambda error: errors.append(str(error)))
    login.goto(ORIGIN + '/login.html', wait_until='domcontentloaded')
    login.locator('#loginEmail').fill('admin@example.test')
    login.locator('#loginSenha').fill('test-password')
    login.locator('#loginBtn').click()
    login.wait_for_url('**/admin.html', wait_until='domcontentloaded')
    login.locator('#adminLogout').click()
    login.wait_for_url('**/login.html', wait_until='domcontentloaded')
    assert login.evaluate("localStorage.getItem('token')") is None
    assert not errors, errors
    browser.close()
    print('OK: dashboard, busca/paginação, promoção, bloqueio/reativação, confirmações, criação/remoção de vínculos, perfil, XSS do chat, 401/403, login/logout e larguras 1440/768/390/320.')
    print(f'Screenshots: {ARTIFACTS}')
