"""Generate Docker reproduction files from a research session's execution log.

Creates standard Docker artifacts (Dockerfile + run.sh + docker-compose.yml)
so that `docker compose up` re-runs all experiments in order.

This module lives at the backend top level — it depends only on db and config,
avoiding a circular dependency between pipeline/ and agent/.
"""

from backend.config import settings
from backend.db import ResearchDB


def generate_reproduce_files(db: ResearchDB):
    """Generate Docker reproduction files from the execution log.

    Creates in the research root:
    - Dockerfile.experiment — environment with all dependencies
    - scripts/ — copies of all experiment scripts (ordered)
    - run.sh — executes all scripts in order
    - docker-compose.yml — one-command reproduction

    Called automatically by ExecuteStage._build_final_output().
    """
    if not db.execution_log:
        return

    if not db.research_id:
        return
    root = db.get_root()

    scripts_dir = root / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    artifacts_dir = root / "artifacts"

    # Collect unique requirements and ordered scripts
    all_requirements: set[str] = set()
    ordered_scripts: list[str] = []

    for entry in db.execution_log:
        script_name = entry["script"]
        if entry["requirements"]:
            for pkg in entry["requirements"].split():
                all_requirements.add(pkg)
        ordered_scripts.append(script_name)

        # Copy script to scripts/ directory
        src = artifacts_dir / script_name
        if src.exists():
            (scripts_dir / script_name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # --- Dockerfile.experiment ---
    pip_line = ""
    if all_requirements:
        pip_line = f"RUN pip install --no-cache-dir {' '.join(sorted(all_requirements))}\n"

    dockerfile = f"""\
FROM {settings.docker_sandbox_image}
USER root
{pip_line}COPY scripts/ /workspace/scripts/
COPY run.sh /workspace/run.sh
RUN chmod +x /workspace/run.sh && chown -R sandbox:sandbox /workspace
USER sandbox
WORKDIR /workspace
CMD ["bash", "run.sh"]
"""
    (root / "Dockerfile.experiment").write_text(dockerfile, encoding="utf-8")

    # --- run.sh ---
    lines = ["#!/bin/bash", "set -e", "mkdir -p /workspace/results", ""]
    for script in ordered_scripts:
        lines.append(f'echo "=== Running {script} ==="')
        lines.append(f"cd /workspace/results && python /workspace/scripts/{script}")
        lines.append("")
    lines.append('echo "All experiments completed. Results in /workspace/results/"')

    (root / "run.sh").write_text("\n".join(lines), encoding="utf-8")

    # --- docker-compose.yml ---
    compose = """\
services:
  experiment:
    build:
      context: .
      dockerfile: Dockerfile.experiment
    volumes:
      - ./results:/workspace/results
"""
    (root / "docker-compose.yml").write_text(compose, encoding="utf-8")

    # Clear log for next session
    db.execution_log.clear()
