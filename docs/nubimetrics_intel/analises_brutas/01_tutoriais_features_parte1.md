# Análise Detalhada de Features Nubimetrics - Parte 1 (Batch 1/2)

Análise completa word-by-word dos vídeos de tutoriais e features do Nubimetrics - plataforma concorrente de inteligência para Mercado Livre. Este documento contém inteligência competitiva sobre features, workflows, métricas e terminologias.

**Período de Análise**: 10 vídeos principais (duração total: ~1 hora)
**Data de Análise**: 2026-03-18
**Nível de Detalhe**: Máximo (cada palavra importa)

---

## 1. COMO CONFIGURAR O MÓDULO CONCORRÊNCIA (Como_configurar_o_modulo_Concorrencia__OKIo8HMb3f0.pt.vtt)

### Nome da Feature
**Módulo Concorrência** (ou "Concorrência" conforme nomenclatura interna)

### Descrição Completa
O módulo Concorrência é a funcionalidade principal do Explorador de Anúncios. Ele permite:
1. **Configuração de concorrentes**: usuario pode vincular manualmente MLBs (anúncios) de concorrentes para monitoramento
2. **Identificação automática**: o sistema busca automaticamente anúncios similares em termos de competição
3. **Histórico de snapshots**: coleta diária de dados dos concorrentes vinculados
4. **Visualização comparativa**: mostra lado a lado dados do usuário vs concorrentes

Funcionalidade central do Explorador de Anúncios.

### Termos/Vocabulário Específicos
- **MLB** = anúncio do Mercado Livre (item listing)
- **Concorrentes** = MLBs externos vinculados manualmente para acompanhamento
- **Snapshot diário** = foto/coleta de dados em um ponto no tempo (preço, vendas, visitas, estoque)
- **Explorador de Anúncios** = módulo principal onde se configura concorrência
- **Vinculação** = ação de linkar um MLB externo ao monitoramento
- **Demanda** = volume de buscas/interesse de compradores
- **Posição orgânica** = ranking natural no search do ML sem anúncios pagos
- **Configuração** = setup inicial de quais MLBs monitorar

### Métricas e KPIs Mencionados
1. **Preço** (em tempo real e histórico)
2. **Vendas por dia** (ou período)
3. **Visitas** (estimadas ou reais)
4. **Estoque** (quantidade disponível)
5. **Perguntas** (volume de perguntas dos compradores)
6. **Conversão** (% de visitas que resultam em venda)
7. **Posição no ranking** (posição relativa vs concorrentes)
8. **Faturamento** (receita total)
9. **Vendas diárias** (vendas por 24h)
10. **Taxa de conversão** (venda ÷ visita)

### Fluxo do Usuário - Passo a Passo
1. Acessar menu "Explorador de Anúncios"
2. Selecionar ou buscar um MLB próprio para análise
3. Identificar concorrentes (manualmente procurando ou usando sugestões do sistema)
4. **Vinculação manual**: entrar o ID do MLB ou link do concorrente
5. Sistema começa coleta automática de snapshots diários
6. Visualizar gráfico comparativo de preço x vendas x conversão ao longo do tempo
7. Receber alertas quando concorrente muda preço

### Dados Necessários
- **MLBs internos**: lista de todos os anúncios ativos do usuário (obtidos via API /users/{id}/items)
- **MLBs externos**: IDs dos anúncios dos concorrentes para vinculação
- **Histórico de snapshots**: API /items/{id} (preço, stock), /items/{id}/visits (visitas), /orders (vendas)
- **Atributos de items**: detalhes completos do anúncio (preço, descrição, categoria, marca)
- **Dados de marketplace**: tendências, ranking de categorias

### Endpoints Mercado Livre API Mencionados
1. **GET /users/{seller_id}/items/search** - lista anúncios ativos do vendedor
   - Status: active, paused, suspended

2. **GET /items/{item_id}** - detalhe completo do anúncio
   - Retorna: price, original_price, stock, sold_quantity, attributes, category, title

3. **GET /users/{USER_ID}/items_visits?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD** - visitas agregadas de todos items (1 chamada para todos)
   - Extremamente eficiente: traz estatísticas consolidadas por período

4. **GET /items/{ITEM_ID}/visits/time_window?last=1&unit=day** - visitas de um item específico por janela de tempo
   - Unidades: hour, day, week, month

5. **GET /orders/search?seller={seller_id}&order.date_created.from={ISO_DATE}** - pedidos/vendas do dia
   - Retorna quantidade de unidades vendidas por item

### Screenshots/UI Elementos Mencionados
1. **Painel principal de Explorador**:
   - Barra lateral com filtros
   - Lista de anúncios (próprios + vinculados como concorrentes)
   - Coluna "Preço" com valores atualizados
   - Coluna "Vendas" (unidades e data)
   - Coluna "Visitas"
   - Coluna "Taxa de Conversão"

2. **Gráfico de Comparação**:
   - Linha do tempo (eixo X: datas)
   - Eixo Y duplo: preço (esquerda), conversão % (direita)
   - Cores diferenciadas: próprio vs concorrente(s)
   - Anotações de eventos (mudanças de preço do concorrente)

3. **Formulário de Vinculação de Concorrente**:
   - Campo de entrada: "MLB ou link do concorrente"
   - Botão "Vincular"
   - Validação automática do ID

### Regras de Negócio
1. **Limite de concorrentes por anúncio**: não especificado, mas UI sugere múltiplos
2. **Frequência de coleta**: diária (provavelmente às 6h BRT, coincidindo com o Celery job)
3. **Histórico mantido**: pelo menos últimos 30-90 dias (mencionado em contextos de análise de período)
4. **Preço com desconto**: sempre usar o `price` (já inclui desconto), nunca `original_price` para tracking diário
5. **Bloqueio de IPs**: não mencionado, mas implies que scraping do HTML não é usado (usa API oficial)
6. **Alertas**: disparados quando delta de preço > threshold (não especificado quanto, mas inferir ~3-5%)

---

## 2. ALINHAMENTO À DEMANDA - APP MOBILE (Alinhamento_a_demanda_-_App_Mobile__IgarAjV88Gk.pt.vtt)

### Nome da Feature
**Alinhamento à Demanda** (ou "Alinhamento AD" internamente; "Demand Alignment")

### Descrição Completa
Feature exclusiva do app mobile que mostra:
1. **Score de alinhamento**: métrica de 0-10 indicando quanto o anúncio está alinhado com o que as pessoas buscam
2. **Análise de palavras-chave**:
   - Palavras presentes no anúncio vs demanda (em uma escala 0-10)
   - Palavras sugeridas que DEVERIAM estar no anúncio (com %demand)
3. **Dashboard mobile**: visualização simplificada para celular com gráfico de alinhamento

**Propósito**: melhorar visibilidade de anúncios que estão "sem vendas" alinhando-os melhor com o que os compradores realmente buscam.

