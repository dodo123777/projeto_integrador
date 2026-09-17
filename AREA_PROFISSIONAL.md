# Área do Profissional — InfoHelp

> A evolução administrativa está documentada em [AREA_ADMIN.md](AREA_ADMIN.md). A autorização atual usa `usuarios.role`, `usuarios.ativo` e versão de sessão; vínculos são encerrados logicamente e consultados novamente em cada operação.

## Arquitetura e análise

O projeto existente é uma agenda de apoio à organização de rotina, com tarefas pessoais, indicadores de progresso e chat com Gemini. Usa Flask e Blueprints, models com SQL parametrizado via psycopg2 e PostgreSQL (configuração preparada para Supabase). O frontend é estático, em HTML, CSS e JavaScript; usa Bootstrap, Font Awesome e a fonte Inter nas páginas internas. Frontend e backend são publicados separadamente, com CORS e JWT HS256 de duas horas enviado no cabeçalho `Authorization`.

As entidades identificadas no código anterior são `usuarios` (`id`, `nome`, `email`, `senha`) e `tarefas`. Não havia papéis profissionais, vínculos ou agenda clínica. Não há DDL anterior no repositório, nem `.env` neste checkout; os tipos e restrições do banco real precisam ser conferidos antes da migração.

A implementação mantém a arquitetura, os contratos de login/cadastro, tarefas e chat, e reutiliza `style.css`, botões, inputs, cards, sombras e cores. A recuperação de senha foi corrigida: `/esqueci_senha` antes alterava a senha de qualquer conta sem verificar sua identidade. Agora retorna 403 sem alterar credenciais; a tela explica a indisponibilidade. É necessária uma recuperação verificada por link de uso único para reativar esse recurso.

## Funcionalidades

- Início com consultas de hoje, próximas consultas, pacientes vinculados e total finalizado.
- Pacientes com busca por nome, último/próximo atendimento e detalhes das consultas com o profissional atual.
- Agenda com filtro por dia, criação de consultas e transições de status.
- Atendimentos finalizados e perfil com nome, profissão, registro, especialidade e e-mail.
- Estados de carregamento, vazio, erro, acesso negado, sessão expirada e nova tentativa.
- Sidebar, menu móvel, navegação por teclado, diálogo acessível e layout responsivo.
- Login direciona profissionais habilitados à nova área. A agenda pessoal também exibe o link após confirmação do backend.

Nenhum dado de demonstração integra a aplicação. As fixtures estão apenas nos testes. Idade, telefone, foto e prontuário não foram acrescentados. Tarefas pessoais, senhas e conversas do paciente não são expostas.

## Arquivos criados

- `Programacao_front-end/profissional.html`
- `Programacao_front-end/static/css/profissional.css`
- `Programacao_front-end/static/js/profissional.js`
- `Programacao_back-end/controllers/professional_controller.py`
- `Programacao_back-end/models/professional.py`
- `Programacao_back-end/professional_commands.py`
- `Programacao_back-end/migrations/001_area_profissional.sql`
- `Programacao_back-end/tests/test_professional.py`
- `Programacao_back-end/tests/browser_professional.py`
- `AREA_PROFISSIONAL.md`

## Arquivos modificados

- `Programacao_back-end/app.py`: registra o Blueprint/comandos e fecha a conexão ao encerrar o contexto.
- `Programacao_back-end/auth.py`: remove o log do token e rejeita identidades JWT inválidas.
- `Programacao_back-end/database.py`: conexão criada sob demanda e isolada por thread, evitando transações compartilhadas entre requisições concorrentes.
- `Programacao_back-end/controllers/user_controller.py`: impede redefinição de senha sem prova de identidade.
- `Programacao_front-end/index.html` e `static/js/auth.js`: acesso à nova área para profissionais habilitados.
- `Programacao_front-end/login.html` e `static/js/login.js`: destino após login e aviso de recuperação indisponível.

## Endpoints

Todos os novos endpoints exigem JWT e perfil profissional ativo no banco:

