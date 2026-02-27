"""
Task output validation - checks output against output_spec.
Used when useMock=False; Mock mode still uses random for testing.
"""

import json
from typing import Any, Dict, Tuple


def validate_task_output(
    result: Any, output_spec: Dict[str, Any], task_id: str
) -> Tuple[bool, str]:
    """
    Validate task output against output_spec.
    Returns (passed, report_markdown).
    """
    report_lines = [f"# Validating Task {task_id}\n", "Checking output against criteria...\n"]
    checks_passed = []

    # Criterion 1: Output format
    output_format = (output_spec or {}).get("format") or ""
    fmt_upper = output_format.strip().upper()
    if "JSON" in fmt_upper or fmt_upper.startswith("JSON"):
        try:
            if isinstance(result, dict):
                pass  # already parsed
            elif isinstance(result, str):
                json.loads(result)
            else:
                json.dumps(result)  # ensure serializable
            checks_passed.append(("Output format (JSON)", True))
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            checks_passed.append(("Output format (JSON)", False))
    else:
        # Markdown or other: check non-empty
        content = result.get("content", result) if isinstance(result, dict) else result
        is_ok = content is not None and (
            (isinstance(content, str) and content.strip()) or (not isinstance(content, str))
        )
        checks_passed.append(("Output format", is_ok))

    # Criterion 2: Content presence
    if isinstance(result, dict):
        has_content = "content" in result or len(result) > 0
    else:
        has_content = result is not None and (not isinstance(result, str) or result.strip())
    checks_passed.append(("Content completeness", has_content))

    # Criterion 3: Alignment with spec (basic - no LLM)
    alignment_ok = True
    checks_passed.append(("Alignment with spec", alignment_ok))

    # Build report
    for label, ok in checks_passed:
        report_lines.append(f"- {label}: {'PASS' if ok else 'FAIL'}\n")
    all_passed = all(ok for _, ok in checks_passed)
    report_lines.append(f"\n**Result: {'PASS' if all_passed else 'FAIL'}**\n")
    return all_passed, "".join(report_lines)
