"""Tests for NetworkGraphBuilderCube — airport network graph construction.

Tests cover:
- Cube metadata (id, category, inputs/outputs)
- Builds route graph from flight data (correct nodes, edges, weights)
- min_edge_weight filtering (only edges meeting threshold)
- Centrality scores (hub airport has higher centrality)
- Empty input handling
"""

import pytest


# ============================================================
# Helpers
# ============================================================


def make_flight(flight_id: str, origin: str, dest: str, callsign: str = "CS001"):
    """Build a minimal flight dict."""
    return {
        "flight_id": flight_id,
        "origin_airport": origin,
        "destination_airport": dest,
        "callsign": callsign,
    }


# ============================================================
# Cube metadata
# ============================================================


def test_cube_metadata():
    """NetworkGraphBuilderCube has correct cube_id, name, and category."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube
    from app.schemas.cube import CubeCategory

    cube = NetworkGraphBuilderCube()
    assert cube.cube_id == "network_graph_builder"
    assert cube.name == "Network Graph Builder"
    assert cube.category == CubeCategory.ANALYSIS


def test_cube_inputs():
    """NetworkGraphBuilderCube has the required inputs."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    input_names = {p.name for p in cube.inputs}
    assert "flights" in input_names
    assert "graph_type" in input_names
    assert "min_edge_weight" in input_names


def test_cube_outputs():
    """NetworkGraphBuilderCube has the required outputs."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    output_names = {p.name for p in cube.outputs}
    assert "nodes" in output_names
    assert "edges" in output_names
    assert "stats" in output_names


def test_flights_input_accepts_full_result():
    """flights input has accepts_full_result=True."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    flights_param = next(p for p in cube.inputs if p.name == "flights")
    assert flights_param.accepts_full_result is True


# ============================================================
# Route graph building
# ============================================================


@pytest.mark.asyncio
async def test_builds_route_graph():
    """Builds correct nodes, edges, and weights from flight data."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    flights = [
        make_flight("f1", "TLV", "JFK", "EL001"),
        make_flight("f2", "TLV", "JFK", "EL002"),
        make_flight("f3", "JFK", "TLV", "EL003"),
        make_flight("f4", "TLV", "LHR", "BA001"),
    ]

    result = await cube.execute(flights=flights)

    # 3 airports
    assert result["stats"]["total_nodes"] == 3
    # 3 directed edges: TLV->JFK, JFK->TLV, TLV->LHR
    assert result["stats"]["total_edges"] == 3

    # Check TLV->JFK edge has weight 2
    tlv_jfk = next(e for e in result["edges"] if e["source"] == "TLV" and e["target"] == "JFK")
    assert tlv_jfk["weight"] == 2
    assert sorted(tlv_jfk["callsigns"]) == ["EL001", "EL002"]
    assert set(tlv_jfk["flight_ids"]) == {"f1", "f2"}

    # Edges sorted by weight descending
    weights = [e["weight"] for e in result["edges"]]
    assert weights == sorted(weights, reverse=True)


@pytest.mark.asyncio
async def test_nodes_sorted_by_degree_centrality():
    """Nodes are sorted by degree_centrality descending."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    flights = [
        make_flight("f1", "TLV", "JFK"),
        make_flight("f2", "TLV", "LHR"),
        make_flight("f3", "TLV", "CDG"),
        make_flight("f4", "JFK", "LHR"),
    ]

    result = await cube.execute(flights=flights)

    centralities = [n["degree_centrality"] for n in result["nodes"]]
    assert centralities == sorted(centralities, reverse=True)


# ============================================================
# min_edge_weight filtering
# ============================================================


