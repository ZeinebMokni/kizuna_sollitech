/**
 * NDVI (Normalized Difference Vegetation Index) calculations & color ramps
 * for Copernicus Sentinel-2 MSI (B08 NIR @ 842nm, B04 RED @ 665nm).
 */

export interface NDVIColorStop {
  min: number;
  max: number;
  hex: string;
  rgba: string;
  labelFr: string;
  labelAr: string;
  description: string;
}

export const NDVI_COLOR_SCALE: NDVIColorStop[] = [
  {
    min: -1.0,
    max: 0.15,
    hex: '#D32F2F',
    rgba: 'rgba(211, 47, 47, 0.75)',
    labelFr: 'Très Faible (< 0.15)',
    labelAr: 'منخفض جداً',
    description: 'Sol nu, roche, infrastructure ou eau. Ne signifie pas nécessairement un stress.',
  },
  {
    min: 0.15,
    max: 0.30,
    hex: '#FB8C00',
    rgba: 'rgba(251, 140, 0, 0.75)',
    labelFr: 'Faible (0.15 - 0.30)',
    labelAr: 'منخفض',
    description: 'Végétation clairsemée, début de levée ou culture sénescente.',
  },
  {
    min: 0.30,
    max: 0.45,
    hex: '#FDD835',
    rgba: 'rgba(253, 216, 53, 0.75)',
    labelFr: 'Modéré (0.30 - 0.45)',
    labelAr: 'متوسط',
    description: 'Végétation en développement végétatif intermédiaire.',
  },
  {
    min: 0.45,
    max: 0.65,
    hex: '#7CB342',
    rgba: 'rgba(124, 179, 66, 0.75)',
    labelFr: 'Élevé (0.45 - 0.65)',
    labelAr: 'مرتفع',
    description: 'Biomasse saine, bonne couverture foliaire et activité photosynthétique.',
  },
  {
    min: 0.65,
    max: 1.0,
    hex: '#2E7D32',
    rgba: 'rgba(46, 125, 50, 0.85)',
    labelFr: 'Très Élevé (> 0.65)',
    labelAr: 'مرتفع جداً',
    description: 'Canopée très dense, feuillage vigoureux à maturité maximale.',
  },
];

/**
 * Calculates NDVI from Sentinel-2 Band 8 (NIR) and Band 4 (Red) reflectance values.
 */
export function calculateNDVI(nirB08: number, redB04: number): number {
  if (nirB08 + redB04 === 0) return 0;
  const ndvi = (nirB08 - redB04) / (nirB08 + redB04);
  return Number(Math.max(-1.0, Math.min(1.0, ndvi)).toFixed(3));
}

/**
 * Returns the hex color corresponding to an NDVI value.
 */
export function getNDVIColor(ndvi: number): string {
  if (ndvi < 0.15) return '#D32F2F';
  if (ndvi < 0.30) return '#FB8C00';
  if (ndvi < 0.45) return '#FDD835';
  if (ndvi < 0.65) return '#7CB342';
  return '#2E7D32';
}

/**
 * Returns the RGBA color with specified opacity.
 */
export function getNDVIRgba(ndvi: number, opacity: number = 0.75): string {
  if (ndvi < 0.15) return `rgba(211, 47, 47, ${opacity})`;
  if (ndvi < 0.30) return `rgba(251, 140, 0, ${opacity})`;
  if (ndvi < 0.45) return `rgba(253, 216, 53, ${opacity})`;
  if (ndvi < 0.65) return `rgba(124, 179, 66, ${opacity})`;
  return `rgba(46, 125, 50, ${opacity})`;
}

/**
 * Returns comprehensive agronomic interpretation for an NDVI reading.
 */
export function getNDVIInterpretation(ndvi: number): {
  category: string;
  explanation: string;
  color: string;
  isBareSoilLikely: boolean;
} {
  if (ndvi < 0.15) {
    return {
      category: 'Sol Nu / Non-Végétalisé',
      explanation: 'Indice très bas caractéristique du sol sablo-limoneux sec ou inter-rangs non enherbés.',
      color: '#D32F2F',
      isBareSoilLikely: true,
    };
  }
  if (ndvi < 0.30) {
    return {
      category: 'Végétation Faible',
      explanation: 'Végétation clairsemée, stade post-semis ou stress hydrique prononcé.',
      color: '#FB8C00',
      isBareSoilLikely: false,
    };
  }
  if (ndvi < 0.45) {
    return {
      category: 'Développement Modéré',
      explanation: 'Couvert végétal moyen en cours de croissance végétative.',
      color: '#FDD835',
      isBareSoilLikely: false,
    };
  }
  if (ndvi < 0.65) {
    return {
      category: 'Biomasse Vigoureuse',
      explanation: 'Excellente réflectance proche-infrarouge, feuillage bien irrigué et actif.',
      color: '#7CB342',
      isBareSoilLikely: false,
    };
  }
  return {
    category: 'Vigueur Maximale',
    explanation: 'Forte densité de chlorophylle et canopée totalement fermée.',
    color: '#2E7D32',
    isBareSoilLikely: false,
  };
}
