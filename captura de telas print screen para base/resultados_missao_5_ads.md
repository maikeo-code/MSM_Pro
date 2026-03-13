# Resultado das Missões de Captura de Dados (Mercado Livre) - Parte 3

Aqui estão os dados da **MISSÃO 5 (Product Ads / Publicidade)** que a IA poderá usar como mapeamento para a rentabilidade da campanha do vendedor.

## MISSÃO 5: Publicidade / Product Ads

**URLs Base:**
*   Listagem Campanhas: `https://www.mercadolivre.com.br/publicidade/product-ads/campanhas`
*   Detalhe de uma Campanha Ativa (Ex: "Cadeiras 5%"): Dashboard analítico da campanha.

### 1. Painel da Lista de Campanhas Ativas
A listagem centraliza o controle de verba por grupo de anúncio. Identificamos as seguintes métricas chaves solicitadas no escopo:
*   **Diagnóstico Algorrítmico:** O Status do ML sobre a entrega (Ex: "Excelente" ou "Pode melhorar - Você está perdendo 78 vendas por falta de orçamento").
*   **Orçamento Médio Diário:** Investimento programado pelo seller (Ex: R$ 100,00).
*   **ROAS Objetivo:** Indicador de retorno alvo definido no algoritmo (Ex: 20x).
*   **Vendas por Product Ads:** Unidades absolutas convertidas pelo patrocínio no período (Ex: 49 vendas ▲188%).
*   **ROAS Realizado:** O Retorno em receita dividido pelo investimento efetivo na campanha (Ex: 18,02x ▲32%).
*   **ACOS (Advertising Cost of Sales):** Percentual do custo do Ad frente a receita bruta. É a métrica mais relevante. Uma das melhores campanhas capturadas performa a **5,55% de ACOS**.

### 2. Painel Detalhado de Rentabilidade da Campanha
Ao clicar em uma campanha ativa (período: 10 fev. - 12 mar.), entramos no drill-down gráfico contendo:
*   `Vendas por Product Ads:` 49 unidades
*   `Vendas sem Product Ads (Organico associado):` 58 unidades
*   `Cliques:` 2.193 cliques
*   `Receita:` R$ 17.386 
*   `Investimento:` R$ 964,63
*   `ACOS daquele cluster:` 5,55%

**Nota sobre as métricas personalizadas (CPC):** O dashboard de "Métricas" (detalhe_ads) foca em Receita, Investimento, ACOS e Cliques. Para extrair Custo por Clique (CPC), a fórmula a mapear no software futuro deve ser: *Investimento Total / Total de Cliques.*

### 3. Arquivos de Referência (Disponíveis na VM e pasta final)
*   `missao5_campanhas.png`
*   `missao5_detalhe_ads.png`
