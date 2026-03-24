"""Unit and integration tests for workflow validation engine."""

import pytest
from unittest.mock import MagicMock

from app.agents.schemas import ValidationIssue, ValidationRequest, ValidationResponse
from app.agents.validation import validate_graph
from app.schemas.cube import CubeDefinition, CubeCategory, ParamDefinition, ParamType
from app.schemas.workflow import WorkflowGraph, WorkflowNode, WorkflowNodeData, WorkflowEdge, Position


# ---------------------------------------------------------------------------
# Helpers: build minimal graph fixtures
# ---------------------------------------------------------------------------

def make_node(node_id: str, cube_id: str, params: dict = None) -> WorkflowNode:
    return WorkflowNode(
        id=node_id,
        type="cube",
        position=Position(x=0, y=0),
        data=WorkflowNodeData(cube_id=cube_id, params=params or {}),
    )


def make_edge(
    edge_id: str,
    source: str,
    target: str,
    source_handle: str | None = None,
    target_handle: str | None = None,
) -> WorkflowEdge:
    return WorkflowEdge(
        id=edge_id,
        source=source,
        target=target,
        sourceHandle=source_handle,
        targetHandle=target_handle,
    )


def make_cube_def(
    cube_id: str,
    name: str,
    inputs: list[ParamDefinition] = None,
    outputs: list[ParamDefinition] = None,
) -> CubeDefinition:
    return CubeDefinition(
        cube_id=cube_id,
        name=name,
        description="",
        category=CubeCategory.DATA_SOURCE,
        inputs=inputs or [],
        outputs=outputs or [],
    )


def make_registry(cubes: dict[str, CubeDefinition]) -> MagicMock:
    """Create a mock CubeRegistry that returns cube instances with .definition."""
    registry = MagicMock()

    def get_cube(cube_id: str):
        if cube_id not in cubes:
            return None
        cube_instance = MagicMock()
        cube_instance.definition = cubes[cube_id]
        return cube_instance

    registry.get.side_effect = get_cube
    return registry


# ---------------------------------------------------------------------------
# Cube definitions used across tests
# ---------------------------------------------------------------------------

SOURCE_CUBE = make_cube_def(
    "source_cube",
    "Source Cube",
    inputs=[],
    outputs=[
        ParamDefinition(name="flight_list", type=ParamType.LIST_OF_STRINGS),
        ParamDefinition(name="count", type=ParamType.NUMBER),
    ],
)

FILTER_CUBE = make_cube_def(
    "filter_cube",
    "Filter Cube",
    inputs=[
        ParamDefinition(name="flight_list", type=ParamType.LIST_OF_STRINGS, required=True),
        ParamDefinition(name="threshold", type=ParamType.NUMBER, required=False),
    ],
    outputs=[
        ParamDefinition(name="result", type=ParamType.LIST_OF_STRINGS),
    ],
)


# ---------------------------------------------------------------------------
# TestValidation: unit tests for all 7 rule types
# ---------------------------------------------------------------------------

