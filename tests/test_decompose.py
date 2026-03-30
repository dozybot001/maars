"""Tests for decompose module — dependency resolution and tree serialization."""

from backend.pipeline.decompose import (
    Task,
    _ancestor_chain,
    _finalize,
    _get_atomic_descendants,
    _resolve_dependencies,
    _serialize_tree,
)


class TestAncestorChain:
    def test_root_child(self):
        assert _ancestor_chain("1") == ["0"]

    def test_nested(self):
        assert _ancestor_chain("1_2_3") == ["1_2", "1", "0"]

    def test_deep(self):
        chain = _ancestor_chain("1_2_3_4")
        assert chain == ["1_2_3", "1_2", "1", "0"]


class TestGetAtomicDescendants:
    def test_atomic_task_returns_self(self):
        tasks = {"1": Task(id="1", description="a", is_atomic=True)}
        result = _get_atomic_descendants(tasks, "1", tasks)
        assert result == {"1"}

    def test_non_atomic_returns_children(self):
        tasks = {
            "1": Task(id="1", description="parent", is_atomic=False, children=["1_1", "1_2"]),
            "1_1": Task(id="1_1", description="child1", is_atomic=True),
            "1_2": Task(id="1_2", description="child2", is_atomic=True),
        }
        atomic = {k: v for k, v in tasks.items() if v.is_atomic}
        result = _get_atomic_descendants(tasks, "1", atomic)
        assert result == {"1_1", "1_2"}

    def test_missing_task(self):
        result = _get_atomic_descendants({}, "nonexistent", {})
        assert result == set()


class TestResolveAndFinalize:
    def _build_simple_tree(self):
        """Build: root(0) → {1, 2}, where 2 depends on 1. Both atomic."""
        tasks = {
            "0": Task(id="0", description="root", is_atomic=False, children=["1", "2"]),
            "1": Task(id="1", description="first", is_atomic=True, dependencies=[]),
            "2": Task(id="2", description="second", is_atomic=True, dependencies=["1"]),
        }
        return tasks

    def test_finalize_returns_atomic_only(self):
        tasks = self._build_simple_tree()
        flat = _finalize(tasks)
        ids = {t["id"] for t in flat}
        assert ids == {"1", "2"}
        assert "0" not in ids

    def test_finalize_preserves_dependencies(self):
        tasks = self._build_simple_tree()
        flat = _finalize(tasks)
        task_2 = next(t for t in flat if t["id"] == "2")
        assert "1" in task_2["dependencies"]

    def test_nested_dependency_resolution(self):
        """Nested: 0 → {1(→1_1,1_2), 2 depends on 1}. Task 2 should depend on 1_1 and 1_2."""
        tasks = {
            "0": Task(id="0", description="root", is_atomic=False, children=["1", "2"]),
            "1": Task(id="1", description="group", is_atomic=False, children=["1_1", "1_2"]),
            "1_1": Task(id="1_1", description="sub1", is_atomic=True, dependencies=[]),
            "1_2": Task(id="1_2", description="sub2", is_atomic=True, dependencies=["1_1"]),
            "2": Task(id="2", description="after group", is_atomic=True, dependencies=["1"]),
        }
        atomic = {k: v for k, v in tasks.items() if v.is_atomic}
        resolved = _resolve_dependencies(tasks, atomic)
        # Task 2 depends on non-atomic 1 → expanded to {1_1, 1_2}
        assert set(resolved["2"]) == {"1_1", "1_2"}


class TestSerializeTree:
    def test_basic_tree(self):
        tasks = {
            "0": Task(id="0", description="root", is_atomic=False, children=["1"]),
            "1": Task(id="1", description="leaf", is_atomic=True),
        }
        tree = _serialize_tree(tasks)
        assert tree["id"] == "0"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["id"] == "1"
        assert tree["children"][0]["is_atomic"] is True

    def test_empty_tasks(self):
        assert _serialize_tree({}) == {}
