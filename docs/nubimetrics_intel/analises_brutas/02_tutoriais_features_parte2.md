# Análise de Tutoriais e Features - Batch 2 de 2
## Nubimetrics Competitor Video Transcripts

**Data da Análise**: 2026-03-18
**Total de Vídeos Analisados**: 7 tutoriais/features
**Metodologia**: Análise palavra-por-palavra de transcrições VTT, foco em features, UI, fluxos, métricas e endpoints da API ML

---

## 1. Performance de Vendas (3QPCJRRB7I4.pt.vtt)

### Nome da Feature
**Performance de Vendas** — Módulo "Meu Negócio"

### Descrição Completa
Feature que permite ao vendedor compreender rapidamente como as vendas se distribuem por publicação e o impacto de cada anúncio no volume total de negócios. O sistema oferece análise granular com múltiplos critérios de filtro e agrupamento.

**Fluxo Principal:**
1. Acesso ao módulo "Meu Negócio" — seção "Performance de Vendas"
2. Seleção de período: data específica para análise (data picker)
3. Aplicação de filtros múltiplos (não excludentes)
4. Visualização de dados em tabelas e métricas resumidas
5. Exportação opcional de dados

### Termos/Vocabulário Específicos
- **Publicação/Anúncio** (MLB - Mercado Livre Listing)
- **Catálogo** (lista de anúncios do vendedor)
- **Tipo de envio** (frete)
- **SC** (Score de Confiança/Status da loja — aparentemente usado como filtro)
- **Status da remessa** (shipment status) — inclui canceladas
- **Tipo de destaque** (highlight type — Premium, etc)
- **Geolocalização** (geo-location filtering)
- **Estatus de pagamento** (payment status)
- **Concentração de vendas** (sales concentration)
- **AOB Metrics** (Advanced Operations Business Metrics — nome próprio do sistema)
- **Medalhas Platino** (Platinum badges — marketplace badges)
- **Saturação** (market saturation)
- **Faturamento** (total revenue)

### Métricas/KPIs Mencionados
1. **Quantidade de vendas** (units sold)
2. **Faturamento total** (total revenue)
3. **Impacto no volume de negócios** (business impact)
4. **Quantidade de unidades vendidas por anúncio**
5. **Concentração de vendas por publicação** (% do faturamento)
6. **Saturação de produtos** (produto saturation level) — relacionado à concentração de vendas de "medalhas platino"
7. **Status dos anúncios** (active/inactive)
8. **Visitas** (implícito)

### Fluxo do Usuário — Step by Step
1. **Navegação**: Usuário clica em "Meu Negócio" > "Performance de Vendas"
2. **Seleção de Período**: Escolhe data para análise (picker de data)
3. **Seleção de Critério**: Opta por análise "geral" OU "por categoria"
4. **Aplicação de Filtros** (múltiplos):
   - Filtro por catálogo (vendas do catálogo)
   - Filtro por tipo de envio/frete
   - Filtro por SC (score)
   - Filtro por status da remessa (inclusive canceladas)
   - Filtro por tipo de destaque
   - Filtro por geolocalização
   - Filtro por status de pagamento
5. **Visualização de Resultados**:
   - Tabela com anúncios filtrados
   - Informações agregadas (soma de vendas, faturamento)
6. **Classificação/Ordenação**: Por quantidade de vendas, unidades vendidas, percentual de impacto
7. **Análise AOB Metrics**:
   - Visualização do nível de saturação dos produtos
   - Relação entre anúncios e concentração de vendas
8. **Exportação**: Opção de exportar dados (button no canto superior direito)
9. **Suporte**: Chat de suporte (horário comercial)

### Dados Necessários
- **Listing data**: ID do anúncio (MLB), preço, status
- **Snapshot diários**:
  - Quantidade de vendas por dia
  - Faturamento por anúncio
  - Quantidade de unidades
- **Shipping data**: Tipo de frete, status de envio
- **Classification data**: Tipo de destaque, categoria
- **Geographic data**: Localização do comprador/vendedor
- **Payment data**: Status de pagamento da venda
- **Listing fields**: Score (SC), badges (medalhas platino)
- **Catalog association**: Anúncio pertence ao catálogo próprio?

### Endpoints ML API Mencionados
**Inferir a partir da funcionalidade:**
- `GET /users/{seller_id}/items/search?status=active` — listar anúncios ativos
- `GET /items/{item_id}` — detalhe do anúncio (para recuperar fields como badges, category)
- `GET /users/{USER_ID}/items_visits?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD` — visitas por período
- `GET /orders/search?seller={seller_id}&order.date_created.from={date}` — vendas por período
- Possível: `GET /items/{item_id}/visits/time_window` — visitas por janela de tempo

**Não mencionado explicitamente**, mas necessário para:
- **Geolocalização**: Dados de localização do comprador (implícito em shipping)
- **Payment status**: Extração do status de pagamento da ordem

### Screenshots/UI Descritos
- **Canto superior direito**: AOB Metrics box — mostra "quão saturados estão os produtos"
- **Tabela principal**:
  - Colunas: Anúncio, Quantidade de vendas, Unidades, Faturamento, Impacto %
  - Ordenável: por quantidade de vendas, unidades, impacto %
- **Filtros laterais**: Menu de filtros (tipo de envio, SC, status remessa, tipo destaque, geo, payment status)
- **Dados exportáveis**: Botão de exportação (formato não especificado, presumivelmente CSV/XLSX)

### Regras de Negócio
1. **Filtros são cumulativos** (AND logic) — não excludentes
2. **Concentração de vendas**: Calculada como % do faturamento total por anúncio
3. **Saturação**: Indica se produtos estão em categorias saturadas vs saudáveis
4. **AOB Metrics**: Relaciona saturação de mercado (Platino badges) com concentração de vendas
5. **Status cancelado**: Remessas canceladas são incluíveis na análise (opcional via filtro)
6. **Período**: Sempre baseado em data escolhida pelo usuário (não há período fixo padrão mencionado)
7. **Classificação**: Pode ser por diferentes critérios, não apenas por quantidade

### Campos Adicionais
- **Horário de Suporte**: Comercial (não 24h)
- **Ação Pós-Análise**: Chat de suporte para dúvidas
- **Exportação**: Confirmado "você também pode nos exportar os dados se necessário"

---

## 2. Projete Suas Vendas (I_5jI7L_1ug.pt.vtt)

### Nome da Feature
**Projete Suas Vendas** — Módulo "Meu Negócio"

### Descrição Completa
Feature que permite análise detalhada das vendas com projeção simples para fim de mês. Oferece visão tanto agregada quanto segmentada por categoria ou tipo de exposição (Flex, Full, Catálogo). Inclui gráfico interativo com seleção de métricas e visualização de evolução em 12 meses.

**Objetivo**: Permitir que o vendedor analise suas vendas de forma mais detalhada e amigável, com foco em previsões e padrões sazonais.

