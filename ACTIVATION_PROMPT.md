# Activation Prompt
# Copy and paste this into Claude Code to start the system.

## For Claude Code (CLI):
Open a terminal in this project folder, then run:
```
claude
```

Then paste this prompt:

---

Read the file CLAUDE.md completely. Then read .claude/_registry.md to see the pending analysis tasks. You are operating in ANALYZE mode — you must NOT modify any source code files. Start the analysis loop: begin with TASK-001 (scan project structure), then proceed through each analysis task in priority order. For each task, read the relevant source files, perform the analysis, have the critic review it, and write the report to docs/analysis/. After all tasks are done, generate the consolidated report at docs/analysis/FULL_PROJECT_ANALYSIS.md. Go.

---

## Tips:
- Press Ctrl+C to pause at any time
- Reopen Claude Code and it will read _registry.md to continue
- Reports will appear in docs/analysis/ (ANALYZE mode)
- Learnings accumulate in .claude/memory/chunks.jsonl
