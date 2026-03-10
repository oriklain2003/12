/**
 * Geo column detection utility.
 * Inspects the first row of a result set to find latitude, longitude,
 * and/or geometry columns for map rendering.
 *
 * Supports three modes:
 *  1. lat/lon only — point markers from scalar columns
 *  2. lat/lon + geometry — uses geometry objects, falls back to lat/lon
 *  3. geometry only — uses GeoJSON geometry objects (LineString, Polygon, etc.)
 */

export interface GeoInfo {
  latCol?: string;
  lonCol?: string;
  geomCol?: string;
}

const LAT_EXACT = /^(lat|latitude|lat_deg|y)$/i;
const LAT_SUFFIX = /_lat$|_latitude$/i;
const LON_EXACT = /^(lon|lng|long|longitude|lon_deg|x)$/i;
const LON_SUFFIX = /_lon$|_longitude$/i;
const GEOM_EXACT = /^(geometry|geom|geojson|shape|the_geom)$/i;

/**
 * Detects latitude, longitude, and/or geometry columns from result rows.
 *
 * @param rows - Array of result row objects
 * @returns GeoInfo if any geo columns found, null otherwise
 */
export function detectGeoColumns(rows: unknown[]): GeoInfo | null {
  if (!rows || rows.length === 0) return null;

  const firstRow = rows[0];
  if (typeof firstRow !== 'object' || firstRow === null) return null;

  const keys = Object.keys(firstRow as Record<string, unknown>);
  const row = firstRow as Record<string, unknown>;

  // Detect lat/lon columns
  const latCol = keys.find((k) => LAT_EXACT.test(k) || LAT_SUFFIX.test(k)) ?? null;
  const lonCol = keys.find((k) => LON_EXACT.test(k) || LON_SUFFIX.test(k)) ?? null;

  const hasLatLon =
    latCol !== null &&
    lonCol !== null &&
    isFinite(Number(row[latCol])) &&
    isFinite(Number(row[lonCol]));

  // Detect geometry column
  const geomCol = keys.find((k) => GEOM_EXACT.test(k)) ?? null;
  const hasGeom =
    geomCol !== null &&
    row[geomCol] !== null &&
    typeof row[geomCol] === 'object';

  if (!hasLatLon && !hasGeom) return null;

  const result: GeoInfo = {};
  if (hasLatLon) {
    result.latCol = latCol!;
    result.lonCol = lonCol!;
  }
  if (hasGeom) {
    result.geomCol = geomCol!;
  }

  return result;
}
