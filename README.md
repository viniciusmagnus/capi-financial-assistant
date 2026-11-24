# Capi, assistente financeiro

Repositório `nota-a-nota`. Copiloto financeiro pessoal que lê seus extratos e cupons fiscais **item a item**, organiza
tudo num ledger de partidas dobradas e responde perguntas sobre o seu dinheiro: no
dashboard ou direto do Claude Desktop, via MCP.

> "Quanto gastei com delivery depois que mudei de emprego?"
> "O café que eu compro subiu mais que o IPCA?"
> "Essa transação de R$ 89 em 'PAG*JOAO' é o quê? Marca como Pets."

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
- **Cada pessoa vê só o que é dela.** Cadastro com e-mail verificado ou Google, sessões
  revogáveis e dados financeiros com dono imposto no ORM e no banco. Decisões e limites em
  [docs/seguranca.md](docs/seguranca.md).

Detalhes em [docs/arquitetura.md](docs/arquitetura.md).

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
npm test && npm run lint && npx tsc --noEmit && npm run build
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
claude mcp add --transport http capi http://localhost:8100/mcp \
  --header "Authorization: Bearer capi_…"
```

Cada token enxerga só os dados de quem o criou e pode ser revogado na mesma tela. Ferramentas:
`gastos_por_categoria`, `saldos`, `buscar_transacoes`, `cofrinho_do_mes`, `recategorizar` e
`criar_regra`.

## Roadmap

- [x] Ledger de partidas dobradas com trigger de balanceamento
- [x] Importação de OFX (SGML e XML, idempotente)
- [x] Validação da chave de acesso da NFC-e
- [x] Categorização em lote com Claude Haiku 5.5 e saída estruturada
- [x] Regras de categoria da pessoa aplicadas antes do Claude (tela, API e ferramenta MCP)
- [ ] Sugerir regra a partir das correções feitas à mão
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
