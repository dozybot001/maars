"""
Sugiyama layered graph layout algorithm for DAGs.

Implements the standard Sugiyama framework:
1. Layer assignment (longest-path)
2. Dummy node insertion (for long edges)
3. Crossing minimization (barycenter heuristic, multi-pass)
4. Coordinate assignment (median-based with iterative refinement)
5. Edge routing (straight lines through dummy waypoints)
"""

from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx


DEFAULT_NODE_W = 36
DEFAULT_NODE_H = 28
DEFAULT_NODE_SEP = 20
DEFAULT_RANK_SEP = 40
DEFAULT_PADDING = 24


def compute_layout(
    tasks: List[Dict[str, Any]],
    decomposition: bool = False,
    node_w: int = DEFAULT_NODE_W,
    node_h: int = DEFAULT_NODE_H,
    node_sep: int = DEFAULT_NODE_SEP,
    rank_sep: int = DEFAULT_RANK_SEP,
    padding: int = DEFAULT_PADDING,
) -> Optional[Dict[str, Any]]:
    """
    Compute a layered graph layout for a task DAG (dependency-based).
    For decomposition/task-id hierarchy, use tree_layout.compute_decomposition_layout.

    Returns {nodes: {id: {x,y,w,h}}, edges: [{from,to,points}], width, height}
    or None if tasks are empty.
    """
    valid = [t for t in (tasks or []) if t.get("task_id")]
    if not valid:
        return None

    G = build_dependency_graph(valid)
    if G.number_of_nodes() == 0:
        return None

    _break_cycles(G)

    layers = _assign_layers(G)
    layers, dummy_nodes = _insert_dummy_nodes(G, layers)
    _minimize_crossings(G, layers)
    positions = _assign_coordinates(G, layers, dummy_nodes, node_w, node_h, node_sep, rank_sep)
    edges = _route_edges(G, positions, dummy_nodes)

    real_ids = {t["task_id"] for t in valid}
    xs = [p["x"] for nid, p in positions.items() if nid in real_ids]
    ys = [p["y"] for nid, p in positions.items() if nid in real_ids]
    ws = [p["x"] + p["w"] for nid, p in positions.items() if nid in real_ids]
    hs = [p["y"] + p["h"] for nid, p in positions.items() if nid in real_ids]

    if not xs:
        return None

    min_x, min_y = min(xs), min(ys)
    max_x, max_y = max(ws), max(hs)

    off_x = min_x - padding
    off_y = min_y - padding

    nodes_out = {}
    for nid, pos in positions.items():
        if nid in real_ids:
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


# ---------------------------------------------------------------------------
# 1. Graph construction (single source for all DAG operations)
# ---------------------------------------------------------------------------

def build_dependency_graph(tasks: List[Dict], ids: Optional[Set[str]] = None) -> nx.DiGraph:
    """Build dependency graph from tasks. ids: if provided, only include nodes in ids."""
    ids = ids or {t["task_id"] for t in (tasks or []) if t.get("task_id")}
    G = nx.DiGraph()
    for t in tasks or []:
        tid = t.get("task_id")
        if not tid or tid not in ids:
            continue
        G.add_node(tid)
        for dep in t.get("dependencies") or []:
            if dep in ids and dep != tid:
                G.add_edge(dep, tid)
    return G


def _break_cycles(G: nx.DiGraph) -> None:
    """Remove back-edges to make the graph acyclic (greedy)."""
    try:
        cycles = list(nx.simple_cycles(G))
    except Exception:
        return
    removed: Set[Tuple[str, str]] = set()
    for cycle in cycles:
        for i in range(len(cycle)):
            u, v = cycle[i], cycle[(i + 1) % len(cycle)]
            if (u, v) not in removed and G.has_edge(u, v):
                G.remove_edge(u, v)
                removed.add((u, v))
                break


# ---------------------------------------------------------------------------
# 2. Layer assignment (longest path from sources)
# ---------------------------------------------------------------------------

def _assign_layers(G: nx.DiGraph) -> List[List[str]]:
    """Assign each node to a layer using longest-path algorithm."""
    node_layer: Dict[str, int] = {}
    topo = list(nx.topological_sort(G))
    for n in topo:
        preds = list(G.predecessors(n))
        if not preds:
            node_layer[n] = 0
        else:
            node_layer[n] = max(node_layer.get(p, 0) for p in preds) + 1

    max_layer = max(node_layer.values()) if node_layer else 0
    layers: List[List[str]] = [[] for _ in range(max_layer + 1)]
    for n, lyr in node_layer.items():
        layers[lyr].append(n)

    return layers


# ---------------------------------------------------------------------------
# 3. Dummy node insertion
# ---------------------------------------------------------------------------

