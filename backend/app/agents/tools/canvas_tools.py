"""Canvas Agent tools — four tools for reading and modifying the workflow canvas.

Tools registered here:
- read_workflow_graph: Returns the current workflow graph from ToolContext
- propose_graph_diff: Proposes structured canvas changes (add/remove nodes/edges, update params)
- read_execution_errors: Returns errors from the last workflow run
- read_execution_results: Returns summarized results from the last workflow run
"""

from app.agents.context import ToolContext
from app.agents.registry import agent_tool


@agent_tool(
    name="read_workflow_graph",
    description="Return the current workflow graph state (nodes, edges, parameter values). The graph is also included in every request context, so use this only if you need to re-read after mid-conversation changes.",
    parameters_schema={"type": "object", "properties": {}},
)
async def read_workflow_graph(ctx: ToolContext) -> dict:
    """Return the serialized workflow graph from context."""
    if ctx.workflow_graph is None:
        return {"error": "No workflow graph available. The user may not have a workflow open."}
    return {"workflow_graph": ctx.workflow_graph}


@agent_tool(
    name="propose_graph_diff",
    description="Propose a set of changes to the workflow canvas. Returns a structured diff with additions, removals, and parameter updates. The user will see this as a reviewable proposal with Apply/Reject buttons.",
    parameters_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Human-readable summary of what this diff does"},
            "add_nodes": {
                "type": "array",
                "description": "Nodes to add to the canvas",
                "items": {
                    "type": "object",
                    "properties": {
                        "cube_id": {"type": "string", "description": "Cube type ID from catalog"},
                        "position_x": {"type": "number", "description": "X position on canvas"},
                        "position_y": {"type": "number", "description": "Y position on canvas"},
                        "params": {"type": "object", "description": "Parameter values to set"},
                        "label": {"type": "string", "description": "Optional display label"},
                    },
                    "required": ["cube_id", "position_x", "position_y"],
                },
            },
            "remove_node_ids": {
                "type": "array",
                "description": "IDs of nodes to remove",
                "items": {"type": "string"},
            },
            "update_params": {
                "type": "array",
                "description": "Parameter updates on existing nodes",
                "items": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                        "params": {"type": "object", "description": "Key-value param updates to merge"},
                    },
                    "required": ["node_id", "params"],
                },
            },
            "add_edges": {
                "type": "array",
                "description": "Edges to add between nodes",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source node ID"},
                        "target": {"type": "string", "description": "Target node ID"},
                        "source_handle": {"type": "string", "description": "Source output handle ID"},
                        "target_handle": {"type": "string", "description": "Target input handle ID"},
                    },
                    "required": ["source", "target"],
                },
            },
            "remove_edge_ids": {
                "type": "array",
                "description": "IDs of edges to remove",
                "items": {"type": "string"},
            },
        },
        "required": ["summary"],
    },
)
async def propose_graph_diff(ctx: ToolContext, **kwargs) -> dict:
    """Return a structured diff proposal for the canvas. Restructures flat position_x/y into nested position."""
    diff = dict(kwargs)
    if "add_nodes" in diff and diff["add_nodes"]:
        for node in diff["add_nodes"]:
            if "position_x" in node and "position_y" in node:
                node["position"] = {"x": node.pop("position_x"), "y": node.pop("position_y")}
    return {"proposed_diff": diff}


@agent_tool(
    name="read_execution_errors",
    description="Return error messages from the last workflow execution for each failed cube. Use this in Fix mode to diagnose pipeline failures.",
    parameters_schema={"type": "object", "properties": {}},
)
async def read_execution_errors(ctx: ToolContext) -> dict:
    """Return execution errors from context."""
    if ctx.execution_errors is None:
        return {"error": "No execution errors available. Run the workflow first."}
    return {"execution_errors": ctx.execution_errors}


@agent_tool(
    name="read_execution_results",
    description="Return summarized results from the last workflow execution: row count, column names, and up to 3 sample rows per cube. Results are capped at the store limit.",
    parameters_schema={"type": "object", "properties": {}},
)
async def read_execution_results(ctx: ToolContext) -> dict:
    """Return summarized execution results from context.

    Summarizes to {row_count, columns, sample_rows(3), truncated} per node
    to avoid sending large datasets to the LLM.
    """
    if ctx.execution_results is None:
        return {"error": "No execution results available. Run the workflow first."}
    # Summarize: per node, extract row_count, columns from first row, sample 3 rows
    summarized = {}
    for node_id, data in ctx.execution_results.items():
        rows = data.get("rows", []) if isinstance(data, dict) else []
        columns = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
        summarized[node_id] = {
            "row_count": len(rows),
            "columns": columns,
            "sample_rows": rows[:3],
            "truncated": data.get("truncated", False) if isinstance(data, dict) else False,
        }
    return {
        "execution_results": summarized,
        "note": "Results shown are capped at the store limit and may not reflect the full execution output.",
    }
