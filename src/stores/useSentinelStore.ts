import { create } from 'zustand';
import { getScenes, getSentinelStatus, SentinelError, toPolygon, type SentinelScene, type NdviStats } from '@/lib/sentinel/client';
import { DEMO_FARM } from '@/lib/mockData';

/**
 * live          backend reachable and Copernicus configured → real Sentinel-2 data
 * unconfigured  backend reachable, credentials missing
 * offline       backend not running / unreachable
 * checking      first check in progress
 */
export type SentinelLink = 'checking' | 'live' | 'unconfigured' | 'offline';

interface SentinelState {
  link: SentinelLink;
  message: string | null;
  scenes: SentinelScene[];
  selectedDate: string | null;
  loadingImage: boolean;
  imageError: string | null;
  dateStats: NdviStats | null;

  connect: () => Promise<void>;
  setSelectedDate: (date: string) => void;
  setLoadingImage: (v: boolean) => void;
  setImageError: (msg: string | null) => void;
  setDateStats: (s: NdviStats | null) => void;
}

/** Farm outline used for the real NDVI image and the scene list. */
export const farmGeometry = () => toPolygon(DEMO_FARM.boundary.coordinates[0] as number[][]);

let connecting: Promise<void> | null = null;

export const useSentinelStore = create<SentinelState>((set, get) => ({
  link: 'checking',
  message: null,
  scenes: [],
  selectedDate: null,
  loadingImage: false,
  imageError: null,
  dateStats: null,

  connect: () => {
    if (connecting) return connecting;
    connecting = (async () => {
      try {
        const status = await getSentinelStatus();
        if (!status.configured) {
          set({ link: 'unconfigured', message: 'Copernicus non configuré : ajoutez vos clés dans backend/.env' });
          return;
        }
        const scenes = await getScenes(farmGeometry());
        set({
          link: 'live',
          message: null,
          scenes,
          selectedDate: get().selectedDate ?? scenes[0]?.date ?? null,
        });
      } catch (err) {
        const e = err as SentinelError;
        set({
          link: e.kind === 'offline' ? 'offline' : e.kind === 'unconfigured' ? 'unconfigured' : 'offline',
          message: e.message,
        });
      } finally {
        connecting = null;
      }
    })();
    return connecting;
  },

  setSelectedDate: (date) => set({ selectedDate: date, dateStats: null, imageError: null }),
  setLoadingImage: (loadingImage) => set({ loadingImage }),
  setImageError: (imageError) => set({ imageError }),
  setDateStats: (dateStats) => set({ dateStats }),
}));
