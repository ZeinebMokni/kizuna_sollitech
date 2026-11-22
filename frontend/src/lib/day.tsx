"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

export const DEFAULT_DAY = "2025-06-15";
export const DAY_MIN = "2025-03-08";
export const DAY_MAX = "2025-09-06";

const DayContext = createContext<{ day: string; setDay: (d: string) => void }>({
  day: DEFAULT_DAY,
  setDay: () => {},
});

export function DayProvider({ children }: { children: ReactNode }) {
  const [day, setDay] = useState(DEFAULT_DAY);
  return <DayContext.Provider value={{ day, setDay }}>{children}</DayContext.Provider>;
}

export const useDay = () => useContext(DayContext);
