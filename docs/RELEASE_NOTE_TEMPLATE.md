# Release Note Template

> Copy this template for each release. Fill in sections, delete unused ones.
> Format: English body first, then full Chinese translation in `<details>`.

---

```markdown
## MAARS X.Y.Z — {One-line Title}

{1-2 sentence summary. What changed and why.}

Net result: **{+/-N} lines** ({added} added, {removed} removed across {N} files).

### {Section Title}

- bullet points — what changed, why it matters
- reference specific files/functions only when they clarify the change

### {Section Title}

...

### Bug Fixes

- {description of fix}

**Full Changelog**: https://github.com/dozybot001/MAARS/compare/vPREV...vCURR

---

<details>
<summary>中文</summary>

## MAARS X.Y.Z — {一行标题}

{1-2 句摘要。改了什么、为什么改。}

净变化：**{+/-N} 行**（{N} 个文件，新增 {added}，删除 {removed}）。

### {中文标题}

- 中文要点

### 问题修复

- {修复描述}

**完整变更日志**: https://github.com/dozybot001/MAARS/compare/vPREV...vCURR

</details>
```

> Guidelines:
> - English body first, complete. Chinese in `<details>` block, complete mirror.
> - Bullet points, not paragraphs — scannable
> - "What changed + why" not "how it's implemented"
> - Net line count in header if significant
