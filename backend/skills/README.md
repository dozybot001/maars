# Agent Skills

Skills are loaded by the Executor Agent via `ListSkills` and `LoadSkill` tools.

## Source

Most skills are from [anthropics/skills](https://github.com/anthropics/skills). To update:

```bash
cd backend
git clone --depth 1 https://github.com/anthropics/skills.git vendor/anthropics-skills
cp -r vendor/anthropics-skills/skills/* skills/
rm -rf vendor/anthropics-skills
```

## Structure

Each skill is a directory with `SKILL.md` (YAML frontmatter + Markdown instructions). The skills root is `backend/skills/` by default, or set `MAARS_SKILLS_DIR` to override.
