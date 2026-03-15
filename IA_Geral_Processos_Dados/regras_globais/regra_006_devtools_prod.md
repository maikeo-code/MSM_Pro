# Regra #6: DevTools em devDependencies
Fonte: Ciclo 4 — Frontend Audit
Confianca: 99%
Status: ATIVA

## Regra
react-query-devtools e qualquer ferramenta de debug DEVE estar em devDependencies.
Renderizar apenas dentro de `if (import.meta.env.DEV)`.
