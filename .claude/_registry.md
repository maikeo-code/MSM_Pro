# Session Registry
# Last updated: 2026-03-12 23:27
# CLAUDE.md version: 2.0
# Mode: ANALYZE
# Current cycle: 0

---

## TASK-001
- status: pending
- priority: P1
- assigned_to: orchestrator
- description: "Scan project structure and identify all code files, dependencies, and configuration"
- failure_count: 0
- output: null

## TASK-002
- status: pending
- priority: P2
- assigned_to: critic
- description: "Analyze code quality: naming, DRY, SOLID, complexity"
- failure_count: 0
- output: docs/analysis/code_quality_report.md

## TASK-003
- status: pending
- priority: P2
- assigned_to: critic
- description: "Analyze architecture: folder structure, separation of concerns, patterns"
- failure_count: 0
- output: docs/analysis/architecture_report.md

## TASK-004
- status: pending
- priority: P1
- assigned_to: security-agent
- description: "Security audit: secrets, vulnerabilities, unsafe patterns"
- failure_count: 0
- output: docs/analysis/security_report.md

## TASK-005
- status: pending
- priority: P2
- assigned_to: critic
- description: "Performance analysis: bottlenecks, N+1 queries, heavy loops"
- failure_count: 0
- output: docs/analysis/performance_report.md

## TASK-006
- status: pending
- priority: P3
- assigned_to: tester
- description: "Test coverage analysis: coverage gaps, untested critical paths"
- failure_count: 0
- output: docs/analysis/test_coverage_report.md

## TASK-007
- status: pending
- priority: P3
- assigned_to: researcher
- description: "Dependency health: outdated packages, known vulnerabilities"
- failure_count: 0
- output: docs/analysis/dependency_report.md

## TASK-008
- status: pending
- priority: P3
- assigned_to: documenter
- description: "Documentation quality: README, comments, API docs"
- failure_count: 0
- output: docs/analysis/documentation_report.md

## TASK-009
- status: pending
- priority: P2
- assigned_to: critic
- description: "API design review: REST patterns, naming, consistency"
- failure_count: 0
- output: docs/analysis/api_design_report.md

## TASK-010
- status: pending
- priority: P1
- assigned_to: documenter
- description: "Generate consolidated FULL_PROJECT_ANALYSIS.md with all scores"
- failure_count: 0
- output: docs/analysis/FULL_PROJECT_ANALYSIS.md

---

## HANDOFF
- last_agent: setup_script
- last_action: "Initialized analysis system"
- next_action: "Start TASK-001 — scan project structure"
- blockers: []
