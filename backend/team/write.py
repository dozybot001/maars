"""Write stage: iterative paper writing (Writer + Reviewer)."""

import json
import re

from backend.team.stage import TeamStage


class WriteStage(TeamStage):

    _primary_dir = "drafts"
    _reviewer_dir = "reviews"
    _primary_phase = "draft"
    _reviewer_phase = "review"

    def __init__(self, name: str = "write", model=None, writer_tools=None,
                 reviewer_tools=None, db=None, max_delegations: int = 10):
        super().__init__(name=name, model=model, db=db, max_delegations=max_delegations)
        self._writer_tools = writer_tools or []
        self._reviewer_tools = reviewer_tools or []

    @staticmethod
    def _rewrite_artifact_paths(text: str, prefix: str) -> str:
        if not text:
            return text
        normalized_prefix = prefix.rstrip("/")
        patterns = [
            (r"\]\(\.\./artifacts/", f"]({normalized_prefix}/artifacts/"),
            (r'\]\(artifacts/', f"]({normalized_prefix}/artifacts/"),
            (r'src="\.\./artifacts/', f'src="{normalized_prefix}/artifacts/'),
            (r'src="artifacts/', f'src="{normalized_prefix}/artifacts/'),
            (r'href="\.\./artifacts/', f'href="{normalized_prefix}/artifacts/'),
            (r'href="artifacts/', f'href="{normalized_prefix}/artifacts/'),
        ]
        rewritten = text
        for pattern, replacement in patterns:
            rewritten = re.sub(pattern, replacement, rewritten)
        return rewritten

    def load_input(self) -> str:
        from backend.config import settings
        summary_text = ""
        if self.db:
            summary = self.db.get_results_summary_json()
            if summary:
                summary_text = json.dumps(summary, indent=2, ensure_ascii=False)
        if settings.is_chinese():
            parts = [
                "以下 JSON 是研究阶段生成的确定性实验摘要，也是论文写作的唯一事实锚点。",
                "你写出的论文题目、任务、模型、数据集、结果、图表与结论，必须与这份 JSON 一致；如果不一致，就是错误草稿。",
                "先阅读并严格遵守这份 JSON，再使用 list_tasks 和 read_task_output 工具补充阅读已完成研究产出。",
                "使用 read_refined_idea 获取研究目标，使用 read_plan_tree 了解结构。",
                "使用 list_artifacts 核对可用图片，并只引用真实存在的文件。",
                "重要：当前草稿文件保存在 drafts/ 或 reviews/ 子目录中，因此图片和 artifacts 链接在草稿里必须写成 ../artifacts/... 形式。",
                "用 markdown 撰写完整论文。",
            ]
            if summary_text:
                parts.extend(["", "## 规范化实验摘要 JSON", summary_text])
            return "\n".join(parts)
        parts = [
            "The JSON below is the deterministic results summary from the research stage and is the sole factual anchor for the paper.",
            "The paper's topic, task, model, dataset, results, figures, and conclusions must match this JSON. If they do not match, the draft is wrong.",
            "Read and follow this JSON first, then use list_tasks and read_task_output to inspect completed research outputs in more detail.",
            "Use read_refined_idea for context and read_plan_tree for structure.",
            "Use list_artifacts to verify available images and cite only files that actually exist.",
            "Important: draft files are saved under drafts/ or reviews/, so image and artifact links inside drafts must use ../artifacts/... paths.",
            "Write the complete research paper in markdown.",
        ]
        if summary_text:
            parts.extend(["", "## Canonical Results Summary JSON", summary_text])
        return "\n".join(parts)

    def _save_round_md(self, dirname: str, text: str, iteration: int):
        adjusted = text
        if dirname in {self._primary_dir, self._reviewer_dir}:
            adjusted = self._rewrite_artifact_paths(text, "..")
        super()._save_round_md(dirname, adjusted, iteration)

    def _primary_config(self) -> tuple[str, list, str]:
        from backend.team.prompts import WRITE_WRITER_SYSTEM
        return WRITE_WRITER_SYSTEM, self._writer_tools, "Writer"

    def _reviewer_config(self) -> tuple[str, list, str]:
        from backend.team.prompts import WRITE_REVIEWER_SYSTEM
        return WRITE_REVIEWER_SYSTEM, self._reviewer_tools, "Reviewer"

    def _finalize(self) -> str:
        result = self._rewrite_artifact_paths(self.output, ".")
        if self.db:
            self.db.save_paper(result)
        return result
