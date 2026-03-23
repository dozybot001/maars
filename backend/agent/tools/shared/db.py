"""Shared tools available to all agents."""

from backend.db import ResearchDB


def create_db_tools(db: ResearchDB) -> list:
    """Create DB access tools bound to a specific research session."""

    def read_task_output(task_id: str) -> str:
        """Read the output of a previously completed task by its ID."""
        output = db.get_task_output(task_id)
        return output if output else f"No output found for task {task_id}"

    def save_task_output(task_id: str, content: str) -> str:
        """Save the output of a completed task."""
        db.save_task_output(task_id, content)
        return f"Saved output for task {task_id}"

    def read_refined_idea() -> str:
        """Read the refined research idea from the Refine stage."""
        return db.get_refined_idea() or "No refined idea available"

    return [read_task_output, save_task_output, read_refined_idea]
