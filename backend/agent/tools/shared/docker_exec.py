"""Docker-based code execution tools for agents.

Runs code in isolated containers with file artifacts persisted
to research/{id}/artifacts/. Scripts are kept alongside outputs
for full reproducibility.

After all experiments, generate_reproduce_files() creates
Dockerfile + run.sh + docker-compose.yml for one-command reproduction.
"""

import json
import hashlib
import time
from pathlib import Path

from backend.config import settings
from backend.db import ResearchDB

# NOTE: generate_reproduce_files() lives in backend/reproduce.py (not here)
# to avoid circular dependency between pipeline/ and agent/.

def create_docker_tools(db: ResearchDB) -> list:
    """Create Docker execution tools bound to a research session."""

    def code_execute(code: str, language: str = "python", requirements: str = "") -> str:
        """Execute code in an isolated Docker container.

        Args:
            code: Source code to execute.
            language: 'python' (default). More languages in the future.
            requirements: Space-separated pip packages to install before execution.

        Returns:
            JSON with: stdout, stderr, exit_code, timed_out, files (list of artifact filenames).

        Files written to /workspace/output/ inside the container are persisted
        to the research session's artifacts directory. The script itself is
        also preserved for reproducibility.
        """
        try:
            import docker
        except ImportError:
            return json.dumps({"error": "Docker SDK not installed. pip install docker"})

        try:
            client = docker.from_env()
        except Exception as e:
            return json.dumps({"error": f"Docker not available: {e}"})

        # Prepare directories
        artifacts_dir = db.get_artifacts_dir()
        tasks_dir = db.get_root() / "tasks" if db.research_id else None

        # Write script with a unique name
        timestamp = int(time.time())
        code_hash = hashlib.md5(code.encode()).hexdigest()[:6]
        ext = ".py" if language == "python" else ".r"
        script_name = f"run_{timestamp}_{code_hash}{ext}"
        script_path = artifacts_dir / script_name
        script_path.write_text(code, encoding="utf-8")

        # Track this execution for reproduce file generation
        db.execution_log.append({
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
            str(artifacts_dir.resolve()): {"bind": "/workspace/output", "mode": "rw"},
        }
        if tasks_dir and tasks_dir.exists():
            volumes[str(tasks_dir.resolve())] = {"bind": "/workspace/input", "mode": "ro"}

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

            # Wait with timeout
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

        # List all files in artifacts (including the script)
        files = sorted(f.name for f in artifacts_dir.iterdir() if f.is_file())

        return json.dumps({
            "stdout": stdout[-5000:],
            "stderr": stderr[-2000:],
            "exit_code": exit_code,
            "timed_out": timed_out,
            "script": script_name,
            "files": files,
        }, indent=2)

    def list_artifacts() -> str:
        """List all files in the artifacts directory for this research session.
        Includes experiment scripts and their outputs."""
        try:
            artifacts_dir = db.get_artifacts_dir()
        except RuntimeError:
            return "No active research session."

        files = []
        for f in sorted(artifacts_dir.iterdir()):
            if f.is_file():
                files.append({"filename": f.name, "size_bytes": f.stat().st_size})

        if not files:
            return "No artifacts produced yet."
        return json.dumps(files, indent=2)

    return [code_execute, list_artifacts]
