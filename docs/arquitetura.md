# Arquitetura

## Visão geral

```
                ┌──────────────────────────┐
  navegador ──▶ │ frontend (Next.js)       │  Cloud Run, scale-to-zero
                └────────────┬─────────────┘
                             │ REST + Bearer
                ┌────────────▼─────────────┐
 Claude Desktop │ backend (FastAPI)        │  Cloud Run, scale-to-zero
 Claude Code ──▶│  /api   REST             │
 claude.ai      │  /mcp   MCP (HTTP)       │──▶ Claude API (Haiku 5.5)
                └────────────┬─────────────┘
                             │
                ┌────────────▼─────────────┐
                │ Cloud SQL Postgres 17    │  + pgvector, db-f1-micro
                └──────────────────────────┘
```

Um único backend serve a API REST do dashboard e o servidor MCP. As ferramentas são as
mesmas funções nos dois lados: o chat do app e o Claude Desktop enxergam exatamente o
mesmo conjunto de capacidades.

## Ledger de partidas dobradas

Todo dinheiro vive em `lancamentos`, em centavos (`BIGINT`), e cada `transacao` soma zero.
Um trigger `DEFERRABLE INITIALLY DEFERRED` garante isso no commit, então nenhuma importação
consegue deixar o livro desbalanceado.

Convenção de sinal (débito positivo):

| Tipo de conta | Aumenta com | Exemplo                               |
|---------------|-------------|---------------------------------------|
| ativo         | +           | conta corrente recebe salário         |
| passivo       | −           | fatura do cartão cresce               |
| despesa       | +           | compra no mercado                     |
| receita       | −           | salário                               |
| patrimonio    | −           | saldo de abertura                     |

Uma compra de R$ 50 no débito vira dois lançamentos: `Ativo:Banco −5000` e
`Despesa:Mercado +5000`.

**Categoria é conta.** Não existe coluna "categoria": classificar uma transação é trocar a
conta da contrapartida de `Despesa:A classificar` para `Despesa:Mercado`. Relatório de
gastos é só `SUM` nos lançamentos de contas `despesa`, e o modelo não tem como divergir
do saldo.

## Ingestão

| Fonte       | Como entra                                                        | Idempotência                      |
|-------------|-------------------------------------------------------------------|-----------------------------------|
| OFX         | parser próprio (SGML v1 e XML v2, CP1252 dos bancos brasileiros)  | `(origem, id_externo)` = ACCTID:FITID |
| NFC-e       | URL do QR code → chave de acesso (44 dígitos, DV módulo 11) → itens | `chave_acesso` única              |
| PDF/CSV     | roadmap                                                           |                                   |

A NFC-e é o diferencial: com os itens da nota dá para acompanhar o preço de cada produto no
tempo e calcular a **inflação pessoal** contra o IPCA (série 433 do SGS do Banco Central).

## Onde o Claude entra

| Tarefa                         | Modelo           | Por quê                                                          |
|--------------------------------|------------------|------------------------------------------------------------------|
| Categorizar transações em lote | Haiku 5.5, effort `low` | volume alto, saída estruturada (`messages.parse` + Pydantic) |
| Normalizar itens de NFC-e      | Haiku 5.5        | "CAFE PILAO TRAD 500G" → produto canônico para comparar preço   |
| Chat e resumo do mês           | Haiku 5.5        | escolhe as ferramentas certas e gasta pouco; troque MODELO_ANALISE se quiser mais raciocínio |
| Importações grandes            | Batch API        | metade do preço, sem pressa                                      |

Hoje a categorização manda todas as pendentes para o Claude. O plano é mandar só o que
nenhuma regra resolveu e usar as correções do usuário (`categorizada_por = 'usuario'`) como
exemplos nos próximos lotes.

## RAG: o que vai para vetor e o que não vai

Pergunta agregada ("quanto gastei com delivery em outubro?") **não** é RAG: é SQL, exposta
como ferramenta. Vetor serve para o que é difuso:

- descrições de transação e itens de nota ("café" precisa achar `CAFE PILAO 500G` e
  `PAG*CAFETERIA X`);
- documentos anexados (contrato de aluguel, regulamento do cartão, informe de rendimentos).

A tabela `trechos` guarda texto, `embedding vector(1024)` com índice HNSW e um `tsvector`
gerado em português com índice GIN. A busca é híbrida: as duas listas são combinadas por
Reciprocal Rank Fusion. Embeddings vêm do Voyage AI (a Anthropic não tem modelo de
embeddings próprio).

## Segurança

- O repositório é público; dados reais não são. Cada pessoa entra com e-mail e senha ou Google
  (Better Auth no Next.js); o FastAPI só aceita um JWT Ed25519 de 5 minutos emitido para a sessão,
  e o MCP só aceita token pessoal. Todo dado financeiro tem dono, filtrado no ORM e amarrado por
  chaves estrangeiras compostas. Detalhes, decisões e limitações em [seguranca.md](seguranca.md).
- Segredos ficam no Secret Manager e chegam ao Cloud Run como variáveis de ambiente. Os containers
  rodam com uma conta de serviço própria (`capi-run`) que só lê segredos e conecta no Cloud SQL.
- O GitHub Actions publica sem chave JSON: Workload Identity Federation aceita só o OIDC da `main`
  deste repositório (pelo id numérico, não pelo nome) e entrega a conta `capi-deploy`, que só faz
  deploy no Cloud Run, envia imagem e enxerga quais segredos existem, sem ler o valor.
- A demonstração em `/demonstracao` usa dados sintéticos.

## Custos esperados (uso pessoal)

- Cloud Run: dois serviços com mínimo de 0 instâncias, dentro da camada gratuita.
- Cloud SQL: db-f1-micro com 10 GB de SSD e backup diário, na faixa de US$ 10 a 13 por mês em São
  Paulo. É o único custo fixo; o banco não dorme.
- Claude: categorizar 500 transações por mês com Haiku 5.5 fica em centavos de dólar.
