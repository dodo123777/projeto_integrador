// Serviços públicos consultados apenas quando o usuário abre o mapa ou faz uma busca.
const CLINIC_SERVICES = {
    geocoder: 'https://photon.komoot.io/api/',
    places: 'https://photon.komoot.io/reverse',
    tiles: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
};

class ClinicsManager {
    constructor() {
        this.tabs = Array.from(document.querySelectorAll('.app-tab'));
        this.form = document.getElementById('clinicSearchForm');
        this.address = document.getElementById('clinicAddress');
        this.radius = document.getElementById('clinicRadius');
        this.status = document.getElementById('clinicStatus');
        this.summary = document.getElementById('clinicResultsSummary');
        this.list = document.getElementById('clinicList');
        this.choices = document.getElementById('clinicLocationChoices');
        this.mapElement = document.getElementById('clinicsMap');
        this.geocoderCache = new Map();
        this.placesCache = new Map();

        this.tabs.forEach((tab, index) => {
            tab.addEventListener('click', () => this.activateTab(tab));
            tab.addEventListener('keydown', event => {
                const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
                if (!keys.includes(event.key)) return;
                event.preventDefault();
                const next = event.key === 'Home' ? 0 : event.key === 'End' ? this.tabs.length - 1
                    : (index + (event.key === 'ArrowRight' ? 1 : -1) + this.tabs.length) % this.tabs.length;
                this.tabs[next].focus();
                this.activateTab(this.tabs[next]);
            });
        });
        this.form.addEventListener('submit', event => {
            event.preventDefault();
            this.run(() => this.searchAddress());
        });
        document.getElementById('locateClinicsButton').addEventListener('click', () => {
            this.run(() => this.locate());
        });
        this.radius.addEventListener('change', () => {
            if (this.origin) this.run(() => this.searchClinics(this.origin, this.originLabel));
        });
    }

    activateTab(selected) {
        this.tabs.forEach(tab => {
            const active = tab === selected;
            tab.setAttribute('aria-selected', String(active));
            tab.tabIndex = active ? 0 : -1;
            document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
        });
        if (selected.id === 'clinicsTab') {
            this.ensureMap().then(() => this.map.invalidateSize()).catch(error => {
                this.setStatus(error.message, 'error');
            });
        } else {
            requestAnimationFrame(() => {
                if (dashboardManager.lastStats) dashboardManager.render(dashboardManager.lastStats);
            });
        }
    }

