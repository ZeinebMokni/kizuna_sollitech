'use client';

import { useEffect, useState } from 'react';

/**
 * False during server render and the first client render, true after mount.
 * Parcels live in local storage, so lists render only once hydrated to avoid
 * a server/client mismatch.
 */
export function useHydrated() {
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);
  return hydrated;
}
