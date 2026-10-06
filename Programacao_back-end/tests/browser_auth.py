"""Fluxos de autenticação com API simulada, sem criar contas ou alterar senhas reais.

Executar da raiz com Playwright disponível: python3 Programacao_back-end/tests/browser_auth.py
"""
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2] / 'Programacao_front-end'
ARTIFACTS = Path(os.environ.get('AUTH_BROWSER_ARTIFACTS', '/private/tmp/infohelp-auth-review'))
ARTIFACTS.mkdir(exist_ok=True)
ASSETS = Path(os.environ.get('BROWSER_ASSETS_DIR', '/private/tmp/infohelp-map-assets'))
ORIGIN = 'http://localhost:5500'
state = {'login': 401, 'register': 409, 'session': 503, 'destination': 'index.html', 'hold': False}
requests, held, errors, dialogs = [], [], [], []
HEADERS = {'Access-Control-Allow-Origin': '*',
           'Access-Control-Allow-Headers': 'Authorization, Content-Type',
           'Access-Control-Allow-Methods': 'GET, POST, OPTIONS'}


def fulfill(route):
    url = urlparse(route.request.url)
    if url.port == 5500:
        if url.path in ('/index.html', '/admin.html', '/profissional.html'):
            route.fulfill(content_type='text/html', body='<h1>Destino de teste</h1>')
            return
        file = (ROOT / url.path.lstrip('/')).resolve()
        if ROOT not in file.parents or not file.is_file():
            route.fulfill(status=404)
            return
        route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        return
    if url.port != 5001:
        file = ASSETS / ('bootstrap.css' if 'bootstrap' in url.path else
                         'fontawesome.css' if url.path.endswith('all.min.css') else Path(url.path).name)
        if file.is_file():
            route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        else:
            route.abort()
        return
    if route.request.method == 'OPTIONS':
        route.fulfill(status=204, headers=HEADERS)
        return
    requests.append((url.path, route.request.post_data_json))
    if url.path == '/login':
        if state['hold']:
            held.append(route)
            return
        status = state['login']
        data = {'token': 'mock-token', 'destino': state['destination']} if status == 200 else {'erro': 'Credenciais inválidas'}
    elif url.path == '/registrar':
        status = state['register']
        data = {'msg': 'Usuário registrado com sucesso!'} if status == 200 else {'erro': 'E-mail já cadastrado!'}
    elif url.path == '/sessao':
        status = state['session']
        data = {'destino': state['destination']} if status == 200 else {'erro': 'O serviço está temporariamente indisponível.'}
    else:
        raise AssertionError('API inesperada: ' + url.path)
    route.fulfill(status=status, headers=HEADERS, json=data)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path=os.environ.get('PLAYWRIGHT_EXECUTABLE_PATH') or None)
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='pt-BR')
    context.route('**/*', fulfill)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('dialog', lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
    page.goto(ORIGIN + '/login.html')
    expect(page.locator('#loginEmail')).to_have_attribute('autocomplete', 'username')
    page.locator('#loginEmail').press('Enter')
    expect(page.locator('#erroLogin')).to_contain_text('Informe seu e-mail')
    expect(page.locator('#loginEmail')).to_be_focused()
    expect(page.locator('#loginEmail')).to_have_attribute('aria-invalid', 'true')
    page.locator('#loginEmail').fill('invalido')
    page.locator('#loginSenha').fill('senha-teste')
    page.locator('#loginBtn').click()
    expect(page.locator('#erroLogin')).to_contain_text('Confira o e-mail')
    assert not requests
    page.locator('#loginEmail').fill('ana@example.test')
    toggle = page.locator('[data-password-target="loginSenha"]')
    toggle.focus()
    toggle.press('Enter')
    expect(page.locator('#loginSenha')).to_have_attribute('type', 'text')
    expect(toggle).to_have_attribute('aria-label', 'Ocultar senha')
    assert not requests, 'Enter no botão de mostrar senha não pode enviar o login'
    toggle.click()
    state['hold'] = True
    page.locator('#loginSenha').press('Enter')
    expect(page.locator('#loginBtn')).to_have_text('Entrando…')
    expect(page.locator('#loginBtn')).to_be_disabled()
    expect(page.locator('#openRegisterBtn')).to_be_disabled()
    page.locator('#loginSenha').press('Enter')
    assert len(held) == 1, 'Não duplicar requisições enquanto aguarda a API'
    held.pop().fulfill(status=401, headers=HEADERS, json={'erro': 'Credenciais inválidas'})
    state['hold'] = False
    expect(page.locator('#erroLogin')).to_contain_text('Confira os dados e tente de novo.')
    expect(page.locator('#loginBtn')).to_be_enabled()
    page.screenshot(path=str(ARTIFACTS / 'login-error-desktop.png'))
    page.locator('#openResetBtn').click()
    expect(page.locator('#resetTitle')).to_be_focused()
    expect(page.locator('#resetForm')).to_contain_text('A recuperação de senha está temporariamente indisponível.')
    page.locator('#backToLoginBtn').click()
    expect(page.locator('#loginForm')).to_be_visible()
    expect(page.locator('#loginEmail')).to_have_value('ana@example.test')
    page.locator('#openRegisterBtn').focus()
    page.locator('#openRegisterBtn').press('Enter')
    expect(page.locator('#registerTitle')).to_be_focused()
    assert len(requests) == 1, 'Navegação e recuperação não devem enviar credenciais'
    page.locator('#registerBtn').click()
    expect(page.locator('#regNome')).to_be_focused()
    page.locator('#regNome').fill('Ana Oliveira')
    page.locator('#regEmail').fill('ana@example.test')
    page.locator('#regSenha').fill('123')
    page.locator('#regSenha').press('Enter')
    expect(page.locator('#erroRegistro')).to_contain_text('pelo menos 6')
    page.locator('#regSenha').fill('á' * 37)
    page.locator('#registerBtn').click()
    expect(page.locator('#erroRegistro')).to_contain_text('longa demais')
    assert len(requests) == 1
    page.locator('#regSenha').fill('senha-teste')
    page.locator('[data-password-target="regSenha"]').click()
    page.locator('#regSenha').press('Enter')
    expect(page.locator('#erroRegistro')).to_have_text('Esse e-mail já tem uma conta. Volte ao login para entrar.')
    expect(page.locator('#regEmail')).to_have_value('ana@example.test')
    state['register'] = 200
    page.locator('#registerBtn').click()
    expect(page.locator('#loginNotice')).to_contain_text('Conta criada, Ana!')
    expect(page.locator('#loginSenha')).to_be_focused()
    expect(page.locator('#loginSenha')).to_have_value('')
    expect(page.locator('#regSenha')).to_have_value('')
    expect(page.locator('#regSenha')).to_have_attribute('type', 'password')
    assert requests[-1] == ('/registrar', {'nome': 'Ana Oliveira', 'email': 'ana@example.test', 'senha': 'senha-teste'})
    assert not dialogs, 'Cadastro deve confirmar na tela, sem alert'
    page.screenshot(path=str(ARTIFACTS / 'register-success-desktop.png'))

    # Mesmos estados em telas largas, tablet e celular estreito.
    for width, height in [(1440, 1000), (1440, 650), (1366, 768), (1024, 768), (768, 1024), (390, 844), (320, 740)]:
        page.set_viewport_size({'width': width, 'height': height})
        page.reload()
        for panel in ('login', 'register', 'reset'):
            if panel == 'register':
                page.locator('#openRegisterBtn').click()
            elif panel == 'reset':
                page.locator('#closeRegisterBtn').click()
                page.locator('#openResetBtn').click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, panel)
            expect(page.locator('#' + panel + 'Form')).to_be_visible()
            if panel == 'login' and width > 820:
                button = page.locator('#openRegisterBtn').bounding_box()
                assert button['y'] + button['height'] <= height, 'Login e cadastro devem caber sem rolagem no notebook'
            page.screenshot(path=str(ARTIFACTS / (panel + '-' + str(width) + 'x' + str(height) + '.png')), full_page=True)

    for destination in ('index.html', 'admin.html', 'profissional.html'):
        state['login'], state['destination'] = 200, destination
        page.goto(ORIGIN + '/login.html')
        page.locator('#loginEmail').fill('ana@example.test')
        page.locator('#loginSenha').fill('senha-teste')
        page.locator('#loginSenha').press('Enter')
        page.wait_for_url('**/' + destination)
        assert page.evaluate("localStorage.getItem('token')") == 'Bearer mock-token'
        page.evaluate('localStorage.clear()')

    # Falha temporária mantém sessão; rejeição 401 remove a sessão expirada.
    page.goto(ORIGIN + '/login.html')
    page.evaluate("localStorage.setItem('token', 'Bearer existing-session')")
    page.reload()
    expect(page.locator('#retrySessionButton')).to_be_visible()
    expect(page.locator('#erroLogin')).to_contain_text('Sua sessão foi mantida.')
    assert page.evaluate("localStorage.getItem('token')") == 'Bearer existing-session'
    page.screenshot(path=str(ARTIFACTS / 'session-error-mobile.png'), full_page=True)
    state['session'] = 401
    page.locator('#retrySessionButton').click()
    expect(page.locator('#erroLogin')).to_have_text('Sua sessão expirou. Entre novamente.')
    expect(page.locator('#retrySessionButton')).to_be_hidden()
    assert page.evaluate("localStorage.getItem('token')") is None

    # Dispositivo com toque: tamanho de fonte evita zoom e controles têm área de toque.
    mobile = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
    mobile.route('**/*', fulfill)
    touch = mobile.new_page()
    touch.goto(ORIGIN + '/login.html')
    assert touch.locator('#loginEmail').evaluate('el => getComputedStyle(el).fontSize') == '16px'
    assert touch.locator('#openResetBtn').bounding_box()['height'] >= 44
    touch.screenshot(path=str(ARTIFACTS / 'login-touch-mobile.png'), full_page=True)
    assert not errors, errors
    browser.close()
    print('OK: login/cadastro por Enter, validações, senha visível, foco, requisição única, erros, sucesso sem alert, navegação, três perfis, sessão 503/401 e layout 320 a 1440, incluindo notebook com 650 px de altura; sem erros JavaScript.')
    print('Screenshots:', ARTIFACTS)
