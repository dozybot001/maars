"""Docker-based code execution tools for agents."""

import asyncio
import json
import threading
from pathlib import Path

from backend.config import settings
from backend.db import ResearchDB

_active_containers: list = []
_containers_lock = threading.Lock()


def kill_all_containers():
    with _containers_lock:
        snapshot = list(_active_containers)
    for container in snapshot:
        try:
            container.kill()
        except Exception:
            pass


def _get_docker_client():
    import docker
    return docker.from_env()


def _run_container(client, shell_cmd, volumes, timeout):
    run_kwargs = dict(
        image=settings.docker_sandbox_image,
        command=["bash", "-c", shell_cmd],
        volumes=volumes,
        mem_limit=settings.docker_sandbox_memory,
        cpu_quota=int(settings.docker_sandbox_cpu * 100000),
        network_disabled=not settings.docker_sandbox_network,
        detach=True,
    )
    if settings.docker_sandbox_gpu:
        import docker
        run_kwargs["device_requests"] = [
            docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])
        ]
    container = client.containers.run(**run_kwargs)
    with _containers_lock:
        _active_containers.append(container)

    try:
        result = container.wait(timeout=timeout)
        exit_code = result["StatusCode"]
        timed_out = False
    except Exception:
        try:
            container.kill()
        except Exception:
            pass
        exit_code = -1
        timed_out = True

    stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
    stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
    container.remove(force=True)

    with _containers_lock:
        try:
            _active_containers.remove(container)
        except ValueError:
            pass

    return stdout, stderr, exit_code, timed_out


def create_docker_tools(db: ResearchDB) -> list:
    async def code_execute(code: str, language: str = "python", requirements: str = "") -> str:
        """Execute code in an isolated Docker container."""
        try:
            client = _get_docker_client()
        except Exception as e:
            return json.dumps({"error": str(e)})

        script_path, script_name = db.save_script(code, language)
        task_artifacts = script_path.parent
        artifacts_root = db.get_artifacts_dir()
        tasks_dir = db.get_tasks_dir() if db.research_id else None

        db.append_execution_log(
            task_id=db.current_task_id or "",
            script=script_name,
            language=language,
            requirements=requirements.strip(),
        )

        cmd_parts = []
        if requirements.strip():
            cmd_parts.append(f"pip install --quiet {requirements}")
        cmd_parts.append(f"cd /workspace/output && {language} /workspace/output/{script_name}")
        shell_cmd = " && ".join(cmd_parts)

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

        try:
            stdout, stderr, exit_code, timed_out = await asyncio.to_thread(
                _run_container, client, shell_cmd, volumes, settings.docker_sandbox_timeout,
            )
        except Exception as e:
            return json.dumps({"error": f"Container execution failed: {e}"})

        db.promote_best_score()
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
        """List all files in the artifacts directory. During task execution, lists the current task's artifacts. Otherwise (e.g. Write stage), lists all artifacts recursively with relative paths."""
        try:
            task_id = db.current_task_id
            artifacts_dir = db.get_artifacts_dir(task_id)
        except RuntimeError:
            return "No active research session."
        files = []
        if task_id:
            for f in sorted(artifacts_dir.iterdir()):
                if f.is_file():
                    files.append({"filename": f.name, "size_bytes": f.stat().st_size})
        else:
            for f in sorted(artifacts_dir.rglob("*")):
                if f.is_file():
                    rel = str(f.relative_to(artifacts_dir))
                    files.append({"path": rel, "size_bytes": f.stat().st_size})
        return json.dumps(files, indent=2) if files else "No artifacts produced yet."

    return [code_execute, list_artifacts]
