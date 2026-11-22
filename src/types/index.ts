export type Language = 'fr' | 'ar' | 'en';

export interface User {
  id: string;
  name: string;
  email: string;
  role: 'farmer' | 'buyer' | 'agronomist' | 'admin';
  farmId?: string;
  avatarUrl?: string;
}

export type HealthStatus = 'healthy' | 'warning' | 'critical' | 'irrigating' | 'nodata';

export type MapLayerMode = 
  | 'satellite'
  | 'ndvi'
  | 'elevation'
  | 'health' 
  | 'moisture' 
  | 'temperature' 
  | 'irrigation' 
  | 'energy' 
  | 'crop'
  | 'alerts'
  | 'historical'
  | 'prediction';

export interface NDVIStats {
  min: number;
  mean: number;
  max: number;
  standardDeviation: number;
  acquisitionDate: string;
  cloudCoverPercent: number;
  sensor: 'Sentinel-2 L2A MSI' | 'Copernicus CDSE';
  resolutionMeters: 10;
}

export interface SatelliteScene {
  id: string;
  acquisitionDate: string; // ISO format or YYYY-MM-DD
  cloudCoverPercent: number;
  tileUrl: string;
  ndviTileUrl?: string;
  sunElevationAngle: number;
  sensor: string;
  orbitNumber: number;
  attribution: string;
}

export interface IrrigationPipe {
  id: string;
  name: string;
  coordinates: [number, number][]; // LineString coords [lng, lat]
  valveStatus: 'open' | 'closed';
  flowRateM3H: number;
  pressureBar: number;
}

export interface DrawingState {
  isDrawing: boolean;
  drawingType: 'farm_boundary' | 'zone_polygon' | null;
  currentPoints: [number, number][]; // [lng, lat]
  activeZoneDraft?: {
    name: string;
    cropType: string;
    targetMoistureMin: number;
    targetMoistureMax: number;
  };
}

export interface GeoPolygon {
  type: 'Polygon';
  coordinates: number[][][]; // [lng, lat]
}

export interface FarmZone {
  id: string;
  farmId: string;
  name: string;
  cropType: string;
  variety?: string;
  plantingDate: string;
  areaHa: number;
  soilType: string;
  status: HealthStatus;
  soilMoisturePercent: number; // 0-100%
  targetMoistureMin: number;
  targetMoistureMax: number;
  temperatureC: number;
  humidityPercent: number;
  irrigationStatus: 'active' | 'scheduled' | 'idle';
  irrigationMethod: 'Goutte-à-goutte' | 'Pivot' | 'Micro-aspersion';
  dailyWaterLiters: number;
  dailyEnergyKwh: number;
  predictedHarvestDate: string;
  yieldEstimateTons: number;
  polygon: GeoPolygon;
  center: [number, number]; // [lng, lat]
  alertsCount: number;
  sensorsAssigned: string[];
  ndviStats?: NDVIStats;
}

export interface Farm {
  id: string;
  name: string;
  ownerName: string;
  governorate: string; // e.g. Sidi Bouzid, Kairouan
  delegation: string;
  totalAreaHa: number;
  centerCoordinates: [number, number]; // [lng, lat]
  boundary: GeoPolygon;
  waterSource: 'Puits profond (Sondage)' | 'Retenue collinaire' | 'Réseau Sonede' | 'Eau recyclée';
  wellDepthMeters: number;
  waterSalinityGPerL: number;
  solarCapacityKw: number;
  batteryCapacityKwh: number;
  storageTankVolumeM3: number;
  currentTankLevelPercent: number;
  gridAvailable: boolean;
  zones: FarmZone[];
}

export type DeviceType = 
  | 'esp32_gateway' 
  | 'soil_sensor' 
  | 'temp_humidity' 
  | 'water_flow' 
  | 'irrigation_pump' 
  | 'solar_inverter' 
  | 'battery_bms';

export interface Device {
  id: string;
  name: string;
  type: DeviceType;
  zoneId?: string;
  status: 'online' | 'offline' | 'warning' | 'alert';
  batteryPercent?: number;
  lastPing: string;
  ipAddress?: string;
  firmwareVersion: string;
  coordinates: [number, number]; // [lng, lat]
  readings: Record<string, number | string | boolean>;
}

export interface IrrigationSchedule {
  id: string;
  zoneId: string;
  zoneName: string;
  startTime: string; // "05:30"
  durationMinutes: number;
  daysOfWeek: number[]; // 0-6
  solarTriggerOnly: boolean; // only start if solar energy > pump demand
  enabled: boolean;
}

export interface EnergyTelemetry {
  timestamp: string;
  solarProductionKw: number;
  pumpConsumptionKw: number;
  auxiliaryConsumptionKw: number;
  batterySoCPercent: number;
  batteryPowerKw: number; // positive = charging, negative = discharging
  gridAvailable: boolean;
  gridImportKw: number;
}

export interface MarketForecast {
  id: string;
  cropName: string;
  category: 'Légumes' | 'Fruits' | 'Céréales' | 'Huiles' | 'Fourrages';
  season: string;
  nationalDemandTons: number;
  projectedSupplyTons: number;
  balanceRatio: number; // >1 = surplus, <1 = deficit
  balanceStatus: 'Déficit élevé (Opportunité)' | 'Équilibré' | 'Surproduction prévue (Risque)';
  currentAvgPriceTnd: number;
  projectedPriceTnd: number;
  priceTrend: 'up' | 'down' | 'stable';
  confidenceScore: number; // 0-100%
  topProducingGovernorates: string[];
  driverInsights: string;
}

export interface CropRecommendation {
  id: string;
  cropName: string;
  category: string;
  suitabilityScore: number; // 0-100
  waterRequirementM3Ha: number;
  energyRequirementKwhHa: number;
  growthDurationDays: number;
  harvestPeriod: string;
  estimatedYieldTonsHa: number;
  estimatedCostTndHa: number;
  estimatedRevenueTndHa: number;
  netMarginTndHa: number;
  droughtResistance: 'Haute' | 'Moyenne' | 'Faible';
  solarFitScore: number; // 0-100
  whyRecommended: string[];
  keyRisks: string[];
}

export interface ProductListing {
  id: string;
  farmerName: string;
  farmName: string;
  governorate: string;
  cropName: string;
  variety: string;
  quantityKg: number;
  harvestDate: string;
  askingPriceTndKg: number;
  qualityGrade: 'Extra' | 'Catégorie I' | 'Catégorie II';
  status: 'available' | 'reserved' | 'sold';
  description: string;
  certifications: string[];
  inquiryCount: number;
  createdAt: string;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  severity: 'info' | 'success' | 'warning' | 'critical';
  timestamp: string;
  category: 'irrigation' | 'energy' | 'sensor' | 'market' | 'alert';
  read: boolean;
  actionUrl?: string;
  zoneId?: string;
}
