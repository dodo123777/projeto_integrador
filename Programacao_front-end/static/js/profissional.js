(() => {
    'use strict';
    const baseURL = ['localhost', '127.0.0.1'].includes(location.hostname)
        ? 'http://localhost:5001' : 'https://projeto-integrador-uvxi.onrender.com';
    const $ = (id) => document.getElementById(id);
    const labels = { agendada: 'Agendada', confirmada: 'Confirmada', em_atendimento: 'Em atendimento', finalizada: 'Finalizada', cancelada: 'Cancelada' };
    const actions = { agendada: [['confirmada', 'Confirmar'], ['cancelada', 'Cancelar']], confirmada: [['em_atendimento', 'Iniciar'], ['cancelada', 'Cancelar']], em_atendimento: [['finalizada', 'Finalizar']] };
    const pages = { inicio: ['Início', 'Seu dia de atendimento, com espaço para cuidar de cada pessoa.'], pacientes: ['Pacientes', 'Pessoas vinculadas ao seu acompanhamento.'], agenda: ['Agenda / Consultas', 'Consulte sua agenda e organize novos atendimentos.'], semana: ['Minha semana', 'Veja os próximos dias e organize um atendimento de cada vez.'], atendimentos: ['Atendimentos', 'Histórico das consultas finalizadas por você.'], perfil: ['Perfil profissional', 'Seus dados cadastrados na plataforma.'] };
    let profile;
    const isAdmin = () => profile?.tipo === 'admin';
    let generation = 0;
    let searchTimer;
    let weekDate = CalendarDates.today();
    const escape = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const formatDate = (value) => value ? new Date(value).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' }) : '—';
    const empty = (message) => `<div class="empty-state"><i class="fa-regular fa-calendar" aria-hidden="true"></i>${escape(message)}</div>`;
    const badge = (status) => `<span class="status-badge status-${escape(status)}">${escape(labels[status] || status)}</span>`;

    function clearPrivateContent() {
        generation++;
        $('professionalApp').hidden = true;
        $('pageContent').replaceChildren();
        $('patientDetails').replaceChildren();
        $('patientDialog').close();
        profile = null;
    }

    function logout() {
        localStorage.removeItem('token');
        clearPrivateContent();
        location.replace('login.html');
    }

    async function api(path, options = {}) {
        const token = localStorage.getItem('token');
        if (!token) { logout(); throw new Error('Entre novamente para continuar.'); }
        const response = await fetch(`${baseURL}/profissional${path}`, {
            ...options, cache: 'no-store',
            headers: { Authorization: token, ...(options.body ? { 'Content-Type': 'application/json' } : {}) }
        });
        if (localStorage.getItem('token') !== token) throw new Error('A sessão foi alterada. Atualize a página.');
        if (response.status === 401) { logout(); throw new Error('Sua sessão expirou.'); }
        const data = response.status === 204 ? null : await response.json();
        if (response.status === 403 && data?.codigo !== 'paciente_nao_vinculado') {
            clearPrivateContent();
            $('accessState').hidden = false;
            $('accessMessage').textContent = 'Este espaço é para psicólogos habilitados e administradores do InfoHelp.';
            $('retryAccess').hidden = true;
        }
        if (!response.ok) {
            const error = new Error(data?.erro || 'Não foi possível carregar os dados.');
            error.status = response.status;
            throw error;
        }
        return data;
    }

    function feedback(message = '', error = false) {
        $('feedback').textContent = message;
        $('feedback').classList.toggle('error', error);
    }

    function appointmentsTable(rows, editable = false) {
        editable = editable && !isAdmin();
        if (!rows.length) return empty('Nenhum atendimento para exibir.');
        return `<div class="table-wrap"><table class="professional-table"><thead><tr><th scope="col">Data e horário</th><th scope="col">Paciente</th>${isAdmin() ? '<th scope="col">Psicólogo</th>' : ''}<th scope="col">Tipo</th><th scope="col">Status</th>${editable ? '<th scope="col">Ações</th>' : ''}</tr></thead><tbody>${rows.map(row => `<tr><td>${escape(formatDate(row.inicio))}</td><td><button class="btn ghost-btn" data-patient="${row.paciente_id}">${escape(row.paciente)}</button></td>${isAdmin() ? `<td>${escape(row.profissional)}</td>` : ''}<td>${escape(row.tipo)}</td><td>${badge(row.status)}</td>${editable ? `<td><div class="d-flex gap-2">${(actions[row.status] || []).map(([status, label]) => `<button class="btn ghost-btn" data-appointment="${row.id}" data-status="${status}">${label}</button>`).join('')}</div></td>` : ''}</tr>`).join('')}</tbody></table></div>`;
    }

    function patientsTable(rows) {
        if (!rows.length) return empty(isAdmin() ? 'Nenhum paciente encontrado.' : 'Nenhum paciente encontrado. Os vínculos são habilitados pela equipe responsável, com autorização do paciente.');
        return `<div class="table-wrap"><table class="professional-table"><thead><tr><th scope="col">Paciente</th><th scope="col">Último atendimento</th><th scope="col">Próximo atendimento</th><th scope="col">${isAdmin() ? 'Conta' : 'Vínculo'}</th></tr></thead><tbody>${rows.map(row => `<tr><td><button class="btn ghost-btn" data-patient="${row.id}">${escape(row.nome)}</button></td><td>${escape(formatDate(row.ultimo_atendimento))}</td><td>${escape(formatDate(row.proximo_atendimento))}</td><td>${isAdmin() ? `<span class="status-badge ${row.ativo === false ? 'status-cancelada' : 'status-confirmada'}">${row.ativo === false ? 'Bloqueada' : 'Ativa'}</span>` : '<span class="status-badge status-confirmada">Vinculado</span>'}</td></tr>`).join('')}</tbody></table></div>`;
    }

    function appointmentCards(rows, editable = false) {
        editable = editable && !isAdmin();
        return rows.map(row => {
            const time = new Date(row.inicio).toLocaleTimeString('pt-BR', { timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit' });
            return `<article class="consultation-card"><time class="consultation-time" datetime="${escape(row.inicio)}">${escape(time)}</time><div class="consultation-details"><button type="button" class="btn ghost-btn" data-patient="${row.paciente_id}">${escape(row.paciente)}</button><p>${escape(row.tipo)}</p>${isAdmin() ? `<p>Psicólogo(a): ${escape(row.profissional)}</p>` : ''}${badge(row.status)}${editable ? `<div class="d-flex flex-wrap gap-2 mt-2">${(actions[row.status] || []).map(([status, label]) => `<button type="button" class="btn ghost-btn" data-appointment="${row.id}" data-status="${status}">${label}</button>`).join('')}</div>` : ''}</div></article>`;
        }).join('');
    }

    function weeklyAppointments(rows) {
        const days = CalendarDates.week(weekDate);
        const today = CalendarDates.today();
        const range = CalendarDates.label(days[0]) + ' — ' + CalendarDates.label(days[6], { day: '2-digit', month: 'short', year: 'numeric' });
        return `<section class="card panel professional-week"><div class="panel-heading"><div><h2 class="section-title">${isAdmin() ? 'Semana de todos os atendimentos' : 'Sua semana de atendimentos'}</h2><p class="helper-text mb-0 mt-2">Horários de Brasília. Abra o nome para ver o paciente.</p></div>${isAdmin() ? '' : '<a class="btn ghost-btn" href="#agenda">Agendar consulta</a>'}</div><div class="week-navigation"><p class="week-range" id="professionalWeekRange">${escape(range)}</p><div class="week-buttons"><button type="button" class="btn ghost-btn" id="previousProfessionalWeek" aria-label="Semana anterior"><i class="fa-solid fa-chevron-left" aria-hidden="true"></i></button><button type="button" class="btn ghost-btn" id="currentProfessionalWeek">Esta semana</button><button type="button" class="btn ghost-btn" id="nextProfessionalWeek" aria-label="Próxima semana"><i class="fa-solid fa-chevron-right" aria-hidden="true"></i></button></div></div><div class="mt-3"><label class="form-label" for="professionalWeekDate">Escolha um dia para abrir a semana</label><input class="form-control" type="date" id="professionalWeekDate" value="${escape(weekDate)}"></div><div class="week-grid">${days.map(day => {
            const appointments = rows.filter(row => CalendarDates.appointmentDay(row.inicio) === day);
            const label = CalendarDates.label(day, { weekday: 'long', day: '2-digit', month: '2-digit' });
            return `<section class="week-day ${day === today ? 'week-day-selected' : ''}" data-date="${day}" aria-label="${escape(label)}"><div class="week-day-heading"><h3>${escape(label)}${day === today ? ' · Hoje' : ''}</h3><small>${appointments.length ? appointments.length + (appointments.length === 1 ? ' consulta' : ' consultas') : ''}</small></div>${appointments.length ? appointmentCards(appointments, true) : '<p class="week-empty">Sem atendimentos marcados.</p>'}</section>`;
        }).join('')}</div></section>`;
    }

    async function render() {
        if (!profile) return;
        const version = ++generation;
        clearTimeout(searchTimer);
        const page = Object.hasOwn(pages, location.hash.slice(1)) ? location.hash.slice(1) : 'inicio';
        document.querySelectorAll('[data-page]').forEach(link => {
            if (link.dataset.page === page) link.setAttribute('aria-current', 'page');
            else link.removeAttribute('aria-current');
        });
        $('pageTitle').textContent = page === 'inicio' ? `Olá, ${profile.nome}` : isAdmin() && page === 'semana' ? 'Semana de atendimentos' : pages[page][0];
        if (isAdmin() && page === 'perfil') $('pageTitle').textContent = 'Perfil administrativo';
        $('pageDescription').textContent = isAdmin() ? 'Visão administrativa de todos os psicólogos, pacientes e atendimentos.' : pages[page][1];
        $('pageContent').innerHTML = '<p class="helper-text" role="status">Carregando…</p>';
        $('pageContent').setAttribute('aria-busy', 'true');
        feedback();
        try {
            let html = '';
            if (page === 'inicio') {
                const data = await api('/dashboard');
                const metrics = [['hoje', 'Consultas de hoje'], ['proximos', 'Próximos atendimentos'], ['pacientes', isAdmin() ? 'Todos os pacientes' : 'Pacientes vinculados'], ['realizados', 'Atendimentos realizados']];
                html = `<div class="professional-today"><section class="card panel"><div class="panel-heading"><div><h2 class="section-title">Atendimentos de hoje</h2><p class="helper-text mt-2 mb-0">${escape(CalendarDates.label(CalendarDates.today(), { weekday: 'long', day: '2-digit', month: 'long' }))}</p></div></div>${data.hoje?.length ? appointmentCards(data.hoje) : empty('Nenhum atendimento marcado para hoje.')}</section><section class="card panel professional-week-shortcut"><h2 class="section-title">${isAdmin() ? 'Semana de atendimentos' : 'Minha semana'}</h2><p class="mt-2">Um olhar para os próximos dias ajuda a preparar cada encontro.</p><a href="#semana" class="btn ghost-btn">Ver atendimentos da semana</a></section></div><div class="metric-grid">${metrics.map(([key, label], i) => `<article class="card metric-card ${i === 0 ? 'highlight' : ''}"><span>${label}</span><strong>${escape(data.resumo[key])}</strong></article>`).join('')}</div><section class="card panel"><div class="panel-heading"><h2 class="section-title">Próximos atendimentos</h2><a class="btn ghost-btn" href="#agenda">Ver agenda</a></div>${appointmentsTable(data.proximos)}</section>`;
            } else if (page === 'semana') {
                const rows = await api('/consultas?semana=' + encodeURIComponent(weekDate));
                if (!Array.isArray(rows)) throw new Error('Não foi possível ler a semana. Tente novamente.');
                html = weeklyAppointments(rows);
            } else if (page === 'pacientes') {
                const rows = await api('/pacientes');
                html = `<section class="card panel"><div class="filter-bar"><div><label for="patientSearch" class="form-label">Buscar por nome</label><input id="patientSearch" class="form-control" type="search" maxlength="120" placeholder="Nome do paciente" autocomplete="off"></div></div><div id="patientsResult">${patientsTable(rows)}</div></section>`;
            } else if (page === 'agenda' || page === 'atendimentos') {
                const rows = await api(page === 'atendimentos' ? '/consultas?historico=1' : '/consultas');
                html = `<section class="card panel">${page === 'agenda' ? '<div class="panel-heading"><h2 class="section-title">Consultas</h2>' + (isAdmin() ? '' : '<button id="newAppointment" class="btn primary-btn">Agendar consulta</button>') + '</div><div id="appointmentFormContainer" hidden></div><form id="dateFilter" class="filter-bar"><div><label for="appointmentDate" class="form-label">Filtrar por data</label><input id="appointmentDate" class="form-control" type="date"></div><button class="btn ghost-btn" type="submit">Filtrar</button><button id="clearDate" class="btn ghost-btn" type="button">Todas</button></form>' : '<h2 class="section-title mb-3">Histórico de atendimentos</h2>'}<div id="appointmentsResult">${appointmentsTable(rows, page === 'agenda')}</div></section>`;
            } else {
                const fields = isAdmin() ? [['Nome', profile.nome], ['Perfil', 'Administrador(a)'], ['E-mail', profile.email]] : [['Nome', profile.nome], ['Profissão', 'Psicólogo(a)'], ['Registro profissional', profile.registro], ['Especialidade', profile.especialidade || 'Não informada'], ['E-mail', profile.email]];
                html = `<section class="card panel"><dl class="profile-grid">${fields.map(([label, value]) => `<div><dt>${label}</dt><dd>${escape(value)}</dd></div>`).join('')}</dl>${isAdmin() ? '<p class="helper-text mt-4 mb-0">Você está usando seu perfil de administrador. Volte ao ADM para gerenciar contas e vínculos.</p>' : '<p class="helper-text mt-4 mb-0">Para atualizar seus dados profissionais, entre em contato com a equipe responsável pela plataforma.</p>'}</section>`;
            }
            if (version === generation) $('pageContent').innerHTML = html;
        } catch (error) {
            if (version === generation) {
                $('pageContent').innerHTML = profile ? '<button type="button" id="retryProfessionalPage" class="btn ghost-btn">Tentar carregar novamente</button>' : '';
                feedback(error.message, true);
            }
        } finally {
            if (version === generation) $('pageContent').setAttribute('aria-busy', 'false');
        }
    }

    async function showPatient(id) {
        const dialog = $('patientDialog');
        $('patientTitle').textContent = 'Paciente';
        $('patientDetails').textContent = 'Carregando…';
        if (!dialog.open) dialog.showModal();
        try {
            const data = await api(`/pacientes/${id}`);
            if (!profile || !dialog.open) return;
            $('patientTitle').textContent = data.paciente.nome;
            $('patientDetails').innerHTML = `<p class="helper-text mt-3">${isAdmin() ? 'Histórico com todos os profissionais.' : 'Histórico de consultas com você.'}</p>${appointmentsTable(data.consultas)}<p class="helper-text mt-3">Tarefas pessoais e conversas com a IA permanecem privadas.</p>`;
        } catch (error) { $('patientDetails').textContent = error.message; }
    }

    async function showAppointmentForm() {
        const version = generation;
        const rows = await api('/pacientes');
        if (version !== generation) return;
        const container = $('appointmentFormContainer');
        container.hidden = false;
        if (!rows.length) { container.innerHTML = empty('É necessário ter um paciente vinculado para agendar.'); return; }
        const kind = 'Consulta psicológica';
        container.innerHTML = `<form id="appointmentForm" class="appointment-form mb-4"><div><label class="form-label" for="newPatient">Paciente</label><select id="newPatient" class="form-control" required><option value="">Selecione</option>${rows.map(row => `<option value="${row.id}">${escape(row.nome)}</option>`).join('')}</select></div><div><label class="form-label" for="newKind">Tipo de consulta</label><select id="newKind" class="form-control"><option>${kind}</option><option>Retorno</option></select></div><div><label class="form-label" for="newStart">Data e horário de Brasília</label><input id="newStart" type="datetime-local" class="form-control" required></div><div class="wide d-flex gap-2"><button class="btn primary-btn" type="submit">Salvar consulta</button><button id="cancelNew" class="btn ghost-btn" type="button">Fechar</button></div></form>`;
        $('newPatient').focus();
    }

    async function filterAppointments() {
        const version = generation;
        const rows = await api(`/consultas?data=${encodeURIComponent($('appointmentDate').value)}`);
        if (version === generation) $('appointmentsResult').innerHTML = appointmentsTable(rows, true);
    }

    $('pageContent').addEventListener('click', async event => {
        const button = event.target.closest('button');
        if (!button) return;
        feedback();
        try {
            if (button.dataset.patient) return await showPatient(button.dataset.patient);
            if (button.id === 'retryProfessionalPage') return await render();
            if (['previousProfessionalWeek', 'nextProfessionalWeek', 'currentProfessionalWeek'].includes(button.id)) {
                weekDate = button.id === 'currentProfessionalWeek' ? CalendarDates.today()
                    : CalendarDates.add(weekDate, button.id === 'previousProfessionalWeek' ? -7 : 7);
                return await render();
            }
            if (button.id === 'newAppointment') return await showAppointmentForm();
            if (button.id === 'cancelNew') { $('appointmentFormContainer').hidden = true; return; }
            if (button.id === 'clearDate') { $('appointmentDate').value = ''; return await filterAppointments(); }
            if (button.dataset.appointment) {
                if (button.dataset.status === 'cancelada' && !window.confirm('Cancelar esta consulta?')) return;
                button.disabled = true;
                await api(`/consultas/${button.dataset.appointment}/status`, { method: 'PATCH', body: JSON.stringify({ status: button.dataset.status }) });
                if ($('appointmentDate')) await filterAppointments();
                else await render();
                feedback('Status atualizado.');
            }
        } catch (error) { feedback(error.message, true); }
        finally { button.disabled = false; }
    });

    $('pageContent').addEventListener('submit', async event => {
        event.preventDefault();
        const submit = event.target.querySelector('[type="submit"]');
        submit.disabled = true;
        try {
            if (event.target.id === 'dateFilter') return await filterAppointments();
            if (event.target.id !== 'appointmentForm') return;
            await api('/consultas', { method: 'POST', body: JSON.stringify({ paciente_id: Number($('newPatient').value), tipo: $('newKind').value, inicio: `${$('newStart').value}:00-03:00` }) });
            await render();
            feedback('Consulta agendada.');
        } catch (error) { feedback(error.message, true); }
        finally { submit.disabled = false; }
    });

    let searchVersion = 0;
    $('pageContent').addEventListener('change', event => {
        if (event.target.id === 'professionalWeekDate' && event.target.value) {
            weekDate = event.target.value;
            render();
        }
    });
    $('pageContent').addEventListener('input', event => {
        if (event.target.id !== 'patientSearch') return;
        const value = event.target.value;
        const requestVersion = ++searchVersion;
        const pageVersion = generation;
        clearTimeout(searchTimer);
        searchTimer = setTimeout(async () => {
            try {
                const rows = await api(`/pacientes?busca=${encodeURIComponent(value)}`);
                if (pageVersion === generation && requestVersion === searchVersion) $('patientsResult').innerHTML = patientsTable(rows);
            } catch (error) { if (pageVersion === generation) feedback(error.message, true); }
        }, 250);
    });

    async function boot() {
        $('retryAccess').hidden = true;
        $('accessMessage').textContent = 'Verificando seu acesso…';
        try {
            profile = await api('/me');
            $('backToAdmin').hidden = !isAdmin();
            document.querySelector('.sidebar-heading').textContent = isAdmin() ? 'ADM · ATENDIMENTOS' : 'ÁREA DO PROFISSIONAL';
            document.querySelector('.privacy-note').textContent = isAdmin() ? 'Visão de todos os atendimentos. Horários de Brasília.' : 'Apenas pacientes vinculados a você. Horários de Brasília.';
            document.querySelector('[data-page="semana"]').lastChild.textContent = isAdmin() ? ' Semana de atendimentos' : ' Minha semana';
            $('accessState').hidden = true;
            $('professionalApp').hidden = false;
            await render();
        } catch (error) {
            if (error.status === 403) return;
            $('accessMessage').textContent = error.message;
            $('retryAccess').hidden = false;
        }
    }
    $('retryAccess').addEventListener('click', boot);
    $('refreshProfessional').addEventListener('click', render);
    $('professionalLogout').addEventListener('click', logout);
    $('closePatient').addEventListener('click', () => $('patientDialog').close());
    $('patientDetails').addEventListener('click', event => {
        const button = event.target.closest('[data-patient]');
        if (button) showPatient(button.dataset.patient);
    });
    $('menuToggle').addEventListener('click', () => {
        const expanded = $('menuToggle').getAttribute('aria-expanded') !== 'true';
        $('menuToggle').setAttribute('aria-expanded', String(expanded));
        document.querySelector('.professional-sidebar').classList.toggle('menu-open', expanded);
    });
    window.addEventListener('hashchange', () => {
        $('menuToggle').setAttribute('aria-expanded', 'false');
        document.querySelector('.professional-sidebar').classList.remove('menu-open');
        $('content').focus();
        render();
    });
    window.addEventListener('storage', event => { if (event.key === 'token') { clearPrivateContent(); boot(); } });
    window.addEventListener('pageshow', event => { if (event.persisted) { clearPrivateContent(); boot(); } });
    boot();
})();