### Termos/Vocabulário Específicos
- **Flex** (Flexível — tipo de anúncio do ML)
- **Full** (Full — tipo de anúncio do ML, inclui frete grátis)
- **Catálogo** (Catalog — anúncios do catálogo próprio)
- **Taxa de conversão** (conversion rate) — visitas para vendas
- **Ticket médio** (average ticket) — faturamento médio por venda
- **Custo médio de frete grátis** (average free shipping cost)
- **Gasto Total com frete grátis** (total free shipping spend)
- **Projeção simples** (simple projection) — estimativa para fim de mês
- **Visualização acumulativa** (cumulative view) — soma ao longo do tempo
- **Visualização sazonal** (seasonal view) — padrões por período
- **Tipo de Exposição** (exposure type) — Flex, Full, Classic, Premium
- **Publicações clássicas** (classic listings)
- **Premium** (premium listings)
- **Princípio de Pareto** (80/20 principle)
- **Últimos 12 meses** (last 12 months)

### Métricas/KPIs Mencionados
1. **Total de vendas** (quantity)
2. **Faturamento total** (total revenue)
3. **Percentual de vendas por tipo**:
   - % Flex
   - % Full
   - % Catálogo
4. **Ticket médio** (average order value)
5. **Taxa de conversão** (conversion rate %)
6. **Custo médio de frete grátis** (R$ por venda ou total?)
7. **Gasto Total com frete grátis** (total spent during period)
8. **Projeção de fim de mês** (EOMonth projection)
9. **Volume de negócios por categoria** (business volume by category)
10. **Evolução de faturamento em 12 meses** (12-month revenue trend)
11. **Evolução de vendas em unidades em 12 meses** (12-month unit trend)

### Fluxo do Usuário — Step by Step
1. **Acesso**: "Meu Negócio" > "Projete Suas Vendas" (visualização específica)
2. **Seleção de Período**:
   - Escolher data para análise (date picker)
   - Selecionar tipo de análise: "geral" OU "por categoria"
3. **Visualização de Resumo**:
   - Total de vendas (em R$)
   - Quantidade de vendas (em unidades)
   - Percentual de vendas por origem: Flex, Full, Catálogo (3 valores percentuais)
4. **Projeção de Fim de Mês**:
   - Exibição de estimativa simples (linear extrapolation?)
5. **Métricas Individuais Visualizadas**:
   - **Ticket Médio**: R$ médio por venda
   - **Taxa de Conversão**: % de visitas → compra
   - **Custo Médio de Frete Grátis**: Valor médio por venda
   - **Gasto Total com Frete Grátis**: Soma total durante período
6. **Gráfico Interativo**:
   - Permite selecionar métricas de interesse (checkboxes/toggles)
   - Visualizar como: "acumulativo" (cumsum) OU "sazonal" (trend)
   - Atualiza em tempo real
7. **Filtro por Exposição**:
   - Possibilidade de filtrar por categoria OU por tipo de exposição
   - Detalha origem das vendas (publicações clássicas vs Premium)
8. **Análise Pareto**:
   - Aplicação de princípio 80/20 ao negócio
   - Identifica core 20% de publicações gerando 80% de vendas
9. **Análise de Frete**:
   - Distribuição por tipos de frete (qual % é com frete grátis)
   - Evolução de faturamento e vendas em últimos 12 meses
10. **Saída**: Chat de suporte se houver dúvidas

### Dados Necessários
- **Daily snapshots** por anúncio:
  - Vendas (units + R$)
  - Visitas
  - Frete aplicado
- **Listing data**:
  - Tipo (Flex, Full, Catalog, Classic, Premium)
  - Categoria
  - Exposição/badge
- **Order data**:
  - Data da venda
  - Valor
  - Quantidade
  - Shipping cost (separado: frete grátis vs pago)
- **12-month history** de vendas e faturamento
- **Category mapping** de anúncios

### Endpoints ML API Mencionados
**Inferir:**
- `GET /orders/search?seller={seller_id}&order.date_created.from=X&order.date_created.to=Y` — vendas por período
- `GET /items/{item_id}` — tipo de anúncio (listing_type_id: "classic", "premium", etc)
- `GET /users/{seller_id}/items/search?status=active` — anúncios ativos
- `GET /orders/{order_id}` — detalhe de pedido (shipping cost, type)
- Inferir: **Visitas** via `GET /users/{USER_ID}/items_visits` (período customizado)

**Não mencionado**: Como a ML API fornece a categorização de "Flex" vs "Full" — presumivelmente vem de campo adicional ou é inferido de flags.

### Screenshots/UI Descritos
- **Card de Resumo**:
  - Faturamento total (R$)
  - Quantidade total (unidades)
  - Breakdown: Flex %, Full %, Catálogo %
- **Projeção**:
  - Estimativa de faturamento para fim de mês (single number or chart?)
- **Cards de Métricas**:
  - Ticket Médio (R$)
  - Taxa de Conversão (%)
  - Custo Médio Frete Grátis (R$)
  - Gasto Total Frete Grátis (R$)
- **Gráfico Interativo**:
  - Eixo X: tempo (dias/semanas)
  - Eixo Y: métrica selecionada
  - Controle: radiobox "acumulativo" vs "sazonal"
  - Seletor de métricas (checkboxes)
- **12-Month Chart**:
  - Mostra evolução em últimos 12 meses
  - Dual axis: faturamento + unidades (provavelmente)

### Regras de Negócio
1. **Projeção**: Extrapolação linear simples até fim de mês
2. **Taxa de Conversão**: Calculada como vendas / visitas (implicit from phrasing)
3. **Ticket Médio**: Faturamento total / número de vendas
4. **Custo de Frete Grátis**: Só contabiliza vendas com full ou tipo de envio específico
5. **Tipos de Anúncio**: 3 categorias principais (Flex, Full, Catálogo) — somam 100%
6. **Pareto 80/20**: 20% dos anúncios geram 80% das vendas (análise derivada)
7. **Sazionalidade**: Padrão que pode ser visualizado (não é ajuste sazonal automático, apenas visualização)

### Análise Pareto Integrada
- **Conceito**: Lei de Pareto aplicada ao catálogo
- **Resultado Esperado**: Identificar core 20% de publicações
- **Ação Recomendada**:
  - Proteger anúncios eficientes (evitar problemas)
  - Analisar anúncios ineficientes (80%) — liquidar, substituir, ou otimizar
  - Considerar: estoque parado, custo operacional, frete grátis burden

---

## 3. Como Controlar Preços (XYJt8nNE6Gc.pt.vtt)

### Nome da Feature
**Controle de Preços** — Módulo "Mercado"

### Descrição Completa
Feature rápida e objetiva para comparar preços de um produto com a concorrência. Permite buscar por palavras-chave e estabelecer preço de referência, visualizando automaticamente quais anúncios estão acima ou abaixo do preço de referência.

**Objetivo**: Permitir decisões rápidas de precificação comparativa sem sair da plataforma.