| Método | Rota | Resultado |
| --- | --- | --- |
| GET | `/profissional/me` | Perfil autenticado |
| GET | `/profissional/dashboard` | Resumo e seis próximos atendimentos |
| GET | `/profissional/pacientes?busca=nome` | Pacientes vinculados e datas resumidas |
| GET | `/profissional/pacientes/<id>` | Paciente vinculado e consultas com o profissional |
| GET | `/profissional/consultas?data=AAAA-MM-DD` | Agenda, opcionalmente filtrada por dia |
| GET | `/profissional/consultas?historico=1` | Consultas finalizadas |
| POST | `/profissional/consultas` | Criação com `paciente_id`, `inicio` ISO 8601 com fuso, `tipo` |
| PATCH | `/profissional/consultas/<id>/status` | Alteração com `status` |

`POST /esqueci_senha` foi modificado para retornar 403 e uma explicação, sem atualizar o banco. As demais APIs anteriores mantêm seus contratos.

## Autorização e privacidade

O JWT fornece identidade, expiração e versão de sessão. Cada requisição consulta `usuarios` e exige conta ativa e role atual `medico` ou `psicologo`, além de perfil ativo em `profissionais`. Pacientes e administradores não recebem acesso profissional. O cadastro público cria somente pacientes e ignora campos de papel enviados pelo cliente. Bloqueios invalidam a versão dos tokens antigos, inclusive após reativação.

O servidor obtém o profissional do JWT, não do corpo ou da URL. Todas as consultas SQL usam esse ID; detalhes, consultas, resumos, agendamentos e alterações de status exigem vínculo ativo em `profissional_pacientes` e paciente ativo. Encerrar um vínculo preserva a linha e os históricos, mas recusa novos acessos com o mesmo JWT imediatamente após a transação. O profissional não pode listar todos os usuários nem criar vínculos via HTTP. Respostas têm `Cache-Control: no-store`, e falhas de banco não retornam detalhes de conexão. Conteúdos da interface são escapados antes da renderização.

Como o frontend é estático, `profissional.html` entrega somente a estrutura pública, sem dados embutidos. O painel só é exibido após `/profissional/me`; todas as informações e ações privadas ficam protegidas no backend, inclusive se alguém ignorar o JavaScript. Não é uma rota Flask de HTML com sessão em cookie.

As tabelas novas usam RLS sem políticas públicas para impedir leitura pela Data API do Supabase. O backend deve conectar com o papel confiável proprietário das tabelas (ou outro papel de servidor adequadamente autorizado). Não use uma credencial pública `anon` no backend e não crie políticas irrestritas para essas tabelas. A autorização entre profissionais continua sendo aplicada pelo Flask/SQL.

O armazenamento do JWT em `localStorage` foi mantido para compatibilidade. Isso não representa uma certificação de conformidade com a LGPD; retenção, auditoria e procedimentos de autorização do paciente dependem da operação da plataforma.

## Banco e ativação

A migração cria, no banco existente:

- `profissionais`: extensão de `usuarios`, com profissão, registro, especialidade opcional e habilitação.
- `profissional_pacientes`: vínculo explícito, único e com data de criação.
- `consultas`: profissional/paciente vinculados, início, tipo e status.

Não altera as tabelas `usuarios` ou `tarefas`, não concede papéis automaticamente e não insere dados fictícios. A chave estrangeira composta impede consultas sem vínculo. Um índice único impede duas consultas não canceladas do mesmo profissional no mesmo instante. O agendamento não possui duração, portanto não faz verificação de sobreposição de intervalos.

1. Confira o schema existente e configure `SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` no ambiente ou `.env` do backend. Use o mesmo segredo JWT já utilizado pela aplicação. Gemini continua com suas configurações atuais.
2. Execute o diagnóstico `preflight_admin.sql` no banco de desenvolvimento e confira o schema real. Aplique `Programacao_back-end/migrations/001_area_profissional.sql` se ainda não aplicada, seguido de `002_roles_admin_auditoria.sql`, como papel confiável do backend. As migrations não são executadas ao iniciar a aplicação. Verifique a compatibilidade de `usuarios.id` com as referências inteiras e os campos/roles existentes. Crie o primeiro administrador conforme `AREA_ADMIN.md` antes dos comandos abaixo; a interface administrativa passa a gerenciar perfis e vínculos.
3. Use o cadastro existente para criar as contas que ainda não existem. Após verificar identidade e registro, habilite o profissional pelo terminal do backend:

