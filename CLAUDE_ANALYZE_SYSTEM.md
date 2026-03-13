# CLAUDE.md — Universal Master Instructions v2.0
# =====================================================
# BEFORE ANYTHING: Read this file completely.
# This system works for ANY project with 3 to 20 sub-agents.
# Supports: BUILD mode (develop) and ANALYZE mode (audit/learn).
# =====================================================

CLAUDE_MD_VERSION: "2.0"

---

## 0. OPERATION MODE

OPERATION_MODE: "ANALYZE"

# Options:
#   "BUILD"   — Full development cycle (code, test, deploy, iterate)
#   "ANALYZE" — Read-only audit (analyze, report, suggest, learn — NO code changes)

# ANALYZE MODE: Agents MUST NOT modify source code. Read-only analysis only.
# All outputs go to docs/analysis/. The loop generates insights, NOT code changes.

---

## 1. PROJECT IDENTITY

PROJECT_NAME: "MSM_Pro"
TECH_STACK: "Docker Railway"
PROJECT_DESCRIPTION: "{FILL_IN}"
MAIN_REPOSITORY: "{FILL_IN}"
DEPLOY_PLATFORM: "{FILL_IN or N/A}"
PROJECT_OWNER: "{FILL_IN}"
EXTERNAL_API: "None"
EXTERNAL_API_BASE_URL: "N/A"
EXTERNAL_API_DOCS: "N/A"

---

## 2. ACTIVE AGENTS

ACTIVE_AGENTS:
  - name: orchestrator
    required: true
    role: "Central coordinator — assigns tasks, resolves conflicts"
    authority_level: 3

  - name: critic
    required: true
    role: "Reviews all decisions, code, and outputs before approval"
    authority_level: 2

  - name: developer
    required: true
    role: "Implements features and fixes (BUILD mode only)"
    authority_level: 1

  - name: researcher
    required: false
    role: "Searches for solutions, patterns, best practices"
    authority_level: 1

  - name: documenter
    required: false
    role: "Writes and maintains all documentation"
    authority_level: 1

  - name: tester
    required: false
    role: "Validates with tests"
    authority_level: 1

  - name: security-agent
    required: false
    role: "Reviews code for vulnerabilities"
    authority_level: 2

---

## 3. CONFLICT RESOLUTION

CONFLICT_RESOLUTION:
  step_1: "Disagreeing agents each write a 3-line justification"
  step_2: "Orchestrator evaluates both"
  step_3: "Higher authority_level wins ties"
  step_4: "Same authority — orchestrator decides"
  step_5: "If orchestrator is involved, escalate to user"
  step_6: "Log in docs/decisions_log.md"

---

## 4. ABSOLUTE RULES

RULE_01: "Read CLAUDE.md completely before starting any task."
RULE_02: "Check _registry.md before executing."
RULE_03: "Never edit two critical files simultaneously without committing first."
RULE_04: "Never deploy without passing all tests."
RULE_05: "Commit after each completed step (BUILD mode only)."
RULE_06: "If unsure about an API, consult official docs first."
RULE_07: "Document every decision in docs/knowledge_base.md."
RULE_08: "Do NOT invent API endpoints."
RULE_09: "If context exceeds 150k tokens, compress immediately."
RULE_10: "After each cycle, run /wrap-up."
RULE_11: "NEVER commit secrets (API keys, tokens, passwords)."
RULE_12: "In ANALYZE mode, NEVER modify source code."
RULE_13: "After 3 consecutive failures on same task, STOP and escalate."

---

## 5. TASK PRIORITY SYSTEM

PRIORITY_LEVELS:
  P0_CRITICAL: "Blocks everything — immediate response"
  P1_HIGH: "Core broken, deploy blocked — same cycle"
  P2_MEDIUM: "New feature, non-critical bug — next cycle"
  P3_LOW: "Docs, refactoring — when available"

PRIORITY_RULES:
  - "P0 interrupts everything"
  - "Within same priority, FIFO order"
  - "Orchestrator can override with logged justification"

---

## 6. SECURITY

SECRETS_FORBIDDEN:
  - "Hardcoding secrets in source code"
  - "Committing .env files"
  - "Logging secret values anywhere"
  - "Storing secrets in _registry.md or NOTES.md"

---

## 7A. BUILD LOOP (BUILD mode)

LOOP_CYCLE:
  1: "Read _registry.md"
  2: "Read NOTES.md"
  3: "Select highest priority pending task"
  4: "Execute task"
  5: "Critic reviews"
  6: "Tester validates"
  7: "Documenter records"
  8: "Extract learning -> chunks.jsonl"
  9: "Compress if needed"
  10: "Update _registry.md"
  11: "Next cycle"

