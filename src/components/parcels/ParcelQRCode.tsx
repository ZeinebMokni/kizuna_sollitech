'use client';

import React, { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import type { Parcel } from '@/lib/parcels/types';
import { parcelShareUrl } from '@/lib/parcels/geometry';
import { cn } from '@/lib/utils';

/**
 * QR code that opens the parcel fiche. The link carries the parcel data, so
 * the fiche can open on a phone that has never seen this parcel.
 */
export function ParcelQRCode({ parcel, size = 168, className }: { parcel: Parcel; size?: number; className?: string }) {
  const [svg, setSvg] = useState<string>('');

  useEffect(() => {
    const url = parcelShareUrl(parcel, window.location.origin);
    QRCode.toString(url, { type: 'svg', margin: 1, errorCorrectionLevel: 'M', color: { dark: '#103C48', light: '#FFFFFF' } })
      .then(setSvg)
      .catch(() => setSvg(''));
  }, [parcel]);

  return (
    <div
      className={cn('rounded-glass-sm bg-white p-2 ring-1 ring-line [&>svg]:h-full [&>svg]:w-full', className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`QR code de la parcelle ${parcel.id}`}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
