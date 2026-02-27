---
name: comparison-report
description: Produce comparison reports between two or more options (technologies, approaches, products). Use when task involves comparing, evaluating alternatives, or making recommendations. Output typically includes criteria, comparison table, pros/cons, and recommendation.
---

# Comparison Report

Guidelines for producing comparison reports between two or more options.

## Output Structure

1. **Criteria**: List the dimensions used for comparison (e.g. performance, ecosystem, learning curve).
2. **Comparison Table**: Side-by-side comparison. Rows = criteria, columns = options.
3. **Pros and Cons**: Per-option strengths and weaknesses.
4. **Recommendation**: Clear conclusion with rationale. Map to scenarios when appropriate.

## Table Format

```markdown
| Criterion    | Option A | Option B | Option C |
|--------------|----------|----------|----------|
| Performance  | High     | Medium   | High     |
| Ecosystem    | Mature   | Growing | Mature   |
| Learning     | Moderate | Easy    | Steep    |
```

- Use consistent scale or labels (e.g. High/Medium/Low, or specific metrics).
- Add a brief "Notes" row if needed for context.

## Pros/Cons Format

**Option A**
- Pros: ...
- Cons: ...

**Option B**
- Pros: ...
- Cons: ...

## Recommendation

- State the recommended option clearly.
- Include "when to use" or "best for" scenarios.
- Support with evidence from the comparison.

## Input Artifacts

- Use ReadArtifact to get research outputs for each option (e.g. task_1, task_2, task_3).
- Combine into unified comparison. Ensure criteria align across sources.

## Output Format

- Markdown for human-readable reports.
- JSON for structured output when spec requires: `{"options": [...], "comparison": {...}, "recommendation": "..."}`.
