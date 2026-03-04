/**
 * Geo column detection utility.
 * Inspects the first row of a result set to find latitude, longitude,
 * and optional geometry columns for map rendering.
 */

export interface GeoInfo {
  latCol: string;
  lonCol: string;
  geomCol?: string;
}

const LAT_EXACT = /^(lat|latitude|lat_deg|y)$/i;
const LAT_SUFFIX = /_lat$|_latitude$/i;
const LON_EXACT = /^(lon|lng|long|longitude|lon_deg|x)$/i;
const LON_SUFFIX = /_lon$|_lng$|_longitude$/i;
const GEOM_EXACT = /^(geometry|geom|geojson|shape|the_geom)$/i;

/**
 * Detects latitude, longitude, and optional geometry columns from result rows.
 *
 * @param rows - Array of result row objects
 * @returns GeoInfo if lat/lon columns found with finite numeric values, null otherwise
 */
export function detectGeoColumns(rows: unknown[]): GeoInfo | null {
  if (!rows || rows.length === 0) return null;

  const firstRow = rows[0];
  if (typeof firstRow !== 'object' || firstRow === null) return null;

  const keys = Object.keys(firstRow as Record<string, unknown>);

  const latCol = keys.find((k) => LAT_EXACT.test(k) || LAT_SUFFIX.test(k)) ?? null;
  const lonCol = keys.find((k) => LON_EXACT.test(k) || LON_SUFFIX.test(k)) ?? null;

  if (!latCol || !lonCol) return null;

  // Validate that the matched columns contain finite numeric values in the first row
  const row = firstRow as Record<string, unknown>;
  if (!isFinite(Number(row[latCol]))) return null;
  if (!isFinite(Number(row[lonCol]))) return null;

  const geomCol = keys.find((k) => GEOM_EXACT.test(k));

  return geomCol ? { latCol, lonCol, geomCol } : { latCol, lonCol };
}
