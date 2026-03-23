import asyncio

from backend.db import ResearchDB
from backend.pipeline.stage import BaseStage, StageState

STAGE_ORDER = ["refine", "plan", "execute", "write"]


class PipelineOrchestrator:
    """Manages the four-stage research pipeline."""

    def __init__(self, stages: dict[str, BaseStage] | None = None):
        self.research_input = ""
        self.db = ResearchDB()

        # SSE subscribers — each connection gets its own queue
        self._subscribers: list[asyncio.Queue] = []

        # Merge: externally provided stages override, rest default to BaseStage
        self.stages: dict[str, BaseStage] = {
            name: BaseStage(name=name)
            for name in STAGE_ORDER
        }
        if stages:
            self.stages.update(stages)

        # Wire all stages to broadcast through us
        for stage in self.stages.values():
            stage._broadcast = self._broadcast

        # Track background tasks
        self._tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # SSE subscriber management
    # ------------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        """Create a per-connection queue. Call unsubscribe() on disconnect."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Remove a subscriber queue."""
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def _broadcast(self, event: dict):
        """Push an event to every active subscriber."""
        for q in self._subscribers:
            q.put_nowait(event)

    # ------------------------------------------------------------------
    # Task lifecycle helpers
    # ------------------------------------------------------------------

    async def _cancel_task(self, key: str):
        """Cancel a tracked task and wait for it to finish."""
        task = self._tasks.pop(key, None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def _cancel_all_tasks(self):
        """Cancel all tracked tasks."""
        keys = list(self._tasks.keys())
        for key in keys:
            await self._cancel_task(key)

    # ------------------------------------------------------------------
    # Pipeline-level operations
    # ------------------------------------------------------------------

    async def start(self, research_input: str):
        """Start the full pipeline from the beginning."""
        await self._cancel_all_tasks()

        self.research_input = research_input
        self.db.create_session(research_input)
        self.db.save_idea(research_input)

        for stage in self.stages.values():
            stage.retry()
            if stage.llm_client:
                stage.llm_client.reset()

        task = asyncio.create_task(self._run_all())
        self._tasks["pipeline"] = task

    async def _run_all(self):
        """Run all stages sequentially, saving outputs to DB."""
        for name in STAGE_ORDER:
            try:
                await self.run_stage(name)
                if self.stages[name].state != StageState.COMPLETED:
                    break
                self._save_stage_output(name)
            except asyncio.CancelledError:
                raise
            except Exception:
                break

    def _save_stage_output(self, stage_name: str):
        """Persist stage output to the research DB."""
        stage = self.stages[stage_name]
        if stage_name == "refine":
            self.db.save_refined_idea(stage.output)
        elif stage_name == "plan":
            self.db.save_plan(stage.output, stage.get_artifacts())
        elif stage_name == "write":
            self.db.save_paper(stage.output)

    # ------------------------------------------------------------------
    # Stage-level operations
    # ------------------------------------------------------------------

    async def run_stage(self, stage_name: str):
        """Run a single stage. Input comes from the previous stage's output."""
        stage = self.stages[stage_name]
        input_text = self._get_stage_input(stage_name)
        await stage.run(input_text)

    def check_runnable(self, stage_name: str) -> str | None:
        """Return an error message if this stage cannot run, or None if OK."""
        idx = STAGE_ORDER.index(stage_name)
        if idx == 0:
            return None
        prev = self.stages[STAGE_ORDER[idx - 1]]
        if prev.state != StageState.COMPLETED:
            return f"Previous stage '{prev.name}' has not completed"
        return None

    async def run_stage_background(self, stage_name: str):
        """Cancel any existing task for this stage, then launch a new one."""
        await self._cancel_task(stage_name)
        task = asyncio.create_task(self.run_stage(stage_name))
        self._tasks[stage_name] = task

    def stop_stage(self, stage_name: str):
        self.stages[stage_name].stop()

    def resume_stage(self, stage_name: str):
        self.stages[stage_name].resume()

    async def retry_stage(self, stage_name: str):
        """Reset and re-run a stage from scratch.

        Also invalidates all downstream stages since their inputs
        are now stale.
        """
        await self._cancel_task("pipeline")

        idx = STAGE_ORDER.index(stage_name)
        for name in STAGE_ORDER[idx:]:
            await self._cancel_task(name)
            self.stages[name].retry()

        task = asyncio.create_task(self.run_stage(stage_name))
        self._tasks[stage_name] = task

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "input": self.research_input,
            "stages": [self.stages[name].get_status() for name in STAGE_ORDER],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_stage_input(self, stage_name: str) -> str:
        """Determine the input for a given stage."""
        idx = STAGE_ORDER.index(stage_name)
        if idx == 0:
            return self.research_input
        prev_name = STAGE_ORDER[idx - 1]
        prev_stage = self.stages[prev_name]
        if prev_stage.state != StageState.COMPLETED:
            raise RuntimeError(f"Cannot run '{stage_name}': previous stage '{prev_name}' not completed")
        return prev_stage.output
