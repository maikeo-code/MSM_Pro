# MSM_Pro — Cronograma Completo de Implementação

> Atualizado: 2026-03-12
> Baseado em: análise das missões ML, capturas UpSeller, insights de ferramentas similares

---

## FASE 1 — Correções e Ajustes Visuais (AGORA)
**Status:** Em andamento
**Estimativa:** Sessão atual

| # | Tarefa | Status |
|---|--------|--------|
| 1.1 | Ordenar tabela de anúncios por vendas do dia (decrescente) | Em andamento |
| 1.2 | Coluna "Receita" entre Conversão e Valor Estoque no resumo por período | Em andamento |
| 1.3 | SKU ao lado do MLB (formato: `MLB... · SKU: ...`) | Código pronto, aguardando sync |
| 1.4 | Forçar sync para popular category_id e seller_sku | Em andamento |
| 1.5 | Garantir mesmas colunas de vendas em Dashboard e Anúncios | Em andamento |

---

## FASE 2 — Taxa Real por Categoria (próxima sessão)
**Prioridade:** ALTA
**Impacto:** "Você Recebe" com valor preciso (não estimativa)

| # | Tarefa | Dependência |
|---|--------|-------------|
| 2.1 | Cache de taxas ML por categoria (tabela `ml_category_fees` ou Redis) | - |
| 2.2 | No sync diário: chamar `/sites/MLB/listing_prices` por categoria única | 2.1 |
| 2.3 | Atualizar cálculo `voce_recebe` para usar taxa real do cache | 2.2 |
| 2.4 | Mapeamento `listing_type` → `listing_type_id` ML (classico→gold_special, premium→gold_pro) | 2.2 |
| 2.5 | Taxa fixa por faixa de preço (R$6,75 para R$50-79, etc.) | 2.2 |
| 2.6 | Tooltip no frontend mostrando breakdown: comissão % + taxa fixa + frete | 2.3 |

---

## FASE 3 — Frete Real por Anúncio
**Prioridade:** ALTA
**Impacto:** "Você Recebe" completo (preço - taxa - frete)

| # | Tarefa | Dependência |
|---|--------|-------------|
| 3.1 | Extrair dimensões/peso do item ML (campo `shipping.dimensions`) | - |
| 3.2 | Salvar dimensões no Listing (migration) | 3.1 |
| 3.3 | Chamar `/users/{USER_ID}/shipping_options/free` com dimensões do item | 3.2 |
| 3.4 | Cache de custo de frete por anúncio (atualizar 1x/dia no sync) | 3.3 |
| 3.5 | Atualizar `voce_recebe = preço - taxa_real - frete_real` | 3.4, 2.3 |
| 3.6 | Distinguir "frete grátis" (vendedor paga) vs "comprador paga" | 3.3 |

---

## FASE 4 — Margem Real e Rentabilidade
**Prioridade:** ALTA
**Impacto:** O vendedor sabe EXATAMENTE quanto lucra por anúncio

| # | Tarefa | Dependência |
|---|--------|-------------|
| 4.1 | Cadastro de custo por SKU (já existe base no módulo produtos) | - |
| 4.2 | Vincular SKU → Listing automaticamente via seller_sku do ML | 1.4 |
| 4.3 | Calcular margem = voce_recebe - custo_sku | 3.5, 4.1 |
| 4.4 | Coluna "Margem (R$)" e "Margem (%)" na tabela de anúncios | 4.3 |
| 4.5 | Alerta automático: "margem abaixo de X%" | 4.3 |
| 4.6 | Dashboard card: "Margem Total do Dia" | 4.3 |

---

## FASE 5 — Simulador de Preço (What-If)
**Prioridade:** MÉDIA
**Impacto:** Vendedor testa cenários antes de alterar preço

| # | Tarefa | Dependência |
|---|--------|-------------|
| 5.1 | Endpoint `POST /api/v1/financeiro/simular` | 2.3, 3.5 |
| 5.2 | Frontend: slider de preço na página de detalhe do anúncio | 5.1 |
| 5.3 | Mostrar em tempo real: novo preço → nova taxa → novo frete → nova margem | 5.2 |
| 5.4 | Botão "Aplicar preço" (chama PUT /items/{id} via API ML) | 5.3 |
| 5.5 | Simulação em lote (alterar preço de múltiplos anúncios) | 5.4 |

---

## FASE 6 — Funil de Vendas e Heatmap
**Prioridade:** MÉDIA
**Impacto:** Visualização avançada igual ao painel ML

| # | Tarefa | Dependência |
|---|--------|-------------|
| 6.1 | Gráfico funil: Visitas → Vendas (Recharts) | - |
| 6.2 | Heatmap de vendas por dia da semana e horário | - |
| 6.3 | Extrair hora dos pedidos (campo `date_created` nas orders) | - |
| 6.4 | Card "Melhor dia/horário para vender" | 6.2 |
| 6.5 | Gráfico de tendência semanal (vendas por dia da semana) | 6.2 |

---

## FASE 7 — Multi-conta e Concorrência Avançada
**Prioridade:** MÉDIA

| # | Tarefa | Dependência |
|---|--------|-------------|
| 7.1 | Testar OAuth com segunda conta ML | - |
| 7.2 | Sync paralelo por conta (Celery group) | 7.1 |
| 7.3 | Dashboard consolidado (todas as contas juntas) | 7.2 |
| 7.4 | Gráfico comparativo meu preço vs concorrente no tempo | Sprint 3 |
| 7.5 | Alerta: concorrente vendendo abaixo de X% do meu preço | Sprint 4 |

---

## FASE 8 — Inteligência e Automação
**Prioridade:** BAIXA (futuro)

| # | Tarefa | Dependência |
|---|--------|-------------|
| 8.1 | Sugestão automática de preço ótimo (maximizar margem × volume) | 4.3 |
| 8.2 | Previsão de estoque (quando reabastecer) | 6.2 |
| 8.3 | Ranking de saúde dos anúncios (health score ponderado) | - |
| 8.4 | Relatório semanal por email (resumo automático) | Sprint 4 |
| 8.5 | WebSocket para atualizações em tempo real | - |
| 8.6 | Integração com Bling/Tiny (importar custos automaticamente) | 4.1 |

---

## Resumo de Prioridades

| Fase | Nome | Prioridade | Impacto |
|------|------|-----------|---------|
| 1 | Correções visuais | URGENTE | Tabelas corretas, UX |
| 2 | Taxa real por categoria | ALTA | "Você Recebe" preciso |
| 3 | Frete real | ALTA | "Você Recebe" completo |
| 4 | Margem real | ALTA | Lucro real por anúncio |
| 5 | Simulador de preço | MÉDIA | Decisão informada |
| 6 | Funil e heatmap | MÉDIA | Visualização avançada |
| 7 | Multi-conta | MÉDIA | Escala |
| 8 | Inteligência | BAIXA | Automação futura |

---

## Fontes de dados por feature

| Feature | API ML usada | Endpoint |
|---------|-------------|----------|
| Taxa real | listing_prices | GET /sites/MLB/listing_prices |
| Frete real | shipping_options | GET /users/{id}/shipping_options/free |
| SKU vendedor | items | GET /items/{id} → seller_custom_field |
| Thumbnail | items | GET /items/{id} → secure_thumbnail |
| Vendas do dia | orders/search | GET /orders/search?seller={id}&order.status=paid |
| Visitas | visits/items | GET /visits/items?ids=... |
| Promoções | seller-promotions | GET /seller-promotions/items/{id} |
| Concorrentes | items | GET /items/{id} (público) |
| Hora da venda | orders/search | order.date_created → extrair hora |
