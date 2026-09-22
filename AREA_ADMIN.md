# Área Administrativa — InfoHelp

## Resultado e arquitetura

A administração usa **o mesmo `/login`, a mesma tabela `usuarios`, bcrypt e JWT do restante da plataforma**. Não há tabela de senhas administrativas, senha fixa, login paralelo ou chave Supabase no navegador.

Adaptação ao banco real preparada e aguardando aprovação: [PLANO_MIGRACAO_SUPABASE.md](PLANO_MIGRACAO_SUPABASE.md). Não executar migrations antes da confirmação explícita. Dados profissionais agora ficam em `usuarios`, sem tabela `profissionais`.

O Flask consulta o banco para decidir a área de destino:

| Role em `usuarios` | Cadastro/concessão | Destino após login |
| --- | --- | --- |
| `paciente` | Todo cadastro público | `index.html` |
| `psicologo` | Promoção administrativa com perfil na mesma linha de `usuarios` | `profissional.html` |
| `admin` | Bootstrap protegido do primeiro administrador pelo terminal | `admin.html` |

O schema real não possui roles/perfis anteriores. A adaptação usa somente paciente, psicólogo e administrador, conforme a solicitação atual. O cadastro público não aceita concessão de papéis, mesmo se a requisição enviar `role`, `tipo` ou `user_type`.

O frontend recebe `role` e `destino` calculados pelo servidor após o login. Para uma sessão existente, consulta `GET /sessao`. Essas informações servem para navegação; a autorização de cada API permanece obrigatória no Flask.

## O que foi criado

- Dashboard com totais de usuários, pacientes, psicólogos, contas ativas/bloqueadas, vínculos e consultas, além de auditoria recente.
- Lista de usuários com busca por nome/e-mail e paginação, detalhes e vínculos relacionados.
- Promoção de pacientes ativos para psicólogo, mantendo o mesmo usuário e preenchendo CRP/especialidade.
- Bloqueio/reativação lógica, com revogação de sessões anteriores ao bloqueio.
- Lista e detalhes de psicólogos, edição de CRP/especialidade/habilitação do perfil, pacientes vinculados e busca de candidatos.
- Criação e encerramento de vínculos, com confirmações e feedback visual.
- Auditoria transacional: a alteração e seu registro são confirmados juntos; falha na auditoria desfaz a alteração.
- Proteção contra bloqueio da própria conta e do último administrador ativo.

As ações sensíveis usam um diálogo de confirmação. Nenhum dado fictício integra a aplicação: as fixtures ficam nos testes. Telefone, prontuário e dados clínicos não foram acrescentados.

## Arquivos desta etapa

Criados:

- `Programacao_front-end/admin.html`
- `Programacao_front-end/static/css/admin.css`
- `Programacao_front-end/static/js/admin.js`
- `Programacao_back-end/controllers/admin_controller.py`
- `Programacao_back-end/models/admin.py`
- `Programacao_back-end/admin_commands.py`
- `Programacao_back-end/migrations/002_roles_admin_auditoria.sql`
- `Programacao_back-end/migrations/preflight_admin.sql`
- `Programacao_back-end/tests/test_admin.py`
- `Programacao_back-end/tests/browser_admin.py`
- `AREA_ADMIN.md`

Modificados nesta evolução:

