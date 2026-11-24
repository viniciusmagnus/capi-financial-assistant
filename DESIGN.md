---
name: Capi (nota-a-nota)
description: Um fim de tarde no Guaíba: o sol anda pelo arco do céu conforme o gasto chega ao teto ou à renda do mês.
colors:
  fundo: "#0a1c1b"
  superficie: "#0f2726"
  elevada: "#15332f"
  texto: "#f3ebe1"
  suave: "#9fbab4"
  borda: "#1f4440"
  trilho: "#183834"
  poente: "#ff7a3d"
  destaque-fundo: "#3a2219"
  sobre-destaque: "#1a0f0a"
  sol: "#ffb347"
  correnteza: "#5fd4c4"
  correnteza-fundo: "#12353a"
  brasa: "#ff6b6b"
  balao: "#f3ebe1"
  balao-texto: "#0b1a1c"
  ceu-alto: "#241d47"
  ceu-meio: "#6e3a68"
  ceu-baixo: "#d9684f"
  horizonte: "#ffb36b"
  agua: "#0d2624"
  agua-clara: "#1b3a38"
  ceu-brasa-alto: "#160f2b"
  ceu-brasa-meio: "#3f1c47"
  ceu-brasa-baixo: "#8f3443"
  horizonte-brasa: "#c8553f"
  sol-claro: "#fff4cf"
  sol-meio: "#ffd27a"
typography:
  display:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "3rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 118"
  headline:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.33
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 118"
  figure:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 118"
  title:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.56
  body:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.43
  label:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.33
rounded:
  sm: "2px"
  lg: "8px"
  xl: "12px"
  2xl: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.poente}"
    textColor: "{colors.sobre-destaque}"
    rounded: "{rounded.xl}"
    padding: "10px 16px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.texto}"
    rounded: "{rounded.xl}"
    padding: "10px 16px"
  button-secondary-hover:
    backgroundColor: "{colors.elevada}"
  import-strip:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.2xl}"
    padding: "12px 20px"
  import-strip-empty:
    backgroundColor: "{colors.destaque-fundo}"
    textColor: "{colors.texto}"
    rounded: "{rounded.2xl}"
    padding: "20px"
  scene-card:
    backgroundColor: "{colors.agua}"
    textColor: "{colors.texto}"
    rounded: "{rounded.2xl}"
  speech-bubble:
    backgroundColor: "{colors.balao}"
    textColor: "{colors.balao-texto}"
    rounded: "{rounded.2xl}"
    padding: "10px 16px"
  bottom-sheet:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.2xl}"
    padding: "20px"
  list-block:
    backgroundColor: "{colors.superficie}"
    rounded: "{rounded.xl}"
    padding: "12px"
  select-field:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.xl}"
    padding: "10px 12px"
  tab-current:
    backgroundColor: "{colors.superficie}"
    textColor: "{colors.texto}"
    rounded: "{rounded.lg}"
    padding: "6px 12px"
  tab:
    textColor: "{colors.suave}"
    rounded: "{rounded.lg}"
    padding: "6px 12px"
  bar-track:
    backgroundColor: "{colors.trilho}"
    rounded: "{rounded.sm}"
    height: "10px"
  bar-fill:
    backgroundColor: "{colors.poente}"
    rounded: "{rounded.sm}"
    height: "10px"
---

# Design System: Capi (nota-a-nota)

## Overview

**Creative North Star: "Guaíba ao entardecer"**

O mês é um fim de tarde no Guaíba: um arco pontilhado cruza o céu e o sol anda por ele, do horizonte da esquerda ao da direita, conforme o gasto chega ao teto do mês (ou, sem teto, à renda mensal inteira). O chão é o rio escuro (verde-água profundo), o céu é um degradê de violeta, rosa e laranja, e o sol é dourado. O sistema é só escuro, por decisão e não por omissão: o uso é no celular, à noite, com pouca luz. Não existe tema claro nesta versão.

A cor tem função, não enfeite: laranja do poente marca gasto, turquesa da correnteza marca renda e entrada, brasa marca o que passou do limite. A hierarquia vem do eixo de largura do Archivo: números largos e pesados, texto de interface em largura normal. Em vez de caixas, linhas finas tingidas de verde-água e trocas de tom. A Capi, uma capivara de desenho animado, espia da água no centro do horizonte e fala num balão creme: é a única figura com cor própria de pelo e o único bloco claro. O sistema recusa o painel de banco com cartões brancos iguais e o número grande solto num retângulo.