### Termos/Vocabulário Específicos
- **Alinhamento à demanda (AD)** = grau de match entre palavras do anúncio e buscas dos compradores
- **Demanda insatisfeita** = pessoas buscando por certos termos, mas poucos anúncios disponíveis
- **Palavras-chave** = termos de busca usados por compradores
- **Top 10 de buscas** = ranking das 10 palavras mais procuradas na categoria
- **Escala de demanda** = 0-10 (10 = muito buscado, 0 = pouco/não buscado)
- **Alinhamento geral** = score médio do anúncio na conta
- **Posição orgânica** = ranking no search do ML (não pago)
- **Visitas** = visualizações do anúncio
- **Conversão** = vendas ÷ visitas (%)
- **Tal (palavra)** = termos específicos mencionados (ex: "brinco", "trio", "argola", "ouro", "prata")
- **Escala 0-10** = sistema de pontuação/ranking interno
- **Peso** = importância relativa da palavra para a demanda da categoria

### Métricas/KPIs
1. **Score de alinhamento** (0-10)
2. **Demanda por palavra** (0-10 scale, em %)
3. **Palavras em publicação** (lista com scores)
4. **Palavras sugeridas** (lista com % de demanda)
5. **Visitas** (contagem)
6. **Vendas** (contagem de unidades)
7. **Taxa de conversão** (%)
8. **Posicionamento** (ranking no search)

### Fluxo do Usuário
1. Abrir app mobile do Nubimetrics
2. Acessar aba "Alinhamento à Demanda"
3. Ver score geral de alinhamento de todos anúncios (em gráfico/lista)
4. Clicar em um anúncio específico
5. Tela detalhada mostra:
   - **Alinhamento geral**: score 0-10 (ex: 7/10)
   - **Período selecionado**: 30-60 dias (pode mudar)
6. Seção "Palavras em Publicação":
   - Lista cada palavra presente no título/descrição
   - Score 0-10 para cada
   - Exemplo: "brinco" = 10 (top demanda), "argola" = 8, "ouro" = 7
7. Seção "Palavras Sugeridas":
   - Palavras NÃO no anúncio mas sendo buscadas
   - Score % (ex: "prata" = 88%, "infantil" = 23%)
   - Com explicação: "palavra muito buscada, mas você ainda não tem no seu anúncio"
8. **Segundo exemplo de anúncio**:
   - Mostra dinâmica diferente (ex: "moto", "mini", "elétrica")
   - Mesma estrutura de palavras em publicação vs sugeridas
9. Pode aplicar filtros (maior/menor alinhamento, sem vendas)
10. Sistema diz: "clique aqui para ver os anúncios sem venda"

### Dados Necessários
- **Título e descrição do anúncio** (text parsing)
- **Ranking de buscas por categoria** (API ou scraping do ML search trends)
- **Frequência de busca por palavra-chave** (dados internos do ML ou Nubimetrics próprio)
- **Histórico de buscas** (últimos 30-60 dias, agregado por categoria)
- **Estoque de cada anúncio** (API /items/{id})
- **Vendas por período** (API /orders)

### Endpoints Mercado Livre API
1. **GET /sites/{SITE_ID}/search_trends** (se existir) - tendências de busca por categoria
   - Não confirmado na transcrição, pode ser proprietary do Nubimetrics

2. **GET /categories/{CATEGORY_ID}** - metadados da categoria
   - Retorna: nome, atributos obrigatórios, dicas de otimização

3. **GET /items/{ITEM_ID}** - dados do anúncio incluindo título, descrição, atributos

4. **Parsing de title + description** - análise textual de palavras-chave presentes

### Screenshots/UI
1. **Tela principal (mobile)**:
   - Título: "Alinhamento à Demanda"
   - Gráfico mostrando score geral (ex: 7/10)
   - Lista de todos anúncios abaixo:
     - Anúncio 1: "Alinhamento: 9/10" (high)
     - Anúncio 2: "Alinhamento: 3/10" (low)
   - Botão "Ver detalhes" para cada

2. **Tela detalhada de anúncio**:
   - Título do anúncio
   - Score de alinhamento (ex: "Seu alinhamento: 7/10")
   - Data de publicação
   - Duas opções/abas:
     a) "Palavras em Publicação" - tab com tabela
     b) "Palavras Sugeridas" - tab com tabela
   - Cada tab mostra palavra + score 0-10
   - Coluna de cores (verde = bom, amarelo = médio, vermelho = baixo)

3. **Filtros**:
   - Dropdown: "Maior alinhamento" vs "Menor alinhamento"
   - Checkbox: "Ver anúncios sem venda"

### Regras de Negócio
1. **Escala de 0-10**: representação interna de importância/demanda
2. **Categorias particulares**: algumas categorias (como "Outros") podem ter alinhamento = 0 porque o ML não fornece dados de tendência
3. **Período de coleta**: 30-60 dias pré-selecionado (pode ser ajustado)
4. **Atualização de dados**: semanal ou diária (não especificado)
5. **Visibilidade**: feature exists na categoria se o ML entrega dados de tendência para ela
6. **Palavras obrigatórias vs opcionais**: sistema diferencia (top 10 são "must-have")

---

## 3. COMO USAR OS RANKINGS DE MERCADO (Como_usar_os_rankings_de_Mercado__1XoXZwF1szA.pt.vtt)

### Nome da Feature
**Rankings de Mercado** (ou "Market Rankings")

### Descrição Completa
Feature que mostra 5 rankings diferentes de uma categoria:

1. **Ranking de Demanda** (1 ranking)
   - Mostra palavras-chave mais procuradas na categoria
   - Atualizado semanalmente
   - Acumula até fim do mês
   - Propósito: "aproximar do comprador"

2. **Rankings de Vendas** (4 rankings com focos diferentes)
   - Ranking de Publicações (listings mais vendidas)
   - Ranking de Catálogo (produtos/SKUs agregados, múltiplos vendedores)
   - Ranking de Marcas (brands mais vendidas)
   - Ranking de Vendedores (sellers que mais faturam)

**Todos ordenados por faturamento**.

### Termos/Vocabulário
- **Ranking de demanda** = words most searched
- **Criterios de busca** = marca, materiais, capacidades, atributos
- **Palavras-chave** = search terms do comprador
- **Demanda** = volume de buscas
- **Posição orgânica** = rank no search
- **Ranking de publicações** = listings mais vendidas
- **Variações bruscas** = sudden jumps in sales (identificar growth trends)
- **Publicações tradicionais vs catalogadas** = different listing types (clássico vs premium)
- **Ranking do catálogo** = produto agregado (SKU level, multiple sellers)
- **Vendas agrupadas** = sum of all listings for one product SKU
- **Tendências de vendas** = sales trends by model/product
- **Ranking de marcas** = most sold brands (aggregated)
- **Novos fornecedores** = suppliers emerging in category
- **Competitividade da marca** = how competitive is that brand space
- **Distribuição de vendas** = if sales are concentrated in few sellers or spread
- **Ranking de vendedores** = sellers ranked by faturamento (revenue)
- **Estratégias** = tactics used by top sellers
- **Crescimento de vendedores** = sellers growing fast in category
- **Modelos de negócio** = business approaches that work well

### Métricas/KPIs
1. **Frequência de busca** (por palavra-chave, em período)
2. **Faturamento** (receita total)
3. **Unidades vendidas** (quantidade)
4. **Preço** (median, avg)
5. **Concentração de vendas** (% por seller/brand)
6. **Tendências** (week-over-week, month-over-month growth)
7. **Taxa de conversão** (implied, não explicitamente mencionada)