- `Programacao_back-end/app.py`: registra Blueprint e comando administrativo.
- `Programacao_back-end/auth.py`: verifica assinatura, expiração obrigatória, identidade, conta atual, ativação e versão de sessão no banco.
- `Programacao_back-end/models/user.py`: cadastro paciente e contexto de acesso atual.
- `Programacao_back-end/controllers/user_controller.py`: valida entradas, recusa contas bloqueadas e fornece destino por role; adiciona `/sessao`.
- `Programacao_back-end/controllers/task_controller.py`: passa a usar a mesma autenticação com verificação de conta ativa.
- `Programacao_back-end/controllers/professional_controller.py` e `models/professional.py`: exigem role atual e vínculo ativo também nas leituras, resumos, criação de consultas e alterações de status.
- `Programacao_back-end/professional_commands.py`: comandos antigos exigem uma conta administrativa ativa para autorizar/auditar operações; não promovem ou revogam administradores.
- `Programacao_front-end/index.html`, `static/js/login.js` e `static/js/auth.js`: navegação por role e link administrativo.
- `Programacao_front-end/chat.html` e `static/js/chat.js`: sanitização das respostas Markdown com DOMPurify e fallback seguro em texto.
- `Programacao_front-end/static/js/tasks.js`: texto de tarefas inserido com `textContent`.
- `Programacao_front-end/static/js/profissional.js`: diferencia paciente não vinculado de revogação da permissão profissional.
- `Programacao_back-end/tests/test_professional.py` e `tests/browser_professional.py`: adaptados à autenticação atual.
- `AREA_PROFISSIONAL.md`: atualizado para a nova fonte de autorização e ativação administrativa.

O CSS administrativo reutiliza `style.css` e `profissional.css`, incluindo fonte, cores, botões, inputs, cards, sidebar e comportamento móvel.

## Tabelas e migrations

Tabelas reais existentes: `usuarios` e `tarefas`.

A migration 001 revisada adiciona em `usuarios`: `role`, `ativo`, `auth_version`, `criado_em`, `registro`, `especialidade` e `perfil_profissional_ativo`. Cria `profissional_pacientes` e `consultas`, com referências BIGINT diretamente à identidade em `usuarios`. Não cria `profissionais`.

A migration 002 revisada cria `auditoria_admin`, preserva/habilita RLS e revoga grants de PUBLIC/anon/authenticated em contas, tarefas, vínculos, consultas e auditoria. Nenhuma identidade ou senha é criada pela migration. Campos/tipos/dados de `tarefas` não mudam.

Não há `DROP`, reset de banco, exclusão de usuário/consulta ou banco paralelo. A chave estrangeira das consultas continua apontando para o vínculo, que é preservado ao ser encerrado. Reativar um vínculo atualiza suas datas; os períodos anteriores continuam registrados na auditoria.

`criado_em` dos registros anteriores fica `NULL`, pois a data histórica é desconhecida. Novos cadastros recebem `CURRENT_TIMESTAMP`. A interface mostra `—` quando não há data; não se inventa a data real de cadastro.

**Migrations criadas/preparadas, nenhuma aplicada.** Em 17/09/2026, a conexão do `.env` privado foi validada e o schema remoto foi consultado somente em leitura: existem `usuarios` e `tarefas`, mas faltam as colunas e tabelas novas. Os IDs reais são `BIGINT`; as referências das migrations foram ajustadas para esse tipo. Antes da aplicação, execute `preflight_admin.sql` no desenvolvimento e confira colunas existentes, roles, constraints, proprietários, RLS/policies e grants. Resultados completos em [VALIDACAO_PROJETO.md](VALIDACAO_PROJETO.md).

## Rotas administrativas

Todas exigem JWT válido, usuário existente/ativo e `usuarios.role = 'admin'` atual:

