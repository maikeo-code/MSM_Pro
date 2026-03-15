# IA Geral — Processos e Dados

> Cerebro central que orquestra todos os projetos de IA.
> Leia este arquivo COMPLETO antes de qualquer acao.

## O que e

Sistema de inteligencia artificial centralizado que:
1. **Orquestra** todos os projetos (MSM_Pro, WhatsApp, Instagram, Emails)
2. **Aprende** continuamente com cada projeto via auto-learning
3. **Distribui** regras globais para todos os projetos
4. **Instala** o sistema de auto-learning em novos projetos

## Estrutura

```
IA_Geral_Processos_Dados/
├── CLAUDE.md                   <- este arquivo (cerebro central)
├── engine.py                   <- motor do banco de dados global
├── loop_runner.py              <- CLI para operacoes no banco
├── db/
│   ├── schema.sql              <- schema das tabelas
│   └── learning.db             <- banco SQLite global (gerado na 1a execucao)
├── agentes/                    <- 13 agentes centralizados
│   ├── curiosa.md              <- [Learning L1] Gera perguntas
│   ├── respondedora.md         <- [Learning L1] Responde
│   ├── confrontadora.md        <- [Learning L2] Valida
│   ├── analista.md             <- [Learning L3] Sintetiza
│   ├── orchestrator.md         <- [Dev L3] Coordena
│   ├── critic.md               <- [Dev L2] Revisa
│   ├── developer.md            <- [Dev L1] Implementa
│   ├── tester.md               <- [Dev L1] Testa
│   ├── researcher.md           <- [Dev L1] Pesquisa
│   ├── documenter.md           <- [Dev L1] Documenta
│   ├── founder.md              <- [Dev L2] Valida APIs
│   ├── api-specialist.md       <- [Dev L1] APIs externas
│   └── security-agent.md       <- [Dev L2] Seguranca
├── regras_globais/             <- regras que valem para TODOS os projetos
│   ├── regra_001_celery_tasks.md
│   ├── regra_002_code_duplication.md
│   ├── ... (12 regras aprendidas)
│   └── regra_012_python_jose_cve.md
├── kit_instalador/             <- kit portatil para instalar em novos projetos
│   ├── instalar.py             <- python instalar.py /caminho/do/projeto
│   ├── desinstalar.py          <- python desinstalar.py /caminho/do/projeto
│   ├── COMO_USAR.md
│   ├── engine.py
│   ├── loop_runner.py
│   └── db/schema.sql
├── projetos/                   <- registro e conhecimento por projeto
│   ├── msm_pro/config.json     <- MSM_Pro (ativo, 5 ciclos, 12 regras)
│   ├── whatsapp/config.json    <- WhatsApp (planejado)
│   ├── instagram/config.json   <- Instagram (planejado)
│   └── emails/config.json      <- Emails (planejado)
└── docs/                       <- documentacao global gerada pela IA
```

---

## REGRAS ABSOLUTAS

### REGRA #1 — IA Geral e ORQUESTRADORA, nao executora
A IA Geral **coordena e aprende**. Quem executa codigo sao os agentes dentro de cada projeto.
Aqui so ficam: regras, planos, analises, conhecimento cruzado.

### REGRA #2 — Regras globais valem para TODOS os projetos
Quando uma regra e promovida a global (confianca > 0.8, confirmada em 2+ projetos),
ela e copiada para `regras_globais/` e aplicada em todos os projetos futuros.

### REGRA #3 — Cada projeto tem sua instancia local
Cada projeto tem seu proprio `_auto_learning/` com banco SQLite local.
A IA Geral **sincroniza** regras entre projetos mas **nao apaga** dados locais.

### REGRA #4 — Instalar antes de orquestrar
Para adicionar um novo projeto:
1. `python kit_instalador/instalar.py /caminho/do/novo/projeto`
2. Registrar em `projetos/<nome>/config.json`
3. Copiar regras globais para o `_auto_learning/regras/` do projeto

---

## Projetos Registrados

| Projeto | Status | Auto-Learning | Ciclos | Regras |
|---------|--------|---------------|--------|--------|
| MSM_Pro | Ativo | Instalado | 5 | 12 |
| WhatsApp | Planejado | Nao | 0 | 0 |
| Instagram | Planejado | Nao | 0 | 0 |
| Emails | Planejado | Nao | 0 | 0 |

