"""
Level-order tree layout for decomposition (task_id hierarchy).
Each node gets a fixed slot — subtree width does not affect sibling spacing.
"""

from typing import Any, Dict, List, Optional, Tuple

DEFAULT_NODE_W = 36
DEFAULT_NODE_H = 28
DEFAULT_NODE_SEP = 12   # 兄弟节点横向间距（固定槽位）
DEFAULT_RANK_SEP = 48   # 父子层级纵向间距
DEFAULT_PADDING = 24


def _natural_task_id_key(tid: str) -> Tuple:
    """Sort key: '1' < '1_1' < '1_2' < '1_10'."""
    parts = tid.split("_")
    return tuple(int(p) if p.isdigit() else p for p in parts)


def _build_tree(tasks: List[Dict]) -> Dict[str, List[str]]:
    """Build parent -> sorted children from task_id hierarchy."""
    ids = {t["task_id"] for t in tasks if t.get("task_id")}
    children: Dict[str, List[str]] = {}
    for t in tasks:
        tid = t.get("task_id")
        if not tid:
            continue
        parent = tid.rsplit("_", 1)[0] if "_" in tid else "0"
        if parent in ids and parent != tid:
            children.setdefault(parent, []).append(tid)
    for pid in children:
        children[pid].sort(key=_natural_task_id_key)
    return children


def compute_decomposition_layout(
    tasks: List[Dict[str, Any]],
    node_w: int = DEFAULT_NODE_W,
    node_h: int = DEFAULT_NODE_H,
    node_sep: int = DEFAULT_NODE_SEP,
    rank_sep: int = DEFAULT_RANK_SEP,
    padding: int = DEFAULT_PADDING,
) -> Optional[Dict[str, Any]]:
    """
    Level-order layout: each node gets a fixed slot. Subtree width does not
    affect the distance between sibling (parent) nodes.
    Returns {nodes: {id: {x,y,w,h}}, edges: [{from,to,points}], width, height}.
    """
    valid = [t for t in (tasks or []) if t.get("task_id")]
    if not valid:
        return None

    ids = {t["task_id"] for t in valid}
    children_map = _build_tree(valid)

    all_children = {c for cs in children_map.values() for c in cs}
    roots = sorted([tid for tid in ids if tid not in all_children], key=_natural_task_id_key)
    if not roots:
        return None

    slot_w = node_w + node_sep

    # Level-order (BFS): nodes by depth, each level left-to-right by task_id
    levels: List[List[str]] = []
    frontier = list(roots)
    while frontier:
        levels.append(frontier[:])
        next_frontier = []
        for nid in frontier:
            kids = sorted(children_map.get(nid, []), key=_natural_task_id_key)
            next_frontier.extend(kids)
        frontier = next_frontier

    # Assign x by slot index — fixed slot per node; each level centered to prevent overflow
    max_level_width = max(len(layer) * slot_w for layer in levels) if levels else 0
    positions: Dict[str, Dict[str, Any]] = {}
    for depth, layer in enumerate(levels):
        y = depth * (node_h + rank_sep)
        level_width = len(layer) * slot_w
        level_offset = (max_level_width - level_width) / 2  # 居中对齐
        for idx, nid in enumerate(layer):
            x = level_offset + idx * slot_w
            positions[nid] = {"x": x, "y": y, "w": node_w, "h": node_h}

    # Build edges
    edges: List[Dict[str, Any]] = []
    for parent, kids in children_map.items():
        if parent not in positions:
            continue
        pp = positions[parent]
        src_cx = pp["x"] + pp["w"] / 2
        src_bottom = pp["y"] + pp["h"]
        for c in kids:
            if c not in positions:
                continue
            cp = positions[c]
            dst_cx = cp["x"] + cp["w"] / 2
            dst_top = cp["y"]
            edges.append({
                "from": parent,
                "to": c,
                "points": [[round(src_cx, 1), round(src_bottom, 1)],
                          [round(dst_cx, 1), round(dst_top, 1)]],
            })

    # Normalize to origin and add padding
    xs = [p["x"] for p in positions.values()]
    ys = [p["y"] for p in positions.values()]
    ws = [p["x"] + p["w"] for p in positions.values()]
    hs = [p["y"] + p["h"] for p in positions.values()]
    min_x, min_y = min(xs), min(ys)
    max_x, max_y = max(ws), max(hs)
    off_x = min_x - padding
    off_y = min_y - padding

    nodes_out = {}
    for nid, pos in positions.items():
        if nid in ids:
            nodes_out[nid] = {
                "x": round(pos["x"] - off_x, 1),
                "y": round(pos["y"] - off_y, 1),
                "w": pos["w"],
                "h": pos["h"],
            }

    edges_out = []
    for e in edges:
        shifted = [[round(pt[0] - off_x, 1), round(pt[1] - off_y, 1)] for pt in e["points"]]
        edges_out.append({"from": e["from"], "to": e["to"], "points": shifted})

    width = round(max(max_x - min_x + padding * 2, 200), 1)
    height = round(max(max_y - min_y + padding * 2, 100), 1)

    return {"nodes": nodes_out, "edges": edges_out, "width": width, "height": height}
