"""
Artifact resolution: load input artifacts from dependency tasks.
"""

from typing import Any, Dict

from db import get_task_artifact


async def resolve_artifacts(
    task: Dict[str, Any],
    task_map: Dict[str, Dict],
    plan_id: str,
) -> Dict[str, Any]:
    """
    Resolve input artifacts from dependency tasks.
    For each dep_id in task.dependencies, load the dep's output artifact from db.
    Returns { artifact_name: value }.
    """
    deps = task.get("dependencies") or []
    if not deps:
        return {}

    result: Dict[str, Any] = {}
    for dep_id in deps:
        dep_task = task_map.get(dep_id)
        if not dep_task:
            continue
        output_spec = dep_task.get("output") or {}
        artifact_name = output_spec.get("artifact")
        if not artifact_name:
            continue
        value = await get_task_artifact(plan_id, dep_id)
        if value is not None:
            result[artifact_name] = value
    return result
