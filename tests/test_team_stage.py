import json
import tempfile
import unittest
from pathlib import Path

from backend.db import ResearchDB
from backend.team.stage import TeamStage


class _FakeTeamStage(TeamStage):
    _primary_dir = "drafts"
    _reviewer_dir = "reviews"
    _primary_phase = "draft"
    _reviewer_phase = "review"

    def __init__(self, db, responses, max_delegations):
        super().__init__(name="write", model=None, db=db, max_delegations=max_delegations)
        self._responses = list(responses)

    def load_input(self) -> str:
        return "input"

    def _primary_config(self):
        return "writer", [], "Writer"

    def _reviewer_config(self):
        return "reviewer", [], "Reviewer"

    def _finalize(self) -> str:
        return self.output

    async def _stream_llm(self, *args, **kwargs) -> str:
        return self._responses.pop(0)


class TeamStageTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_round_still_runs_review_before_returning_last_draft(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = ResearchDB(base_dir=tmpdir)
            db.create_session("team stage test")

            stage = _FakeTeamStage(
                db=db,
                max_delegations=2,
                responses=[
                    "draft round 1",
                    json.dumps({"pass": False, "issues": [{"id": "i1", "problem": "fix one"}]}),
                    "draft round 2",
                    json.dumps({"pass": False, "issues": [{"id": "i2", "problem": "fix two"}]}),
                ],
            )

            result = await stage._execute()

            root = Path(tmpdir) / db.research_id
            self.assertEqual(result, "draft round 2")
            self.assertTrue((root / "drafts" / "round_0.md").exists())
            self.assertTrue((root / "drafts" / "round_1.md").exists())
            self.assertTrue((root / "reviews" / "round_0.md").exists())
            self.assertTrue((root / "reviews" / "round_0.json").exists())
            self.assertTrue((root / "reviews" / "round_1.md").exists())
            self.assertTrue((root / "reviews" / "round_1.json").exists())

    async def test_reviewer_pass_allows_finalize(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = ResearchDB(base_dir=tmpdir)
            db.create_session("team stage pass")

            stage = _FakeTeamStage(
                db=db,
                max_delegations=2,
                responses=[
                    "draft round 1",
                    json.dumps({"pass": False, "issues": [{"id": "i1", "problem": "fix one"}]}),
                    "draft round 2",
                    json.dumps({"issues": []}),
                ],
            )

            result = await stage._execute()

            self.assertEqual(result, "draft round 2")


if __name__ == "__main__":
    unittest.main()
