---
description: Mostra o sprint atual com tarefas pendentes e concluídas do MSM_Pro
allowed-tools: [Read, Grep]
---

# Sprint Status — MSM_Pro

Leia o arquivo `CLAUDE.md` na raiz do projeto e extraia a seção de Sprints.

Exiba de forma clara e organizada:

1. **Sprint atual** — qual sprint está em andamento (o primeiro com tarefas `[ ]` pendentes)
2. **Tarefas concluídas** `[x]` do sprint atual
3. **Tarefas pendentes** `[ ]` do sprint atual com destaque
4. **Próximos sprints** — apenas o título de cada sprint futuro

Formato de saída:
```
## Sprint X — [Nome] (EM ANDAMENTO)

✅ Concluído:
  - tarefa 1
  - tarefa 2

⏳ Pendente:
  - tarefa 3   ← próxima
  - tarefa 4

📅 Próximos:
  - Sprint X+1 — [Nome]
  - Sprint X+2 — [Nome]
```

Se todos os sprints estiverem concluídos, informe isso e sugira o que pode ser o próximo passo.
