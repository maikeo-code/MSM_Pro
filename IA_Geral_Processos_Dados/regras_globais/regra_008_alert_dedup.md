# Regra #8: Alertas Devem Ter Deduplicacao
Fonte: Ciclo 5 — Alertas spam
Confianca: 97%
Status: ATIVA

## Regra
AlertConfig DEVE ter campo cooldown_hours (default 24) e last_triggered_at.
Antes de disparar alerta, verificar se cooldown expirou.
