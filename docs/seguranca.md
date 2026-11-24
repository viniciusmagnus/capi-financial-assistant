# Autenticação, sessões e isolamento dos dados

Este documento explica como o Capi decide quem é a pessoa, o que ela pode ler e por quê. Ele
também lista o que **não** está coberto. Nenhum sistema é "100% seguro"; o objetivo aqui é deixar
cada escolha explícita e testada.

## Visão geral

```
navegador ──cookie HttpOnly──▶ Next.js (Better Auth) ──JWT Ed25519, 5 min──▶ FastAPI ──▶ Postgres
                                   │                                          ▲
                                   └── /api/auth/jwks (chave pública) ────────┘
Claude Desktop/Code ──token pessoal capi_…──▶ FastAPI /mcp
```

- **Quem autentica é o Next.js**, com o [Better Auth](https://www.better-auth.com) 1.7.18: cadastro,
  login, verificação de e-mail, recuperação de senha, Google e sessões.
- **O FastAPI não confia em nada que venha do navegador.** O Next emite, a cada requisição e só no
  servidor, um JWT de 5 minutos assinado com Ed25519 para a sessão atual. O FastAPI confere a
  assinatura pela chave pública (JWKS), o emissor, a audiência, a validade, `email_verified` e se o
  usuário ainda existe e está verificado no banco. O `sub` do token é o único lugar de onde sai o
  `usuario_id`.
- **O MCP usa tokens pessoais**, criados em Conta, guardados só como SHA-256 e revogáveis.

### Por que Better Auth

- É mantido ativamente.
- Roda no próprio Next.js, onde já ficam os Server Actions e a sessão.
- Usa o Postgres que o projeto já tem.
- Traz pronto, sem criptografia ou protocolo escritos à mão, tudo o que o projeto precisava:
  - hash de senha;
  - tokens de verificação com expiração e uso único;
  - OAuth com state e PKCE;
  - sessões no banco com revogação;
  - limite de tentativas guardado no banco;
  - checagem de origem nas rotas de autenticação;
  - plugin de JWT com JWKS.

Antes de configurar, cada comportamento usado abaixo foi conferido no código da versão instalada,
não só na documentação.

O Auth.js foi descartado porque a manutenção dele passou para o próprio Better Auth. Já o
fastapi-users está em modo de manutenção, e adotá-lo obrigaria o front a falar de autenticação com
dois serviços.

## Cadastro, senha e e-mail

| Decisão | Por quê |
|---|---|
| Senha com hash **scrypt** (N=16384, r=16, p=1, chave de 64 bytes), o padrão do Better Auth | Algoritmo resistente a GPU recomendado pela OWASP; usa os parâmetros que a biblioteca recomenda e mantém. |
| Mínimo de **12** e máximo de **256** caracteres, sem regra de composição | Segue a linha do NIST SP 800-63B: comprimento vale mais que símbolos. O NIST pede 15 quando a senha é o único fator; 12 é um meio-termo de usabilidade, registrado como limitação. |
| Senha checada no **Have I Been Pwned** por k-anonimato | Só os 5 primeiros caracteres do SHA-1 saem do servidor. Se o serviço cair, o cadastro falha fechado. Desligável com `VERIFICAR_SENHA_VAZADA=false`. |
| Campos aceitam colar e gerenciador de senha, com `autocomplete` certo e botão de mostrar | Senha longa e única depende de gerenciador. |
| **Verificação de e-mail obrigatória** antes de qualquer dado financeiro | O login é recusado sem verificação, e o FastAPI recusa JWT sem `email_verified`. |
| Cadastro com e-mail já existente devolve **a mesma resposta** de um e-mail novo | O Better Auth calcula o hash da senha nos dois casos para aproximar o tempo de resposta. O dono do e-mail recebe um aviso de que tentaram criar uma conta. |
| Recuperação de senha sempre responde "se houver uma conta…" | Não revela se o e-mail existe. |
| Login responde "e-mail ou senha não conferem" | Mensagem única para os dois erros. |

### Tokens de verificação e de recuperação

- **Recuperação de senha:**
  - o token tem 30 minutos de validade;
  - é guardado na tabela `verification` só como SHA-256 (`verification.storeIdentifier: "hashed"`);
  - é consumido de forma atômica na troca, então serve uma vez só;
  - a troca encerra **todas** as sessões (`revokeSessionsOnPasswordReset`) e manda e-mail avisando.
- **Verificação de e-mail:**
  - o Better Auth usa um JWT HS256 de 24 horas, sem estado;
  - um gancho (`hooks` em `frontend/src/lib/auth.ts`) grava o hash do link já usado e recusa um segundo uso (`?error=LINK_USADO`);
  - a verificação **não** faz login sozinha (`autoSignInAfterVerification: false`), para que quem intercepte o e-mail não ganhe uma sessão.
- **Rate limit:**
  - o limitador do Better Auth usa o caminho da requisição como chave, e `/reset-password/<token>` colocaria o token em texto puro na tabela `rateLimit`;
  - esse GET, que só redireciona, fica fora da contagem;
  - o POST que de fato troca a senha continua limitado.

## Login com Google

- Fluxo OAuth 2.0 / OpenID Connect do Better Auth, com `state` guardado no servidor e PKCE.
- O redirect URI é fixo: `${BETTER_AUTH_URL}/api/auth/callback/google`.
- Escopos mínimos: `openid email profile`.
- Os tokens do Google são criptografados no banco (`encryptOAuthTokens`), embora o app não use.
- **Sem vinculação implícita:** `accountLinking.disableImplicitLinking: true`. Se já existe uma
  conta com o mesmo e-mail, o login com Google é recusado (`account_not_linked`) e a tela explica o
  caminho. Para vincular, a pessoa:
  - já está logada na conta do Capi, o que prova que a conta é dela;
  - completa o OAuth do Google pelo `linkSocial`, o que prova que o Google é dela;
  - usa um Google com o mesmo e-mail (`allowDifferentEmails: false`).
- Quem entrou só pelo Google cria uma senha pelo fluxo de recuperação, que prova o controle do
  e-mail.

## Sessões e rotas

- **Cookie:**
  - `capi.session_token`, `HttpOnly`, `SameSite=Lax`, `Path=/`;
  - em HTTPS ganha `Secure` e o prefixo `__Secure-`;
  - nada de autenticação vai para `localStorage`;
  - o `/api/auth/token` é bloqueado para o navegador e só o servidor gera JWT.
- **Validade e revogação:**
  - a sessão vale 7 dias e se renova a cada 24 horas de uso;
  - o cache de sessão em cookie está desligado, então uma revogação vale no próximo pedido;
  - a revogação acontece no logout, na recuperação de senha, ao trocar a senha (que derruba os outros aparelhos) e ao encerrar um aparelho específico em Conta.
- **Proteção em camadas:**
  - o `proxy.ts` faz só a checagem otimista: sem cookie, uma página privada manda para `/entrar?volta=…`;
  - a verificação de verdade acontece em cada página (`exigirUsuario`) e em cada chamada à API, porque o JWT só sai de uma sessão válida;
  - os Server Actions passam pela mesma `lib/api.ts`.
- **CSRF:**
  - os cookies são `SameSite=Lax`;
  - o Better Auth confere a origem nas rotas `/api/auth/*`;
  - os Server Actions têm a checagem de origem do Next;
  - as duas rotas próprias que recebem POST (`/api/importar` e `/api/chat`) recusam outra origem.
- **Redirecionamentos:** o parâmetro `volta` passa por `destinoSeguro`, que aceita só caminho interno e recusa:
  - `//host` e barra invertida;
  - esquemas como `javascript:`;
  - caracteres de controle, inclusive codificados;
  - as próprias páginas de entrada e a API.

  A função tem testes em `frontend/src/lib/destino.test.ts`. Nos fluxos do Better Auth, os `callbackURL` também são validados contra `trustedOrigins`.
- **Limite de tentativas** no Better Auth, guardado na tabela `rateLimit` do Postgres, então vale para várias instâncias:

  | Rota | Limite |
  |---|---|
  | login | 8 em 5 minutos |
  | cadastro | 5 por hora |
  | pedido de recuperação | 5 por hora |
  | troca de senha | 10 em 15 minutos |
  | reenvio de verificação | 5 por hora |
  | trocar senha logado | 5 em 15 minutos |

  A chave é IP + rota. Atrás de proxy, configure `AUTH_TRUSTED_PROXIES` ou `AUTH_IP_HEADERS`.
- **Segredos:** `BETTER_AUTH_SECRET`, as credenciais do Google, a URL do SMTP e a do banco ficam só no servidor. Nenhuma variável `NEXT_PUBLIC_` carrega segredo.

## Isolamento dos dados financeiros

Autenticar não basta: cada linha financeira tem dono, e o banco e o ORM impõem isso.

1. **Coluna `usuario_id` obrigatória** em todas as tabelas privadas: `contas`, `transacoes`,
   `lancamentos`, `importacoes`, `regras_categoria`, `perfil_financeiro`, `tetos_mensais`,
   `notas_fiscais`, `itens_nota` e `trechos` (os embeddings da busca). As chaves únicas passaram a
   ser por pessoa.
2. **Chaves estrangeiras compostas**, por exemplo `(conta_id, usuario_id) → contas(id, usuario_id)`.
   O banco recusa um lançamento que use a conta de outra pessoa, mesmo vindo de SQL escrito à mão
   (há teste para isso).
3. **Filtro central no ORM** (`backend/src/nota_a_nota/acesso.py`). Todo SELECT, UPDATE ou DELETE
   do SQLAlchemy recebe `with_loader_criteria(usuario_id = dono da sessão)`, inclusive em
   subconsultas e aliases. Uma sessão sem usuário que toque uma tabela privada **levanta erro**, em
   vez de devolver tudo. Objetos novos ganham o dono da sessão, e gravar um objeto com outro dono
   levanta `DonoDiferente`.
4. **O `usuario_id` nunca vem do cliente.** Na API ele sai do `sub` do JWT; no MCP, do token
   pessoal; no chat, da mesma requisição autenticada. Um id de registro de outra pessoa simplesmente
   não é encontrado (404).
5. **Caches por pessoa:** as falas da Capi ficam em memória com o `usuario_id` na chave, para não
   reaproveitar uma piada que cita a loja de outra pessoa.

Os testes de isolamento ficam em `backend/tests/test_isolamento.py`:

- duas pessoas passam por todas as rotas de leitura, e nada de uma aparece para a outra;
- uma tenta alterar transação, regra, token e teto da outra usando os ids reais;
- MCP e chat respondem só com os dados de quem chamou;
- a sessão sem usuário falha fechada;
- o banco recusa a chave composta cruzada;
- a memória da Capi não vaza entre pessoas.

Esses testes pegaram um vazamento real durante o desenvolvimento: uma contagem com
`select(func.count()).select_from(Transacao)` escapava do filtro. Ela foi corrigida antes de ir
para o código.

### O papel do `APP_TOKEN`

Ele **deixou de existir**. Um token compartilhado dava acesso a tudo e não diz de quem é o pedido,
então não tem como conviver com isolamento. Hoje existem só três caminhos:

- o JWT por usuário, emitido pelo Next;
- o token pessoal do MCP;
- o `/health`, público.

Se ainda houver `APP_TOKEN` ou `NOTA_APP_TOKEN` num `.env` antigo, eles são ignorados.

### Dados de antes da autenticação

A migration `0006` não entrega os dados antigos a ninguém automaticamente:

- **Banco vazio:** apaga as contas e regras semeadas, que agora são criadas por pessoa no primeiro acesso.
- **Banco com dados:** tudo vai para o usuário `legado-pre-autenticacao`. Ele tem e-mail
  `@nota-a-nota.invalid`, está sem verificação, sem senha e sem Google, então ninguém consegue
  entrar como ele.

Quem opera o servidor decide para quem vão os dados, depois que a pessoa criou a conta e confirmou
o e-mail:

```bash
cd backend
python -m nota_a_nota.legado --email voce@exemplo.com             # simula e mostra as contagens
python -m nota_a_nota.legado --email voce@exemplo.com --confirmar # transfere e apaga o dono legado
```

A ferramenta recusa destino não verificado e destino que já tem dados próprios, para não misturar.

## MCP

- O token tem formato `capi_` + 32 bytes aleatórios e é mostrado uma vez só.
- No banco fica só o SHA-256; a lista mostra o prefixo e o último uso.
- Cada pessoa pode ter até 10 tokens ativos, e revogar um vale no próximo pedido.
- O servidor MCP roda sem estado: cada pedido HTTP carrega o próprio token e o próprio usuário.
  As ferramentas leem o usuário de um `ContextVar` definido pelo middleware e falham fechadas sem
  ele.

## Limitações reais

- **Ataque distribuído:** o limite de tentativas é por IP. Um ataque espalhado por muitos IPs
  contra a mesma conta não é bloqueado por conta; não há bloqueio progressivo nem CAPTCHA.
- **Sem segundo fator:** não há 2FA. O plugin `twoFactor` do Better Auth é o próximo passo natural.
- **Tamanho mínimo da senha:** 12 caracteres, abaixo dos 15 que o NIST pede para senha como fator
  único.
- **Revogação do JWT:** o JWT dura 5 minutos. Se ele vazasse do servidor do Next, valeria até
  vencer, porque a revogação da sessão não o alcança. Ele nunca vai ao navegador.
- **Diferença de tempo:** a resposta do cadastro de e-mail existente e de e-mail novo tem o mesmo
  formato e um hash nos dois casos, mas o envio de e-mail e as gravações ainda podem gerar
  diferença de tempo mensurável.
- **Google não testado de ponta a ponta:** sem credenciais, o Google foi verificado só por
  configuração e pelo código da biblioteca.
- **RLS:** o filtro central fica no ORM; consultas em SQL puro (só a ferramenta de legado) não
  passam por ele. O Row-Level Security do Postgres seria a próxima camada, mas exige um papel de
  banco sem `BYPASSRLS`, o que depende do provedor.
- **Monitoramento:** não há alerta de login suspeito nem registro de auditoria além dos dados de
  sessão (IP e user agent).
- **Prerender das páginas de entrada:** elas leem `BETTER_AUTH_SECRET` e `DATABASE_URL` no build
  para decidir entre login e demonstração. Faça o build com as mesmas variáveis de produção.
