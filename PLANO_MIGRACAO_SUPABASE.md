# Adaptação ao Supabase existente — proposta para aprovação

**Status: análise concluída, código local adaptado e SQL preparado. Nenhuma migration executada. A aplicação no Supabase depende da confirmação do usuário.**

## Diagnóstico real de 17/09/2026

A análise usou as credenciais privadas do backend e uma transação PostgreSQL `READ ONLY`, com limite de tempo. Foram consultados metadados e contagens; não foram exportados nomes, e-mails, tarefas ou hashes de senha.

| Tabela existente | Coluna | Tipo real | Restrições observadas |
| --- | --- | --- | --- |
| `usuarios` | `id` | `BIGINT` | Identity BY DEFAULT, PK e UNIQUE |
| `usuarios` | `nome` | `TEXT` | Aceita NULL |
| `usuarios` | `email` | `TEXT` | NOT NULL e UNIQUE, sensível a maiúsculas |
| `usuarios` | `senha` | `TEXT` | Aceita NULL |
| `tarefas` | `id` | `BIGINT` | Identity BY DEFAULT, PK e UNIQUE |
| `tarefas` | `usuario_id` | `BIGINT` | NOT NULL, FK para `usuarios(id)` com ON DELETE CASCADE |
| `tarefas` | `data` | `DATE` | NOT NULL |
| `tarefas` | `texto` | `TEXT` | NOT NULL |
| `tarefas` | `horario`, `deadline` | `TIME WITHOUT TIME ZONE` | NOT NULL |
| `tarefas` | `concluida` | `BOOLEAN` | NOT NULL |

Existem **7 usuários e 14 tarefas**. Todos os usuários têm nome/senha presentes e hashes com formato bcrypt compatível. Não há grupos de e-mail duplicado ao ignorar maiúsculas/minúsculas, nem tarefas sem usuário. A análise de formato não comprova o login individual: isso requer a senha da própria conta.

Somente `usuarios` e `tarefas` existem no schema público. Ambas são de propriedade de `postgres`, têm RLS habilitada e não possuem policies. A conexão atual usa `postgres`, com `BYPASSRLS`. `anon` e `authenticated` têm grants amplos, incluindo TRUNCATE; a ausência de policies bloqueia operações por linha, mas não equivale a remover esses grants.

## Comparação com a implementação anterior

| Funcionalidade | Dependência anterior | Proposta compatível com a exigência atual |
| --- | --- | --- |
| Login único e sessão | `usuarios.role`, `ativo`, `auth_version` | Adicionar colunas à mesma tabela; preservar bcrypt/JWT |
| CRP/especialidade/habilitação | Tabela `profissionais` | Adicionar campos em `usuarios`; não criar outra tabela de pessoas |
| Administração | Novas colunas em `usuarios` e auditoria | Manter identidade e senha em `usuarios` |
| Vínculo | FK do profissional para `profissionais` | Ambos os participantes referenciam `usuarios(id)` |
| Consultas | FK para o par profissional/paciente | Preservar vínculo mesmo após encerramento |
| Auditoria | IDs de usuários em `auditoria_admin` | Manter referências à única tabela de usuários |

As versões anteriores de 001/002 **não foram aplicadas no banco inspecionado**, por isso foram revisadas antes de sua primeira aplicação. Se uma nova inspeção encontrar `profissionais`, os scripts interrompem a execução: não removem essa tabela ou tentam transferir seus registros automaticamente.

As roles aprovadas nesta proposta são `paciente`, `psicologo` e `admin`. A compatibilidade anterior com `medico` foi retirada do código local e do SQL; não havia roles ou perfis médicos no banco real. Um schema diferente com roles incompatíveis exige nova análise, sem conversão silenciosa.

## Tabela alterada: usuarios

`id`, `nome`, `email`, `senha`, identidade, PK, índices e unicidade existentes são preservados.

| Nova coluna | Tipo | Tratamento dos usuários atuais | Novos cadastros |
| --- | --- | --- | --- |
| `role` | `VARCHAR(20) NOT NULL` | `paciente` | DEFAULT `paciente`; cadastro público não concede role |
| `ativo` | `BOOLEAN NOT NULL` | `TRUE` | DEFAULT `TRUE` |
| `auth_version` | `INTEGER NOT NULL` | `0` | DEFAULT `0`; bloqueio incrementa e revoga tokens anteriores |
| `criado_em` | `TIMESTAMPTZ`, aceita NULL | `NULL`: data histórica desconhecida | DEFAULT `CURRENT_TIMESTAMP` |
| `registro` | `VARCHAR(60)`, aceita NULL | `NULL` | Preenchido na promoção administrativa para psicólogo |
| `especialidade` | `VARCHAR(120)`, aceita NULL | `NULL` | Opcional no perfil profissional |
| `perfil_profissional_ativo` | `BOOLEAN NOT NULL` | `FALSE` | DEFAULT `FALSE`; promoção habilita explicitamente |

