# Resultado das Missões de Captura de Dados (Mercado Livre)

Aqui estão os dados estruturados e detalhamentos das Missões 1 e 2 para utilização por outros agentes/IAs no projeto MSM_Pro.

## MISSÃO 1: Painel do Vendedor (Métricas Gerais)

**URL Base:** `https://www.mercadolivre.com.br/metricas#summary`

### 1. Métricas Principais Exibidas
O painel concentra o topo do funil de vendas com os seguintes indicadores:
*   **Visitas únicas:** Volume de tráfego nos anúncios.
*   **Intenção de compra:** Usuários que adicionaram itens ao carrinho ou clicaram em "Comprar Agora".
*   **Vendas brutas:** O somatório em R$ e a quantidade absoluta de vendas realizadas (ex: 1.591 vendas = R$ 182.944).
*   **Conversão:** Taxa percentual da transição de "Visitas" -> "Vendas".

### 2. Filtros de Período Suportados Integrados na Tela
Há um select nativo que cruza o período atual com o "Período anterior" com os seguintes cortes de tempo testados pela navegação:
*   Últimos 7 dias
*   Últimos 15 dias
*   Últimos 30 dias
*   Últimos 60 dias

### 3. Outros Módulos na Página
*   **Recuperação de Carrinho:** Um banner com call-to-action para geradores de cupons ("Converta em vendas X carrinhos abandonados oferecendo um cupom... entre 3 e 14 dias atrás").
*   **Concentração de Vendas por Dia e Horário:** Tabela agregadora mostrando:
    *   Dia com mais vendas (Ex: Quarta-feira).
    *   Intervalo de horário com mais vendas (Ex: Das 12:00 às 18:00).
    *   Venda média diária em R$.

### 4. Chamadas de Rede (Network) Observadas
Durante os cliques nos filtros de tempo, além de eventos de telemetria (`o11y-proxy` e `melidata`), as trocas de data-range invocam rotas da API interna do portal como `api/processes?viewId=list` que recompilam os pacotes.

### 5. Arquivos de Referência (Localizados no servidor)
*   **Tela Inicial / 7 dias:** `missao1_metricas_dashboard_1773333471751.png`
*   **Filtro 15 dias:** `missao1_15_days_1773333695379.png` / `missao1_15_days_done_1773333890238.png`
*   **Filtro 30 dias:** `missao1_30_days_final_1773333971543.png`
*   **Filtro 60 dias:** `missao1_60_days_final_v3_1773334068401.png`
*   **Dropdown Aberto:** `missao1_dropdown_open_1773333569588.png`

---

## MISSÃO 2: Detalhes de Vendas

**URL Base:** `https://www.mercadolivre.com.br/vendas/omni/lista`

### 1. Tabela Principal de Vendas
A listagem traz cada pacote unitário transacionado com os seguintes dados:
*   **Pack ID:** (Ex: #2000011997444029).
*   **Timestamp:** Data e Hora por extenso (Ex: "12 mar 13:41 hs").
*   **Impacto de Reputação:** Etiqueta explícita indicando se o cancelamento ou atraso impacta as métricas da conta.
*   **Comprador:** Nome atrelado ao usuário.
*   **SKU / Referência Interna do Produto:** Visível logo abaixo da miniatura do item.
*   **Logística:** Tag indicando a modalidade (Ex: Todos os analisados contavam com a tag **FULL** verde).

### 2. Detalhe da Venda Específica (Drill-down)
Ao isolar o pedido `#2000011997444029`, temos acesso ao break-down contábil:
*   **Status atual do fulfillment:** "Em preparação" (etapa do ciclo FULL).
*   **Item:** Identificado o modelo, variação (Cor: Branco) e SKU da base do usuário (`42185422`).
*   **Cliente:** Soraia Pezati, inclui exposição do CPF e dados fiscais atrelados (`256.xxx.xxx-xx`).
*   **Detalhamento de Custos e Taxas da Transação (Break-down financeiro):**
    *   **Produto:** `R$ 498,00`
    *   **Tarifa de Venda:** `-R$ 84,66` (Equivale a ~17% de comissão Premium para repasse ML).
    *   **Custo de Envio (Frete descontado do Seller):** `-R$ 106,95`
    *   **Preço Líquido a Receber:** `R$ 306,39`
*   **Dados Complementares do Pagamento:**
    *   ID do Pagamento: `#149326177843`
    *   Data de Aprovação: `12 de março`
    *   Regra de Liquidação: Liberação programada para **8 dias após a entrega** física.

### 3. Arquivos de Referência (Localizados no servidor)
*   **Detalhe Financeiro/Venda Aberta:** `missao2_detalhes_v2_1773334646731.png`

*(Nota aos Agentes: O subagente do navegador não gravou o arquivo `*.har` limpo de network localmente, mas a tabela acima condensa precisamente as variáveis e subchaves visuais mapeadas dinamicamente nas rotas privadas do Mercado Livre.)*