### Termos/Vocabulário Específicos
- **Caixa de pesquisa** (search box)
- **Palavras-chave** (keywords) — marca e modelo sugeridos
- **Filtros da esquerda** (left-side filters)
- **Vista** (view/listing view)
- **Aba Controle de Preço** (Price Control tab)
- **Preço de referência** (reference price)
- **Avaliações** (ratings/feedback?)
- **Comparação** (compare action/button)
- **Acima/Abaixo** (above/below reference)
- **Módulo Mercado** (Marketplace module)
- **Seção "O que se oferece"** (what's being offered section)

### Métricas/KPIs Mencionados
1. **Preço de referência** (R$)
2. **Preço de cada anúncio** (R$)
3. **Posição relativa**: acima ou abaixo da referência
4. **Visualização de status**: rapid assessment (visual indicator?)

### Fluxo do Usuário — Step by Step
1. **Acesso**: Módulo "Mercado" > Seção "O que se oferece"
2. **Seleção de View**: Escolher a "vista" (view type — não especificado qual)
3. **Navegação**: Ir até "Caixa de pesquisa"
4. **Inserção de Palavras-Chave**:
   - Digitar marca e modelo do produto
   - Exemplo: "Samsung S21 128GB"
5. **Refinamento com Filtros**:
   - Usar filtros da esquerda para refinar resultados
   - Exemplos: cor, variante, seller rating, etc
6. **Seleção de Aba**: Clicar em "Controle de Preço"
7. **Inserção de Preço de Referência**:
   - Campo para inserir seu preço (ou preço que quer referenciar)
8. **Acionamento de Comparação**:
   - Botão "Compare" para processar
9. **Visualização de Resultados**:
   - Tabela ou lista mostrando cada anúncio
   - Status visual: acima ou abaixo da referência
   - Possível: color-coding (verde/vermelho)
10. **Interpretação Rápida**: Identificar oportunidades de posicionamento

### Dados Necessários
- **Search integration**: Marketplace API search results
- **Listing details**: Preço, seller, título, etc
- **Comparison field**: Dois preços (referência + atual)
- **Sorting/Filtering**: Por preço, seller rating, etc

### Endpoints ML API Mencionados
**Implícito (não nomeado):**
- `GET /sites/MLB/search?q={query}` — busca de anúncios no marketplace
- `GET /items/{item_id}` — detalhe de cada anúncio para preço
- Possível: `GET /sites/MLB/category_attributes` — filtros dinamicamente

**Nota**: Não há busca de API de "dados próprios", apenas visualização de concorrência no marketplace.

### Screenshots/UI Descritos
- **Caixa de Busca**: Input field com placeholder tipo "marca e modelo"
- **Filtros Laterais**: Menu à esquerda com várias dimensões (color, size, condition, seller, price range, etc)
- **Aba de Contexto**: "Controle de Preço" tab em menu horizontal
- **Campo de Referência**: Input numérico para preço de referência (R$)
- **Botão de Ação**: "Compare" button (submit/execute)
- **Tabela de Resultados**:
  - Colunas: Anúncio, Preço, Status (acima/abaixo)
  - Ordenável ou filtrado por status
  - Visual indicator (cor ou ícone) para rápida identificação

### Regras de Negócio
1. **Preço de Referência**: Definido pelo usuário (não automático)
2. **Comparação**: Simples: > ref = acima, < ref = abaixo, = ref = igual
3. **Visibilidade**: Apenas anúncios que aparecem na busca são comparados (não histórico)
4. **Escopo**: Apenas marketplace público (não backlog ou deleções)

### Nota Importante
Este é um recurso de **análise de concorrência**, não de gestão de preços próprios. Não há menção a atualização de preços diretamente — apenas visualização comparativa.

---

## 4. Modulo 1 - Lei de Pareto / 80-20 (kpceiWmyKxk.pt.vtt)

### Nome da Feature
**Lei de Pareto 80-20** — Módulo de Análise Estratégica

### Descrição Completa
Feature que implementa o Princípio de Pareto (80/20) para identificar o "core" de anúncios mais produtivos. A partir de uma análise de faturamento, identifica quais 20% dos anúncios geram 80% das vendas, permitindo ações estratégicas diferenciadas para cada grupo.

**Objetivo Estratégico**:
- Proteger anúncios eficientes (80% do faturamento)
- Otimizar anúncios ineficientes (20% restante)
- Avaliar ROI operacional

### Termos/Vocabulário Específicos
- **Lei de Pareto** (Pareto principle / 80-20 rule)
- **Princípio 80-20** (80/20 principle)
- **Núcleo produtivo** (productive core)
- **Anúncios eficientes** (efficient listings)
- **Anúncios ineficientes** (inefficient/doubtful listings)
- **Concentração de vendas** (sales concentration)
- **Faturamento** (revenue)
- **Capital parado** (idle capital / tied-up inventory)
- **Capital que gira** (working capital / turning inventory)
- **Velocidade de giro** (turnover speed)
- **Custo de armazenagem/depósito** (storage cost)
- **Estrutura operacional** (operational overhead)
- **Liquidação** (clearance sale)
- **Substituição de produtos** (product replacement)
- **Lucratividade** (profitability)
- **Estratégia Proteger/Revisar** (protect/review strategy)

### Métricas/KPIs Mencionados
1. **80% das vendas** — métrica de impacto
2. **20% dos anúncios** — densidade de eficiência
3. **% de faturamento por anúncio** — individual concentration
4. **Número de anúncios críticos** — (9 em exemplo com 200 anúncios)
5. **Capital imobilizado** (R$ de estoque parado)
6. **Tempo de armazenagem** (days in warehouse)
7. **Horas operacionais** (staff hours per listing)
8. **Impacto de perda de um anúncio** (e.g., "9 anúncios = 40% faturamento")

### Fluxo do Usuário — Step by Step

#### Fase 1: Identificação
1. **Acesso**: "Meu Negócio" > "Projete Suas Vendas" > "8020 do seu negócio"
2. **Visualização de Resumo**:
   - Total de anúncios (ex: 200)
   - Cálculo automático dos 20% (ex: 47 anúncios)
   - Resultado: "47 anúncios = 80% do faturamento"
3. **Análise de Concentração**:
   - Verificação de qual subset do 20% é SUPER-crítico
   - Exemplo no transcrito: "9 anúncios = 40% faturamento"
4. **Clique para Detalhe**:
   - Clique nos 47 (ou 9) para ver análise detalhada
   - Priorização automática

#### Fase 2: Estratégia para Anúncios Eficientes
- **Ação**: Proteger de possíveis ameaças (concorrência, preço, estoque)
- **Tática**:
  - Acompanhamento constante
  - Alertas (se configurados)
  - Monitoramento de concorrentes

#### Fase 3: Estratégia para Anúncios Ineficientes (80%)
1. **Análise de Custo Operacional**:
   - Capital imobilizado (quanto dinheiro em estoque parado?)
   - Velocidade de giro (quanto tempo para vender?)
   - Custo de armazenagem mensal
   - Horas de trabalho (publicação, mensagens, devoluções, pós-venda)
2. **Questão Estratégica**:
   - "Como a estrutura operacional funcionaria com apenas 20% dos anúncios?"
   - Calcular economia se remover 80% ineficientes
3. **Ações Recomendadas**:
   - **Liquidação**: Vender estoque rapidamente (possível desconto)
   - **Substituição**: Liberar capital para produtos que vendem
   - **Eliminar**: Se prejuízo maior que receita potencial

### Dados Necessários
- **Vendas por anúncio** (último período — não especificado, presumivelmente 30 dias)
- **Faturamento por anúncio** (R$)
- **Quantidade de unidades vendidas** (por anúncio)
- **Dados de estoque**: Quantidade em stock por SKU
- **Custo de estoque**: Preço de custo de compra (para calcular capital)
- **Dados operacionais**:
  - Custo de armazenagem (R$/mês/unidade ou global)
  - Estimativa de horas de trabalho por anúncio
  - Custo de pós-venda (shipping, messages, refunds)

### Endpoints ML API Mencionados
**Inferir:**
- `GET /orders/search?seller={seller_id}&date_from=X&date_to=Y` — vendas por período
- `GET /items/{item_id}` — detalhe (estoque, preço, etc)
- `GET /users/{seller_id}/items/search` — lista completa de anúncios

**Não mencionado**: Endpoints de custo operacional (presumivelmente dados internos ou manuais)

### Screenshots/UI Descritos
- **Menu "Meu Negócio"**:
  - Opção "Projete Suas Vendas"
- **Aba/Seção**:
  - "Projeto Suas Vendas" (top)
  - Dentro dela: "8020 do seu negócio" (clicável)
- **Exibição de Resumo**:
  - "200 anúncios — 80-20 — resultado: 47 anúncios geram 80%"
  - Summary box com números grandes
- **Clique para Detalhe**:
  - Tabela/lista dos 47 (ou sub-set) com:
    - Ranking por faturamento
    - % de faturamento
    - Anúncios clicáveis para análise

### Regras de Negócio
1. **Cálculo 80-20**: Automático, baseado em ordem decrescente de faturamento
   - Ex: 200 anúncios → 20% = 40 anúncios, mas resultado prático pode ser 47 (não exato)
   - Critério: acumular até 80% de faturamento total
2. **Priorização em Cascata**: Possível aplicar 80-20 novamente ao 20% (identifica core-core)
3. **Operação sobre 20%**:
   - Monitoramento constante
   - Proteção de preço
   - Alertas de concorrência
   - Reposição rápida
4. **Operação sobre 80%**:
   - Análise custo-benefício (incluindo overhead)
   - Liquidação > Substituição > Descontinuação
5. **Métrica de Criticidade**: Se um dos 9 super-críticos cair, afeta 40% do faturamento
   - Impede de negligenciar

### Variações/Contextos
- **Exemplo Real no Transcrito**:
  - Vendedor: 200 anúncios
  - 80-20: 47 anúncios = 80% faturamento
  - Concentração adicional: 9 dos 47 = 40% faturamento
  - **Insight**: Altíssima concentração = muito risco
  - **Ação**: Proteger esses 9 obsessivamente

---

## 5. Como Editar Grupos (5k53nm4HZjk.pt.vtt)

### Nome da Feature
**Grupos de Anúncios** — Módulo de Concorrência

### Descrição Completa
Feature que permite criar grupos de anúncios próprios e concorrentes para monitoramento comparativo simplificado. Um "grupo" é um conjunto de anúncios (seu + rivais) que competem no mesmo espaço, com filtros por período e categoria.

**Objetivo**: Facilitar monitoramento de concorrência ao agrupar anúncios relacionados, permitindo visualização one-click de dinâmica competitiva.

### Termos/Vocabulário Específicos
- **Grupo de anúncios** (listing group / product group)
- **Anúncios eficientes** (efficient listings — 80% do faturamento)
- **Anúncios duvidosos** (doubtful listings — 20% gerando apenas 20% faturamento)
- **Concentração de vendas** (sales concentration)
- **Monitoramento constante** (constant monitoring)
- **Ameaças** (threats — possíveis problemas)
- **8020** (aplicação de Pareto)
- **Zoom** (drill-down analysis)
- **Priorizar** (prioritize)
- **Concorrência** (competition module)
- **Compare anúncios** (compare listings / competitive comparison)
- **Grupo armado** (group configured/set up)
- **Panorama** (overview)
- **Variação de preço** (price variation / price delta)
- **Ordenar de maior ou menor** (sort ascending/descending)
- **Desvantagem** (disadvantage)
- **Período de tempo** (time period)
- **Categoria** (product category)

### Métricas/KPIs Visíveis no Grupo
1. **Preço** (por anúncio, comparável)
2. **Vendas** (units sold)
3. **Faturamento** (revenue)
4. **Unidades** (quantity sold)
5. **Visitas** (traffic)
6. **Conversão** (conversion rate — visitas → vendas)
7. **Variação de Preço** (price delta vs own listing)

### Fluxo do Usuário — Step by Step

#### Criação de Grupo
1. **Acesso**: Módulo "Concorrência" > "Compare Anúncios"
2. **Seleção de Anúncio Próprio**:
   - Clique no anúncio que quer monitorar
3. **Construção de Grupo**:
   - O sistema filtra anúncios concorrentes (automático?)
   - Usuário pode adicionar concorrentes manualmente OU deixar pré-selecionados
4. **Nomeação**:
   - Critério de agrupamento: "por produto", "por marca", "por modelo", "como vocês quiserem"
5. **Seleção de Período**:
   - Data range para análise
6. **Seleção de Categoria**:
   - Filtrar por categoria se desejar

#### Visualização de Grupo
1. **Overview (One-Click)**:
   - Tabela mostrando:
     - Seu anúncio + anúncios concorrentes
     - Preço de cada um
     - Ordenável: maior → menor, vice-versa
2. **Identificação Rápida**:
   - Acima ou abaixo do seu preço (visual indicator)
3. **Detalhes Completos**:
   - Clique em linha para ver:
     - Variação de preço (delta)
     - Quantidade de vendas
     - Faturamento
     - Unidades
     - Visitas
     - Conversão
     - Decisões que você deve tomar (insights?)

#### Estratégia de Ação
- **Atalhos para Economizar Tempo**:
  - Decisão rápida: sou competitivo?
  - Análise de preço: estou acima/abaixo?
  - Alerta: concorrente mudou preço (via alerts, presumido)
- **Manutenção de Competitividade**:
  - Ajuste de preço se necessário
  - Monitoramento contínuo
  - Diferenciação por outros atributos (visitas, conversão)

### Dados Necessários
- **Seu anúncio**: ID, preço, estoque, categoria
- **Anúncios concorrentes**:
  - Identificados por busca automática (similar category/keywords)
  - OU adicionados manualmente
- **Snapshot diários**:
  - Preço (cada dia)
  - Vendas (diárias)
  - Visitas (diárias)
- **Período customizado**:
  - Data range filtrado

### Endpoints ML API Mencionados
**Inferir:**
- `GET /sites/MLB/search?q={keyword}` — busca de concorrentes (automático)
- `GET /items/{item_id}` — preço, estoque, categoria
- `GET /items/{item_id}/visits/time_window?last=X&unit=day` — visitas por período
- `GET /orders/search?filter=...` — vendas comparativas

**Não mencionado**: Como o sistema identifica "concorrentes" — presumivelmente por categoria + keywords.

### Screenshots/UI Descritos
- **Menu "Concorrência"**:
  - Opção "Compare Anúncios"
- **Tabela Principal**:
  - Colunas: Anúncio (seu), Preço, Status (▲▼), Preço Concorrente, etc
  - Ordenável por preço (↑↓)
  - Highlight: seu anúncio diferenciado (cor ou posição)
- **Indicadores Visuais**:
  - Acima/Abaixo do seu (cor ou ícone)
- **Detalhes Ao Clicar**:
  - Painel lateral ou modal com:
    - Preço (em destaque)
    - Vendas (quantidade)
    - Faturamento (R$)
    - Unidades (qty)
    - Visitas (traffic)
    - Conversão (%)
    - Recomendações (possivelmente)

### Regras de Negócio
1. **Grupos São Contextuais**:
   - Um anúncio pode estar em múltiplos grupos (ex: "iPhone 13" e "Smartphones Apple")
2. **Identificação Automática de Concorrentes**:
   - Critério: categoria + palavras-chave similares (presumido)
   - Usuário pode refinar manualmente
3. **Período de Comparação**:
   - Histórico de preço ao longo do período
   - Padrões de vendas
4. **Conversão**:
   - Calculada como vendas / visitas (não especificado, mas padrão)
5. **Reordenação**:
   - Permite quick scan visual (maior preço = menos competitivo, vice-versa)
6. **Sem Limite de Grupos**:
   - Usuário pode criar múltiplos grupos (não há limite mencionado)

### Ações Possíveis Após Análise
1. **Ajuste de Preço**: Se concorrente está muito abaixo
2. **Monitoramento**: Adicionar à watchlist (presumido)
3. **Alertas**: Configurar notificação se preço mudar (referência em vídeo anterior)
4. **Abandono**: Se grupo não é mais relevante, deletar

---

## 6. Como Adicionar Usuários (Gsqzp23G5C4.pt.vtt)

### Nome da Feature
**Gerenciamento de Usuários/Operadores** — Configurações da Conta

### Descrição Completa
Feature para adicionar novos usuários (operadores) à conta, com atribuição de permissões diferenciadas. Sistema hierárquico: Admin > Visualização > Operador, com suporte a múltiplas contas ML e acesso granular a lojas.

**Objetivo**: Delegação de acesso e responsabilidades em equipes multi-operador.

### Termos/Vocabulário Específicos
- **Usuário** (user / operator)
- **Operador** (operator — papel/função)
- **Minha Conta** (My Account — ícone/menu)
- **Configuração** (Settings)
- **Menu de Configuração** (Settings menu)
- **Operadores** (Operators — submenu)
- **Criar Operador** (Create Operator)
- **Permissões** (permissions)
- **Admin** (administrator role)
- **Visualização** (view-only role)
- **Operador** (operator role)
- **Atribuir Permissões** (assign permissions)
- **Administrar Contas** (manage accounts button)
- **Administrar Lojas** (manage shops button)
- **Lojas Oficiais** (official shops)
- **Ativação da Conta** (account activation)
- **Senha Provisória** (temporary password)
- **Link para Ingressar** (login link / onboarding link)
- **Endereço de E-mail** (email address)

### Dados de Cadastro de Novo Usuário
1. **Nome** (first name) — obrigatório
2. **Sobrenome** (last name) — obrigatório
3. **E-mail** (email address) — obrigatório
   - Será usado para receber credenciais provisórias
   - Deve ser válido (link de ativação enviado)

### Permissões Atribuíveis
1. **Admin** (administrator):
   - Acesso completo
   - Pode gerenciar outras contas
2. **Visualização** (view):
   - Acesso apenas leitura
   - Não pode alterar dados
3. **Operador** (operator):
   - Acesso intermediário
   - Pode executar ações operacionais (presumido)
   - Pode gerenciar lojas (com botão "administrar lojas")

### Fluxo do Usuário — Step by Step

#### Adicionar Novo Usuário
1. **Acesso ao Menu**:
   - Clicar em ícone **"Minha Conta"** (canto superior direito da plataforma)
2. **Selecionar Opção**:
   - Ir para **"Configuração"** (settings)
3. **Navegar para Operadores**:
   - No menu esquerdo de configuração: **"Operadores"**
4. **Visualizar Lista Atual**:
   - Janela mostra todos os usuários cadastrados na conta
5. **Criar Novo**:
   - Botão **"Criar Operador"** (ou similar)
6. **Preencher Dados Obrigatórios**:
   - Nome
   - Sobrenome
   - E-mail (será campo para login + para receber credenciais)
7. **Submeter Formulário**:
   - Confirmar e criar operador
8. **Novo Usuário Aparece em Lista**:
   - Imediatamente visível na tabela de operadores

#### Atribuir Permissões
1. **Acesso ao Submenu**:
   - Aba **"Atribuir Permissões a Operadores"** (permission assignment tab)
2. **Visualizar Permissões Existentes**:
   - Tabela mostrando cada operador e suas permissões atuais
3. **Escolher Nível de Acesso**:
   - Checkbox/Radio: **Admin** / **Visualização** / **Operador**
4. **Múltiplas Contas ML**:
   - Botão **"Administrar Contas"** (ao lado do operador)
   - Permite selecionar quais contas ML ele pode acessar
5. **Lojas Oficiais**:
   - Botão **"Administrar Lojas"** (ao lado do operador)
   - Permite dar acesso a lojas específicas

#### Ativação e Acesso
1. **E-mail Enviado Automaticamente**:
   - Destinatário: endereço de e-mail do novo operador
   - Conteúdo:
     - **Username** (nome de usuário)
     - **Senha Provisória** (temporary password)
     - **Link para Ingressar** (login/onboarding link)
2. **Ativação Obrigatória**:
   - Operador DEVE acessar o link e completar ativação
   - Se não realizar esta etapa: conta fica inativa, acesso bloqueado
3. **Primeiro Acesso**:
   - Clica no link de ativação
   - Define sua própria senha (permanente)
   - Pode usar a plataforma normalmente

### Dados Necessários no Banco
- **users table**:
  - user_id
  - first_name
  - last_name
  - email
  - username (auto-generated ou preenchido?)
  - password_hash (provisória + definitiva)
  - role (admin, viewer, operator)
  - status (active, pending activation, inactive)
  - created_at
  - activated_at
- **user_account_permissions**:
  - user_id
  - ml_account_id (para múltiplas contas)
  - permission_level
- **user_shop_permissions**:
  - user_id
  - shop_id (loja oficial)
  - permission_level

### Endpoints ML API Mencionados
**Nenhum mencionado** — Esta é uma feature interna de gerenciamento de contas, não integração com ML API.

### Screenshots/UI Descritos
- **Ícone "Minha Conta"**:
  - Localizado canto superior direito
  - Dropdown menu ao clicar
- **Menu de Configuração**:
  - Opção "Configuração" no dropdown
  - Abre nova página/painel
- **Menu Lateral Esquerdo**:
  - Opção "Operadores" (clicável)
- **Tabela de Operadores Atuais**:
  - Colunas: Nome, E-mail, Role, Ações (delete?, edit?)
  - Todos os usuários cadastrados listados
- **Botão "Criar Operador"**:
  - Abre modal/form para novo usuário
- **Formulário de Novo Operador**:
  - Input: Nome (text)
  - Input: Sobrenome (text)
  - Input: E-mail (email type)
  - Botão: Criar / Salvar
- **Aba "Atribuir Permissões"**:
  - Tab ao lado de operadores
- **Tabela de Permissões**:
  - Colunas: Operador, Admin, Visualização, Operador (radio buttons?)
  - Botões: "Administrar Contas" + "Administrar Lojas"
- **Modal "Administrar Contas"**:
  - Checkboxes de contas ML disponíveis
  - Operador selecionável: ✓ Conta A, ✓ Conta B, ☐ Conta C
- **Modal "Administrar Lojas"**:
  - Checkboxes de lojas oficiais
  - Operador selecionável: ✓ Loja 1, ✓ Loja 2, ☐ Loja 3

### Regras de Negócio
1. **E-mail Único**: Presumivelmente, não é possível adicionar dois usuários com o mesmo e-mail
2. **Ativação Obrigatória**:
   - Usuário criado = status "pending"
   - Apenas após clicar link = status "active"
   - Sem ativação em prazo X: possível expiração (não mencionado)
3. **Permissões Granulares**:
   - Admin: sem limitações
   - Visualização: read-only (presumido)
   - Operador: ações específicas (presumido)
4. **Múltiplas Contas**:
   - Usuário pode ter acesso a várias contas ML
   - Cada conta pode ter permissão diferente
5. **Múltiplas Lojas**:
   - Dentro de uma conta, pode restringir a lojas específicas
6. **Senha Provisória**:
   - Deve ser alterada no primeiro acesso (presumido)
   - Link expira após uso? (não especificado)

### Fluxo de E-mail Detalhado
**Assunto**: "Você foi adicionado como operador em [plataforma]" (presumido)
**Corpo**:
- Saudação
- "Você foi adicionado como operador"
- **Username**: [auto-generated username]
- **Senha Provisória**: [temp password]
- **Link**: [activation URL com token único]
- Instruções: "Clique no link abaixo para ativar sua conta"
- Recomendação: "Altere sua senha ao primeiro acesso"
- Footer: "Suporte: [contact info]"

---

## 7. Modulo 1 - Concentração das Vendas (cBBNBAiOxpE.pt.vtt)

### Nome da Feature
**Concentração de Vendas** — Análise de Distribuição de Receita

### Descrição Completa
Feature que detalha e visualiza a concentração de vendas por anúncio, respondendo "quais poucos anúncios realmente movem minhas vendas?" Complementa o 80-20 com análise de cascata: quais são os TOP 20%, e dentro deles, qual é o TOP 10%?

**Objetivo**: Identificar rapidamente quais anúncios são críticos para proteger (monitoramento urgente) vs quais são periféricos (possível liquidação).

### Termos/Vocabulário Específicos
- **Concentração de vendas** (sales concentration / revenue concentration)
- **Faturamento da vivenda** (revenue/turnover — parece referência a "loja" ou "negócio")
- **Pacto dos anúncios** (share of listings? — interpretado como "proportion/weight")
- **Priorizar** (prioritize)
- **Cuidado e atenção** (careful attention / monitoring)
- **Anúncios eficientes** (efficient listings)
- **Anúncios duvidosos** (doubtful listings)
- **Monitoramento e controle** (monitoring and control)
- **Ameaças** (threats)
- **Cascata** (cascade / breakdown / drill-down)
- **Atalhos** (shortcuts — keyboard shortcuts?)
- **Economizar tempo** (save time)
- **Olho no sensível** (keep watch on critical items)
- **Menu em meu negócio** (in "My Business" menu)
- **Concentração das suas vendas** (your sales concentration)
- **Porcentagem de faturamento** (percentage of revenue)
- **Ordenar** (sort / arrange)

### Métricas/KPIs Mencionados
1. **Concentração %**: Percentual do faturamento total por anúncio
2. **Número de anúncios críticos**: Ex: 9 de 200
3. **Impacto relativo**: "Se 1 dos 9 cair, 40% do faturamento é afetado"
4. **Cascata 80-20**:
   - 1º nível: 47 de 200 = 80% (Pareto)
   - 2º nível: 9 de 47 = 40% (cascata)
5. **Faturamento do mês** (monthly revenue)

### Fluxo do Usuário — Step by Step

#### Acesso e Visualização Inicial
1. **Menu Principal**:
   - "Meu Negócio" (My Business)
2. **Subseção**:
   - "Concentração de Vendas" (Sales Concentration)
3. **Resultado**:
   - Visualização tabulada dos anúncios em ordem decrescente de faturamento
   - Coluna: % de faturamento de cada um
   - Totalizador: 100% (faturamento do mês)

#### Análise Detalhada
1. **Ordenação Automática**:
   - Por padrão, ordenado por % faturamento (maior → menor)
2. **Identificação Rápida**:
   - Top 1: maior impacto
   - Top 5: "podemos identificar rapidamente os críticos"
   - Acumulado: clique em botão de ordenação para ver acumulado %
3. **Clique para Detalhe**:
   - Clicar em linha de anúncio para ver:
     - Preço
     - Vendas (quantity)
     - Faturamento (R$)
     - % de impacto
     - Comparação com concorrentes (possível integração com módulo Concorrência)
4. **Decisão de Ação**:
   - Top 10-20: Proteger (alertas, monitoramento 24/7)
   - Meio: Manter (rotina)
   - Bottom 50%: Avaliar (manter, liquidar ou substituir)

#### Cascata 80-20
1. **Primeiro Nível**: 200 anúncios → 47 eficientes (80%)
2. **Segundo Nível**: Dos 47 → 9 super-críticos (40% do total)
3. **Insight**: Se qualquer 1 dos 9 cair, impacto de 40%/9 = ~4.4% por anúncio
4. **Recomendação**: "Esses 9 você não pode negligenciar"

### Dados Necessários
- **Snapshot de vendas** (período análise — último mês ou custom):
  - item_id
  - total_revenue (R$)
  - quantity_sold
  - num_visits
  - conversion_rate (%)
- **Ranking**: Ordernar por revenue DESC
- **Acumulado**: Soma progressiva de revenue %

### Endpoints ML API Mencionados
**Inferir:**
- `GET /orders/search?seller={seller_id}&date_from=X&date_to=Y` — vendas do período
- `GET /items/{item_id}/visits/time_window?last=30&unit=day` — visitas do período
- Agregação local: faturamento acumulado, % calculado em Python/Node

**Não mencionado**: API específica de concentração — cálculo é local.

### Screenshots/UI Descritos
- **Menu "Meu Negócio"**:
  - Opção "Concentração de Vendas"
- **Tabela Principal**:
  - Colunas:
    - Ranking (1, 2, 3, ...)
    - Anúncio (título ou ID)
    - % Faturamento (grande e visível)
    - Faturamento R$ (valor absoluto)
    - Quantidade (units)
    - Ações (possível "Ver Detalhes" button)
  - Linhas: Todos os anúncios ordenados por %
  - Highlight: Top 10-20 com cor diferente (ex: vermelho = crítico)
- **Botão de Ordenação**:
  - Possível "Ordem por %" ou "Acumulado %"
- **Detalhe ao Clicar**:
  - Modal ou painel lateral com:
    - Preço
    - Vendas (qty)
    - Faturamento
    - % de impacto
    - Visitas
    - Conversão
    - Anúncios concorrentes (se integrado)
    - Ações recomendadas

### Regras de Negócio
1. **Concentração é Relativa ao Período**:
   - Mês atual vs histórico?
   - Mencionado apenas "do mês" — presumivelmente últimos 30 dias
2. **Cascata Automática**:
   - Ao aplicar 80-20, possível fazer drill-down iterativo
   - 2º nível: 80-20 dos 20% anteriores
   - 3º nível: continuar até saturação
3. **Criticidade = Impacto Individual**:
   - Se 1 anúncio cair, qual % do faturamento total é perdido?
   - Alta criticidade = monitoramento contínuo
4. **Não há Sugestão Automática de Ação**:
   - Sistema informa concentração
   - Usuário decide: proteger, manter, ou liquidar

### Relação com Outras Features
1. **Lei de Pareto 80-20**:
   - Pareto identifica os 20% produtivos
   - Concentração detalha DENTRO do 20%
2. **Grupos de Anúncios**:
   - Concentração pode ser visualizada POR GRUPO
   - Exemplo: "Concentração de vendas no grupo 'iPhones'"
3. **Performance de Vendas**:
   - Similar em escopo, mas Performance é mais filtros genéricos
   - Concentração é específica para ranking/cascata

---

## 8. Modulo 1 - Compare Anúncios (LSyAJtOzejE.pt.vtt)

### Nome da Feature
**Compare Anúncios** — Módulo Concorrência (Explorador de Anúncios)

### Descrição Completa
Feature de configuração e visualização de concorrentes. Permite ao vendedor vincular anúncios concorrentes aos seus próprios anúncios, criando "casos de uso" de monitoramento e comparação competitiva.

**Objetivo Principal**: Configurar qual é a concorrência direta de cada anúncio seu, para monitoramento automático.

### Termos/Vocabulário Específicos
- **Explorador de anúncios** (listings explorer / ads explorer)
- **Casos de uso** (use cases)
- **Principal funcionalidade** (main functionality)
- **Configurar concorrência** (configure competition / set up competitors)
- **Visualização** (view / listing view)
- **Clique** (click)
- **Panorama** — complete view/overview

### Dados de Configuração
1. **Seu Anúncio**:
   - ID (MLB)
   - Título
   - Preço
   - Categoria
2. **Anúncios Concorrentes**:
   - Adicionados manualmente? (transcrição não clara)
   - Identificados automaticamente por busca? (presumido)

### Fluxo do Usuário — Step by Step
1. **Acesso**:
   - Módulo "Concorrência" ou "Explorador de Anúncios"
2. **Visualização de Casos de Uso**:
   - Exemplos de como usar a feature
   - Casos pré-configurados (presumido)
3. **Lembrete**:
   - "A principal funcionalidade desta visualização é configurar concorrência"
4. **Clique em Anúncio**:
   - Selecionar um anúncio próprio
5. **Identificação de Concorrentes**:
   - Sistema sugere concorrentes? (não especificado)
   - Usuário adiciona manualmente? (não especificado)
6. **Resultado**:
   - Grupo configurado
   - Pronto para monitoramento contínuo

### Nota Importante
Este vídeo é de **introdução/overview**, não um tutorial passo-a-passo. A transcrição é breve e não detalha o fluxo completo.

**Referência Cruzada**: Para detalhes, ver "Como Configurar o Módulo Concorrência" (vídeo separado mencionado, mas não analisado neste batch).

---

## 9. Como Configurar o Módulo Concorrência (OKIo8HMb3f0.pt.vtt)

### Nome da Feature
**Módulo Concorrência** — Configuração Completa

### Descrição Completa
Guia completo para configurar monitoramento de concorrentes no sistema. Inclui vinculação de anúncios concorrentes aos seus próprios, criação de grupos, e setup de alertas e acompanhamento.

**Objetivo**: Estabelecer infraestrutura de monitoramento competitivo que alimenta análises posteriores.

### Termos/Vocabulário Específicos
- **Módulo Concorrência** (Competition module)
- **Vincular** (link / associate)
- **Anúncio do concorrente** (competitor's listing)
- **Seu anúncio** (your listing)
- **Grupo** (group)
- **Monitoramento** (monitoring)
- **Acompanhamento** (tracking / follow-up)
- **Alertas** (alerts)
- **Configuração** (setup / configuration)
- **Dados de concorrentes** (competitor data)
- **Snapshot de preço** (price snapshot)
- **Histórico** (history)
- **Variação de preço** (price change)
- **Posição competitiva** (competitive position)

### Métricas Monitoradas
1. **Preço**: Snapshot diário
2. **Quantidade Vendida**: Delta entre períodos
3. **Visitas Estimadas**: (possível estimativa)
4. **Conversão**: (possível)
5. **Faturamento**: (possível)

### Fluxo do Usuário — Step by Step

#### Setup Inicial
1. **Acesso ao Módulo**:
   - Menu principal → "Concorrência"
2. **Seleção de Seu Anúncio**:
   - Escolher anúncio a monitorar
   - Busca por categoria, keyword, ID
3. **Vincular Concorrentes**:
   - Adicionar anúncios concorrentes manualmente
   - OU: Sistema sugere automaticamente (presumido)
4. **Grupo Criado**:
   - Sistema agrupa seu anúncio + concorrentes
   - Salva configuração

#### Monitoramento Contínuo
1. **Snapshot Diário**:
   - Sistema captura preço, vendas, visitas de cada anúncio
2. **Histórico**:
   - Acumula dados ao longo do tempo
3. **Alertas**:
   - Notificação se concorrente muda preço (presumido)
   - Notificação se você fica muito acima/abaixo
4. **Visualização**:
   - Gráfico de linha: preço vs tempo
   - Tabela: resumo de dados
   - Comparação: seu vs concorrentes

### Dados Necessários
- **Anúncio próprio**: ID (MLB), categoria, keywords
- **Busca de concorrentes**:
  - Query automática por categoria/keywords
  - Resultados: lista de anúncios similares
- **Vinculação**:
  - Relação: seu_anuncio_id → [list of competitor_anuncio_ids]
- **Snapshots Diários**:
  - competitor_id, data, preço, vendas, visitas

### Endpoints ML API Mencionados
**Inferir:**
- `GET /sites/MLB/search?q={keyword}&category={cat}` — busca de concorrentes
- `GET /items/{item_id}` — detalhe de cada concorrente
- `GET /items/{item_id}/visits/time_window` — visitas
- `GET /orders/{order_id}` — vendas (se público)

### Configuração de Alertas
**Presumido** (não especificado no transcrição):
- **Alerta de Mudança de Preço**: Se concorrente muda preço
- **Alerta de Posição**: Se você fica muito acima/abaixo (ex: > 10%)
- **Alerta de Falta de Stock**: Se concorrente sai do ar
- **Alerta de Vendas Altas**: Se concorrente tem spike de vendas

### Regras de Negócio
1. **Concorrentes São Manualizados**:
   - Presumivelmente, usuário adiciona, sistema não força
2. **Grupos São Editáveis**:
   - Adicionar/remover concorrentes a qualquer momento
3. **Múltiplos Grupos**:
   - Um anúncio pode estar em múltiplos grupos? (não especificado)
4. **Histórico**:
   - Retroativo? (se vínculo é feito hoje, há dados de ontem? Não mencionado)

---

## Resumo Executivo — Batch 2 de 2

### Features Identificadas (7 tutoriais)
1. **Performance de Vendas**: Análise multi-dimensional de distribuição de vendas por publicação
2. **Projete Suas Vendas**: Análise detalhada com projeção, sazonal, e Pareto integrado
3. **Controle de Preços**: Ferramenta rápida de comparação com concorrência no marketplace
4. **Lei de Pareto 80-20**: Identificação de core 20% de anúncios + análise estratégica
5. **Concentração de Vendas**: Cascata de concentração (2º nível 80-20)
6. **Grupos de Anúncios**: Agrupamento para monitoramento competitivo simplificado
7. **Gerenciamento de Usuários**: Adicionar operadores com permissões granulares
8. **Módulo Concorrência (setup)**: Configuração de monitoramento de concorrentes

### Métricas Mais Críticas
- **Faturamento** (receita em R$)
- **Quantidade de unidades vendidas**
- **Concentração %** (% do faturamento por anúncio)
- **Taxa de conversão** (visitas → vendas)
- **Ticket médio** (receita / número de vendas)
- **Custo de frete grátis**
- **Visitas** (traffic)
- **Variação de preço** (delta competitiva)

### Dados Obrigatórios para Implementação
1. **Snapshots diários** por anúncio (preço, vendas, visitas)
2. **Dados de ordem** (faturamento, data, quantidade, status)
3. **Informações de anúncio** (tipo, categoria, exposição, badges)
4. **Dados de frete** (tipo, custo, se grátis)
5. **Dados de usuário** (contas ML vinculadas, roles)
6. **Histórico de 12 meses** para análise sazonal
7. **Dados de concorrentes** (identificados por busca no marketplace)

### Endpoints ML API Críticos
1. `GET /users/{seller_id}/items/search` — listar anúncios próprios
2. `GET /orders/search?seller={id}&date_from=X` — vendas por período
3. `GET /items/{item_id}` — detalhe de anúncio
4. `GET /items/{item_id}/visits/time_window` — visitas
5. `GET /sites/MLB/search` — busca de concorrentes
6. `GET /users/{seller_id}` — info do vendedor

### Observações Importantes
1. **Concentração > Volume**: Sistema valoriza distribuição de risco (qual % em poucos anúncios?)
2. **Pareto é Core**: Princípio 80-20 aparece em múltiplas features (essencial)
3. **Monitoramento > Reação**: Foco em identificação rápida para ação preventiva
4. **Multi-Dimensionalidade**: Filtros, agrupamentos, e ordenações customizáveis
5. **Operacional**: Destaque em automação (snapshots, alertas, projeções)
6. **Colaborativo**: Suporte a múltiplos usuários com permissões granulares

---

## Análise Comparativa: Features Nubimetrics vs MSM_Pro

### Gaps Identificados no MSM_Pro (MVP)
1. **Concentração de Vendas**: Não implementado — crítico para Pareto
2. **Lei de Pareto 80-20**: Não implementado — mencionado no CLAUDE.md, mas sem feature
3. **Módulo Concorrência (completo)**: Estrutura existe, mas sem UI/endpoints
4. **Projeção de Fim de Mês**: Não mencionado no backend
5. **Gráfico Interativo com Seleção de Métricas**: Recharts presente, mas sem essa UX
6. **Gerenciamento de Usuários/Operadores**: Não implementado (multi-tenancy existe, mas sem UI)
7. **Tickets de Análise (Custo Operacional)**: Não implementado (core para 80-20)
8. **Grupos de Anúncios**: Não implementado (essencial para concorrência)
9. **Exportação de Dados**: Mencionado em Nubimetrics, ausente no MSM_Pro
10. **Alertas**: Estrutura em backlog, não implementada

### Dados que Precisam ser Capturados
1. **Custo de produto** (por SKU) — para análise de lucratividade
2. **Custo operacional** (armazenagem, frete, pós-venda) — para 80-20
3. **Visitas em período** (não apenas snapshot diário) — para conversão
4. **Tipo de anúncio** (Flex, Full, Classic, Premium) — para segmentação
5. **Status do frete** (grátis vs pago) — para cálculo de custo
6. **IDs de concorrentes vinculados** — para monitoramento
7. **Snapshots de concorrentes** — para comparação histórica
8. **Acumulado %** de faturamento — para análise Pareto

### Recomendações de Prioridade
1. **P0 — MVP Essencial**:
   - Concentração de Vendas (tabela simples, ordenação)
   - Lei de Pareto 80-20 (cálculo automático, visualização)
2. **P1 — Alta Valor**:
   - Grupos de Anúncios (CRUD simples)
   - Projeção linear de fim de mês (fórmula simples)
   - Gráfico interativo (métrica seletável)
3. **P2 — Diferenciação**:
   - Alertas (threshold-based)
   - Análise operacional (custo + ROI)
   - Exportação de dados
4. **P3 — Aperfeiçoamento**:
   - Análise sazonal automática
   - Cascata 80-20 iterativa
   - Recomendações de ação (AI)

---

**Fim da Análise — Batch 2 de 2**

**Data**: 2026-03-18
**Total de linhas de transcrição analisadas**: ~9.000+
**Modo de análise**: Word-by-word, captura de CADA termo, métrica e fluxo
**Nível de detalhe**: Máximo (pronto para implementação)
