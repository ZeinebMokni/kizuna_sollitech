import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { Parcel, ParcelDraft, LngLat } from '@/lib/parcels/types';
import { generateParcelId } from '@/lib/parcels/id';
import { calculatePolygonAreaHectares, calculateCentroid } from '@/lib/geo/geodesic';
import { closeRing } from '@/lib/parcels/geometry';
import { DEMO_FARM } from '@/lib/mockData';

/** What a click / drag on the map does while registering land. */
export type ParcelMode = 'idle' | 'rectangle' | 'auto';

export interface NewParcelInput {
  name: string;
  ownerName: string;
  cropType: string;
  irrigationMethod: string;
}

interface ParcelState {
  // Persisted (local storage, this browser only)
  parcels: Parcel[];
  currentOwner: string;

  // Session state
  mode: ParcelMode;
  draft: ParcelDraft | null;
  detecting: boolean;
  detectError: string | null;
  selectedParcelId: string | null;
  lastCreatedId: string | null;

  setMode: (mode: ParcelMode) => void;
  setDraft: (draft: ParcelDraft | null) => void;
  setDetecting: (detecting: boolean) => void;
  setDetectError: (message: string | null) => void;
  selectParcel: (id: string | null) => void;
  setCurrentOwner: (name: string) => void;
  createParcelFromDraft: (input: NewParcelInput) => Parcel | null;
  removeParcel: (id: string) => void;
  clearLastCreated: () => void;
}

export const useParcelStore = create<ParcelState>()(
  persist(
    (set, get) => ({
      parcels: [],
      currentOwner: DEMO_FARM.ownerName,

      mode: 'idle',
      draft: null,
      detecting: false,
      detectError: null,
      selectedParcelId: null,
      lastCreatedId: null,

      setMode: (mode) => set({ mode, draft: null, detectError: null }),
      setDraft: (draft) => set({ draft }),
      setDetecting: (detecting) => set({ detecting }),
      setDetectError: (detectError) => set({ detectError }),
      selectParcel: (selectedParcelId) => set({ selectedParcelId }),
      setCurrentOwner: (name) => set({ currentOwner: name.trim() || DEMO_FARM.ownerName }),

      createParcelFromDraft: (input) => {
        const { draft, parcels } = get();
        if (!draft || draft.polygon.length < 3) return null;
        const polygon = draft.polygon.map(([x, y]) => [Number(x.toFixed(6)), Number(y.toFixed(6))] as LngLat);
        const id = generateParcelId(DEMO_FARM.governorate, DEMO_FARM.delegation, new Set(parcels.map((p) => p.id)));
        const parcel: Parcel = {
          id,
          name: input.name.trim() || `Parcelle ${parcels.length + 1}`,
          ownerName: input.ownerName.trim() || get().currentOwner,
          cropType: input.cropType,
          irrigationMethod: input.irrigationMethod,
          polygon,
          areaHa: calculatePolygonAreaHectares(closeRing(polygon)),
          center: calculateCentroid(polygon),
          governorate: DEMO_FARM.governorate,
          delegation: DEMO_FARM.delegation,
          createdAt: new Date().toISOString(),
          source: draft.source,
        };
        set({
          parcels: [...parcels, parcel],
          draft: null,
          mode: 'idle',
          selectedParcelId: id,
          lastCreatedId: id,
          currentOwner: parcel.ownerName,
        });
        return parcel;
      },

      removeParcel: (id) =>
        set((s) => ({
          parcels: s.parcels.filter((p) => p.id !== id),
          selectedParcelId: s.selectedParcelId === id ? null : s.selectedParcelId,
        })),

      clearLastCreated: () => set({ lastCreatedId: null }),
    }),
    {
      name: 'qatra-parcels',
      version: 1,
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ parcels: s.parcels, currentOwner: s.currentOwner }),
    }
  )
);