def _insert_dummy_nodes(
    G: nx.DiGraph, layers: List[List[str]]
) -> Tuple[List[List[str]], Set[str]]:
    """Insert dummy nodes for edges spanning more than one layer."""
    node_layer: Dict[str, int] = {}
    for i, layer in enumerate(layers):
        for n in layer:
            node_layer[n] = i

    dummy_nodes: Set[str] = set()
    edges_to_process = list(G.edges())
    counter = 0

    for u, v in edges_to_process:
        lu, lv = node_layer.get(u), node_layer.get(v)
        if lu is None or lv is None or lv - lu <= 1:
            continue

        G.remove_edge(u, v)
        prev = u
        for step in range(1, lv - lu):
            counter += 1
            d = f"__d{counter}"
            dummy_nodes.add(d)
            G.add_node(d)
            G.add_edge(prev, d)
            target_layer = lu + step
            layers[target_layer].append(d)
            node_layer[d] = target_layer
            prev = d
        G.add_edge(prev, v)

    return layers, dummy_nodes


# ---------------------------------------------------------------------------
# 4. Crossing minimization (barycenter heuristic)
# ---------------------------------------------------------------------------

def _count_crossings(G: nx.DiGraph, layer_a: List[str], layer_b: List[str]) -> int:
    """Count edge crossings between two adjacent layers."""
    pos_b = {n: i for i, n in enumerate(layer_b)}
    edges = []
    for i, u in enumerate(layer_a):
        for v in G.successors(u):
            if v in pos_b:
                edges.append((i, pos_b[v]))

    crossings = 0
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            if (edges[i][0] - edges[j][0]) * (edges[i][1] - edges[j][1]) < 0:
                crossings += 1
    return crossings


def _total_crossings(G: nx.DiGraph, layers: List[List[str]]) -> int:
    total = 0
    for i in range(len(layers) - 1):
        total += _count_crossings(G, layers[i], layers[i + 1])
    return total


def _barycenter_sort(
    G: nx.DiGraph, fixed_layer: List[str], free_layer: List[str], downward: bool
) -> List[str]:
    """Reorder free_layer to minimize crossings with fixed_layer using barycenter."""
    fixed_pos = {n: i for i, n in enumerate(fixed_layer)}
    bary: Dict[str, float] = {}

    for n in free_layer:
        neighbors = list(G.predecessors(n)) if downward else list(G.successors(n))
        relevant = [fixed_pos[nb] for nb in neighbors if nb in fixed_pos]
        if relevant:
            bary[n] = sum(relevant) / len(relevant)
        else:
            bary[n] = float("inf")

    anchored = [(n, b) for n, b in bary.items() if b != float("inf")]
    unanchored = [n for n, b in bary.items() if b == float("inf")]
    anchored.sort(key=lambda x: x[1])

    result = [n for n, _ in anchored]

    for u in unanchored:
        idx = free_layer.index(u)
        best = len(result)
        for i, r in enumerate(result):
            if free_layer.index(r) > idx:
                best = i
                break
        result.insert(best, u)

    return result


def _minimize_crossings(G: nx.DiGraph, layers: List[List[str]], passes: int = 30) -> None:
    """Multi-pass barycenter crossing minimization (in-place)."""
    if len(layers) <= 1:
        return

    best_order = [list(layer) for layer in layers]
    best_crossings = _total_crossings(G, layers)

    for iteration in range(passes):
        if iteration % 2 == 0:
            for i in range(1, len(layers)):
                layers[i] = _barycenter_sort(G, layers[i - 1], layers[i], downward=True)
        else:
            for i in range(len(layers) - 2, -1, -1):
                layers[i] = _barycenter_sort(G, layers[i + 1], layers[i], downward=False)

        c = _total_crossings(G, layers)
        if c < best_crossings:
            best_crossings = c
            best_order = [list(layer) for layer in layers]
        if best_crossings == 0:
            break

    for i in range(len(layers)):
        layers[i] = best_order[i]


# ---------------------------------------------------------------------------
# 5. Coordinate assignment (median-based, iterative)
# ---------------------------------------------------------------------------

def _assign_coordinates(
    G: nx.DiGraph,
    layers: List[List[str]],
    dummy_nodes: Set[str],
    node_w: int,
    node_h: int,
    node_sep: int,
    rank_sep: int,
) -> Dict[str, Dict[str, Any]]:
    """Assign (x, y) coordinates using median-based placement with iterative refinement."""
    positions: Dict[str, Dict[str, Any]] = {}

    for layer_idx, layer in enumerate(layers):
        y = layer_idx * (node_h + rank_sep)
        for pos_in_layer, nid in enumerate(layer):
            x = pos_in_layer * (node_w + node_sep)
            w = node_w if nid not in dummy_nodes else 0
            h = node_h if nid not in dummy_nodes else 0
            positions[nid] = {"id": nid, "x": float(x), "y": float(y), "w": w, "h": h}

    for _ in range(12):
        for layer_idx in range(1, len(layers)):
            _align_to_connected(G, layers[layer_idx], positions, dummy_nodes, node_w, node_sep)
        for layer_idx in range(len(layers) - 2, -1, -1):
            _align_to_connected(G, layers[layer_idx], positions, dummy_nodes, node_w, node_sep)

    return positions