**Key Characteristics:**
- Escuro único: fundo `#0a1c1b`, texto creme `#f3ebe1`.
- Cor como direção do dinheiro: poente = gasto, correnteza = renda, brasa = estourou, sol = atenção e foco.
- Archivo com eixo `wdth`: 118 nos números e títulos de seção, 100 na interface.
- Linha de 1px no lugar de caixa; cantos de 8 a 16px.
- Um único gesto de movimento: o sol subindo pelo arco ao carregar.

## Colors

Rio escuro com entardecer: neutros em verde-água profundo, um laranja quente de ação, um dourado de atenção e um turquesa que lê como entrada de dinheiro.

### Primary
- **Laranja do poente** (`#ff7a3d`, token `poente` / `destaque`): ação primária ("Escolher arquivos", "+ Anotar gasto", salvar), barras de gasto, item atual da navegação inferior, sublinhado da aba atual no topo, categoria escolhida no seletor de gasto, seleção de texto e controles nativos (`accent-color`).
- **Fundo de destaque** (`#3a2219`, `destaque-fundo`): chão da faixa de importação quando está vazia, do aviso de demonstração e da categoria escolhida, com borda em poente.
- **Tinta sobre destaque** (`#1a0f0a`, `sobre-destaque`): texto sobre poente.

### Secondary
- **Sol dourado** (`#ffb347`, `sol`): anel de foco (2px, offset 2px), cursor de texto, "(revisar)" e avisos leves, spinner de carregamento, traço percorrido do arco e brilho do sol.
- **Sol claro** (`#fff4cf`, `sol-claro`) e **Sol meio** (`#ffd27a`, `sol-meio`): centro e borda inicial do disco do sol; conforme o gasto sobe, a borda do disco passa de `sol-meio` para `poente`.

### Tertiary
- **Turquesa da correnteza** (`#5fd4c4`, `correnteza`; `entrada` e humor "tranquila" apontam para ele): renda, entradas, economia possível, ícone de sucesso, base do logo.
- **Fundo da correnteza** (`#12353a`, `correnteza-fundo`): chão de áreas de entrada.

### Error
- **Brasa** (`#ff6b6b`): o que passou do limite, erros, ícone de alerta; no sol, é o destino do degradê quando passou. É também o humor "estourou" da Capi.

### Neutral
- **Fundo do rio** (`#0a1c1b`, `fundo`): chão da página e barra de topo. O `theme-color` do documento segue em `#0b1a1c`, um tom acima.
- **Superfície** (`#0f2726`): faixas, blocos de lista, campos, aba atual, folhas de diálogo.
- **Elevada** (`#15332f`): hover de botões secundários e de itens, segmento ativo de controles agrupados.
- **Linha de água** (`#1f4440`, `borda`): linhas e contornos de 1px, divisores de lista, barra de rolagem.
- **Trilho** (`#183834`): fundo das barras de progresso.
- **Texto creme** (`#f3ebe1`, `texto`) e **Texto suave** (`#9fbab4`, `suave`): texto principal e secundário; o suave é a cor de rótulo, apoio e item inativo.
- **Balão** (`#f3ebe1` com texto `#0b1a1c`): único bloco claro, o balão de fala da Capi.
- **Céu** (`ceu-alto #241d47`, `ceu-meio #6e3a68`, `ceu-baixo #d9684f`, `horizonte #ffb36b`), **Céu em brasa** (`ceu-brasa-alto #160f2b`, `ceu-brasa-meio #3f1c47`, `ceu-brasa-baixo #8f3443`, `horizonte-brasa #c8553f`) e **Água** (`agua #0d2624`, `agua-clara #1b3a38`): vivem só na cena do mês. O céu é degradê de cima para baixo (0, 45%, 82%, 100%); a água desce de `agua-clara` a `agua`.

### Named Rules
**The Cor É Direção do Dinheiro Rule.** Poente é gasto, correnteza é renda e entrada, brasa é o que passou do limite, sol é atenção. Nenhuma dessas cores entra como decoração.

**The Sol Só no Céu Rule.** O céu em degradê, o arco e o disco do sol existem apenas na cena do mês. Nas demais telas o chão é `fundo` e `superficie`; texto sobre o céu fica em `texto`, nunca em poente ou sol.

## Typography

