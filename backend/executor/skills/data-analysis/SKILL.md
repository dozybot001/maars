---
name: data-analysis
description: Analyze structured data (JSON, tables, metrics) and produce insights. Use when task involves analyzing data, computing metrics, or deriving conclusions from structured input. Output can be report (Markdown) or structured (JSON).
---

# Data Analysis

Guidelines for analyzing structured data and producing insights.

## Input Handling

- Use ReadArtifact to get dependency outputs (e.g. benchmark results, survey data, configs).
- Use ReadFile for `sandbox/*` or plan-level files.
- Parse JSON or tabular data. Identify structure (keys, arrays, nested objects).

## Analysis Types

| Type | Input | Output |
|------|-------|--------|
| Aggregate | List of items | Metrics (count, sum, avg, min, max), distribution |
| Compare | Multiple datasets | Side-by-side comparison, deltas |
| Trend | Time-series or ordered data | Patterns, trends, anomalies |
| Correlation | Multi-variate data | Relationships, dependencies |
| Summary | Large dataset | Key statistics, representative samples |

## Output Format

### Markdown Report
- **Methodology**: What was analyzed.
- **Results**: Key metrics, tables, findings.
- **Interpretation**: What the numbers mean.
- **Conclusions**: Takeaways, recommendations.

### JSON Output
```
{
  "metrics": {"count": N, "avg": X, ...},
  "findings": ["finding1", "finding2"],
  "recommendations": ["rec1", "rec2"]
}
```

- Match the output spec exactly when format is specified.

## Tables for Results

Use Markdown tables for numerical results:

```markdown
| Metric | Value A | Value B | Delta |
|--------|---------|---------|-------|
| Latency | 10ms | 15ms | +50% |
```

## Sandbox Usage

- Save intermediate parsed data to `sandbox/parsed.json`
- Save computed metrics to `sandbox/metrics.json`
- Final output via Finish

## Error Handling

- If input is malformed: document the issue, suggest correction.
- If data is missing: note gaps, proceed with available data.
