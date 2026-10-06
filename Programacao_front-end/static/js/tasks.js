class TaskManager {
    constructor() {
        this.selectedDate = document.getElementById('selectedDate');
        this.form = document.getElementById('taskForm');
        this.formTitle = document.getElementById('taskFormTitle');
        this.taskInput = document.getElementById('taskInput');
        this.timeInput = document.getElementById('timeInput');
        this.deadlineInput = document.getElementById('deadlineInput');
        this.addTaskButton = document.getElementById('addTaskButton');
        this.cancelEditButton = document.getElementById('cancelEditButton');
        this.editDateField = document.getElementById('editDateField');
        this.editTaskDate = document.getElementById('editTaskDate');
        this.repeatFields = document.getElementById('repeatFields');
        this.repeatFrequency = document.getElementById('repeatFrequency');
        this.repeatUntilField = document.getElementById('repeatUntilField');
        this.repeatUntil = document.getElementById('repeatUntil');
        this.taskList = document.getElementById('taskList');
        this.loadStatus = document.getElementById('taskLoadStatus');
        this.retryButton = document.getElementById('retryTasksButton');
        this.statusMessage = document.getElementById('statusMessage');
        this.focusToggle = document.getElementById('focusToggle');
        this.loadVersion = 0;
        this.editingId = null;
        this.busy = false;
        this.listLoading = false;
        this.renderedDate = null;
        this.viewMode = 'day';
        this.dayViewButton = document.getElementById('dayViewButton');
        this.weekViewButton = document.getElementById('weekViewButton');
        this.weekNav = document.getElementById('taskWeekNav');
        this.weekRange = document.getElementById('taskWeekRange');
        this.calendarButtons = [this.dayViewButton, this.weekViewButton,
            ...this.weekNav.querySelectorAll('button')];
        this.init();
    }

    init() {
        this.dayViewButton.addEventListener('click', () => this.setView('day'));
        this.weekViewButton.addEventListener('click', () => this.setView('week'));
        document.getElementById('previousTaskWeek').addEventListener('click', () => this.navigateDate(CalendarDates.add(this.selectedDate.value, -7)));
        document.getElementById('nextTaskWeek').addEventListener('click', () => this.navigateDate(CalendarDates.add(this.selectedDate.value, 7)));
        document.getElementById('currentTaskWeek').addEventListener('click', () => this.navigateDate(this.getTodayDateInput()));
        [this.timeInput, this.deadlineInput].forEach(input => {
            input.addEventListener('blur', () => this.normalizeTimeInput(input));
        });
        this.form.addEventListener('submit', event => {
            event.preventDefault();
            this.addTask();
        });
        this.cancelEditButton.addEventListener('click', () => {
            this.clearEditor();
            this.showStatus('Edição cancelada.', 'neutral');
        });
        this.repeatFrequency.addEventListener('change', () => this.updateRepeatFields());
        this.retryButton.addEventListener('click', () => this.renderTasks(this.selectedDate.value));
        if (!this.selectedDate.value) this.selectedDate.value = this.getTodayDateInput();
        this.selectedDate.addEventListener('change', () => {
            if (!this.selectedDate.value) return;
            if (this.editingId !== null) this.clearEditor();
            this.updateRepeatFields();
            this.renderTasks(this.selectedDate.value);
        });
        this.focusToggle.addEventListener('click', () => {
            document.body.classList.toggle('focus-mode');
            const enabled = document.body.classList.contains('focus-mode');
            this.focusToggle.textContent = enabled ? 'Sair do modo foco' : 'Modo foco';
            this.showStatus(enabled ? 'Modo foco ativado. Apenas o essencial na tela.' : 'Modo padrão restaurado.');
        });
        this.updateRepeatFields();
        this.renderTasks(this.selectedDate.value);
    }

    updateRepeatFields() {
        const repeating = this.repeatFrequency.value !== 'none';
        this.repeatUntilField.hidden = !repeating;
        this.repeatUntil.min = this.selectedDate.value;
        const end = new Date(this.selectedDate.value + 'T12:00:00');
        if (!Number.isNaN(end.getTime())) {
            end.setDate(end.getDate() + 365);
            this.repeatUntil.max = this.formatDate(end);
        }
    }

    applyBusyState() {
        this.selectedDate.disabled = this.busy;
        this.calendarButtons.forEach(button => { button.disabled = this.busy; });
        Array.from(this.form.elements).forEach(element => { element.disabled = this.busy; });
        this.taskList.querySelectorAll('button').forEach(button => {
            button.disabled = this.busy || this.listLoading;
        });
        this.retryButton.disabled = this.busy || this.listLoading;
        this.taskList.setAttribute('aria-busy', String(this.listLoading || this.busy));
    }

    async fetchTasks(date) {
        const tasks = await apiRequest('/tarefas?date=' + encodeURIComponent(date));
        if (!Array.isArray(tasks)) throw new ApiError('O servidor retornou uma lista inválida.');
        return tasks;
    }

    setView(mode) {
        if (this.busy || mode === this.viewMode) return;
        if (!this.selectedDate.value) {
            this.showStatus('Escolha um dia para abrir a agenda.', 'warning');
            this.selectedDate.focus();
            return;
        }
        this.viewMode = mode;
        this.renderTasks(this.selectedDate.value);
    }

    navigateDate(date) {
        if (this.busy) return;
        if (!date) {
            this.showStatus('Escolha um dia válido para abrir a semana.', 'warning');
            return;
        }
        this.selectedDate.value = date;
        if (this.editingId !== null) this.clearEditor();
        this.updateRepeatFields();
        this.renderTasks(date);
    }

    updateView(date) {
        const weekly = this.viewMode === 'week';
        this.dayViewButton.setAttribute('aria-pressed', String(!weekly));
        this.weekViewButton.setAttribute('aria-pressed', String(weekly));
        this.weekNav.hidden = !weekly;
        document.body.classList.toggle('week-view', weekly);
        this.taskList.classList.toggle('week-grid', weekly);
        document.getElementById('tasksTitle').textContent = weekly ? 'Sua semana, um dia de cada vez' : 'Tarefas do dia';
        document.getElementById('tasksDescription').textContent = weekly
            ? 'Veja o que vem pela frente. Toque no dia para olhar só para ele.'
            : 'Conclua, adie ou remova sem perder de vista o que é prioridade.';
        if (weekly) {
            const days = CalendarDates.week(date);
            this.weekRange.textContent = CalendarDates.label(days[0]) + ' — ' + CalendarDates.label(days[6], { day: '2-digit', month: 'short', year: 'numeric' });
        }
    }

    renderWeek(days) {
        days.forEach(day => {
            const item = document.createElement('li');
            item.className = 'week-day' + (day.date === this.selectedDate.value ? ' week-day-selected' : '');
            const heading = document.createElement('div');
            heading.className = 'week-day-heading';
            const title = document.createElement('h3');
            const openDay = document.createElement('button');
            openDay.type = 'button';
            openDay.textContent = CalendarDates.label(day.date, { weekday: 'long', day: '2-digit', month: '2-digit' });
            openDay.setAttribute('aria-label', 'Ver tarefas de ' + openDay.textContent);
            openDay.addEventListener('click', () => {
                if (this.busy || this.listLoading) return;
                this.selectedDate.value = day.date;
                if (this.editingId !== null) this.clearEditor();
                this.updateRepeatFields();
                this.setView('day');
                document.getElementById('tasksTitle').scrollIntoView({ block: 'nearest' });
            });
            title.appendChild(openDay);
            const count = document.createElement('small');
            const pending = day.tasks.filter(task => !task.completed).length;
            count.textContent = day.tasks.length ? pending
                ? pending + (pending === 1 ? ' pendente' : ' pendentes')
                : day.tasks.length + (day.tasks.length === 1 ? ' concluída' : ' concluídas') : '';
            heading.append(title, count);
            item.appendChild(heading);
            if (!day.tasks.length) {
                const empty = document.createElement('p');
                empty.className = 'week-empty';
                empty.textContent = 'Sem tarefas por aqui.';
                item.appendChild(empty);
            } else {
                const list = document.createElement('ul');
                list.className = 'list-unstyled mb-0';
                day.tasks.forEach(task => this.renderTask(task, list));
                item.appendChild(list);
            }
            this.taskList.appendChild(item);
        });
    }

    async removeTask(taskId) {
        return apiRequest('/tarefas/' + taskId, { method: 'DELETE' });
    }

    async toggleComplete(taskId, completed) {
        return apiRequest('/tarefas/' + taskId + '/concluir', {
            method: 'POST', body: JSON.stringify({ completed })
        });
    }

    async performTaskAction(action, message) {
        if (this.busy || this.listLoading) return;
        this.busy = true;
        this.applyBusyState();
        try {
            await action();
            const loaded = await this.renderTasks(this.selectedDate.value);
            this.showStatus(loaded ? message : 'Alteração salva. Tente carregar a agenda novamente.', loaded ? 'positive' : 'warning');
        } catch (error) {
            if (error.status !== 401) this.showStatus(error.message, 'warning');
        } finally {
            this.busy = false;
            this.applyBusyState();
        }
    }

    async renderTasks(date) {
        const version = ++this.loadVersion;
        const mode = this.viewMode;
        const key = mode === 'week' ? 'week:' + CalendarDates.week(date)[0] : date;
        this.updateView(date);
        this.listLoading = true;
        this.loadStatus.textContent = 'Carregando tarefas…';
        this.loadStatus.classList.remove('task-load-error');
        this.retryButton.hidden = true;
        if (this.renderedDate !== key) {
            this.taskList.replaceChildren();
            this.renderedDate = null;
            progressManager.unavailable('Carregando o progresso do dia…');
        }
        this.applyBusyState();
        dashboardManager.update(date);
        if (this.progressDate !== date) progressManager.unavailable('Carregando o progresso do dia…');
        try {
            let tasks, days;
            if (mode === 'week') {
                const data = await apiRequest('/tarefas/semana?date=' + encodeURIComponent(date));
                const expected = CalendarDates.week(date);
                if (!Array.isArray(data?.days) || data.days.length !== 7 || data.days.some((day, index) => day.date !== expected[index] || !Array.isArray(day.tasks))) {
                    throw new ApiError('Não foi possível ler a semana. Tente carregar novamente.');
                }
                days = data.days;
                tasks = days.find(day => day.date === date).tasks;
            } else {
                tasks = await this.fetchTasks(date);
            }
            if (version !== this.loadVersion || date !== this.selectedDate.value || mode !== this.viewMode) return false;
            this.taskList.replaceChildren();
            if (mode === 'week') this.renderWeek(days);
            if (mode === 'day' && tasks.length === 0) {
                const empty = document.createElement('li');
                empty.className = 'task-empty-state';
                empty.innerHTML = '<i class="fa-regular fa-calendar-check" aria-hidden="true"></i><strong>Nenhuma tarefa para este dia</strong><p class="mb-0 mt-2">Adicione um pequeno passo para começar.</p>';
                this.taskList.appendChild(empty);
            }
            if (mode === 'day') tasks.forEach(task => this.renderTask(task));
            this.renderedDate = key;
            this.loadStatus.textContent = '';
            progressManager.update(tasks);
            this.progressDate = date;
            return true;
        } catch (error) {
            if (version !== this.loadVersion || date !== this.selectedDate.value || mode !== this.viewMode || error.status === 401) return false;
            const snapshot = this.renderedDate === key ? ' A lista exibida é a última carregada.' : '';
            this.loadStatus.textContent = error.message + snapshot;
            this.loadStatus.classList.add('task-load-error');
            this.retryButton.hidden = false;
            if (this.renderedDate !== key || this.progressDate !== date) progressManager.unavailable();
            return false;
        } finally {
            if (version === this.loadVersion) {
                this.listLoading = false;
                this.applyBusyState();
            }
        }
    }

    renderTask(task, target = this.taskList) {
        const li = document.createElement('li');
        li.className = 'task-item d-flex flex-column flex-sm-row flex-lg-column flex-xl-row align-items-sm-center align-items-lg-stretch align-items-xl-center gap-2 p-3 fade-in';
        li.innerHTML = '<div class="task-details d-flex flex-column flex-grow-1 gap-1"><span class="fw-bold"></span><span class="time fw-semibold"></span><span class="time fw-semibold"></span></div><div class="task-actions d-flex flex-wrap justify-content-end gap-2"><button type="button" class="btn ghost-btn edit-btn fw-bold">Editar</button><button type="button" class="btn delete-btn fw-bold">Remover</button><button type="button" class="btn check-btn fw-bold"></button></div>';
        const details = li.querySelectorAll('.task-details span');
        details[0].textContent = task.text;
        details[1].textContent = 'Horário: ' + task.time;
        details[2].textContent = 'Concluir até: ' + task.deadline;
        const checkButton = li.querySelector('.check-btn');
        checkButton.textContent = task.completed ? 'Desfazer' : 'Concluir';
        checkButton.addEventListener('click', () => this.performTaskAction(
            () => this.toggleComplete(task.id, !task.completed),
            task.completed ? 'Tarefa reaberta. Reorganize o foco.' : 'Bom trabalho! Você concluiu uma tarefa.'
        ));
        li.querySelector('.delete-btn').addEventListener('click', () => this.performTaskAction(
            async () => {
                await this.removeTask(task.id);
                if (this.editingId === task.id) this.clearEditor();
            }, 'Tarefa removida.'
        ));
        li.querySelector('.edit-btn').addEventListener('click', () => this.startEdit(task));
        if (task.completed) li.classList.add('task-done', 'pulse-success');
        target.appendChild(li);
    }

    startEdit(task) {
        if (this.busy || this.listLoading) return;
        if (task.date && task.date !== this.selectedDate.value) {
            this.selectedDate.value = task.date;
            this.updateRepeatFields();
            this.renderTasks(task.date);
        }
        this.editingId = task.id;
        this.formTitle.textContent = 'Editar tarefa';
        this.taskInput.value = task.text;
        this.timeInput.value = task.time.slice(0, 5);
        this.deadlineInput.value = task.deadline.slice(0, 5);
        this.editTaskDate.value = this.selectedDate.value;
        this.editDateField.hidden = false;
        this.repeatFields.hidden = true;
        this.cancelEditButton.hidden = false;
        this.addTaskButton.textContent = 'Salvar alterações';
        this.taskInput.focus();
    }

    clearEditor() {
        this.editingId = null;
        this.form.reset();
        this.formTitle.textContent = 'Adicionar tarefa';
        this.addTaskButton.textContent = 'Adicionar tarefa';
        this.cancelEditButton.hidden = true;
        this.editDateField.hidden = true;
        this.repeatFields.hidden = false;
        this.updateRepeatFields();
    }

    normalizeTimeInput(input) {
        const value = input.value.trim();
        const match = /^(\d{1,2})(?::(\d{2})?)?$/.exec(value);
        if (match && Number(match[1]) < 24 && Number(match[2] || '00') < 60) {
            input.value = match[1].padStart(2, '0') + ':' + (match[2] || '00');
        }
        return input.value.trim();
    }

    async addTask() {
        if (this.busy) return;
        const editing = this.editingId !== null;
        const date = editing ? this.editTaskDate.value : this.selectedDate.value;
        const text = this.taskInput.value.trim();
        const time = this.normalizeTimeInput(this.timeInput);
        const deadline = this.normalizeTimeInput(this.deadlineInput);
        if (!date || !text || !time || !deadline) {
            this.showStatus('Preencha a tarefa, o dia e os horários.', 'warning');
            return;
        }
        if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(time) || !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(deadline)) {
            this.showStatus('Informe horários válidos, como 08:00 ou 18:30.', 'warning');
            return;
        }
        if (deadline < time) {
            this.showStatus('O prazo deve ser igual ou posterior ao horário de início.', 'warning');
            return;
        }
        const payload = { text, date, time, deadline };
        if (!editing && this.repeatFrequency.value !== 'none') {
            if (!this.repeatUntil.value) {
                this.showStatus('Escolha a data final da repetição.', 'warning');
                return;
            }
            payload.repeat = { frequency: this.repeatFrequency.value, until: this.repeatUntil.value };
        }
        this.busy = true;
        this.applyBusyState();
        try {
            const result = await apiRequest(editing ? '/tarefas/' + this.editingId : '/tarefas', {
                method: editing ? 'PUT' : 'POST', body: JSON.stringify(payload)
            });
            this.clearEditor();
            this.selectedDate.value = date;
            this.updateRepeatFields();
            const loaded = await this.renderTasks(date);
            const message = editing ? 'Tarefa atualizada.' : result.created > 1
                ? result.created + ' tarefas criadas até ' + new Date(payload.repeat.until + 'T12:00:00').toLocaleDateString('pt-BR') + '.'
                : 'Tarefa adicionada! Comece pelo primeiro passo.';
            this.showStatus(loaded ? message : 'Tarefa salva. Tente carregar a agenda novamente.', loaded ? 'positive' : 'warning');
        } catch (error) {
            if (error.status !== 401) this.showStatus(error.message, 'warning');
        } finally {
            this.busy = false;
            this.applyBusyState();
        }
    }

    showStatus(message, tone = 'positive') {
        clearTimeout(this.statusTimer);
        this.statusMessage.style.color = { positive: '#0f7a8c', neutral: '#4a6072', warning: '#b52e46' }[tone];
        this.statusMessage.textContent = message;
        this.statusMessage.classList.remove('hide');
        if (tone !== 'warning') this.statusTimer = setTimeout(() => this.statusMessage.classList.add('hide'), 5000);
    }

    formatDate(date) {
        return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
    }

    getTodayDateInput() {
        return CalendarDates.today();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new TaskManager();
});
