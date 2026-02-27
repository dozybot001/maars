# Executor Skills

Skills for the Executor Agent (execution, file I/O, domain tools). Used when `executorAgentMode=True`.

## Built-in Skills

| Skill | Description |
|-------|-------------|
| **find-skills** | Discover and install skills from skills.sh ecosystem |
| **skill-creator** | Create, improve, and evaluate new skills |
| **markdown-reporter** | Structured Markdown reports; templates; tables; code blocks |
| **json-utils** | Validate, format, structure JSON; schema alignment |
| **web-research** | Research process; synthesis techniques; output structure |
| **comparison-report** | Compare options; criteria table; pros/cons; recommendation |
| **literature-synthesis** | Synthesize literature; thematic organization; gaps and conclusions |
| **data-analysis** | Analyze structured data; metrics; trends; report or JSON output |

## Structure

Each skill is a directory with `SKILL.md`. May include `scripts/`, `references/`, `assets/`. Use `RunSkillScript` to execute `.py`, `.sh`, `.js` scripts.

## Config

- Root: `backend/executor/skills/` (default)
- Override: `MAARS_EXECUTOR_SKILLS_DIR` env
