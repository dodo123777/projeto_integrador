# Clínicas próximas

A aba na agenda usa Leaflet 1.9.4 para o mapa e Photon para buscar endereços e unidades de saúde nos dados de OpenStreetMap. Não exige chave de API nem alterações no `.env`.

O mapa carrega quando a aba é aberta. A localização só é solicitada ao clicar em “Usar minha localização”; no site publicado, o navegador exige HTTPS. Quem não autorizar pode buscar uma cidade, bairro ou endereço. As consultas aos mapas não enviam o token da aplicação.

A busca oferece raios de 2, 5 e 10 km. Consulta até 50 locais, filtra pelo raio e exibe até 30, ordenados pela distância em linha reta. A cobertura depende dos estabelecimentos cadastrados em OpenStreetMap; resultados vazios não significam ausência de clínicas na região. “Como chegar” abre uma rota no Google Maps.

Os endereços consultados ficam em cache em memória durante a sessão da página; as buscas de clínicas ficam em cache por cinco minutos. Os serviços públicos podem limitar o volume de consultas e não garantem disponibilidade. Para ampliar o uso, configure um provedor adequado em `CLINIC_SERVICES` no arquivo `Programacao_front-end/static/js/clinics.js`.

Referências: [API Photon](https://github.com/komoot/photon/blob/master/docs/api-v1.md), [condições do servidor público Photon](https://github.com/komoot/photon#demo-server), [política de tiles OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/), [Leaflet](https://leafletjs.com/examples/quick-start/).

## Validação

Com Playwright e Chromium de testes instalados:

```sh
python3 Programacao_back-end/tests/browser_patient.py
python3 Programacao_back-end/tests/browser_clinics.py
```

`PLAYWRIGHT_EXECUTABLE_PATH` permite selecionar um Chromium de testes. `BROWSER_ASSETS_DIR` permite usar arquivos de CDN em cache (`leaflet.js`, `leaflet.css`, `bootstrap.css`, `fontawesome.css` e fontes Font Awesome) no teste de clínicas. As APIs são simuladas; os testes não escrevem no banco e não baixam tiles públicos. As capturas ficam em `/private/tmp/infohelp-clinics-review`.
