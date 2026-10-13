"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCandidatures, updateCandidature, exportCandidatures, getLettre, postuler, marquerEnvoyee, updateOffreEmail, downloadFile, copierTexte, errorMessage, type PostulerResult, type Candidature } from "@/lib/api";
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
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const { data: candidatures = [], isLoading, isError, error } = useQuery({
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

  const [kit, setKit] = useState<{ c: Candidature; r: Extract<PostulerResult, { mode: "site" }> } | null>(null);
  const [emailRecruteur, setEmailRecruteur] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["candidatures"] });

  const postulerMutation = useMutation({
    mutationFn: (c: Candidature) =>
      postuler(c.id)
        .catch((e) => {
          // SMTP non configuré : on bascule sur le kit « dépôt sur le site » (aucun envoi).
          if ((e as { response?: { status?: number } })?.response?.status !== 503) throw e;
          toast.error("SMTP non configuré : candidature à déposer sur le site");
          return postuler(c.id, "site");
        })
        .then((r) => ({ c, r })),
    onSuccess: ({ c, r }) => {
      if (r.mode === "email") {
        toast.success(`Candidature envoyée à ${r.destinataire}`);
        refresh();
      } else {
        setEmailRecruteur("");
        setKit({ c, r });
      }
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const onPostuler = async (c: Candidature) => {
    if (c.offre_email_contact) {
      if (!c.lettre_id) return;
      // Validation humaine : montrer destinataire, offre et début de la lettre avant tout envoi.
      let contenu: string;
      try {
        contenu = (await getLettre(c.lettre_id)).contenu;
      } catch (e) {
        toast.error(`Lettre introuvable, envoi annulé : ${errorMessage(e)}`);
        return;
      }
      const extrait = contenu.length > 400 ? `${contenu.slice(0, 400)}…` : contenu;
      const message =
        `Envoyer la lettre et le CV à ${c.offre_email_contact} ?

` +
        `Offre : ${c.offre_titre ?? `#${c.offre_id}`}

` +
        `Début de la lettre :
${extrait}`;
      if (!window.confirm(message)) return;
    }
    postulerMutation.mutate(c);
  };

  const marquerMutation = useMutation({
    mutationFn: (id: number) => marquerEnvoyee(id),
    onSuccess: () => { toast.success("Candidature marquée envoyée"); setKit(null); refresh(); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const emailMutation = useMutation({
    mutationFn: ({ offreId, email }: { offreId: number; email: string }) => updateOffreEmail(offreId, email),
    onSuccess: () => { toast.success("E-mail enregistré : « Postuler » enverra désormais par e-mail"); setKit(null); refresh(); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const telecharger = (path: string, nom: string) =>
    downloadFile(path, nom).catch((e) => toast.error(errorMessage(e)));

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
            aria-label="Filtrer par statut"
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

      {isError ? (
        <div className="text-center py-12 text-red-600">Impossible de charger les candidatures : {errorMessage(error)}</div>
      ) : isLoading ? (
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
              onPostuler={() => onPostuler(c)}
              postulerPending={postulerMutation.isPending}
            />
          ))}
        </div>
      )}

      {kit && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl space-y-3">
            <h2 className="font-bold text-lg">Postuler sur le site — {kit.c.offre_titre}</h2>
            <p className="text-sm text-gray-600">Ouvrez l&apos;offre, déposez la lettre et le CV, puis confirmez ici.</p>
            <div className="flex flex-wrap gap-2">
              <a href={kit.r.lien} target="_blank" rel="noopener noreferrer" className="bg-primary-600 text-white px-3 py-2 rounded-lg text-sm">Ouvrir l&apos;offre</a>
              <button onClick={() => copierTexte(kit.r.lettre_texte).then(() => toast.success("Lettre copiée"), () => toast.error("Copie impossible : sélectionnez le texte manuellement"))} className="border px-3 py-2 rounded-lg text-sm">Copier la lettre</button>
              <button onClick={() => telecharger(`/lettres/${kit.r.lettre_id}/pdf`, `lettre_${kit.c.offre_entreprise ?? kit.c.id}.pdf`)} className="border px-3 py-2 rounded-lg text-sm">Télécharger la lettre (PDF)</button>
              <button onClick={() => telecharger("/cv/actif/fichier", "CV.pdf")} className="border px-3 py-2 rounded-lg text-sm">Télécharger le CV</button>
            </div>
            <div className="flex gap-2 pt-2 border-t">
              <input aria-label="E-mail du recruteur" type="email" placeholder="E-mail du recruteur (si connu)"
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={emailRecruteur} onChange={(e) => setEmailRecruteur(e.target.value)} />
              <button disabled={!emailRecruteur || emailMutation.isPending}
                onClick={() => emailMutation.mutate({ offreId: kit.c.offre_id, email: emailRecruteur })}
                className="border px-3 py-2 rounded-lg text-sm disabled:opacity-50">Enregistrer</button>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={() => setKit(null)} className="px-4 py-2 text-gray-600">Fermer</button>
              <button onClick={() => marquerMutation.mutate(kit.c.id)} disabled={marquerMutation.isPending}
                className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50">J&apos;ai postulé</button>
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
  onPostuler,
  postulerPending,
}: {
  candidature: Candidature;
  selected: boolean;
  onToggle: () => void;
  onStatusChange: (s: string) => void;
  onPostuler: () => void;
  postulerPending: boolean;
}) {
  return (
    <div className={`bg-white rounded-xl border p-4 flex gap-3 items-center transition-all ${selected ? "border-primary-500" : "border-gray-100"} shadow-sm`}>
      <input type="checkbox" checked={selected} onChange={onToggle} className="w-4 h-4 accent-primary-600" aria-label={`Sélectionner candidature #${candidature.id}`} />
      <div className="flex-1">
        <p className="text-sm font-medium text-gray-900">{candidature.offre_titre ?? `Offre #${candidature.offre_id}`}</p>
        <p className="text-xs text-gray-500">
          {candidature.offre_entreprise ?? ""} · {candidature.lettre_id ? "Lettre prête" : "Lettre en préparation"}
          {candidature.envoyee_le ? ` · envoyée le ${new Date(candidature.envoyee_le).toLocaleDateString("fr-FR")}` : ""}
        </p>
      </div>
      <select
        aria-label={`Statut de la candidature #${candidature.id}`}
        className={`text-xs font-medium px-3 py-1 rounded-full border-0 cursor-pointer ${STATUT_COLORS[candidature.statut] ?? "bg-gray-100 text-gray-700"}`}
        value={candidature.statut}
        onChange={(e) => onStatusChange(e.target.value)}
      >
        {STATUTS.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <button onClick={onPostuler} disabled={!candidature.lettre_id || postulerPending}
        className="text-sm bg-primary-600 text-white px-3 py-1 rounded-lg hover:bg-primary-700 disabled:opacity-40">
        Postuler
      </button>
    </div>
  );
}
