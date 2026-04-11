"""Refine StateGraph — Explorer <-> Critic adversarial loop."""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from maars.agents.critic import critique_draft
from maars.agents.explorer import draft_proposal
from maars.config import CHECKPOINT_DB, REFINE_MAX_ROUND
from maars.state import RefineState


def explorer_node(state: RefineState) -> dict:
    """Draft or revise the research proposal."""
    draft = draft_proposal(
        raw_idea=state["raw_idea"],
        prior_draft=state.get("draft"),
        prior_issues=state.get("issues"),
    )
    return {
        "draft": draft,
        "round": state.get("round", 0) + 1,
    }


def critic_node(state: RefineState) -> dict:
    """Review the current draft and return structured critique."""
    result = critique_draft(
        draft=state["draft"],
        prior_issues=state.get("issues"),
    )
    return {
        "issues": result.issues,
        "resolved": result.resolved,
        "passed": result.passed,
    }


def should_continue(state: RefineState) -> str:
    """Decide whether to loop back to Explorer or end."""
    if state.get("passed", False):
        return END
    if state.get("round", 0) >= REFINE_MAX_ROUND:
        return END
    return "explorer"


def build_refine_graph():
    """Build and compile the Refine StateGraph with a SQLite checkpointer."""
    workflow = StateGraph(RefineState)
    workflow.add_node("explorer", explorer_node)
    workflow.add_node("critic", critic_node)

    workflow.add_edge(START, "explorer")
    workflow.add_edge("explorer", "critic")
    workflow.add_conditional_edges("critic", should_continue)

    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return workflow.compile(checkpointer=checkpointer)
