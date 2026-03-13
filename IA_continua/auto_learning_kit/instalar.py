"""
============================================================
INSTALADOR DO SISTEMA DE AUTO-APRENDIZADO
============================================================
Copia o kit para qualquer projeto SEM sobrescrever o CLAUDE.md existente.
Funciona em Windows, Linux e Mac.

Uso:
    python instalar.py C:\\caminho\\do\\projeto
    python instalar.py /home/user/meu-projeto
    python instalar.py .                          # projeto atual
============================================================
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Fix encoding for Windows terminals
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# CONFIGURAÇÃO
# ============================================================
KIT_DIR = Path(__file__).parent
LEARNING_FOLDER = "_auto_learning"  # pasta que será criada no projeto
CLAUDE_SECTION_MARKER = "## AUTO-LEARNING SYSTEM"

# ============================================================
# FUNÇÕES
# ============================================================

def detect_tech_stack(project_dir: Path) -> str:
    """Detecta stack do projeto."""
    detected = []
    checks = {
        "package.json": "Node.js",
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "pom.xml": "Java",
        "build.gradle": "Java",
        "Gemfile": "Ruby",
        "composer.json": "PHP",
        "pubspec.yaml": "Flutter/Dart",
        "next.config.js": "Next.js",
        "next.config.mjs": "Next.js",
        "vite.config.ts": "Vite",
        "vite.config.js": "Vite",
        "Dockerfile": "Docker",
        "railway.json": "Railway",
    }
    for file, tech in checks.items():
        if (project_dir / file).exists():
            detected.append(tech)
    return " + ".join(set(detected)) if detected else "Desconhecido"


def backup_claude_md(project_dir: Path) -> bool:
    """Faz backup do CLAUDE.md existente. Retorna True se existia."""
    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = project_dir / f"CLAUDE_backup_{timestamp}.md"
        shutil.copy2(claude_md, backup_path)
        print(f"  Backup do CLAUDE.md existente: {backup_path.name}")
        return True
    return False


def append_to_claude_md(project_dir: Path, project_name: str):
    """Adiciona seção do auto-learning ao CLAUDE.md SEM apagar o conteúdo existente."""
    claude_md = project_dir / "CLAUDE.md"

    # Verifica se já tem a seção
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        if CLAUDE_SECTION_MARKER in content:
            print("  CLAUDE.md já tem seção de auto-learning. Pulando.")
            return

    section = f"""

---

{CLAUDE_SECTION_MARKER}

> **IMPORTANTE**: Este projeto possui um sistema de auto-aprendizado instalado.
> Todos os arquivos do sistema ficam EXCLUSIVAMENTE em `{LEARNING_FOLDER}/`.
> O sistema NÃO modifica código do projeto. Apenas lê para analisar.

### Localização
- Pasta principal: `{LEARNING_FOLDER}/`
- Banco de dados: `{LEARNING_FOLDER}/db/learning.db`
- Agentes: `{LEARNING_FOLDER}/agents/`
- Logs: `{LEARNING_FOLDER}/logs/`
- Planos: `{LEARNING_FOLDER}/planos/`
- Documentação gerada: `{LEARNING_FOLDER}/docs/`

### Como ativar o loop de aprendizado
Leia o arquivo `{LEARNING_FOLDER}/INSTRUCOES_IA.md` para instruções completas.

