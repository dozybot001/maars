"""TeamStage -- base for iterative two-agent stages (primary + reviewer)."""

import asyncio
import logging
from dataclasses import dataclass, field

from backend.pipeline.stage import Stage
from backend.utils import parse_json_fenced

log = logging.getLogger(__name__)


def _is_zh() -> bool:
    from backend.config import settings
    return settings.is_chinese()


@dataclass
class IterationState:
    """Compact state passed between iterations. Replaces share_member_interactions."""

    draft: str = ""
    issues: list[dict] = field(default_factory=list)
    iteration: int = 0

    def format_issues(self) -> str:
        if not self.issues:
            return "（无待解决问题）" if _is_zh() else "(No open issues)"
        zh = _is_zh()
        lines = []
        for issue in self.issues:
            iid = issue.get("id", "unknown")
            severity = issue.get("severity", "major")
            section = issue.get("section", "General")
            problem = issue.get("problem", "")
            suggestion = issue.get("suggestion", "")
            lines.append(f"- **{iid}** [{severity}] {section}: {problem}")
            if suggestion:
                label = "建议" if zh else "Suggestion"
                lines.append(f"  {label}: {suggestion}")
        return "\n".join(lines)

    def update(self, new_draft: str, feedback: dict):
        self.draft = new_draft
        resolved_ids = set(feedback.get("resolved", []))
        remaining = [iss for iss in self.issues if iss.get("id") not in resolved_ids]
        remaining.extend(feedback.get("issues", []))
        self.issues = remaining
        self.iteration += 1


class TeamStage(Stage):
    """Iterative two-agent loop: primary produces, reviewer critiques."""

    _primary_dir: str = "proposals"
    _reviewer_dir: str = "critiques"
    _primary_phase: str = "proposal"
    _reviewer_phase: str = "critique"

    def __init__(self, name: str, model=None, db=None, max_delegations: int = 10):
        super().__init__(name=name, db=db)
        self._model = model
        self._max_delegations = max_delegations

    def load_input(self) -> str:
        raise NotImplementedError

    def _primary_config(self) -> tuple[str, list, str]:
        """Return (instruction, tools, label) for the primary agent."""
        raise NotImplementedError

    def _reviewer_config(self) -> tuple[str, list, str]:
        """Return (instruction, tools, label) for the reviewer agent."""
        raise NotImplementedError

    def _finalize(self) -> str:
        raise NotImplementedError

    async def _execute(self) -> str:
        input_text = self.load_input()
        state = IterationState()
        reviewer_approved = False
        primary_instr, primary_tools, primary_label = self._primary_config()
        reviewer_instr, reviewer_tools, reviewer_label = self._reviewer_config()

        for round_num in range(self._max_delegations):
            if self._stop_requested:
                raise asyncio.CancelledError()

            # 1. Primary agent produces/revises — skip if already on disk
            self._current_phase = self._primary_phase
            draft = self._load_round_md(self._primary_dir, round_num + 1)
            if not draft:
                primary_user = self._build_primary_prompt(input_text, state)
                draft = await self._stream_llm(
                    self._model, primary_tools, primary_instr, primary_user,
                    call_id=primary_label, content_level=3,
                    label=True, label_level=2,
                )
                if self.db:
                    self._save_round_md(self._primary_dir, draft, round_num + 1)
            state.draft = draft
            self._send()

            if self._stop_requested:
                raise asyncio.CancelledError()

            # 2. Reviewer critiques — skip if already on disk
            self._current_phase = self._reviewer_phase
            feedback = self._load_round_json(self._reviewer_dir, round_num + 1)
            if feedback is None:
                reviewer_user = self._build_reviewer_prompt(input_text, state)
                review_raw = await self._stream_llm(
                    self._model, reviewer_tools, reviewer_instr, reviewer_user,
                    call_id=reviewer_label, content_level=3,
                    label=True, label_level=2,
                )
                feedback = parse_json_fenced(review_raw, fallback={"pass": False, "issues": []})
                if self.db:
                    self._save_round_md(self._reviewer_dir, review_raw, round_num + 1)
                    self._save_round_json(self._reviewer_dir, feedback, round_num + 1)
            self._send()

            if feedback.get("pass", False):
                reviewer_approved = True
                break

            # On the final allowed round, keep the reviewer output on disk/UI
            # but stop instead of attempting another revision cycle.
            if round_num >= self._max_delegations - 1:
                break

            # 3. Update state for next round
            state.update(draft, feedback)

        self._current_phase = ""
        self.output = state.draft
        if not self.output:
            log.warning("%s: no content produced", self.name)

        if not reviewer_approved:
            raise RuntimeError(
                f"{self.name} stage reached the review limit "
                f"({self._max_delegations}) without reviewer approval"
            )

        return self._finalize()

    def _build_primary_prompt(self, input_text: str, state: IterationState) -> str:
        if state.iteration == 0:
            return input_text
        zh = _is_zh()
        parts = [input_text]
        draft_hdr = f"当前草稿（第 {state.iteration} 版）" if zh else f"Current Draft (Revision {state.iteration})"
        parts.append(f"\n## {draft_hdr}\n{state.draft}")
        issues_hdr = "需解决的问题" if zh else "Issues to Address"
        parts.append(f"\n## {issues_hdr}\n{state.format_issues()}")
        revise = "修改草稿以解决所有列出的问题。输出完整的修改版本。" if zh else \
                 "Revise the draft to address all listed issues. Output the complete revised version."
        parts.append(f"\n{revise}")
        return "\n".join(parts)

    def _build_reviewer_prompt(self, input_text: str, state: IterationState) -> str:
        zh = _is_zh()
        parts = [input_text]
        review_hdr = "待审内容" if zh else "Content to Review"
        parts.append(f"\n## {review_hdr}\n{state.draft}")
        if state.issues:
            prev_hdr = "此前已识别的问题" if zh else "Previously Identified Issues"
            parts.append(f"\n## {prev_hdr}\n{state.format_issues()}")
        return "\n".join(parts)

    def _load_round_md(self, dirname: str, iteration: int) -> str:
        if not self.db:
            return ""
        return self.db.load_round_md(dirname, iteration)

    def _load_round_json(self, dirname: str, iteration: int) -> dict | None:
        if not self.db:
            return None
        return self.db.load_round_json(dirname, iteration)

    def _save_round_md(self, dirname: str, text: str, iteration: int):
        self.db.save_round_md(dirname, text, iteration)

    def _save_round_json(self, dirname: str, data: dict, iteration: int):
        self.db.save_round_json(dirname, data, iteration)
