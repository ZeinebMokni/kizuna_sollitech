/**
 * Precise astronomical solar calculations for solar positioning & light direction.
 * Based on NOAA Solar Calculator equations.
 */

export interface SunPosition {
  azimuth: number; // degrees from North (0° = North, 90° = East, 180° = South, 270° = West)
  altitude: number; // degrees above horizon (-90° to +90°)
  isDaylight: boolean;
  solarNoon: string;
  sunrise: string;
  sunset: string;
  compassDirection: string;
}

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

function getDayOfYear(date: Date): number {
  const start = new Date(date.getFullYear(), 0, 0);
  const diff = date.getTime() - start.getTime() + (start.getTimezoneOffset() - date.getTimezoneOffset()) * 60000;
  return Math.floor(diff / (1000 * 60 * 60 * 24));
}

export function calculateSunPosition(date: Date, lat: number, lng: number): SunPosition {
  const dayOfYear = getDayOfYear(date);
  const hours = date.getHours() + date.getMinutes() / 60 + date.getSeconds() / 3600;

  // Fractional year in radians
  const gamma = (2 * Math.PI / 365) * (dayOfYear - 1 + (hours - 12) / 24);

  // Equation of time in minutes
  const eqtime = 229.18 * (
    0.000075 +
    0.001868 * Math.cos(gamma) -
    0.032077 * Math.sin(gamma) -
    0.014615 * Math.cos(2 * gamma) -
    0.040849 * Math.sin(2 * gamma)
  );

  // Solar declination angle in radians
  const decl = 0.006918 -
    0.399912 * Math.cos(gamma) +
    0.070257 * Math.sin(gamma) -
    0.006758 * Math.cos(2 * gamma) +
    0.000907 * Math.sin(2 * gamma) -
    0.002697 * Math.cos(3 * gamma) +
    0.00148 * Math.sin(3 * gamma);

  // Time offset in minutes (assuming local timezone offset in minutes)
  const timezoneOffsetMinutes = -date.getTimezoneOffset(); // e.g. UTC+1 for Tunisia = +60
  const timeOffset = eqtime + 4 * lng - timezoneOffsetMinutes;

  // True solar time in minutes
  const tst = hours * 60 + timeOffset;

  // Solar hour angle in degrees
  let ha = (tst / 4) - 180;
  if (ha < -180) ha += 360;
  if (ha > 180) ha -= 360;

  const latRad = lat * RAD;
  const haRad = ha * RAD;

  // Solar zenith angle
  const cosZenith = Math.sin(latRad) * Math.sin(decl) + Math.cos(latRad) * Math.cos(decl) * Math.cos(haRad);
  const zenith = Math.acos(Math.max(-1, Math.min(1, cosZenith)));
  const altitude = 90 - (zenith * DEG);

  // Solar azimuth angle (degrees clockwise from North)
  const cosAzimuth = (Math.sin(decl) - Math.sin(latRad) * Math.cos(zenith)) / (Math.cos(latRad) * Math.sin(zenith));
  let azimuth = Math.acos(Math.max(-1, Math.min(1, cosAzimuth))) * DEG;
  if (ha > 0) {
    azimuth = 360 - azimuth;
  }

  // Compass text
  const directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  const index = Math.round(azimuth / 22.5) % 16;
  const compassDirection = directions[index];

  // Approximate sunrise/sunset
  const hourAngleSunrise = Math.acos(
    Math.max(-1, Math.min(1, Math.cos(90.833 * RAD) / (Math.cos(latRad) * Math.cos(decl)) - Math.tan(latRad) * Math.tan(decl)))
  ) * DEG;

  const solarNoonMinutes = 720 - 4 * lng - eqtime + timezoneOffsetMinutes;
  const sunriseMinutes = solarNoonMinutes - hourAngleSunrise * 4;
  const sunsetMinutes = solarNoonMinutes + hourAngleSunrise * 4;

  const formatTime = (totalMin: number) => {
    let m = Math.round(totalMin);
    if (m < 0) m += 1440;
    if (m >= 1440) m -= 1440;
    const h = Math.floor(m / 60);
    const min = m % 60;
    return `${h.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}`;
  };

  return {
    azimuth: Math.round(azimuth * 10) / 10,
    altitude: Math.round(altitude * 10) / 10,
    isDaylight: altitude > -0.5,
    solarNoon: formatTime(solarNoonMinutes),
    sunrise: formatTime(sunriseMinutes),
    sunset: formatTime(sunsetMinutes),
    compassDirection,
  };
}
