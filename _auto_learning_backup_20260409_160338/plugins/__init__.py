"""
SWARM GENESIS v8 — plugins não-destrutivos.

Cada plugin é um módulo auto-contido que:
- Define suas próprias tabelas via CREATE TABLE IF NOT EXISTS (idempotente)
- Expõe uma função init_schema(conn) aplicada sob demanda
- Não modifica engine.py nem schema.sql do core
- É totalmente opcional; nada quebra se o plugin nunca for importado

Plugins:
- ekas_efficiency       Budget cap + usage log + cache_control helper
- tiered_autonomy       L0-L4 + circuit breakers + audit hash encadeado
- memory_procedural     Skills versionadas (camada procedural)
- self_model            Relatório semanal de auto-avaliação
- daily_consolidator    Consolidação diária heurística (Jaccard)
- functional_emotions   boredom/curiosity/fear em agentes
- question_dedup        Descarta perguntas similares por Jaccard
"""

__version__ = "8.0.0"
