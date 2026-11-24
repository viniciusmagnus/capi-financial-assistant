# Surface: início (/)

Escopo: a primeira tela do app, que junta importação e diagnóstico do mês. Modo: Operate. Público e fatos do produto em PRODUCT.md.

Tarefa: soltar extrato e fatura de uma vez, ver o mês na hora, corrigir categorias e simular cortes. Uso típico no celular, à noite, com pouca luz. Restrições: nada de passo obrigatório antes de importar, renda editável no próprio painel, números só do backend.

Decisões em aberto: tema claro não existe nesta versão (a cena de uso decidiu pelo escuro).

## Direction contract

THESIS: o mês é um fim de tarde no Guaíba: a renda é o dia e cada gasto empurra o sol para o horizonte. Recusa o painel de banco com cartões brancos iguais e o número grande solto num retângulo.

OWN-WORLD: chão de rio escuro (verde-água profundo), céu de entardecer em violeta, rosa e laranja, sol dourado. Laranja do poente marca gastos, turquesa da correnteza marca renda e entradas, brasa para o que passou da renda. Archivo com eixo de largura: números largos e pesados, texto de interface normal. Linhas finas tingidas de verde-água no lugar de caixas.

STORY: a pessoa solta os arquivos, vê o sol cair até a altura do quanto da renda já foi, entende para onde o dinheiro foi nas barras, toca para corrigir, lê o que a Capi notou e testa um corte no simulador.

FIRST VIEWPORT: barra de topo com a marca Capi e navegação; logo abaixo, a faixa de importação (soltar ou escolher arquivos, OFX, CSV ou PDF). Em seguida a cena ocupando a largura: um arco pontilhado no céu (o antigo medidor do Cofrinho) por onde o sol anda da esquerda para a direita conforme o gasto se aproxima do teto (ou da renda cheia, sem teto), crescendo e esquentando; a cabeça da Capi saindo da água no centro do horizonte, com o balão de fala logo abaixo; na água, os gastos do mês em número largo, a linha do teto e os botões de anotar gasto e de teto; abaixo, renda, quanto da renda já foi e renda menos gastos. Ação primária: escolher arquivos; secundária: anotar gasto. Revisão do usuário em 23/11: Cofrinho dentro da cena, renda sempre cheia, últimos gastos no lugar dos avisos.

FORM: Guaíba ao entardecer, terceira da lista ordenada (escolhida pelo usuário entre quatro opções apresentadas pela ferramenta de perguntas). seed: none (unavailable) — não corroborado: o lançador da skill (binário baixado) não foi executado, então não houve rolagem; a direção foi apresentada e escolhida pela ferramenta de perguntas.

Gesto marcante: ao carregar, o sol percorre o arco até a fração do teto já gasta e fica mais forte (maior, mais laranja, mais brilho) quanto maior o gasto (uma vez, ease-out exponencial; sem animação com redução de movimento). Passou do teto, o céu queima e o sol fica em brasa no horizonte direito.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
