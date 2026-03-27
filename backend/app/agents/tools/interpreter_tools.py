"""Interpreter Agent tools — tools for results interpretation.

Tools registered here:
- read_pipeline_summary: Walks upstream from a node to build a pipeline chain string
- read_cube_results: Fetches detailed results for a specific cube node
"""

from app.agents.context import ToolContext
from app.agents.registry import agent_tool


@agent_tool(
    name="read_pipeline_summary",
    description=(
        "Walk the workflow graph upstream from a given node and return the pipeline chain "
        "as a readable string (e.g. 'all_flights -> squawk_filter -> signal_health_analyzer'). "
        "Use this to give context about how data flows to the cube being interpreted."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "node_id": {
                "type": "string",
                "description": "Node ID of the cube to trace upstream from",
            },
        },
        "required": ["node_id"],
    },
)
async def read_pipeline_summary(ctx: ToolContext, node_id: str) -> dict:
    """Walk upstream from node_id using BFS and return the pipeline chain string."""
    if ctx.workflow_graph is None:
        return {"error": "No workflow graph available."}

    nodes = ctx.workflow_graph.get("nodes", [])
    edges = ctx.workflow_graph.get("edges", [])

    if not nodes:
        return {"error": "Workflow graph has no nodes."}

    nodes_by_id = {n["id"]: n for n in nodes}

    chain = []
    visited: set[str] = set()
    queue = [node_id]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        node = nodes_by_id.get(current)
        if node:
            cube_id = node.get("data", {}).get("cube_id") or node.get("data", {}).get(
                "cubeDef", {}
            ).get("id", current)
            chain.append(cube_id)

        # Find all upstream nodes (edges where this node is the target)
        for e in edges:
            if e.get("target") == current and e.get("source") not in visited:
                queue.append(e["source"])

    chain.reverse()
    return {"pipeline": " -> ".join(chain), "cube_count": len(chain)}


@agent_tool(
    name="read_cube_results",
    description=(
        "Fetch results for a specific cube node from the execution results. "
        "Returns row count, column names, and up to 10 sample rows. "
        "Use this when the analyst asks specific questions about the data."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "node_id": {
                "type": "string",
                "description": "Node ID of the cube to fetch results for",
            },
        },
        "required": ["node_id"],
    },
)
async def read_cube_results(ctx: ToolContext, node_id: str) -> dict:
    """Return detailed results for a specific cube node."""
    if ctx.execution_results is None:
        return {"error": "No execution results available."}

    data = ctx.execution_results.get(node_id)
    if data is None:
        available = list(ctx.execution_results.keys())
        return {
            "error": f"No results found for node_id '{node_id}'.",
            "available_node_ids": available,
        }

    # Handle both dict-with-rows and list formats (matches canvas_tools.py pattern)
    rows = data.get("rows", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    columns = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []

    return {
        "node_id": node_id,
        "row_count": len(rows),
        "columns": columns,
        "sample_rows": rows[:10],
        "truncated": data.get("truncated", False) if isinstance(data, dict) else False,
    }
