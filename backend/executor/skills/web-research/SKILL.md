---
name: web-research
description: Conduct web research, gather information from multiple sources, and synthesize findings. Use when task involves searching, comparing sources, or aggregating information. Covers process, synthesis techniques, and output structure.
---

# Web Research

Guidelines for research tasks that involve gathering and synthesizing information from multiple sources.

## Research Process

1. **Define scope**: Clarify what information is needed, from which domains, and what format the output should take.
2. **Gather sources**: Use ReadArtifact for dependency outputs; ReadFile for local files. Note: MAARS Executor does not have live web search—use provided artifacts and general knowledge. If the task expects external data, document assumptions.
3. **Synthesize**: Combine findings. Note agreements, conflicts, and gaps. Use tables for side-by-side comparison.
4. **Cite**: When referencing sources from input artifacts, include clear attribution (e.g. [Source Name], [Author, Year]).

## Synthesis Techniques

- **Thematic synthesis**: Group findings by theme or topic.
- **Comparative synthesis**: Side-by-side table when comparing options.
- **Chronological**: When timeline or evolution matters.
- **Gap analysis**: What is known vs unknown; recommend next steps.

## Output Structure

| Section | Purpose |
|---------|---------|
| Findings | Organized by topic or source. Use subsections. |
| Summary | Key takeaways in bullet or paragraph form. |
| Gaps | What could not be determined; limitations. |
| Recommendations | Next steps, conclusions, or suggested actions. |

## Sandbox Usage

- Save intermediate notes to `sandbox/notes.md`
- Store raw or structured data to `sandbox/data.json` if needed
- Draft sections in `sandbox/draft.md` before finalizing
- Final output via Finish tool

## Quality Checklist

- [ ] Findings organized logically
- [ ] Sources attributed when from input artifacts
- [ ] Summary captures main points
- [ ] Gaps/limitations acknowledged when relevant
- [ ] Recommendations actionable when appropriate
