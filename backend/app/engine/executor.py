"""WorkflowExecutor: topological sort, input resolution, Full Result bundling, row limiting, failure isolation."""

import asyncio
import logging
import time
from collections import deque
from typing import Any, AsyncGenerator

logger = logging.getLogger("flow.executor")

from fastapi import HTTPException
from starlette.requests import Request

from app.config import settings
from app.engine.registry import registry
from app.schemas.execution import CubeStatusEvent
from app.schemas.workflow import WorkflowEdge, WorkflowGraph, WorkflowNode


def topological_sort(
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
) -> list[str]:
    """Return node IDs in topological order using Kahn's algorithm.

    Raises:
        ValueError: If the graph contains a cycle.
    """
    node_ids = [node.id for node in nodes]

    # Build adjacency list and in-degree map
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

    for edge in edges:
        if edge.source in adjacency and edge.target in in_degree:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1

    # Start with all zero-in-degree nodes
    queue: deque[str] = deque(
        nid for nid in node_ids if in_degree[nid] == 0
    )
    order: list[str] = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in adjacency[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) < len(node_ids):
        raise ValueError("Workflow graph contains a cycle")

    return order


def resolve_inputs(
    node: WorkflowNode,
    edges: list[WorkflowEdge],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Resolve input values for a node by merging manual params with connection values.

    Connection values take precedence over manually-entered params (BACK-12).
    The __full_result__ sourceHandle bundles all source outputs into a single dict (BACK-10).
    """
    inputs: dict[str, Any] = dict(node.data.params)

    for edge in edges:
        if edge.target != node.id:
            continue

        source_id = edge.source
        source_outputs = results.get(source_id, {}).get("outputs", {})

        if edge.sourceHandle == "__full_result__":
            # Bundle all outputs of the source node into a single dict
            value = source_outputs
        else:
            value = source_outputs.get(edge.sourceHandle)

        if edge.targetHandle is not None:
            inputs[edge.targetHandle] = value

    return inputs


def apply_row_limit(
    outputs: dict[str, Any],
    limit: int | None = None,
) -> tuple[dict[str, Any], bool]:
    """Cap list outputs at the row limit and flag if any were truncated.

    Args:
        outputs: The cube's output dict.
        limit: Row cap; defaults to settings.result_row_limit (10,000).

    Returns:
        (capped_outputs, truncated) where truncated is True if any list was capped.
    """
    if limit is None:
        limit = settings.result_row_limit

    capped: dict[str, Any] = {}
    truncated = False

    for key, value in outputs.items():
        if isinstance(value, list) and len(value) > limit:
            capped[key] = value[:limit]
            truncated = True
        else:
            capped[key] = value

    return capped, truncated


async def stream_graph(
    graph: WorkflowGraph,
    request: Request | None = None,
) -> AsyncGenerator[CubeStatusEvent, None]:
    """Async generator that yields per-cube status events during workflow execution.

    Assumes the graph has already been validated (no cycles). Callers are
    responsible for calling topological_sort and handling ValueError before
    invoking this generator.

    Args:
        graph: The WorkflowGraph containing nodes and edges (already validated).
        request: Optional HTTP request for client-disconnect detection. Pass None
                 when calling from execute_graph or tests without an HTTP context.

    Yields:
        CubeStatusEvent for each status transition:
        - "pending" for all nodes (emitted up-front before execution begins)
        - "running" when a cube starts executing
        - "done" with outputs and truncated flag on success
        - "error" with error message on failure
        - "skipped" for nodes downstream of a failed cube
    """
    order = topological_sort(graph.nodes, graph.edges)
    node_map: dict[str, WorkflowNode] = {node.id: node for node in graph.nodes}
    results: dict[str, dict[str, Any]] = {}
    failed_or_skipped: set[str] = set()

    try:
        # Phase 1: emit pending for ALL nodes before any execution begins
        for node_id in order:
            yield CubeStatusEvent(node_id=node_id, status="pending")

        # Phase 2: execute in topological order, yielding running/done/error/skipped
        for node_id in order:
            # Check for client disconnect between cubes
            if request is not None and await request.is_disconnected():
                break

            node = node_map[node_id]

            # a. Check if any direct upstream node failed or was skipped
            upstream_ids = {
                edge.source
                for edge in graph.edges
                if edge.target == node_id
            }
            if upstream_ids & failed_or_skipped:
                yield CubeStatusEvent(
                    node_id=node_id,
                    status="skipped",
                    reason="upstream cube failed or was skipped",
                )
                failed_or_skipped.add(node_id)
                results[node_id] = {
                    "status": "skipped",
                    "reason": "upstream cube failed or was skipped",
                    "outputs": {},
                }
                continue

            # b. Look up cube
            cube = registry.get(node.data.cube_id)
            if cube is None:
                yield CubeStatusEvent(
                    node_id=node_id,
                    status="error",
                    error=f"Unknown cube: {node.data.cube_id}",
                )
                failed_or_skipped.add(node_id)
                results[node_id] = {
                    "status": "error",
                    "message": f"Unknown cube: {node.data.cube_id}",
                    "outputs": {},
                }
                continue

            # c. Emit running event
            logger.info("Executing cube %s (node %s)", node.data.cube_id, node_id)
            yield CubeStatusEvent(node_id=node_id, status="running")

            # d. Resolve inputs and execute
            inputs = resolve_inputs(node, graph.edges, results)
            try:
                t0 = time.monotonic()
                raw_outputs = await cube.execute(**inputs)
                execution_ms = int((time.monotonic() - t0) * 1000)
                capped_outputs, truncated = apply_row_limit(raw_outputs)
                yield CubeStatusEvent(
                    node_id=node_id,
                    status="done",
                    outputs=capped_outputs,
                    truncated=truncated,
                    execution_ms=execution_ms,
                )
                results[node_id] = {
                    "status": "done",
                    "outputs": capped_outputs,
                    "truncated": truncated,
                }
            except Exception as exc:
                logger.exception("Cube %s (node %s) failed", node.data.cube_id, node_id)
                yield CubeStatusEvent(
                    node_id=node_id,
                    status="error",
                    error=str(exc),
                )
                failed_or_skipped.add(node_id)
                results[node_id] = {
                    "status": "error",
                    "message": str(exc),
                    "outputs": {},
                }

    except asyncio.CancelledError:
        # Required by sse-starlette: re-raise CancelledError to allow clean teardown
        raise


async def execute_graph(graph: WorkflowGraph) -> dict[str, Any]:
    """Execute a workflow graph and return per-node results.

    Delegates to stream_graph internally, collecting events into the same dict
    format as before. This eliminates code duplication between sync and streaming paths.

    Args:
        graph: The WorkflowGraph containing nodes and edges.

    Returns:
        Dict keyed by node_id with shape:
        {
          "node-1": {"status": "done", "outputs": {...}, "truncated": false},
          "node-2": {"status": "error", "message": "...", "outputs": {}},
          "node-3": {"status": "skipped", "reason": "...", "outputs": {}}
        }

    Raises:
        HTTPException(400): If the graph contains a cycle.
    """
    # Validate the graph first so we can raise HTTPException (not inside the generator)
    try:
        topological_sort(graph.nodes, graph.edges)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results: dict[str, dict[str, Any]] = {}

    async for event in stream_graph(graph, request=None):
        if event.status == "done":
            results[event.node_id] = {
                "status": "done",
                "outputs": event.outputs or {},
                "truncated": event.truncated or False,
            }
        elif event.status == "error":
            results[event.node_id] = {
                "status": "error",
                "message": event.error or "",
                "outputs": {},
            }
        elif event.status == "skipped":
            results[event.node_id] = {
                "status": "skipped",
                "reason": event.reason or "upstream cube failed or was skipped",
                "outputs": {},
            }
        # pending and running events are discarded — not part of the final result

    return results