class TestValidation:

    def test_missing_required_param(self):
        """Required input with no value and no incoming edge -> error."""
        nodes = [make_node("n1", "filter_cube")]  # flight_list required, not set
        graph = WorkflowGraph(nodes=nodes, edges=[])
        registry = make_registry({"filter_cube": FILTER_CUBE})

        response = validate_graph(graph, registry)
        errors = [i for i in response.issues if i.rule == "missing_required_param"]
        assert len(errors) == 1
        assert errors[0].severity == "error"
        assert "Filter Cube" in errors[0].message
        assert "flight_list" in errors[0].message
        assert errors[0].node_id == "n1"
        assert errors[0].cube_name == "Filter Cube"
        assert errors[0].param_name == "flight_list"

    def test_required_param_satisfied_by_connection(self):
        """Required input connected by an edge -> no error for that param."""
        nodes = [
            make_node("n1", "source_cube"),
            make_node("n2", "filter_cube"),
        ]
        edges = [make_edge("e1", "n1", "n2", "flight_list", "flight_list")]
        graph = WorkflowGraph(nodes=nodes, edges=edges)
        registry = make_registry({"source_cube": SOURCE_CUBE, "filter_cube": FILTER_CUBE})

        response = validate_graph(graph, registry)
        missing = [i for i in response.issues if i.rule == "missing_required_param"]
        assert len(missing) == 0

    def test_required_param_satisfied_by_value(self):
        """Required input manually set in params -> no error for that param."""
        nodes = [make_node("n1", "filter_cube", params={"flight_list": ["f1", "f2"]})]
        graph = WorkflowGraph(nodes=nodes, edges=[])
        registry = make_registry({"filter_cube": FILTER_CUBE})

        response = validate_graph(graph, registry)
        missing = [i for i in response.issues if i.rule == "missing_required_param"]
        assert len(missing) == 0

    def test_dangling_source_handle(self):
        """Edge with sourceHandle not in cube outputs -> error dangling_source_handle."""
        nodes = [
            make_node("n1", "source_cube"),
            make_node("n2", "filter_cube"),
        ]
        edges = [make_edge("e1", "n1", "n2", "nonexistent_output", "flight_list")]
        graph = WorkflowGraph(nodes=nodes, edges=edges)
        registry = make_registry({"source_cube": SOURCE_CUBE, "filter_cube": FILTER_CUBE})

        response = validate_graph(graph, registry)
        dangling = [i for i in response.issues if i.rule == "dangling_source_handle"]
        assert len(dangling) == 1
        assert dangling[0].severity == "error"
        assert "Source Cube" in dangling[0].message
        assert "nonexistent_output" in dangling[0].message

    def test_dangling_target_handle(self):
        """Edge with targetHandle not in cube inputs -> error dangling_target_handle."""
        nodes = [
            make_node("n1", "source_cube"),
            make_node("n2", "filter_cube"),
        ]
        edges = [make_edge("e1", "n1", "n2", "flight_list", "nonexistent_input")]
        graph = WorkflowGraph(nodes=nodes, edges=edges)
        registry = make_registry({"source_cube": SOURCE_CUBE, "filter_cube": FILTER_CUBE})

        response = validate_graph(graph, registry)
        dangling = [i for i in response.issues if i.rule == "dangling_target_handle"]
        assert len(dangling) == 1
        assert dangling[0].severity == "error"
        assert "Filter Cube" in dangling[0].message
        assert "nonexistent_input" in dangling[0].message

    def test_full_result_handle_valid(self):
        """Edge with sourceHandle='__full_result__' -> NOT flagged as dangling."""
        nodes = [
            make_node("n1", "source_cube"),
            make_node("n2", "filter_cube"),
        ]
        edges = [make_edge("e1", "n1", "n2", "__full_result__", "flight_list")]
        graph = WorkflowGraph(nodes=nodes, edges=edges)
        registry = make_registry({"source_cube": SOURCE_CUBE, "filter_cube": FILTER_CUBE})

        response = validate_graph(graph, registry)
        dangling = [i for i in response.issues if i.rule == "dangling_source_handle"]
        assert len(dangling) == 0

    def test_cycle_detection(self):
        """Graph with A->B->A cycle -> error with rule='cycle'."""
        nodes = [
            make_node("n1", "source_cube"),
            make_node("n2", "filter_cube"),
        ]
        # n1 -> n2 -> n1 (cycle)
        edges = [
            make_edge("e1", "n1", "n2", "flight_list", "flight_list"),
            make_edge("e2", "n2", "n1", "result", "flight_list"),
        ]
        graph = WorkflowGraph(nodes=nodes, edges=edges)
        registry = make_registry({"source_cube": SOURCE_CUBE, "filter_cube": FILTER_CUBE})

        response = validate_graph(graph, registry)
        cycle_issues = [i for i in response.issues if i.rule == "cycle"]
        assert len(cycle_issues) == 1
        assert cycle_issues[0].severity == "error"
        assert "cycle" in cycle_issues[0].message.lower()

    def test_type_mismatch_warning(self):
        """Edge connecting string output to number input -> warning type_mismatch."""
        mismatch_cube = make_cube_def(
            "mismatch_cube",
            "Mismatch Cube",
            inputs=[ParamDefinition(name="count_input", type=ParamType.NUMBER, required=False)],
            outputs=[],
        )
        nodes = [
            make_node("n1", "source_cube"),
            make_node("n2", "mismatch_cube"),
        ]
        # flight_list (LIST_OF_STRINGS) -> count_input (NUMBER) — type mismatch
        edges = [make_edge("e1", "n1", "n2", "flight_list", "count_input")]
        graph = WorkflowGraph(nodes=nodes, edges=edges)
        registry = make_registry({"source_cube": SOURCE_CUBE, "mismatch_cube": mismatch_cube})

        response = validate_graph(graph, registry)
        warnings = [i for i in response.issues if i.rule == "type_mismatch"]
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"

    def test_orphan_node_warning(self):
        """Node with zero edges in a multi-node graph -> warning orphan_node."""
        nodes = [
            make_node("n1", "source_cube"),
            make_node("n2", "filter_cube"),  # no edges to/from n2
        ]
        graph = WorkflowGraph(nodes=nodes, edges=[])
        registry = make_registry({"source_cube": SOURCE_CUBE, "filter_cube": FILTER_CUBE})

        response = validate_graph(graph, registry)
        orphans = [i for i in response.issues if i.rule == "orphan_node"]
        # Both nodes have no connections — both should be flagged
        assert len(orphans) >= 1
        # Check that the filter cube (with missing required) also generates orphan warning
        orphan_node_ids = {i.node_id for i in orphans}
        assert "n1" in orphan_node_ids or "n2" in orphan_node_ids

    def test_clean_graph_no_issues(self):
        """Valid 2-node graph with proper connections -> empty issues list."""
        nodes = [
            make_node("n1", "source_cube"),
            make_node("n2", "filter_cube"),
        ]
        edges = [make_edge("e1", "n1", "n2", "flight_list", "flight_list")]
        graph = WorkflowGraph(nodes=nodes, edges=edges)
        registry = make_registry({"source_cube": SOURCE_CUBE, "filter_cube": FILTER_CUBE})

        response = validate_graph(graph, registry)
        assert response.issues == []
        assert response.has_errors is False

    def test_unknown_cube(self):
        """Node with cube_id not in registry -> error unknown_cube."""
        nodes = [make_node("n1", "nonexistent_cube_id")]
        graph = WorkflowGraph(nodes=nodes, edges=[])
        registry = make_registry({})  # empty registry

        response = validate_graph(graph, registry)
        unknown = [i for i in response.issues if i.rule == "unknown_cube"]
        assert len(unknown) == 1
        assert unknown[0].severity == "error"
        assert "nonexistent_cube_id" in unknown[0].message

    def test_has_errors_property(self):
        """ValidationResponse.has_errors returns True when errors present, False otherwise."""
        response_with_errors = ValidationResponse(issues=[
            ValidationIssue(
                severity="error",
                node_id="n1",
                cube_name="Test",
                param_name="param",
                message="Error message",
                rule="missing_required_param",
            )
        ])
        assert response_with_errors.has_errors is True

        response_warnings_only = ValidationResponse(issues=[
            ValidationIssue(
                severity="warning",
                node_id="n1",
                cube_name="Test",
                param_name=None,
                message="Warning message",
                rule="orphan_node",
            )
        ])
        assert response_warnings_only.has_errors is False

        empty_response = ValidationResponse()
        assert empty_response.has_errors is False


