"""Rule-based workflow graph validator — pure Python, no LLM calls (per D-14).

Implements 7 validation rules:
    1. cycle               — Graph has a cycle (blocks execution)
    2. unknown_cube        — Node references a cube not in the registry
    3. missing_required_param — Required input is not connected or manually set
    4. dangling_source_handle — Edge sourceHandle not in cube's output definitions
    5. dangling_target_handle — Edge targetHandle not in cube's input definitions
    6. type_mismatch       — Connected params have incompatible types (warning)
    7. orphan_node         — Node has zero connections in a multi-node graph (warning)
"""

from app.agents.schemas import ValidationIssue, ValidationResponse
from app.engine.executor import topological_sort
from app.schemas.workflow import WorkflowGraph


def validate_graph(graph: WorkflowGraph, registry) -> ValidationResponse:
    """Validate a workflow graph for structural issues.

    Args:
        graph: The workflow graph to validate.
        registry: CubeRegistry instance for cube definition lookup.

    Returns:
        ValidationResponse with a list of issues found. Empty list means valid.
    """
    issues: list[ValidationIssue] = []

    # -----------------------------------------------------------------------
    # Rule 1: Cycle check — early return (cycles make other checks meaningless)
    # -----------------------------------------------------------------------
    try:
        topological_sort(graph.nodes, graph.edges)
    except ValueError:
        issues.append(ValidationIssue(
            severity="error",
            node_id=None,
            cube_name=None,
            param_name=None,
            message="Workflow contains a cycle. Circular connections are not allowed.",
            rule="cycle",
        ))
        return ValidationResponse(issues=issues)

    # Build node -> cube definition map (skip unknown cubes after flagging them)
    node_cube_map: dict[str, object] = {}  # node_id -> CubeDefinition

    # -----------------------------------------------------------------------
    # Rule 2: Unknown cube check
    # -----------------------------------------------------------------------
    for node in graph.nodes:
        cube_instance = registry.get(node.data.cube_id)
        if cube_instance is None:
            issues.append(ValidationIssue(
                severity="error",
                node_id=node.id,
                cube_name=None,
                param_name=None,
                message=(
                    f"Cube '{node.data.cube_id}' is not registered in the catalog. "
                    f"It cannot be validated or executed."
                ),
                rule="unknown_cube",
            ))
        else:
            node_cube_map[node.id] = cube_instance.definition

    # -----------------------------------------------------------------------
    # Rule 3: Missing required params
    # -----------------------------------------------------------------------
    for node in graph.nodes:
        defn = node_cube_map.get(node.id)
        if defn is None:
            continue  # Already flagged as unknown cube

        # Build set of params satisfied by incoming edges
        connected_inputs = {
            e.targetHandle
            for e in graph.edges
            if e.target == node.id and e.targetHandle is not None
        }

        for param in defn.inputs:
            if not param.required:
                continue

            # Satisfied by manual value?
            manual_value = node.data.params.get(param.name)
            if manual_value not in (None, "", []):
                continue

            # Satisfied by connection?
            if param.name in connected_inputs:
                continue

            issues.append(ValidationIssue(
                severity="error",
                node_id=node.id,
                cube_name=defn.name,
                param_name=param.name,
                message=(
                    f"Cube '{defn.name}' is missing required input '{param.name}'. "
                    f"Connect a data source or enter a value."
                ),
                rule="missing_required_param",
            ))

    # -----------------------------------------------------------------------
    # Rule 4: Dangling handles
    # -----------------------------------------------------------------------
    for edge in graph.edges:
        src_defn = node_cube_map.get(edge.source)
        tgt_defn = node_cube_map.get(edge.target)

        # Source side
        if src_defn is not None and edge.sourceHandle is not None:
            valid_outputs = {p.name for p in src_defn.outputs}
            valid_outputs.add("__full_result__")  # Special convention — never flagged
            if edge.sourceHandle not in valid_outputs:
                issues.append(ValidationIssue(
                    severity="error",
                    node_id=edge.source,
                    cube_name=src_defn.name,
                    param_name=edge.sourceHandle,
                    message=(
                        f"Cube '{src_defn.name}' has a connection from unknown output "
                        f"'{edge.sourceHandle}'. Remove this edge or update the cube."
                    ),
                    rule="dangling_source_handle",
                ))

        # Target side
        if tgt_defn is not None and edge.targetHandle is not None:
            valid_inputs = {p.name for p in tgt_defn.inputs}
            if edge.targetHandle not in valid_inputs:
                issues.append(ValidationIssue(
                    severity="error",
                    node_id=edge.target,
                    cube_name=tgt_defn.name,
                    param_name=edge.targetHandle,
                    message=(
                        f"Cube '{tgt_defn.name}' has a connection to unknown input "
                        f"'{edge.targetHandle}'. Remove this edge or update the cube."
                    ),
                    rule="dangling_target_handle",
                ))

    # -----------------------------------------------------------------------
    # Rule 5: Type mismatch warnings
    # -----------------------------------------------------------------------
    for edge in graph.edges:
        if edge.sourceHandle == "__full_result__":
            continue  # Full result is polymorphic — skip type check
        if edge.sourceHandle is None or edge.targetHandle is None:
            continue

        src_defn = node_cube_map.get(edge.source)
        tgt_defn = node_cube_map.get(edge.target)
        if src_defn is None or tgt_defn is None:
            continue

        src_param = next((p for p in src_defn.outputs if p.name == edge.sourceHandle), None)
        tgt_param = next((p for p in tgt_defn.inputs if p.name == edge.targetHandle), None)

        if src_param is not None and tgt_param is not None:
            if src_param.type != tgt_param.type:
                issues.append(ValidationIssue(
                    severity="warning",
                    node_id=edge.target,
                    cube_name=tgt_defn.name,
                    param_name=edge.targetHandle,
                    message=(
                        f"'{src_defn.name}.{edge.sourceHandle}' ({src_param.type.value}) "
                        f"is connected to '{tgt_defn.name}.{edge.targetHandle}' "
                        f"({tgt_param.type.value}). Types differ -- connection is allowed "
                        f"but may produce unexpected results."
                    ),
                    rule="type_mismatch",
                ))

    # -----------------------------------------------------------------------
    # Rule 6: Orphan node warnings (only meaningful in multi-node graphs)
    # -----------------------------------------------------------------------
    if len(graph.nodes) > 1:
        all_connected_nodes: set[str] = set()
        for edge in graph.edges:
            all_connected_nodes.add(edge.source)
            all_connected_nodes.add(edge.target)

        for node in graph.nodes:
            if node.id not in all_connected_nodes:
                defn = node_cube_map.get(node.id)
                cube_name = defn.name if defn is not None else node.data.cube_id
                issues.append(ValidationIssue(
                    severity="warning",
                    node_id=node.id,
                    cube_name=cube_name,
                    param_name=None,
                    message=(
                        f"Cube '{cube_name}' has no connections. "
                        f"It will not execute in this workflow."
                    ),
                    rule="orphan_node",
                ))

    return ValidationResponse(issues=issues)
