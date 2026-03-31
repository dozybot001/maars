"""Tests for Session management API routes."""

import pytest
from fastapi.testclient import TestClient

from backend.db import ResearchDB


@pytest.fixture
def app_with_sessions(tmp_path):
    """Create a test app with a temporary results directory."""
    from fastapi import FastAPI
    from backend.routes.sessions import router

    # Create some sessions
    db = ResearchDB(base_dir=str(tmp_path))
    db.create_session("first test idea")
    db.save_idea("first test idea")
    db.save_paper("final paper")
    first_id = db.research_id

    db2 = ResearchDB(base_dir=str(tmp_path))
    db2.create_session("second test idea")
    db2.save_idea("second test idea")
    second_id = db2.research_id

    # Build app with mock orchestrator
    app = FastAPI()
    app.include_router(router)

    class MockOrchestrator:
        def __init__(self):
            # Use a fresh DB pointing to same dir (no active session)
            self.db = ResearchDB(base_dir=str(tmp_path))

    app.state.orchestrator = MockOrchestrator()

    return TestClient(app), first_id, second_id


class TestListSessions:
    def test_list_returns_all(self, app_with_sessions):
        client, first_id, second_id = app_with_sessions
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        ids = [s["id"] for s in data]
        assert first_id in ids
        assert second_id in ids

    def test_list_includes_status(self, app_with_sessions):
        client, first_id, _ = app_with_sessions
        resp = client.get("/api/sessions")
        sessions = {s["id"]: s for s in resp.json()}
        assert sessions[first_id]["status"] == "completed"