Constraints restringem role aos três valores e exigem registro não vazio para psicólogo. Perfil profissional habilitado só é permitido para role psicólogo. A alteração de role e dos campos profissionais ocorre no mesmo UPDATE, com auditoria na mesma transação.

`tarefas` não recebe colunas nem mudança de FK, tipos ou conteúdo. A migration 002 ajusta somente suas permissões públicas e preserva RLS habilitada. A FK antiga com ON DELETE CASCADE não é modificada; a aplicação administrativa usa bloqueio lógico, sem endpoint de exclusão de usuários.

## Apenas três tabelas serão criadas

### profissional_pacientes

- `profissional_id BIGINT` e `paciente_id BIGINT`, ambos FKs para `usuarios(id)`; PK composta pelo par.
- `vinculado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`.
- `ativo BOOLEAN NOT NULL DEFAULT TRUE` e `desvinculado_em TIMESTAMPTZ NULL`.
- Impede vínculo de usuário consigo mesmo; data de encerramento acompanha o estado ativo/inativo.
- Índice por paciente; a PK já atende buscas por profissional.

O banco valida identidade/FKs. O Flask/SQL verifica as roles atuais, conta ativa e habilitação profissional antes de criar o vínculo. A cada operação profissional relevante, consulta o vínculo atual e exige paciente ativo com role paciente. Um JWT não contém a lista de pacientes autorizados.

### consultas

- `id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY`.
- `profissional_id BIGINT`, `paciente_id BIGINT`, `inicio TIMESTAMPTZ`, `tipo VARCHAR(40)` e `status VARCHAR(20)`, obrigatórios.
- FK composta para `profissional_pacientes`; sem exclusão em cascata.
- Tipos `Consulta psicológica` e `Retorno`.
- Status `agendada` (default), `confirmada`, `em_atendimento`, `finalizada` ou `cancelada`.
- Índices por profissional/início e profissional/paciente/início. Índice único impede dois agendamentos não cancelados no mesmo instante para o mesmo profissional.

### auditoria_admin

- `id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY`.
- `administrador_id`, `usuario_afetado_id`, `profissional_id` e `paciente_id`: referências opcionais BIGINT para `usuarios(id)`.
- `acao VARCHAR(60) NOT NULL`, `detalhes JSONB NOT NULL DEFAULT '{}'` e `criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`.
- Índices por data e administrador/data; sem exclusão em cascata.

Não serão criadas tabelas de administradores, psicólogos, profissionais ou senhas adicionais. Não serão criados outro banco, sistema de login, policies permissivas ou vínculo automático.

## Preservação das contas existentes

Os 7 usuários passam a ser pacientes ativos. As 14 tarefas continuam com os mesmos IDs e referências. Senhas não são alteradas ou reprocessadas; o mesmo `/login` verifica o hash bcrypt existente. Não há promoção automática para administrador/psicólogo.

Tokens anteriores com identidade/expiração válidas e sem `ver` são tratados como versão zero, compatível com os usuários migrados. Isso pressupõe manter o mesmo SECRET_KEY da instância que emitiu o token. Depois de bloqueio, a versão incrementada impede reutilizar tokens antigos.

A primeira conta administrativa será uma **conta existente escolhida pelo responsável**, promovida pelo comando `admin-criar-primeiro`; o comando não será executado nessa fase. Depois, o administrador promove psicólogos e cria vínculos na interface, sem novas identidades ou senhas.

## Arquitetura real de autorização e RLS

Fluxo: navegador → API Flask com JWT próprio → psycopg2 → PostgreSQL Supabase. Não existe integração de autenticação com Supabase Auth nem envio de JWT do Flask para `auth.uid()`.

O Flask valida assinatura, expiração, identidade, conta ativa, role atual e versão de sessão. Modelos SQL usam parâmetros, IDs do usuário autenticado e vínculos atuais. Auditoria e alterações administrativas são transacionais.

**A proteção entre paciente/psicólogo/admin está no Flask e no SQL da aplicação. RLS não isola esses usuários na conexão atual**, que possui BYPASSRLS. A migration preserva RLS em `usuarios`/`tarefas` e habilita nas tabelas novas, sem policies públicas. Revoga privilégios diretos de PUBLIC/anon/authenticated nessas cinco tabelas e nas sequências novas, fechando o caminho público da Data API. Papéis privilegiados, inclusive service_role, continuam privilegiados; não são a identidade do paciente.

