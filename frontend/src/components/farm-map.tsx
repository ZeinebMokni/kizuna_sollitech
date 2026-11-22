"use client";

import dynamic from "next/dynamic";

// Leaflet touches `window`: load it only in the browser.
export const FarmMap = dynamic(() => import("./farm-map-inner"), {
  ssr: false,
  loading: () => <div className="h-80 w-full animate-pulse rounded-lg bg-stone-200" />,
});
