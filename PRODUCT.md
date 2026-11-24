# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Uma pessoa no Brasil cuidando do próprio dinheiro, sozinha. Abre o app no celular, à noite, depois que a fatura do cartão fecha ou quando o mês aperta, para entender quanto da renda já foi e com o quê. Também é o projeto de portfólio de quem o constrói, então quem avalia o código e a tela é um segundo público.

## Product Purpose

Transformar os arquivos que o banco já entrega (extrato da conta e fatura do cartão em OFX, CSV ou PDF) num diagnóstico honesto do mês: renda, gastos, quanto da renda está comprometido, para onde o dinheiro foi e o que dá para mudar. Sucesso é soltar os arquivos e entender o mês sem preencher nada à mão.

## Positioning

Os números são calculados em código, em centavos, a partir do extrato; a IA só categoriza o que as regras do usuário não cobrem e escreve as piadas da Capi, nunca os valores. Transferências, pagamento de fatura e estornos ficam fora dos gastos, a mesma compra vinda em formatos diferentes não conta duas vezes, e os gastos são sempre comparados com o salário cheio do mês (decisão do usuário: renda proporcional confundia).

## Operating Context

O usuário baixa os arquivos no app ou no internet banking (Nubank manda a fatura em CSV e PDF; a conta sai em OFX ou CSV) e solta todos de uma vez. Na mesma tela ficam o teto do mês e a anotação rápida de gastos (o antigo Cofrinho) e os últimos gastos. Depois revisa categorias tocando nas barras do gráfico, cria regras ("sempre que for X") e testa reduções no simulador. Usa também o chat com o Claude, a busca e as regras.

## Capabilities and Constraints

- Importação de OFX, CSV (Nubank e genérico) e PDF de fatura; detecção automática de conta ou cartão e do banco; reimportação idempotente.
- Categorização por regras do usuário primeiro, depois Claude Haiku 5.5; funciona sem IA (o que sobra fica "A classificar").
- Diagnóstico mensal com período parcial, projeção rotulada como projeção, até três sugestões com cálculo explicado e simulador de hipóteses.
- Teto do Cofrinho só muda com confirmação explícita.
- Modo demonstração com dados fictícios sempre identificado e sem receber arquivos.
- Nada de serviço externo de logos: marcas vêm de um pacote local.
- Ainda sem login no front: não pode ser publicado apontando para a API real.

## Brand Commitments

- Nome do produto: Capi, assistente financeiro (pode aparecer só como "Capi"). O repositório continua se chamando nota-a-nota. Mascote: a própria Capi, a capivara debochada.
- Voz: português do Brasil informal, debochada com o hábito e nunca com a pessoa; sem humilhar, sem presumir gênero, idade ou condição de vida, sem inventar fatos.