@pytest.mark.asyncio
async def test_min_edge_weight_filtering():
    """Only edges meeting min_edge_weight threshold are included."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    flights = [
        # TLV->JFK: 3 flights
        make_flight("f1", "TLV", "JFK"),
        make_flight("f2", "TLV", "JFK"),
        make_flight("f3", "TLV", "JFK"),
        # TLV->LHR: 1 flight (below threshold)
        make_flight("f4", "TLV", "LHR"),
    ]

    result = await cube.execute(flights=flights, min_edge_weight=2)

    # Only TLV->JFK edge should remain
    assert result["stats"]["total_edges"] == 1
    assert result["edges"][0]["source"] == "TLV"
    assert result["edges"][0]["target"] == "JFK"
    assert result["edges"][0]["weight"] == 3
    # Only TLV and JFK nodes (LHR filtered out)
    assert result["stats"]["total_nodes"] == 2


# ============================================================
# Centrality scores
# ============================================================


@pytest.mark.asyncio
async def test_hub_airport_higher_centrality():
    """Hub airport connected to many others has higher centrality."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    # TLV is a hub connecting to 4 airports; spoke airports only connect to TLV
    flights = [
        make_flight("f1", "TLV", "JFK"),
        make_flight("f2", "TLV", "LHR"),
        make_flight("f3", "TLV", "CDG"),
        make_flight("f4", "TLV", "FRA"),
        make_flight("f5", "JFK", "TLV"),
    ]

    result = await cube.execute(flights=flights)

    node_map = {n["id"]: n for n in result["nodes"]}
    tlv = node_map["TLV"]
    jfk = node_map["JFK"]

    # TLV should have higher degree centrality than any spoke
    assert tlv["degree_centrality"] > jfk["degree_centrality"]
    # TLV is the first node (sorted by degree_centrality desc)
    assert result["nodes"][0]["id"] == "TLV"

    # Verify node fields
    assert "in_degree" in tlv
    assert "out_degree" in tlv
    assert "betweenness_centrality" in tlv


@pytest.mark.asyncio
async def test_betweenness_centrality_for_bridge_node():
    """A node that bridges two clusters has high betweenness centrality."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    # HUB bridges cluster {A, B} and cluster {C, D}
    flights = [
        make_flight("f1", "A", "HUB"),
        make_flight("f2", "B", "HUB"),
        make_flight("f3", "HUB", "C"),
        make_flight("f4", "HUB", "D"),
    ]

    result = await cube.execute(flights=flights)

    node_map = {n["id"]: n for n in result["nodes"]}
    assert node_map["HUB"]["betweenness_centrality"] > node_map["A"]["betweenness_centrality"]


# ============================================================
# Empty input handling
# ============================================================


@pytest.mark.asyncio
async def test_empty_flights_returns_empty():
    """Empty flight list returns empty results."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    result = await cube.execute(flights=[])

    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["stats"]["total_nodes"] == 0
    assert result["stats"]["total_edges"] == 0
    assert result["stats"]["density"] == 0.0


@pytest.mark.asyncio
async def test_none_flights_returns_empty():
    """None flights input returns empty results."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    result = await cube.execute(flights=None)

    assert result["nodes"] == []
    assert result["edges"] == []
    assert result["stats"]["total_nodes"] == 0


@pytest.mark.asyncio
async def test_flights_missing_airports_skipped():
    """Flights without origin or destination airports are skipped."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    flights = [
        {"flight_id": "f1", "origin_airport": "TLV"},  # no destination
        {"flight_id": "f2", "destination_airport": "JFK"},  # no origin
        make_flight("f3", "TLV", "JFK"),  # valid
    ]

    result = await cube.execute(flights=flights)

    assert result["stats"]["total_edges"] == 1
    assert result["stats"]["total_nodes"] == 2


# ============================================================
# Full result wrapping
# ============================================================


@pytest.mark.asyncio
async def test_extracts_flights_from_full_result_flights_key():
    """Flights extracted from full_result dict with 'flights' key."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    wrapped = {
        "flights": [make_flight("f1", "TLV", "JFK")],
        "flight_ids": ["f1"],
    }

    result = await cube.execute(flights=wrapped)

    assert result["stats"]["total_edges"] == 1


@pytest.mark.asyncio
async def test_extracts_flights_from_full_result_filtered_flights_key():
    """Flights extracted from full_result dict with 'filtered_flights' key."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    wrapped = {
        "filtered_flights": [make_flight("f1", "TLV", "JFK")],
    }

    result = await cube.execute(flights=wrapped)

    assert result["stats"]["total_edges"] == 1


@pytest.mark.asyncio
async def test_density_calculation():
    """Density is correctly computed via networkx."""
    from app.cubes.network_graph_builder import NetworkGraphBuilderCube

    cube = NetworkGraphBuilderCube()
    # Complete graph: A->B, B->A => density = 2 / (2*1) = 1.0
    flights = [
        make_flight("f1", "A", "B"),
        make_flight("f2", "B", "A"),
    ]

    result = await cube.execute(flights=flights)

    assert result["stats"]["density"] == pytest.approx(1.0)
