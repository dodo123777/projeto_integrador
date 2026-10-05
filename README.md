# InfoHelp

Agenda de tarefas com progresso diário, gráficos, chat de organização, clínicas próximas e áreas profissional e administrativa.

## Executar localmente

Na raiz do repositório:

```sh
python3 -m venv Programacao_back-end/.venv
Programacao_back-end/.venv/bin/python -m pip install -r Programacao_back-end/requirements.txt
cd Programacao_back-end
.venv/bin/python app.py
```

O backend usa `http://localhost:5001`. A porta 5000 pode estar ocupada pelo AirPlay no macOS. O arquivo privado `Programacao_back-end/.env` deve conter `SECRET_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` e, para o chat, `GEMINI_API_KEY` e `GEMINI_MODEL`.

Em outro terminal, na raiz:

```sh
python3 -m http.server 5500 --bind 127.0.0.1 --directory Programacao_front-end
```

Abra [a tela de login](http://localhost:5500/login.html). O banco Supabase precisa estar ativo. Após mudar o código Python ou o `.env`, reinicie o backend. As alterações de frontend aparecem ao recarregar a página.

## Tarefas

- **Editar:** altera texto, dia e horários de uma ocorrência. O estado de conclusão é preservado.
- **Repetir:** escolha diariamente ou semanalmente e uma data final. O primeiro dia é incluído. São permitidas até 90 ocorrências por cadastro, dentro dos próximos 365 dias a partir do dia inicial.
- As repetições são tarefas independentes, criadas em uma única transação: se uma falhar, nenhuma é salva. Editar ou remover uma ocorrência mantém as demais.
- Erros de carregamento aparecem com uma ação para tentar novamente. Uma lista carregada anteriormente é identificada como tal; uma falha não aparece como um dia sem tarefas.
- Falhas temporárias e de rede preservam a sessão. Respostas 401 exigem novo login.

## Diagnóstico

- `GET /`: verifica se a API está respondendo.
- `GET /health/ready`: verifica a conexão e executa `SELECT 1`. Retorna 200 com `api: ok` e `database: ok`, ou 503 com `api: ok` e `database: unavailable`.

O diagnóstico não divulga credenciais. As conexões usam `connect_timeout=8` e as consultas têm `statement_timeout=15000`. Uma conexão nova recusada não é repetida automaticamente.

## Testes

No diretório do backend, com as dependências instaladas:

```sh
.venv/bin/python -m unittest discover -s tests -q
```

Os testes de navegador usam Playwright e Chromium separados, com APIs simuladas. Na raiz, usando o mesmo ambiente Python:

```sh
Programacao_back-end/.venv/bin/python -m pip install playwright
Programacao_back-end/.venv/bin/python -m playwright install chromium
Programacao_back-end/.venv/bin/python Programacao_back-end/tests/browser_patient.py
Programacao_back-end/.venv/bin/python Programacao_back-end/tests/browser_task_resilience.py
Programacao_back-end/.venv/bin/python Programacao_back-end/tests/browser_clinics.py
Programacao_back-end/.venv/bin/python Programacao_back-end/tests/browser_professional.py
Programacao_back-end/.venv/bin/python Programacao_back-end/tests/browser_admin.py
```

`PLAYWRIGHT_EXECUTABLE_PATH` permite selecionar um Chromium de testes existente. `BROWSER_ASSETS_DIR` pode apontar para arquivos de CDN em cache nos testes de clínicas e resiliência. Os testes simulados não alteram o banco remoto.

Consulte também [área profissional](AREA_PROFISSIONAL.md), [área administrativa](AREA_ADMIN.md), [migrações aplicadas](PLANO_MIGRACAO_SUPABASE.md) e [clínicas próximas](MAPA_CLINICAS.md).