**Display Font:** Archivo (variável, eixo `wdth`, fallback `ui-sans-serif, system-ui, sans-serif`)
**Body Font:** Archivo, o mesmo arquivo, em largura normal
**Label/Mono Font:** nenhuma; `tabular-nums` ligado no `body` para os números alinharem

**Character:** uma só família que muda de corpo, não de rosto. O eixo de largura separa o que é dinheiro (largo, 118, apertado -0.02em) do que é interface (normal, 100). A classe `.largo` aplica `wdth 118` e `letter-spacing: -0.02em`; `.estreito` aplica `wdth 88`.

### Hierarchy
- **Display** (700, 36px / 48px a partir de `sm`, largo): gastos do mês, na faixa de água da cena. Um por tela.
- **Headline** (700, 24px, largo): título de seção (Últimos gastos, gráfico de gastos, Capi, simulador, "De onde vieram os números"); 20px na chamada da faixa de importação vazia e 18px no título das folhas de diálogo.
- **Figure** (600, 16px / 20px a partir de `sm`, largo): valores em reais nos três números sob a cena, nas linhas de categoria, nos últimos gastos e nas sugestões; em 700 quando é economia (30px no resultado do simulador).
- **Title** (600, 18px, largura normal): título de cada sugestão da Capi. A marca no topo é "Capi" em 700, 20px, largo, seguida de "assistente financeiro" em 14px `suave`.
- **Body** (400, 14px; 16px na base): texto de interface. Parágrafos de leitura limitados a `max-w-[65ch]`.
- **Label** (400, 12px, cor `suave`): rótulo de métrica, legenda, detalhe. Aba inferior em 11px.

### Named Rules
**The Largo Só nos Números Rule.** Largura 118 é para valores em reais e títulos de seção. Texto corrido, botões e rótulos ficam em largura normal.

## Layout

Coluna única, centrada. A tela do mês usa `max-w-3xl` (48rem) com gutter de 16px no celular (`px-4`) e 0 a partir de `sm` (640px), com a cena a sangrar de borda a borda no celular; a barra de topo usa `max-w-5xl`. O celular é o caso primário: a navegação vira uma barra fixa embaixo com quatro destinos (Mês, Chat, Busca, Regras; `pb-16` no body abre espaço), respeitando a área segura do aparelho. Em `sm` a navegação sobe para a barra de topo (altura 56px) e a cena ganha cantos de 16px.

Ordem da tela do mês: faixa de importação, abas de mês, cena, depois, com 56px entre seções, "Últimos gastos", gráfico de gastos, sugestões da Capi, simulador e "De onde vieram os números" (contas, fora dos gastos e observações recolhidas num `details`).

O ritmo vertical é por linha, não por caixa: listas usam `divide-y` em `borda`, blocos se separam por 12 a 20px de padding e trocas de tom. A cena tem duas faixas: o céu, de altura fixa (224px, 256px em `sm`), com o arco pontilhado ocupando 76% da largura (a partir de 12%), e a água embaixo, com altura do conteúdo. Sob a água, os números "Renda mensal", "Da renda já foi" e "Renda − gastos" ficam em grade de três colunas. As abas de mês rolam na horizontal; a ativa é centralizada ao carregar e, quando transborda, as bordas esmaecem por máscara.

## Elevation & Depth

Plano por padrão. A profundidade vem da troca de tom (`fundo` → `superficie` → `elevada`) e da linha de 1px em `borda`, nunca de sombra de cartão. A barra de navegação inferior usa `fundo` a 95% com desfoque de fundo; os diálogos usam véu preto a 60%. Dentro da cena, a água é um degradê de `agua-clara` a `agua` com uma linha de horizonte em `horizonte` a 60% (`horizonte-brasa` quando passou do limite).

### Shadow Vocabulary
- **Brilho do sol** (`box-shadow` calculado em tela: `0 4px (18 a 68)px (4 a 20)px`, em `sol` a 20-65%, ou em `brasa` quando passou): único halo do sistema, no disco do sol, crescendo com o gasto. Um segundo halo, radial e sem sombra, ilumina o céu em torno do sol.

### Named Rules
**The Linha no Lugar de Caixa Rule.** Separar com 1px de `borda` ou com troca de tom. Sombra só no sol.

## Shapes

