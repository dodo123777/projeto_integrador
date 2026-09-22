const API_URL = ['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? 'http://localhost:5000'
    : 'https://projeto-integrador-uvxi.onrender.com';

class TaskManager {
    constructor() {
        this.token = localStorage.getItem('token');
        this.selectedDate = document.getElementById('selectedDate');
        this.taskInput = document.getElementById('taskInput');
        this.timeInput = document.getElementById('timeInput');
        this.deadlineInput = document.getElementById('deadlineInput');
        this.addTaskButton = document.getElementById('addTaskButton');
        this.taskList = document.getElementById('taskList');
        this.statusMessage = document.getElementById('statusMessage');
        this.focusToggle = document.getElementById('focusToggle');

        this.init();
    }

    init() {
        // Botão de adicionar tarefa
        this.addTaskButton.addEventListener('click', () => this.addTask());

        if (!this.selectedDate.value) {
            this.selectedDate.value = this.getTodayDateInput();
        }

        // Quando mudar a data, recarrega tarefas daquele dia
        this.selectedDate.addEventListener('change', () => {
            const date = this.selectedDate.value;
            if (date) this.renderTasks(date);
        });

        // Modo foco para reduzir distrações visuais
        if (this.focusToggle) {
            this.focusToggle.addEventListener('click', () => {
                document.body.classList.toggle('focus-mode');
                const focusEnabled = document.body.classList.contains('focus-mode');
                this.focusToggle.textContent = focusEnabled ? 'Sair do modo foco' : 'Modo foco';
                this.showStatus(focusEnabled ? 'Modo foco ativado. Apenas o essencial na tela.' : 'Modo padrão restaurado.');
            });
        }

        // Se já tiver uma data selecionada ao carregar, renderiza
        if (this.selectedDate.value) {
            this.renderTasks(this.selectedDate.value);
        }
    }

    _handleUnauthorized() {
        localStorage.removeItem('token');
        window.location.href = 'login.html';
    }

    async fetchTasks(date) {
        const resp = await fetch(`${API_URL}/tarefas?date=${encodeURIComponent(date)}`, {
            headers: {
                'Authorization': this.token
            }
        });
        if (resp.status === 401) {
            this._handleUnauthorized();
            return [];
        }
        if (!resp.ok) {
            console.error("Erro ao buscar tarefas:", await resp.text());
            return [];
        }
        return await resp.json();
    }

    async saveTask(task, date) {
        const response = await fetch(`${API_URL}/tarefas`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': this.token
            },
            body: JSON.stringify({
                text: task.text,
                time: task.time,
                deadline: task.deadline,
                date: date
            })
        });

        if (response.status === 401) {
            this._handleUnauthorized();
            return;
        }
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.erro || "Erro ao salvar tarefa!");
        }
        return await response.json();
    }

    async removeTask(taskId) {
        const resp = await fetch(`${API_URL}/tarefas/${taskId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': this.token
            }
        });
        if (resp.status === 401) this._handleUnauthorized();
    }

    async toggleComplete(taskId, completed) {
        const resp = await fetch(`${API_URL}/tarefas/${taskId}/concluir`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': this.token
            },
            body: JSON.stringify({ completed })
        });
        if (resp.status === 401) this._handleUnauthorized();
    }

    async renderTasks(date) {
        const tasks = await this.fetchTasks(date);
        this.taskList.innerHTML = "";

        tasks.forEach((task) => {
            const li = document.createElement('li');
            li.className = 'task-item d-flex flex-column flex-sm-row flex-lg-column flex-xl-row align-items-sm-center align-items-lg-stretch align-items-xl-center gap-2 p-3';

            li.innerHTML = `
                <div class="task-details d-flex flex-column flex-grow-1 gap-1">
                    <span class="fw-bold"></span>
                    <span class="time fw-semibold"></span>
                    <span class="time fw-semibold"></span>
                </div>
                <div class="task-actions d-flex flex-wrap justify-content-end gap-2">
                    <button class="btn delete-btn fw-bold">Remover</button>
                    <button class="btn check-btn fw-bold">${task.completed ? 'Desfazer' : 'Concluir'}</button>
                </div>
            `;

            const details = li.querySelectorAll('.task-details span');
            details[0].textContent = task.text;
            details[1].textContent = `Horário: ${task.time}`;
            details[2].textContent = `Concluir até: ${task.deadline}`;

            li.classList.add('fade-in');

            const checkButton = li.querySelector('.check-btn');
            const deleteButton = li.querySelector('.delete-btn');

            checkButton.addEventListener('click', async () => {
                await this.toggleComplete(task.id, !task.completed);
                this.showStatus(!task.completed ? 'Bom trabalho! Você concluiu uma tarefa.' : 'Tarefa reaberta. Reorganize o foco.');
                this.renderTasks(date);
            });

            deleteButton.addEventListener('click', async () => {
                await this.removeTask(task.id);
                this.showStatus('Tarefa removida.', 'neutral');
                this.renderTasks(date);
            });

            if (task.completed) {
                li.classList.add('task-done');
                li.classList.add('pulse-success');
            }

            this.taskList.appendChild(li);
        });

        // Atualiza barra de progresso, se existir
        if (typeof progressManager !== 'undefined') {
            progressManager.update(tasks);
        }

        if (typeof dashboardManager !== 'undefined') {
            dashboardManager.update(date);
        }
    }

    async addTask() {
        const taskText = this.taskInput.value.trim();
        const taskTime = this.timeInput.value.trim();
        const taskDeadline = this.deadlineInput.value.trim();
        const date = this.selectedDate.value;

        if (!date || !taskText || !taskTime || !taskDeadline) {
            alert("Preencha todos os campos!");
            return;
        }

        // Validar formato HH:MM
        if (!/^\d{2}:\d{2}$/.test(taskTime) || !/^\d{2}:\d{2}$/.test(taskDeadline)) {
            alert("Digite os horários no formato correto, ex: 13:30");
            return;
        }

        const task = {
            text: taskText,
            time: taskTime,
            deadline: taskDeadline,
            completed: false
        };

        try {
            await this.saveTask(task, date);

            // Limpar campos
            this.taskInput.value = "";
            this.timeInput.value = "";
            this.deadlineInput.value = "";

            // Recarregar lista
            this.renderTasks(date);
            this.showStatus('Tarefa adicionada! Comece pelo primeiro passo.');
        } catch (error) {
            console.error(error);
            this.showStatus(error.message, 'warning');
        }
    }

    showStatus(message, tone = 'positive') {
        if (!this.statusMessage) return;
        const colors = {
            positive: '#0f7a8c',
            neutral: '#4a6072',
            warning: '#b52e46'
        };

        this.statusMessage.style.color = colors[tone] || colors.positive;
        this.statusMessage.textContent = message;
        this.statusMessage.classList.remove('hide');

        clearTimeout(this.statusTimeout);
        this.statusTimeout = setTimeout(() => {
            this.statusMessage.classList.add('hide');
        }, 3200);
    }

    getTodayDateInput() {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
}

// Inicializa o gerenciador de tarefas quando a página estiver pronta
document.addEventListener('DOMContentLoaded', () => {
    new TaskManager();
});
