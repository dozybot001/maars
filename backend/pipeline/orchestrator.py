import asyncio

from backend.db import ResearchDB
from backend.pipeline.stage import BaseStage, StageState

STAGE_ORDER = ["refine", "research", "write"]


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

        # Wire all stages (and their clients) to broadcast through us
        self._wire_broadcast()

        # Track background tasks
        self._tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # SSE subscriber management
    # ------------------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        """Create a per-connection queue. Call unsubscribe() on disconnect."""
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Remove a subscriber queue."""
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def _broadcast(self, event: dict):
        """Push an event to every active subscriber. Drop if queue full."""
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def _wire_broadcast(self):
        """Inject broadcast callback into all stages."""
        for stage in self.stages.values():
            stage._broadcast = self._broadcast

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

        task = asyncio.create_task(self._run_from("refine"))
        self._tasks["pipeline"] = task

    async def start_kaggle(self, competition_id: str, data_dir: str = "data"):
        """Start pipeline in Kaggle mode: fetch competition → skip Refine → Research.

        Downloads dataset, constructs a structured idea from competition metadata,
        saves it as both idea and refined_idea, then starts from the Research stage.
        """
        from backend.kaggle import fetch_competition, build_kaggle_idea
        from backend.config import settings

        await self._cancel_all_tasks()

        info = fetch_competition(competition_id, data_dir=data_dir)

        # Point Docker sandbox to the downloaded data + enable Kaggle scoring
        settings.dataset_dir = info["data_dir"]
        settings.kaggle_competition_id = competition_id

        idea = build_kaggle_idea(info)
        self.research_input = idea
        self.db.create_session(info["title"])
        self.db.save_idea(idea)
        self.db.save_refined_idea(idea)  # Skip Refine — idea IS the refined idea

        for stage in self.stages.values():
            stage.retry()
            if stage.llm_client:
                stage.llm_client.reset()

        # Mark Refine as completed (skipped)
        refine = self.stages["refine"]
        refine.output = idea
        refine.state = StageState.COMPLETED
        self._broadcast({"stage": "refine", "type": "state", "data": "completed"})

        task = asyncio.create_task(self._run_from("research"))
        self._tasks["pipeline"] = task

    async def _run_from(self, stage_name: str):
        """Run stages sequentially from the given stage to the end."""
        idx = STAGE_ORDER.index(stage_name)
        for name in STAGE_ORDER[idx:]:
            try:
                stage = self.stages[name]
                await stage.run()
                if stage.state != StageState.COMPLETED:
                    break
            except asyncio.CancelledError:
                raise
            except Exception:
                break

    # ------------------------------------------------------------------
    # Stage-level operations
    # ------------------------------------------------------------------

    async def stop_stage(self, stage_name: str):
        """Stop a running stage by cancelling its task.

        Sets state to PAUSED so the user can resume (checkpoint restart)
        or retry (clean restart).
        """
        stage = self.stages[stage_name]
        if stage.state != StageState.RUNNING:
            return
        if stage.llm_client:
            stage.llm_client.request_stop()
        # Invalidate current run so CancelledError handler won't change state
        stage._run_id += 1
        await self._cancel_task("pipeline")
        stage.state = StageState.PAUSED
        stage._emit("state", stage.state.value)

    async def resume_stage(self, stage_name: str):
        """Resume a paused stage, then auto-continue remaining stages.

        Execute stage loads checkpoint from DB and skips completed tasks.
        Other stages restart from scratch (resume ≡ retry for single-session stages).
        """
        stage = self.stages[stage_name]
        if stage.state != StageState.PAUSED:
            return
        stage.output = ""
        stage.rounds = []
        task = asyncio.create_task(self._run_from(stage_name))
        self._tasks["pipeline"] = task

    async def retry_stage(self, stage_name: str):
        """Reset and re-run a stage from scratch, then auto-continue.

        Also invalidates all downstream stages since their inputs
        are now stale.
        """
        await self._cancel_task("pipeline")

        idx = STAGE_ORDER.index(stage_name)
        for name in STAGE_ORDER[idx:]:
            self.stages[name].retry()

        task = asyncio.create_task(self._run_from(stage_name))
        self._tasks["pipeline"] = task

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "input": self.research_input,
            "stages": [self.stages[name].get_status() for name in STAGE_ORDER],
        }