| Método | Endpoint | Uso |
| --- | --- | --- |
| GET | `/admin`, `/admin/`, `/admin/me` | Identidade administrativa protegida |
| GET | `/admin/dashboard` | Indicadores e auditoria recente |
| GET | `/admin/usuarios?busca=&pagina=1&por_pagina=20&role=` | Busca e paginação; máximo de 100 por página |
| GET | `/admin/usuarios/<id>` | Dados administrativos do usuário |
| GET | `/admin/usuarios/<id>/vinculos` | Vínculos ativos e encerrados do usuário |
| POST | `/admin/usuarios/<id>/promover-psicologo` | `registro`, `especialidade`, `confirmacao: true` |
| PATCH | `/admin/usuarios/<id>/status` | `ativo` booleano e `confirmacao: true` |
| GET | `/admin/psicologos?busca=&pagina=1&por_pagina=20` | Lista de psicólogos |
| GET | `/admin/psicologos/<id>` | Perfil e vínculos |
| PATCH | `/admin/psicologos/<id>/perfil` | CRP/especialidade e habilitação do perfil; confirmação obrigatória |
| GET | `/admin/vinculos?busca=&pagina=1&por_pagina=20` | Vínculos ativos/encerrados |
| POST | `/admin/vinculos` | `psicologo_id`, `paciente_id`, `confirmacao: true` |
| DELETE | `/admin/vinculos/<psicologo_id>/<paciente_id>` | Encerramento lógico; exige `confirmacao: true` |
| GET | `/admin/auditoria` | Até 100 ações recentes |

Não foi criado endpoint para o cliente escolher uma role arbitrária ou conceder `admin`. A promoção HTTP possui apenas o destino `psicologo` e exige que o usuário afetado seja um paciente ativo.

## JWT, vínculos e bloqueios

O JWT contém identidade, expiração e versão de sessão. **Não contém role autoritativa nem lista de pacientes**. Cada API protegida consulta a conta atual. Uma role enviada pelo cliente ou mesmo presente no JWT é ignorada para autorização.

Cada leitura relevante do profissional usa o ID do JWT e consulta o vínculo atual no banco, exigindo `vinculo.ativo`, paciente ativo e role paciente. Consultas, dashboard, criação de consultas e mudanças de status também verificam o vínculo. Um ID de paciente de outro profissional não concede acesso.

Encerrar o vínculo atualiza `ativo = false` e `desvinculado_em`. Após a transação de remoção ser confirmada, uma nova chamada do psicólogo com **o mesmo token** a `/profissional/pacientes/<id>` recebe 403. IDs inexistentes e pacientes não vinculados recebem a mesma mensagem, sem revelar informações adicionais. Informações já recebidas no navegador não podem ser retiradas retroativamente; novos acessos e operações são recusados no servidor.

Bloquear uma conta define `usuarios.ativo = false` e incrementa `auth_version`. Ela não pode realizar login, e tokens anteriores são recusados por todas as APIs protegidas, inclusive tarefas e chat. Reativação restaura a conta, mas não torna os tokens antigos válidos: é necessário novo login. Bloqueio não apaga consultas, históricos ou vínculos.

O administrador não pode bloquear a própria conta nesta interface. Bloqueios de administradores são serializados com locks de linha e verificam a existência de outro administrador ativo. Não há ação HTTP de remoção de role administrativa.

## Supabase, segredos e RLS

O projeto usa **conexão PostgreSQL direta via psycopg2**, com credenciais em variáveis de ambiente. Não usa Supabase Auth, supabase-js ou service role para chamar a Data API. A busca nos arquivos atuais não encontrou `SUPABASE_SERVICE_ROLE_KEY`, chave privada Supabase ou token administrativo real entregue ao frontend. Strings de teste são fixtures, não credenciais da plataforma.

O JWT HS256 do Flask não configura automaticamente `auth.uid()` no banco: as consultas usam o papel da conexão PostgreSQL, não a identidade do paciente/psicólogo. Habilitar RLS sem uma política de acesso produz negação por padrão para papéis normais; **proprietários de tabelas, superusuários e papéis `BYPASSRLS` podem ignorá-la**. Esse comportamento é descrito na [documentação do PostgreSQL](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) e na [documentação de RLS do Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security).

Assim, a proteção preparada no banco restringe o caminho público da Data API. A conexão confiável do backend, se proprietária, continua aplicando isolamento por Flask e SQL parametrizado. **Não é correto afirmar que RLS já reforça por paciente cada consulta dessa conexão.** Para isso seria necessário um papel dedicado sem bypass, contexto de identidade por transação e policies compatíveis, com validação no banco real.

