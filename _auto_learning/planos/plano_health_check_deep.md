# Plano: Health Check com Verificacao de Dependencias
Data: 2026-03-13
Baseado em: Sucesso #5 (ciclo 1)
Prioridade: P2

## Problema Identificado
O endpoint /health retorna {status: "ok"} estaticamente sem verificar se Postgres e Redis estao acessiveis. Se o banco cair, Railway continua achando que o servico esta saudavel e nao reinicia o container.

## Solucao Proposta
1. Criar endpoint `/health/ready` (readiness probe) que:
   - Executa `SELECT 1` no Postgres via async session
   - Executa `PING` no Redis
   - Retorna status 200 se ambos respondem, 503 se algum falha
2. Manter `/health` como liveness probe (rapido, sem I/O)
3. Atualizar `railway.json` para usar `/health/ready` como healthcheckPath

## Arquivos Afetados
- `backend/app/main.py` — adicionar rota /health/ready
- `backend/railway.json` — atualizar healthcheckPath

## Riscos
- Se Postgres tiver latencia alta, o health check pode timeout e Railway reiniciar desnecessariamente
- Mitigacao: timeout de 5s no check, com fallback para "degraded" em vez de "unhealthy"

## Metricas de Sucesso
- Quando Postgres cai, Railway detecta em < 30s e reinicia
- Health check responde em < 100ms em operacao normal

## Status: PENDENTE
