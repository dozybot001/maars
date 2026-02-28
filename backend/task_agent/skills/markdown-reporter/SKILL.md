---
name: markdown-reporter
description: Generate structured Markdown reports, summaries, and documentation. Use when task output format is Markdown, document, report, summary, or README. Covers structure, tables, code blocks, and common report types. Essential for FormatTask output spec format: Markdown.
---

# Markdown Reporter

Guidelines for producing high-quality Markdown output in research and documentation tasks.

## Output Structure

- **Headings**: Use `##` for main sections, `###` for subsections. Keep hierarchy clear (h2 > h3 > h4). Do not skip levels.
- **Lists**: Use `-` for unordered, `1.` for ordered. Nest appropriately.
- **Code**: Use fenced blocks with language when including code: ` ```python ` ... ` ``` `
- **Tables**: Use pipe `|` syntax. Align columns for readability.
- **Links**: `[text](url)` for references. Use `[Author, Year]` for citations when appropriate.
- **Bold/Italic**: `**bold**` for emphasis, `*italic*` for terms.

## Common Report Types

| Type | Structure | Sections |
|------|-----------|----------|
| Summary | Executive summary, key findings, conclusions | Summary, Findings, Conclusions |
| Comparison | Side-by-side table, pros/cons, recommendation | Criteria, Comparison Table, Pros/Cons, Recommendation |
| Analysis | Methodology, data, findings, implications | Methodology, Data/Results, Findings, Implications |
| Literature synthesis | Themes, gaps, synthesis | Overview, Key Themes, Gaps, Synthesis |
| Documentation | Overview, usage, examples | Overview, Usage, Examples, API/Reference |
| Technical report | Problem, approach, results, discussion | Problem, Approach, Results, Discussion |

## Table Format

```markdown
| Column A | Column B | Column C |
|----------|----------|----------|
| value 1  | value 2  | value 3  |
```

- Header row with `|` separators
- Alignment row: `|---|` or `:---:|` for center
- Consistent column width for readability
- Escape `|` inside cells with `\|` if needed

## Validation Alignment

When the task's validation spec requires specific sections (e.g. "Document has ## Summary section"), ensure those sections exist with exact heading text. Use the same heading level as specified.

## Quality Checklist

- [ ] Clear section hierarchy (no skipped levels)
- [ ] Concise but complete coverage
- [ ] Code blocks with syntax hint when relevant
- [ ] Tables for comparative or tabular data
- [ ] Citations/references when using external sources
- [ ] No raw HTML unless necessary
- [ ] Validation criteria from task spec satisfied

## Sandbox Usage

- Save drafts to `sandbox/draft.md` if iterating
- Final output via Finish tool (pass Markdown string)

## References

- For templates, see [references/templates.md](references/templates.md)