---

## 7B. ANALYZE LOOP (ANALYZE mode)

ANALYZE_LOOP_CYCLE:
  1: "Read _registry.md — current analysis state"
  2: "Read NOTES.md — previous findings"
  3: "Select next analysis task"
  4: "Execute analysis (read-only)"
  5: "Critic reviews accuracy"
  6: "Documenter writes to docs/analysis/"
  7: "Generate score (0-100)"
  8: "Extract learning -> chunks.jsonl"
  9: "Compress if needed"
  10: "Update _registry.md"
  11: "Next cycle"

ANALYSIS_TYPES:
  - code_quality     -> docs/analysis/code_quality_report.md
  - architecture     -> docs/analysis/architecture_report.md
  - security_audit   -> docs/analysis/security_report.md
  - performance      -> docs/analysis/performance_report.md
  - test_coverage    -> docs/analysis/test_coverage_report.md
  - dependency_health -> docs/analysis/dependency_report.md
  - documentation    -> docs/analysis/documentation_report.md
  - api_design       -> docs/analysis/api_design_report.md

FINAL_REPORT: "docs/analysis/FULL_PROJECT_ANALYSIS.md"

---

## 8. LOOP PROTECTION

FAILURE_TRACKING:
  max_consecutive_failures: 3

ESCALATION:
  1: "Log failure in docs/skill_gaps.md"
  2: "Mark task as BLOCKED"
  3: "Researcher looks for alternatives"
  4: "If still failing, STOP and notify user"

HEALTH_CHECK_EVERY: 10 cycles
  - "If productivity < 30%, pause and review"
  - "If any task stuck > 5 cycles, split into subtasks"

---

## 9. REGISTRY FORMAT

# _registry.md MUST follow this format. No free-form text.

TASK_FORMAT: |
  ## TASK-{NNN}
  - status: pending | in_progress | completed | blocked
  - priority: P0 | P1 | P2 | P3
  - assigned_to: {agent}
  - description: "{what to do}"
  - failure_count: 0
  - output: null

HANDOFF_FORMAT: |
  ## HANDOFF
  - last_agent: {name}
  - last_action: "{what was done}"
  - next_action: "{what to do next}"
  - blockers: []

---

## 10. SELF-LEARNING

LEARNING_FORMAT: |
  {"date":"YYYY-MM-DD","agent":"name","task":"TASK-NNN",
   "type":"success|failure|discovery","learning":"what was learned",
   "tags":["tag1"],"confidence":0.0-1.0}

STORAGE: ".claude/memory/chunks.jsonl"

PATTERN_DETECTION:
  every: 20 cycles
  threshold: "3+ occurrences = promote to auto rule"
  rule_location: ".claude/rules/auto_rule_{N}.md"
  deprecate_after: "3+ counter-examples"

---

## 11. MEMORY SYSTEM

MEMORY_LAYERS:
  working_memory: "Current context (chat window)"
  session_memory: "docs/NOTES.md (max 200 lines)"
  long_term: ".claude/memory/chunks.jsonl"
  registry: ".claude/_registry.md (rolling 3 days)"
  knowledge: "docs/knowledge_base.md"

COMPRESSION_TRIGGER: "~80% context (~150k tokens)"

---

## 12. STOP CONDITIONS

STOP_IF:
  - "User interrupts (Ctrl+C)"
  - "All tasks completed"
  - "Unrecoverable error after escalation"
  - "3 consecutive failures (escalate first)"
  - "Security breach detected"

GRACEFUL_STOP:
  1: "Finish current atomic operation"
  2: "Save learnings to chunks.jsonl"
  3: "Update _registry.md with handoff"
  4: "Update NOTES.md"
  5: "Report to user"

---

## 13. KNOWN BUGS

# Check here BEFORE debugging. Apply known solutions directly.
# BUG-001: "Unfilled"

---

## 14. QUICK START

# ANALYZE MODE (audit existing project):
#   1. Run: ./setup.sh /path/to/project ANALYZE
#   2. Open Claude Code in the project folder
#   3. Say: "Read CLAUDE.md and start the analysis loop"
#   4. Reports appear in docs/analysis/
#
# BUILD MODE:
#   1. Run: ./setup.sh /path/to/project BUILD
#   2. Edit _registry.md to add your development tasks
#   3. Open Claude Code in the project folder
#   4. Say: "Read CLAUDE.md and start the build loop"
