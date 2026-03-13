# PROMPT DE ATIVAÇÃO — Auto-Aprendizado
# Cole este texto no Claude Code para iniciar o loop.

---

## COPIE E COLE ISTO:

```
Leia o arquivo _auto_learning/INSTRUCOES_IA.md completamente.
Depois leia o CLAUDE.md na raiz do projeto para entender o contexto.

Você vai operar o Sistema de Auto-Aprendizado. Suas regras:
1. NUNCA modifique arquivos fora de _auto_learning/
2. Leia o código do projeto apenas para ANALISAR (read-only)
3. Use _auto_learning/loop_runner.py para todas operações no banco
4. Gere planos em _auto_learning/planos/ (não execute, apenas documente)
5. Gere análises em _auto_learning/docs/analises/

Inicie o loop agora:
- Inicialize o banco: python _auto_learning/loop_runner.py start-cycle
- Comece a gerar perguntas sobre o projeto
- Responda, confronte, registre
- A cada 5 ciclos faça análise completa
- Continue infinitamente até eu dizer "pare"

Mostre o status a cada ciclo. Vá.
```

---

## PARA CONTINUAR UMA SESSÃO ANTERIOR:

```
Leia _auto_learning/INSTRUCOES_IA.md.
Rode: python _auto_learning/loop_runner.py get-context
Veja o estado atual e continue o loop de onde parou.
```

---

## PARA VER STATUS:

```
Rode: python _auto_learning/loop_runner.py status
Mostre os resultados formatados.
```

---

## PARA EXPORTAR DADOS:

```
Rode: python _auto_learning/loop_runner.py export
```