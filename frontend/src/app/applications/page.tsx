"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCandidatures, updateCandidature, sendCandidatureEmail, exportCandidatures, type Candidature } from "@/lib/api";
import toast from "react-hot-toast";

const STATUTS = ["en_attente", "envoyee", "refusee", "entretien", "acceptee"];
const STATUT_COLORS: Record<string, string> = {
  en_attente: "bg-yellow-100 text-yellow-800",
  envoyee: "bg-blue-100 text-blue-800",
  refusee: "bg-red-100 text-red-800",
  entretien: "bg-purple-100 text-purple-800",
  acceptee: "bg-green-100 text-green-800",
};

export default function ApplicationsPage() {
  const qc = useQueryClient();
  const [filterStatut, setFilterStatut] = useState("");
  const [emailModal, setEmailModal] = useState<{ id: number } | null>(null);
  const [emailAddr, setEmailAddr] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const { data: candidatures = [], isLoading } = useQuery({
    queryKey: ["candidatures", filterStatut],
    queryFn: () => getCandidatures(filterStatut || undefined),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, statut }: { id: number; statut: string }) => updateCandidature(id, statut),
    onSuccess: () => {
      toast.success("Statut mis à jour");
      qc.invalidateQueries({ queryKey: ["candidatures"] });
    },
  });

  const sendMutation = useMutation({
    mutationFn: ({ id, email }: { id: number; email: string }) => sendCandidatureEmail(id, email),
    onSuccess: () => {
      toast.success("Email envoyé !");
      qc.invalidateQueries({ queryKey: ["candidatures"] });
      setEmailModal(null);
    },
    onError: () => toast.error("Échec de l'envoi. Vérifiez la config email."),
  });

  const exportMutation = useMutation({
    mutationFn: () => exportCandidatures(Array.from(selected)),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "candidatures.zip";
      a.click();
      URL.revokeObjectURL(url);
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
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-900">Candidatures</h1>
        <div className="flex gap-2">
          <select
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
            value={filterStatut}
            onChange={(e) => setFilterStatut(e.target.value)}
          >
            <option value="">Tous statuts</option>
            {STATUTS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          {selected.size > 0 && (
            <button
              onClick={() => exportMutation.mutate()}
              disabled={exportMutation.isPending}
              className="bg-gray-700 text-white px-4 py-2 rounded-lg hover:bg-gray-800 text-sm disabled:opacity-50"
            >
              📦 Exporter ZIP ({selected.size})
            </button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Chargement...</div>
      ) : candidatures.length === 0 ? (
        <div className="text-center py-12 text-gray-400">Aucune candidature en cours.</div>
      ) : (
        <div className="space-y-3">
          {candidatures.map((c) => (
            <CandidatureCard
              key={c.id}
              candidature={c}
              selected={selected.has(c.id)}
              onToggle={() => toggleSelect(c.id)}
              onStatusChange={(statut) => updateMutation.mutate({ id: c.id, statut })}
              onSendEmail={() => setEmailModal({ id: c.id })}
            />
          ))}
        </div>
      )}

      {emailModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
            <h2 className="font-bold text-lg mb-4">Envoyer la candidature par email</h2>
            <input
              className="w-full border border-gray-200 rounded-lg px-3 py-2 mb-4"
              placeholder="Email destinataire..."
              value={emailAddr}
              onChange={(e) => setEmailAddr(e.target.value)}
              type="email"
            />
            <div className="flex justify-end gap-3">
              <button onClick={() => setEmailModal(null)} className="px-4 py-2 text-gray-600">Annuler</button>
              <button
                onClick={() => sendMutation.mutate({ id: emailModal.id, email: emailAddr })}
                disabled={sendMutation.isPending || !emailAddr}
                className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {sendMutation.isPending ? "Envoi..." : "Envoyer"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CandidatureCard({
  candidature,
  selected,
  onToggle,
  onStatusChange,
  onSendEmail,
}: {
  candidature: Candidature;
  selected: boolean;
  onToggle: () => void;
  onStatusChange: (s: string) => void;
  onSendEmail: () => void;
}) {
  return (
    <div className={`bg-white rounded-xl border p-4 flex gap-3 items-center transition-all ${selected ? "border-primary-500" : "border-gray-100"} shadow-sm`}>
      <input type="checkbox" checked={selected} onChange={onToggle} className="w-4 h-4 accent-primary-600" />
      <div className="flex-1">
        <p className="text-sm text-gray-600">Offre #{candidature.offre_id}</p>
        <p className="text-xs text-gray-400">{new Date(candidature.cree_le).toLocaleDateString("fr-FR")}</p>
      </div>
      <select
        className={`text-xs font-medium px-3 py-1 rounded-full border-0 cursor-pointer ${STATUT_COLORS[candidature.statut] ?? "bg-gray-100 text-gray-700"}`}
        value={candidature.statut}
        onChange={(e) => onStatusChange(e.target.value)}
      >
        {STATUTS.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <button onClick={onSendEmail} className="text-sm text-primary-600 hover:underline">
        📧 Envoyer
      </button>
    </div>
  );
}