### Fluxo do Usuário
1. Acessar "Rankings de Mercado"
2. Selecionar uma categoria
3. Ver 5 rankings em abas ou seções:

   **Aba 1: Ranking de Demanda**
   - Top 10 palavras-chave (search terms)
   - Cada uma com score/volume (0-100%)
   - Atualizado semanalmente
   - Acumula até fim do mês
   - Mostra: marca, materiais, capacidades, atributos buscados
   - **Propósito**: criar títulos mais eficazes com palavras que correspondem às pesquisas

   **Aba 2: Ranking de Publicações**
   - Lista listagens mais vendidas
   - Coluna: posição, título, vendedor, preço, unidades vendidas
   - Identificar variações bruscas (crescimento rápido)
   - Diferencias publicações "tradicionais" vs "catalogadas"
   - Mostra como amadurece um anúncio
   - **Sortable columns**: ordenar por faturamento, unidades, preço, etc
   - **Last update**: data de atualização

   **Aba 3: Ranking do Catálogo**
   - Venda agregada por produto (SKU level)
   - Uma "produto" = sum of sales de múltiplos sellers + múltiplos listings
   - Mostra tendências de vendas por modelo

   **Aba 4: Ranking de Marcas**
   - Marcas mais vendidas e agrupadas
   - Detectar novos fornecedores
   - Ver quanto vendem e quão competitiva é a marca
   - Ver se vendas distribuídas entre muitos ou poucos

   **Aba 5: Ranking de Vendedores**
   - Vendedores que mais faturam na categoria
   - O que vendem, a que preço, com quais estratégias
   - Detectar vendedores crescendo muito
   - **Propósito**: conhecer diferentes modelos de negócio bem-sucedidos

4. **Interatividade**:
   - Ordenar colunas de acordo com necessidade
   - Exemplo: ver quais faturam mais, vendem mais unidades, vendem a preço alto
   - Pode comparar preço com competitividade
   - Limpeza de filtros entre análises

### Dados Necessários
- **Histórico de buscas** (search query logs by category, 30-60 dias)
- **Catálogo de items** (todos listings da categoria)
- **Histórico de vendas** (orders por listing, por período)
- **Informações de sellers** (nome, tipo medalha, etc)
- **Dados de marcas** (brand name from item attributes)
- **Preços históricos** (price changes over time)
- **Atributos** (materials, capacities, etc)

### Endpoints Mercado Livre API
1. **GET /sites/{SITE_ID}/category_predictions/items** (ou similar) - busca logs/trends
   - Pode não ser público; pode ser proprietary Nubimetrics data

2. **GET /categories/{CATEGORY_ID}** - categoria metadata

3. **GET /items/{ITEM_ID}** - detalhe do item

4. **GET /users/{SELLER_ID}** - detalhe do vendedor (medalha, métricas)

5. **GET /items/search?category={CAT_ID}** - search items in category

6. **GET /orders/search?category={CAT_ID}** - historical orders

### Screenshots/UI
1. **Menu de seleção**:
   - Dropdown: "Selecione uma categoria"
   - Exibe subcategorias se houver

2. **Abas superiores**:
   - "Ranking de Demanda" | "Publicações" | "Catálogo" | "Marcas" | "Vendedores"
   - Cada aba com ícone representativo

3. **Ranking de Demanda** (aba 1):
   - Tabela: #, Palavra-chave, Freq Busca (%), Atributos Associados
   - Cores: verde (top), amarelo (médio), vermelho (baixo)
   - Nota: "Atualizado semanalmente, acumula até fim do mês"

4. **Ranking de Publicações** (aba 2):
   - Tabela: Posição, Título, Vendedor, Preço, Unidades, Faturamento
   - Botão de sort por coluna
   - Destaca variações bruscas com sinal visual

5. **Outros rankings**: estrutura similar com colunas apropriadas

### Regras de Negócio
1. **Atualização de ranking de demanda**: semanal (segunda-feira ou sexta)
2. **Acúmulo de dados**: reseta no fim de cada mês
3. **Ranking de catálogo**: dados agregados de múltiplos sellers/listings de mesmo produto
4. **Preço no ranking**: últimas 24-48h (dados recentes)
5. **Mineração de concorrentes**: "ótima forma de detectar novos fornecedores"
6. **Análise de marca**: identifica se categoria é competitiva (muitos sellers) ou concentrada (poucos)
7. **Propósito de Nubimetrics**: "Esperamos que seja muito útil. Estamos sempre disponíveis em horário comercial no nosso chat de suporte."

---

## 4. OTIMIZADOR DE ANÚNCIOS (Otimizador_de_anuncios__vCRg-MDIEk4.pt.vtt)

### Nome da Feature
**Otimizador de Anúncios** (ou "Ad Optimizer", "Diagnostic de Anúncios")

### Descrição Completa
Sistema de diagnóstico inteligente que:
1. Analisa cada anúncio com 5 índices (AI-powered)
2. Gera score de qualidade 0-100%
3. Sugere melhorias chaves para potencializar vendas e visitas
4. Mostra anúncios ativos com vendas nos últimos 30 dias
5. Permite filtrar e ordenar resultados
6. Indicadores diferenciados por perfil do vendedor (novo vs estabelecido)

### Termos/Vocabulário
- **Índice de qualidade (Nubimetrics)** = resumo/média dos 4 índices abaixo
- **Índice de alinhamento de demanda** = quão alinhado o título está com o que as pessoas pesquisam
- **Índice de posicionamento** = IA compara características do seu anúncio vs melhores anúncios da categoria
- **Taxa de conversão** = (usando IA) nível de conformidade das características vs anúncios que mais vendem
- **Índice de eficiência de conversão** = quão boa é a conversão do anúncio em relação à melhor da categoria
- **Índice de qualidade do Mercado Livre** = "saúde" do anúncio conforme regras genéricas do ML
- **Dinâmica vs Regras** = diferenciar entre o que realmente funciona vs checklist genérico
- **Recomendações diferenciadas** = dicas customizadas por tipo de produto + categoria + perfil vendedor
- **Perfil do vendedor**:
  - Pequeno/novo vendedor = prioridade é VISITAS (posicionamento)
  - Vendedor grande/profissional = prioridade é CONVERSÃO
- **Aprendizagem permanente** = sistema atualiza constantemente o que funciona
- **Características** = atributos do produto (cor, tamanho, marca, etc)
- **Variáveis de impacto** = quais características mais influenciam visitas vs conversão

### Métricas/KPIs
1. **Índice de qualidade** (0-100%, média ponderada de 4 índices)
2. **Índice de alinhamento de demanda** (0-100%)
3. **Índice de posicionamento (IA)** (0-100%)
4. **Taxa de conversão (IA)** (0-100%)
5. **Índice de eficiência de conversão** (0-100%)
6. **Índice de qualidade do Mercado Livre** (0-100%, regras genéricas)
7. **Visitas** (contagem)
8. **Vendas** (unidades)
9. **Período de análise**: últimos 30 dias (padrão)

