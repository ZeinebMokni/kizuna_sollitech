export type LngLat = [number, number];

/** How the parcel outline was captured on the map. */
export type ParcelSource = 'rectangle' | 'auto';

/** A piece of land registered by one owner, identified by a unique ID. */
export interface Parcel {
  /** Unique ID, e.g. TN-BZ-MTR-7K4Q2X */
  id: string;
  name: string;
  ownerName: string;
  cropType: string;
  irrigationMethod: string;
  /** Open ring of [lng, lat] (first point is not repeated at the end) */
  polygon: LngLat[];
  areaHa: number;
  center: LngLat;
  governorate: string;
  delegation: string;
  /** ISO date */
  createdAt: string;
  source: ParcelSource;
  irrigationActive?: boolean;
}

/** A parcel outline being created, before it is saved. */
export interface ParcelDraft {
  polygon: LngLat[];
  source: ParcelSource;
  /** True once the outline is final (mouse released / detection finished). */
  ready?: boolean;
}
