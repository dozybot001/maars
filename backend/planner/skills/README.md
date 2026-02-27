# Planner Skills

Skills for the Planner Agent (decomposition, scoping, formatting). Used when `plannerAgentMode=True`.

## Built-in Skills

| Skill | Description |
|-------|-------------|
| **decomposition-patterns** | Phase-based and domain-specific decomposition patterns; MECE rules; anti-patterns |
| **research-scoping** | Scoping research ideas; granularity; atomicity hints |
| **format-specs** | Input/output/validation specs for atomic tasks; format-specific examples |
| **atomicity-criteria** | When a task is atomic vs non-atomic; decision rules and examples |
| **dependency-rules** | Sibling-only dependencies; acyclic graph; task_id conventions |

## Structure

Each skill is a directory with `SKILL.md` (YAML frontmatter + content). Optional: `references/`, `scripts/`.

## Config

- Root: `backend/planner/skills/` (default)
- Override: `MAARS_PLANNER_SKILLS_DIR` env
