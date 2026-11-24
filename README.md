# Capi, assistente financeiro

Copiloto financeiro pessoal que lê seus extratos e cupons fiscais **item a item**, organiza
tudo num ledger de partidas dobradas e responde perguntas sobre o seu dinheiro: no
dashboard ou direto do Claude Desktop, via MCP.

> "Quanto gastei com delivery depois que mudei de emprego?"
> "O café que eu compro subiu mais que o IPCA?"
> "Essa transação de R$ 89 em 'PAG*JOAO' é o quê? Marca como Pets."

**No ar:** https://capi-web-618639451720.southamerica-east1.run.app

Crie uma conta (e-mail ou Google) e importe um extrato, ou abra a
[demonstração](https://capi-web-618639451720.southamerica-east1.run.app/demonstracao), com
dados fictícios e sem cadastro. Cada push na `main` passa pelos testes e é publicado sozinho.

## O que tem de diferente

- **Solte os arquivos e veja o mês.** A primeira tela recebe de uma vez o extrato da conta e a
  fatura do cartão, em OFX, CSV (formato do Nubank ou genérico) ou o PDF da fatura. O app
  reconhece sozinho o banco e se é conta ou cartão, e a mesma compra vinda em CSV e PDF não conta
  duas vezes. O mês aparece como um fim de tarde no Guaíba: o sol percorre um arco no céu
  conforme os gastos se aproximam do teto do mês (ou do salário, sem teto) e fica mais forte
  quanto mais você gasta. Abaixo, os últimos gastos, para onde foi o dinheiro (por categoria e
  por estabelecimento, com logo quando a marca é reconhecida localmente), revisão de
  categorias, sugestões e simulação de cortes. Toda conta é feita em centavos no backend, e os
  gastos são sempre comparados com o salário cheio do mês.
- **Uma capivara que julga.** Na mesma cena você define o teto e anota um gasto em dois toques.
  A Capi, capivara porto-alegrense e debochada que dá nome ao app, sai da água com o humor do
  mês e comenta com uma piada gerada pelo Haiku 5.5 a partir do ledger. O código
  sorteia o detalhe zoado, a expressão gaúcha e o tipo de piada; um filtro barra fala sobre corpo,
  trabalho, com gênero ou que cite o Guaíba, rio ou enchente (assunto sensível no RS desde 2024), e aí entra o roteiro fixo, que também vale sem chave da API. A piada
  carrega à parte, então o mês aparece antes dela.
- **Ledger de verdade.** Cada transação vira lançamentos que somam zero, garantido por um
  trigger no Postgres. Categoria é uma conta de despesa, não uma coluna solta.
- **NFC-e item a item.** A chave do QR code do cupom identifica a nota (com validação do
  dígito verificador). Com os itens dá para calcular a sua **inflação pessoal** contra o IPCA.
- **Claude onde ele rende.** Suas regras ("ZAFFARI vira Mercado") categorizam primeiro, de
  graça, já na importação. Só o que nenhuma regra pega vai em lote para o Haiku 5.5 com saída
  estruturada; o chat também roda no Haiku 5.5 para gastar pouco token.
- **RAG que sabe o que não é RAG.** Total por período é SQL, exposto como ferramenta. Busca
  híbrida (pgvector + full-text em português) fica para o que é difuso: descrições de banco
  abreviadas, nomes de produto, documentos.
- **Servidor MCP no mesmo backend.** As ferramentas que o app usa são as mesmas que o Claude
  Desktop e o Claude Code enxergam.
- **Revisar Outros em um clique.** Em "Para onde foi o dinheiro", o botão "Revisar Outros" manda
  os gastos dessa categoria para o Claude.
  - **O que ele faz:** identifica o estabelecimento e sugere uma das suas categorias. Quando o
    nome não basta, pesquisa na web, e mostra as fontes junto com uma justificativa curta.
  - **O que fica em Outros:** o que não dá para identificar com segurança, como "PIX enviado"
    sem nome ou uma compra na Amazon sem o produto.
  - **A modal:** você aprova, troca a categoria (inclusive por uma nova) ou rejeita cada gasto, e
    só o aprovado muda. As escolhas podem virar regra para as próximas importações, e o aviso
    final tem "Desfazer".
- **Cada pessoa vê só o que é dela.** Cadastro com e-mail verificado ou Google, sessões
  revogáveis e dados financeiros com dono imposto no ORM e no banco. Decisões e limites em
  [docs/seguranca.md](docs/seguranca.md).

Detalhes em [docs/arquitetura.md](docs/arquitetura.md).

## Técnicas usadas

### Dados financeiros

- **Partidas dobradas com garantia no banco.** Todo valor é `BIGINT` em centavos, e cada
  transação vira lançamentos que somam zero. Um trigger `DEFERRABLE INITIALLY DEFERRED` confere a
  soma no commit, então nenhum bug de importação deixa o livro desbalanceado. Categoria é a conta de
  despesa da contrapartida: recategorizar é trocar a conta, e relatório é `SUM`.
- **Importação idempotente.** O OFX usa o par conta + FITID como chave única. CSV e PDF, que não
  têm id, ganham um id estável a partir de data, valor e descrição normalizada (sem acento,
  pontuação e espaços), com um contador para compras iguais no mesmo dia.
- **Deduplicação entre formatos.** Antes de gravar, o app procura na mesma conta lançamentos com a
  mesma data e valor e compara as descrições normalizadas. Assim a compra que veio no CSV não conta
  de novo quando chega o PDF da fatura.
- **Reconhecimento de banco e de tipo de conta.** Pelo código de compensação ou pelo nome no
  arquivo, sem a pessoa precisar dizer de onde é o extrato.
- **NFC-e validada.** A chave de 44 dígitos do QR code passa pelo dígito verificador em módulo 11
  antes de virar nota.

### IA

- **Regra antes de modelo.** As regras da pessoa ("ZAFFARI vira Mercado") categorizam na
  importação, de graça. Só o que sobra vai para o Claude.
- **Saída estruturada com enum dinâmico.** A categorização usa `messages.parse` com um modelo
  Pydantic criado na hora, em que o campo categoria é um `Literal` com as categorias daquela pessoa.
  O Haiku 5.5 não consegue responder uma categoria que não existe.
- **Few-shot recuperado do próprio histórico.** Cada transação pendente leva até três parecidas
  que a pessoa já categorizou ou corrigiu à mão, achadas por vetor com distância máxima calibrada
  (0,30). O modelo aprende o jeito dela de organizar sem fine-tuning.
- **Chat com as mesmas ferramentas do MCP.** O chat lista as ferramentas do servidor MCP e as
  executa no mesmo processo, com streaming e cache de prompt. O que funciona no app funciona no
  Claude Desktop.
- **Persona com rédea curta.** A piada da Capi é gerada pelo Haiku, mas o código sorteia o assunto,
  a expressão gaúcha e o tipo de piada, e uma expressão regular descarta fala fora do tom. Quando a
  fala é barrada, ou não há chave da API, entra um roteiro fixo.
- **Agente que sugere, humano que aplica.** Na revisão de "Outros", o Claude recebe os gastos
  agrupados por descrição parecida, o que economiza tokens. Tem três ferramentas: buscar no
  histórico, pesquisar na web e registrar sugestões. Nenhuma delas escreve no ledger.
- **Guardas que não dependem do modelo.** O servidor valida cada sugestão:
  - a categoria precisa existir e não pode ser "Outros" nem "Transferência interna";
  - fonte citada precisa ter vindo de uma pesquisa real;
  - marketplace nunca ganha categoria automática, nem pelo histórico;
  - descrição sem nome de quem recebeu ("PIX enviado") fica em Outros.

  A confirmação aplica só o aprovado, só em quem ainda está em "Outros", numa transação, com chave
  de idempotência e registro de cada alteração.
- **Pesquisa na web com dados mínimos.** A busca roda numa chamada separada ao Claude com a
  ferramenta de web search. Ela recebe só o nome do estabelecimento como está na descrição e, se a
  descrição trouxer, o bairro. O backend tira números, valores e palavras de pagamento e recusa Pix
  e transferências. Os links mostrados vêm dos blocos de resultado da ferramenta, nunca do texto
  do modelo.

### Busca

- **RAG só onde é difuso.** Totais e saldos são SQL exposto como ferramenta. Vetor serve para
  descrição abreviada de banco e nome de produto.
- **Busca híbrida.** Full-text em português (`tsvector` + GIN) e similaridade por vetor (Voyage,
  pgvector com HNSW) geram dois rankings, combinados por Reciprocal Rank Fusion (k = 60).

### Segurança

- **Autenticação por biblioteca mantida.** Better Auth no Next: senha com scrypt, verificação de
  e-mail obrigatória, recuperação com token de uso único guardado como hash, Google com PKCE e sem
  vínculo automático por e-mail, sessão em cookie `HttpOnly` revogável e limite de tentativas no
  Postgres (vale com várias instâncias).
- **API sem segredo compartilhado.** O FastAPI aceita só um JWT Ed25519 de 5 minutos emitido pelo
  Next para a sessão, validado pela chave pública (JWKS). O navegador nunca fala com a API.
- **Isolamento falha fechado.** Todo dado financeiro tem dono. Um filtro central do SQLAlchemy
  (`with_loader_criteria`) restringe toda consulta ao usuário atual, e uma consulta sem usuário dá
  erro em vez de devolver tudo. Chaves estrangeiras compostas impedem, no próprio banco, que uma
  transação aponte para a conta de outra pessoa.
- **MCP com token pessoal.** Gerado na tela Conta, mostrado uma vez, guardado como SHA-256 e
  revogável.

### Front

- **Next.js 16 com Partial Prerendering.** A moldura das páginas sai estática e o conteúdo logado
  chega por streaming. Tudo que depende de variável de ambiente ou de sessão espera a requisição
  (`connection()`), então a mesma imagem serve qualquer ambiente.
- **Server Actions e rotas do Next como único caminho até a API**, com checagem de origem contra
  CSRF e redirecionamento só para caminhos internos.

### Infra e entrega

- **Cloud Run + Cloud SQL.** Dois containers sem instância mínima e Postgres 17 com pgvector.
  Migrations rodam num job do Cloud Run antes do deploy da API.
- **Segredos fora do código e do CI.** Ficam no Secret Manager e chegam aos containers como
  variáveis. Os containers rodam com uma conta de serviço que só lê segredos e conecta no banco.
- **Deploy sem chave.** O GitHub Actions entra no GCP por Workload Identity Federation, aceito só
  para a `main` deste repositório, identificado pelo id numérico. Não existe chave JSON em lugar
  nenhum.
- **CI completo em todo PR.** ruff e pytest contra um Postgres com pgvector de verdade, inclusive
  testes de isolamento entre usuários e da migration de dados antigos; lint, tipos, testes e build
  do front.

## Stack

Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Postgres 17 + pgvector, SDK `anthropic`, SDK
oficial `mcp`, PyJWT. Next.js 16 + Tailwind, Better Auth 1.7 (sessões, e-mail e Google),
nodemailer. Deploy em Cloud Run com Cloud SQL, CI/CD no GitHub Actions.

## Rodando localmente

Pré-requisitos: Python 3.12+, Node 20+ e Docker.

```bash
cp .env.example .env                 # backend: preencha ANTHROPIC_API_KEY (opcional)
docker compose up -d --wait          # Postgres + pgvector (55432) e Mailpit (SMTP 1025, caixa em :8025)

cd backend
python -m venv .venv
.venv/Scripts/activate               # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head                 # inclui as tabelas de autenticação
uvicorn nota_a_nota.main:app --port 8100 --reload
```

Front: copie a seção "frontend" do `.env.example` para `frontend/.env.local` e gere o segredo
(`openssl rand -base64 48`) em `BETTER_AUTH_SECRET`.

```bash
cd frontend
npm install
npm run dev -- --port 3100
```

Abra http://localhost:3100, crie uma conta e confirme o e-mail pelo link que chega no Mailpit
(http://localhost:8025). Sem `BETTER_AUTH_SECRET`, `DATABASE_URL` ou `NOTA_API_URL`, o front
mostra só a demonstração em `/demonstracao`, com dados fictícios.

O navegador nunca fala com a API: as páginas, os Server Actions e as rotas do Next pedem ao
Better Auth um JWT de 5 minutos para a sessão e chamam o FastAPI com ele.

### Dados de antes da autenticação

Se o banco já tinha dados quando a migration `0006` rodou, eles ficam com um dono "legado" que não
consegue entrar. Depois de criar e verificar a sua conta:

```bash
cd backend
python -m nota_a_nota.legado --email voce@exemplo.com              # simula
python -m nota_a_nota.legado --email voce@exemplo.com --confirmar  # transfere
```

### Testes

```bash
cd backend
pytest                                                                   # unitários
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:55432/nota_a_nota_teste pytest  # + integração e isolamento

cd ../frontend
npm test && npm run lint && npx next typegen && npx tsc --noEmit && npm run build
```

## Produção

| Onde | Variável | Para quê |
|---|---|---|
| front | `BETTER_AUTH_SECRET` | Assina cookies e tokens de verificação; 32+ bytes aleatórios, só no Secret Manager. |
| front | `BETTER_AUTH_URL` | URL pública do front, em `https://` (liga `Secure` nos cookies). |
| front | `DATABASE_URL` | O mesmo Postgres da API (tabelas `user`, `session`, `account`, `verification`, `jwks`, `rateLimit`). |
| front | `SMTP_URL`, `EMAIL_REMETENTE` | Envio dos e-mails de verificação, recuperação e avisos. |
| front | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Login com Google (opcional). |
| front | `AUTH_TRUSTED_PROXIES` ou `AUTH_IP_HEADERS` | IP real atrás do balanceador, para o limite de tentativas. |
| front | `NOTA_API_URL`, `NOTA_API_URL_PUBLICA` | Endereço da API (interno) e o que aparece no comando do MCP. |
| API | `AUTH_JWKS_URL`, `AUTH_ISSUER`, `AUTH_AUDIENCE` | Onde buscar a chave pública e o que exigir no JWT. |

O front decide entre login e demonstração na hora do acesso, então a mesma imagem serve para
qualquer ambiente.

### Deploy no GCP

Dois serviços no Cloud Run (`capi-web` e `capi-api`), Cloud SQL com Postgres 17 + pgvector, segredos
no Secret Manager e imagens no Artifact Registry, tudo em `southamerica-east1`. Os scripts ficam em
`scripts/gcp/` e rodam no PowerShell (Windows) ou no `pwsh` (Linux/macOS):

| Script | Quando |
|---|---|
| `infra.ps1 [-RepositorioGitHub dono/repo]` | Uma vez: APIs, repositório de imagens, contas de serviço, Cloud SQL (gera a senha do banco e o `BETTER_AUTH_SECRET` direto no Secret Manager) e, com o repositório, o acesso do GitHub Actions por Workload Identity Federation, sem chave JSON. |
| `segredo.ps1 -Nome <segredo>` | Para gravar `anthropic-api-key`, `voyage-api-key`, `smtp-url`, `google-client-id` e `google-client-secret`. Pede o valor sem mostrar na tela. |
| `publicar.ps1 [-Remetente "Capi <...>"]` | Build, migrations (job `capi-migrar`) e deploy dos dois serviços. Segredo que não existe fica de fora. |

**CI/CD.** `.github/workflows/ci-cd.yml` roda ruff e pytest (com Postgres + pgvector), lint, tipos,
testes e build do front em todo PR e push. Em push na `main`, com tudo verde, o job `deploy` entra no
GCP por OIDC (só a `main` deste repositório pode assumir a conta `capi-deploy`) e roda o
`publicar.ps1`. Variáveis do repositório no GitHub (Settings → Secrets and variables → Actions →
Variables), impressas pelo `infra.ps1`: `GCP_PROJECT`, `GCP_PROJECT_NUMBER`, `GCP_REGION`,
`GCP_DEPLOY_SA` e `GCP_WIF_PROVIDER`. Nenhum segredo fica no GitHub.

**E-mail.** Qualquer SMTP serve (Resend, Amazon SES, Postmark, SendGrid…): use
`smtps://usuario:senha@host:465` e um remetente de domínio com SPF, DKIM e DMARC configurados.
Sem `SMTP_URL`, cadastro e recuperação falham com erro explícito, de propósito.

**Pesquisa de estabelecimentos.** A revisão de "Outros" pesquisa na web quando a API tem
`PESQUISA_WEB=anthropic` (o `publicar.ps1` liga por padrão; `-PesquisaWeb desligada` desliga). Ela
usa a ferramenta de web search da API da Anthropic com a mesma `ANTHROPIC_API_KEY`:
- **Liberação:** a busca precisa estar liberada para a organização no Console da Anthropic
  (Settings → Privacy).
- **Custo:** cada busca é cobrada à parte, além dos tokens.
- **Limites:** cada pesquisa faz no máximo 2 buscas, e cada revisão permite no máximo
  `PESQUISA_WEB_MAX_POR_ANALISE` pesquisas (6 por padrão).

Sem a variável, o Claude decide só pela descrição e pelo seu histórico, e a modal avisa que a
pesquisa na web não está configurada.

**Google OAuth.** No Google Cloud Console, crie uma credencial "OAuth client ID" do tipo
"Web application" e configure:

- Origem JavaScript autorizada: `https://seu-dominio` (e `http://localhost:3100` no
  desenvolvimento).
- URI de redirecionamento autorizado: `https://seu-dominio/api/auth/callback/google` (e
  `http://localhost:3100/api/auth/callback/google`).
- Tela de consentimento com os escopos `openid`, `email` e `profile`, e nada além.

Copie o client ID e o secret para `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`. O app não junta
uma conta Google a uma conta existente só porque o e-mail é igual; a pessoa vincula em Conta, já
logada.

## Conectando ao Claude

O servidor MCP responde em `/mcp` (Streamable HTTP) e aceita só tokens pessoais. Crie um em
**Conta → Claude (MCP)**; a tela mostra o comando pronto, uma vez só:

```bash
claude mcp add --transport http capi https://capi-api-618639451720.southamerica-east1.run.app/mcp \
  --header "Authorization: Bearer capi_…"
```

Localmente, o endereço é `http://localhost:8100/mcp`.

Cada token enxerga só os dados de quem o criou e pode ser revogado na mesma tela. Ferramentas:
`gastos_por_categoria`, `saldos`, `buscar_transacoes`, `cofrinho_do_mes`, `recategorizar` e
`criar_regra`.

## Roadmap

- [x] Ledger de partidas dobradas com trigger de balanceamento
- [x] Importação de OFX (SGML e XML, idempotente)
- [x] Validação da chave de acesso da NFC-e
- [x] Categorização em lote com Claude Haiku 5.5 e saída estruturada
- [x] Regras de categoria da pessoa aplicadas antes do Claude (tela, API e ferramenta MCP)
- [x] Revisar Outros em um clique: Claude + pesquisa na web, aprovação item a item, regras e desfazer
- [ ] Sugerir regra a partir das correções feitas à mão fora da revisão
- [x] Servidor MCP com token pessoal por usuário, guardado como hash e revogável
- [x] Cofrinho: teto do mês, gasto anotado em dois toques e a Capi comentando com Claude
- [ ] Busca de itens da NFC-e no portal da SEFAZ-RS
- [x] Embeddings (Voyage) e busca híbrida com Reciprocal Rank Fusion (API, MCP e tela de busca)
- [x] Histórico parecido (inclusive correções à mão) como exemplos na categorização
- [x] Calibrar os limites de distância do vetor com dados reais (voyage-4-lite: busca 0,56, exemplos 0,30)
- [ ] Inflação pessoal × IPCA (SGS/BCB)
- [x] Chat no app com as mesmas ferramentas do MCP (Haiku 5.5, streaming, cache de prompt)
- [x] Diagnóstico do mês: renda, importação com estados reais, gráfico por categoria e estabelecimento, revisão, sugestões da Capi e simulador
- [x] Importação de CSV e do PDF da fatura, vários arquivos de uma vez, conta e cartão reconhecidos sozinhos e deduplicação entre formatos
- [x] Categorias criadas pela pessoa (aparecem nas regras, na correção, no anotar gasto e para a IA)
- [x] Salário obrigatório como teto padrão de todo mês, com teto próprio por mês quando quiser
- [x] Primeira tela com importação, diagnóstico e teto juntos (mundo visual "Guaíba ao entardecer", PRODUCT.md e DESIGN.md na raiz)
- [ ] Ligar estorno à compra original para poder descontá-lo do gasto
- [ ] Projeção que separe gastos pontuais dos recorrentes (hoje é linear pelos dias cobertos)
- [x] Contas com e-mail verificado e Google, sessões revogáveis, limite de tentativas e isolamento dos dados por pessoa (ORM + chaves compostas)
- [ ] Segundo fator (TOTP) e alerta de login novo
- [ ] Conciliar gasto anotado à mão com o lançamento que chega depois no OFX
- [x] Deploy no Cloud Run + Cloud SQL com CI/CD pelo GitHub Actions (OIDC, sem chave)
- [ ] Eval da categorização com conjunto rotulado

## Privacidade

O repositório é público, os dados não. Nada de extrato, nota, backup ou `.env` entra no git (veja
o `.gitignore`). Toda rota fora de `/health` exige um JWT de usuário ou um token pessoal do MCP, e
cada consulta só enxerga os dados do dono. Veja [docs/seguranca.md](docs/seguranca.md).
