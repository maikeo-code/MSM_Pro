# MSM_Pro — Historico de Insights e Sugestoes

> Arquivo para registrar todas as dicas, sugestoes e analises ao longo do tempo.
> Cada entrada tem data, status e prioridade para acompanhar o que foi implementado.

---

## 2026-03-12 — Sessao 1: Analise Inicial

### Proximos Passos por Prioridade

| # | Feature | Prioridade | Status | Notas |
|---|---------|-----------|--------|-------|
| 1 | Cadastro de custo por SKU + Calculadora de margem | ALTA | Pendente | Sem custo, nao sabe se lucra ou perde |
| 2 | Alertas de estoque baixo (email) | ALTA | Pendente | Estoque zero = anuncio morre no ranking |
| 3 | Grafico preco x conversao | ALTA | Implementado | Recharts na pagina de detalhe do MLB |
| 4 | Monitoramento de concorrentes | MEDIA | Pendente | Sprint 3 — so util apos saber margem |
| 5 | WhatsApp para alertas | BAIXA | Pendente | Email resolve por agora |
| 6 | Importacao de custos via CSV | MEDIA | Pendente | Acelera adocao para quem tem planilha |

### Metricas Importantes para Iniciante

| Metrica | Faixa Ideal | Acao |
|---------|------------|------|
| Conversao < 1% | RUIM | Revisar preco, titulo, fotos, descricao |
| Conversao 1-3% | NORMAL | Manter e monitorar |
| Conversao 3-5% | BOM | Nao mexer no preco sem motivo |
| Conversao > 5% | OTIMO | Considerar aumento leve de preco |
| Estoque < 5 un | CRITICO | Reabastecer imediatamente |
| Estoque < 10 un | ALERTA | Planejar reposicao |
| Valor estoque alto + conversao baixa | RISCO | Capital parado — considerar promocao |

### Erros Comuns de Iniciantes no ML

1. **Estoque zerado** — Anuncio some do ranking, perde historico de posicao
2. **Preco igual ao concorrente com Full** — Perde sempre (Full tem frete gratis)
3. **Subir preco bruscamente** — Conversao despenca, algoritmo penaliza
4. **Perguntas sem resposta** — Reputacao cai, afeta TODOS os anuncios
5. **Margem negativa sem saber** — Vende muito mas perde dinheiro
6. **Ignorar health score** — Anuncio incompleto rankeia pior

### Comparacao com Ferramentas do Mercado

| Ferramenta | O que faz | O que MSM_Pro faz diferente |
|-----------|-----------|----------------------------|
| Nubimetrics | Inteligencia de mercado (categorias, tendencias) | MSM_Pro analisa SEUS anuncios especificamente |
| Bling | ERP completo (NF, estoque fisico, contas) | MSM_Pro foca em decisao estrategica de preco |
| Anymarket/Skyhub | Hub multi-marketplace (ML + Shopee + Amazon) | MSM_Pro tem profundidade no ML |
| Melhor Envio | Compara fretes de transportadoras | Integracao futura para margem mais precisa |
| Seller Central ML | Painel nativo do ML | Nao guarda historico longo, nao calcula margem |

### Integracoes Futuras Sugeridas

1. **Melhor Envio API** — Custo real de frete por produto (margem mais precisa)
2. **WhatsApp (Twilio/Evolution API)** — Alertas urgentes direto no celular
3. **Google Sheets** — Importar/exportar dados para quem gosta de planilha
4. **N8N** — Automacoes customizadas (ja tem workflow no projeto)

### Alertas Sugeridos para Implementar

| Alerta | Tipo | Prioridade |
|--------|------|-----------|
| Estoque abaixo de X unidades | CRITICO | Sprint 4 |
| Conversao caiu mais de 50% vs ontem | WARNING | Sprint 4 |
| 0 vendas por N dias consecutivos | WARNING | Sprint 4 |
| Concorrente mudou preco | INFO | Sprint 4 |
| Preco subiu/desceu mais de X% | INFO | Sprint 4 |
| Perguntas novas sem resposta | WARNING | Futuro |

---

## Como usar este arquivo

- Cada nova sessao de insights adiciona uma secao com a data
- Marcar status como: Pendente / Em Progresso / Implementado / Descartado
- Comparar periodicamente: o que foi sugerido vs o que foi feito
- Usar como base para planejar proximos sprints
