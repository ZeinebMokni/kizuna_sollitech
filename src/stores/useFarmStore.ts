import { create } from 'zustand';
import { Farm, FarmZone, MapLayerMode, HealthStatus, SatelliteScene, DrawingState } from '@/types';
import { DEMO_FARM } from '@/lib/mockData';
import { SENTINEL2_TUNISIA_SCENES } from '@/lib/geo/providers';
import { calculatePolygonAreaHectares, calculateCentroid } from '@/lib/geo/geodesic';

export interface SampledPixel {
  lng: number;
  lat: number;
  ndvi: number;
  nir: number;
  red: number;
  zoneName?: string;
}

interface FarmState {
  farm: Farm;
  selectedZoneId: string | null;
  mapLayerMode: MapLayerMode;
  isSimulating: boolean;
  isPowerOutage: boolean;
  emergencyStopActive: boolean;

  // Real Satellite & NDVI controls
  selectedScene: SatelliteScene;
  historicalCompareScene: SatelliteScene | null;
  tileProviderId: 'sentinel2Cloudless' | 'esriWorldImagery' | 'osmStandard';
  ndviOpacity: number; // 0 to 1
  sampledPixel: SampledPixel | null;
  mapPitch: number; // 0 (2D) to 55 (3D isometric)
  mapBearing: number; // camera rotation

  // 3D Terrain & Sun Simulation
  terrain3DEnabled: boolean;
  terrainExaggeration: number; // 1.0 to 3.0
  elevationOpacity: number; // 0 to 1
  sunSimulationEnabled: boolean;
  simulationTime: string; // ISO time or 'now'

  // Drawing & Zone boundary editing
  drawingState: DrawingState;

  // Actions
  selectZone: (zoneId: string | null) => void;
  setMapLayerMode: (mode: MapLayerMode) => void;
  setSelectedScene: (scene: SatelliteScene) => void;
  setHistoricalCompareScene: (scene: SatelliteScene | null) => void;
  setTileProviderId: (id: 'sentinel2Cloudless' | 'esriWorldImagery' | 'osmStandard') => void;
  setNdviOpacity: (opacity: number) => void;
  setSampledPixel: (pixel: SampledPixel | null) => void;
  setMapPitch: (pitch: number) => void;
  setMapBearing: (bearing: number) => void;
  setTerrain3DEnabled: (enabled: boolean) => void;
  setTerrainExaggeration: (exaggeration: number) => void;
  setElevationOpacity: (opacity: number) => void;
  setSunSimulationEnabled: (enabled: boolean) => void;
  setSimulationTime: (time: string) => void;

  // Drawing actions
  startDrawing: (type: 'farm_boundary' | 'zone_polygon') => void;
  addDrawingPoint: (point: [number, number]) => void;
  undoLastDrawingPoint: () => void;
  cancelDrawing: () => void;
  saveDrawnPolygon: (metadata: { name: string; cropType: string }) => void;
  deleteZone: (zoneId: string) => void;

  // Operations
  startIrrigation: (zoneId: string) => void;
  stopIrrigation: (zoneId: string) => void;
  toggleEmergencyStop: () => void;
  togglePowerOutage: () => void;
  toggleSimulation: () => void;
  tickSimulation: () => void;
  updateZoneThresholds: (zoneId: string, min: number, max: number) => void;
}

