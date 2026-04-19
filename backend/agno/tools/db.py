"""DB access tools for agents — scoped to pipeline-defined boundaries."""

import json
from pathlib import Path
from backend.db import ResearchDB


def create_db_tools(db: ResearchDB) -> list:
    def read_task_output(task_id: str) -> str:
        """Read the output of a previously completed task by its ID."""
        output = db.get_task_output(task_id)
        return output if output else f"No output found for task {task_id}"

    def list_tasks() -> str:
        """List all research tasks with their IDs, descriptions, summaries, and status."""
        tasks = db.get_plan_list()
        if not tasks:
            return "No tasks available."
        result = []
        for t in tasks:
            result.append({
                "id": t.get("id", ""),
                "description": t.get("description", ""),
                "summary": t.get("summary", ""),
                "status": t.get("status", "unknown"),
            })
        return json.dumps(result, indent=2, ensure_ascii=False)

    def read_refined_idea() -> str:
        """Read the refined research idea produced by the Refine stage."""
        return db.get_refined_idea() or "No refined idea available."

    def read_plan_tree() -> str:
        """Read the full decomposition tree."""
        tree = db.get_plan_tree()
        return json.dumps(tree, indent=2) if tree else "No plan tree available."

    def read_results_summary() -> str:
        """Read the deterministic summary of completed research results."""
        summary = db.get_results_summary()
        return summary if summary else "No results summary available."

    def read_artifact_file(path: str) -> str:
        """Read the text content of an artifact file produced during research.

        Use this to verify exact numeric values before writing or reviewing any
        data table. Always call this for every JSON metrics file referenced in
        the paper — never infer or approximate numbers without reading the source.

        Args:
            path: Relative path under artifacts/, e.g. '1/grayscale_metrics.json'
                  or 'r1_4/final_performance_report.json'.
                  Call list_artifacts first to discover available files.
        """
        try:
            artifacts_root = db.get_artifacts_dir()
            target = (artifacts_root / path).resolve()
            if not str(target).startswith(str(artifacts_root.resolve())):
                return "Error: path escapes artifacts directory."
            if not target.exists():
                return f"File not found: {path}"
            if not target.is_file():
                return f"Not a file: {path}"
            if target.stat().st_size > 512_000:
                return f"File too large to read inline ({target.stat().st_size} bytes). Use a summary instead."
            return target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading {path}: {e}"

    return [
        read_task_output,
        list_tasks,
        read_refined_idea,
        read_plan_tree,
        read_results_summary,
        read_artifact_file,
    ]
