class LoginManager {
    constructor() {
        this.loginForm = document.getElementById('loginForm');
        this.registerForm = document.getElementById('registerForm');
        this.resetForm = document.getElementById('resetForm');
        this.erroLogin = document.getElementById('erroLogin');
        this.erroRegistro = document.getElementById('erroRegistro');
        this.erroReset = document.getElementById('erroReset');
        this.loginNotice = document.getElementById('loginNotice');
        this.retrySessionButton = document.getElementById('retrySessionButton');
        this.navigationButtons = [
            'openRegisterBtn', 'closeRegisterBtn', 'openResetBtn',
            'closeResetBtn', 'backToLoginBtn', 'retrySessionButton'
        ].map(id => document.getElementById(id));
        this.addEventListeners();
        this.checkAlreadyLoggedIn();
    }

    addEventListeners() {
        this.loginForm.addEventListener('submit', event => {
            event.preventDefault();
            this.fazerLogin();
        });
        this.registerForm.addEventListener('submit', event => {
            event.preventDefault();
            this.fazerRegistro();
        });
        document.getElementById('openRegisterBtn').addEventListener('click', () => this.abrirRegistro());
        document.getElementById('closeRegisterBtn').addEventListener('click', () => this.fecharRegistro());
        document.getElementById('openResetBtn').addEventListener('click', () => this.abrirReset());
        document.getElementById('closeResetBtn').addEventListener('click', () => this.fecharReset());
        document.getElementById('backToLoginBtn').addEventListener('click', () => this.fecharReset());
        this.retrySessionButton.addEventListener('click', () => this.checkAlreadyLoggedIn());

        document.querySelectorAll('.password-toggle').forEach(button => {
            button.addEventListener('click', () => {
                const input = document.getElementById(button.dataset.passwordTarget);
                const show = input.type === 'password';
                input.type = show ? 'text' : 'password';
                button.setAttribute('aria-pressed', String(show));
                button.setAttribute('aria-label', show ? 'Ocultar senha' : 'Mostrar senha');
                button.querySelector('i').className = show ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
            });
        });
        document.querySelectorAll('.password-field input').forEach(input => {
            const hint = input.closest('.field-group').querySelector('.caps-lock-hint');
            input.addEventListener('keyup', event => {
                hint.hidden = !event.getModifierState('CapsLock');
            });
            input.addEventListener('blur', () => { hint.hidden = true; });
        });
        [this.loginForm, this.registerForm].forEach(form => {
            form.addEventListener('input', event => {
                event.target.removeAttribute('aria-invalid');
                if (!this.busy && (form !== this.loginForm || this.retrySessionButton.hidden)) {
                    form.querySelector('.erro').textContent = '';
                }
            });
        });
    }

    setBusy(button, busy, label) {
        this.busy = busy;
        if (busy) {
            button.dataset.idleLabel = button.textContent;
            button.textContent = label;
        } else {
            button.textContent = button.dataset.idleLabel || button.textContent;
        }
        button.disabled = busy;
        button.closest('form').setAttribute('aria-busy', String(busy));
        this.navigationButtons.forEach(item => { item.disabled = busy; });
    }

    showMessage(element, message, tone = 'error') {
        element.dataset.tone = tone;
        element.textContent = message;
    }

    showError(element, message, inputId) {
        this.showMessage(element, message);
        if (inputId) {
            const input = document.getElementById(inputId);
            input.setAttribute('aria-invalid', 'true');
            input.focus();
        }
    }

    async checkAlreadyLoggedIn() {
        const token = localStorage.getItem('token');
        if (!token || this.busy) return;
        const button = document.getElementById('loginBtn');
        this.retrySessionButton.hidden = true;
        this.setBusy(button, true, 'Verificando sessão…');
        this.showMessage(this.erroLogin, 'Verificando sua sessão…', 'info');
        try {
            window.location.href = await this.destination(token);
        } catch (error) {
            if (error.status === 401) {
                localStorage.removeItem('token');
                this.showError(this.erroLogin, 'Sua sessão expirou. Entre novamente.');
            } else {
                this.showError(this.erroLogin, error.message + ' Sua sessão foi mantida.');
                this.retrySessionButton.hidden = false;
            }
        } finally {
            this.setBusy(button, false);
        }
    }

    async destination(token) {
        const data = await apiRequest('/sessao', {
            authenticated: false, headers: { Authorization: token }
        });
        const allowed = ['index.html', 'profissional.html', 'admin.html'];
        return allowed.includes(data.destino) ? data.destino : 'index.html';
    }

    showPanel(panel, titleId) {
        if (this.busy) return;
        [this.loginForm, this.registerForm, this.resetForm].forEach(item => {
            item.classList.toggle('d-none', item !== panel);
        });
        document.body.classList.toggle('auth-secondary-view', panel !== this.loginForm);
        this.limparErros();
        this.loginNotice.hidden = true;
        document.querySelectorAll('.password-toggle').forEach(button => {
            document.getElementById(button.dataset.passwordTarget).type = 'password';
            button.setAttribute('aria-pressed', 'false');
            button.setAttribute('aria-label', 'Mostrar senha');
            button.querySelector('i').className = 'fa-regular fa-eye';
        });
        document.querySelectorAll('.caps-lock-hint').forEach(hint => { hint.hidden = true; });
        document.getElementById(titleId).focus();
        const titles = {
            loginTitle: 'Entrar - InfoHelp',
            registerTitle: 'Criar conta - InfoHelp',
            resetTitle: 'Recuperar acesso - InfoHelp'
        };
        document.title = titles[titleId];
    }

