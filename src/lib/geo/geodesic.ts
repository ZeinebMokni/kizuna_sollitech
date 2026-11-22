/**
 * Geodesic and GIS geometry utility functions for QATRA.
 * Based on WGS84 ellipsoid approximations for accurate area in hectares.
 */

const EARTH_RADIUS_METERS = 6378137.0;

/**
 * Calculates geodesic area of a polygon defined by [lng, lat] coordinates in Hectares (1 Ha = 10,000 m²).
 * Uses spherical polygon area formula (spherical excess).
 */
export function calculatePolygonAreaHectares(coordinates: [number, number][]): number {
  if (!coordinates || coordinates.length < 3) return 0;

  // Ensure ring closes
  const points = [...coordinates];
  if (
    points[0][0] !== points[points.length - 1][0] ||
    points[0][1] !== points[points.length - 1][1]
  ) {
    points.push(points[0]);
  }

  let totalAngle = 0;
  const numPoints = points.length - 1;

  for (let i = 0; i < numPoints; i++) {
    const p1 = points[i];
    const p2 = points[i + 1];

    const lambda1 = (p1[0] * Math.PI) / 180;
    const phi1 = (p1[1] * Math.PI) / 180;
    const lambda2 = (p2[0] * Math.PI) / 180;
    const phi2 = (p2[1] * Math.PI) / 180;

    totalAngle += (lambda2 - lambda1) * (2 + Math.sin(phi1) + Math.sin(phi2));
  }

  const areaM2 = Math.abs((totalAngle * EARTH_RADIUS_METERS * EARTH_RADIUS_METERS) / 2.0);
  const areaHa = areaM2 / 10000.0;
  return Number(areaHa.toFixed(2));
}

/**
 * Calculates the bounding box [minLng, minLat, maxLng, maxLat] of a set of coordinates.
 */
export function getBoundingBox(coordinates: [number, number][]): [number, number, number, number] {
  let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
  for (const [lng, lat] of coordinates) {
    if (lng < minLng) minLng = lng;
    if (lat < minLat) minLat = lat;
    if (lng > maxLng) maxLng = lng;
    if (lat > maxLat) maxLat = lat;
  }
  return [minLng, minLat, maxLng, maxLat];
}

/**
 * Computes polygon centroid [lng, lat].
 */
export function calculateCentroid(coordinates: [number, number][]): [number, number] {
  if (!coordinates || coordinates.length === 0) return [0, 0];
  let sumLng = 0;
  let sumLat = 0;
  for (const [lng, lat] of coordinates) {
    sumLng += lng;
    sumLat += lat;
  }
  return [
    Number((sumLng / coordinates.length).toFixed(5)),
    Number((sumLat / coordinates.length).toFixed(5)),
  ];
}

/**
 * Formats [lng, lat] to standard readable GPS coordinates (e.g. 35.0382° N, 9.4858° E).
 */
export function formatGPSCoordinates(coords: [number, number]): string {
  const [lng, lat] = coords;
  const latDir = lat >= 0 ? 'N' : 'S';
  const lngDir = lng >= 0 ? 'E' : 'O';
  return `${Math.abs(lat).toFixed(4)}° ${latDir}, ${Math.abs(lng).toFixed(4)}° ${lngDir}`;
}

/**
 * Tests if point [lng, lat] is inside polygon using ray-casting algorithm.
 */
export function isPointInPolygon(point: [number, number], vs: [number, number][]): boolean {
  const x = point[0], y = point[1];
  let inside = false;
  for (let i = 0, j = vs.length - 1; i < vs.length; j = i++) {
    const xi = vs[i][0], yi = vs[i][1];
    const xj = vs[j][0], yj = vs[j][1];
    const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}
