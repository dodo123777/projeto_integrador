class ProgressManager {
    constructor() {
        this.progressBar = document.getElementById('progressBar');
        this.progressPerc = document.getElementById('progressPerc');
        this.congratsMessage = document.getElementById('congratsMessage');
        this.progressCaption = document.getElementById('progressCaption');
    }

    update(tasks) {
        const completedTasks = tasks.filter(task => task.completed).length;
        const percentage = tasks.length > 0 ? Math.round((completedTasks / tasks.length) * 100) : 0;

        this.progressBar.style.width = `${percentage}%`;
        this.progressPerc.textContent = percentage > 0 ? `${percentage}%` : "";

        if (this.progressCaption) {
            if (percentage === 0) {
                this.progressCaption.textContent = 'Comece com algo de 5 minutos para ganhar impulso.';
            } else if (percentage < 50) {
                this.progressCaption.textContent = 'Bom inicio! Termine um bloco curto e volte para a lista.';
            } else if (percentage < 100) {
                this.progressCaption.textContent = 'Voce esta no meio do caminho. Respire e conclua o proximo passo.';
            } else {
                this.progressCaption.textContent = 'Dia concluido! Aproveite o descanso.';
            }
        }

        if (percentage === 100 && tasks.length > 0) {
            this.showCongrats();
        }
    }

    showCongrats() {
        if (document.body.classList.contains('focus-mode')) {
            return;
        }
        this.congratsMessage.style.display = "block";
        fireworks.createEffect();
        setTimeout(() => {
            this.congratsMessage.style.display = "none";
        }, 5000);
    }
}

class DashboardManager {
    constructor() {
        this.token = localStorage.getItem('token');
        this.subtitle = document.getElementById('dashboardSubtitle');
        this.statusChartLabel = document.getElementById('statusChartLabel');
        this.metricTotal = document.getElementById('metricTotal');
        this.metricCompleted = document.getElementById('metricCompleted');
        this.metricPending = document.getElementById('metricPending');
        this.metricRate = document.getElementById('metricRate');
        this.statusChart = document.getElementById('statusChart');
        this.weeklyChart = document.getElementById('weeklyChart');
        this.periodChart = document.getElementById('periodChart');
        this.refreshButton = document.getElementById('refreshDashboard');
        this.currentDate = null;
        this.colors = {
            ink: '#10344a',
            muted: '#60778a',
            grid: '#dbe6ef',
            completed: '#0f8b8d',
            completedDark: '#0f4662',
            pending: '#e7edf4',
            accent: '#6fd0b5',
            warning: '#b52e46'
        };

        if (this.refreshButton) {
            this.refreshButton.addEventListener('click', () => {
                if (this.currentDate) this.update(this.currentDate);
            });
        }

        window.addEventListener('resize', () => {
            clearTimeout(this.resizeTimer);
            this.resizeTimer = setTimeout(() => {
                if (this.lastStats) this.render(this.lastStats);
            }, 150);
        });
    }

    async update(date) {
        if (!this.statusChart || !this.weeklyChart || !this.periodChart) return;

        this.currentDate = date;
        this.setLoading(true);

        try {
            const response = await fetch(`${API_URL}/tarefas/estatisticas?date=${encodeURIComponent(date)}`, {
                headers: { 'Authorization': this.token }
            });

            if (!response.ok) {
                throw new Error('Nao foi possivel carregar os graficos.');
            }

            const stats = await response.json();
            this.lastStats = stats;
            this.render(stats);
        } catch (error) {
            console.error(error);
            if (this.subtitle) this.subtitle.textContent = error.message;
            this.drawEmptyState(this.statusChart, 'Sem dados');
            this.drawEmptyState(this.weeklyChart, 'Sem dados');
            this.drawEmptyState(this.periodChart, 'Sem dados');
        } finally {
            this.setLoading(false);
        }
    }

    setLoading(isLoading) {
        if (!this.refreshButton) return;
        this.refreshButton.disabled = isLoading;
        this.refreshButton.classList.toggle('is-loading', isLoading);
    }

    render(stats) {
        const dateLabel = this.formatFullDate(stats.selectedDate);
        if (this.subtitle) {
            this.subtitle.textContent = `Indicadores atualizados para ${dateLabel}.`;
        }
        if (this.statusChartLabel) {
            this.statusChartLabel.textContent = dateLabel;
        }

        this.metricTotal.textContent = stats.day.total;
        this.metricCompleted.textContent = stats.day.completed;
        this.metricPending.textContent = stats.day.pending;
        this.metricRate.textContent = `${stats.day.completionRate}%`;

        this.drawStatusChart(stats.day);
        this.drawWeeklyChart(stats.week);
        this.drawPeriodChart(stats.periods);
    }

