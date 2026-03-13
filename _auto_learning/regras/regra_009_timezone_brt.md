# Regra #9: Timestamps ML Devem Usar Timezone Explicito
Fonte: Ciclo 5 — UTC offset bug
Confianca: 95%
Status: ATIVA

## Regra
NAO hardcodar offset `-03:00` em strings de timestamp.
Usar `datetime.now(tz.utc).astimezone(BRT)` OU `+00:00` (UTC puro).
