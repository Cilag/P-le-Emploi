"use client";
import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  copierTexte, errorMessage, getAnnonce, getAnnonces, getEtatAppartements, lireAlertesMaintenant,
  relancerAnalyse, updateAnnonceStatut, type Annonce,
} from "@/lib/api";

const STATUTS: Record<string, string> = {
  a_contacter: "À contacter", contacte: "Contacté", visite: "Visite prévue", refuse: "Refusé", retenu: "Retenu",
};
const DRAPEAUX: Record<string, string> = {
  charges_inconnues: "charges inconnues", loyer_inconnu: "loyer inconnu",
  pieces_inconnues: "pièces inconnues", ville_inconnue: "ville à vérifier",
};

const couleurNote = (n: number | null) =>
  n === null
    ? "bg-gray-100 text-gray-500"
    : n >= 8
      ? "bg-green-100 text-green-800"
      : n >= 5
        ? "bg-yellow-100 text-yellow-800"
        : "bg-red-100 text-red-800";

// Un lien venu d'un e-mail n'est cliquable que s'il est en http(s) (jamais « javascript: »).
const lienSur = (lien: string | null) => (lien && /^https?:\/\//i.test(lien) ? lien : null);

function ilYa(iso: string | null): { texte: string; minutes: number | null } {
  if (!iso) return { texte: "jamais", minutes: null };
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  return { texte: minutes < 1 ? "à l'instant" : `il y a ${minutes} min`, minutes };
}

export default function AppartementsPage() {
  const qc = useQueryClient();
  const [filtres, setFiltres] = useState({ statut: "", ville: "", note_min: "" });
  const [ouverte, setOuverte] = useState<Annonce | null>(null);

  const { data: annonces = [], isLoading, isError, error } = useQuery({
    queryKey: ["annonces", filtres],
    queryFn: () => getAnnonces(Object.fromEntries(Object.entries(filtres).filter(([, v]) => v))),
    refetchInterval: 60_000,
  });
  const { data: etat } = useQuery({ queryKey: ["etat-appartements"], queryFn: getEtatAppartements, refetchInterval: 60_000 });

  const rafraichir = () => {
    qc.invalidateQueries({ queryKey: ["annonces"] });
    qc.invalidateQueries({ queryKey: ["etat-appartements"] });
  };
  const lire = useMutation({
    mutationFn: lireAlertesMaintenant,
    onSuccess: () => {
      toast.success("Lecture des alertes lancée");
      setTimeout(rafraichir, 15_000);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const ouvrir = useMutation({
    mutationFn: (id: number) => getAnnonce(id),
    onSuccess: (a) => {
      setOuverte(a);
      qc.invalidateQueries({ queryKey: ["annonces"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const statut = useMutation({
    mutationFn: ({ id, s }: { id: number; s: string }) => updateAnnonceStatut(id, s),
    onSuccess: (a) => {
      setOuverte(a);
      qc.invalidateQueries({ queryKey: ["annonces"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const relancer = useMutation({
    mutationFn: (id: number) => relancerAnalyse(id),
    onSuccess: () => {
      toast.success("Analyse relancée");
      setOuverte(null);
      setTimeout(rafraichir, 20_000);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const derniere = ilYa(etat?.derniere_lecture ?? null);
  const enAlerte = !etat || etat.dernier_statut === "erreur" || derniere.minutes === null || derniere.minutes > 15;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-900">Appartements</h1>
        <div className="flex items-center gap-3 text-sm flex-wrap">
          <span className={enAlerte ? "text-red-600" : "text-gray-500"}>
            Dernière lecture des alertes : {derniere.texte}
            {etat?.derniere_erreur ? ` — ${etat.derniere_erreur}` : ""}
          </span>
          <button
            onClick={() => lire.mutate()}
            disabled={lire.isPending}
            className="bg-primary-600 text-white px-3 py-1.5 rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            Lire maintenant
          </button>
          <Link href="/appartements/dossier" className="text-primary-600 hover:underline">Mon dossier</Link>
        </div>
      </div>

      {etat && etat.alertes_abandonnees.length > 0 && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
          {etat.alertes_abandonnees.length} alerte(s) n&apos;ont pas pu être lues après 3 essais (leurs annonces
          manquent) :
          <ul className="list-disc pl-5 mt-1">
            {etat.alertes_abandonnees.map((a, i) => (
              <li key={i}>{a.sujet ?? "sans sujet"} — {a.erreur ?? "erreur inconnue"}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex gap-3 flex-wrap">
        <select
          aria-label="Filtrer par statut"
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={filtres.statut}
          onChange={(e) => setFiltres((f) => ({ ...f, statut: e.target.value }))}
        >
          <option value="">Tous statuts</option>
          {Object.entries(STATUTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input
          aria-label="Filtrer par ville"
          placeholder="Ville..."
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={filtres.ville}
          onChange={(e) => setFiltres((f) => ({ ...f, ville: e.target.value }))}
        />
        <select
          aria-label="Note minimum"
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={filtres.note_min}
          onChange={(e) => setFiltres((f) => ({ ...f, note_min: e.target.value }))}
        >
          <option value="">Toutes notes</option>
          {[5, 6, 7, 8, 9].map((n) => <option key={n} value={n}>{n}/10 et plus</option>)}
        </select>
      </div>

      {isError ? (
        <div className="text-center py-12 text-red-600">Impossible de charger les annonces : {errorMessage(error)}</div>
      ) : isLoading ? (
        <div className="text-center py-12 text-gray-500">Chargement...</div>
      ) : annonces.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          Aucune annonce pour l&apos;instant. Vérifiez vos alertes et le libellé Gmail « Appartements ».
        </div>
      ) : (
        <div className="space-y-3">
          {annonces.map((a) => (
            <button
              key={a.id}
              onClick={() => ouvrir.mutate(a.id)}
              className="w-full text-left bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex gap-4 items-start hover:border-primary-300"
            >
              <span className={`shrink-0 text-sm font-bold px-2.5 py-1 rounded-full ${couleurNote(a.note)}`}>
                {a.note === null ? "?" : `${a.note}/10`}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-gray-900 truncate">{a.titre}</h3>
                  {!a.vue && <span className="text-xs bg-primary-100 text-primary-700 px-2 py-0.5 rounded-full">Nouveau</span>}
                </div>
                <p className="text-sm text-gray-600">
                  {a.loyer_retenu !== null ? `${Math.round(a.loyer_retenu)} €` : "loyer ?"}
                  {a.surface !== null ? ` · ${a.surface} m²` : ""}
                  {a.pieces !== null ? ` · ${a.pieces} p.` : ""}
                  {a.ville ? ` · ${a.ville}` : ""}
                  {a.quartier ? ` (${a.quartier})` : ""}
                </p>
                <p className="text-xs text-gray-400">
                  {a.sites}
                  {a.drapeaux ? ` · ${a.drapeaux.split(",").map((d) => DRAPEAUX[d] ?? d).join(", ")}` : ""}
                  {a.alertes ? ` · ⚠ ${a.alertes.split("\n")[0]}` : ""}
                </p>
              </div>
              <span className="shrink-0 text-xs text-gray-500">{STATUTS[a.statut] ?? a.statut}</span>
            </button>
          ))}
        </div>
      )}

      {ouverte && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl shadow-xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-bold text-lg">{ouverte.titre}</h2>
              <span className={`shrink-0 text-sm font-bold px-2.5 py-1 rounded-full ${couleurNote(ouverte.note)}`}>
                {ouverte.note === null ? "?" : `${ouverte.note}/10`}
              </span>
            </div>
            {ouverte.resume && <p className="text-sm text-gray-700">{ouverte.resume}</p>}
            {ouverte.alertes && (
              <ul className="text-sm text-orange-700 list-disc pl-5">
                {ouverte.alertes.split("\n").map((l, i) => <li key={i}>{l}</li>)}
              </ul>
            )}
            {ouverte.analyse_erreur && (
              <p className="text-sm text-red-600">Analyse impossible : {ouverte.analyse_erreur}</p>
            )}
            {ouverte.message && (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-gray-700">Message au propriétaire</h3>
                <p className="text-sm whitespace-pre-wrap bg-gray-50 rounded-lg p-3">{ouverte.message}</p>
              </div>
            )}
            <div className="flex flex-wrap gap-2 items-center">
              {lienSur(ouverte.lien) && (
                <a
                  href={lienSur(ouverte.lien) ?? undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-primary-600 text-white px-3 py-2 rounded-lg text-sm"
                >
                  Ouvrir l&apos;annonce
                </a>
              )}
              {ouverte.message && (
                <button
                  onClick={() =>
                    copierTexte(ouverte.message ?? "").then(
                      () => toast.success("Message copié"),
                      () => toast.error("Copie impossible : sélectionnez le texte manuellement"),
                    )
                  }
                  className="border px-3 py-2 rounded-lg text-sm"
                >
                  Copier le message
                </button>
              )}
              {ouverte.analyse_erreur && (
                <button
                  onClick={() => relancer.mutate(ouverte.id)}
                  disabled={relancer.isPending}
                  className="border px-3 py-2 rounded-lg text-sm disabled:opacity-50"
                >
                  Relancer l&apos;analyse
                </button>
              )}
              <select
                aria-label="Statut de l'annonce"
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={ouverte.statut}
                onChange={(e) => statut.mutate({ id: ouverte.id, s: e.target.value })}
              >
                {Object.entries(STATUTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="flex justify-end">
              <button onClick={() => setOuverte(null)} className="px-4 py-2 text-gray-600">Fermer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
