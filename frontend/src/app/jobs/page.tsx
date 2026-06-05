"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getOffres, launchScan, getScanStatus, getSources, type Offre, type ScanParams } from "@/lib/api";
import toast from "react-hot-toast";

const CONTRACT_TYPES = ["", "CDI", "CDD", "alternance"];
const SOURCES_LABELS: Record<string, string> = {
  france_travail: "France Travail",
  indeed: "Indeed",
  linkedin: "LinkedIn",
  welcome_to_the_jungle: "WTTJ",
  apec: "APEC",
  hellowork: "HelloWork",
  cadremploi: "Cadremploi",
  jobteaser: "JobTeaser",
  monster: "Monster",
  letudiant: "L'Étudiant",
  regionsjob: "RégionsJob",
};

export default function JobsPage() {
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ source: "", type_contrat: "", ville: "" });
  const [scanParams, setScanParams] = useState<ScanParams>({ secteur: "informatique", mots_cles: "" });
  const [scanTaskId, setScanTaskId] = useState<string | null>(null);
  const [showScanModal, setShowScanModal] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const { data: offres = [], isLoading } = useQuery({
    queryKey: ["offres", filters],
    queryFn: () => getOffres(Object.fromEntries(Object.entries(filters).filter(([, v]) => v))),
  });

  const { data: sourcesData } = useQuery({
    queryKey: ["sources"],
    queryFn: getSources,
  });

  const { data: scanStatus } = useQuery({
    queryKey: ["scan-status", scanTaskId],
    queryFn: () => getScanStatus(scanTaskId!),
    enabled: !!scanTaskId,
    refetchInterval: (q) => (q.state.data?.status === "SUCCESS" || q.state.data?.status === "FAILURE" ? false : 2000),
    select: (data) => {
      if (data.status === "SUCCESS") {
        toast.success(`Scan terminé : ${(data.result as { imported?: number })?.imported ?? 0} offres importées`);
        qc.invalidateQueries({ queryKey: ["offres"] });
        setScanTaskId(null);
      }
      return data;
    },
  });

  const scanMutation = useMutation({
    mutationFn: launchScan,
    onSuccess: (data) => {
      setScanTaskId(data.task_id);
      setShowScanModal(false);
      toast.success("Scan lancé en arrière-plan...");
    },
  });

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Offres d'emploi</h1>
        <button
          onClick={() => setShowScanModal(true)}
          className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors font-medium"
        >
          🔍 Lancer un scan
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex gap-3 flex-wrap">
        <select
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={filters.source}
          onChange={(e) => setFilters((f) => ({ ...f, source: e.target.value }))}
        >
          <option value="">Toutes les sources</option>
          {sourcesData?.sources.map((s) => (
            <option key={s} value={s}>{SOURCES_LABELS[s] ?? s}</option>
          ))}
        </select>
        <select
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={filters.type_contrat}
          onChange={(e) => setFilters((f) => ({ ...f, type_contrat: e.target.value }))}
        >
          {CONTRACT_TYPES.map((t) => (
            <option key={t} value={t}>{t || "Tous contrats"}</option>
          ))}
        </select>
        <input
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-[150px]"
          placeholder="Ville..."
          value={filters.ville}
          onChange={(e) => setFilters((f) => ({ ...f, ville: e.target.value }))}
        />
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Chargement...</div>
      ) : offres.length === 0 ? (
        <div className="text-center py-12 text-gray-400">Aucune offre. Lancez un scan pour commencer.</div>
      ) : (
        <div className="space-y-3">
          {offres.map((offre) => (
            <OffreCard
              key={offre.id}
              offre={offre}
              selected={selected.has(offre.id)}
              onToggle={() => toggleSelect(offre.id)}
            />
          ))}
        </div>
      )}

      {/* Scan Modal */}
      {showScanModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl">
            <h2 className="text-lg font-bold mb-4">Paramètres du scan</h2>
            <div className="space-y-3">
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2"
                placeholder="Secteur (ex: informatique)"
                value={scanParams.secteur}
                onChange={(e) => setScanParams((p) => ({ ...p, secteur: e.target.value }))}
              />
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2"
                placeholder="Mots-clés (ex: React, Python)"
                value={scanParams.mots_cles}
                onChange={(e) => setScanParams((p) => ({ ...p, mots_cles: e.target.value }))}
              />
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2"
                placeholder="Ville (optionnel)"
                value={scanParams.ville ?? ""}
                onChange={(e) => setScanParams((p) => ({ ...p, ville: e.target.value }))}
              />
              <select
                className="w-full border border-gray-200 rounded-lg px-3 py-2"
                value={scanParams.type_contrat ?? ""}
                onChange={(e) => setScanParams((p) => ({ ...p, type_contrat: e.target.value || undefined }))}
              >
                {CONTRACT_TYPES.map((t) => (
                  <option key={t} value={t}>{t || "Tous contrats"}</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setShowScanModal(false)} className="px-4 py-2 text-gray-600 hover:text-gray-800">
                Annuler
              </button>
              <button
                onClick={() => scanMutation.mutate(scanParams)}
                disabled={scanMutation.isPending}
                className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {scanMutation.isPending ? "Lancement..." : "Lancer le scan"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function OffreCard({ offre, selected, onToggle }: { offre: Offre; selected: boolean; onToggle: () => void }) {
  return (
    <div className={`bg-white rounded-xl border p-4 flex gap-3 items-start transition-all ${selected ? "border-primary-500 shadow-md" : "border-gray-100 shadow-sm"}`}>
      <input type="checkbox" checked={selected} onChange={onToggle} className="mt-1 w-4 h-4 accent-primary-600" />
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-gray-900 truncate">{offre.titre}</h3>
          <span className="shrink-0 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{offre.source}</span>
        </div>
        <p className="text-sm text-gray-600 mt-0.5">{offre.entreprise} {offre.ville ? `— ${offre.ville}` : ""}</p>
        {offre.type_contrat && (
          <span className="inline-block mt-1 text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">{offre.type_contrat}</span>
        )}
      </div>
      <a href={offre.lien_source} target="_blank" rel="noopener noreferrer" className="text-primary-600 text-sm hover:underline shrink-0">
        Voir l'offre →
      </a>
    </div>
  );
}
