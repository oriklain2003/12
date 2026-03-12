"""NetworkGraphBuilder cube: builds airport-to-airport directed network graph from flight metadata."""

import logging
from collections import defaultdict
from typing import Any

import networkx as nx

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType

logger = logging.getLogger(__name__)


class NetworkGraphBuilderCube(BaseCube):
    """Builds a directed network graph of airport-to-airport routes from flight data."""

    cube_id = "network_graph_builder"
    name = "Network Graph Builder"
    description = "Build an airport-to-airport directed network graph with centrality metrics from flight data"
    category = CubeCategory.ANALYSIS

    inputs = [
        ParamDefinition(
            name="flights",
            type=ParamType.JSON_OBJECT,
            required=True,
            accepts_full_result=True,
            description="Array of flight objects with origin_airport and destination_airport",
        ),
        ParamDefinition(
            name="graph_type",
            type=ParamType.STRING,
            required=False,
            default="route",
            widget_hint="select",
            options=["route"],
            description="Graph type",
        ),
        ParamDefinition(
            name="min_edge_weight",
            type=ParamType.NUMBER,
            required=False,
            default=1,
            description="Minimum flight count to include an edge",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="nodes",
            type=ParamType.JSON_OBJECT,
            description="Array of node objects with centrality metrics",
        ),
        ParamDefinition(
            name="edges",
            type=ParamType.JSON_OBJECT,
            description="Array of edge objects with weight and callsigns",
        ),
        ParamDefinition(
            name="stats",
            type=ParamType.JSON_OBJECT,
            description="Graph statistics (total_nodes, total_edges, density)",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Build network graph from flight data and compute centrality metrics."""
        flights_input = inputs.get("flights")
        min_edge_weight = inputs.get("min_edge_weight", 1)
        if min_edge_weight is None:
            min_edge_weight = 1

        # Extract flight list — handle full_result wrapping
        flight_list = self._extract_flights(flights_input)

        if not flight_list:
            return {
                "nodes": [],
                "edges": [],
                "stats": {"total_nodes": 0, "total_edges": 0, "density": 0.0},
            }

        # Count edges: (origin, dest) -> {weight, callsigns, flight_ids}
        edge_data: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"weight": 0, "callsigns": set(), "flight_ids": []}
        )

        for flight in flight_list:
            origin = flight.get("origin_airport")
            dest = flight.get("destination_airport")
            if not origin or not dest:
                continue

            key = (origin, dest)
            edge_data[key]["weight"] += 1
            callsign = flight.get("callsign")
            if callsign:
                edge_data[key]["callsigns"].add(callsign)
            flight_id = flight.get("flight_id")
            if flight_id:
                edge_data[key]["flight_ids"].append(flight_id)

        # Build networkx DiGraph with edges meeting min_edge_weight threshold
        G = nx.DiGraph()
        for (origin, dest), data in edge_data.items():
            if data["weight"] >= min_edge_weight:
                G.add_edge(origin, dest, weight=data["weight"])

        if G.number_of_nodes() == 0:
            return {
                "nodes": [],
                "edges": [],
                "stats": {"total_nodes": 0, "total_edges": 0, "density": 0.0},
            }

        # Compute centrality metrics
        degree_centrality = nx.degree_centrality(G)
        betweenness_centrality = nx.betweenness_centrality(G)

        # Build node objects
        node_list = []
        for node in G.nodes():
            node_list.append({
                "id": node,
                "degree_centrality": degree_centrality[node],
                "betweenness_centrality": betweenness_centrality[node],
                "in_degree": G.in_degree(node),
                "out_degree": G.out_degree(node),
            })
        node_list.sort(key=lambda n: n["degree_centrality"], reverse=True)

        # Build edge objects
        edge_list = []
        for (origin, dest), data in edge_data.items():
            if data["weight"] >= min_edge_weight:
                edge_list.append({
                    "source": origin,
                    "target": dest,
                    "weight": data["weight"],
                    "callsigns": sorted(data["callsigns"]),
                    "flight_ids": data["flight_ids"],
                })
        edge_list.sort(key=lambda e: e["weight"], reverse=True)

        # Stats
        stats = {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "density": nx.density(G),
        }

        return {
            "nodes": node_list,
            "edges": edge_list,
            "stats": stats,
        }

    @staticmethod
    def _extract_flights(flights_input: Any) -> list[dict]:
        """Extract flight list from input, handling full_result wrapping."""
        if flights_input is None:
            return []

        # Direct list of flights
        if isinstance(flights_input, list):
            return flights_input

        # Dict — check for wrapped data
        if isinstance(flights_input, dict):
            # Check 'flights' key first
            if "flights" in flights_input:
                val = flights_input["flights"]
                if isinstance(val, list):
                    return val
            # Then 'filtered_flights' key
            if "filtered_flights" in flights_input:
                val = flights_input["filtered_flights"]
                if isinstance(val, list):
                    return val

        return []