export const useFarmStore = create<FarmState>((set, get) => ({
  farm: DEMO_FARM,
  selectedZoneId: 'zone-4', // Default to Zone D (critical need)
  mapLayerMode: 'satellite',   // Satellite imagery of real agricultural fields (Béja)
  isSimulating: true,
  isPowerOutage: false,
  emergencyStopActive: false,

  selectedScene: SENTINEL2_TUNISIA_SCENES[0],
  historicalCompareScene: null,
  tileProviderId: 'esriWorldImagery',
  ndviOpacity: 0.75,
  sampledPixel: null,
  mapPitch: 48,
  mapBearing: -15,
  terrain3DEnabled: true,
  terrainExaggeration: 2.5,  // Strong relief so altitude differences are clearly visible
  elevationOpacity: 0.8,
  sunSimulationEnabled: true,
  simulationTime: 'now',

  drawingState: {
    isDrawing: false,
    drawingType: null,
    currentPoints: [],
  },

  selectZone: (zoneId) => set({ selectedZoneId: zoneId }),
  setMapLayerMode: (mode) => set({ mapLayerMode: mode }),
  setSelectedScene: (scene) => set({ selectedScene: scene }),
  setHistoricalCompareScene: (scene) => set({ historicalCompareScene: scene }),
  setTileProviderId: (id) => set({ tileProviderId: id }),
  setNdviOpacity: (opacity) => set({ ndviOpacity: opacity }),
  setSampledPixel: (pixel) => set({ sampledPixel: pixel }),
  setMapPitch: (pitch) => set({ mapPitch: pitch }),
  setMapBearing: (bearing) => set({ mapBearing: bearing }),
  setTerrain3DEnabled: (enabled) => set({ terrain3DEnabled: enabled }),
  setTerrainExaggeration: (exaggeration) => set({ terrainExaggeration: exaggeration }),
  setElevationOpacity: (opacity) => set({ elevationOpacity: opacity }),
  setSunSimulationEnabled: (enabled) => set({ sunSimulationEnabled: enabled }),
  setSimulationTime: (time) => set({ simulationTime: time }),

  startDrawing: (type) => {
    set({
      drawingState: {
        isDrawing: true,
        drawingType: type,
        currentPoints: [],
      },
    });
  },

  addDrawingPoint: (point) => {
    set((state) => ({
      drawingState: {
        ...state.drawingState,
        currentPoints: [...state.drawingState.currentPoints, point],
      },
    }));
  },

  undoLastDrawingPoint: () => {
    set((state) => ({
      drawingState: {
        ...state.drawingState,
        currentPoints: state.drawingState.currentPoints.slice(0, -1),
      },
    }));
  },

  cancelDrawing: () => {
    set({
      drawingState: {
        isDrawing: false,
        drawingType: null,
        currentPoints: [],
      },
    });
  },

  saveDrawnPolygon: (metadata) => {
    const { drawingState, farm } = get();
    const points = drawingState.currentPoints;
    if (points.length < 3) return;

    // Close polygon
    const closedCoords = [...points];
    if (
      closedCoords[0][0] !== closedCoords[closedCoords.length - 1][0] ||
      closedCoords[0][1] !== closedCoords[closedCoords.length - 1][1]
    ) {
      closedCoords.push(closedCoords[0]);
    }

    const areaHa = calculatePolygonAreaHectares(closedCoords);
    const center = calculateCentroid(closedCoords);

    if (drawingState.drawingType === 'farm_boundary') {
      set({
        farm: {
          ...farm,
          totalAreaHa: areaHa,
          boundary: {
            type: 'Polygon',
            coordinates: [closedCoords],
          },
          centerCoordinates: center,
        },
        drawingState: { isDrawing: false, drawingType: null, currentPoints: [] },
      });
    } else {
      // Add new zone
      const newZoneId = `zone-${Date.now().toString().slice(-4)}`;
      const newZone: FarmZone = {
        id: newZoneId,
        farmId: farm.id,
        name: metadata.name || `Parcelle ${farm.zones.length + 1}`,
        cropType: metadata.cropType || 'Maraîchage divers',
        plantingDate: new Date().toISOString().split('T')[0],
        areaHa,
        soilType: 'Sablo-limoneux',
        status: 'healthy',
        soilMoisturePercent: 35,
        targetMoistureMin: 30,
        targetMoistureMax: 60,
        temperatureC: 28.5,
        humidityPercent: 45,
        irrigationStatus: 'idle',
        irrigationMethod: 'Goutte-à-goutte',
        dailyWaterLiters: 2500,
        dailyEnergyKwh: 3.5,
        predictedHarvestDate: '2027-02-15',
        yieldEstimateTons: Number((areaHa * 8).toFixed(1)),
        polygon: {
          type: 'Polygon',
          coordinates: [closedCoords],
        },
        center,
        alertsCount: 0,
        sensorsAssigned: [],
        ndviStats: {
          min: 0.22,
          mean: 0.54,
          max: 0.72,
          standardDeviation: 0.08,
          acquisitionDate: '2026-11-12',
          cloudCoverPercent: 1.8,
          sensor: 'Sentinel-2 L2A MSI',
          resolutionMeters: 10,
        },
      };

      set({
        farm: {
          ...farm,
          zones: [...farm.zones, newZone],
        },
        selectedZoneId: newZoneId,
        drawingState: { isDrawing: false, drawingType: null, currentPoints: [] },
      });
    }
  },

  deleteZone: (zoneId) => {
    set((state) => ({
      farm: {
        ...state.farm,
        zones: state.farm.zones.filter((z) => z.id !== zoneId),
      },
      selectedZoneId: state.selectedZoneId === zoneId ? null : state.selectedZoneId,
    }));
  },

  startIrrigation: (zoneId) => {
    if (get().emergencyStopActive) return;

    set((state) => {
      const updatedZones = state.farm.zones.map((zone) => {
        if (zone.id === zoneId) {
          return {
            ...zone,
            status: 'irrigating' as HealthStatus,
            irrigationStatus: 'active' as const,
          };
        }
        return zone;
      });

      return {
        farm: {
          ...state.farm,
          zones: updatedZones,
        },
      };
    });
  },

  stopIrrigation: (zoneId) => {
    set((state) => {
      const updatedZones = state.farm.zones.map((zone) => {
        if (zone.id === zoneId) {
          const newStatus: HealthStatus = 
            zone.soilMoisturePercent < zone.targetMoistureMin
              ? 'critical'
              : zone.soilMoisturePercent < (zone.targetMoistureMin + 10)
              ? 'warning'
              : 'healthy';

          return {
            ...zone,
            status: newStatus,
            irrigationStatus: 'idle' as const,
          };
        }
        return zone;
      });

      return {
        farm: {
          ...state.farm,
          zones: updatedZones,
        },
      };
    });
  },

  toggleEmergencyStop: () => {
    set((state) => {
      const nextActive = !state.emergencyStopActive;
      if (nextActive) {
        const safeZones = state.farm.zones.map((zone) => {
          if (zone.irrigationStatus === 'active') {
            return {
              ...zone,
              status: 'critical' as HealthStatus,
              irrigationStatus: 'idle' as const,
            };
          }
          return zone;
        });
        return {
          emergencyStopActive: true,
          farm: { ...state.farm, zones: safeZones },
        };
      }
      return { emergencyStopActive: false };
    });
  },

  togglePowerOutage: () => {
    set((state) => {
      const nextOutage = !state.isPowerOutage;
      return {
        isPowerOutage: nextOutage,
        farm: {
          ...state.farm,
          gridAvailable: !nextOutage,
        },
      };
    });
  },

  toggleSimulation: () => set((state) => ({ isSimulating: !state.isSimulating })),

  tickSimulation: () => {
    const { isSimulating, emergencyStopActive } = get();
    if (!isSimulating || emergencyStopActive) return;

    set((state) => {
      const updatedZones = state.farm.zones.map((zone) => {
        if (zone.irrigationStatus === 'active') {
          const newMoisture = Math.min(85, zone.soilMoisturePercent + 0.8);
          const newStatus: HealthStatus = newMoisture >= zone.targetMoistureMin ? 'healthy' : 'warning';
          return {
            ...zone,
            soilMoisturePercent: Number(newMoisture.toFixed(1)),
            dailyWaterLiters: zone.dailyWaterLiters + 25,
            dailyEnergyKwh: Number((zone.dailyEnergyKwh + 0.05).toFixed(2)),
            status: 'irrigating' as HealthStatus,
          };
        } else {
          const newMoisture = Math.max(10, zone.soilMoisturePercent - 0.04);
          let newStatus = zone.status;
          if (newMoisture < zone.targetMoistureMin - 10) newStatus = 'critical';
          else if (newMoisture < zone.targetMoistureMin) newStatus = 'warning';
          else newStatus = 'healthy';

          return {
            ...zone,
            soilMoisturePercent: Number(newMoisture.toFixed(1)),
            status: newStatus,
          };
        }
      });

      return {
        farm: {
          ...state.farm,
          zones: updatedZones,
        },
      };
    });
  },

  updateZoneThresholds: (zoneId, min, max) => {
    set((state) => ({
      farm: {
        ...state.farm,
        zones: state.farm.zones.map((z) => (z.id === zoneId ? { ...z, targetMoistureMin: min, targetMoistureMax: max } : z)),
      },
    }));
  },
}));
