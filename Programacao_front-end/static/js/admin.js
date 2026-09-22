(() => {
    'use strict';
    const baseURL = ['localhost', '127.0.0.1'].includes(location.hostname)
        ? 'http://localhost:5000' : 'https://projeto-integrador-uvxi.onrender.com';
    const $ = id => document.getElementById(id);
    const pages = {
        dashboard: ['Dashboard', 'Indicadores de usuários, vínculos e consultas.'],
        usuarios: ['Usuários', 'Consulte contas e gerencie permissões e acesso.'],
        psicologos: ['Psicólogos', 'Perfis profissionais e pacientes vinculados.'],
        vinculos: ['Vínculos', 'Relações ativas e encerradas entre psicólogos e pacientes.'],
        perfil: ['Perfil administrativo', 'Dados da conta autenticada.']
    };
    const roleLabels = { paciente: 'Paciente', psicologo: 'Psicólogo(a)', admin: 'Administrador(a)' };
    let admin = null;
    let generation = 0;
    let listPage = 1;
    let search = '';
    let detailGeneration = 0;
    const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
    const date = value => value ? new Date(value).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' }) : '—';
    const statusBadge = active => `<span class="status-badge ${active ? 'status-confirmada' : 'status-cancelada'}">${active ? 'Ativo' : 'Bloqueado'}</span>`;
    const linkBadge = active => `<span class="status-badge ${active ? 'status-confirmada' : 'status-cancelada'}">${active ? 'Ativo' : 'Encerrado'}</span>`;
    const empty = message => `<div class="empty-state"><i class="fa-solid fa-inbox"></i>${escape(message)}</div>`;

    function feedback(message = '', error = false) {
        $('adminFeedback').textContent = message;
        $('adminFeedback').classList.toggle('error', error);
        $('adminDialogFeedback').textContent = $('adminDetailDialog').open ? message : '';
        $('adminDialogFeedback').classList.toggle('error', error);
    }

    function clearPrivate() {
        generation++;
        detailGeneration++;
        admin = null;
        $('adminApp').hidden = true;
        $('adminPage').replaceChildren();
        $('adminDialogBody').replaceChildren();
        if ($('adminDetailDialog').open) $('adminDetailDialog').close();
    }

    function logout() {
        localStorage.removeItem('token');
        clearPrivate();
        location.replace('login.html');
    }

    async function api(path, options = {}) {
        const token = localStorage.getItem('token');
        if (!token) { logout(); throw new Error('Entre novamente para continuar.'); }
        const response = await fetch(`${baseURL}/admin${path}`, {
            ...options, cache: 'no-store',
            headers: { Authorization: token, ...(options.body ? { 'Content-Type': 'application/json' } : {}) }
        });
        if (localStorage.getItem('token') !== token) throw new Error('A sessão foi alterada.');
        if (response.status === 401) { logout(); throw new Error('Sua sessão expirou.'); }
        const data = response.status === 204 ? null : await response.json().catch(() => ({}));
        if (response.status === 403) {
            clearPrivate();
            $('adminAccess').hidden = false;
            $('adminAccessMessage').textContent = 'Acesso exclusivo a administradores autorizados.';
            $('retryAdmin').hidden = true;
        }
        if (!response.ok) {
            const error = new Error(data.erro || 'Não foi possível concluir a operação.');
            error.status = response.status;
            throw error;
        }
        return data;
    }

    function pagination(data) {
        if (data.paginas <= 1) return '';
        return `<div class="pagination-bar"><span>Página ${data.pagina} de ${data.paginas} · ${data.total} registros</span><div class="d-flex gap-2"><button class="btn ghost-btn" data-list-page="${data.pagina - 1}" ${data.pagina <= 1 ? 'disabled' : ''}>Anterior</button><button class="btn ghost-btn" data-list-page="${data.pagina + 1}" ${data.pagina >= data.paginas ? 'disabled' : ''}>Próxima</button></div></div>`;
    }

    function auditList(rows) {
        if (!rows.length) return empty('Nenhuma ação administrativa registrada.');
        return `<div class="audit-list">${rows.map(row => `<article class="audit-entry"><p><strong>${escape(row.administrador || 'Sistema')}</strong> · ${escape(row.acao.replaceAll('_', ' '))}${row.usuario_afetado ? ` · ${escape(row.usuario_afetado)}` : ''}</p><small>${escape(date(row.criado_em))}</small></article>`).join('')}</div>`;
    }

    function usersTable(data) {
        if (!data.itens.length) return empty('Nenhum usuário encontrado.');
        return `<div class="table-wrap"><table class="professional-table"><thead><tr><th>Nome</th><th>E-mail</th><th>Tipo</th><th>Status</th><th>Ações</th></tr></thead><tbody>${data.itens.map(user => `<tr class="${user.ativo ? '' : 'inactive-row'}"><td>${escape(user.nome)}</td><td>${escape(user.email)}</td><td>${escape(roleLabels[user.role] || user.role)}</td><td>${statusBadge(user.ativo)}</td><td><button class="btn ghost-btn" data-user="${user.id}">Visualizar</button></td></tr>`).join('')}</tbody></table></div>${pagination(data)}`;
    }

    function psychologistsTable(data) {
        if (!data.itens.length) return empty('Nenhum psicólogo encontrado.');
        return `<div class="table-wrap"><table class="professional-table"><thead><tr><th>Nome</th><th>CRP</th><th>Especialidade</th><th>Pacientes</th><th>Status</th><th>Ações</th></tr></thead><tbody>${data.itens.map(item => `<tr class="${item.ativo ? '' : 'inactive-row'}"><td>${escape(item.nome)}</td><td>${escape(item.registro)}</td><td>${escape(item.especialidade || '—')}</td><td>${escape(item.pacientes)}</td><td>${statusBadge(item.ativo)}</td><td><button class="btn ghost-btn" data-psychologist="${item.id}">Visualizar</button></td></tr>`).join('')}</tbody></table></div>${pagination(data)}`;
    }

    function linksTable(data) {
        if (!data.itens.length) return empty('Nenhum vínculo encontrado.');
        return `<div class="table-wrap"><table class="professional-table"><thead><tr><th>Psicólogo</th><th>Paciente</th><th>Início</th><th>Encerramento</th><th>Status</th><th>Ação</th></tr></thead><tbody>${data.itens.map(item => `<tr class="${item.ativo ? '' : 'inactive-row'}"><td>${escape(item.psicologo)}</td><td>${escape(item.paciente)}</td><td>${escape(date(item.vinculado_em))}</td><td>${escape(date(item.desvinculado_em))}</td><td>${linkBadge(item.ativo)}</td><td>${item.ativo ? `<button class="btn ghost-btn" data-remove-link data-psychologist-id="${item.profissional_id}" data-patient-id="${item.paciente_id}" data-names="${escape(`${item.psicologo} e ${item.paciente}`)}">Remover</button>` : '—'}</td></tr>`).join('')}</tbody></table></div>${pagination(data)}`;
    }

    async function render() {
        if (!admin) return;
        const version = ++generation;
        const page = Object.hasOwn(pages, location.hash.slice(1)) ? location.hash.slice(1) : 'dashboard';
        document.querySelectorAll('[data-admin-page]').forEach(link => link.dataset.adminPage === page ? link.setAttribute('aria-current', 'page') : link.removeAttribute('aria-current'));
        $('adminTitle').textContent = pages[page][0];
        $('adminDescription').textContent = pages[page][1];
        $('adminPage').innerHTML = '<p class="helper-text">Carregando…</p>';
        $('adminPage').setAttribute('aria-busy', 'true');
        feedback();
        try {
            let html;
            if (page === 'dashboard') {
                const data = await api('/dashboard');
                const metrics = [['total', 'Total de usuários'], ['pacientes', 'Pacientes'], ['psicologos', 'Psicólogos'], ['ativos', 'Usuários ativos'], ['bloqueados', 'Usuários bloqueados'], ['vinculos', 'Vínculos ativos'], ['consultas_hoje', 'Consultas hoje'], ['consultas_agendadas', 'Consultas agendadas'], ['consultas_realizadas', 'Consultas realizadas']];
                html = `<div class="metric-grid admin-metrics">${metrics.map(([key, label]) => `<article class="card metric-card"><span>${label}</span><strong>${escape(data.resumo[key])}</strong></article>`).join('')}</div><section class="card panel"><h2 class="section-title mb-3">Atividade administrativa recente</h2>${auditList(data.auditoria)}</section>`;
            } else if (page === 'usuarios') {
                const data = await api(`/usuarios?busca=${encodeURIComponent(search)}&pagina=${listPage}`);
                html = `<section class="card panel"><form class="filter-bar" data-search-form><div><label class="form-label" for="adminSearch">Buscar por nome ou e-mail</label><input class="form-control" id="adminSearch" maxlength="120" value="${escape(search)}"></div><button class="btn primary-btn">Buscar</button></form><div id="adminList">${usersTable(data)}</div></section>`;
            } else if (page === 'psicologos') {
                const data = await api(`/psicologos?busca=${encodeURIComponent(search)}&pagina=${listPage}`);
                html = `<section class="card panel"><form class="filter-bar" data-search-form><div><label class="form-label" for="adminSearch">Buscar psicólogo</label><input class="form-control" id="adminSearch" maxlength="120" value="${escape(search)}"></div><button class="btn primary-btn">Buscar</button></form>${psychologistsTable(data)}</section>`;
            } else if (page === 'vinculos') {
                const data = await api(`/vinculos?busca=${encodeURIComponent(search)}&pagina=${listPage}`);
                html = `<section class="card panel"><form class="filter-bar" data-search-form><div><label class="form-label" for="adminSearch">Buscar psicólogo ou paciente</label><input class="form-control" id="adminSearch" maxlength="120" value="${escape(search)}"></div><button class="btn primary-btn">Buscar</button></form>${linksTable(data)}</section>`;
            } else {
                html = `<section class="card panel"><dl class="profile-grid"><div><dt>Nome</dt><dd>${escape(admin.nome)}</dd></div><div><dt>E-mail</dt><dd>${escape(admin.email)}</dd></div><div><dt>Permissão</dt><dd>Administrador(a)</dd></div></dl><p class="helper-text mt-4 mb-0">Sua conta usa o mesmo login dos demais usuários. A permissão é consultada no banco a cada requisição.</p></section>`;
            }
            if (version === generation) $('adminPage').innerHTML = html;
        } catch (error) {
            if (version === generation) { $('adminPage').replaceChildren(); feedback(error.message, true); }
        } finally {
            if (version === generation) $('adminPage').setAttribute('aria-busy', 'false');
        }
    }

    async function showUser(id) {
        const version = ++detailGeneration;
        feedback();
        const user = await api(`/usuarios/${id}`);
        if (version !== detailGeneration || !admin) return;
        $('adminDialogTitle').textContent = user.nome;
        $('adminDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-item"><small>E-mail</small><strong>${escape(user.email)}</strong></div><div class="detail-item"><small>Tipo</small><strong>${escape(roleLabels[user.role] || user.role)}</strong></div><div class="detail-item"><small>Status</small>${statusBadge(user.ativo)}</div><div class="detail-item"><small>Cadastro</small><strong>${escape(date(user.criado_em))}</strong></div>${user.registro ? `<div class="detail-item"><small>CRP</small><strong>${escape(user.registro)}</strong></div><div class="detail-item"><small>Especialidade</small><strong>${escape(user.especialidade || '—')}</strong></div>` : ''}</div>${user.role === 'paciente' && user.ativo ? `<form id="promotionForm" class="admin-form"><h3 class="section-title">Transformar em psicólogo</h3><div class="admin-form-grid"><div><label for="promotionRegistration">CRP</label><input id="promotionRegistration" class="form-control" maxlength="60" required></div><div><label for="promotionSpecialty">Especialidade</label><input id="promotionSpecialty" class="form-control" maxlength="120"></div></div><button class="btn success-action mt-3" type="submit" data-user-id="${user.id}" data-user-name="${escape(user.nome)}">Promover</button></form>` : ''}<div class="admin-actions">${user.id === admin.id ? '<span class="helper-text">Sua própria conta não pode ser bloqueada nesta tela.</span>' : `<button class="btn ${user.ativo ? 'danger-action' : 'success-action'}" data-toggle-user="${user.id}" data-active="${!user.ativo}" data-name="${escape(user.nome)}">${user.ativo ? 'Bloquear usuário' : 'Reativar usuário'}</button>`}</div>`;
        if (!$('adminDetailDialog').open) $('adminDetailDialog').showModal();
        const related = await api(`/usuarios/${id}/vinculos`);
        if (version === detailGeneration && $('adminDetailDialog').open && related.length) {
            $('adminDialogBody').insertAdjacentHTML('beforeend', `<section class="admin-form"><h3 class="section-title">Vínculos deste usuário</h3>${linksTable({ itens: related, paginas: 1 })}</section>`);
        }
    }

    async function loadPatientOptions(psychologistId, query = '') {
        const version = detailGeneration;
        const data = await api(`/usuarios?role=paciente&busca=${encodeURIComponent(query)}&por_pagina=100`);
        const select = $('linkPatient');
        if (!select || version !== detailGeneration) return;
        select.innerHTML = `<option value="">Selecione um paciente</option>${data.itens.filter(item => item.ativo).map(item => `<option value="${item.id}">${escape(item.nome)} · ${escape(item.email)}</option>`).join('')}`;
        select.dataset.psychologistId = psychologistId;
    }

    async function showPsychologist(id) {
        const version = ++detailGeneration;
        feedback();
        const data = await api(`/psicologos/${id}`);
        if (version !== detailGeneration || !admin) return;
        const psych = data.psicologo;
        $('adminDialogTitle').textContent = psych.nome;
        const activeLinks = data.vinculos.filter(link => link.vinculo_ativo);
        $('adminDialogBody').innerHTML = `<div class="detail-grid"><div class="detail-item"><small>E-mail</small><strong>${escape(psych.email)}</strong></div><div class="detail-item"><small>CRP</small><strong>${escape(psych.registro)}</strong></div><div class="detail-item"><small>Especialidade</small><strong>${escape(psych.especialidade || '—')}</strong></div><div class="detail-item"><small>Status</small>${statusBadge(psych.ativo)}</div></div><section class="admin-form"><h3 class="section-title">Pacientes vinculados</h3>${activeLinks.length ? `<div class="table-wrap"><table class="professional-table"><tbody>${activeLinks.map(link => `<tr><td>${escape(link.nome)}</td><td>${escape(link.email)}</td><td><button class="btn ghost-btn" data-remove-link data-psychologist-id="${id}" data-patient-id="${link.id}" data-names="${escape(`${psych.nome} e ${link.nome}`)}">Remover</button></td></tr>`).join('')}</tbody></table></div>` : empty('Nenhum paciente vinculado.')}</section>${psych.ativo ? `<form id="linkForm" class="admin-form"><h3 class="section-title">Adicionar paciente</h3><div class="filter-bar"><div><label for="candidateSearch">Buscar paciente</label><input id="candidateSearch" class="form-control" maxlength="120"></div><button id="searchCandidates" class="btn ghost-btn" type="button">Buscar</button></div><label for="linkPatient">Paciente</label><select id="linkPatient" class="form-control" required></select><button class="btn success-action mt-3" type="submit">Criar vínculo</button></form>` : ''}`;
        if (!$('adminDetailDialog').open) $('adminDetailDialog').showModal();
        $('adminDialogBody').insertAdjacentHTML('beforeend', `<form id="professionalProfileForm" class="admin-form"><h3 class="section-title">Editar perfil profissional</h3><div class="admin-form-grid"><div><label for="editRegistration">CRP</label><input id="editRegistration" class="form-control" maxlength="60" value="${escape(psych.registro || '')}" required></div><div><label for="editSpecialty">Especialidade</label><input id="editSpecialty" class="form-control" maxlength="120" value="${escape(psych.especialidade || '')}"></div></div><label class="mt-3"><input id="editProfileActive" type="checkbox" ${psych.perfil_profissional_ativo !== false ? 'checked' : ''}> Perfil profissional habilitado</label><button class="btn success-action mt-3" type="submit" data-psychologist-id="${id}">Salvar perfil</button></form>`);
        if (psych.ativo) await loadPatientOptions(id);
    }

    function confirmAction(title, message, label = 'Confirmar') {
        return new Promise(resolve => {
            $('confirmTitle').textContent = title;
            $('confirmMessage').textContent = message;
            $('acceptConfirm').textContent = label;
            $('confirmDialog').showModal();
            const finish = value => { $('confirmDialog').close(); resolve(value); };
            $('acceptConfirm').onclick = () => finish(true);
            $('cancelConfirm').onclick = () => finish(false);
            $('confirmDialog').oncancel = event => { event.preventDefault(); finish(false); };
        });
    }

    $('adminPage').addEventListener('submit', event => {
        if (!event.target.matches('[data-search-form]')) return;
        event.preventDefault();
        search = $('adminSearch').value.trim();
        listPage = 1;
        render();
    });

    $('adminPage').addEventListener('click', event => {
        const button = event.target.closest('button');
        if (!button) return;
        if (button.dataset.user) showUser(button.dataset.user).catch(error => feedback(error.message, true));
        if (button.dataset.psychologist) showPsychologist(button.dataset.psychologist).catch(error => feedback(error.message, true));
        if (button.dataset.listPage) { listPage = Number(button.dataset.listPage); render(); }
        if (button.hasAttribute('data-remove-link')) removeLink(button);
    });

    async function removeLink(button) {
        const ok = await confirmAction('Remover vínculo', `Tem certeza de que deseja remover o vínculo entre ${button.dataset.names}? O psicólogo perderá imediatamente o acesso às informações desse paciente.`, 'Remover vínculo');
        if (!ok) return;
        try {
            const data = await api(`/vinculos/${button.dataset.psychologistId}/${button.dataset.patientId}`, { method: 'DELETE', body: JSON.stringify({ confirmacao: true }) });
            $('adminDetailDialog').close();
            await render();
            feedback(data.msg);
        } catch (error) { feedback(error.message, true); }
    }

    $('adminDialogBody').addEventListener('click', async event => {
        const button = event.target.closest('button');
        if (!button) return;
        if (button.id === 'searchCandidates') {
            try { await loadPatientOptions($('linkPatient').dataset.psychologistId, $('candidateSearch').value.trim()); }
            catch (error) { feedback(error.message, true); }
        }
        if (button.hasAttribute('data-remove-link')) removeLink(button);
        if (button.dataset.toggleUser) {
            const active = button.dataset.active === 'true';
            const ok = await confirmAction(active ? 'Reativar usuário' : 'Bloquear usuário', `Tem certeza de que deseja ${active ? 'reativar' : 'bloquear'} ${button.dataset.name}? ${active ? 'O acesso será restaurado.' : 'Tokens existentes serão rejeitados imediatamente.'}`, active ? 'Reativar' : 'Bloquear');
            if (!ok) return;
            try {
                const data = await api(`/usuarios/${button.dataset.toggleUser}/status`, { method: 'PATCH', body: JSON.stringify({ ativo: active, confirmacao: true }) });
                $('adminDetailDialog').close(); await render(); feedback(data.msg);
            } catch (error) { feedback(error.message, true); }
        }
    });

    $('adminDialogBody').addEventListener('submit', async event => {
        event.preventDefault();
        const submit = event.target.querySelector('[type="submit"]');
        submit.disabled = true;
        try {
            if (event.target.id === 'promotionForm') {
                const ok = await confirmAction('Transformar em psicólogo', `Tem certeza de que deseja transformar ${submit.dataset.userName} em psicólogo?`, 'Promover');
                if (!ok) return;
                const data = await api(`/usuarios/${submit.dataset.userId}/promover-psicologo`, { method: 'POST', body: JSON.stringify({ registro: $('promotionRegistration').value.trim(), especialidade: $('promotionSpecialty').value.trim(), confirmacao: true }) });
                $('adminDetailDialog').close(); await render(); feedback(data.msg);
            } else if (event.target.id === 'linkForm') {
                const patient = $('linkPatient');
                if (!patient.value) throw new Error('Selecione um paciente.');
                const ok = await confirmAction('Criar vínculo', `Vincular o paciente ${patient.options[patient.selectedIndex].text} a este psicólogo?`, 'Criar vínculo');
                if (!ok) return;
                const data = await api('/vinculos', { method: 'POST', body: JSON.stringify({ psicologo_id: Number(patient.dataset.psychologistId), paciente_id: Number(patient.value), confirmacao: true }) });
                $('adminDetailDialog').close(); await render(); feedback(data.msg);
            } else if (event.target.id === 'professionalProfileForm') {
                const ok = await confirmAction('Atualizar perfil profissional', 'Confirma as alterações no registro, especialidade e habilitação deste perfil?', 'Salvar perfil');
                if (!ok) return;
                const data = await api(`/psicologos/${submit.dataset.psychologistId}/perfil`, { method: 'PATCH', body: JSON.stringify({ registro: $('editRegistration').value.trim(), especialidade: $('editSpecialty').value.trim(), ativo: $('editProfileActive').checked, confirmacao: true }) });
                $('adminDetailDialog').close(); await render(); feedback(data.msg);
            }
        } catch (error) { feedback(error.message, true); }
        finally { submit.disabled = false; }
    });

    async function boot() {
        $('retryAdmin').hidden = true;
        $('adminAccessMessage').textContent = 'Verificando seu acesso…';
        try {
            admin = await api('/me');
            $('adminAccess').hidden = true;
            $('adminApp').hidden = false;
            await render();
        } catch (error) {
            if (error.status === 403) return;
            $('adminAccessMessage').textContent = error.message;
            $('retryAdmin').hidden = false;
        }
    }

    $('retryAdmin').addEventListener('click', boot);
    $('refreshAdmin').addEventListener('click', render);
    $('adminLogout').addEventListener('click', logout);
    $('closeAdminDialog').addEventListener('click', () => { detailGeneration++; $('adminDetailDialog').close(); });
    $('adminMenuToggle').addEventListener('click', () => {
        const expanded = $('adminMenuToggle').getAttribute('aria-expanded') !== 'true';
        $('adminMenuToggle').setAttribute('aria-expanded', String(expanded));
        document.querySelector('.professional-sidebar').classList.toggle('menu-open', expanded);
    });
    window.addEventListener('hashchange', () => {
        listPage = 1; search = '';
        $('adminMenuToggle').setAttribute('aria-expanded', 'false');
        document.querySelector('.professional-sidebar').classList.remove('menu-open');
        $('adminContent').focus(); render();
    });
    window.addEventListener('storage', event => { if (event.key === 'token') { clearPrivate(); boot(); } });
    window.addEventListener('pageshow', event => { if (event.persisted) { clearPrivate(); boot(); } });
    boot();
})();
