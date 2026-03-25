"""Wizard tools — Build Wizard Agent tools for workflow construction.

Three tools:
  - present_options: Return structured option cards for the LLM to present choices.
  - show_intent_preview: Return a node/connection graph preview structure.
  - generate_workflow: Validate the graph, save to DB with mission metadata, return workflow_id.
"""

import uuid
from datetime import datetime, timezone

from app.agents.context import ToolContext
from app.agents.registry import agent_tool
from app.agents.validation import validate_graph
from app.models.workflow import Workflow
from app.schemas.workflow import (
    Position,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeData,
)


@agent_tool(
    name="present_options",
    description=(
        "Show clickable option cards to the analyst. Use this to present structured choices "
        "during workflow building — mission types, data sources, filter cubes, etc. "
        "The frontend renders these as interactive card selectors. "
        "IMPORTANT: After calling this tool, end your turn immediately with a brief prompt. "
        "Wait for the analyst's next message with their selection before continuing."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question or prompt to show the analyst above the option cards.",
            },
            "options": {
                "type": "array",
                "description": "Array of option cards to display.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for the option.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Display title for the option card.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional longer description shown on the card.",
                        },
                    },
                    "required": ["id", "title"],
                },
            },
            "multi_select": {
                "type": "boolean",
                "description": (
                    "If true, analyst can select multiple options. "
                    "Use true for filter selection; false for data source, analysis type, etc."
                ),
            },
        },
        "required": ["question", "options"],
    },
)
async def present_options(
    ctx: ToolContext,
    question: str = "",
    options: list = None,
    multi_select: bool = False,
) -> dict:
    """Return structured option card data for the frontend to render."""
    return {
        "question": question,
        "options": options or [],
        "multi_select": multi_select,
        "awaiting_user_input": True,
        "instruction": "STOP. The analyst sees interactive cards in the UI. You MUST end your turn NOW and wait for their next message with their selection. Do NOT continue speaking or call any more tools.",
    }


@agent_tool(
    name="show_intent_preview",
    description=(
        "Show a visual mini-graph preview of the planned workflow to the analyst before generating. "
        "Displays planned cube nodes and their connections so the analyst can confirm or adjust. "
        "The frontend renders this as an interactive preview with 'Build This' and 'Adjust Plan' buttons. "
        "IMPORTANT: After calling this tool, end your turn immediately. "
        "Wait for the analyst to click 'Build This' or 'Adjust Plan' before continuing."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "mission_name": {
                "type": "string",
                "description": "Name for the workflow mission (e.g., 'Squawk 7700 in Jordan FIR').",
            },
            "mission_description": {
                "type": "string",
                "description": "Brief description of what this workflow analyzes.",
            },
            "nodes": {
                "type": "array",
                "description": "Planned cube nodes to include in the workflow.",
                "items": {
                    "type": "object",
                    "properties": {
                        "cube_id": {
                            "type": "string",
                            "description": "The cube identifier (e.g., 'all_flights', 'squawk_filter').",
                        },
                        "label": {
                            "type": "string",
                            "description": "Display label for this node in the preview.",
                        },
                        "key_params": {
                            "type": "object",
                            "description": "Key parameter values to display in the preview.",
                        },
                    },
                    "required": ["cube_id", "label"],
                },
            },
            "connections": {
                "type": "array",
                "description": "Planned connections between cubes.",
                "items": {
                    "type": "object",
                    "properties": {
                        "from_cube": {
                            "type": "string",
                            "description": "Source cube_id.",
                        },
                        "from_output": {
                            "type": "string",
                            "description": "Source output parameter name.",
                        },
                        "to_cube": {
                            "type": "string",
                            "description": "Target cube_id.",
                        },
                        "to_input": {
                            "type": "string",
                            "description": "Target input parameter name.",
                        },
                    },
                    "required": ["from_cube", "to_cube"],
                },
            },
        },
        "required": ["mission_name", "nodes"],
    },
)
async def show_intent_preview(
    ctx: ToolContext,
    mission_name: str = "",
    mission_description: str = "",
    nodes: list = None,
    connections: list = None,
) -> dict:
    """Return a structured preview of the planned workflow for frontend rendering."""
    return {
        "mission_name": mission_name,
        "mission_description": mission_description,
        "nodes": nodes or [],
        "connections": connections or [],
    }