Cantos suaves em quatro degraus: 2px para barras e trilhos de dados, 8px (`rounded-lg`) para abas e campos pequenos, 12px (`rounded-xl`) para botões, campos e blocos de lista, 16px (`rounded-2xl`) para a faixa de importação, a cena, o balão e as folhas de diálogo. Círculo completo para o sol. O arco do céu é a forma de assinatura: semielipse pontilhada (`stroke-dasharray` 1 2.5) em `texto` a 22%, com o trecho percorrido em traço contínuo de 2px, pontas redondas. Contornos são sempre de 1px em `borda`; o laranja só contorna a faixa de importação vazia e a categoria escolhida. Ícones são SVG do `lucide-react` a 16px (inline) ou 20px (navegação), nunca glifos de texto.

## Components

### Buttons
- **Shape:** cantos de 12px; padding 10px 16px (12px 16px nos botões da cena); peso 600 no primário.
- **Primary:** fundo `poente`, texto `sobre-destaque`. É a única ação cheia da tela; "Escolher arquivos", "+ Anotar gasto" e "Salvar" usam esse padrão.
- **Secondary:** transparente, contorno de 1px em `borda`, texto `texto`, peso 500; hover vai a `elevada`. "Teto" (ou "Definir teto") é o secundário da cena.
- **Focus / Disabled:** anel de 2px em `sol` com offset 2px (global); desabilitado a 50% de opacidade, sem pointer events.
- **Ícone:** quadrado pequeno de 8px (`p-1`), cor `suave`, hover para `elevada` e `texto`.

### Faixa de importação
Superfície arredondada a 16px com contorno de 1px. Vazia (estado de destaque), ganha `destaque-fundo`, borda em poente a 60% e chamada em headline largo de 20px; com dados, recua para `superficie` e `borda`, com o botão secundário. Depois de importar, o resultado recolhe numa linha de resumo (transações novas, repetidas, recusadas) com o botão "ver os arquivos importados" que abre a lista, divisores de `borda` e ícones de estado (turquesa, brasa, sol girando), e um botão de fechar.

### Cena do mês: céu, arco e sol (componente de assinatura)
Seção cheia de largura sobre `agua`, em duas faixas. No céu, em degradê (`ceu-alto` a `horizonte`): título do período em 12px a 85%, o arco pontilhado de horizonte a horizonte e o sol. O sol anda pelo arco da esquerda para a direita conforme o gasto se aproxima do limite (o teto, se definido; senão a renda mensal inteira), parando em 97% do arco; o disco cresce de 36px até 76px (88px quando passou) e muda de dourado pálido (`sol-meio`) para laranja de poente (`poente`), com brilho que também cresce. Ao carregar, uma animação em JavaScript (1.8s, ease-out exponencial) leva o sol do horizonte até a posição final; com `prefers-reduced-motion` ele já nasce no lugar. Passou do limite: o céu muda para a variante em brasa, o traço percorrido e o brilho vão a `brasa`, o disco vai de `poente` a `brasa`, a linha do horizonte vira `horizonte-brasa` e o sol fica junto ao horizonte da direita. Sem renda nem teto, não há sol. Sem dados, o sol não aparece.

A Capi (`Capivara.tsx`, cabeça de desenho animado com humor: tranquila, de olho, apertada, estourou) espia da água no centro do horizonte (80px, 96px em `sm`). Abaixo da linha do horizonte, na faixa de água, o balão de fala creme com a frase da Capi, e então o título "Gastos de {mês}" em 14px `suave`, o valor do mês em display largo, a linha do teto ("Pode gastar R$ X do teto de R$ Y", ou "Sem teto: o sol se põe quando os gastos chegam à renda de R$ Y") e os botões "+ Anotar gasto" e "Teto". Sob a água, a grade de três números: renda mensal em `correnteza`, "da renda já foi" em porcentagem e "renda − gastos" ("não é o saldo da conta"), ambos em `brasa` quando estouram. Todas as comparações com a renda usam a renda mensal inteira.

### Folha de diálogo
"+ Anotar gasto" e "Teto" abrem em `<dialog>` nativo (o simulador tem um centrado, para aplicar o teto sugerido): no celular colado à borda de baixo com cantos de cima de 16px, a partir de `sm` centrado com 16px em todos os cantos; fundo `superficie`, contorno de 1px em `borda`, véu preto a 60%, 20px de padding, título largo de 18px e botão de fechar de ícone. Dentro, campo de reais, categorias em botões de 8px (a escolhida vai a `destaque-fundo` com borda e texto em poente) e botão primário de largura cheia.

