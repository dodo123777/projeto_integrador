# InfoHelp — telas de acesso

final result: passed

Referência visual: `/private/tmp/infohelp-auth-review/source-agenda-desktop.png`.
Implementação inicial: `/private/tmp/infohelp-auth-review/login-1440.png`,
`login-touch-mobile.png`, `register-320.png` e `reset-390.png` no mesmo diretório.

Comparação conjunta: referência da agenda e telas implementadas abertas no mesmo
input visual. A referência orienta tipografia, paleta e controles; agenda e
autenticação são fluxos distintos, portanto a composição é uma adaptação
intencional, não uma reprodução pixel a pixel.

## Iteração 1

- [P2] Título sem espaço após a vírgula no celular. Evidência:
  `login-touch-mobile.png` e `register-320.png` mostram “Sua rotina,no seu ritmo.”
  Correção: preservar espaço no HTML quando a quebra de linha é ocultada.
- [P2] Apresentação repetida acima do cadastro e recuperação no celular prolonga
  esses fluxos. Evidência: `register-320.png` e `reset-390.png`.
  Correção: ocultar a introdução nesses dois estados, mantendo marca e cartão.

## Iteração 2 — revisão após correções

Novas capturas, sobrescrevendo os caminhos da implementação inicial, foram
abertas junto à referência no mesmo input visual. O título agora preserva o
espaço após a vírgula. Cadastro e recuperação no celular começam diretamente
pelo cartão abaixo da marca, reduzindo a rolagem. Não restam achados P0/P1/P2.

## Iteração 3 — personalidade e linguagem mais próxima

A pedido do usuário, a apresentação passou de uma lista de benefícios para
“Vamos por partes?” e um exemplo concreto de pequeno passo: “Ler uma página.”
Saíram o selo com folha, ícones de benefícios e títulos em caixa alta. As cores
da agenda e os controles existentes foram preservados. O cadastro pergunta
como chamar a pessoa; a confirmação usa seu primeiro nome via textContent.
Erros de credenciais e e-mail já cadastrado explicam o próximo passo.

Referências desta revisão: `source-agenda-desktop.png` e
`previous-login-1440.png`. As novas capturas `login-1440.png`,
`login-touch-mobile.png`, `register-320.png`, `reset-390.png` e
`register-success-desktop.png` foram abertas com essas referências no mesmo
input visual. A diferença na composição e no conteúdo é intencional; a paleta,
hierarquia dos formulários e legibilidade permanecem consistentes.
Sem novos achados P0/P1/P2. `browser_auth.py` passou novamente, incluindo
mensagens atualizadas, nome na confirmação e todos os destinos de acesso.

## Evidência e normalização

- Referência da agenda: 1440 × 1000 px, viewport CSS 1440 × 1000.
- Login desktop: `login-1440.png`, 1440 × 1000 px, mesmo viewport.
- Login com toque: `login-touch-mobile.png`, 390 × 1000 px, viewport 390 × 844;
  captura da página inteira para incluir o cadastro e rodapé abaixo da dobra.
- Cadastro estreito: `register-320.png`, 320 × 835 px, viewport 320 × 740;
  captura da página inteira, com rolagem vertical permitida.
- Recuperação: `reset-390.png`, 390 × 844 px, viewport 390 × 844.
- Densidade em todos os casos: deviceScaleFactor 1; não houve redimensionamento.
- Estados adicionais: erro de credenciais em `login-error-desktop.png`, sucesso
  de cadastro em `register-success-desktop.png`, falha temporária da sessão em
  `session-error-mobile.png`. Todos no diretório da referência.

A comparação completa confirmou hierarquia, contraste visual, alinhamento e
adaptação responsiva. Os rótulos, campos, botões e mensagens são legíveis nas
capturas em escala 1:1, especialmente nas capturas móveis; não foi necessário
um recorte adicional para julgar esses controles. A agenda autenticada fornece
a referência de estilo, enquanto login/cadastro/recuperação são estados de
autenticação distintos e intencionalmente têm outra disposição.

## Superfícies verificadas

- **Fontes e tipografia:** mesma família Inter e fallback system-ui da agenda;
  hierarquia consistente em títulos, rótulos e texto auxiliar, sem truncamento.
  Nos testes isolados Google Fonts foi bloqueado e as duas telas usam o mesmo
  fallback. O carregamento da Inter pelo CDN não foi validado nesta execução.
- **Espaçamento e layout:** campos de 50 px, intervalos regulares, cartões
  brancos, bordas leves e sombra discreta. Layout em duas colunas no desktop e
  coluna única no celular. Não há rolagem horizontal em 1440/1024/768/390/320 px.
  Raios maiores que os da agenda são uma adaptação intencional da tela de entrada.
- **Cores:** fundo #f7f9fc → #eef2f7, azul #0f4662/#10344a e teal #0f7a8c
  acompanham a agenda. Estados de erro e sucesso incluem texto explicativo;
  navegação por teclado tem contorno visível.
- **Imagens e ícones:** logo UNISAL original, com proporção e transparência
  preservadas; ícones da mesma biblioteca Font Awesome usada na agenda.
- **Conteúdo:** instruções curtas, rótulos persistentes e confirmação de cadastro
  no cartão. Recuperação informa a indisponibilidade real do serviço, sem
  prometer envio de e-mail ou alterar credenciais.

## Verificação de interação

`browser_auth.py` passou com API simulada: envio por Enter no formulário correto,
validações, foco no campo com erro, mostrar/ocultar senha, navegação, bloqueio de
requisições duplicadas, confirmação de cadastro sem alert, destinos dos três
perfis, sessão preservada em 503 e removida em 401. Navegação móvel com toque
verificou fonte de 16 px e alvo de 44 px para recuperação. Sem erros JavaScript.

As regressões existentes `browser_professional.py` e `browser_admin.py` também
passaram, incluindo login/logout e redirecionamento para as páginas reais do
frontend com APIs fictícias. Não foram usados dados ou senhas de contas reais.

## Checklist final

- [x] Paleta e tipografia alinhadas à agenda aprovada.
- [x] Login, cadastro, recuperação, erros e sucesso revisados no navegador.
- [x] Achados P2 da primeira comparação corrigidos e recapturados.
- [x] Desktop, tablet, celular e teclado verificados.
- [x] Limite atual da recuperação de senha descrito com clareza.

Limites: a recuperação por e-mail continua indisponível no backend. Os testes
usam APIs simuladas; entrega de e-mail e credenciais reais não foram testadas.
