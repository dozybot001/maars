"""DB access tools for agents — scoped to pipeline-defined boundaries."""

import json
from backend.db import ResearchDB


def create_db_tools(db: ResearchDB) -> list:
    """Create DB tools bound to a specific research session."""

    def read_task_output(task_id: str) -> str:
        """Read the output of a previously completed task by its ID.
        Use list_tasks first to see available task IDs."""
        output = db.get_task_output(task_id)
        return output if output else f"No output found for task {task_id}"

    def list_tasks() -> str:
        """List all completed atomic tasks with their IDs and output sizes.
        Returns a JSON array of {id, size_bytes}."""
        tasks = db.list_completed_tasks()
        if not tasks:
            return "No tasks completed yet."
        return json.dumps(tasks, indent=2)

    def read_refined_idea() -> str:
        """Read the refined research idea produced by the Refine stage."""
        return db.get_refined_idea() or "No refined idea available."

    def read_plan_tree() -> str:
        """Read the full decomposition tree from the Plan stage.
        Shows the hierarchical task structure with dependencies."""
        tree = db.get_plan_tree()
        return tree if tree else "No plan tree available."

    def save_task_output(task_id: str, content: str) -> str:
        """Save the output of a completed task."""
        db.save_task_output(task_id, content)
        return f"Saved output for task {task_id}"

    return [read_task_output, list_tasks, read_refined_idea, read_plan_tree, save_task_output]