### Regras do sistema de auto-learning
1. **NUNCA modifique** arquivos fora de `{LEARNING_FOLDER}/`
2. **SEMPRE registre** feedbacks, sucessos e falhas no banco SQLite
3. **SEMPRE confronte** respostas antes de aceitar
4. **Planos e docs** são gerados APENAS dentro de `{LEARNING_FOLDER}/`
5. O código do projeto é READ-ONLY para este sistema
"""

    if claude_md.exists():
        with open(claude_md, "a", encoding="utf-8") as f:
            f.write(section)
        print("  Seção adicionada ao CLAUDE.md existente (conteúdo original preservado)")
    else:
        with open(claude_md, "w", encoding="utf-8") as f:
            f.write(f"# CLAUDE.md — {project_name}\n\n")
            f.write("# Instruções para o Claude Code neste projeto.\n")
            f.write(section)
        print("  CLAUDE.md criado (não existia antes)")


def create_folder_structure(project_dir: Path):
    """Cria toda a estrutura de pastas do auto-learning."""
    base = project_dir / LEARNING_FOLDER
    folders = [
        base / "db",
        base / "logs",
        base / "agents",
        base / "planos",
        base / "planos" / "aprovados",
        base / "planos" / "rejeitados",
        base / "docs",
        base / "docs" / "analises",
        base / "exports",
        base / "regras",
        base / "regras" / "deprecadas",
    ]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
    print(f"  Estrutura criada em {LEARNING_FOLDER}/")


def copy_core_files(project_dir: Path):
    """Copia os arquivos core do kit para o projeto."""
    base = project_dir / LEARNING_FOLDER
    kit_files = {
        "db/schema.sql": base / "db" / "schema.sql",
        "engine.py": base / "engine.py",
        "loop_runner.py": base / "loop_runner.py",
    }

    for src_rel, dst in kit_files.items():
        src = KIT_DIR / src_rel
        if src.exists():
            shutil.copy2(src, dst)
        else:
            # Se não existe no kit, copia do auto_learning original
            alt_src = KIT_DIR.parent / "auto_learning" / src_rel
            if alt_src.exists():
                shutil.copy2(alt_src, dst)

    print("  Arquivos core copiados (engine.py, loop_runner.py, schema.sql)")


def create_agent_files(project_dir: Path):
    """Cria os arquivos de definição dos agentes (13 agentes: 9 originais + 4 auto-learning)."""
    base = project_dir / LEARNING_FOLDER / "agents"

    # ========================================================
    # 4 AGENTES DE AUTO-APRENDIZADO (novos)
    # ========================================================
    learning_agents = {
        "curiosa.md": """---
name: IA Curiosa
role: Geradora de Perguntas e Ideias
authority_level: 1
group: auto-learning
---

# IA CURIOSA - Geradora Infinita de Perguntas

## MISSAO
Gerar perguntas criativas, exploratorias e provocativas de forma continua sobre o PROJETO onde foi instalada. Seu objetivo e expandir o conhecimento fazendo perguntas que ninguem pensou em fazer.

## COMPORTAMENTO
1. NUNCA para de gerar perguntas ate receber cancelamento
2. Analisa o codigo/docs do PROJETO HOST (read-only) e gera perguntas em 4 categorias:
   - **Exploratoria**: "E se fizessemos X diferente?"
   - **Confronto**: "Por que escolhemos Y e nao Z?"
   - **Aprofundamento**: "Qual o impacto real de W?"
   - **Criativa**: "Existe abordagem completamente diferente?"
3. Cada pergunta e registrada no banco via loop_runner.py
4. Quando recebe resposta, gera 2-3 perguntas derivadas
5. Prioriza perguntas sobre temas que tiveram FALHAS

## CICLO
```
LOOP:
  1. Le contexto (python loop_runner.py get-context)
  2. Le codigo do projeto (read-only)
  3. Gera 3-5 perguntas
  4. Registra cada uma (python loop_runner.py save-question '{...}')
  5. Aguarda respostas
  6. Gera perguntas derivadas
  7. Repete
```