### Fluxo do Usuário
1. Acessar "Otimizador de Anúncios"
2. Ver lista de anúncios ativos com vendas nos últimos 30 dias
3. Cada anúncio mostra:
   - Título
   - Índice de qualidade (card com %), barra colorida
   - Filtros disponíveis (ordenar por diferentes critérios)
4. Clicar em um anúncio para ver diagnóstico detalhado
5. **Vista detalhada mostra**:
   - Dados recolhidos para concluir a avaliação
   - Links externos (categoria, rankings de mercado, explorador de publicações)
   - Desempenho de competição:
     - Seu anúncio vs outros similares
     - Vs outros vendedores vendendo produtos iguais
     - NÃO é "se segue regras" mas "se está alinhado com dinâmicas que realmente funcionam"
   - Sistema constantemente avalia O QUE FUNCIONA no ML
   - Aprendizagem permanente (IA em loop contínuo)

6. **Recomendações diferenciadas por contexto**:
   - Variam por produto, publicação, categoria
   - NÃO uma recomendação geral (diferente do ML)
   - **Exemplo**: adição de parcelas é recomendação genérica do ML, mas Nubimetrics customiza
   - Recomendações específicas para cada produto + categoria

7. **Segmentação por perfil do vendedor**:
   - **Pequeno vendedor começando**:
     - Prioridade: atrair visitas
     - Foco em posicionamento
     - Depois, melhorar conversão
   - **Vendedor maior/profissional**:
     - Alto volume
     - Desafios de conversão
     - Aprendizagem permanente e ajustes

8. **Variáveis de impacto detectadas**:
   - Indices diferenciados se pequeno vs grande
   - Detecta quais variáveis impactam visitas (posicionamento)
   - Detecta quais impactam conversão
   - Consequentemente, recomendações são diferentes

9. **Funcionalidade será atualizada constantemente**:
   - Estarão vendo o que funciona melhor
   - Quais características diferenciam
   - Como atrair mais visitas ou vender melhor

### Dados Necessários
- **Anúncio**: título, descrição, atributos, preço, imagens
- **Histórico de vendas**: últimos 30 dias (orders)
- **Histórico de visitas**: últimos 30 dias
- **Dados dos concorrentes** (best sellers na categoria)
- **Métricas do ML**: qualidade rules/guidelines
- **Dados de mercado**: rankings, tendências

### Endpoints Mercado Livre API
1. **GET /items/{ITEM_ID}** - detalhe do item (title, description, attributes, price, images)
2. **GET /orders/search?seller={id}&created.from={date}** - vendas de 30 dias
3. **GET /items/{id}/visits/time_window?last=30&unit=day** - visitas de 30 dias
4. **GET /categories/{CAT_ID}** - categoria rules/guidelines
5. **GET /items/search?category={CAT_ID}&sort=sales** - top sellers na categoria

### Screenshots/UI
1. **Lista de anúncios**:
   - Tabela: Título, Índice de Qualidade (%), Vendas (30d), Visitas (30d), Conversão (%)
   - Card colorido para cada índice (verde/amarelo/vermelho conforme score)
   - Filtros/sorting por coluna

2. **Detalhe de anúncio**:
   - Seção "Diagnóstico": 4-5 cards com índices principais
   - Cada card: nome + score 0-100% + barra + explicação curta
   - Seção "Dados Recolhidos": mostra dados brutos usados para cálculo
   - Links externos (navegação rápida para categoria, rankings, explorador)
   - Seção "Desempenho": comparação com concorrentes
   - Seção "Recomendações": listagem de ações sugeridas (prioritizadas)

### Regras de Negócio
1. **Índice de qualidade**: média dos 4 índices (ou weighted average)
2. **IA utilizada para 2 índices**: posicionamento (IA comparar características) e conversão (IA avaliar conformidade)
3. **Dinâmica vs Regras**: Nubimetrics foca em "dinâmicas que funcionam" não checklist genérico
4. **Recomendações específicas**: por produto + categoria + perfil vendedor
5. **Atualização**: contínua (IA em loop)
6. **Período padrão**: 30 dias
7. **Histórico**: mantém dados para análise de tendência

---

## 5. EXPLORADOR DE ANÚNCIOS - ATUALIZAÇÕES (Atualizacoes_Explorador_de_anuncios__NbSow_P0tbc.pt.vtt)

### Nome da Feature
**Explorador de Anúncios** (com atualizações de UI/UX)

### Descrição Completa
Atualizações recentes na feature Explorador:
1. **Filtro à esquerda**: novo painel com filtros avançados
2. **Categoria L1 e L2**: permitir buscar por nível 1 (categoria inicial) e nível 2 (final)
3. **Catálogo Flex**: novo filtro de tipo de catálogo
4. **Marca**: filtro por marca do produto
5. **Exportação**: até 10.000 resultados podem ser exportados
6. **Colunas novas na exportação**:
   - Código completo da categoria
   - Categoria completa (full path)
7. **Vistas de vendas**: novas colunas de vendas (moeda local, unidades, períodos)

### Termos/Vocabulário
- **Explorador de anúncios** = ferramenta de busca/análise no marketplace
- **Categoria L1** = categoria raiz/inicial (ex: "Eletrônicos")
- **Categoria L2** = subcategoria (ex: "Eletrônicos > Smartphones")
- **Catálogo Fu** = tipo de catálogo (Flex Universal?)
- **Catálogo Flex** = tipo de catálogo (Flexible pricing?)
- **Filtro** = opção para refinar busca
- **Exportar** = download de dados em CSV/Excel
- **Vendas em moeda local** = vendas em reais (BRL)
- **Unidades vendidas** = quantidade
- **Período pré-selecionado** = 30-60 dias (padrão)
- **Vendas históricas reais** = dados acumulados desde sempre
- **Visitas históricas** = accumulated desde publicação
- **Informação passada** = dados antigos (históricas)
- **Informação recente** = dados de 30-60 dias (atualizados)
- **Dados relacionados** = correlação com período/tipo

### Métricas/KPIs
1. **Vendas em moeda local** (BRL)
2. **Unidades vendidas** (quantidade)
3. **Vendas históricas reais** (acumulado total)
4. **Unidades vendidas históricas** (acumulado total)
5. **Período de 30-60 dias** (recent data)
6. **Dias ativos da publicação** (duration online)

### Fluxo do Usuário
1. Acessar "Explorador de Anúncios"
2. Executar busca (palavra-chave)
3. **Novo painel à esquerda** com filtros:
   - Busca por categoria L1 (inicial)
   - Busca por categoria L2 (final)
   - Filtro de catálogo (Fu, Flex)
   - Filtro de marca
4. Ver resultados: lista de items com formações (dados agrupados)
5. **Colunas de vendas**:
   - Coluna 1: Vendas em moeda local (recente, 30-60 dias)
   - Coluna 2: Unidades vendidas (recente)
   - Coluna 3: Vendas históricas (acumulado total)
   - Coluna 4: Unidades vendidas históricas (acumulado)
   - Nota: "históricas trazem informação um pouco passada"
   - Nota: "recentes trazem informação mais atualizada (30-60 dias)"