---

## Como funciona a orquestracao

```
IA_Geral (cerebro)
    |
    |-- Le regras_globais/
    |-- Le projetos/*/config.json
    |
    +-- Para cada projeto ATIVO:
    |     1. Verifica _auto_learning/ do projeto
    |     2. Coleta novas regras locais
    |     3. Se regra local tem confianca > 0.8:
    |         -> Promove para regras_globais/
    |         -> Distribui para outros projetos
    |     4. Se regra global falha em projeto especifico:
    |         -> Marca como nao-aplicavel naquele contexto
    |
    +-- A cada sincronizacao:
          1. Atualiza stats em projetos/*/config.json
          2. Gera relatorio cruzado em docs/
          3. Sugere novas direcoes para projetos parados
```

---

## 13 Agentes — Resumo

### Grupo Auto-Learning (4 agentes — loop infinito)
| Agente | Nivel | Funcao |
|--------|:-----:|--------|
| Curiosa | L1 | Gera perguntas sem parar |
| Respondedora | L1 | Pesquisa respostas no codigo e docs |
| Confrontadora | L2 | Valida cada resposta com 3 testes |
| Analista | L3 | Sintetiza tudo, gera planos e regras |

### Grupo Desenvolvimento (9 agentes — ativados por demanda)
| Agente | Nivel | Funcao |
|--------|:-----:|--------|
| Orchestrator | L3 | Coordenador central |
| Critic | L2 | Revisa todo codigo e decisoes |
| Security Agent | L2 | Auditoria de seguranca |
| Founder | L2 | Valida APIs com fontes oficiais |
| Developer | L1 | Implementa features e fixes |
| Tester | L1 | Roda testes, valida implementacoes |
| Researcher | L1 | Pesquisa solucoes e boas praticas |
| Documenter | L1 | Escreve e mantem documentacao |
| API Specialist | L1 | Integracoes com APIs externas |

---

## 12 Regras Globais Ativas

| # | Regra | Origem |
|---|-------|--------|
| 001 | Celery tasks devem ter try/except + logger.exception() | MSM_Pro ciclo 3 |
| 002 | Logica duplicada deve ser extraida para helpers | MSM_Pro ciclo 2 |
| 003 | Webhooks devem validar origem antes de processar | MSM_Pro ciclo 3 |
| 004 | Tokens ML devem ser encriptados com Fernet | MSM_Pro ciclo 4 |
| 005 | FK products->listings deve ser SET NULL, nao CASCADE | MSM_Pro ciclo 2 |
| 006 | react-query-devtools em devDependencies, nao dependencies | MSM_Pro ciclo 3 |
| 007 | Endpoints pagos devem ter rate limiting + cache | MSM_Pro ciclo 4 |
| 008 | Alertas devem ter deduplicacao de 24h | MSM_Pro ciclo 4 |
| 009 | Timestamps ML devem usar timezone BRT explicito | MSM_Pro ciclo 3 |
| 010 | Docker containers devem rodar como non-root | MSM_Pro ciclo 5 |
| 011 | Respostas HTTP devem ter security headers | MSM_Pro ciclo 5 |
| 012 | python-jose==3.3.0 tem CVE — substituir por PyJWT>=2.8.0 | MSM_Pro ciclo 5 |

---

## Comandos

```bash
# Ver status global
python IA_Geral_Processos_Dados/loop_runner.py status

# Instalar auto-learning em novo projeto
python IA_Geral_Processos_Dados/kit_instalador/instalar.py /caminho/projeto

# Desinstalar de um projeto
python IA_Geral_Processos_Dados/kit_instalador/desinstalar.py /caminho/projeto

# Exportar dados globais
python IA_Geral_Processos_Dados/loop_runner.py export
```

---

## Proximos Passos

1. [ ] Iniciar auto-learning no projeto WhatsApp
2. [ ] Iniciar auto-learning no projeto Instagram
3. [ ] Iniciar auto-learning no projeto Emails
4. [ ] Criar sincronizador automatico de regras entre projetos
5. [ ] Dashboard central para ver status de todos os projetos
6. [ ] Criar agente orquestrador cross-project