    abrirRegistro() { this.showPanel(this.registerForm, 'registerTitle'); }
    fecharRegistro() {
        if (this.busy) return;
        this.showPanel(this.loginForm, 'loginTitle');
        this.registerForm.reset();
    }
    abrirReset() { this.showPanel(this.resetForm, 'resetTitle'); }
    fecharReset() { this.showPanel(this.loginForm, 'loginTitle'); }

    limparErros() {
        [this.erroLogin, this.erroRegistro, this.erroReset].forEach(item => {
            item.textContent = '';
            delete item.dataset.tone;
        });
        document.querySelectorAll('[aria-invalid]').forEach(input => input.removeAttribute('aria-invalid'));
    }

    validarEmail(email) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email); }

    async fazerLogin() {
        if (this.busy) return;
        const button = document.getElementById('loginBtn');
        const email = document.getElementById('loginEmail').value.trim();
        const senha = document.getElementById('loginSenha').value;
        this.limparErros();
        if (!email || !senha) {
            this.showError(this.erroLogin, 'Informe seu e-mail e sua senha para entrar.', !email ? 'loginEmail' : 'loginSenha');
            return;
        }
        if (!this.validarEmail(email)) {
            this.showError(this.erroLogin, 'Confira o e-mail. Exemplo: voce@exemplo.com.', 'loginEmail');
            return;
        }
        this.loginNotice.hidden = true;
        this.setBusy(button, true, 'Entrando…');
        try {
            const data = await apiRequest('/login', {
                authenticated: false, method: 'POST',
                body: JSON.stringify({ email, senha })
            });
            if (typeof data.token === 'string' && data.token) {
                const bearerToken = data.token.startsWith('Bearer ') ? data.token : 'Bearer ' + data.token;
                localStorage.setItem('token', bearerToken);
                const allowed = ['index.html', 'profissional.html', 'admin.html'];
                window.location.href = allowed.includes(data.destino) ? data.destino : await this.destination(bearerToken);
            } else {
                this.showError(this.erroLogin, data.erro || 'Não foi possível entrar. Tente novamente.');
            }
        } catch (error) {
            const message = error.status === 401
                ? 'Não conseguimos entrar com esse e-mail e senha. Confira os dados e tente de novo.'
                : error.message;
            this.showError(this.erroLogin, message);
            if (localStorage.getItem('token') && error.status !== 401) {
                this.retrySessionButton.hidden = false;
            }
        } finally {
            this.setBusy(button, false);
        }
    }

    async fazerRegistro() {
        if (this.busy) return;
        const button = document.getElementById('registerBtn');
        const nome = document.getElementById('regNome').value.trim();
        const email = document.getElementById('regEmail').value.trim();
        const senha = document.getElementById('regSenha').value;
        this.limparErros();
        if (!nome || !email || !senha) {
            const field = !nome ? 'regNome' : !email ? 'regEmail' : 'regSenha';
            this.showError(this.erroRegistro, 'Preencha seu nome, e-mail e senha para criar a conta.', field);
            return;
        }
        if (!this.validarEmail(email)) {
            this.showError(this.erroRegistro, 'Confira o e-mail. Exemplo: voce@exemplo.com.', 'regEmail');
            return;
        }
        if (senha.length < 6) {
            this.showError(this.erroRegistro, 'Use uma senha com pelo menos 6 caracteres.', 'regSenha');
            return;
        }
        if (new TextEncoder().encode(senha).length > 72) {
            this.showError(this.erroRegistro, 'Sua senha está longa demais. Use uma senha mais curta.', 'regSenha');
            return;
        }
        this.setBusy(button, true, 'Criando conta…');
        let registered = false;
        try {
            const data = await apiRequest('/registrar', {
                authenticated: false, method: 'POST',
                body: JSON.stringify({ nome, email, senha })
            });
            if (data.msg) {
                registered = true;
            } else {
                this.showError(this.erroRegistro, data.erro || 'Não foi possível criar a conta. Tente novamente.');
            }
        } catch (error) {
            const message = error.status === 409
                ? 'Esse e-mail já tem uma conta. Volte ao login para entrar.'
                : error.message;
            this.showError(this.erroRegistro, message);
        } finally {
            this.setBusy(button, false);
        }
        if (registered) {
            this.fecharRegistro();
            document.getElementById('loginEmail').value = email;
            document.getElementById('loginSenha').value = '';
            const firstName = nome.split(/\s+/)[0];
            this.loginNotice.textContent = 'Conta criada, ' + firstName + '! Agora é só entrar com seu e-mail e sua senha.';
            this.loginNotice.hidden = false;
            document.getElementById('loginSenha').focus();
        }
    }
}

document.addEventListener('DOMContentLoaded', () => { new LoginManager(); });