O diagnóstico fornecido permite verificar proprietários, `rolbypassrls`, políticas preexistentes e grants, incluindo permissões herdadas/PUBLIC. A migration não exclui policies anteriores e não afirma que grants desconhecidos já foram auditados. A inspeção de 17/09/2026 confirmou RLS habilitada em `usuarios`/`tarefas`, sem policies nessas tabelas, e `BYPASSRLS` no papel da conexão. Isso não equivale a validar acessos da Data API. Aplique e teste com o papel real do backend; `anon`/`authenticated` não devem ler nem modificar contas, vínculos, perfis, consultas ou auditoria pela Data API.

## Primeiro administrador e início do projeto

1. Configure o mesmo PostgreSQL/Supabase existente e o segredo JWT já utilizado: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` e `SECRET_KEY` no ambiente ou no `.env` privado do backend. As configurações Gemini permanecem iguais. O `.env` é ignorado pelo Git.
2. No banco de desenvolvimento, execute o diagnóstico de leitura, confira conflitos e aplique `001_area_profissional.sql` se ainda não aplicada, seguido de `002_roles_admin_auditoria.sql`, preservando o ambiente existente. Use um papel confiável compatível com a configuração de RLS. A aplicação não executa migrations ao iniciar.
3. Crie a conta inicial pelo cadastro público normal, como paciente. Depois, no terminal confiável do backend:

```sh
cd Programacao_back-end
python -m pip install -r requirements.txt
python -m flask --app app admin-criar-primeiro --email seu-email@example.com --confirmacao 'CRIAR PRIMEIRO ADMIN'
```

O comando exige uma única conta paciente ativa com esse e-mail e só funciona se **não existir nenhum administrador**. Atualiza o usuário existente e registra a auditoria. Nenhuma senha é criada, alterada ou impressa. Use a senha normal dessa conta no login da plataforma.

4. Inicie o backend e o frontend em terminais separados, a partir da raiz:

```sh
python -m flask --app Programacao_back-end/app run --port 5000
python -m http.server 5500 --directory Programacao_front-end
```

URLs locais:

- Login único: `http://localhost:5500/login.html`
- Área Administrativa: `http://localhost:5500/admin.html`
- Área do Profissional: `http://localhost:5500/profissional.html`
- Agenda do paciente: `http://localhost:5500/index.html`

`admin.html` é a estrutura estática da interface, sem informações privadas embutidas. O painel só é mostrado após a autorização de `/admin/me`. A rota Flask `/admin` é uma API protegida de identidade, não o arquivo HTML; acessar o HTML público ou ignorar o JavaScript não concede acesso a dados ou ações administrativas.

Em produção, publique a nova página e assets no frontend já existente; a API Render existente permanece configurada. Aplique a migration antes de publicar o backend atualizado, pois o contexto de autenticação passa a consultar os novos campos.

Os comandos profissionais anteriores agora exigem `--admin-email` para identificar uma conta administrativa ativa e registrar a operação. Preferencialmente use a interface administrativa; a CLI é uma ferramenta de operação do servidor com acesso às credenciais do banco, não um endpoint acessível a pacientes.

## Testes, vulnerabilidades e pendências

Após a revisão para o banco real: **56 testes passaram**, incluindo promoção/edição profissional na mesma linha de `usuarios`, sem tabela de profissionais. SQL e blocos PL/pgSQL passaram em parser local. Interfaces profissional/administrativa passaram novamente com APIs simuladas. As validações descritas abaixo registram também as etapas anteriores.

Testes isolados executados: **54 passaram** em 17/09/2026, abrangendo autenticação, tarefas, chat, área profissional e administração. Incluem paciente/psicólogo recusados em todas as rotas administrativas, administrador permitido, busca/paginação, promoção, confirmação, bloqueio, reativação, roles ignoradas no payload/JWT, auditoria, bootstrap e proteção administrativa. Os testes de tarefas/chat usam banco e provedor simulados. A interface do paciente também passou no Chromium de testes; detalhes em [VALIDACAO_PROJETO.md](VALIDACAO_PROJETO.md).

