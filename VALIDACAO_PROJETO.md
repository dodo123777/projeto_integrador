# Validação do projeto — 17/09/2026

Os testes locais passaram. A conexão com o Supabase funciona, mas o backend atual ainda não consegue fazer login nesse banco porque faltam migrations. A API Gemini recusou a chave configurada.

## Testes executados

| Verificação | Resultado |
| --- | --- |
| Autenticação PostgreSQL, TLS e `SELECT 1` | Passou no Supabase remoto |
| Inspeção das tabelas e colunas | Executada em transação somente de leitura |
| Consultas de tarefas e estatísticas | Passaram usando usuário inexistente; sem ler tarefas de usuários reais |
| Suíte Python | 54 testes passaram, com banco e provedor de IA simulados |
| Interface do profissional | Passou: busca, agenda, status, perfil, login/logout, permissões e erros |
| Interface administrativa | Passou: paginação, promoção, bloqueio, vínculos, perfil e confirmações |
| Interface do paciente | Passou: criar/concluir/reabrir/remover tarefas, progresso, gráficos, modo foco e sessão expirada |
| Renderização de conteúdo malicioso | Passou nos fluxos testados de tarefas, profissionais, administração e chat |
| Responsividade | Três interfaces testadas em 1440, 768, 390 e 320 px sem transbordamento horizontal |
| Sintaxe Python/JavaScript e `git diff --check` | Passaram |
| Login com banco real | Retornou 503: colunas exigidas pelo backend ainda não existem |
| Configuração Gemini | HTTP 400 `INVALID_ARGUMENT`: `API key not valid. Please pass a valid API key.` |

Os testes de navegador usaram Chromium de testes separado, com APIs interceptadas e dados fictícios. Nenhum perfil do Chrome foi aberto. Os testes de criação, alteração e remoção não escreveram no banco remoto.

## Estrutura encontrada no Supabase

- `usuarios`: `id BIGINT`, `nome`, `email`, `senha`; faltam `role`, `ativo`, `auth_version` e `criado_em`.
- `tarefas`: contém as colunas exigidas pelo modelo atual; `id` e `usuario_id` são `BIGINT`.
- Não existem `profissionais`, `profissional_pacientes`, `consultas` e `auditoria_admin`.
- Foram encontrados 7 usuários, sem grupos de e-mails duplicados ao ignorar maiúsculas/minúsculas. Não foram exportados nomes, e-mails ou senhas.
- RLS está habilitada em `usuarios` e `tarefas`, sem policies nessas tabelas. O papel da conexão tem `BYPASSRLS`; o isolamento dessa conexão continua dependendo do backend. Acessos da Data API, grants e concorrência não foram validados.

As migrations `001_area_profissional.sql` e `002_roles_admin_auditoria.sql` foram ajustadas localmente para usar referências `BIGINT`, compatíveis com os IDs encontrados. **Nenhuma migration foi aplicada.** Não houve criação de contas, mudança de permissões, alteração de registros ou deploy no banco real.

## Para testar os fluxos completos no banco

1. Revisar/aplicar as migrations, na ordem 001 e 002, no ambiente destinado à validação. O backend não as aplica automaticamente.
2. Criar o primeiro administrador pelo comando documentado em `AREA_ADMIN.md` e preparar contas de teste com vínculos.
3. Repetir login, promoção, vínculos, consultas e bloqueio usando contas de teste reais, incluindo remoção de vínculo com o mesmo JWT e concorrência.
4. Configurar uma chave Gemini aceita pela API e confirmar um modelo disponível. O modelo configurado termina em `-1t` (dígito um), enquanto a captura apresentada terminava em `-it`; a disponibilidade não pôde ser verificada porque a chave foi recusada. Não foi feita geração real de conteúdo.

## Repetir os testes locais

```sh
cd Programacao_back-end
python -m unittest discover -s tests -q
```

Da raiz, com Playwright e Chromium instalados:

```sh
python Programacao_back-end/tests/browser_patient.py
python Programacao_back-end/tests/browser_professional.py
python Programacao_back-end/tests/browser_admin.py
```

Opcionalmente, `PLAYWRIGHT_EXECUTABLE_PATH` seleciona um executável Chromium de testes já instalado. As capturas desta execução estão em `/private/tmp/infohelp-patient-review`, `/private/tmp/infohelp-review` e `/private/tmp/infohelp-admin-review`. Os diagnósticos sem credenciais estão em `/private/tmp/infohelp-validation`.
