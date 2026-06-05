"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getLettres, updateLettre, getLettrePdfUrl, type Lettre } from "@/lib/api";
import toast from "react-hot-toast";

export default function LettersPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Lettre | null>(null);
  const [editContent, setEditContent] = useState("");

  const { data: lettres = [], isLoading } = useQuery({
    queryKey: ["lettres", search],
    queryFn: () => getLettres(search || undefined),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, contenu }: { id: number; contenu: string }) => updateLettre(id, contenu),
    onSuccess: () => {
      toast.success("Lettre sauvegardée");
      qc.invalidateQueries({ queryKey: ["lettres"] });
      setEditing(null);
    },
    onError: () => toast.error("Erreur lors de la sauvegarde"),
  });

  const openEdit = (lettre: Lettre) => {
    setEditing(lettre);
    setEditContent(lettre.contenu);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Lettres de motivation</h1>
        <input
          aria-label="Filtrer par entreprise"
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-64"
          placeholder="Filtrer par entreprise..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Chargement...</div>
      ) : lettres.length === 0 ? (
        <div className="text-center py-12 text-gray-400">Aucune lettre. Générez-en depuis les offres.</div>
      ) : (
        <div className="space-y-4">
          {lettres.map((lettre) => (
            <div key={lettre.id} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-gray-900">{lettre.entreprise}</h3>
                  <p className="text-xs text-gray-400 mt-0.5">Version {lettre.version} · {new Date(lettre.modifie_le).toLocaleDateString("fr-FR")}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => openEdit(lettre)}
                    className="text-sm text-primary-600 hover:underline"
                  >
                    Modifier
                  </button>
                  <a
                    href={getLettrePdfUrl(lettre.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-gray-500 hover:underline"
                  >
                    PDF ↓
                  </a>
                </div>
              </div>
              <p className="text-sm text-gray-600 whitespace-pre-wrap line-clamp-4">{lettre.contenu}</p>
            </div>
          ))}
        </div>
      )}

      {/* Edit Modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-2xl shadow-xl flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-gray-100">
              <h2 className="font-bold text-lg">Modifier la lettre — {editing.entreprise}</h2>
            </div>
            <textarea
              aria-label={`Contenu de la lettre — ${editing.entreprise}`}
              className="flex-1 p-5 text-sm font-mono resize-none outline-none overflow-y-auto"
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              rows={20}
            />
            <div className="p-4 border-t border-gray-100 flex justify-end gap-3">
              <button onClick={() => setEditing(null)} className="px-4 py-2 text-gray-600 hover:text-gray-800">
                Annuler
              </button>
              <button
                onClick={() => updateMutation.mutate({ id: editing.id, contenu: editContent })}
                disabled={updateMutation.isPending}
                className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {updateMutation.isPending ? "Sauvegarde..." : "Sauvegarder"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