    async ensureMap() {
        if (this.map) return;
        if (this.mapPromise) return this.mapPromise;
        this.mapPromise = (async () => {
            await this.loadLeaflet();
            this.map = L.map(this.mapElement, { scrollWheelZoom: false }).setView([-14.2, -51.9], 4);
            L.tileLayer(CLINIC_SERVICES.tiles, {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).on('tileerror', () => {
                document.getElementById('clinicMapNotice').hidden = false;
            }).on('tileload', () => {
                document.getElementById('clinicMapNotice').hidden = true;
            }).addTo(this.map);
            this.markers = L.layerGroup().addTo(this.map);
            this.originLayers = L.layerGroup().addTo(this.map);
            this.mapObserver = new ResizeObserver(() => {
                if (!document.getElementById('clinicsPanel').hidden) this.map.invalidateSize();
            });
            this.mapObserver.observe(this.mapElement);
        })();
        try {
            await this.mapPromise;
        } finally {
            this.mapPromise = null;
        }
    }

    loadLeaflet() {
        if (this.leafletReady) return Promise.resolve();
        const css = document.createElement('link');
        css.rel = 'stylesheet';
        css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
        css.integrity = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
        css.crossOrigin = 'anonymous';
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
        script.integrity = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
        script.crossOrigin = 'anonymous';
        const resources = [css, script];
        return new Promise((resolve, reject) => {
            let loaded = 0;
            const timeout = setTimeout(fail, 12000);
            function fail() {
                clearTimeout(timeout);
                resources.forEach(resource => resource.remove());
                reject(new Error('Não foi possível carregar o mapa. Verifique sua conexão e tente buscar novamente.'));
            }
            resources.forEach(resource => {
                resource.onload = () => {
                    loaded += 1;
                    if (loaded === resources.length) {
                        clearTimeout(timeout);
                        this.leafletReady = true;
                        resolve();
                    }
                };
                resource.onerror = fail;
                document.head.appendChild(resource);
            });
        });
    }

    setStatus(message, tone = 'info') {
        this.status.textContent = message;
        this.status.dataset.tone = tone;
    }

    async run(action) {
        if (this.busy) return;
        this.busy = true;
        Array.from(this.form.elements).forEach(element => { element.disabled = true; });
        this.choices.hidden = true;
        this.list.replaceChildren();
        if (this.markers) this.markers.clearLayers();
        if (this.originLayers) this.originLayers.clearLayers();
        this.summary.textContent = 'Aguardando os resultados da busca…';
        this.mapElement.setAttribute('aria-busy', 'true');
        document.querySelector('.clinic-results').setAttribute('aria-busy', 'true');
        try {
            await action();
        } catch (error) {
            this.setStatus(error.message, 'error');
            this.summary.textContent = 'A busca não foi concluída. Tente novamente.';
        } finally {
            this.busy = false;
            Array.from(this.form.elements).forEach(element => { element.disabled = false; });
            this.mapElement.setAttribute('aria-busy', 'false');
            document.querySelector('.clinic-results').setAttribute('aria-busy', 'false');
        }
    }

    async fetchJSON(url, options = {}) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 30000);
        try {
            const response = await fetch(url, { ...options, signal: controller.signal });
            if (!response.ok) throw new Error('Serviço de mapas indisponível. Tente novamente em alguns instantes.');
            return await response.json();
        } catch (error) {
            if (error.name === 'AbortError') throw new Error('A busca demorou mais que o esperado. Tente novamente ou reduza a distância.');
            if (error instanceof TypeError) throw new Error('Não foi possível conectar ao serviço de mapas. Verifique sua conexão e tente novamente.');
            throw error;
        } finally {
            clearTimeout(timeout);
        }
    }

    async searchAddress() {
        this.origin = null;
        const query = this.address.value.trim();
        if (query.length < 3) throw new Error('Digite uma cidade, bairro ou endereço com pelo menos 3 caracteres.');
        this.setStatus('Buscando o local informado…');
        await this.ensureMap();
        const key = query.toLocaleLowerCase('pt-BR');
        let features = this.geocoderCache.get(key);
        if (!features) {
            const params = new URLSearchParams({ q: query, limit: '5' });
            const data = await this.fetchJSON(`${CLINIC_SERVICES.geocoder}?${params}`);
            if (!Array.isArray(data.features)) throw new Error('O serviço de mapas retornou uma resposta inválida. Tente novamente.');
            features = data.features.filter(feature => this.validCoordinates(feature.geometry?.coordinates));
            this.geocoderCache.set(key, features);
        }
        if (!features.length) {
            this.origin = null;
            throw new Error('Local não encontrado. Acrescente a cidade e o estado ou use sua localização.');
        }
        const places = features.map(feature => {
            const p = feature.properties || {};
            return {
                coordinates: [feature.geometry.coordinates[1], feature.geometry.coordinates[0]],
                label: [...new Set([p.name, p.street, p.city, p.state, p.country].filter(Boolean))].join(', ') || query
            };
        });
        if (places.length === 1) return this.searchClinics(places[0].coordinates, places[0].label);
        this.origin = null;
        this.choices.replaceChildren();
        places.forEach(place => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn ghost-btn text-start';
            button.textContent = place.label;
            button.addEventListener('click', () => this.run(() => this.searchClinics(place.coordinates, place.label)));
            this.choices.appendChild(button);
        });
        this.choices.hidden = false;
        this.setStatus('Encontramos mais de um local. Escolha abaixo onde deseja buscar clínicas.');
        this.summary.textContent = 'Escolha um local para ver as clínicas próximas.';
        this.choices.querySelector('button').focus();
    }

    async locate() {
        this.origin = null;
        if (!window.isSecureContext || !navigator.geolocation) {
            throw new Error('Localização indisponível neste navegador. Busque pela cidade ou endereço.');
        }
        this.setStatus('Aguardando sua localização. Autorize o acesso no navegador.');
        const position = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, error => {
                const messages = {
                    1: 'Permissão de localização negada. Você pode buscar pela cidade ou endereço.',
                    2: 'Não foi possível determinar sua localização. Busque pela cidade ou endereço.',
                    3: 'A localização demorou para responder. Tente novamente ou busque pela cidade.'
                };
                reject(new Error(messages[error.code] || messages[2]));
            }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
        });
        await this.searchClinics([position.coords.latitude, position.coords.longitude], 'Sua localização');
    }

    validCoordinates(coordinates) {
        return Array.isArray(coordinates) && coordinates.length >= 2
            && Number.isFinite(coordinates[0]) && Math.abs(coordinates[0]) <= 180
            && Number.isFinite(coordinates[1]) && Math.abs(coordinates[1]) <= 90;
    }

    async searchClinics(origin, label) {
        this.origin = origin;
        this.originLabel = label;
        const radius = Number(this.radius.value);
        this.setStatus(`Buscando clínicas em até ${radius / 1000} km de ${label}…`);
        await this.ensureMap();
        this.originLayers.clearLayers();
        L.circleMarker(origin, { radius: 8, color: '#fff', weight: 3, fillColor: '#0f4662', fillOpacity: 1 })
            .bindPopup(this.textElement('strong', label)).addTo(this.originLayers);
        const circle = L.circle(origin, { radius, color: '#0f8b8d', weight: 1, fillOpacity: 0.06 }).addTo(this.originLayers);
        this.map.invalidateSize();
        this.map.fitBounds(circle.getBounds(), { padding: [20, 20] });
        const key = `${origin.join(',')}:${radius}`;
        let elements = this.placesCache.get(key);
        if (!elements || Date.now() - elements.time > 300000) {
            const params = new URLSearchParams({
                lat: origin[0], lon: origin[1], radius: radius / 1000, limit: '50'
            });
            ['amenity:clinic', 'amenity:doctors', 'amenity:hospital', 'healthcare:clinic',
                'healthcare:doctor', 'healthcare:psychologist', 'healthcare:psychotherapist',
                'healthcare:centre'].forEach(tag => params.append('osm_tag', tag));
            const data = await this.fetchJSON(`${CLINIC_SERVICES.places}?${params}`);
            if (!Array.isArray(data.features)) {
                throw new Error('Não foi possível concluir a consulta de clínicas. Tente novamente.');
            }
            elements = { data: data.features, time: Date.now() };
            this.placesCache.set(key, elements);
        }
        const clinics = elements.data.map(feature => {
            if (!this.validCoordinates(feature.geometry?.coordinates)) return null;
            const [lng, lat] = feature.geometry.coordinates;
            const properties = feature.properties || {};
            return {
                coordinates: [lat, lng],
                name: properties.name || 'Unidade de saúde sem nome informado',
                address: [properties.street, properties.housenumber, properties.district, properties.city].filter(Boolean).join(', '),
                distance: L.latLng(origin).distanceTo([lat, lng])
            };
        }).filter(clinic => clinic && clinic.distance <= radius).sort((a, b) => a.distance - b.distance);
        const shown = clinics.slice(0, 30);
        shown.forEach(clinic => this.renderClinic(clinic));
        this.summary.textContent = clinics.length > shown.length
            ? `Mostrando os ${shown.length} locais mais próximos de ${clinics.length} encontrados.`
            : `${clinics.length} ${clinics.length === 1 ? 'local encontrado' : 'locais encontrados'} em até ${radius / 1000} km.`;
        this.setStatus(clinics.length
            ? `Clínicas próximas de ${label}. Selecione um marcador ou veja a lista ao lado.`
            : `Nenhuma clínica cadastrada no mapa nessa região. Aumente a distância ou busque outro local.`);
    }

    textElement(tag, text, className = '') {
        const element = document.createElement(tag);
        element.textContent = text;
        element.className = className;
        return element;
    }

    routeLink(clinic) {
        const link = this.textElement('a', 'Como chegar');
        link.href = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(clinic.coordinates.join(','))}`;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        return link;
    }

    renderClinic(clinic) {
        const distance = clinic.distance < 1000
            ? `${Math.round(clinic.distance)} m` : `${(clinic.distance / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} km`;
        const popup = document.createElement('div');
        popup.className = 'clinic-popup';
        popup.append(this.textElement('strong', clinic.name), this.textElement('span', `${distance} do local da busca`));
        if (clinic.address) popup.appendChild(this.textElement('span', clinic.address));
        popup.appendChild(this.routeLink(clinic));
        const marker = L.circleMarker(clinic.coordinates, {
            radius: 9, color: '#fff', weight: 2, fillColor: '#0f8b8d', fillOpacity: 1
        }).bindPopup(popup).addTo(this.markers);
        const item = document.createElement('li');
        item.className = 'clinic-item';
        item.append(this.textElement('h4', clinic.name), this.textElement('p', `${distance} do local da busca`, 'helper-text mb-2'));
        item.appendChild(this.textElement('p', clinic.address || 'Endereço não informado no mapa.', 'helper-text mb-3'));
        const actions = document.createElement('div');
        actions.className = 'd-flex flex-wrap gap-2';
        const view = this.textElement('button', 'Ver no mapa', 'btn ghost-btn');
        view.type = 'button';
        view.addEventListener('click', () => {
            this.map.setView(clinic.coordinates, 16);
            marker.openPopup();
            this.mapElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
        const route = this.routeLink(clinic);
        route.className = 'btn primary-btn';
        actions.append(view, route);
        item.appendChild(actions);
        this.list.appendChild(item);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ClinicsManager();
});