    setupCanvas(canvas) {
        const rect = canvas.getBoundingClientRect();
        const width = Math.max(rect.width, 260);
        const height = Math.max(rect.height, Number(canvas.getAttribute('height')) || 220);
        const ratio = window.devicePixelRatio || 1;
        canvas.width = width * ratio;
        canvas.height = height * ratio;
        const ctx = canvas.getContext('2d');
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, width, height);
        return { ctx, width, height };
    }

    drawStatusChart(day) {
        const { ctx, width, height } = this.setupCanvas(this.statusChart);
        const total = day.total;
        const completed = day.completed;
        const pending = day.pending;
        const centerX = width / 2;
        const centerY = height / 2 + 6;
        const radius = Math.min(width, height) * 0.31;
        const lineWidth = 24;

        ctx.lineWidth = lineWidth;
        ctx.lineCap = 'round';
        ctx.strokeStyle = this.colors.pending;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.stroke();

        if (total > 0) {
            const completedAngle = (completed / total) * Math.PI * 2;
            ctx.strokeStyle = this.colors.completed;
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, -Math.PI / 2, completedAngle - Math.PI / 2);
            ctx.stroke();

            if (pending > 0) {
                ctx.strokeStyle = '#b52e4626';
                ctx.beginPath();
                ctx.arc(centerX, centerY, radius, completedAngle - Math.PI / 2, Math.PI * 1.5);
                ctx.stroke();
            }
        }

        ctx.fillStyle = this.colors.ink;
        ctx.font = '800 32px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${day.completionRate}%`, centerX, centerY + 4);
        ctx.fillStyle = this.colors.muted;
        ctx.font = '700 10px Inter, sans-serif';
        ctx.fillText(`${completed} de ${total} concluidas`, centerX, centerY + 28);
    }

    drawWeeklyChart(week) {
        const { ctx, width, height } = this.setupCanvas(this.weeklyChart);
        const padding = { top: 22, right: 12, bottom: 34, left: 30 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;
        const maxValue = Math.max(1, ...week.map(day => day.total));
        const barGap = 10;
        const barWidth = Math.max(16, (chartWidth - barGap * (week.length - 1)) / week.length);

        this.drawAxis(ctx, padding, width, height);

        week.forEach((day, index) => {
            const x = padding.left + index * (barWidth + barGap);
            const totalHeight = (day.total / maxValue) * chartHeight;
            const completedHeight = (day.completed / maxValue) * chartHeight;
            const baseY = height - padding.bottom;

            ctx.fillStyle = this.colors.pending;
            this.roundRect(ctx, x, baseY - totalHeight, barWidth, totalHeight, 6);
            ctx.fill();

            ctx.fillStyle = this.colors.completed;
            this.roundRect(ctx, x, baseY - completedHeight, barWidth, completedHeight, 6);
            ctx.fill();

            ctx.fillStyle = this.colors.muted;
            ctx.font = '700 8px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(this.formatShortDate(day.date), x + barWidth / 2, height - 10);
        });
    }

    drawPeriodChart(periods) {
        const { ctx, width, height } = this.setupCanvas(this.periodChart);
        const padding = { top: 26, right: 42, bottom: 18, left: 72 };
        const rowHeight = 42;
        const barWidth = width - padding.left - padding.right;

        periods.forEach((period, index) => {
            const y = padding.top + index * rowHeight;
            const total = Number(period.total) || 0;
            const completed = Number(period.completed) || 0;
            const safeCompleted = Math.min(Math.max(completed, 0), Math.max(total, 0));
            const completionRatio = total > 0 ? safeCompleted / total : 0;
            const completedWidth = completionRatio * barWidth;

            ctx.fillStyle = this.colors.ink;
            ctx.font = '800 12px Inter, sans-serif';
            ctx.textAlign = 'right';
            ctx.fillText(period.label, padding.left - 12, y + 22);

            ctx.fillStyle = this.colors.pending;
            this.roundRect(ctx, padding.left, y, Math.max(barWidth, 4), 24, 8);
            ctx.fill();

            if (safeCompleted > 0) {
                ctx.fillStyle = this.colors.completedDark;
                this.roundRect(ctx, padding.left, y, Math.max(completedWidth, 4), 24, 8);
                ctx.fill();
            }

            ctx.fillStyle = this.colors.muted;
            ctx.font = '700 11px Inter, sans-serif';
            ctx.textAlign = 'right';

            const valueText = total > 0
                ? `${safeCompleted}/${total}`
                : '0';

            ctx.fillText(valueText, width - 8, y + 17);
        });

        if (periods.every(period => period.total === 0)) {
            this.drawEmptyState(this.periodChart, 'Nenhuma tarefa neste dia');
        }
    }

    drawAxis(ctx, padding, width, height) {
        ctx.strokeStyle = this.colors.grid;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding.left, height - padding.bottom);
        ctx.lineTo(width - padding.right, height - padding.bottom);
        ctx.stroke();
    }

    drawEmptyState(canvas, text) {
        const { ctx, width, height } = this.setupCanvas(canvas);
        ctx.fillStyle = this.colors.muted;
        ctx.font = '700 14px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(text, width / 2, height / 2);
    }

    roundRect(ctx, x, y, width, height, radius) {
        const safeWidth = Math.max(width, 0);
        const safeHeight = Math.max(height, 0);
        if (safeWidth === 0 || safeHeight === 0) return;

        const safeRadius = Math.min(radius, safeWidth / 2, safeHeight / 2);
        ctx.beginPath();
        ctx.moveTo(x + safeRadius, y);
        ctx.lineTo(x + safeWidth - safeRadius, y);
        ctx.quadraticCurveTo(x + safeWidth, y, x + safeWidth, y + safeRadius);
        ctx.lineTo(x + safeWidth, y + safeHeight - safeRadius);
        ctx.quadraticCurveTo(x + safeWidth, y + safeHeight, x + safeWidth - safeRadius, y + safeHeight);
        ctx.lineTo(x + safeRadius, y + safeHeight);
        ctx.quadraticCurveTo(x, y + safeHeight, x, y + safeHeight - safeRadius);
        ctx.lineTo(x, y + safeRadius);
        ctx.quadraticCurveTo(x, y, x + safeRadius, y);
        ctx.closePath();
    }

    formatFullDate(value) {
        return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: 'short'
        });
    }

    formatShortDate(value) {
        return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: '2-digit'
        });
    }
}

const progressManager = new ProgressManager();
const dashboardManager = new DashboardManager();
