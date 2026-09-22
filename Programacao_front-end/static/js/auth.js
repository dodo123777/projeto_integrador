// Verificar se usuário está logado
function checkAuth() {
    if (!localStorage.getItem('token')) {
        window.location.href = 'login.html';
    }
}

// Fazer logout
function logout() {
    localStorage.removeItem('token');
    window.location.href = 'login.html';
}

// Executar verificação ao carregar
document.addEventListener('DOMContentLoaded', () => {
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // Só checa auth se não estiver na página de login
    if (!window.location.pathname.endsWith('login.html')) {
        checkAuth();
    }

    const professionalLink = document.getElementById('professionalLink');
    const adminLink = document.getElementById('adminLink');
    const token = localStorage.getItem('token');
    if ((professionalLink || adminLink) && token) {
        const base = ['localhost', '127.0.0.1'].includes(location.hostname)
            ? 'http://localhost:5000' : 'https://projeto-integrador-uvxi.onrender.com';
        fetch(`${base}/sessao`, { headers: { Authorization: token }, cache: 'no-store' })
            .then(async response => response.ok ? response.json() : Promise.reject())
            .then(data => {
                if (professionalLink) professionalLink.hidden = data.role !== 'psicologo';
                if (adminLink) adminLink.hidden = data.role !== 'admin';
            })
            .catch(() => {
                if (professionalLink) professionalLink.hidden = true;
                if (adminLink) adminLink.hidden = true;
            });
    }
});
