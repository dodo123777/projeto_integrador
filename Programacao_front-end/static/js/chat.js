const API_URL = ['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? 'http://localhost:5000'
    : 'https://projeto-integrador-uvxi.onrender.com';

class ChatManager {
    constructor() {
        this.chatForm = document.getElementById('chatForm');
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.statusText = document.getElementById('statusText');
        this.promptChips = document.querySelectorAll('.prompt-chip');
        this.isSending = false;

        this.init();
    }

    init() {
        this.addMessage('assistant', 'Ola! Eu posso ajudar a transformar uma tarefa confusa em passos menores. Por onde voce quer comecar?');

        this.chatForm.addEventListener('submit', (event) => {
            event.preventDefault();
            this.sendMessage();
        });

        this.messageInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                this.sendMessage();
            }
        });

        this.promptChips.forEach((chip) => {
            chip.addEventListener('click', () => {
                this.messageInput.value = chip.dataset.prompt || '';
                this.autoResize();
                this.messageInput.focus();
            });
        });

        this.messageInput.addEventListener('input', () => this.autoResize());
        this.messageInput.focus();
        this.autoResize();
    }

    autoResize() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = `${Math.min(this.messageInput.scrollHeight, 150)}px`;
    }

    setStatus(text) {
        this.statusText.textContent = text;
    }

    addMessage(role, text) {
        const messageElement = document.createElement('article');
        messageElement.className = `message ${role} d-flex align-items-end gap-2`;
        if (role === 'user') {
            messageElement.classList.add('flex-row-reverse', 'align-self-end');
        }

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar d-flex align-items-center justify-content-center flex-shrink-0';
        avatar.innerHTML = role === 'assistant'
            ? '<i class="fa-solid fa-robot"></i>'
            : '<i class="fa-solid fa-user"></i>';

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble flex-grow-1';

        if (role === 'assistant') {
            bubble.innerHTML = marked.parse(text);
        } else {
            bubble.textContent = text;
        }

        messageElement.appendChild(avatar);
        messageElement.appendChild(bubble);
        this.chatMessages.appendChild(messageElement);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    toggleSendingState(isSending) {
        this.isSending = isSending;
        this.sendButton.disabled = isSending;
        this.messageInput.disabled = isSending;
        this.sendButton.innerHTML = isSending
            ? '<i class="fa-solid fa-spinner fa-spin"></i><span>Enviando</span>'
            : '<i class="fa-solid fa-paper-plane"></i><span>Enviar</span>';
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        const token = localStorage.getItem('token');

        if (!message || this.isSending) {
            return;
        }

        if (!token) {
            window.location.href = 'login.html';
            return;
        }

        this.addMessage('user', message);
        this.messageInput.value = '';
        this.autoResize();
        this.toggleSendingState(true);
        this.setStatus('A IA esta organizando a resposta...');

        try {
            const response = await fetch(`${API_URL}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token
                },
                body: JSON.stringify({ message })
            });

            const data = await response.json().catch(() => ({}));

            if (response.status === 401) {
                localStorage.removeItem('token');
                window.location.href = 'login.html';
                return;
            }

            if (!response.ok) {
                throw new Error(data.erro || 'Erro ao conversar com a IA.');
            }

            this.addMessage('assistant', data.reply || 'A IA nao retornou nenhuma resposta.');
            this.setStatus('');
        } catch (error) {
            console.error('Erro no chat:', error);
            this.addMessage('assistant', `Desculpe, ocorreu um problema: ${error.message}`);
            this.setStatus('Nao foi possivel concluir a resposta agora.');
        } finally {
            this.toggleSendingState(false);
            this.messageInput.focus();
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ChatManager();
});
