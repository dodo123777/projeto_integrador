class LoginManager {
    constructor() {
        this.init();
    }


    init() {
        // Elementos dos formulários
        this.loginForm = document.getElementById('loginForm');
        this.registerForm = document.getElementById('registerForm');
        this.resetForm = document.getElementById('resetForm');

        // Elementos de erro
        this.erroLogin = document.getElementById('erroLogin');
        this.erroRegistro = document.getElementById('erroRegistro');
        this.erroReset = document.getElementById('erroReset');
        this.retrySessionButton = document.getElementById('retrySessionButton');
        this.retrySessionButton.addEventListener('click', () => this.checkAlreadyLoggedIn());

        // Adicionar event listeners
        this.addEventListeners();
        
        // Verificar se já está logado
        this.checkAlreadyLoggedIn();
    }

    addEventListeners() {
        // Botões principais
        document.getElementById('loginBtn').addEventListener('click', () => this.fazerLogin());
        document.getElementById('registerBtn').addEventListener('click', () => this.fazerRegistro());

        // Botões de navegação
        document.getElementById('openRegisterBtn').addEventListener('click', () => this.abrirRegistro());
        document.getElementById('closeRegisterBtn').addEventListener('click', () => this.fecharRegistro());
        document.getElementById('openResetBtn').addEventListener('click', () => this.abrirReset());
        document.getElementById('closeResetBtn').addEventListener('click', () => this.fecharReset());

        // Enter para fazer login
        document.addEventListener('keydown', (e) => {
            if (e.key === "Enter" && !this.loginForm.classList.contains('d-none')) {
                this.fazerLogin();
            }
        });
    }

    async checkAlreadyLoggedIn() {
        const token = localStorage.getItem('token');
        if (!token || this.verifyingSession) return;
        this.verifyingSession = true;
        this.retrySessionButton.hidden = true;
        document.getElementById('loginBtn').disabled = true;
        this.erroLogin.textContent = 'Verificando sua sessão…';
        try {
            window.location.href = await this.destination(token);
        } catch (error) {
            if (error.status === 401) {
                localStorage.removeItem('token');
                this.erroLogin.textContent = 'Sua sessão expirou. Entre novamente.';
            } else {
                this.erroLogin.textContent = error.message + ' Sua sessão foi mantida.';
                this.retrySessionButton.hidden = false;
            }
        } finally {
            this.verifyingSession = false;
            document.getElementById('loginBtn').disabled = false;
        }
    }

    async destination(token) {
        const data = await apiRequest('/sessao', {
            authenticated: false, headers: { Authorization: token }
        });
        const allowed = ['index.html', 'profissional.html', 'admin.html'];
        return allowed.includes(data.destino) ? data.destino : 'index.html';
    }

    // Navegação entre formulários
    abrirRegistro() {
        this.registerForm.classList.remove('d-none');
        this.loginForm.classList.add('d-none');
        this.limparErros();
    }

    fecharRegistro() {
        this.registerForm.classList.add('d-none');
        this.loginForm.classList.remove('d-none');
        this.limparErros();
        this.limparCamposRegistro();
    }

    abrirReset() {
        this.resetForm.classList.remove('d-none');
        this.loginForm.classList.add('d-none');
        this.limparErros();
    }

    fecharReset() {
        this.resetForm.classList.add('d-none');
        this.loginForm.classList.remove('d-none');
        this.limparErros();
    }

    limparErros() {
        this.erroLogin.innerText = "";
        this.erroRegistro.innerText = "";
        this.erroReset.innerText = "";
    }

    limparCamposRegistro() {
        document.getElementById('regNome').value = '';
        document.getElementById('regEmail').value = '';
        document.getElementById('regSenha').value = '';
    }


    // Validações
    validarEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    validarSenha(senha) {
        return senha.length >= 6;
    }

    // Operações de API
    async fazerLogin() {
        const button = document.getElementById('loginBtn');
        if (button.disabled) return;
        const email = document.getElementById('loginEmail').value.trim();
        const senha = document.getElementById('loginSenha').value;

        // Validações básicas
        if (!email || !senha) {
            this.erroLogin.innerText = "Preencha todos os campos!";
            return;
        }

        if (!this.validarEmail(email)) {
            this.erroLogin.innerText = "Email inválido!";
            return;
        }

        button.disabled = true;
        try {
            const data = await apiRequest('/login', {
                authenticated: false,
                method: 'POST',
                body: JSON.stringify({ email, senha })
            });
            if (typeof data.token === 'string' && data.token) {
                // já guardar com prefixo Bearer para facilitar uso nas outras requisições
                const bearerToken = data.token.startsWith('Bearer ')
                    ? data.token
                    : `Bearer ${data.token}`;
                localStorage.setItem('token', bearerToken);
                const allowed = ['index.html', 'profissional.html', 'admin.html'];
                window.location.href = allowed.includes(data.destino)
                    ? data.destino : await this.destination(bearerToken);
            } else {
                this.erroLogin.innerText = data.erro || 'Erro no login';
            }
        } catch (error) {
            this.erroLogin.innerText = error.message;
            if (localStorage.getItem('token') && error.status !== 401) {
                this.retrySessionButton.hidden = false;
            }
        } finally {
            button.disabled = false;
        }
    }

    async fazerRegistro() {
        const button = document.getElementById('registerBtn');
        if (button.disabled) return;
        const nome = document.getElementById('regNome').value.trim();
        const email = document.getElementById('regEmail').value.trim();
        const senha = document.getElementById('regSenha').value;

        // Validações
        if (!nome || !email || !senha) {
            this.erroRegistro.innerText = "Preencha todos os campos!";
            return;
        }

        if (!this.validarEmail(email)) {
            this.erroRegistro.innerText = "Email inválido!";
            return;
        }

        if (!this.validarSenha(senha)) {
            this.erroRegistro.innerText = "A senha deve ter pelo menos 6 caracteres!";
            return;
        }

        button.disabled = true;
        try {
            const data = await apiRequest('/registrar', {
                authenticated: false,
                method: 'POST',
                body: JSON.stringify({ nome, email, senha })
            });
            if (data.msg) {
                // sucesso
                alert(data.msg + " Agora faça login.");
                this.fecharRegistro();
                document.getElementById('loginEmail').value = email;
            } else {
                // erro vindo do back-end (ex.: "E-mail já cadastrado!")
                this.erroRegistro.innerText = data.erro || data.msg || 'Erro ao registrar';
            }
        } catch (error) {
            this.erroRegistro.innerText = error.message;
        } finally {
            button.disabled = false;
        }
    }


}

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    new LoginManager();
});
