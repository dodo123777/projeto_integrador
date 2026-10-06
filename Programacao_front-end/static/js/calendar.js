// Datas sem horário: o calendário mantém o dia escolhido em qualquer fuso.
const CalendarDates = {
    format(date) {
        if (!Number.isFinite(date.getTime()) || date.getFullYear() < 1 || date.getFullYear() > 9999) return '';
        return String(date.getFullYear()).padStart(4, '0') + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
    },
    add(value, days) {
        const date = new Date(value + 'T12:00:00');
        date.setDate(date.getDate() + days);
        return this.format(date);
    },
    week(value) {
        const day = new Date(value + 'T12:00:00').getDay();
        const start = this.add(value, -((day + 6) % 7));
        return Array.from({ length: 7 }, (_, index) => this.add(start, index));
    },
    label(value, options = { day: '2-digit', month: 'short' }) {
        return new Date(value + 'T12:00:00').toLocaleDateString('pt-BR', options);
    },
    today() {
        const parts = Object.fromEntries(new Intl.DateTimeFormat('pt-BR', {
            timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit'
        }).formatToParts(new Date()).map(part => [part.type, part.value]));
        return parts.year + '-' + parts.month + '-' + parts.day;
    },
    appointmentDay(value) {
        const parts = Object.fromEntries(new Intl.DateTimeFormat('pt-BR', {
            timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit'
        }).formatToParts(new Date(value)).map(part => [part.type, part.value]));
        return parts.year + '-' + parts.month + '-' + parts.day;
    }
};
