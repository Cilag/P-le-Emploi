"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { errorMessage, getDossier, saveDossier } from "@/lib/api";

const MAX = 3000;

export default function DossierPage() {
  const { data, isError, error } = useQuery({ queryKey: ["dossier"], queryFn: getDossier });
  const [texte, setTexte] = useState("");
  useEffect(() => {
    if (data) setTexte(data.texte);
  }, [data]);
  const enregistrer = useMutation({
    mutationFn: () => saveDossier(texte),
    onSuccess: () => toast.success("Dossier enregistré"),
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="space-y-4 max-w-3xl">
      <Link href="/appartements" className="text-sm text-primary-600 hover:underline">← Appartements</Link>
      <h1 className="text-2xl font-bold text-gray-900">Mon dossier locataire</h1>
      <p className="text-sm text-gray-600">
        Situation, revenus, garant, date d&apos;entrée souhaitée, courte présentation. Hermes s&apos;en sert pour
        rédiger les messages aux propriétaires ; il n&apos;invente rien qui n&apos;y figure pas.
      </p>
      {isError && <p className="text-red-600 text-sm">Impossible de charger le dossier : {errorMessage(error)}</p>}
      <textarea
        aria-label="Dossier locataire"
        rows={12}
        maxLength={MAX}
        className="w-full border border-gray-200 rounded-lg p-3 text-sm"
        value={texte}
        onChange={(e) => setTexte(e.target.value)}
      />
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">{texte.length} / {MAX}</span>
        <button
          onClick={() => enregistrer.mutate()}
          disabled={enregistrer.isPending}
          className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          Enregistrer
        </button>
      </div>
    </div>
  );
}