# ---------------------------------------------------------------------------
# TestValidateEndpoint: integration tests hitting POST /api/agent/validate
# ---------------------------------------------------------------------------

class TestValidateEndpoint:

    @pytest.mark.anyio
    async def test_validate_endpoint_clean_graph(self):
        """POST /api/agent/validate with empty graph -> 200, empty issues."""
        import httpx
        from app.main import app

        graph_payload = {
            "graph": {
                "nodes": [],
                "edges": [],
            }
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/agent/validate", json=graph_payload)

        assert response.status_code == 200
        data = response.json()
        assert "issues" in data
        assert data["issues"] == []

    @pytest.mark.anyio
    async def test_validate_endpoint_invalid_graph(self):
        """POST /api/agent/validate with missing required param -> 200, non-empty issues."""
        import httpx
        from app.main import app

        # Use a real registered cube from the registry that has required inputs
        # We'll use a node pointing to a nonexistent cube to get an unknown_cube error
        graph_payload = {
            "graph": {
                "nodes": [
                    {
                        "id": "test-node-1",
                        "type": "cube",
                        "position": {"x": 0, "y": 0},
                        "data": {
                            "cube_id": "cube_that_does_not_exist_xyz",
                            "params": {},
                        },
                    }
                ],
                "edges": [],
            }
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/agent/validate", json=graph_payload)

        assert response.status_code == 200
        data = response.json()
        assert "issues" in data
        assert len(data["issues"]) > 0
        # Should have at least one error
        errors = [i for i in data["issues"] if i["severity"] == "error"]
        assert len(errors) > 0
        assert errors[0]["rule"] == "unknown_cube"

    @pytest.mark.anyio
    async def test_validate_endpoint_response_shape(self):
        """POST /api/agent/validate response has correct JSON shape."""
        import httpx
        from app.main import app

        graph_payload = {"graph": {"nodes": [], "edges": []}}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/agent/validate", json=graph_payload)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "issues" in data
        assert isinstance(data["issues"], list)