O teste crítico de remoção usou os endpoints Flask e um estado de vínculo mutável no lugar do banco: GET com JWT do psicólogo → 200; remoção com JWT administrativo → 200; GET com o **mesmo JWT do psicólogo** → 403. Ele verifica o fluxo da aplicação, mas não equivale à execução SQL no PostgreSQL.

Os dois smokes visuais **passaram no Chrome**, sem exceções JavaScript: administração (busca/paginação, promoção, bloqueio/reativação, confirmações, edição do perfil, criação/remoção de vínculos, login/logout e 401/403), área profissional (incluindo paciente não vinculado sem derrubar o painel) e renderização maliciosa no chat sanitizada. Larguras verificadas: **1440, 768, 390 e 320 pixels**, sem transbordamento horizontal da página. Tabelas têm rolagem interna. Capturas foram inspecionadas em `/private/tmp/infohelp-admin-review` e `/private/tmp/infohelp-review`. Checagens de sintaxe Python/JavaScript e `git diff --check` também passaram.

Para repetir:

```sh
cd Programacao_back-end
python -m unittest discover -s tests -v
```

Testes de navegador com Playwright têm dependência opcional separada da produção:

```sh
python -m pip install playwright
PLAYWRIGHT_CHANNEL=chrome python Programacao_back-end/tests/browser_admin.py
PLAYWRIGHT_CHANNEL=chrome python Programacao_back-end/tests/browser_professional.py
```

Execute os testes visuais a partir da raiz com Chrome instalado; alternativamente instale Chromium do Playwright e omita a variável de canal. Eles servem arquivos locais e interceptam APIs com fixtures. Os recursos externos de fonte/CSS/sanitização precisam de rede.

Falhas encontradas e corrigidas:

- Tokens antigos podiam continuar acessando tarefas sem verificação de conta ativa.
- A autorização profissional estava inferida apenas pelo perfil, sem uma role autoritativa em `usuarios`.
- O vínculo não era rechecado no SQL de alteração de status de consulta; agora é obrigatório também nessa operação.
- A renderização Markdown do chat e texto de tarefas permitiam inserir HTML não confiável na origem que armazena o JWT; sanitização/texto seguro adicionados. O chat usa a versão fixa [DOMPurify 3.4.15](https://github.com/cure53/DOMPurify/releases/tag/3.4.15), com fallback em texto se os scripts externos estiverem indisponíveis.
- Tokens de contas bloqueadas poderiam voltar a funcionar após reativação; versão de sessão impede isso.
- Comandos profissionais antigos poderiam conceder/revogar roles sem conta administrativa e auditoria; foram restringidos.

A recuperação de senha sem prova de identidade já havia sido bloqueada na etapa anterior e permanece indisponível. Ela precisa de um fluxo seguro por link de uso único. O armazenamento de JWT em `localStorage` permanece por compatibilidade; mudanças de sessão/cookies, recuperação, limitação de tentativas de login e revisão de políticas operacionais podem ser tratadas em uma etapa específica.

**Pendências externas:** aplicação das migrations, validação dos fluxos SQL/RLS/grants no Supabase, testes concorrentes contra PostgreSQL, configuração de uma chave Gemini aceita pelo provedor, revisão operacional de consentimento/auditoria/retenção e publicação. A inspeção real de schema foi realizada; não houve alteração em banco real ou deploy.

Na homologação, repita com duas contas profissionais e pacientes diferentes: isolamento por ID, remoção/recriação de vínculo com JWT antigo, consultas após remoção, bloqueio de conta e tentativa com token antigo após reativação. Confira os acessos da Data API com os papéis reais e a conexão usada pelo Flask.