6. **Seção oculta/detalhes** (click para expandir):
   - Informações referentes ao que o vendedor pode registrar no ML
   - SK (SKU) do item
   - "Jeitinho" (configuração/variação?)
   - Número de peça (Part Number)
   - Marca
7. **Exportação**:
   - Opção de exportar até 10.000 resultados
   - Novas colunas adicionadas:
     - Código completo da categoria
     - Categoria completa

### Dados Necessários
- **Catálogo completo** do ML (items com metadata)
- **Histórico de vendas** (por item, acumulado e por período)
- **Histórico de visitas** (por item)
- **Atributos** (categoria L1, L2, marca, tipo de catálogo)
- **Informações do vendedor** (SKU, part number, etc)

### Endpoints Mercado Livre API
1. **GET /items/search?q={query}&category={cat}** - buscar items
   - Filtros: L1, L2, brand, catalog type

2. **GET /items/{ITEM_ID}** - detalhe do item
   - Inclui: SKU, brand, part number, attributes

3. **GET /categories/{CAT_ID}** - categoria metadata
   - Inclui: L1, L2, full path

4. **GET /orders/search?...** - vendas

5. **GET /items/{id}/visits/time_window** - visitas por período

### Screenshots/UI
1. **Painel de filtros (esquerda)**:
   - Busca: input field com keyword
   - Categoria L1: dropdown
   - Categoria L2: dropdown (dependent on L1)
   - Catálogo: checkbox (Fu, Flex)
   - Marca: text input ou dropdown
   - Botão: "Buscar" ou "Aplicar Filtros"

2. **Tabela de resultados**:
   - Coluna: Título/Nome do item
   - Coluna: Categoria L1
   - Coluna: Categoria L2
   - Coluna: Marca
   - Coluna: Vendas (30-60d)
   - Coluna: Unidades (30-60d)
   - Coluna: Vendas históricas (total)
   - Coluna: Unidades históricas (total)
   - Expandir: detalhes (SKU, part number, etc)

3. **Botão de Exportação**:
   - "Exportar até 10.000 resultados"
   - Inclui automaticamente: código categoria, categoria completa

### Regras de Negócio
1. **Limite de exportação**: 10.000 registros
2. **Período padrão**: 30-60 dias para "vendas recentes"
3. **Dados históricos**: acumulado desde data de publicação
4. **Correlação**: vendas históricas x dias ativos (normalization implícita)
5. **Filtros**: L1 (required), L2 (optional), brand, catalog type
6. **Dados ocultos**: detalhes expandíveis (SKU, part number, marca)
7. **Atualização**: os dois primeiros campos (30-60d) trazem dados recentes
8. **Lembrança ao usuário**: "toda essa informação é dentro do tipo de item/produto que você tá buscando"

---

## 6. EXPLORADOR DE ANÚNCIOS - FEATURE PRINCIPAL (Explorador_de_anuncios__C_PQopLGWv4.pt.vtt)

### Nome da Feature
**Explorador de Anúncios (Publisher Explorer)**

### Descrição Completa
Funcionalidade central que permite:
1. Explorar publicações (listings) com vendas recentes
2. Configurar monitoramento de concorrência (concorrentes)
3. Realizar buscas precisas de títulos
4. Filtrar resultados para análise detalhada
5. Dois tipos de busca: exata (specific) e ampliada (broad)

**Propósito**: investigar mercado, monitorar concorrentes, encontrar oportunidades.

### Termos/Vocabulário
- **Explorador de anúncios** = marketplace listings explorer
- **Publicações com vendas** = listings que tiveram transações recentes
- **Período recente** = últimos 30-60 dias (por padrão)
- **Configurar concorrência** = linkar MLBs de concorrentes para monitorar
- **Publicações de concorrentes** = competitor listings
- **Vendedores concorrentes** = competitor sellers
- **Busca precisa de títulos** = exact search string matching
- **Filtros** = refinement options
- **Busca exata** = exact phrase matching
- **Busca ampliada** = broad/partial matching (similar terms)
- **Mercado Livre** = marketplace (often abbreviated as "ML")
- **Feedback** = user suggestions/feature requests

### Métricas/KPIs
1. **Vendas** (count, period)
2. **Período de análise** (30-60 dias)
3. **Número de publicações** (listings count)

### Fluxo do Usuário - Passo a Passo
1. **Acessar Explorador de Anúncios**:
   - Menu principal > "Explorador de Anúncios"
   - (ou similar path in app)

2. **Primeira tela** = busca e filtragem:
   - Entrar palavras-chaves/título que deseja investigar
   - Escolher tipo de busca:
     - **Busca Exata**: procura a frase exatamente como escrita (for specific products)
     - **Busca Ampliada**: procura variações e termos similares (for competition analysis)
   - Recomendação: "Se está investigando concorrência, use a busca ampliada"
   - Opcionalmente, aplicar filtros (categoria, marca, etc)
   - Clicar "Buscar"

3. **Resultados**:
   - Lista de publicações com vendas recentes
   - Cada linha mostra: título, vendedor, preço, vendas count, período
   - Filtros adicionais podem ser aplicados para refinar

4. **Configurar Concorrência** (do explorador):
   - Selecionar uma publicação
   - Opção "Monitorar" ou "Vincular como concorrente"
   - Sistema começa acompanhamento automático

5. **Segunda tela** (após expandir/detalhar um resultado):
   - Ver publicações similares
   - Ver vendedores similares
   - Opção para entrar em análise detalhada

6. **Interatividade**:
   - Usar filtros para refinar (remover se precisa fazer outra análise)
   - Deixar feedback se quiser
   - Recomendação: "Sua sugestão é sempre muito importante"

### Dados Necessários
- **Catálogo completo** do ML
- **Histórico de vendas**
- **Vendedores** (metadata)
- **Atributos e categorias**
- **Avaliações de confiabilidade** (para descartar spam)

### Endpoints Mercado Livre API
1. **GET /items/search?q={query}** - buscar items por keyword
   - Filtros: search_type (exact vs broad)

2. **GET /items/{ITEM_ID}** - detalhe do item
   - Inclui: title, price, seller, sold_quantity, category

3. **GET /orders/search?item={item_id}** - vendas de um item

4. **GET /users/{SELLER_ID}** - detalhe do vendedor

5. **GET /categories/{CAT_ID}** - categoria metadata

### Screenshots/UI
1. **Tela de busca**:
   - Campo de entrada: "Palavras-chaves que deseja investigar"
   - Botões de tipo de busca:
     - Radio: "Busca Exata"
     - Radio: "Busca Ampliada"
     - Texto: "Se está investigando concorrência, recomendamos usar a ampliada"
   - Botão: "Buscar"
   - Filtros (opcional): categoria, marca, etc

2. **Resultados**:
   - Tabela: Título, Vendedor, Preço, Unidades Vendidas, Período
   - Botão para cada linha: "Detalhes" ou "Monitorar"
   - Nota: "Não esqueça de limpar filtros se desejar realizar outra análise"

3. **Feedback**:
   - Botão no final: "Deixe-nos feedback"
   - Nota: "sua sugestão é sempre muito importante"