```sh
cd Programacao_back-end
python -m pip install -r requirements.txt
python -m flask --app app profissional-autorizar --admin-email admin@example.com --email profissional@example.com --tipo psicologo --registro 'CRP verificado' --especialidade 'Psicologia'
python -m flask --app app profissional-vincular --admin-email admin@example.com --profissional-email profissional@example.com --paciente-email paciente@example.com --consentimento-confirmado
```

O vínculo exige autorização previamente verificada pela equipe; a opção confirma essa verificação, mas não substitui o registro do consentimento no procedimento operacional. Esses comandos não são endpoints públicos. Para revogar:

```sh
python -m flask --app app profissional-revogar --admin-email admin@example.com --email profissional@example.com
```

4. Inicie o backend e o servidor estático em terminais separados, a partir da raiz:

```sh
python -m flask --app Programacao_back-end/app run --port 5000
python -m http.server 5500 --directory Programacao_front-end
```

5. Acesse `http://localhost:5500/login.html`. A conta habilitada será direcionada a `profissional.html`. Em produção, publique também a página e seus assets no mesmo frontend; a URL Render existente continua sendo utilizada. Aplique a migração antes de habilitar o novo módulo.

## Regras da agenda

- Tipos: consulta médica para médicos, consulta psicológica para psicólogos e retorno para ambos.
- Agendamento requer data futura com fuso horário; a interface usa Brasília (`America/Sao_Paulo`, entrada com offset `-03:00`).
- Fluxo: `agendada → confirmada → em_atendimento → finalizada`.
- `agendada` e `confirmada` podem ir para `cancelada`.
- O atendimento só pode iniciar no horário marcado ou depois dele.
- Estados finalizados/cancelados não podem ser reabertos neste módulo.

## Validação

Testes executados neste checkout:

- **21 testes unitários passaram**: JWT ausente/inválido/expirado, médicos/psicólogos, usuários sem perfil, revogação, IDs forjados, vínculos, payloads inválidos, conflitos, transições, parametrização SQL, recuperação bloqueada e contratos existentes de login/cadastro/tarefas/health/auth do chat.
- **Smoke de navegador passou no Chrome**: login/logout, navegação, busca, texto potencialmente malicioso, detalhes, criação de consulta, atualização de status, perfil, histórico, vazio, 401/403/503 e nova tentativa.
- **Responsividade em 1440, 768, 390 e 320 pixels**, sem transbordamento horizontal da página; as tabelas têm rolagem interna. Capturas inspecionadas em `/private/tmp/infohelp-review`.
- Nenhuma exceção JavaScript no smoke; sintaxe Python/JavaScript e `git diff --check` aprovados.

Os testes de backend substituem o acesso ao banco por mocks, e os testes de navegador interceptam APIs com fixtures. **Não foi executada a migração nem validado SQL contra um PostgreSQL real**: não há configuração de banco neste checkout e a inspeção do Docker não foi autorizada. A chamada externa ao Gemini também não foi executada.

Para repetir os testes isolados:

```sh
cd Programacao_back-end
python -m unittest discover -s tests -v
```

O teste visual tem dependência opcional, não adicionada às dependências de produção:

```sh
python -m pip install playwright
PLAYWRIGHT_CHANNEL=chrome python Programacao_back-end/tests/browser_professional.py
```

Execute o comando visual a partir da raiz com Chrome instalado; alternativamente instale o Chromium do Playwright e omita `PLAYWRIGHT_CHANNEL`. O teste usa arquivos locais e fixtures; fontes e CSS externos ainda precisam de acesso à rede.

Antes de publicar, valide no banco de homologação: aplicar migração, autorizar dois profissionais, vincular pacientes diferentes, conferir que A não lê/agende/altere registros de B, criar consultas, tentar duplicar horário, finalizar um atendimento, revogar um perfil e confirmar a rejeição do JWT antigo. Confira também que `anon`/`authenticated` não leem as três tabelas pela Data API.

## Evoluções futuras

- Recuperação de senha por link temporário de uso único e revisão do ciclo de sessão.
- Fluxo de autorização/revogação do vínculo pelo paciente, com trilha de auditoria e política de retenção.
- Paginação para listas grandes, duração de consultas e detecção de sobreposição de horários.
