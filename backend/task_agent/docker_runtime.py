"""Local Docker runtime helpers for Task Agent execution."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

DEFAULT_DOCKER_IMAGE = os.getenv("MAARS_DOCKER_IMAGE", "python:3.11-slim")
DOCKER_COMMAND_TIMEOUT = int(os.getenv("MAARS_DOCKER_COMMAND_TIMEOUT", "120"))
_DOCKER_KEEPALIVE_CMD = "trap : TERM INT; while sleep 3600; do :; done"


def _bootstrap_keepalive_cmd(*, plan_mount: str, run_mount: str) -> str:
    return (
        f"mkdir -p {shlex.quote(run_mount)} && "
        f"ln -sfn {shlex.quote(run_mount)} /workdir && "
        f"ln -sfn {shlex.quote(plan_mount)} /plan && "
        f"{_DOCKER_KEEPALIVE_CMD}"
    )


def _docker_bin() -> str:
    return shutil.which("docker") or ""


def _sanitize_name(value: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip())
    raw = raw.strip("-._") or "run"
    return raw[:63]


async def _run_docker_cmd(args: list[str], timeout: int = DOCKER_COMMAND_TIMEOUT) -> dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {
            "ok": False,
            "code": -1,
            "stdout": "",
            "stderr": f"Timed out after {timeout}s",
            "args": args,
        }
    return {
        "ok": proc.returncode == 0,
        "code": proc.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "args": args,
    }


async def get_local_docker_status(*, enabled: bool = True, container_name: str | None = None) -> dict[str, Any]:
    docker = _docker_bin()
    base: dict[str, Any] = {
        "enabled": bool(enabled),
        "available": bool(docker),
        "connected": False,
        "image": DEFAULT_DOCKER_IMAGE,
        "dockerPath": docker,
        "containerName": container_name or "",
        "containerRunning": False,
    }
    if not docker:
        base["error"] = "Docker CLI not found in PATH"
        return base

    info = await _run_docker_cmd([docker, "info", "--format", "{{.ServerVersion}}"], timeout=20)
    if not info["ok"]:
        base["error"] = (info.get("stderr") or info.get("stdout") or "Docker daemon unavailable").strip()
        return base

    base["connected"] = True
    base["serverVersion"] = (info.get("stdout") or "").strip()

    if container_name:
        inspect = await _run_docker_cmd(
            [docker, "inspect", "-f", "{{.State.Running}}", container_name],
            timeout=10,
        )
        if inspect["ok"]:
            base["containerRunning"] = (inspect.get("stdout") or "").strip().lower() == "true"
    return base


def build_container_name(execution_run_id: str) -> str:
    return f"maars-exec-{_sanitize_name(execution_run_id)}"


async def ensure_execution_container(
    *,
    execution_run_id: str,
    run_dir: Path,
    plan_dir: Path,
    skills_dir: Path,
    image: str | None = None,
) -> dict[str, Any]:
    docker = _docker_bin()
    if not docker:
        raise RuntimeError("Docker CLI not found in PATH")

    run_dir = run_dir.resolve()
    plan_dir = plan_dir.resolve()
    skills_dir = skills_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    plan_dir.mkdir(parents=True, exist_ok=True)

    image_name = (image or DEFAULT_DOCKER_IMAGE).strip() or DEFAULT_DOCKER_IMAGE
    container_name = build_container_name(execution_run_id)

    status = await get_local_docker_status(enabled=True, container_name=container_name)
    if not status.get("connected"):
        raise RuntimeError(status.get("error") or "Docker daemon unavailable")
    if status.get("containerRunning"):
        return {
            **status,
            "containerName": container_name,
            "image": image_name,
            "runDir": str(run_dir),
            "planDir": str(plan_dir),
        }

    inspect = await _run_docker_cmd([docker, "inspect", container_name], timeout=10)
    if inspect["ok"]:
        started = await _run_docker_cmd([docker, "start", container_name], timeout=20)
        if not started["ok"]:
            raise RuntimeError(started.get("stderr") or started.get("stdout") or "Failed to start Docker container")
        return {
            **status,
            "connected": True,
            "containerRunning": True,
            "containerName": container_name,
            "image": image_name,
            "runDir": str(run_dir),
            "planDir": str(plan_dir),
        }

    db_root_dir = plan_dir.parent.parent.resolve()
    plan_mount_path = f"/dbroot/{plan_dir.relative_to(db_root_dir).as_posix()}"
    run_mount_path = f"/dbroot/{run_dir.relative_to(db_root_dir).as_posix()}"

    run_cmd = [
        docker,
        "run",
        "-d",
        "--name",
        container_name,
        "--workdir",
        "/workdir",
        "--mount",
        f"type=bind,src={db_root_dir},dst=/dbroot",
        "--mount",
        f"type=bind,src={skills_dir},dst=/skills,readonly",
        "--mount",
        "type=tmpfs,dst=/tmp",
        image_name,
        "sh",
        "-lc",
        _bootstrap_keepalive_cmd(plan_mount=plan_mount_path, run_mount=run_mount_path),
    ]
    created = await _run_docker_cmd(run_cmd, timeout=40)
    if not created["ok"]:
        raise RuntimeError(created.get("stderr") or created.get("stdout") or "Failed to create Docker execution container")

    logger.info("Docker execution container ready run_id={} container={} image={}", execution_run_id, container_name, image_name)
    return {
        "enabled": True,
        "available": True,
        "connected": True,
        "containerRunning": True,
        "containerName": container_name,
        "image": image_name,
        "runDir": str(run_dir),
        "planDir": str(plan_dir),
    }


async def run_command_in_container(
    *,
    container_name: str,
    command: str,
    workdir: str,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    docker = _docker_bin()
    if not docker:
        raise RuntimeError("Docker CLI not found in PATH")
    if not container_name:
        raise RuntimeError("Docker container is not initialized")
    timeout = max(1, int(timeout_seconds or DOCKER_COMMAND_TIMEOUT))
    args = [docker, "exec", "-w", workdir, container_name, "sh", "-lc", command]
    result = await _run_docker_cmd(args, timeout=timeout)
    logger.info(
        "Docker exec container={} workdir={} timeout_s={} exit_code={} command={}",
        container_name,
        workdir,
        timeout,
        result.get("code"),
        command,
    )
    return result


async def run_skill_script_in_container(
    *,
    container_name: str,
    task_id: str,
    skill: str,
    script_rel_path: str,
    args: list[str] | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    ext = Path(script_rel_path).suffix.lower()
    script_path = f"/skills/{skill}/{script_rel_path.lstrip('/')}"
    workspace_dir = f"/workdir/{task_id}/workspace"
    resolved_args = [
        str(a).replace("[[sandbox]]", workspace_dir).replace("{{sandbox}}", workspace_dir)
        for a in (args or [])
    ]
    if ext == ".py":
        command = "python " + " ".join(shlex.quote(part) for part in [script_path, *resolved_args])
    elif ext == ".sh":
        command = "sh " + " ".join(shlex.quote(part) for part in [script_path, *resolved_args])
    elif ext == ".js":
        command = "node " + " ".join(shlex.quote(part) for part in [script_path, *resolved_args])
    else:
        raise RuntimeError(f"Unsupported script extension: {ext}")
    return await run_command_in_container(
        container_name=container_name,
        command=command,
        workdir=f"/skills/{skill}",
        timeout_seconds=timeout_seconds,
    )


async def stop_execution_container(container_name: str) -> None:
    docker = _docker_bin()
    if not docker or not container_name:
        return
    result = await _run_docker_cmd([docker, "rm", "-f", container_name], timeout=20)
    if result["ok"]:
        logger.info("Docker execution container removed container={}", container_name)
    else:
        logger.warning(
            "Failed to remove Docker execution container {}: {}",
            container_name,
            (result.get("stderr") or result.get("stdout") or "").strip(),
        )