### Regras de Negócio
1. **Tipo de busca**:
   - Exata = exact phrase matching (high precision, low recall)
   - Ampliada = broad matching (low precision, high recall)
   - Recomendação interna: "use ampliada para análise competitiva"

2. **Período de dados**: 30-60 dias (padrão)

3. **Limpeza de filtros**: usuário deve lembrar de remover entre análises

4. **Feedback**: incentivado e valorizado ("sua sugestão é sempre muito importante")

5. **Monitoramento de concorrência**: feito automaticamente após vinculação

---

## 7. ANÁLISE SUAS CATEGORIAS (Analise_suas_categorias__jL9HvePmmGM.pt.vtt)

### Nome da Feature
**Análise Suas Categorias**

### Descrição Completa
Feature que permite analisar performance em cada subcategoria onde o usuário vende:
1. Listagem de subcategorias com vendas no mês atual (atualizado semanalmente)
2. Informações do mês anterior (para comparação)
3. Filtros para análise customizada
4. Ranking de concorrentes em cada categoria
5. Análise de desempenho competitivo
6. Recomendações AI para otimização

**Propósito**:
- Descobrir pontos fortes (onde melhor performance)
- Conhecer posição no ranking dos concorrentes
- Analisar desempenho em cada categoria
- Aprender sobre recomendações inteligentes para melhorar visitas e conversão
- Lembrete: "Mercado Livre premia quem mais contribui para a categoria com maior exposição"
- Estratégia: "Adicionar produtos nela facilitará as vendas para você"
- Foco: "Concentre-se naquelas em que você pode ser o líder para maximizar seu esforço"

### Termos/Vocabulário
- **Subcategorias** = nível 2 ou mais específico da hierarquia
- **Vendas** = transações no período
- **Faturamento** = receita total (venda x unidades)
- **Atualizado semanalmente** = dados atualizados 1x por semana
- **Mês atual** = período de 1º a hoje
- **Mês anterior** = período anterior de 30 dias
- **Filtros** = opções de refinamento
- **Ranking** = posição relativa vs concorrentes
- **Posição no ranking** = seu rank (ex: 5º lugar)
- **Concorrentes** = top sellers na categoria
- **Desempenho** = como vai sua performance vs mercado
- **Competição** = quantos/quem estão competindo
- **Subcategorias com vendas** = apenas as que tiveram transações
- **Atalhos** = quick links para relatórios relacionados
- **Detalhes da categoria** = informações mais completas
- **Rankings de mercado** = industry-wide rankings
- **Otimizador de anúncio** = diagnostics tool
- **Recomendações inteligentes** = AI-powered suggestions
- **Eficiência de conversão** = conversion rate quality
- **Características** = product attributes
- **Variáveis de impacto** = factors that influence ranking/conversion
- **Contribuição** = involvement/sales in category (ML rewards this)
- **Exposição** = visibility in category
- **Líderes da categoria** = top performers in subcategory

