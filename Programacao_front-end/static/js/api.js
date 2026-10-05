const API_BASE_URL = ['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? 'http://localhost:5001'
    : 'https://projeto-integrador-uvxi.onrender.com';

class ApiError extends Error {
    constructor(message, status = 0) {
        super(message);
        this.status = status;
    }
}

async function apiRequest(path, { authenticated = true, timeout = 20000, ...options } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const headers = new Headers(options.headers);
    if (authenticated) {
        const token = localStorage.getItem('token');
        if (token) headers.set('Authorization', token);
    }
    if (options.body !== undefined) headers.set('Content-Type', 'application/json');

    try {
        const response = await fetch(API_BASE_URL + path, {
            ...options, headers, signal: controller.signal, cache: 'no-store'
        });
        if (response.status === 401 && authenticated) {
            localStorage.removeItem('token');
            window.location.href = 'login.html';
            throw new ApiError('Sua sessão expirou. Entre novamente.', 401);
        }
        if (response.status === 204) return null;
        let data = null;
        try {
            data = await response.json();
        } catch (error) {
            if (controller.signal.aborted) throw error;
        }
        if (!response.ok) {
            const fallback = response.status >= 500
                ? 'O serviço está temporariamente indisponível. Tente novamente.'
                : 'Não foi possível concluir a solicitação.';
            throw new ApiError(
                typeof data?.erro === 'string' ? data.erro : fallback,
                response.status
            );
        }
        if (data === null) throw new ApiError('O servidor retornou uma resposta inválida.');
        return data;
    } catch (error) {
        if (error instanceof ApiError) throw error;
        if (controller.signal.aborted) {
            throw new ApiError('A solicitação demorou demais. Confira a agenda antes de tentar novamente.');
        }
        throw new ApiError('Não foi possível conectar ao servidor. Verifique a conexão e tente novamente.');
    } finally {
        clearTimeout(timer);
    }
}