def _node_center_x(pos: Dict) -> float:
    return pos["x"] + pos["w"] / 2.0


def _align_to_connected(
    G: nx.DiGraph,
    layer: List[str],
    positions: Dict[str, Dict],
    dummy_nodes: Set[str],
    node_w: int,
    node_sep: int,
) -> None:
    """Shift nodes in a layer toward the median x of connected nodes, preserving order."""
    if not layer:
        return

    ideal_x: Dict[str, float] = {}

    for nid in layer:
        connected = list(G.predecessors(nid)) + list(G.successors(nid))
        if not connected:
            ideal_x[nid] = positions[nid]["x"]
            continue

        cxs = sorted([_node_center_x(positions[nb]) for nb in connected if nb in positions])
        if not cxs:
            ideal_x[nid] = positions[nid]["x"]
            continue

        mid = len(cxs) // 2
        if len(cxs) % 2 == 1:
            median_cx = cxs[mid]
        else:
            median_cx = (cxs[mid - 1] + cxs[mid]) / 2.0

        w = node_w if nid not in dummy_nodes else 0
        ideal_x[nid] = median_cx - w / 2.0

    _place_with_order(layer, ideal_x, positions, dummy_nodes, node_w, node_sep)


def _place_with_order(
    layer: List[str],
    ideal: Dict[str, float],
    positions: Dict[str, Dict],
    dummy_nodes: Set[str],
    node_w: int,
    node_sep: int,
) -> None:
    """Place nodes at ideal x while maintaining layer order and minimum spacing."""
    n = len(layer)
    if n == 0:
        return

    placed = [ideal.get(nid, positions[nid]["x"]) for nid in layer]

    for i in range(1, n):
        w_prev = node_w if layer[i - 1] not in dummy_nodes else 0
        min_x = placed[i - 1] + w_prev + node_sep
        if placed[i] < min_x:
            placed[i] = min_x

    for i in range(n - 2, -1, -1):
        w_cur = node_w if layer[i] not in dummy_nodes else 0
        max_x = placed[i + 1] - node_sep - w_cur
        if placed[i] > max_x:
            placed[i] = max_x

    for idx, nid in enumerate(layer):
        positions[nid]["x"] = placed[idx]


# ---------------------------------------------------------------------------
# 6. Edge routing (straight lines through dummy waypoints)
# ---------------------------------------------------------------------------

def _route_edges(
    G: nx.DiGraph,
    positions: Dict[str, Dict],
    dummy_nodes: Set[str],
) -> List[Dict[str, Any]]:
    """
    Build edge paths using straight lines through dummy node positions.
    For each original edge, traces through the dummy chain and collects waypoints.
    """
    real_edges: Dict[Tuple[str, str], List[str]] = {}

    for n in list(G.nodes()):
        if n in dummy_nodes:
            continue
        _trace_chains_from(G, n, dummy_nodes, real_edges)

    result = []
    for (src, dst), chain in real_edges.items():
        points = _build_polyline(src, dst, chain, positions)
        result.append({"from": src, "to": dst, "points": points})

    return result


def _trace_chains_from(
    G: nx.DiGraph,
    start: str,
    dummy_nodes: Set[str],
    out: Dict[Tuple[str, str], List[str]],
) -> None:
    """From a real node, follow each outgoing edge through dummy chains."""
    for succ in G.successors(start):
        chain = []
        current = succ
        while current in dummy_nodes:
            chain.append(current)
            nexts = list(G.successors(current))
            if len(nexts) != 1:
                break
            current = nexts[0]
        if current not in dummy_nodes:
            out[(start, current)] = chain


def _build_polyline(
    src: str,
    dst: str,
    chain: List[str],
    positions: Dict[str, Dict],
) -> List[List[float]]:
    """Build a polyline from src through dummy chain to dst (straight line segments)."""
    sp = positions[src]
    dp = positions[dst]

    src_cx = sp["x"] + sp["w"] / 2
    src_bottom = sp["y"] + sp["h"]
    dst_cx = dp["x"] + dp["w"] / 2
    dst_top = dp["y"]

    if not chain:
        return [[round(src_cx, 1), round(src_bottom, 1)],
                [round(dst_cx, 1), round(dst_top, 1)]]

    points: List[List[float]] = [[round(src_cx, 1), round(src_bottom, 1)]]

    for d in chain:
        dp_ = positions[d]
        wx = dp_["x"]
        wy = dp_["y"]
        points.append([round(wx, 1), round(wy, 1)])

    points.append([round(dst_cx, 1), round(dst_top, 1)])
    return points
