"""Retry/attempt helper mixin for Task ExecutionRunner."""

import json
import re
from typing import Any, Dict, List


class RunnerRetryMixin:
    def _failure_key(self, task_id: str, bucket: str) -> str:
        return f"{task_id}:{bucket}"

    def _get_failure_count(self, task_id: str, bucket: str) -> int:
        return int(self.task_phase_failure_count.get(self._failure_key(task_id, bucket), 0) or 0)

    def _next_phase_attempt(self, task_id: str, *, phase: str, bucket: str) -> int:
        history = self.task_attempt_history.get(task_id) or []
        phase_attempts = sum(1 for item in history if str(item.get("phase") or "") == phase)
        in_memory_attempts = self._get_failure_count(task_id, bucket)
        next_count = max(phase_attempts, in_memory_attempts) + 1
        self.task_phase_failure_count[self._failure_key(task_id, bucket)] = next_count
        return next_count

    def _clear_task_failure_counts(self, task_id: str) -> None:
        prefix = f"{task_id}:"
        for key in list(self.task_phase_failure_count.keys()):
            if key.startswith(prefix):
                self.task_phase_failure_count.pop(key, None)
        self.task_failure_count.pop(task_id, None)

    @staticmethod
    def _extract_direct_fail_reason(report_text: str) -> str:
        """Return the single most helpful FAIL reason line from a validation report."""
        for line in report_text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            upper = s.upper()
            if ("FAIL" in upper or "FAILED" in upper) and re.search(r"FAIL\s*\(", s, re.IGNORECASE):
                return s.lstrip("-* ")
        for line in report_text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "FAIL" in s.upper() or "FAILED" in s.upper():
                return s.lstrip("-* ")
        for line in report_text.splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                return s
        return "Validation failed."

    def _next_retry_attempt(self, task_id: str) -> int:
        history = self.task_attempt_history.get(task_id) or []
        history_attempts = 0
        for item in history:
            n = int(item.get("attempt") or 0)
            if n > history_attempts:
                history_attempts = n
        in_memory_attempts = self._get_failure_count(task_id, "retry")
        next_count = max(history_attempts, in_memory_attempts) + 1
        self.task_phase_failure_count[self._failure_key(task_id, "retry")] = next_count
        return next_count

    def _get_current_attempt(self, task_id: str) -> int:
        history = self.task_attempt_history.get(task_id) or []
        history_attempts = 0
        for item in history:
            n = int(item.get("attempt") or 0)
            if n > history_attempts:
                history_attempts = n
        in_memory_attempts = self._get_failure_count(task_id, "retry")
        return max(history_attempts, in_memory_attempts) + 1

    def _resolve_run_attempt(self, task_id: str) -> int:
        """Resolve a monotonic attempt number from all retry sources.

        Order is intentionally max-based to avoid regressions when one state source
        is stale (e.g. delayed events or transient resets).
        """
        explicit = int(self.task_run_attempt.get(task_id) or 0)
        baseline = self._get_current_attempt(task_id)
        forced = int(self.task_forced_attempt.get(task_id) or 0)
        hinted = int(self.task_next_attempt_hint.get(task_id) or 0)
        run_attempt = max(1, explicit, baseline, forced, hinted)
        self.task_run_attempt[task_id] = run_attempt
        self.task_next_attempt_hint[task_id] = run_attempt
        return run_attempt

    def _reserve_execute_attempt(self, task_id: str, requested_attempt: int) -> int:
        """Reserve a unique execute-attempt for this task in current run.

        Hard guard: one attempt number can launch execute ADK at most once.
        If a duplicate launch is requested, bump to the next free attempt.
        """
        attempt = max(1, int(requested_attempt or 1))
        seen = self.task_execute_started_attempts.setdefault(task_id, set())
        while attempt in seen:
            attempt += 1
        seen.add(attempt)
        return attempt

    def _get_original_validation_criteria(self, task: Dict[str, Any]) -> List[str]:
        validation = task.setdefault("validation", {})
        if not isinstance(validation, dict):
            validation = {}
            task["validation"] = validation
        original = list(validation.get("originalCriteria") or [])
        current = list(validation.get("criteria") or [])
        if not original:
            original = list(current)
            validation["originalCriteria"] = list(original)
        return list(original)

    @staticmethod
    def _run_step_a_structural_format_gate(result: Any, output_spec: Dict[str, Any]) -> tuple[bool, str]:
        """Step A gate: only check structural completeness, never semantic correctness.

        This stage should answer: "Is the output structurally consumable?"
        It must not enforce business/content criteria, which belong to Step C.
        """
        expected_format = str((output_spec or {}).get("format") or "").strip()
        expected_lc = expected_format.lower()
        requires_structured = any(tok in expected_lc for tok in ("json", "dictionary", "dict", "object", "map"))

        if result is None:
            return False, "- Output structure: FAIL (missing output payload)"

        if isinstance(result, dict):
            if not result:
                return False, "- Output structure: FAIL (empty object)"
            return True, "- Output structure: PASS (non-empty object)"

        if isinstance(result, list):
            if not result:
                return False, "- Output structure: FAIL (empty list)"
            return True, "- Output structure: PASS (non-empty list)"

        if isinstance(result, str):
            text = result.strip()
            if not text:
                return False, "- Output structure: FAIL (empty string)"
            if requires_structured:
                try:
                    parsed = json.loads(text)
                except Exception:
                    return False, "- Output structure: FAIL (expected structured JSON text but parsing failed)"
                if isinstance(parsed, (dict, list)) and parsed:
                    return True, "- Output structure: PASS (structured JSON text is parsable and non-empty)"
                return False, "- Output structure: FAIL (structured JSON text parsed but empty/invalid container)"
            return True, "- Output structure: PASS (non-empty text)"

        text = str(result).strip()
        if not text:
            return False, "- Output structure: FAIL (unreadable output)"
        return True, "- Output structure: PASS (stringifiable output)"
