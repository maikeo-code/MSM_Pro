# Catálogo de Dados — MSM_Pro

> **Propósito:** mapa único de rastreabilidade de TODO número que o app mostra. Para cada campo de
> cada tela, cada endpoint interno e cada método do cliente ML, este documento diz: de onde o dado
> vem, quem é o dono, qual endpoint do ML o alimenta, e se existe um teste/checagem que garante que
> está certo. É o pré-requisito para "testar cada dado" — transforma o app inteiro numa lista finita.
>
> Criado na Etapa E6 (Fase 0) do Plano Definitivo. Preenchido nas Fases 1B, 2 e 2B.
> Status por item: ✓ tem dono e check | ✗ tem dono, falta check | 🔴 órfão/duvidoso (vira bug).

---

## 1. TELAS (preenchido na Fase 2 — E20 a E36)

> Formato por tela: campo exibido → endpoint backend → serviço:função → tabela.coluna →
> endpoint ML → check/teste → status.

| Tela | Campo | Endpoint backend | Serviço:função | Tabela.coluna | Endpoint ML | Check | Status |
|------|-------|------------------|----------------|---------------|-------------|-------|--------|
| _(a preencher — E20 Dashboard em diante)_ | | | | | | | |

---

## 2. ENDPOINTS INTERNOS (preenchido na Fase 2B — EA1 a EA18)

> Inventário completo: 124 endpoints em 17 routers (extraído por grep em 2026-07-09).
> Formato: método+path → serviço:função → tabelas lidas/escritas → endpoint(s) ML → tela que usa →
> teste → status (✓ / 🔴 órfão / 🟡 debug-interno).

| Router | Método + Path | Serviço:função | Tabelas | Endpoint ML | Tela que usa | Teste | Status |
|--------|---------------|----------------|---------|-------------|--------------|-------|--------|
| _(a preencher — EA1 auth em diante)_ | | | | | | | |

---

## 3. CLIENTE ML — 51 MÉTODOS (preenchido na Fase 1B — EC1 a EC12)

> `backend/app/mercadolivre/client.py` — o único arquivo que fala com a API do ML.
> Formato: método → linha → endpoint ML → verbo → call-sites → status (ativo/morto).

| Método | Linha | Endpoint ML | Verbo | Chamado por (call-sites) | Status |
|--------|-------|-------------|-------|--------------------------|--------|
| _(a preencher — EC1)_ | | | | | |

---

## 4. CRUZAMENTO (preenchido em EA17)

> Mapa navegável nos dois sentidos: dado uma tela, quais endpoints e métodos ML a alimentam; dado um
> método ML, quais endpoints e telas dependem dele. Preenchido ao final da Fase 2B.

_(a preencher — EA17)_
