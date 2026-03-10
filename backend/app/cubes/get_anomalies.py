"""GetAnomalies cube: queries Tracer 42 research.anomaly_reports."""

from typing import Any

from sqlalchemy import text

from app.cubes.base import BaseCube
from app.database import engine
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class GetAnomaliesCube(BaseCube):
    """Fetches anomaly report records from research.anomaly_reports."""

    cube_id = "get_anomalies"
    name = "Get Anomalies"
    description = "Fetch anomaly reports from Tracer 42, optionally filtered by flight IDs, anomaly status, or matched rule"
    category = CubeCategory.DATA_SOURCE

    inputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            required=False,
            description="Optional list of flight_id strings to filter by. If empty, queries all anomaly reports.",
        ),
        ParamDefinition(
            name="min_severity",
            type=ParamType.NUMBER,
            required=False,
            description="Minimum severity_cnn score 0.0-1.0. Only returns reports at or above this threshold.",
        ),
        ParamDefinition(
            name="is_anomaly",
            type=ParamType.BOOLEAN,
            required=False,
            description="Filter by anomaly status. True = only anomalies, False = only non-anomalies.",
        ),
        ParamDefinition(
            name="matched_rule_name",
            type=ParamType.STRING,
            required=False,
            description="Filter rows where this rule name appears in the matched_rule_names array.",
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
        """Query anomaly_reports with optional filters."""
        flight_ids = inputs.get("flight_ids") or []
        min_severity = inputs.get("min_severity")
        is_anomaly = inputs.get("is_anomaly")
        matched_rule_name = inputs.get("matched_rule_name")

        sql_parts = [
            """
            SELECT
                id, flight_id, timestamp, is_anomaly,
                severity_cnn, severity_dense,
                callsign, airline, origin_airport, destination_airport,
                aircraft_type, geographic_region, is_military,
                matched_rule_ids, matched_rule_names
            FROM research.anomaly_reports
            WHERE 1=1
            """
        ]
        params: dict[str, Any] = {}

        if flight_ids:
            sql_parts.append("AND flight_id = ANY(:flight_ids)")
            params["flight_ids"] = list(flight_ids)

        if min_severity is not None:
            sql_parts.append("AND severity_cnn >= :min_severity")
            params["min_severity"] = float(min_severity)

        if is_anomaly is not None:
            sql_parts.append("AND is_anomaly = :is_anomaly")
            params["is_anomaly"] = bool(is_anomaly)

        if matched_rule_name:
            sql_parts.append("AND :matched_rule_name = ANY(matched_rule_names)")
            params["matched_rule_name"] = str(matched_rule_name)

        sql_parts.append("LIMIT 5000")

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
