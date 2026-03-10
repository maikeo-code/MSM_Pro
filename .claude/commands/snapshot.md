---
description: Busca e exibe os últimos snapshots de um anúncio MLB no banco de dados
argument-hint: <MLB-ID> [dias]
allowed-tools: [Bash, Read]
---

# Snapshot de Anúncio — MSM_Pro

Exibe o histórico recente de um anúncio MLB diretamente do banco de dados.

## Como usar
O usuário pode fornecer:
- `MLB-ID` — ID do anúncio (ex: MLB-3456789012)
- `dias` — quantos dias de histórico (padrão: 30)

## Passos

1. Verifique se o docker-compose está rodando:
```bash
docker ps | grep msm_postgres
```

2. Se estiver rodando, consulte o banco:
```bash
docker exec msm_postgres psql -U msm -d msm_pro -c "
SELECT
  ls.data,
  ls.preco,
  ls.visitas,
  ls.vendas,
  ls.perguntas,
  ls.estoque,
  ROUND((ls.vendas::numeric / NULLIF(ls.visitas, 0)) * 100, 2) AS conversao_pct
FROM listing_snapshots ls
JOIN listings l ON l.id = ls.listing_id
WHERE l.mlb_id = '[MLB-ID]'
  AND ls.data >= NOW() - INTERVAL '[dias] days'
ORDER BY ls.data DESC;
"
```

3. Exiba os resultados em formato de tabela legível com:
   - Cada linha = 1 dia
   - Destaque a melhor conversão em verde
   - Destaque o maior volume de vendas
   - Calcule médias do período

4. Se o banco não estiver acessível, informe que o Docker precisa estar rodando:
```
docker-compose up -d
```

## Saída esperada
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SNAPSHOTS — [MLB-ID] (últimos [dias] dias)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Data       │ Preço    │ Visitas │ Vendas │ Conversão
  ───────────┼──────────┼─────────┼────────┼──────────
  2025-03-10 │ R$ 99,00 │   312   │   7    │  2,24%
  2025-03-09 │ R$ 99,00 │   298   │   6    │  2,01%
  ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Média do período: [X] vendas/dia | [Y]% conversão
```