class TestGetSession:
    def test_get_existing(self, app_with_sessions):
        client, first_id, _ = app_with_sessions
        resp = client.get(f"/api/sessions/{first_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["idea"] == "first test idea"
        assert data["paper"] == "final paper"

    def test_get_not_found(self, app_with_sessions):
        client, _, _ = app_with_sessions
        # Valid format but doesn't exist → 404
        resp = client.get("/api/sessions/20200101-000000")
        assert resp.status_code == 404
        # Invalid format → 400
        resp = client.get("/api/sessions/nonexistent")
        assert resp.status_code == 400


class TestGetSessionState:
    def test_state_completed_session(self, tmp_path):
        """Full session with all stages produces correct state."""
        from fastapi import FastAPI
        from backend.routes.sessions import router

        db = ResearchDB(base_dir=str(tmp_path))
        db.create_session("state test")
        db.save_idea("state test idea")
        db.save_refined_idea("refined idea")
        db.save_calibration("calibration")
        db.save_strategy("strategy")
        flat_tasks = [
            {"id": "1", "description": "task one", "dependencies": []},
            {"id": "2", "description": "task two", "dependencies": ["1"]},
        ]
        tree = {"id": "0", "children": [{"id": "1"}, {"id": "2"}]}
        db.save_plan(flat_tasks, tree)
        db.save_task_output("1", "output one")
        db.save_task_output("2", "output two")
        db.save_evaluation({"score": 0.5}, 0)
        db.save_evaluation({"score": 0.8}, 1)
        db.save_paper("final paper")
        sid = db.research_id

        app = FastAPI()
        app.include_router(router)

        class MockOrch:
            db = ResearchDB(base_dir=str(tmp_path))

        app.state.orchestrator = MockOrch()
        client = TestClient(app)

        resp = client.get(f"/api/sessions/{sid}/state")
        assert resp.status_code == 200
        state = resp.json()

        # Stage states
        assert state["stage_states"]["refine"] == "completed"
        assert state["stage_states"]["research"] == "completed"
        assert state["stage_states"]["write"] == "completed"

        # Node states
        assert state["node_states"]["refine"] == "done"
        assert state["node_states"]["calibrate"] == "done"
        assert state["node_states"]["strategy"] == "done"
        assert state["node_states"]["decompose"] == "done"
        assert state["node_states"]["execute"] == "done"
        assert state["node_states"]["evaluate"] == "done"
        assert state["node_states"]["write"] == "done"

        # Documents
        assert "refined_idea" in state["documents"]
        assert state["documents"]["paper"]["content"] == "final paper"

        # Tasks
        assert state["task_descriptions"]["1"] == "task one"
        assert state["task_states"]["1"]["status"] == "completed"
        assert state["task_states"]["2"]["status"] == "completed"

        # Exec batches (recomputed from deps: task 1 first, task 2 second)
        assert len(state["exec_batches"]) == 2
        assert state["exec_batches"][0]["tasks"][0]["id"] == "1"
        assert state["exec_batches"][1]["tasks"][0]["id"] == "2"

        # Scores
        assert len(state["scores"]) == 2
        assert state["scores"][0]["current"] == 0.5
        assert state["scores"][1]["current"] == 0.8

    def test_state_partial_session(self, tmp_path):
        """Session with only refine done."""
        from fastapi import FastAPI
        from backend.routes.sessions import router

        db = ResearchDB(base_dir=str(tmp_path))
        db.create_session("partial")
        db.save_idea("partial idea")
        db.save_refined_idea("refined")
        sid = db.research_id

        app = FastAPI()
        app.include_router(router)

        class MockOrch:
            db = ResearchDB(base_dir=str(tmp_path))

        app.state.orchestrator = MockOrch()
        client = TestClient(app)

        resp = client.get(f"/api/sessions/{sid}/state")
        assert resp.status_code == 200
        state = resp.json()
        assert state["stage_states"]["refine"] == "completed"
        assert state["stage_states"]["research"] == "idle"
        assert state["node_states"]["refine"] == "done"
        assert state["node_states"]["decompose"] == "idle"
        assert state["exec_batches"] == []
        assert state["scores"] == []

    def test_state_not_found(self, app_with_sessions):
        client, _, _ = app_with_sessions
        # Valid format but doesn't exist → 404
        resp = client.get("/api/sessions/20200101-000000/state")
        assert resp.status_code == 404
        # Invalid format → 400
        resp = client.get("/api/sessions/nonexistent/state")
        assert resp.status_code == 400


class TestDeleteSession:
    def test_delete_existing(self, app_with_sessions):
        client, first_id, _ = app_with_sessions
        resp = client.delete(f"/api/sessions/{first_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == first_id

        # Verify it's gone
        resp = client.get(f"/api/sessions/{first_id}")
        assert resp.status_code == 404

    def test_delete_not_found(self, app_with_sessions):
        client, _, _ = app_with_sessions
        # Invalid format → 400
        resp = client.delete("/api/sessions/nonexistent")
        assert resp.status_code == 400
        # Valid format but doesn't exist → 404
        resp = client.delete("/api/sessions/20200101-000000")
        assert resp.status_code == 404


class TestAccessTokenAuth:
    def test_no_token_allows_access(self, tmp_path):
        """Without MAARS_ACCESS_TOKEN, all requests pass."""
        from fastapi import FastAPI
        from backend.routes.sessions import router

        app = FastAPI()
        app.include_router(router)

        class MockOrch:
            db = ResearchDB(base_dir=str(tmp_path))

        app.state.orchestrator = MockOrch()
        client = TestClient(app)
        resp = client.get("/api/sessions")
        assert resp.status_code == 200

    def test_token_blocks_without_bearer(self, tmp_path, monkeypatch):
        """With MAARS_ACCESS_TOKEN set, missing auth returns 401."""
        from fastapi import FastAPI
        from backend.main import AccessTokenMiddleware
        from backend.routes.sessions import router
        import backend.config as cfg

        monkeypatch.setattr(cfg.settings, "access_token", "test-secret")

        app = FastAPI()
        app.add_middleware(AccessTokenMiddleware)
        app.include_router(router)

        class MockOrch:
            db = ResearchDB(base_dir=str(tmp_path))

        app.state.orchestrator = MockOrch()
        client = TestClient(app)

        resp = client.get("/api/sessions")
        assert resp.status_code == 401

        # With correct Bearer token
        resp = client.get(
            "/api/sessions",
            headers={"Authorization": "Bearer test-secret"},
        )
        assert resp.status_code == 200

        # Query token no longer accepted — must use header
        resp = client.get("/api/sessions?token=test-secret")
        assert resp.status_code == 401
