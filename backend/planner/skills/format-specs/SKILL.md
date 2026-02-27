---
name: format-specs
description: Guidelines for defining input/output specifications of atomic tasks. Use when formatting tasks (FormatTask) to ensure executor and validator have clear, checkable criteria.
---

# Format Specifications

Guidelines for defining input/output/validation for atomic tasks. Apply when CheckAtomicity returns atomic=true.

## Input Spec

```json
{
  "description": "Human-readable description of what the task consumes",
  "artifacts": ["artifact_from_task_1", "artifact_from_task_2"],
  "parameters": ["optional_param_1"]
}
```

- **artifacts**: List artifact names or types from dependency tasks. Reference by task_id or semantic name.
- **parameters**: Optional explicit params (e.g. comparison_scope, target_audience). Omit if none.
- **description**: What the task needs to start. Be specific.

## Output Spec

```json
{
  "description": "What the task produces",
  "artifact": "output_artifact_name",
  "format": "JSON | Markdown | document | table"
}
```

- **artifact**: Name/type of produced artifact. Used by downstream tasks.
- **format**: JSON (structured), Markdown (document), document (generic), table (tabular).
- **description**: Clear statement of deliverable.

## Validation Spec

```json
{
  "description": "What to validate",
  "criteria": [
    "Output must contain keys X, Y",
    "All sources must be cited",
    "Table has columns A, B, C"
  ],
  "optionalChecks": ["Optional: style consistency"]
}
```

- **criteria**: Concrete, checkable rules. Validator can verify without subjective judgment.
- **optionalChecks**: Nice-to-have; do not fail validation if missing.
- **Aligned**: Criteria must match output format (e.g. JSON schema for JSON; section names for Markdown).

## Format-Specific Examples

### JSON Output
```json
{
  "output": {
    "artifact": "search_config",
    "format": "JSON: { keywords: string[], databases: string[] }"
  },
  "validation": {
    "criteria": [
      "Output is valid JSON",
      "keywords is non-empty array",
      "databases lists at least one valid database"
    ]
  }
}
```

### Markdown Output
```json
{
  "output": {
    "artifact": "synthesis_report",
    "format": "Markdown document"
  },
  "validation": {
    "criteria": [
      "Document has ## Summary section",
      "Document has ## Findings section",
      "All cited sources have [author, year] format"
    ]
  }
}
```

## Anti-Patterns

- Vague criteria: "output should be good" → use concrete checks
- Subjective criteria: "writing quality" → use structural or content rules
- Mismatched format: JSON output with "must have Introduction" → align with format