### Métricas/KPIs
1. **Faturamento** (receita)
2. **Conversão** (venda/visita %)
3. **Eficiência de conversão** (relative to best in category)
4. **Ranking position** (1st, 5th, 100th, etc)
5. **Gap to top 50** (quanto precisa para entrar top 50)
6. **Gap to top 10** (quanto precisa para entrar top 10)
7. **Gap to top 3** (quanto precisa para estar top 3)
8. **Gap to leader** (quanto precisa para ser #1)
9. **Vendas** (count)
10. **Visitas** (estimate)

### Fluxo do Usuário
1. Acessar "Análise Suas Categorias"
2. **Vista principal**:
   - Apresenta lista de TODAS as subcategorias que tiveram vendas
   - Período: mês atual (com atualização semanal)
   - Dados do mês anterior também disponíveis

3. **Filtros disponíveis**:
   - Ordenar por: Ranking, Faturamento, Eficiência de Conversão, Faturamento do Líder
   - Ordem: Crescente ou Decrescente
   - Comodidade: existem atalhos em cada postagem

4. **Cada categoria mostra**:
   - Título/Nome
   - Posição no ranking
   - Quanto precisa para atingir posições (top 50, top 10, top 3, ser líder)
   - Botão "Ver Mais" para detalhes dos 10 concorrentes mais próximos

5. **Detalhes de cada categoria** (ao clicar):
   - **Aba Detalhes**:
     - Gráfico mostrando crescimento e estacionalidade
     - Meses de maior/menor venda do ano
     - Referência a eventos de e-commerce relevantes (Black Friday, Natal, etc)
     - Distribuição de vendas por tipo de medalha (verde, ouro, prata, bronze)
     - % de publicações no catálogo
     - Detalhes sobre características de envio e descontos

   - **Aba Rankings**:
     - Top 10 ranking de demanda (palavras-chave)
     - 4 rankings de vendas: publicações, catálogo, marcas, vendedores

   - **Aba Sugestões** (AI-powered):
     - Identificar variáveis que impactam posicionamento
     - Identificar variáveis que impactam conversão
     - Ordenadas com maior impacto (mais precisão)
     - Recomendações para novas publicações baseadas em dados

6. **Exemplo de sugestão AI**:
   - Selecionar palavras que estejam alinhadas com pesquisas de compradores
   - Compreender o que gera impacto na geração de visitas
   - Compreender o que influencia conversão de visitantes em vendas

7. **Momento da publicação**:
   - Agora pode selecionar palavras alinhadas com pesquisas
   - Com maior precisão ao realizar novas publicações

### Dados Necessários
- **Histó rico de vendas** por categoria (30 dias + month-ago)
- **Informações de concorrentes**: top 10-20 sellers por categoria
- **Dados de medalha**: qual seller tem qual tipo
- **Histórico de preços** por categoria
- **Tipo de catálogo**: catálogo vs free listing
- **Características**: atributos que mais impactam
- **Tendências de busca**: keywords por período
- **Eventos sazonais**: Black Friday, Natal, etc

### Endpoints Mercado Livre API
1. **GET /users/{SELLER_ID}/items/search** - items by seller

2. **GET /orders/search?seller={id}&date_range=...** - vendas por período

3. **GET /categories/{CAT_ID}** - categoria metadata

4. **GET /items/search?category={CAT_ID}&sort=sales** - top items in category

5. **GET /users/...** - seller info (medalha type)

6. **GET /sites/{SITE_ID}/search_trends?category={CAT_ID}** - search trends (if available)

### Screenshots/UI
1. **Lista de categorias**:
   - Tabela: Categoria, Ranking, Faturamento, Eficiência de Conversão, Gap to Top
   - Botões de sort por coluna
   - Aumentar/diminuir ordem
   - Atalho "Ver Mais Concorrentes"

2. **Detalhes de categoria**:
   - **Aba 1: Detalhes**
     - Gráfico de linha: meses X faturamento (highlight picos/vales)
     - Tabela: distribuição por medalha (%)
     - Info: % in catálogo
     - Info: shipping characteristics, discount patterns

   - **Aba 2: Rankings**
     - 5 sub-tabs: Demanda, Publicações, Catálogo, Marcas, Vendedores
     - Cada um com tabela e sorting

   - **Aba 3: Sugestões**
     - Lista de recomendações AI (bullet points)
     - Cada uma mostrando: ação + impacto esperado

3. **Detalhes de Concorrente**:
   - Popup ou modal mostrando: Seller Name, Medalha, Faturamento, info adicional
   - Opção para "Acompanhar" ou "Vincular"

### Regras de Negócio
1. **Subcategorias listadas**: apenas as com vendas no período
2. **Atualização**: semanal (provavelmente segunda ou sexta)
3. **Dados de mês anterior**: para comparação ano-a-ano ou período-a-período
4. **Filtros**: ordenar por ranking, faturamento, eficiência conversão, faturamento do líder
5. **Recomendações AI**: variam por categoria, produto, perfil vendedor
6. **Estacionalidade**: destaca meses altos e baixos
7. **Medalha**: tipos (verde, ouro, prata, bronze) - indicadores de reliability
8. **Eventos**: mencionados como contexto (Natal, Black Friday, etc)
9. **Propósito da análise**: maximizar esforço focando em categorias onde pode ser líder
10. **Premiação do ML**: "Mercado Livre premia quem mais contribui para a categoria" (exposição maior)

---

## 8. REDESENHO DA OPORTUNIDADE (Redesenho_da_Oportunidade__NrVtkD45Bu0.pt.vtt)

### Nome da Feature
**Redesenho da Oportunidade** (ou "Opportunity Redesign")

### Descrição Completa
Melhorias na vista detalhada de categorias, com foco em:
1. Novo design da interface (simplificado)
2. Agregação de informações úteis no momento da publicação
3. Aba de Rankings com top 10 (demanda + vendas)
4. Aba de Detalhes com gráficos de crescimento/estacionalidade
5. Aba de Sugestões (AI-powered) com variáveis de impacto

**Propósito**: redesign do layout para maior clareza e usabilidade.

### Termos/Vocabulário
- **Vista detalhada** = detailed view of category
- **Novo desenho** = new UI/UX design
- **Leitura** = readability/clarity
- **Informações úteis** = relevant data points
- **Momento da publicação** = when creating a new listing
- **Aba** = tab/section
- **Top 10** = ranking of 10 best items
- **Ranking de demanda** = top searched keywords
- **Ranking de vendas** = top sold items (by listing, catalog, brand, seller)
- **Crescimento** = growth trajectory over time
- **Estacionalidade** = seasonal peaks and valleys
- **Meses** = time periods
- **Evento de comércio eletrônico** = seasonal event (Black Friday, Natal, etc)
- **Distribuição de vendas** = sales concentration (by medal, brand, seller)
- **Medalha** = seller reliability badge (Verde, Ouro, Prata, Bronze)
- **Catálogo** = catalog listings (vs free listings)
- **Características de envio** = shipping details (free shipping, express, etc)
- **Descontos** = price reductions/promotions
- **Sugestões** = recommendations (AI-powered)
- **Variáveis de impacto** = factors influencing ranking/conversion
- **Posicionamento** = search ranking/visibility
- **Conversão** = visitor-to-sale rate
- **Precisão** = accuracy of recommendations

### Métricas/KPIs
1. **Crescimento** (% over time)
2. **Estacionalidade** (seasonal pattern)
3. **Meses altos** (peak months)
4. **Meses baixos** (low months)
5. **Distribuição por medalha** (%)
6. **% no catálogo** (vs free listings)
7. **Posicionamento** (ranking position)
8. **Conversão** (%)
9. **Impacto de variáveis** (relative importance)

### Fluxo do Usuário
1. Acessar "Análise Suas Categorias" (ou similar menu)
2. Selecionar uma categoria
3. Ver novo design (simplified, aggregated information)
4. **Aba 1: Detalhes** (por padrão):
   - Gráfico de crescimento + estacionalidade
   - Mostra: picos (meses altos) e vales (meses baixos) do ano
   - Referências a eventos (Black Friday, Natal, etc)
   - Distribuição de vendas por medalha (gráfico ou tabela)
   - % de publicações no catálogo
   - Detalhes sobre características de envio
   - Detalhes sobre descontos praticados

5. **Aba 2: Rankings**:
   - Sub-aba: "Ranking de Demanda" (top 10 search terms)
   - Sub-aba: "Ranking de Vendas" com 4 perspectivas:
     - Publicações
     - Catálogo
     - Marcas
     - Vendedores

6. **Aba 3: Sugestões**:
   - AI identifica variáveis de impacto (on positioning and conversion)
   - Ordenadas por maior impacto (higher precision)
   - "traz uma maior precisão ao realizar novas publicações"
   - Agora no momento da publicação:
     - Pode selecionar palavras alinhadas com pesquisas de compradores
     - Compreender o que gera impacto na geração de visitas
     - Compreender o que influencia conversão

### Dados Necessários
- **Histórico de vendas** (12 meses, por mês)
- **Histórico de características** (atributos trending)
- **Dados de eventos** (calendar of e-commerce events)
- **Distribuição por medalha** (seller badges)
- **Tipo de catálogo** (catalog vs free)
- **Dados de envio** (shipping characteristics)
- **Tendências de desconto** (promotion patterns)
- **Variáveis de impacto** (ML AI features)

### Endpoints Mercado Livre API
(Similar to "Análise Suas Categorias" + add):
1. **GET /categories/{CAT_ID}/trending** - trending attributes/characteristics
2. **GET /events/calendar** (if exists) - e-commerce event calendar

### Screenshots/UI
1. **Menu de navegação**:
   - Dropdown: Selecionar categoria
   - Breadcrumb: Home > Categorias > [Category Name]

2. **Abas principais**:
   - Aba "Detalhes" (active by default)
   - Aba "Rankings"
   - Aba "Sugestões"

3. **Aba Detalhes**:
   - Gráfico de linha: 12 meses X vendas (crescimento + estacionalidade)
   - Anotações: picos (↑ Natal, Black Friday) e vales (↓ Jan, Jul)
   - Gráfico pizza/bar: distribuição por medalha (verde %, ouro %, prata %, bronze %)
   - Estatísticas: "X% no catálogo", "Frete grátis em X%", "Desconto médio: Y%"

4. **Aba Rankings**:
   - Sub-abas: Demanda | Publicações | Catálogo | Marcas | Vendedores
   - Cada sub-aba mostra ranking top 10/20

5. **Aba Sugestões**:
   - Lista bullet-pointed: Sugestão 1, Sugestão 2, etc
   - Cada sugestão com:
     - Descrição da ação
     - Impacto esperado (%)
     - Tipo de impacto (visitas vs conversão)

### Regras de Negócio
1. **Design novo** = simplified, mobile-first friendly
2. **Informações agregadas** = mostra resumos úteis no momento de publicar
3. **Período de análise** = 12 meses para estacionalidade
4. **Eventos** = destacados como contexto (Natal em dezembro, BF em novembro, etc)
5. **Medalhas** = indicador de seller reliability (relevante para escolha de concorrente para monitorar)
6. **Atualização** = semanal ou diária (não especificado)
7. **Recomendações AI** = customizadas por categoria + atributos presentes
8. **Precisão crescente** = "traz uma maior precisão ao realizar novas publicações"

---

## RESUMO DE FEATURES ANALISADAS

| # | Feature | Status | Descrição Breve |
|---|---------|--------|-----------------|
| 1 | Módulo Concorrência | ✅ Core | Vincular MLBs concorrentes para monitorar preço/vendas/visitas |
| 2 | Alinhamento à Demanda (Mobile) | ✅ Mobile | Score 0-10 de alinhamento entre anúncio e buscas do comprador |
| 3 | Rankings de Mercado | ✅ Core | 5 rankings: demanda, publicações, catálogo, marcas, vendedores |
| 4 | Otimizador de Anúncios | ✅ Core | Diagnóstico AI com 4-5 índices de qualidade |
| 5 | Explorador de Anúncios (Updates) | ✅ Core | Novo painel de filtros + export de 10k resultados + novas colunas |
| 6 | Explorador de Anúncios | ✅ Core | Busca/filtro de publicações recentes + configuração de concorrência |
| 7 | Análise Suas Categorias | ✅ Core | Posicionamento por subcategoria + recomendações AI |
| 8 | Redesenho da Oportunidade | ✅ Core | Nova UI para vista detalhada de categorias (rankings + sugestões) |

---

## DADOS CONSOLIDADOS SOBRE NUBIMETRICS

### Algoritmos/IA Mencionados
1. **Inteligência Artificial** para:
   - Comparação de características (índice de posicionamento)
   - Avaliação de conformidade (taxa de conversão)
   - Identificação de variáveis de impacto
   - Detecção de estacionalidade
   - Recomendações customizadas por contexto

2. **Machine Learning**:
   - Aprendizagem permanente (loop contínuo)
   - Avaliação dinâmica do "que funciona" vs regras genéricas
   - Diferenciação por perfil de vendedor (novo vs estabelecido)

### Terminologia Comum (Glossário)
- **MLB** = anúncio/listing do Mercado Livre (item ID)
- **Demanda** = volume de buscas/interesse
- **Alinhamento** = match between offer and demand
- **Posicionamento** = search ranking/visibility
- **Conversão** = visitantes que viraram clientes
- **Taxa de conversão** = %visitas que resultam em venda
- **Ranking** = posição relativa vs concorrentes
- **Score** = métrica 0-100%
- **Snapshot** = foto/estado em um ponto no tempo
- **Faturamento** = receita (venda x quantidade)
- **Medalha** = seller reliability badge (verde, ouro, prata, bronze)
- **Catálogo** = catalog listings (vs free listings)
- **SKU** = stock keeping unit (interno do usuário)
- **Atributos** = product characteristics (cor, tamanho, material, etc)
- **Estacionalidade** = padrão sazonal (peaks/valleys)
- **Dinâmica** = padrões que realmente funcionam
- **Regras** = checklist genérico (menos relevante)
- **Variáveis de impacto** = factors influencing ranking/conversion
- **Perfil do vendedor** = classificação (novo, pequeno, grande, professional)
- **Aprendizagem permanente** = continuous improvement via IA

### KPIs/Métricas Padrão Nubimetrics
1. **Índice de Qualidade** (0-100%)
2. **Índice de Alinhamento de Demanda** (0-100%)
3. **Índice de Posicionamento** (0-100%, AI-powered)
4. **Taxa de Conversão** (%, AI-evaluated)
5. **Índice de Eficiência de Conversão** (0-100%)
6. **Índice de Qualidade do Mercado Livre** (0-100%, rules-based)
7. **Score de Alinhamento** (0-10, mobile)
8. **Faturamento** (BRL)
9. **Visitas** (count)
10. **Vendas** (units)
11. **Ranking Position** (1st, 5th, etc)
12. **Gap to Rank Position** (quanto falta para atingir)

### Endpoints Mercado Livre API Utilizados
1. `GET /users/{seller_id}/items/search` - listar anúncios ativos
2. `GET /items/{item_id}` - detalhe de item
3. `GET /users/{USER_ID}/items_visits?date_from&date_to` - visitas agregadas
4. `GET /items/{ITEM_ID}/visits/time_window?last=X&unit=Y` - visitas por periodo
5. `GET /orders/search?seller={id}&order.date_created.from={date}` - pedidos/vendas
6. `GET /categories/{CAT_ID}` - metadados de categoria
7. `GET /items/search?q={query}&filters` - buscar items
8. `GET /users/{SELLER_ID}` - info do vendedor

### Observações Competitivas Críticas
1. **Nubimetrics VS Mercado Livre API**:
   - Nubimetrics enriches ML data com análises AI próprias
   - Rankings de demanda (search trends) pode ser proprietary (não vem direto da API)
   - Recomendações AI são customizadas (não genéricas do ML)

2. **Diferenciação Nubimetrics**:
   - "Dinâmica vs Regras": foco em o que REALMENTE funciona, não checklist
   - Recomendações customizadas por: produto + categoria + perfil vendedor
   - Aprendizagem permanente (IA em loop)
   - Mobile app com Alinhamento à Demanda (exclusive feature)
   - Interface simplificada vs dados complexos

3. **Frequência de Atualização**:
   - Rankings de demanda: semanal
   - Snapshots: diário (provavelmente 6h BRT, alinhado com Celery job padrão)
   - Dados históricos: mantém 12 meses para estacionalidade
   - Categorias: atualizado semanalmente

4. **Limites Inferidos**:
   - Exportação: até 10.000 registros
   - API rate limit (ML): 1 req/sec padrão + backoff
   - Período de análise padrão: 30-60 dias para "recente", 12 meses para histórico
   - Categorias: apenas as com vendas no período são listadas

---

## CONCLUSÕES PARA MSM_Pro

### Funcionalidades a Considerar Implementar
1. ✅ **Módulo Concorrência** - rastreamento de concorrentes por MLB
2. ✅ **Rankings de Mercado** - 5 tipos de rankings (demanda, publicações, catálogo, marcas, vendedores)
3. ✅ **Otimizador de Anúncios** - diagnóstico AI com 4-5 índices
4. ✅ **Explorador de Anúncios** - busca avançada + configuração de concorrência
5. ✅ **Análise Suas Categorias** - posicionamento por subcategoria + recomendações AI
6. ✅ **Alinhamento à Demanda** - score 0-10 de match entre anúncio e demanda (mobile first)

### Diferenciadores Críticos vs Nubimetrics
1. **MSM_Pro deve focar em**:
   - Experiência mobile-first (Alinhamento à Demanda é hit em mobile)
   - IA customizada por contexto (não regras genéricas)
   - Integração com dados financeiros (margem, frete, impostos)
   - Alertas em tempo real (não semanal)
   - Export/integração com ferramentas de vendas (ERP, WMS)

2. **Componentes Técnicos Necessários**:
   - ETL de dados do ML (snapshots diários)
   - Sistema de ranking/scoring (AI/ML models)
   - Cache distribuído (Redis) para performance
   - Banco de dados de séries temporais (InfluxDB ou similar)
   - Background jobs (Celery) para processamento batch

---

**FIM DA ANÁLISE BATCH 1/2**

Próximas análises: Batch 2 (comportamentos, estratégias sazonais, tendências específicas do ML)

Data de Conclusão: 2026-03-18
Analista: Claude (Data Analyst)
Nível de Detalhe: Máximo (exhaustive)
