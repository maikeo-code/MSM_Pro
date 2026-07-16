# Scraper local de preço de concorrentes

Raspa o preço da **página pública** do Mercado Livre para os concorrentes que a
**API não entrega** e envia para o MSM_Pro via `POST /competitors/prices/ingest`.

## Por que existe (o problema)
- `GET /items/{id}` de **item de terceiro** → **403 access_denied** (bloqueio do ML).
- Multiget `/items?ids=…&attributes=…` → **também 403** (item-level, não atributo).
- O preço existe no **JSON-LD** (`offers.price`) da página pública, MAS o ML barra
  requisição de **IP de datacenter** (o Railway cai no `account-verification`).
- Logo: o scraping precisa rodar de um **IP residencial** → **localmente**, e o
  resultado é enviado ao backend por um endpoint de ingestão.

> Concorrentes de **catálogo** (id 8díg ou que resolvem para `/p/MLBxxxx`) são
> coletados direto no Railway pela task `collect_competitor_prices` (09:30 UTC),
> via `/products/{id}` + `/products/{id}/items`. Este scraper cobre o RESTO.

## O que faz
1. Abre cada página pública (via `dev-browser`, browser real que passa o muro).
2. Extrai o preço do `JSON-LD` (fallback: preço visível `.andes-money-amount`).
3. Loga na API e faz `POST /api/v1/competitors/prices/ingest` (upsert por `(id_ml, day)`).

## Pré-requisitos
- `dev-browser` instalado (`npm install -g dev-browser && dev-browser install`).
- `python` e `curl` no PATH (Git Bash).

## Rodar
```bash
MSM_SENHA='suaSenha' bash run.sh
# opcionais: MSM_EMAIL, MSM_API
```

## Agendar (diário) no Windows
Task Scheduler → nova tarefa → Ação:
```
Programa:  C:\Program Files\Git\bin\bash.exe
Argumentos: -lc "cd '/c/Users/Maikeo/MSM_Imports_Mercado_Livre/msm_pro/scripts/competitor_scraper' && MSM_SENHA='***' bash run.sh >> scraper.log 2>&1"
```
Sugestão: 06:35 BRT (após o job de catálogo do Railway às 06:30 BRT / 09:30 UTC).

## Alvos
Editar o array `TARGETS` em `run.sh`. Hoje: 7 itens 10díg + `MLBU3453370601`.
Mapeamento e histórico no vault: `05 - Projetos Tech/MSM_Pro/12 - Ideias/Coleta de preço de concorrentes (competitor_prices).md`.

## Limitações conhecidas
- `MLBU3453370601`: JSON-LD sem `offers.price` (estrutura de página diferente) →
  precisa de seletor específico; hoje sai "(sem preço)".
- `sold_quantity`/`available_quantity` não vêm confiáveis do scraping → ficam NULL.
- Frágil por natureza (depende do HTML público do ML). Se um preço parar de sair,
  revalidar o seletor com `dev-browser`.
