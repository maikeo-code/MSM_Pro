---
description: Fluxo guiado para configurar um alerta em um anúncio ou SKU
argument-hint: [MLB-ID ou SKU]
allowed-tools: [Read, Bash]
---

# Configurar Alerta — MSM_Pro

Guie o usuário para criar um alerta de monitoramento em um anúncio (MLB) ou produto (SKU).

## Tipos de Alerta Disponíveis

| # | Tipo | Exemplo |
|---|------|---------|
| 1 | Conversão abaixo de X% | "Me avisa se conversão < 1.5%" |
| 2 | Estoque crítico | "Me avisa se estoque < 10 unidades" |
| 3 | Zero vendas por N dias | "Me avisa se 0 vendas por 2 dias seguidos" |
| 4 | Concorrente mudou preço | "Me avisa se concorrente A mudar preço" |
| 5 | Concorrente mais barato | "Me avisa se alguém vender abaixo de R$ X" |

## Fluxo

### Passo 1 — Identificar o alvo
Pergunte:
- O alerta é para um **anúncio específico** (MLB) ou para um **produto** (SKU)?
- Informe o ID (ex: MLB-3456789012 ou FONE-BT-001)

### Passo 2 — Tipo de alerta
Apresente a tabela acima e pergunte qual tipo deseja configurar.
Pode selecionar mais de um.

### Passo 3 — Configurar threshold
Dependendo do tipo escolhido, pergunte o valor limite:
- Tipo 1: qual % mínima de conversão?
- Tipo 2: qual quantidade mínima de estoque?
- Tipo 3: quantos dias sem venda?
- Tipo 4: qual concorrente monitorar? (MLB do concorrente)
- Tipo 5: qual preço mínimo aceitável?

### Passo 4 — Canal de notificação
Pergunte:
- **Email** — qual endereço? (fase atual)
- **Frequência** — notificar 1x por dia ou imediatamente ao detectar?

### Passo 5 — Resumo e instrução
Exiba resumo do alerta e informe:
- Se API estiver rodando: `POST http://localhost:8000/api/v1/alertas/`
- Ou gere o comando curl para cadastro

## Observação
Lembre o usuário que alertas são verificados pelo Celery a cada ciclo de sync (configurável).
