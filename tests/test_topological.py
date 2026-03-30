"""Tests for topological_batches() — DAG scheduling."""

from backend.pipeline.research import topological_batches


class TestTopologicalBatches:
    def test_no_dependencies(self):
        """All independent tasks → single batch."""
        tasks = [
            {"id": "1", "description": "a", "dependencies": []},
            {"id": "2", "description": "b", "dependencies": []},
            {"id": "3", "description": "c", "dependencies": []},
        ]
        batches = topological_batches(tasks)
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_linear_chain(self):
        """1 → 2 → 3 → each in its own batch."""
        tasks = [
            {"id": "1", "description": "a", "dependencies": []},
            {"id": "2", "description": "b", "dependencies": ["1"]},
            {"id": "3", "description": "c", "dependencies": ["2"]},
        ]
        batches = topological_batches(tasks)
        assert len(batches) == 3
        assert batches[0][0]["id"] == "1"
        assert batches[1][0]["id"] == "2"
        assert batches[2][0]["id"] == "3"

    def test_diamond_dag(self):
        """Diamond: 1 → {2,3} → 4."""
        tasks = [
            {"id": "1", "description": "a", "dependencies": []},
            {"id": "2", "description": "b", "dependencies": ["1"]},
            {"id": "3", "description": "c", "dependencies": ["1"]},
            {"id": "4", "description": "d", "dependencies": ["2", "3"]},
        ]
        batches = topological_batches(tasks)
        assert len(batches) == 3
        batch_ids = [[t["id"] for t in b] for b in batches]
        assert batch_ids[0] == ["1"]
        assert set(batch_ids[1]) == {"2", "3"}
        assert batch_ids[2] == ["4"]

    def test_empty_list(self):
        assert topological_batches([]) == []

    def test_single_task(self):
        tasks = [{"id": "1", "description": "only", "dependencies": []}]
        batches = topological_batches(tasks)
        assert len(batches) == 1
        assert batches[0][0]["id"] == "1"

    def test_missing_dependencies_key(self):
        """Tasks without 'dependencies' key default to empty."""
        tasks = [
            {"id": "1", "description": "a"},
            {"id": "2", "description": "b"},
        ]
        batches = topological_batches(tasks)
        assert len(batches) == 1

    def test_circular_dependency_breaks_out(self):
        """Circular deps should not cause infinite loop (forced batch)."""
        tasks = [
            {"id": "1", "description": "a", "dependencies": ["2"]},
            {"id": "2", "description": "b", "dependencies": ["1"]},
        ]
        batches = topological_batches(tasks)
        # Should still produce output (forced batch), not hang
        all_ids = {t["id"] for b in batches for t in b}
        assert all_ids == {"1", "2"}