Isso acompanha o comportamento documentado: RLS sem policy nega acesso normal por linha, mas proprietários normalmente ignoram RLS e papéis BYPASSRLS sempre a ignoram. TRUNCATE/REFERENCES não são operações sujeitas à filtragem por linha. Fontes: [PostgreSQL](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) e [Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security).

Não serão adicionadas policies baseadas em `auth.uid()` que não correspondem aos IDs BIGINT/JWT atuais. Adotar RLS por usuário na conexão Flask exigiria outra proposta: papel sem bypass, contexto de identidade por transação e policies compatíveis.

## Aplicação proposta — somente depois da confirmação

1. Repetir `preflight_admin.sql` e comparar com este diagnóstico para detectar mudanças desde a análise.
2. Obter exportação privada verificável do schema e de `usuarios`/`tarefas`, mantendo o banco atual. Não recriar tabelas.
3. Usar janela de manutenção e aplicar **001 revisada e depois 002 revisada**, com o papel confiável atual. Cada arquivo usa transação, `lock_timeout=5s` e `statement_timeout=60s`. Interromper na primeira falha.
4. Executar `postflight_admin.sql` somente de leitura, comparar IDs/hashes/referências com a exportação e conferir contagens estáveis durante a manutenção. Após migration, nenhum usuário deve virar admin/psicólogo automaticamente.
5. Usar o backend adaptado, testar login com uma conta existente e CRUD com dados de teste previamente autorizados. Definir a conta para bootstrap administrativo, ainda sem aplicar promoção automaticamente.
6. Testar duas contas profissionais, vínculos diferentes, retirada de vínculo com mesmo JWT, bloqueio/reativação e auditoria; validar grants/papéis da Data API. Só então publicar a versão adaptada.

## Riscos e recuperação

- ALTER TABLE exige locks. O limite de 5s interrompe a transação em caso de concorrência, em vez de aguardar indefinidamente.
- Cada arquivo é atômico, mas os dois arquivos não constituem uma transação única. Se 001 concluir e 002 falhar, manter manutenção e corrigir/reexecutar 002 após diagnóstico; não desfazer removendo usuários/tarefas. O backend antigo continua compatível com as colunas adicionais, mas o atual só fica completo após ambas.
- Não usar os scripts antigos publicados na PR inicial: esta proposta revisa ambos. `IF NOT EXISTS` ajuda repetição, mas não garante compatibilidade com schema arbitrariamente diferente; reanalisar qualquer divergência antes de aplicar.
- A revogação de grants pode afetar integrações externas que usam diretamente anon/authenticated. O frontend deste repositório chama Flask; integrações externas precisam ser confirmadas antes da aplicação.
- A data real dos cadastros antigos é irrecuperável pelo schema atual; fica NULL, exibida como `—`.
- Os índices únicos de consultas restringem horário inicial idêntico, não sobreposição de duração: o modelo atual não registra duração.
- Roles/vínculos continuam dependendo das verificações do backend em todas as operações relevantes. Não alegar isolamento por usuário via RLS na conexão privilegiada atual.
- Uma reversão depois de COMMIT será planejada preservando colunas/tabelas/dados e usando a exportação privada como referência. Não há script automático DROP/DELETE de rollback.
- A chave Gemini inválida identificada na validação anterior é independente da migration; não impede adaptar o banco, mas o chat real exige configuração aceita pelo provedor.

## Artefatos e validação local

- `001_area_profissional.sql`: incrementos em usuarios, vínculos e consultas, sem tabela profissionais.
- `002_roles_admin_auditoria.sql`: auditoria e permissões/RLS.
- `preflight_admin.sql`: diagnóstico antes, somente leitura.
- `postflight_admin.sql`: conferência depois, somente leitura; não executado nesta fase.
- Models, comandos e seleção de área adaptados à identidade única em usuarios e às três roles.
- SQL e blocos PL/pgSQL validados em parser local, sem conexão de escrita. A compatibilidade de execução e os fluxos reais pós-migration ainda dependem da aplicação aprovada.
- **56 testes Python passaram** com banco/IA simulados. As interfaces administrativa e profissional passaram novamente em Chromium de testes, sem usar perfis do Chrome, em 1440/768/390/320 px. Sintaxe Python/JavaScript e `git diff --check` passaram.

**Aguardar confirmação explícita para executar migrations.**
