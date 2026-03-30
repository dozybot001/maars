import asyncio

from backend.db import ResearchDB
from backend.pipeline.stage import Stage, StageState

STAGE_ORDER = ["refine", "research", "write"]


class PipelineOrchestrator:
    """Manages the research pipeline: Refine → Research → Write."""

    def __init__(self, stages: dict[str, Stage] | None = None):
        self.research_input = ""
        self.db = ResearchDB()

        # SSE subscribers — each connection gets its own queue
        self._subscribers: list[asyncio.Queue] = []

        # Merge: externally provided stages override, rest default to Stage
        self.stages: dict[str, Stage] = {
            name: Stage(name=name)
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
        """Start the pipeline. Auto-detects Kaggle URLs to fetch competition data."""
        from backend.kaggle import extract_competition_id

        await self._cancel_all_tasks()

        # Detect Kaggle competition URL
        kaggle_id = extract_competition_id(research_input)
        if kaggle_id:
            # Kaggle: fetch data + create session BEFORE retry (retry emits events that need DB)
            self._start_kaggle(research_input, kaggle_id)
            self._reset_stages()
            self._mark_refine_done()
            task = asyncio.create_task(self._run_from("research"))
        else:
            self.research_input = research_input
            self.db.create_session(research_input)
            self.db.save_idea(research_input)
            self._reset_stages()
            task = asyncio.create_task(self._run_from("refine"))

        self._tasks["pipeline"] = task

    def _reset_stages(self):
        """Reset all stages for a fresh run."""
        for stage in self.stages.values():
            stage.retry()
            llm_client = getattr(stage, "llm_client", None)
            if llm_client:
                llm_client.reset()

    def _start_kaggle(self, raw_input: str, competition_id: str):
        """Set up Kaggle mode: fetch data, build refined idea, skip Refine."""
        import re
        from backend.kaggle import fetch_competition, build_kaggle_idea
        from backend.config import settings

        info = fetch_competition(competition_id)

        settings.dataset_dir = info["data_dir"]
        settings.kaggle_competition_id = competition_id

        # Build rich refined idea from competition metadata + data files
        refined = build_kaggle_idea(info)
        user_hint = re.sub(r'https?://\S+', '', raw_input).strip()
        if user_hint:
            refined += f"\n## User Notes\n\n{user_hint}\n"

        self.research_input = refined
        self.db.create_session(info["title"])
        self.db.save_idea(raw_input)
        self.db.save_refined_idea(refined)

    def _mark_refine_done(self):
        """Mark Refine as completed (Kaggle mode skips it). Call AFTER _reset_stages."""
        refine = self.stages["refine"]
        refine.output = self.research_input
        refine.state = StageState.COMPLETED
        self._broadcast({"stage": "refine", "type": "state", "data": "completed"})
        self._broadcast({"stage": "refine", "type": "document", "data": {
            "name": "refined_idea", "label": "Refined Idea", "content": self.research_input,
        }})

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
        # Emit pausing state for frontend transition
        stage._emit("state", "pausing")
        llm_client = getattr(stage, "llm_client", None)
        if llm_client:
            llm_client.request_stop()
        # Kill any running Docker containers immediately
        from backend.agno.tools.docker_exec import kill_all_containers
        kill_all_containers()
        # Invalidate current run so CancelledError handler won't change state
        stage._run_id += 1
        await self._cancel_task("pipeline")
        stage.state = StageState.PAUSED
        stage._emit("state", stage.state.value)

    async def resume_stage(self, stage_name: str):
        """Resume a paused stage, then auto-continue remaining stages.

        Research stage loads checkpoint from DB and skips completed tasks.
        Other stages restart from scratch (resume ≡ retry for single-session stages).
        """
        stage = self.stages[stage_name]
        if stage.state != StageState.PAUSED:
            return
        stage.output = ""
        if hasattr(stage, "rounds"):
            stage.rounds = []
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
