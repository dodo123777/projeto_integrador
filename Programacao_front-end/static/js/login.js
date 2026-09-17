// URL da API (back-end no Render)
const API_URL =
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:5000'
        : 'https://projeto-integrador-uvxi.onrender.com';

class LoginManager {
    constructor() {
        this.baseURL = API_URL;
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
        if (token) {
            try {
                window.location.href = await this.destination(token);
            } catch (error) {
                localStorage.removeItem('token');
                this.erroLogin.textContent = error.message;
            }
        }
    }

    async destination(token) {
        const response = await fetch(`${this.baseURL}/sessao`, {
            headers: { Authorization: token }, cache: 'no-store'
        });
        if (response.status === 401) throw new Error('Sua sessão expirou. Entre novamente.');
        if (!response.ok) throw new Error('Não foi possível verificar sua conta.');
        const data = await response.json();
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

        try {
            const response = await fetch(`${this.baseURL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, senha })
            });

            const data = await response.json();

            if (data.token) {
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
            console.error('Erro ao fazer login:', error);
            this.erroLogin.innerText = 'Erro ao conectar ao servidor!';
        }
    }

    async fazerRegistro() {
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

        try {
            const response = await fetch(`${this.baseURL}/registrar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nome, email, senha })
            });

            const data = await response.json();

            if (response.ok && data.msg) {
                // sucesso
                alert(data.msg + " Agora faça login.");
                this.fecharRegistro();
                document.getElementById('loginEmail').value = email;
            } else {
                // erro vindo do back-end (ex.: "E-mail já cadastrado!")
                this.erroRegistro.innerText = data.erro || data.msg || 'Erro ao registrar';
            }
        } catch (error) {
            console.error('Erro ao registrar:', error);
            this.erroRegistro.innerText = 'Erro ao conectar ao servidor!';
        }
    }


}

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    new LoginManager();
});