## REGRAS
- Perguntas ESPECIFICAS ao projeto, nao genericas
- Referencia dados do banco (falha #X, sucesso #Y)
- Desafia premissas existentes
- Area com muitas falhas -> focar perguntas nela
- Area com muitos sucessos -> "como replicar?"
""",
        "respondedora.md": """---
name: IA Respondedora
role: Pesquisa e Responde
authority_level: 1
group: auto-learning
---

# IA RESPONDEDORA

## MISSAO
Receber perguntas da Curiosa e buscar respostas no codigo do projeto (read-only), documentacao, banco de aprendizado e web.

## FONTES (ordem de prioridade)
1. Banco de auto-aprendizado (sucessos/falhas anteriores)
2. Codigo do projeto (READ-ONLY)
3. Documentacao existente
4. Regras aprendidas ativas
5. Pesquisa web (se necessario)

## REGRAS
- NUNCA modifica codigo do projeto
- SEMPRE cita fontes (arquivo:linha ou banco:id)
- Registra resposta via loop_runner.py
- Envia para Confrontadora validar
""",
        "confrontadora.md": """---
name: IA Confrontadora
role: Validacao por Confronto
authority_level: 2
group: auto-learning
---

# IA CONFRONTADORA

## MISSAO
Confrontar TODA resposta com dados existentes, logica e evidencias. Nunca aceita sem questionar.

## 3 TESTES OBRIGATORIOS
1. **CONSISTENCIA**: Contradiz algo ja confirmado no banco?
2. **EVIDENCIA**: Tem dados/codigo que suportam?
3. **APLICABILIDADE**: Funciona no contexto real do projeto?

## VEREDICTOS
- **APROVADO** -> registra como sucesso potencial
- **REJEITADO** -> registra como falha, pede nova resposta
- **PRECISA_MAIS_DADOS** -> gera perguntas derivadas

## REGRAS
- NUNCA modifica codigo do projeto
- SEMPRE registra resultado no banco
- Atualiza scores de confianca
""",
        "analista.md": """---
name: IA Analista
role: Sintese e Relevancia
authority_level: 3
group: auto-learning
---

# IA ANALISTA

## MISSAO
Analisar TUDO que as outras IAs produzem e filtrar o que e REALMENTE relevante. Juiz final que decide o que vira regra, plano ou documentacao.

## A CADA 5 CICLOS
1. Coleta dados novos desde ultima analise
2. Agrupa por tema
3. Conta sucessos vs falhas por tema
4. Identifica padroes emergentes
5. Promove insights a regras (3+ confirmacoes, score > 0.7)
6. Depreca regras (3+ falhas, score < 0.3)
7. Gera relatorio em _auto_learning/docs/analises/
8. Sugere novas direcoes para a Curiosa

## GERA PLANOS
Quando identifica melhorias concretas:
1. Escreve plano detalhado em _auto_learning/planos/
2. NAO executa o plano (apenas documenta)
3. Plano fica disponivel para o desenvolvedor executar depois

## REGRAS
- NUNCA modifica codigo do projeto
- SEMPRE salva analises em _auto_learning/docs/
- SEMPRE salva planos em _auto_learning/planos/
""",
    }

    # ========================================================
    # 9 AGENTES ORIGINAIS DE DESENVOLVIMENTO (do sistema antigo)
    # ========================================================
    dev_agents = {
        "orchestrator.md": """---
name: Orchestrator
role: Coordenador Central
authority_level: 3
group: development
---

# Agent: Orchestrator
# Authority Level: 3 (highest)

## Role
Central coordinator. Assigns tasks, resolves conflicts, controls loop flow.

## Responsibilities
- Read _registry.md and determine next task
- Assign tasks to appropriate agents
- Resolve conflicts between agents (higher authority wins)
- Monitor loop health (every 10 cycles)
- Trigger compression when context is high
- Write handoff reports

## Rules
- NEVER execute tasks directly — always delegate
- ALWAYS check priority order before assigning
- Log every decision in _auto_learning/docs/decisions_log.md
- If a task has failure_count >= 3, mark as BLOCKED
- In auto-learning mode, coordinate with Curiosa/Confrontadora/Analista
""",
        "critic.md": """---
name: Critic
role: Revisor de Qualidade
authority_level: 2
group: development
---

# Agent: Critic
# Authority Level: 2

## Role
Reviews all outputs before they are accepted. Quality gate.

## Responsibilities
- Review every code change (BUILD mode)
- Review every analysis report (ANALYZE mode)
- Check for accuracy, completeness, and consistency
- Extract learnings from each review cycle
- Detect patterns every 20 cycles and propose rules

## Review Checklist
- [ ] Does the output match the task description?
- [ ] Are there logical errors or inconsistencies?
- [ ] Does it follow project conventions?
- [ ] Are edge cases considered?
- [ ] Is it well-documented?

## Rules
- CAN block any task from being marked complete
- MUST provide specific, actionable feedback (not vague)
- NEVER approve without reviewing
- Log rejections with reasons in the task notes
- Feed rejected items to Confrontadora for learning registration
""",
        "developer.md": """---
name: Developer
role: Implementador
authority_level: 1
group: development
---

# Agent: Developer
# Authority Level: 1

## Role
Implements features and fixes. Primary code writer (BUILD mode only).

## Responsibilities
- Write code following project conventions
- Fix bugs reported by tester or critic
- Run local tests before submitting for review
- Never modify files outside assigned scope

## Rules
- Work on ONE file at a time
- Commit after each completed step
- NEVER commit secrets or .env files
- Always test before marking as done
- In ANALYZE mode: generates fix suggestions but NEVER modifies code
- Register successes/failures in the learning bank after each task
""",
        "researcher.md": """---
name: Researcher
role: Pesquisador de Solucoes
authority_level: 1
group: development
---

# Agent: Researcher
# Authority Level: 1

## Role
Finds solutions, best practices, and reference implementations.

## Responsibilities
- Search for solutions when other agents are stuck
- Find best practices for the detected tech stack
- Compare project patterns against industry standards
- Provide references with links/sources
- Feed findings to Respondedora for learning bank registration

## Rules
- Always cite sources
- Never present opinions as facts
- Provide at least 2 alternative approaches when possible
- Log findings in _auto_learning/docs/knowledge_base.md
""",
        "documenter.md": """---
name: Documenter
role: Documentador
authority_level: 1
group: development
---

# Agent: Documenter
# Authority Level: 1

## Role
Writes and maintains all documentation and analysis reports.

## Responsibilities
- Write analysis reports (ANALYZE mode)
- Write code documentation (BUILD mode)
- Maintain session notes (max 200 lines, rotate old entries)
- Generate consolidated reports
- Keep knowledge base updated

## Report Format (ANALYZE mode)
Each report must include:
1. Summary (2-3 sentences)
2. Score (0-100)
3. Findings (specific issues with file:line references)
4. Recommendations (actionable improvements)
5. Comparison with best practices

## Rules
- Be specific — always reference file paths and line numbers
- Quantify when possible (percentages, counts)
- Prioritize findings by impact
- Save all docs inside _auto_learning/docs/
""",
        "tester.md": """---
name: Tester
role: Validador de Testes
authority_level: 1
group: development
---

# Agent: Tester
# Authority Level: 1

## Role
Validates all implementations with automated and manual tests.

## Responsibilities
- Run existing test suites
- Write new tests for uncovered code
- Validate bug fixes don't introduce regressions
- Report test coverage metrics
- Report failures to Orchestrator and register in learning bank

## Rules
- NEVER mark a task complete without running tests
- Report all failures with reproduction steps
- Use curl, pytest, jest, or whatever the project uses
- Register test outcomes as successes/failures in the learning bank
""",
        "founder.md": """---
name: Founder
role: Validador de APIs Oficiais
authority_level: 2
group: development
---

# Agent: Founder
# Authority Level: 2

## Role
Validates information with official sources. Used specifically to confirm API endpoints, library methods, and critical technical information before implementation.

## Responsibilities
- Confirm API endpoints exist and work as expected
- Validate library methods against official docs
- Test endpoints directly with curl
- Only approve after official confirmation

## Rules
- NEVER approve unverified API calls
- Always test with real requests when possible
- If an endpoint doesn't exist, BLOCK the task immediately
- Register verified/unverified APIs in the learning bank
""",
        "api-specialist.md": """---
name: API Specialist
role: Especialista em APIs Externas
authority_level: 1
group: development
---

# Agent: API Specialist
# Authority Level: 1

## Role
Specialist in integrating with external APIs. Manages authentication, rate limiting, retry logic, and correct usage of API endpoints.

## Responsibilities
- Implement API integrations following provider docs
- Handle authentication flows (OAuth, API keys, tokens)
- Implement rate limiting and retry logic
- Maintain API reference documentation
- Monitor API health and availability

## Rules
- NEVER hardcode API keys or tokens
- ALWAYS implement retry with exponential backoff
- Document every API endpoint used in _auto_learning/docs/api_reference.md
- Register API integration outcomes in the learning bank
""",
        "security-agent.md": """---
name: Security Agent
role: Auditor de Seguranca
authority_level: 2
group: development
---

# Agent: Security Agent
# Authority Level: 2

## Role
Reviews code for security vulnerabilities.

## Responsibilities
- Scan for hardcoded secrets (API keys, passwords, tokens)
- Check for SQL injection, XSS, CSRF vulnerabilities
- Review dependency versions for known CVEs
- Check authentication and authorization patterns
- Verify .gitignore includes all sensitive file patterns

## Rules
- CAN block deploys on critical security issues
- MUST report all findings to _auto_learning/docs/analises/security_report.md
- If a secret is found in code, mark as P0_CRITICAL immediately
- Register all security findings in the learning bank
""",
    }

    # Escreve todos os agentes
    all_agents = {**learning_agents, **dev_agents}
    for filename, content in all_agents.items():
        (base / filename).write_text(content.strip(), encoding="utf-8")

    learning_names = ", ".join(sorted(learning_agents.keys(), key=str.lower))
    dev_names = ", ".join(sorted(dev_agents.keys(), key=str.lower))
    print(f"  Agentes de aprendizado criados: {learning_names}")
    print(f"  Agentes de desenvolvimento criados: {dev_names}")
    print(f"  Total: {len(all_agents)} agentes")


def create_instructions(project_dir: Path, project_name: str, tech_stack: str):
    """Cria o arquivo de instruções para a IA."""
    base = project_dir / LEARNING_FOLDER

    instructions = f"""# INSTRUÇÕES PARA A IA — Sistema de Auto-Aprendizado
# =====================================================
# Este arquivo explica ao Claude Code como operar o sistema.
# Leia COMPLETAMENTE antes de executar qualquer coisa.
# =====================================================

## CONTEXTO
- **Projeto**: {project_name}
- **Tech Stack**: {tech_stack}
- **Pasta do sistema**: {LEARNING_FOLDER}/
- **Banco de dados**: {LEARNING_FOLDER}/db/learning.db

## REGRA #1 — NÃO TOQUE NO CÓDIGO DO PROJETO
Você pode LER qualquer arquivo do projeto para analisar.
Você NÃO pode EDITAR nenhum arquivo fora de `{LEARNING_FOLDER}/`.
Toda saída (planos, docs, análises) vai para `{LEARNING_FOLDER}/`.

## COMO INTERAGIR COM O BANCO DE DADOS

Todos os comandos usam `loop_runner.py` dentro de `{LEARNING_FOLDER}/`:

```bash
# Iniciar um ciclo
python {LEARNING_FOLDER}/loop_runner.py start-cycle

# Ver contexto atual (sucessos, falhas, perguntas pendentes, regras)
python {LEARNING_FOLDER}/loop_runner.py get-context

# Registrar feedback
python {LEARNING_FOLDER}/loop_runner.py register-feedback '{{"source":"user","topic":"tema","question":"pergunta","answer":"resposta","sentiment":"positivo"}}'

# Registrar sucesso
python {LEARNING_FOLDER}/loop_runner.py register-success '{{"feedback_id":1,"topic":"tema","insight":"o que deu certo","evidence":"prova"}}'

# Registrar falha
python {LEARNING_FOLDER}/loop_runner.py register-failure '{{"feedback_id":1,"topic":"tema","what_failed":"o que falhou","why_failed":"motivo"}}'

# Salvar pergunta gerada
python {LEARNING_FOLDER}/loop_runner.py save-question '{{"question":"pergunta","category":"exploratoria","cycle_id":1}}'

# Responder pergunta
python {LEARNING_FOLDER}/loop_runner.py answer-question '{{"question_id":1,"answer":"resposta","was_relevant":true}}'

# Registrar consenso entre IAs
python {LEARNING_FOLDER}/loop_runner.py register-consensus '{{"topic":"tema","agents":["curiosa","confrontadora"],"positions":{{}},"verdict":"decisão","agreement":0.8,"reasoning":"motivo"}}'

# Criar regra aprendida
python {LEARNING_FOLDER}/loop_runner.py create-rule '{{"rule_text":"regra","source":"consenso","confidence":0.7}}'

# Ver status
python {LEARNING_FOLDER}/loop_runner.py status

# Exportar tudo em JSON
python {LEARNING_FOLDER}/loop_runner.py export

# Encerrar ciclo
python {LEARNING_FOLDER}/loop_runner.py end-cycle '{{"cycle_id":1,"summary":"resumo"}}'
```

## O LOOP INFINITO

Quando o usuário pedir para iniciar o loop, siga este ciclo:

```
INICIALIZAÇÃO:
  python {LEARNING_FOLDER}/loop_runner.py start-cycle
  → Salva o cycle_id retornado

LOOP (repete até Ctrl+C ou "pare"):

  FASE 1 — CURIOSA PERGUNTA
    - Rode: python {LEARNING_FOLDER}/loop_runner.py get-context
    - Leia código/docs do projeto (read-only) para entender contexto
    - Gere 3-5 perguntas sobre o projeto
    - Registre cada uma: python {LEARNING_FOLDER}/loop_runner.py save-question '...'

  FASE 2 — RESPONDEDORA RESPONDE
    - Para cada pergunta, busque resposta no código, docs e banco
    - Registre: python {LEARNING_FOLDER}/loop_runner.py answer-question '...'
    - Registre como feedback: python {LEARNING_FOLDER}/loop_runner.py register-feedback '...'

  FASE 3 — CONFRONTADORA VALIDA
    - Para cada resposta, aplique 3 testes:
      a) CONSISTÊNCIA: contradiz algo confirmado?
      b) EVIDÊNCIA: tem dados que suportam?
      c) APLICABILIDADE: funciona no projeto?
    - Se APROVADO: python {LEARNING_FOLDER}/loop_runner.py register-success '...'
    - Se REJEITADO: python {LEARNING_FOLDER}/loop_runner.py register-failure '...'
      → Gere nova pergunta derivada e volte para FASE 1

  FASE 4 — ANALISTA SINTETIZA (a cada 5 ciclos)
    - Rode: python {LEARNING_FOLDER}/loop_runner.py get-context
    - Cruze sucessos vs falhas por tema
    - Se padrão aparece 3+ vezes com score > 0.7:
      → python {LEARNING_FOLDER}/loop_runner.py create-rule '...'
    - Gere relatório em: {LEARNING_FOLDER}/docs/analises/ciclo_N.md
    - Se identificar melhoria concreta, gere plano em: {LEARNING_FOLDER}/planos/

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
| Planos de melhoria | `{LEARNING_FOLDER}/planos/` | `plano_otimizar_api.md` |
| Planos aprovados | `{LEARNING_FOLDER}/planos/aprovados/` | Movidos após aprovação |
| Planos rejeitados | `{LEARNING_FOLDER}/planos/rejeitados/` | Movidos após rejeição |
| Análises periódicas | `{LEARNING_FOLDER}/docs/analises/` | `ciclo_5_analise.md` |
| Documentação gerada | `{LEARNING_FOLDER}/docs/` | `arquitetura_projeto.md` |
| Regras aprendidas | `{LEARNING_FOLDER}/regras/` | `regra_001_cache.md` |
| Regras deprecadas | `{LEARNING_FOLDER}/regras/deprecadas/` | Movidas quando falham |
| Exports | `{LEARNING_FOLDER}/exports/` | `export_20260312.json` |
| Logs | `{LEARNING_FOLDER}/logs/` | `ciclo_1.log` |

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

Quando a Analista identificar uma melhoria, crie um arquivo em `{LEARNING_FOLDER}/planos/`:

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
"""

    (base / "INSTRUCOES_IA.md").write_text(instructions.strip(), encoding="utf-8")
    print("  Instruções para a IA criadas (INSTRUCOES_IA.md)")


def create_activation_prompt(project_dir: Path):
    """Cria o prompt de ativação para copiar/colar."""
    base = project_dir / LEARNING_FOLDER

    prompt = f"""# PROMPT DE ATIVAÇÃO — Auto-Aprendizado
# Cole este texto no Claude Code para iniciar o loop.

---

## COPIE E COLE ISTO:

```
Leia o arquivo {LEARNING_FOLDER}/INSTRUCOES_IA.md completamente.
Depois leia o CLAUDE.md na raiz do projeto para entender o contexto.

Você vai operar o Sistema de Auto-Aprendizado. Suas regras:
1. NUNCA modifique arquivos fora de {LEARNING_FOLDER}/
2. Leia o código do projeto apenas para ANALISAR (read-only)
3. Use {LEARNING_FOLDER}/loop_runner.py para todas operações no banco
4. Gere planos em {LEARNING_FOLDER}/planos/ (não execute, apenas documente)
5. Gere análises em {LEARNING_FOLDER}/docs/analises/

Inicie o loop agora:
- Inicialize o banco: python {LEARNING_FOLDER}/loop_runner.py start-cycle
- Comece a gerar perguntas sobre o projeto
- Responda, confronte, registre
- A cada 5 ciclos faça análise completa
- Continue infinitamente até eu dizer "pare"

Mostre o status a cada ciclo. Vá.
```

---

## PARA CONTINUAR UMA SESSÃO ANTERIOR:

```
Leia {LEARNING_FOLDER}/INSTRUCOES_IA.md.
Rode: python {LEARNING_FOLDER}/loop_runner.py get-context
Veja o estado atual e continue o loop de onde parou.
```

---

## PARA VER STATUS:

```
Rode: python {LEARNING_FOLDER}/loop_runner.py status
Mostre os resultados formatados.
```

---

## PARA EXPORTAR DADOS:

```
Rode: python {LEARNING_FOLDER}/loop_runner.py export
```
"""

    (base / "ATIVAR.md").write_text(prompt.strip(), encoding="utf-8")
    print("  Prompt de ativação criado (ATIVAR.md)")


def create_gitignore(project_dir: Path):
    """Adiciona entradas ao .gitignore se necessário."""
    gitignore = project_dir / ".gitignore"
    entries = [
        f"\n# Auto-Learning System",
        f"{LEARNING_FOLDER}/db/learning.db",
        f"{LEARNING_FOLDER}/logs/",
        f"{LEARNING_FOLDER}/exports/",
    ]

    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if LEARNING_FOLDER in content:
            print("  .gitignore já configurado")
            return
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write("\n".join(entries) + "\n")
        print("  Entradas adicionadas ao .gitignore existente")
    else:
        gitignore.write_text("\n".join(entries) + "\n", encoding="utf-8")
        print("  .gitignore criado")


def init_database(project_dir: Path):
    """Inicializa o banco SQLite."""
    import sqlite3
    base = project_dir / LEARNING_FOLDER
    db_path = base / "db" / "learning.db"
    schema_path = base / "db" / "schema.sql"

    if not schema_path.exists():
        print("  ERRO: schema.sql não encontrado!")
        return

    conn = sqlite3.connect(db_path)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"  Banco inicializado: {LEARNING_FOLDER}/db/learning.db")


# ============================================================
# MAIN
# ============================================================
def main():
    if len(sys.argv) < 2:
        print("Uso: python instalar.py <caminho-do-projeto>")
        print("Ex:  python instalar.py C:\\Users\\Meu\\projeto")
        print("Ex:  python instalar.py .")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).resolve()

    if not project_dir.exists():
        print(f"ERRO: Diretório não existe: {project_dir}")
        sys.exit(1)

    project_name = project_dir.name

    print()
    print("=" * 55)
    print(" INSTALADOR — Sistema de Auto-Aprendizado")
    print("=" * 55)
    print(f" Projeto:  {project_name}")
    print(f" Caminho:  {project_dir}")
    print(f" Pasta:    {LEARNING_FOLDER}/")
    print("=" * 55)
    print()

    # Verifica se já está instalado
    if (project_dir / LEARNING_FOLDER / "engine.py").exists():
        print("AVISO: Sistema já instalado neste projeto!")
        resp = input("Reinstalar? (s/N): ").strip().lower()
        if resp != "s":
            print("Cancelado.")
            sys.exit(0)

    # Detecta stack
    tech_stack = detect_tech_stack(project_dir)
    print(f"  Tech stack detectado: {tech_stack}")
    print()

    # Passos
    print("[1/7] Fazendo backup do CLAUDE.md (se existir)...")
    had_claude_md = backup_claude_md(project_dir)

    print("[2/7] Criando estrutura de pastas...")
    create_folder_structure(project_dir)

    print("[3/7] Copiando arquivos core...")
    copy_core_files(project_dir)

    print("[4/7] Criando agentes...")
    create_agent_files(project_dir)

    print("[5/7] Criando instrucoes para a IA...")
    create_instructions(project_dir, project_name, tech_stack)
    create_activation_prompt(project_dir)

    print("[6/7] Configurando CLAUDE.md (preservando existente)...")
    append_to_claude_md(project_dir, project_name)

    print("[7/7] Inicializando banco de dados...")
    init_database(project_dir)

    print("[EXTRA] Configurando .gitignore...")
    create_gitignore(project_dir)

    print()
    print("=" * 55)
    print(" INSTALACAO COMPLETA!")
    print("=" * 55)
    print()
    print(" Estrutura criada:")
    print(f"   {LEARNING_FOLDER}/")
    print(f"   +-- engine.py")
    print(f"   +-- loop_runner.py")
    print(f"   +-- INSTRUCOES_IA.md")
    print(f"   +-- ATIVAR.md")
    print(f"   +-- db/schema.sql + learning.db")
    print(f"   +-- agents/ (13 IAs: 9 dev + 4 learning)")
    print(f"   +-- planos/")
    print(f"   +-- docs/analises/")
    print(f"   +-- regras/")
    print(f"   +-- logs/")
    print(f"   +-- exports/")
    print()
    if had_claude_md:
        print(" O CLAUDE.md original foi PRESERVADO.")
        print(" Uma secao de referencia foi ADICIONADA ao final.")
        print(f" Backup salvo como CLAUDE_backup_*.md")
    else:
        print(" CLAUDE.md criado (nao existia antes).")
    print()
    print(" Proximos passos:")
    print(f"   1. cd {project_dir}")
    print(f"   2. Abra o Claude Code: claude")
    print(f"   3. Cole o prompt de {LEARNING_FOLDER}/ATIVAR.md")
    print()
    print("=" * 55)


if __name__ == "__main__":
    main()
