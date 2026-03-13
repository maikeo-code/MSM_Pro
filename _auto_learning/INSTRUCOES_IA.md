# INSTRUÇÕES PARA A IA — Sistema de Auto-Aprendizado
# =====================================================
# Este arquivo explica ao Claude Code como operar o sistema.
# Leia COMPLETAMENTE antes de executar qualquer coisa.
# =====================================================

## CONTEXTO
- **Projeto**: MSM_Pro
- **Tech Stack**: Railway
- **Pasta do sistema**: _auto_learning/
- **Banco de dados**: _auto_learning/db/learning.db

## REGRA #1 — NÃO TOQUE NO CÓDIGO DO PROJETO
Você pode LER qualquer arquivo do projeto para analisar.
Você NÃO pode EDITAR nenhum arquivo fora de `_auto_learning/`.
Toda saída (planos, docs, análises) vai para `_auto_learning/`.

## COMO INTERAGIR COM O BANCO DE DADOS

Todos os comandos usam `loop_runner.py` dentro de `_auto_learning/`:

```bash
# Iniciar um ciclo
python _auto_learning/loop_runner.py start-cycle

# Ver contexto atual (sucessos, falhas, perguntas pendentes, regras)
python _auto_learning/loop_runner.py get-context

# Registrar feedback
python _auto_learning/loop_runner.py register-feedback '{"source":"user","topic":"tema","question":"pergunta","answer":"resposta","sentiment":"positivo"}'

# Registrar sucesso
python _auto_learning/loop_runner.py register-success '{"feedback_id":1,"topic":"tema","insight":"o que deu certo","evidence":"prova"}'

# Registrar falha
python _auto_learning/loop_runner.py register-failure '{"feedback_id":1,"topic":"tema","what_failed":"o que falhou","why_failed":"motivo"}'

# Salvar pergunta gerada
python _auto_learning/loop_runner.py save-question '{"question":"pergunta","category":"exploratoria","cycle_id":1}'

# Responder pergunta
python _auto_learning/loop_runner.py answer-question '{"question_id":1,"answer":"resposta","was_relevant":true}'

# Registrar consenso entre IAs
python _auto_learning/loop_runner.py register-consensus '{"topic":"tema","agents":["curiosa","confrontadora"],"positions":{},"verdict":"decisão","agreement":0.8,"reasoning":"motivo"}'

# Criar regra aprendida
python _auto_learning/loop_runner.py create-rule '{"rule_text":"regra","source":"consenso","confidence":0.7}'

# Ver status
python _auto_learning/loop_runner.py status

# Exportar tudo em JSON
python _auto_learning/loop_runner.py export

# Encerrar ciclo
python _auto_learning/loop_runner.py end-cycle '{"cycle_id":1,"summary":"resumo"}'
```

## O LOOP INFINITO

Quando o usuário pedir para iniciar o loop, siga este ciclo:

```
INICIALIZAÇÃO:
  python _auto_learning/loop_runner.py start-cycle
  → Salva o cycle_id retornado

LOOP (repete até Ctrl+C ou "pare"):

  FASE 1 — CURIOSA PERGUNTA
    - Rode: python _auto_learning/loop_runner.py get-context
    - Leia código/docs do projeto (read-only) para entender contexto
    - Gere 3-5 perguntas sobre o projeto
    - Registre cada uma: python _auto_learning/loop_runner.py save-question '...'

  FASE 2 — RESPONDEDORA RESPONDE
    - Para cada pergunta, busque resposta no código, docs e banco
    - Registre: python _auto_learning/loop_runner.py answer-question '...'
    - Registre como feedback: python _auto_learning/loop_runner.py register-feedback '...'

  FASE 3 — CONFRONTADORA VALIDA
    - Para cada resposta, aplique 3 testes:
      a) CONSISTÊNCIA: contradiz algo confirmado?
      b) EVIDÊNCIA: tem dados que suportam?
      c) APLICABILIDADE: funciona no projeto?
    - Se APROVADO: python _auto_learning/loop_runner.py register-success '...'
    - Se REJEITADO: python _auto_learning/loop_runner.py register-failure '...'
      → Gere nova pergunta derivada e volte para FASE 1

  FASE 4 — ANALISTA SINTETIZA (a cada 5 ciclos)
    - Rode: python _auto_learning/loop_runner.py get-context
    - Cruze sucessos vs falhas por tema
    - Se padrão aparece 3+ vezes com score > 0.7:
      → python _auto_learning/loop_runner.py create-rule '...'
    - Gere relatório em: _auto_learning/docs/analises/ciclo_N.md
    - Se identificar melhoria concreta, gere plano em: _auto_learning/planos/

  FASE 5 — FEEDBACK DO USUÁRIO
    - Se o usuário deu feedback:
      1. Registre o feedback original
      2. Confronte (Fase 3) o feedback
      3. Registre resultado do confronto
      4. Gere perguntas derivadas do feedback
      5. Continue o loop

  FIM DO CICLO → Incrementa → Volta para FASE 1
```

## ONDE SALVAR CADA TIPO DE SAÍDA

| Tipo | Local | Exemplo |
|------|-------|---------|
| Planos de melhoria | `_auto_learning/planos/` | `plano_otimizar_api.md` |
| Planos aprovados | `_auto_learning/planos/aprovados/` | Movidos após aprovação |
| Planos rejeitados | `_auto_learning/planos/rejeitados/` | Movidos após rejeição |
| Análises periódicas | `_auto_learning/docs/analises/` | `ciclo_5_analise.md` |
| Documentação gerada | `_auto_learning/docs/` | `arquitetura_projeto.md` |
| Regras aprendidas | `_auto_learning/regras/` | `regra_001_cache.md` |
| Regras deprecadas | `_auto_learning/regras/deprecadas/` | Movidas quando falham |
| Exports | `_auto_learning/exports/` | `export_20260312.json` |
| Logs | `_auto_learning/logs/` | `ciclo_1.log` |

## STATUS (mostrar a cada ciclo)

```
══════ CICLO #N ══════════════════════════════
  Perguntas:  X geradas | Y respondidas | Z relevantes
  Sucessos:   X total   | +Y neste ciclo
  Falhas:     X total   | Y não resolvidas
  Regras:     X ativas  | Y deprecadas
  Confrontos: X aprovados | Y rejeitados
  Planos:     X gerados | Y aprovados
══════════════════════════════════════════════
```

## FORMATO DE PLANO

Quando a Analista identificar uma melhoria, crie um arquivo em `_auto_learning/planos/`:

```markdown
# Plano: [Título Descritivo]
Data: YYYY-MM-DD
Baseado em: [IDs dos sucessos/falhas/consensos que motivaram]
Prioridade: P0|P1|P2|P3

## Problema Identificado
[Descrição clara do problema encontrado no projeto]

## Solução Proposta
[Passos detalhados do que fazer - sem executar]

## Arquivos Afetados
[Lista de arquivos do projeto que seriam modificados]

## Riscos
[O que pode dar errado]

## Métricas de Sucesso
[Como saber se funcionou]

## Status: PENDENTE
```