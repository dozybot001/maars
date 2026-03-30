"""Tests for ResearchStage helper methods."""

import json
from pathlib import Path

import pytest

from backend.db import ResearchDB
from backend.pipeline.research import ResearchStage, topological_batches
from backend.utils import parse_json_fenced


@pytest.fixture
def db(tmp_path):
    d = ResearchDB(base_dir=str(tmp_path))
    d.create_session("test")
    return d


@pytest.fixture
def stage(db):
    s = ResearchStage(name="research")
    s.db = db
    return s


class TestParseVerification:
    """Test _parse_verification via the instance method."""

    def test_pass(self, stage):
        response = json.dumps({"pass": True, "review": "", "summary": "ok", "redecompose": False})
        passed, review, summary, redecomp = stage._parse_verification(response)
        assert passed is True
        assert summary == "ok"
        assert redecomp is False

    def test_fail_with_review(self, stage):
        response = json.dumps({
            "pass": False, "review": "needs fix", "summary": "bad", "redecompose": False,
        })
        passed, review, summary, redecomp = stage._parse_verification(response)
        assert passed is False
        assert review == "needs fix"

    def test_redecompose_flag(self, stage):
        response = json.dumps({
            "pass": False, "review": "too complex", "summary": "", "redecompose": True,
        })
        _, _, _, redecomp = stage._parse_verification(response)
        assert redecomp is True

    def test_fenced_json(self, stage):
        response = '```json\n{"pass": true, "summary": "good"}\n```'
        passed, _, summary, _ = stage._parse_verification(response)
        assert passed is True
        assert summary == "good"

    def test_invalid_json_defaults_to_pass(self, stage):
        passed, _, _, _ = stage._parse_verification("garbage output")
        assert passed is True  # fallback: {"pass": True}


class TestCheckScoreImproved:
    def test_no_score_file(self, stage):
        improved, score = stage._check_score_improved(None, minimize=True)
        assert improved is False
        assert score is None

    def test_first_score_always_improved(self, stage, db):
        artifacts = db.get_artifacts_dir()
        (artifacts / "latest_score.json").write_text(json.dumps({"score": 0.5}))
        improved, score = stage._check_score_improved(None, minimize=True)
        assert improved is True
        assert score == 0.5

    def test_minimize_improved(self, stage, db):
        artifacts = db.get_artifacts_dir()
        (artifacts / "latest_score.json").write_text(json.dumps({"score": 0.3}))
        improved, score = stage._check_score_improved(0.5, minimize=True)
        assert improved is True
        assert score == 0.3

    def test_minimize_plateau(self, stage, db):
        """Score barely changed (<0.5%) → not improved."""
        artifacts = db.get_artifacts_dir()
        (artifacts / "latest_score.json").write_text(json.dumps({"score": 0.499}))
        improved, score = stage._check_score_improved(0.5, minimize=True)
        assert improved is False

    def test_maximize_improved(self, stage, db):
        artifacts = db.get_artifacts_dir()
        (artifacts / "latest_score.json").write_text(json.dumps({"score": 0.8}))
        improved, score = stage._check_score_improved(0.5, minimize=False)
        assert improved is True

    def test_maximize_plateau(self, stage, db):
        artifacts = db.get_artifacts_dir()
        (artifacts / "latest_score.json").write_text(json.dumps({"score": 0.502}))
        improved, score = stage._check_score_improved(0.5, minimize=False)
        assert improved is False

    def test_fallback_to_best_score(self, stage, db):
        """Falls back to best_score.json if latest_score.json missing."""
        artifacts = db.get_artifacts_dir()
        (artifacts / "best_score.json").write_text(json.dumps({"score": 0.7}))
        improved, score = stage._check_score_improved(None, minimize=True)
        assert improved is True
        assert score == 0.7

    def test_corrupt_score_file(self, stage, db):
        artifacts = db.get_artifacts_dir()
        (artifacts / "latest_score.json").write_text("not json")
        improved, score = stage._check_score_improved(0.5, minimize=True)
        assert improved is False
        assert score is None


class TestRenumberTasks:
    def test_basic_renumber(self, stage):
        tasks = [
            {"id": "1", "description": "a", "dependencies": []},
            {"id": "2", "description": "b", "dependencies": ["1"]},
        ]
        result = stage._renumber_tasks(tasks, round_num=1)
        assert result[0]["id"] == "r1_1"
        assert result[1]["id"] == "r1_2"
        assert result[1]["dependencies"] == ["r1_1"]

    def test_cross_round_dependency(self, stage):
        """Dependencies on tasks from earlier rounds stay unchanged."""
        tasks = [
            {"id": "1", "description": "a", "dependencies": ["original_task"]},
        ]
        result = stage._renumber_tasks(tasks, round_num=2)
        assert result[0]["dependencies"] == ["original_task"]


class TestLoadCheckpoint:
    def test_load_completed_tasks(self, stage, db):
        db.save_task_output("1", "result 1")
        db.save_task_output("2", "result 2")
        stage._load_checkpoint()
        assert "1" in stage._task_results
        assert "2" in stage._task_results
        assert stage._task_results["1"] == "result 1"

    def test_empty_checkpoint(self, stage):
        stage._load_checkpoint()
        assert stage._task_results == {}
