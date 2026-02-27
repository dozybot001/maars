---
name: decomposition-patterns
description: Common patterns for decomposing research tasks. Use when decomposing complex tasks to ensure MECE (mutually exclusive, collectively exhaustive) splits and clear phase boundaries. Essential for Decompose tool.
---

# Decomposition Patterns

Reference patterns for task decomposition in research planning. Apply when CheckAtomicity returns atomic=false.

## Phase-Based Decomposition

| Pattern | Phases | Example |
|---------|--------|---------|
| Research → Analyze → Report | 3 phases | Literature review, analysis, synthesis |
| Scope → Gather → Synthesize | 3 phases | Define scope, collect data, combine |
| Setup → Execute → Validate | 3 phases | Config, run, verify |
| Design → Implement → Test | 3 phases | Design first, then build, then test |
| Compare A → Compare B → Synthesize | 3 phases | Technical comparison (Python vs JS) |
| Search → Filter → Rank | 3 phases | Information retrieval pipeline |
| Hypothesis → Experiment → Analyze | 3 phases | Empirical research |

## Domain-Specific Patterns

### Literature Review
- Search (keywords, databases) → Filter (relevance, quality) → Extract (key points) → Synthesize (themes, gaps) → Report

### Technical Comparison
- Define criteria → Research option A → Research option B → Compare (table, pros/cons) → Recommend

### Survey/Interview Study
- Design (questions, sample) → Conduct (collect) → Transcribe/Code → Analyze → Report

### Experiment
- Hypothesis → Setup (env, config) → Run (execute) → Analyze (stats) → Conclusion

## Boundary Rules

- **One responsibility per child**: Each child has exactly one deliverable. If you cannot state it in one sentence, split further.
- **No overlap**: Siblings must not cover the same ground. MECE = Mutually Exclusive, Collectively Exhaustive.
- **Clear handoff**: Phase N's output is Phase N+1's explicit input. Name artifacts.
- **2–6 children typical**: Avoid single-child (task is atomic) or 7+ (over-split; consider merging).
- **Depth-appropriate**: Root = high-level phases; deeper levels = specific sub-steps.

## Task ID Convention

- Parent "0": children "1", "2", "3", ...
- Parent "1": children "1_1", "1_2", "1_3", ...
- Parent "1_1": children "1_1_1", "1_1_2", ...

## Anti-Patterns

- Splitting by "easy/hard" instead of phase or methodology
- Mixing methodology changes in one task (e.g. "collect and analyze")
- Tasks that depend on vague "context" instead of concrete artifacts
- Circular or redundant dependencies between siblings
- Including parent in dependencies (use task_id hierarchy instead)