### Últimos gastos
Lista sem caixa, com `divide-y` e linhas de topo e base em `borda`: descrição em peso 500 (truncada), data e categoria em `suave`, valor em figure largo à direita. Título em headline largo de 24px; vazia, uma linha em `suave`.

### Linha de categoria
Linha sem caixa: nome em peso 500, valor em figure largo, barra de 10px com cantos de 2px sobre `trilho`, em `poente` (ou `sol` quando é "sem categoria"). Hover e estado aberto vão a `superficie`. Abaixo, bloco expandido com transações em `superficie`, cantos de 12px, e seletor de categoria.

### Controles agrupados e abas de mês
Grupo de segmentos com contorno 1px em `borda` e cantos de 12px; segmento ativo em `elevada`, peso 600. Abas de mês em linha com rolagem horizontal sem barra: item inativo em `suave`; ativo em `superficie`, `texto`, peso 600, cantos de 8px; a ativa é centralizada e, quando as abas transbordam, as pontas esmaecem.

### Inputs / Fields
Contorno 1px `borda`, fundo `superficie` (ou `fundo` dentro de blocos e folhas), texto `texto`, cantos de 12px (8px nos pequenos), 14px. Foco herda o anel global dourado (os campos das folhas trocam também a borda para `poente`). Slider e checkbox usam `poente` como `accent-color`.

### Simulador
Título largo de 24px, campos e linhas de corte em `superficie` com cantos de 12px. O resultado fica numa linha compacta: economia em turquesa largo 700 (30px) e, ao lado, o antes e depois da fatia da renda e de "renda − gastos". Sem cortes, o estado vazio é uma frase que convida a escolher o que reduzir ou usar as sugestões da Capi.

### Navigation
Topo (a partir de `sm`): fundo `fundo`, linha inferior em `borda`, marca de 32px (`public/capi.svg`, também o favicon: ladrilho de cantos 14/64 com o céu da cena, sol dourado no horizonte à direita e a cabeça da Capi de olhos fechados saindo da água) seguida de "Capi" e "assistente financeiro"; quatro itens em `suave`, hover `superficie`, atual em `texto` com sublinhado de 2px em `poente` (offset 8px). Celular: barra fixa inferior com quatro colunas, `fundo` a 95% com desfoque, linha superior em `borda`, ícone de 20px e rótulo de 11px; atual em `poente`.

### Sugestão da Capi
Lista numerada com `divide-y` e linhas de topo e base em `borda`, 20px de respiro por item. Título em 18px/600; economia em turquesa largo 700 e unidade em `suave`; fato e consequência em 14px, o segundo em `suave`. A Capi aparece ao lado do título (64px) com humor derivado do diagnóstico (tranquila, de olho, apertada, estourou, sem dados), em cores próprias de pelo (`#a9774e`) e traço (`#2b1d14`).

## Do's and Don'ts

### Do:
- **Do** usar poente para gasto, correnteza para renda e entrada, brasa só para o que passou do limite, sol para atenção e foco.
- **Do** usar `.largo` (`wdth` 118, `-0.02em`) em valores em reais e títulos de seção, e manter `tabular-nums` no corpo.
- **Do** separar com 1px de `borda` e com troca de tom (`fundo`, `superficie`, `elevada`) antes de pensar em caixa.
- **Do** manter o anel de foco de 2px em `sol` com offset 2px em todo elemento interativo.
- **Do** animar o sol uma vez ao carregar e pulá-la com `prefers-reduced-motion`.
- **Do** comparar com a renda mensal inteira; não existe renda proporcional.
- **Do** pensar em celular à noite primeiro: alvo de toque com padding de 10px, navegação inferior, cena de largura inteira, folhas coladas embaixo.

### Don't:
- **Don't** voltar ao painel de banco: cartões brancos iguais e número grande solto num retângulo.
- **Don't** criar tema claro nesta versão; o escuro é decisão da cena de uso.
- **Don't** usar poente como cor decorativa nem para renda; renda é correnteza.
- **Don't** pôr sombra em cartões; o halo do sol é a única sombra.
- **Don't** usar logos de serviço externo; ícones vêm de SVG local (`lucide-react`).
- **Don't** pôr texto em poente ou sol sobre o céu claro da cena; sobre o céu o texto é `texto`.
