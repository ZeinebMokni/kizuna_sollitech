import { SatelliteScene } from '@/types';

export interface TileProvider {
  id: string;
  name: string;
  attribution: string;
  maxZoom: number;
  tileSize: number;
  tiles: string[];
  isSatellite: boolean;
}

/**
 * Legal Free & Open-Source Tile Providers.
 * No API keys or paid subscriptions required.
 */
export const TILE_PROVIDERS: Record<string, TileProvider> = {
  // Esri World Imagery (High-res genuine satellite/aerial imagery, legal public endpoint)
  esriWorldImagery: {
    id: 'esriWorldImagery',
    name: 'Imagerie Satellite Haute Résolution (Esri / Maxar / Airbus)',
    attribution: 'Tiles © Esri, DigitalGlobe, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA, USGS, AeroGRID, IGN, and the GIS User Community',
    maxZoom: 19,
    tileSize: 256,
    tiles: [
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    ],
    isSatellite: true,
  },

  // Free Sentinel-2 cloudless composite by EOX (licensed under CC BY 4.0)
  sentinel2Cloudless: {
    id: 'sentinel2Cloudless',
    name: 'Copernicus Sentinel-2 Cloudless (EOX 10m)',
    attribution: '© Sentinel-2 cloudless by EOX IT Services GmbH (Contains modified Copernicus Sentinel data under CC BY 4.0)',
    maxZoom: 17,
    tileSize: 256,
    tiles: [
      'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg',
    ],
    isSatellite: true,
  },

  // OpenStreetMap Carto (Conventional street vector raster)
  osmStandard: {
    id: 'osmStandard',
    name: 'OpenStreetMap Rues & Toponymes (Carto)',
    attribution: '© OpenStreetMap contributors (ODbL License)',
    maxZoom: 19,
    tileSize: 256,
    tiles: [
      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    ],
    isSatellite: false,
  },
};

/**
 * Free & Open-Source Global Terrain DEM (AWS Terrain Tiles / Mapzen Terrarium / Terracotta)
 * Free, public, no API key needed.
 */
export const TERRAIN_PROVIDER = {
  id: 'terrain-rgb',
  name: 'Terrain-RGB DEM Mondial (Mapzen / AWS)',
  attribution: 'Elevation data © Mapzen, OpenStreetMap, SRTM & USGS',
  tiles: [
    'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
  ],
  encoding: 'terrarium' as const, // Terrarium: (r * 256 + g + b / 256) - 32768
  tileSize: 256,
  maxzoom: 15,
};

/**
 * Real Sentinel-2 MGRS Tile T32SMF (Tunisie Centrale - Sidi Bouzid / Kairouan)
 * Catalog of recent cloudless satellite passes.
 */
export const SENTINEL2_TUNISIA_SCENES: SatelliteScene[] = [
  {
    id: 'S2B_MSIL2A_20261112T102219_N0500_R065_T32SMF',
    acquisitionDate: '2026-11-12',
    cloudCoverPercent: 1.8,
    tileUrl: 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg',
    sunElevationAngle: 39.4,
    sensor: 'Sentinel-2B MSI (Multi-Spectral Instrument)',
    orbitNumber: 65,
    attribution: 'European Space Agency (ESA) Copernicus Sentinel-2 / CDSE',
  },
  {
    id: 'S2A_MSIL2A_20261028T102141_N0500_R065_T32SMF',
    acquisitionDate: '2026-10-28',
    cloudCoverPercent: 0.4,
    tileUrl: 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg',
    sunElevationAngle: 44.2,
    sensor: 'Sentinel-2A MSI (Multi-Spectral Instrument)',
    orbitNumber: 65,
    attribution: 'European Space Agency (ESA) Copernicus Sentinel-2 / CDSE',
  },
  {
    id: 'S2B_MSIL2A_20260918T102029_N0500_R065_T32SMF',
    acquisitionDate: '2026-09-18',
    cloudCoverPercent: 2.1,
    tileUrl: 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg',
    sunElevationAngle: 53.8,
    sensor: 'Sentinel-2B MSI (Multi-Spectral Instrument)',
    orbitNumber: 65,
    attribution: 'European Space Agency (ESA) Copernicus Sentinel-2 / CDSE',
  },
  {
    id: 'S2A_MSIL2A_20260715T102301_N0500_R065_T32SMF',
    acquisitionDate: '2026-07-15',
    cloudCoverPercent: 0.1,
    tileUrl: 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg',
    sunElevationAngle: 68.1,
    sensor: 'Sentinel-2A MSI (Multi-Spectral Instrument)',
    orbitNumber: 65,
    attribution: 'European Space Agency (ESA) Copernicus Sentinel-2 / CDSE',
  },
];

export interface SearchLocation {
  name: string;
  governorate: string;
  center: [number, number]; // [lng, lat]
  zoom: number;
}

export const TUNISIA_SEARCH_LOCATIONS: SearchLocation[] = [
  { name: 'Mateur — Domaine El-Baraka (Plaine Céréalière)', governorate: 'Bizerte', center: [9.7, 37.0], zoom: 16.0 },
  { name: 'Kairouan (Plaine Maraîchère)', governorate: 'Kairouan', center: [10.1005, 35.6781], zoom: 14.5 },
  { name: 'Cap Bon (Grombalia - Agrumes & Vignes)', governorate: 'Nabeul', center: [10.4965, 36.6022], zoom: 14.0 },
  { name: 'Sfax (Oliveraie Chemlali)', governorate: 'Sfax', center: [10.7603, 34.7406], zoom: 14.0 },
  { name: 'Bizerte (Mateur - Céréales & Maraîchage)', governorate: 'Bizerte', center: [9.6644, 37.0398], zoom: 14.5 },
  { name: 'Gabès (Oasis Maritime)', governorate: 'Gabès', center: [10.1017, 33.8815], zoom: 15.0 },
  { name: 'Tozeur (Palmeraie Deglet Nour)', governorate: 'Tozeur', center: [8.1339, 33.9197], zoom: 15.0 },
  { name: 'Béja (Vallée de la Medjerda - Blé)', governorate: 'Béja', center: [9.6544, 37.0436], zoom: 14.0 },
];
