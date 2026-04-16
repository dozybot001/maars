import asyncio
import logging

from backend.db import ResearchDB
from backend.pipeline.stage import Stage, StageState

STAGE_ORDER = ["refine", "research", "write", "polish"]


class PipelineOrchestrator:
    """Manages the research pipeline: Refine → Research → Write."""

    def __init__(self):
        from backend.config import settings
        self.research_input = ""
        self.db = ResearchDB()
        self._subscribers: set[asyncio.Queue] = set()
        self.stages: dict[str, Stage] = {
            name: Stage(name=name) for name in STAGE_ORDER
        }
        self._pipeline_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._api_semaphore = asyncio.Semaphore(settings.api_concurrency)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1024)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)

    async def start(self, research_input: str):
        async with self._lock:
            from backend.kaggle import extract_competition_id
            await self._cancel_pipeline()
            kaggle_id = extract_competition_id(research_input)
            if kaggle_id:
                await asyncio.to_thread(self._start_kaggle, research_input, kaggle_id)
                self._reset_stages()
                self._mark_refine_done()
                self._pipeline_task = asyncio.create_task(self._run_from("research"))
            else:
                self.research_input = research_input
                self.db.create_session(research_input)
                self.db.save_idea(research_input)
                self._reset_stages()
                self._pipeline_task = asyncio.create_task(self._run_from("refine"))

    async def stop(self):
        async with self._lock:
            stage = self._find_stage(StageState.RUNNING)
            if not stage:
                return
            stage.request_stop()
            self._kill_containers()
            await self._cancel_pipeline(timeout=5.0)
            stage.pause()

    async def resume(self):
        async with self._lock:
            stage = self._find_stage(StageState.PAUSED)
            if not stage:
                return
            stage.prepare_resume()
            self._pipeline_task = asyncio.create_task(self._run_from(stage.name))

    async def run_stage(self, stage_name: str, session_id: str | None = None,
                        clear_outputs: bool = True):
        if stage_name not in STAGE_ORDER:
            raise RuntimeError(f"Unknown stage '{stage_name}'")
        async with self._lock:
            await self._cancel_pipeline()
            self._kill_containers()
            if session_id:
                self.db.attach_session(session_id)
            elif not self.db.research_id:
                raise RuntimeError("No active research session.")

            self.research_input = self.db.get_idea() or self.db.get_refined_idea()
            self._reset_stage_runtime()

            # Full subclass retry for the target stage (clears in-memory state)
            self.stages[stage_name].retry()
            if clear_outputs:
                self.db.clear_stage_outputs(stage_name)

            prior_stages = STAGE_ORDER[:STAGE_ORDER.index(stage_name)]
            for name in prior_stages:
                self._mark_stage_completed(name)

            self._pipeline_task = asyncio.create_task(self._run_from(stage_name))

    def _reset_stage_runtime(self):
        """Reset in-memory stage runtime only; keep persisted session artifacts intact."""
        for stage in self.stages.values():
            Stage.retry(stage)

    async def shutdown(self):
        self._kill_containers()
        await self._cancel_pipeline(timeout=5.0)

    def _find_stage(self, state: StageState) -> Stage | None:
        for name in STAGE_ORDER:
            if self.stages[name].state == state:
                return self.stages[name]
        return None

    async def _cancel_pipeline(self, timeout: float = 5.0):
        task = self._pipeline_task
        self._pipeline_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception:
                logging.getLogger(__name__).warning(
                    "Unexpected error while cancelling pipeline", exc_info=True,
                )

    def _kill_containers(self):
        from backend.agno.tools.docker_exec import kill_all_containers
        kill_all_containers()

    def _reset_stages(self):
        for stage in self.stages.values():
            stage.retry()

    def _start_kaggle(self, raw_input: str, competition_id: str):
        import re
        from backend.kaggle import fetch_competition, build_kaggle_idea
        from backend.config import settings
        info = fetch_competition(competition_id, data_dir=settings.dataset_dir)
        self._kaggle_competition_id = competition_id
        refined = build_kaggle_idea(info)
        user_hint = re.sub(r'https?://\S+', '', raw_input).strip()
        if user_hint:
            refined += f"\n## User Notes\n\n{user_hint}\n"
        self.research_input = refined
        self.db.create_session(info["title"])
        self.db.save_idea(raw_input)
        self.db.save_refined_idea(refined)

    def _mark_refine_done(self):
        refine = self.stages["refine"]
        refine.mark_completed(self.research_input)
        refine._send()  # done signal: refined_idea.md already saved

    def _mark_stage_completed(self, stage_name: str):
        stage = self.stages[stage_name]
        if stage_name == "refine":
            output = self.db.get_refined_idea() or self.db.get_idea()
        elif stage_name == "research":
            plan = self.db.get_plan_list()
            output = "\n".join(t.get("summary", "") for t in plan if t.get("summary"))
        elif stage_name == "write":
            output = self.db.get_document("paper")
        elif stage_name == "polish":
            output = self.db.get_document("paper_final")
        else:
            output = ""
        stage.mark_completed(output)

    async def _run_from(self, stage_name: str):
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
                self._kill_containers()
                return
        # All requested stages finished — release sandbox container
        self._kill_containers()

    def _broadcast(self, event: dict):
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def _wire_broadcast(self):
        for stage in self.stages.values():
            stage.configure(self._broadcast, self._api_semaphore)

    def get_status(self) -> dict:
        return {
            "input": self.research_input,
            "stages": [self.stages[name].get_status() for name in STAGE_ORDER],
        }
