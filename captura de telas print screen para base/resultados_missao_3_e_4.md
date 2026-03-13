# Resultado das Missões de Captura de Dados (Mercado Livre) - Parte 2

Aqui estão os dados estruturados e detalhamentos das Missões 3 e 4 para uso pelas outras IAs no projeto MSM_Pro.

## MISSÃO 3: Anúncios Ativos e Métricas (Product Level)

**URLs Base:**
*   Listagem: `https://www.mercadolivre.com.br/anuncios/lista`
*   Desempenho: `https://www.mercadolivre.com.br/metricas/negocio/anuncios`

### 1. Painel da Lista de Anúncios Ativos
*   A lista central de anúncios agrega informações logísticas e de catálogo:
    *   **Identificadores:** Título, Imagem e identificador de catálogo (SKU interno / MLB).
    *   **Status de Fullfilment:** Tag `⚡ FULL` com as unidades em estoque consolidadas no centro de distribuição (ex: 163 unidades).
    *   **Faixa de Preços:** Mostra o detalhe do desconto. Ex: "Você vende por R$ 61,10 na promoção / R$ 106,81 clássico". Inclui tabela de preços de atacado.
    *   **Qualidade do Anúncio (Score):** Pontuação de catálogo de `0` a `100`. (Ex: `86` - "Profissional"). Classifica também a Experiência de compra (`100/100` - "Boa").
    *   **Tarifas Visíveis:** Tarifa de venda clássica de 11.5% e frete (A pagar pelo comprador: R$ 8,55).

### 2. Painel Específico de Métricas de 1 Anúncio (#4447646459 - Fechadura Eletrônica)
*   **Vendas brutas:** Total gerado (ex: R$ 14.193, crescimento de 213,6%).
*   **Visitas:** Volume de clique (1.138 visitas recentes).
*   **Conversão:** Taxa percentual da transição "Visitas -> Vendas". (4,8%).
*   **Unidades vendidas / Compradores:** Detalhamento do giro no prazo visualizado (ex: 57 unidades pra 55 compradores).

### 3. Arquivos de Referência (Disponíveis na VM e pasta final)
*   `missao3_lista.png`
*   `missao3_detalhe.png` (Tela de Métricas Detalhadas do Item)


---

## MISSÃO 4: Dashboard de Reputação e Performance

**URL Base:** `https://www.mercadolivre.com.br/reputacao`

### 1. Visão Geral (Medalhas)
*   **Ranking:** O perfil atingiu a base de `MercadoLíder Gold`.
*   **Termômetro Visual:** A cor atribuída ao vendedor na plataforma baseada nos critérios é `Verde Escuro` (Nível Superior).
*   **Range Datado:** A telemetria analisou as vendas dos "Últimos 60 dias" (2.545 vendas -> R$ 252.977 faturados).

### 2. Variáveis Penalizadoras Mapeadas (KPIs do Termômetro)
O Mercado Livre afixa a cor "Verde" baseada em não exceder a banda dos seguintes KPIs:
*   **Reclamações:** Rate atual `0%` (Teto permitido para o nível Verde: abaixo de `1%`).
*   **Mediações:** Rate atual `0%` (Teto permitido para o nível Verde: abaixo de `0,5%`).
*   **Canceladas por você:** Rate atual `0,07%` (Teto permitido para o nível Verde: abaixo de `0,5%`).
*   **Você despachou com atraso:** Rate atual `2,46%` (Teto permitido para o nível Verde: abaixo de `6%`).

### 3. Arquivos de Referência
*   `missao4_reputacao.png`