@agent_tool(
    name="generate_workflow",
    description=(
        "Generate, validate, and save a complete workflow. Builds the workflow graph from the "
        "provided nodes and edges, validates it against the cube catalog, and saves it to the "
        "database with mission metadata. Returns the workflow_id on success, or validation errors "
        "if the graph is invalid (retry up to 2 times after fixing errors)."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Workflow name (e.g., 'Squawk 7700 in Jordan FIR').",
            },
            "mission_description": {
                "type": "string",
                "description": "Description of what this workflow analyzes.",
            },
            "analysis_intent": {
                "type": "string",
                "description": "The analyst's original intent/question this workflow answers.",
            },
            "nodes": {
                "type": "array",
                "description": "Workflow nodes (cubes) to include.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique node ID (use cube_id + '_1' pattern, e.g., 'all_flights_1').",
                        },
                        "cube_id": {
                            "type": "string",
                            "description": "The cube identifier from the catalog.",
                        },
                        "position": {
                            "type": "object",
                            "description": "Canvas position (x, y). Use x = depth * 300, y = index * 200.",
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                            },
                            "required": ["x", "y"],
                        },
                        "params": {
                            "type": "object",
                            "description": "Parameter values for this cube node.",
                        },
                    },
                    "required": ["id", "cube_id", "position"],
                },
            },
            "edges": {
                "type": "array",
                "description": "Connections between cube nodes.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique edge ID.",
                        },
                        "source": {
                            "type": "string",
                            "description": "Source node ID.",
                        },
                        "target": {
                            "type": "string",
                            "description": "Target node ID.",
                        },
                        "sourceHandle": {
                            "type": "string",
                            "description": "Source output parameter name (must match cube's output param names exactly).",
                        },
                        "targetHandle": {
                            "type": "string",
                            "description": "Target input parameter name (must match cube's input param names exactly).",
                        },
                    },
                    "required": ["id", "source", "target"],
                },
            },
        },
        "required": ["name", "nodes"],
    },
)
async def generate_workflow(
    ctx: ToolContext,
    name: str = "",
    mission_description: str = "",
    analysis_intent: str = "",
    nodes: list = None,
    edges: list = None,
) -> dict:
    """Validate the graph and save the workflow to DB with mission metadata.

    Returns {"status": "created", "workflow_id": ..., "workflow_name": ...} on success.
    Returns {"status": "validation_failed", "errors": [...]} if the graph has errors.
    """
    nodes = nodes or []
    edges = edges or []

    # Build WorkflowGraph from provided nodes/edges
    wf_nodes = [
        WorkflowNode(
            id=n["id"],
            type="cube",
            position=Position(x=n["position"]["x"], y=n["position"]["y"]),
            data=WorkflowNodeData(
                cube_id=n["cube_id"],
                params=n.get("params", {}),
            ),
        )
        for n in nodes
    ]
    wf_edges = [
        WorkflowEdge(
            id=e["id"],
            source=e["source"],
            target=e["target"],
            sourceHandle=e.get("sourceHandle"),
            targetHandle=e.get("targetHandle"),
        )
        for e in edges
    ]
    graph = WorkflowGraph(nodes=wf_nodes, edges=wf_edges)

    # Validate graph against cube registry
    result = validate_graph(graph, ctx.cube_registry)
    if result.has_errors:
        return {
            "status": "validation_failed",
            "errors": [
                issue.model_dump()
                for issue in result.issues
                if issue.severity == "error"
            ],
        }

    # Build graph dict with mission metadata
    graph_dict = graph.model_dump()
    graph_dict["metadata"] = {
        "mission": {
            "description": mission_description or "",
            "analysis_intent": analysis_intent or "",
            "created_by": "build_wizard",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    }

    # Save to database
    wf = Workflow(id=uuid.uuid4(), name=name, graph_json=graph_dict)
    ctx.db_session.add(wf)
    await ctx.db_session.commit()
    await ctx.db_session.refresh(wf)

    return {
        "status": "created",
        "workflow_id": str(wf.id),
        "workflow_name": wf.name,
    }
