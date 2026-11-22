'use client';

import React, { useState } from 'react';
import {
  PenTool,
  Square,
  Check,
  X,
  Undo2,
  Trash2,
  Layers,
  MapPin,
  Sparkles,
  Save
} from 'lucide-react';
import { useFarmStore } from '@/stores/useFarmStore';
import { calculatePolygonAreaHectares } from '@/lib/geo/geodesic';
import { cn } from '@/lib/utils';

export function FarmDrawingTools() {
  const {
    drawingState,
    startDrawing,
    cancelDrawing,
    undoLastDrawingPoint,
    saveDrawnPolygon,
    farm
  } = useFarmStore();

  const [zoneName, setZoneName] = useState('');
  const [cropType, setCropType] = useState('Maraîchage primeur');
  const [saveModalOpen, setSaveModalOpen] = useState(false);

  const points = drawingState.currentPoints;
  const currentAreaHa = points.length >= 3 ? calculatePolygonAreaHectares(points) : 0;

  const handleFinish = () => {
    if (points.length < 3) return;
    setSaveModalOpen(true);
  };

  const handleConfirmSave = (e: React.FormEvent) => {
    e.preventDefault();
    saveDrawnPolygon({
      name: zoneName || `Zone ${farm.zones.length + 1}`,
      cropType: cropType || 'Culture générale',
    });
    setSaveModalOpen(false);
    setZoneName('');
  };

  return (
    <>
      <div className="glass-panel p-1.5 rounded-2xl border flex items-center gap-1 text-xs">
        {!drawingState.isDrawing ? (
          <>
            <button
              onClick={() => startDrawing('zone_polygon')}
              className="px-3 py-1.5 rounded-xl bg-gradient-to-r from-accent to-accent-deep hover:from-accent-hover text-on-accent font-bold flex items-center gap-1.5 border border-brand-500/30 transition-all qa-shine"
            >
              <PenTool className="h-3.5 w-3.5" />
              <span>Tracer une Parcelle</span>
            </button>

            <button
              onClick={() => startDrawing('farm_boundary')}
              className="px-3 py-1.5 rounded-xl bg-raised hover:bg-highlight text-brand-300 font-semibold border border-brand-500/20 flex items-center gap-1.5 transition-colors"
            >
              <Square className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Redéfinir Périmètre Exploitation</span>
            </button>
          </>
        ) : (
          <div className="flex items-center gap-2 px-1">
            <span className="text-[11px] text-brand-300 font-mono font-bold flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-brand-400 animate-ping" />
              {points.length} points
              {currentAreaHa > 0 && ` (${currentAreaHa} Ha)`}
            </span>

            {points.length > 0 && (
              <button
                onClick={undoLastDrawingPoint}
                className="p-1.5 rounded-lg bg-earth-800 hover:bg-earth-700 text-earth-300"
                title="Annuler dernier point"
              >
                <Undo2 className="h-3.5 w-3.5" />
              </button>
            )}

            {points.length >= 3 && (
              <button
                onClick={handleFinish}
                className="px-3 py-1 rounded-lg bg-accent hover:bg-accent-hover text-on-accent font-bold flex items-center gap-1 shadow-md"
              >
                <Check className="h-3.5 w-3.5" />
                <span>Terminer Polygone</span>
              </button>
            )}

            <button
              onClick={cancelDrawing}
              className="p-1.5 rounded-lg bg-alert-950/60 hover:bg-alert-900 border border-alert-500/30 text-alert-300"
              title="Annuler tracé"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Save Zone Modal */}
      {saveModalOpen && (
        <div className="fixed inset-0 z-50 bg-earth-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel rounded-glass max-w-md w-full p-6 text-xs space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <h3 className="text-base font-bold text-ink flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-brand-400" />
                Enregistrer la Nouvelle Parcelle
              </h3>
              <button onClick={() => setSaveModalOpen(false)} className="text-earth-400 hover:text-ink">
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleConfirmSave} className="space-y-3">
              <div>
                <label className="text-earth-300 font-semibold block mb-1">Nom de la Parcelle</label>
                <input
                  type="text"
                  placeholder="Ex: Zone F - Serres Poivrons"
                  value={zoneName}
                  onChange={(e) => setZoneName(e.target.value)}
                  className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink font-medium focus:outline-none focus:border-brand-500"
                  required
                />
              </div>

              <div>
                <label className="text-earth-300 font-semibold block mb-1">Type de Culture</label>
                <select
                  value={cropType}
                  onChange={(e) => setCropType(e.target.value)}
                  className="w-full bg-sunken border border-line rounded-xl px-3 py-2 text-ink font-medium focus:outline-none focus:border-brand-500"
                >
                  <option>Piments Baklouti</option>
                  <option>Tomates de saison</option>
                  <option>Oliviers Chemlali</option>
                  <option>Grenadiers</option>
                  <option>Luzerne / Fourrage</option>
                  <option>Maraîchage divers</option>
                </select>
              </div>

              <div className="bg-sunken p-3 rounded-xl border border-line">
                <span className="text-earth-400">Superficie calculée (WGS84 Géodésique) :</span>
                <p className="text-base font-mono font-black text-brand-400 mt-0.5">{currentAreaHa} Hectares</p>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSaveModalOpen(false)}
                  className="flex-1 py-2 rounded-xl bg-earth-800 text-earth-300 font-semibold"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2 rounded-xl bg-accent hover:bg-accent text-on-accent font-bold shadow-lg"
                >
                  Sauvegarder dans le SIG
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
