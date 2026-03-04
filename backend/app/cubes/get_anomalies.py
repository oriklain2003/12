"""GetAnomalies cube: queries Tracer 42 research.anomaly_reports for given flight_ids."""

from typing import Any

from sqlalchemy import text

from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class GetAnomaliesCube(BaseCube):
    """Fetches anomaly report records from research.anomaly_reports for given flight IDs."""

    cube_id = "get_anomalies"
    name = "Get Anomalies"
    description = "Fetch anomaly reports from Tracer 42 for given flight IDs"
    category = CubeCategory.DATA_SOURCE

    inputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            required=True,
            description="List of flight_id strings to fetch anomaly reports for.",
        ),
        ParamDefinition(
            name="min_severity",
            type=ParamType.NUMBER,
            required=False,
            description="Minimum severity_cnn score 0.0-1.0. Only returns reports at or above this threshold.",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="anomalies",
            type=ParamType.JSON_OBJECT,
            description="Array of anomaly report objects.",
        ),
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Unique flight_ids with anomaly records.",
        ),
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        """Query anomaly_reports for given flight_ids with optional severity filter."""
        flight_ids = inputs.get("flight_ids") or []
        min_severity = inputs.get("min_severity")

        # Guard: empty flight_ids would cause PostgreSQL ANY() error
        if not flight_ids:
            return {"anomalies": [], "flight_ids": []}

        sql_parts = [
            """
            SELECT
                id, flight_id, timestamp, is_anomaly,
                severity_cnn, severity_dense,
                callsign, airline, origin_airport, destination_airport,
                aircraft_type, geographic_region, is_military,
                matched_rule_ids, matched_rule_names
            FROM research.anomaly_reports
            WHERE flight_id = ANY(:flight_ids)
            """
        ]
        params: dict[str, Any] = {"flight_ids": list(flight_ids)}

        if min_severity is not None:
            sql_parts.append("AND severity_cnn >= :min_severity")
            params["min_severity"] = float(min_severity)

        full_sql = "\n".join(sql_parts)

        async with engine.connect() as conn:
            result = await conn.execute(text(full_sql), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        unique_ids = list({row["flight_id"] for row in rows})

        return {
            "anomalies": rows,
            "flight_ids": unique_ids,
        }
