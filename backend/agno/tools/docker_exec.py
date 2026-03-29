"""Docker-based code execution tools for agents.

Runs code in isolated containers with file artifacts persisted
to research/{id}/artifacts/{task_id}/. All file operations go
through ResearchDB.
"""

import json
from pathlib import Path

from backend.config import settings
from backend.db import ResearchDB


def create_docker_tools(db: ResearchDB) -> list:
    """Create Docker execution tools bound to a research session."""

    def code_execute(code: str, language: str = "python", requirements: str = "") -> str:
        """Execute code in an isolated Docker container.

        Args:
            code: Source code to execute.
            language: 'python' (default).
            requirements: Space-separated pip packages to install before execution.

        Returns:
            JSON with: stdout, stderr, exit_code, timed_out, files.
        """
        try:
            import docker
        except ImportError:
            return json.dumps({"error": "Docker SDK not installed. pip install docker"})

        try:
            client = docker.from_env()
        except Exception as e:
            return json.dumps({"error": f"Docker not available: {e}"})

        # Save script via DB
        script_path, script_name = db.save_script(code, language)
        task_artifacts = script_path.parent
        artifacts_root = db.get_artifacts_dir()
        tasks_dir = db.get_tasks_dir() if db.research_id else None

        # Track for reproduce file generation
        db.execution_log.append({
            "task_id": db.current_task_id or "",
            "script": script_name,
            "language": language,
            "requirements": requirements.strip(),
        })

        # Build command
        cmd_parts = []
        if requirements.strip():
            cmd_parts.append(f"pip install --quiet {requirements}")
        cmd_parts.append(f"cd /workspace/output && {language} /workspace/output/{script_name}")
        shell_cmd = " && ".join(cmd_parts)

        # Volume mounts
        volumes = {
            str(task_artifacts.resolve()): {"bind": "/workspace/output", "mode": "rw"},
            str(artifacts_root.resolve()): {"bind": "/workspace/artifacts", "mode": "ro"},
        }
        if tasks_dir and tasks_dir.exists():
            volumes[str(tasks_dir.resolve())] = {"bind": "/workspace/input", "mode": "ro"}
        if settings.dataset_dir:
            dataset_path = Path(settings.dataset_dir).resolve()
            if dataset_path.exists():
                volumes[str(dataset_path)] = {"bind": "/workspace/data", "mode": "ro"}

        # Run container
        try:
            container = client.containers.run(
                image=settings.docker_sandbox_image,
                command=["bash", "-c", shell_cmd],
                volumes=volumes,
                mem_limit=settings.docker_sandbox_memory,
                cpu_quota=int(settings.docker_sandbox_cpu * 100000),
                network_disabled=not settings.docker_sandbox_network,
                detach=True,
            )

            try:
                result = container.wait(timeout=settings.docker_sandbox_timeout)
                exit_code = result["StatusCode"]
                timed_out = False
            except Exception:
                container.kill()
                exit_code = -1
                timed_out = True

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            container.remove(force=True)

        except Exception as e:
            return json.dumps({"error": f"Container execution failed: {e}"})

        # Auto-promote best_score.json via DB
        db.promote_best_score()

        # List files in this task's artifacts
        files = sorted(f.name for f in task_artifacts.iterdir() if f.is_file())

        return json.dumps({
            "stdout": stdout[-5000:],
            "stderr": stderr[-2000:],
            "exit_code": exit_code,
            "timed_out": timed_out,
            "script": script_name,
            "files": files,
        }, indent=2)

    def list_artifacts() -> str:
        """List all files in the current task's artifacts directory."""
        try:
            artifacts_dir = db.get_artifacts_dir(db.current_task_id)
        except RuntimeError:
            return "No active research session."

        files = []
        for f in sorted(artifacts_dir.iterdir()):
            if f.is_file():
                files.append({"filename": f.name, "size_bytes": f.stat().st_size})

        return json.dumps(files, indent=2) if files else "No artifacts produced yet."

    return [code_execute, list_artifacts]
